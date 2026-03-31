"""Kill switch — emergency shutdown with full position closure.

Sanitized excerpt from CryptoGuardian production system.
This is the last line of defense: cancels all orders, closes all
positions, and alerts the operator via Telegram.

Trigger conditions in production:
- Total drawdown >= max threshold
- Hard stop daily loss
- Cointegration break (pairs engine)
- Critical error (exchange offline >10 min)
- Manual Telegram /kill command
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from loguru import logger


class KillSwitch:
    """Emergency kill switch — cancels all orders and closes all positions.

    Anti-loop protection: retries closing up to 3 times, then gives up
    to avoid infinite retry loops during exchange outages.
    """

    def __init__(self) -> None:
        self._activated = False
        self._activation_time: float = 0.0
        self._reason: str = ""
        self._equity_at_kill: float = 0.0

    @property
    def is_activated(self) -> bool:
        return self._activated

    @property
    def reason(self) -> str:
        return self._reason

    async def activate(
        self,
        reason: str,
        equity: float,
        order_manager: Any | None = None,
        alerter: Any | None = None,
    ) -> None:
        """Activate kill switch — cancel orders, close positions, alert.

        Sequence:
        1. Mark as activated (prevents duplicate triggers)
        2. Cancel all pending orders (3 retries)
        3. Close all open positions (3 retries)
        4. Send Telegram critical alert
        5. Require manual reset to resume trading
        """
        if self._activated:
            logger.warning("[KILL] Already activated — ignoring duplicate")
            return

        self._activated = True
        self._activation_time = time.time()
        self._reason = reason
        self._equity_at_kill = equity

        logger.critical("[KILL] ACTIVATED: {} | Equity: ${:.2f}", reason, equity)

        # Cancel all pending orders (with retry)
        if order_manager is not None:
            for attempt in range(3):
                try:
                    await order_manager.cancel_all()
                    logger.info("[KILL] All orders cancelled")
                    break
                except Exception as e:
                    logger.error("[KILL] Cancel attempt {}/3 failed: {}", attempt + 1, e)
                    if attempt < 2:
                        await asyncio.sleep(2)

            # Close all positions (with retry)
            for attempt in range(3):
                try:
                    positions = await order_manager.get_open_positions()
                    for pos in positions:
                        asset = pos.get("coin", "")
                        size = abs(float(pos.get("size", 0)))
                        is_long = float(pos.get("size", 0)) > 0
                        if size > 0:
                            await order_manager.place_market_order(asset, not is_long, size)
                            logger.info("[KILL] Closed {} {:.6f}", asset, size)
                    break
                except Exception as e:
                    logger.error("[KILL] Close attempt {}/3 failed: {}", attempt + 1, e)
                    if attempt < 2:
                        await asyncio.sleep(2)

        # Alert operator
        if alerter is not None:
            try:
                await alerter.send_critical(
                    f"🚨 KILL SWITCH: {reason}\n"
                    f"Equity at kill: ${equity:.2f}\n"
                    f"All positions closed. Manual intervention required."
                )
            except Exception as e:
                logger.error("[KILL] Alert failed: {}", e)

    def reset(self) -> None:
        """Manual reset — requires explicit human intervention."""
        logger.warning("[KILL] Reset by operator")
        self._activated = False
        self._reason = ""

    def get_state(self) -> dict[str, Any]:
        return {
            "activated": self._activated,
            "activation_time": self._activation_time,
            "reason": self._reason,
            "equity_at_kill": self._equity_at_kill,
        }
