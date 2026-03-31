"""Risk Manager — Multi-layered capital protection system.

This is a sanitized excerpt from the production CryptoGuardian bot.
All specific thresholds and parameters have been replaced with
configurable placeholders. The architecture and logic are real.

Production system uses this to protect a live Hyperliquid account
with 8 independent risk checks before every trade.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from loguru import logger


class RiskManager:
    """Central risk management with daily limits, drawdown monitoring,
    circuit breaker, and correlation exposure checks.

    8 independent pre-trade gates:
    1. Hard stop check (account frozen)
    2. Soft stop check (daily loss limit)
    3. Max open positions
    4. Daily loss percentage
    5. Total drawdown vs peak
    6. Portfolio heat (sum of all open risk)
    7. Correlated exposure (max positions per asset)
    8. Circuit breaker (consecutive losses)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        # All parameters loaded from environment / config file
        # Exact values are proprietary — shown here as config keys
        self._max_risk_per_trade = config["max_risk_per_trade_pct"] / 100.0
        self._max_daily_loss = config["max_daily_loss_pct"] / 100.0
        self._max_daily_loss_hard = config["max_daily_loss_hard_pct"] / 100.0
        self._max_total_dd = config["max_total_drawdown_pct"] / 100.0
        self._dd_scale_threshold = config["dd_scale_down_threshold"] / 100.0
        self._max_open_positions = config["max_open_positions"]
        self._max_correlated = config["max_correlated_exposure"]
        self._max_heat = config["max_portfolio_heat_pct"] / 100.0
        self._max_consecutive_losses = config["max_consecutive_losses"]

        # State
        self.equity_peak: float = 0.0
        self.daily_pnl: float = 0.0
        self.daily_reference_equity: float = 0.0
        self.current_equity: float = 0.0
        self.risk_multiplier: float = 1.0
        self.is_soft_stopped: bool = False
        self.is_hard_stopped: bool = False
        self.consecutive_losses: int = 0
        self._last_day: int = -1
        self._open_positions: list[dict[str, Any]] = []

    # ─── Daily Reset ──────────────────────────────────────────────────
    # LESSON from PropGuardian Bug #33: this MUST execute BEFORE
    # soft/hard stop checks, otherwise the bot stays dead forever
    # after a bad day. The fix was to move check_new_day() to the
    # very first line of the main loop, before any early returns.

    def check_new_day(self, current_equity: float) -> bool:
        """Detect UTC day change and reset daily state."""
        now = datetime.now(UTC)
        today = now.timetuple().tm_yday

        if today != self._last_day:
            old_pnl = self.daily_pnl
            self.daily_pnl = 0.0
            self.is_soft_stopped = False
            self.is_hard_stopped = False
            self.daily_reference_equity = current_equity
            self.equity_peak = max(self.equity_peak, current_equity)
            self.current_equity = current_equity
            self._last_day = today

            logger.info(
                "[RISK] New day: equity ${:.2f}, peak ${:.2f}, DD {:.2f}%, yesterday PnL ${:.2f}",
                current_equity, self.equity_peak,
                self.current_drawdown_pct * 100, old_pnl,
            )
            return True
        return False

    # ─── Drawdown Monitoring ──────────────────────────────────────────

    @property
    def current_drawdown_pct(self) -> float:
        if self.equity_peak <= 0:
            return 0.0
        return (self.equity_peak - self.current_equity) / self.equity_peak

    def update_equity(self, equity: float) -> None:
        """Update equity and check all drawdown thresholds."""
        self.current_equity = equity
        self.equity_peak = max(self.equity_peak, equity)

        if self.daily_reference_equity > 0:
            self.daily_pnl = equity - self.daily_reference_equity

        dd = self.current_drawdown_pct

        # Drawdown scale-down: reduce risk when approaching limits
        if dd >= self._dd_scale_threshold:
            if self.risk_multiplier != 0.5:
                self.risk_multiplier = 0.5
                logger.warning("[RISK] DD scaling: {:.2f}% — risk reduced to 0.5x", dd * 100)
        else:
            if self.risk_multiplier != 1.0:
                self.risk_multiplier = 1.0
                logger.info("[RISK] DD recovered — risk restored to 1.0x")

        # Soft stop (block new trades, manage existing)
        if self.daily_reference_equity > 0:
            daily_loss_pct = -self.daily_pnl / self.daily_reference_equity
            if daily_loss_pct >= self._max_daily_loss and not self.is_soft_stopped:
                self.is_soft_stopped = True
                logger.warning("[RISK] SOFT STOP: daily loss {:.2f}%", daily_loss_pct * 100)
            if daily_loss_pct >= self._max_daily_loss_hard and not self.is_hard_stopped:
                self.is_hard_stopped = True
                logger.error("[RISK] HARD STOP: daily loss {:.2f}%", daily_loss_pct * 100)

        # Total drawdown kill switch
        if dd >= self._max_total_dd:
            self.is_hard_stopped = True
            logger.critical("[RISK] KILL SWITCH: total DD {:.2f}%", dd * 100)

    # ─── Pre-Trade Risk Gates (8 checks) ─────────────────────────────

    def can_open_trade(self, signal: Any) -> tuple[bool, str]:
        """Run all pre-trade risk checks. Returns (allowed, reason)."""

        if self.is_hard_stopped:
            return False, "Hard stop active"
        if self.is_soft_stopped:
            return False, "Soft stop active (daily loss limit)"

        if len(self._open_positions) >= self._max_open_positions:
            return False, f"Max positions ({self._max_open_positions}) reached"

        if self.daily_reference_equity > 0:
            daily_loss_pct = -self.daily_pnl / self.daily_reference_equity
            if daily_loss_pct >= self._max_daily_loss:
                return False, "Daily loss limit reached"

        if self.current_drawdown_pct >= self._max_total_dd:
            return False, "Total drawdown exceeds max"

        heat = self._calculate_portfolio_heat()
        if heat >= self._max_heat:
            return False, f"Portfolio heat ({heat*100:.1f}%) exceeds max"

        base_asset = signal.symbol.split("/")[0] if "/" in signal.symbol else signal.symbol
        if self._count_correlated(base_asset) >= self._max_correlated:
            return False, f"Correlated exposure for {base_asset} at max"

        if self.consecutive_losses >= self._max_consecutive_losses:
            return False, f"Circuit breaker: {self.consecutive_losses} consecutive losses"

        return True, "OK"

    # ─── Position Sizing ──────────────────────────────────────────────

    def calculate_position_size(
        self,
        signal: Any,
        balance: float,
        min_order_usd: float = 10.0,
    ) -> float:
        """Calculate position size in USD based on risk parameters.

        Formula: position_usd = (balance * risk% * dd_multiplier) / sl_distance%

        Uses DynamicAllocator for per-asset risk adjustment based on
        rolling Sharpe ratio (not shown — proprietary allocation logic).
        """
        sl_distance_pct = abs(signal.entry_price - signal.stop_loss) / signal.entry_price
        if sl_distance_pct <= 0:
            return 0.0

        risk_rate = self._max_risk_per_trade  # May be overridden by DynamicAllocator
        risk_amount = balance * risk_rate * self.risk_multiplier
        position_usd = risk_amount / sl_distance_pct

        # Hard clamp: never risk >50% of balance in one position
        position_usd = min(position_usd, balance * 0.5)

        if position_usd < min_order_usd:
            return 0.0

        return position_usd

    # ─── Trade Result Tracking ────────────────────────────────────────

    def record_trade_result(self, pnl: float) -> None:
        """Record a closed trade's PnL for circuit breaker logic."""
        self.daily_pnl += pnl
        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= self._max_consecutive_losses:
                self.is_soft_stopped = True
                logger.warning("[RISK] Circuit breaker: {} losses. Paused.", self.consecutive_losses)
        else:
            self.consecutive_losses = 0

    # ─── Internal Helpers ─────────────────────────────────────────────

    def _calculate_portfolio_heat(self) -> float:
        """Sum of all open positions' risk as % of equity."""
        if self.current_equity <= 0:
            return 0.0
        total_risk = 0.0
        for pos in self._open_positions:
            entry = pos.get("entry_price", 0)
            sl = pos.get("stop_loss", 0)
            volume_usd = pos.get("volume_usd", 0)
            if entry > 0:
                sl_dist = abs(entry - sl) / entry
                total_risk += volume_usd * sl_dist
        return total_risk / self.current_equity

    def _count_correlated(self, base_asset: str) -> int:
        """Count open positions with the same base asset."""
        return sum(1 for p in self._open_positions if base_asset in p.get("symbol", ""))

    def get_state(self) -> dict[str, Any]:
        """Serialize risk state for persistence."""
        return {
            "equity_peak": self.equity_peak,
            "daily_pnl": self.daily_pnl,
            "daily_reference_equity": self.daily_reference_equity,
            "current_equity": self.current_equity,
            "risk_multiplier": self.risk_multiplier,
            "is_soft_stopped": self.is_soft_stopped,
            "is_hard_stopped": self.is_hard_stopped,
            "consecutive_losses": self.consecutive_losses,
        }
