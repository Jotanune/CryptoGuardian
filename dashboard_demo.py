"""Dashboard demo — run with mock data for GIF recording.

Usage:
    pip install rich
    python dashboard_demo.py

    # Record GIF (requires asciinema + agg, or terminalizer):
    # Option 1: asciinema
    #   asciinema rec demo.cast -c "python dashboard_demo.py"
    #   agg demo.cast demo.gif --theme monokai
    #
    # Option 2: terminalizer
    #   terminalizer record demo --command "python dashboard_demo.py"
    #   terminalizer render demo
    #
    # Option 3: VHS (charmbracelet)
    #   vhs demo.tape
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any

from showcase.dashboard import Dashboard


class MockDataSource:
    """Simulates live bot data with realistic price movements."""

    def __init__(self) -> None:
        self._start = time.time()
        self._btc_base = 87_412.50
        self._eth_base = 2_041.80
        self._sol_base = 139.22

    def get_dashboard_data(self) -> dict[str, Any]:
        elapsed = time.time() - self._start
        drift = elapsed * 0.3  # Slow upward drift

        btc = self._btc_base + random.uniform(-50, 80) + drift
        eth = self._eth_base + random.uniform(-5, 8) + drift * 0.02
        sol = self._sol_base + random.uniform(-0.5, 0.8) + drift * 0.01

        btc_pnl = (btc - 86_200) * 0.04  # ~0.04 BTC position
        pairs_pnl = random.uniform(15, 35)

        return {
            "balance": 2_847.32 + drift * 0.5,
            "equity": 2_847.32 + btc_pnl + pairs_pnl + drift * 0.5,
            "drawdown_pct": max(0, 1.85 - drift * 0.01),
            "daily_pnl": btc_pnl + pairs_pnl - 12.40,
            "positions": [
                {
                    "symbol": "BTC",
                    "side": "long",
                    "entry_price": 86_200.00,
                    "current_price": btc,
                    "pnl": btc_pnl,
                    "stop_loss": 87_050.00,
                    "take_profit": 89_500.00,
                    "bars": 14 + int(elapsed / 60),
                },
                {
                    "symbol": "INJ/OP",
                    "side": "short",
                    "entry_price": 0.42,
                    "current_price": max(-0.5, 0.42 - random.uniform(0.1, 0.3)),
                    "pnl": pairs_pnl,
                    "stop_loss": 0.85,
                    "take_profit": -0.20,
                    "bars": 8 + int(elapsed / 60),
                },
                {
                    "symbol": "AVAX/NEAR",
                    "side": "short",
                    "entry_price": 1.82,
                    "current_price": max(0.5, 1.82 - random.uniform(0.1, 0.4)),
                    "pnl": random.uniform(5, 20),
                    "stop_loss": 2.50,
                    "take_profit": 0.00,
                    "bars": int(elapsed / 60),
                },
            ],
            "engines": {"smc_active": True, "pairs_active": True},
            "kill_switch": False,
            "websocket": {
                "connected": True,
                "latency_ms": random.uniform(35, 55),
                "msg_per_sec": random.randint(40, 80),
            },
            "recent_trades": [
                {"symbol": "ETH", "pnl": 34.20},
                {"symbol": "SOL", "pnl": -18.50},
                {"symbol": "BTC/ETH", "pnl": 22.80},
                {"symbol": "BTC", "pnl": 45.10},
                {"symbol": "DOGE/SHIB", "pnl": -8.30},
            ],
        }


async def main() -> None:
    print("CryptoGuardian Dashboard Demo — Press Ctrl+C to stop\n")
    source = MockDataSource()
    dashboard = Dashboard(refresh_interval=2.0)
    dashboard.set_data_source(source)

    try:
        await dashboard.start()
    except KeyboardInterrupt:
        dashboard.stop()


if __name__ == "__main__":
    asyncio.run(main())
