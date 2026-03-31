"""Console dashboard — Rich terminal display of live bot state.

This is the actual dashboard from the CryptoGuardian production system.
Uses the `rich` library to display a live-refreshing terminal UI with:
- Account balance, equity, drawdown, daily PnL
- Open positions table with real-time P/L
- System status (engines, kill switch, WebSocket stats)
- Recent trade history

Usage:
    # In production, the dashboard is started as part of the main loop:
    dashboard = Dashboard()
    dashboard.set_data_source(bot)
    await dashboard.start()

    # For the demo GIF, run with mock data:
    python dashboard_demo.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Protocol

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError:
    raise ImportError("Install rich: pip install rich")


class DashboardDataSource(Protocol):
    """Protocol for providing data to the dashboard."""
    def get_dashboard_data(self) -> dict[str, Any]: ...


class Dashboard:
    """Terminal dashboard with live refresh."""

    def __init__(self, refresh_interval: float = 5.0) -> None:
        self._interval = refresh_interval
        self._data_source: DashboardDataSource | None = None
        self._running = False

    def set_data_source(self, source: DashboardDataSource) -> None:
        self._data_source = source

    async def start(self) -> None:
        self._running = True
        console = Console()

        with Live(console=console, refresh_per_second=1, screen=False) as live:
            while self._running:
                data = {}
                if self._data_source:
                    data = self._data_source.get_dashboard_data()
                layout = self._build_layout(data)
                live.update(layout)
                await asyncio.sleep(self._interval)

    def stop(self) -> None:
        self._running = False

    def _build_layout(self, data: dict[str, Any]) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(self._build_header(data), size=3),
            Layout(name="body", ratio=1),
        )
        layout["body"].split_row(
            Layout(self._build_positions(data), ratio=2),
            Layout(self._build_sidebar(data), ratio=1),
        )
        return layout

    def _build_header(self, data: dict[str, Any]) -> Panel:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        balance = data.get("balance", 0)
        equity = data.get("equity", 0)
        dd = data.get("drawdown_pct", 0)
        daily_pnl = data.get("daily_pnl", 0)
        pnl_color = "green" if daily_pnl >= 0 else "red"

        text = Text()
        text.append(f"  Balance: ${balance:,.2f}  |  Equity: ${equity:,.2f}  |  ")
        text.append(f"DD: {dd:.2f}%  |  ", style="yellow" if dd > 3 else "green")
        text.append(f"Daily PnL: ${daily_pnl:+,.2f}  |  ", style=pnl_color)
        text.append(f"{now}")

        return Panel(text, title="[bold]CryptoGuardian[/bold]", border_style="blue")

    def _build_positions(self, data: dict[str, Any]) -> Panel:
        table = Table(title="Open Positions", expand=True)
        table.add_column("Symbol", style="cyan")
        table.add_column("Side")
        table.add_column("Entry", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("PnL", justify="right")
        table.add_column("SL", justify="right")
        table.add_column("TP", justify="right")
        table.add_column("Bars", justify="right")

        for pos in data.get("positions", []):
            pnl = pos.get("pnl", 0)
            pnl_str = f"${pnl:+,.2f}"
            pnl_style = "green" if pnl >= 0 else "red"
            side_style = "green" if pos.get("side") == "long" else "red"

            table.add_row(
                pos.get("symbol", ""),
                Text(pos.get("side", "").upper(), style=side_style),
                f"${pos.get('entry_price', 0):,.2f}",
                f"${pos.get('current_price', 0):,.2f}",
                Text(pnl_str, style=pnl_style),
                f"${pos.get('stop_loss', 0):,.2f}",
                f"${pos.get('take_profit', 0):,.2f}",
                str(pos.get("bars", 0)),
            )

        if not data.get("positions"):
            table.add_row("—", "—", "—", "—", "—", "—", "—", "—")

        return Panel(table)

    def _build_sidebar(self, data: dict[str, Any]) -> Panel:
        table = Table(title="Status", expand=True, show_header=False)
        table.add_column("Key", style="dim")
        table.add_column("Value")

        engines = data.get("engines", {})
        smc_status = "ON" if engines.get("smc_active", False) else "OFF"
        pairs_status = "ON" if engines.get("pairs_active", False) else "OFF"
        kill_status = "OFF" if not data.get("kill_switch", False) else "ON"

        ws = data.get("websocket", {})
        ws_status = "Connected" if ws.get("connected", False) else "Disconnected"

        table.add_row("SMC Engine", Text(smc_status, style="green" if smc_status == "ON" else "red"))
        table.add_row("Pairs Engine", Text(pairs_status, style="green" if pairs_status == "ON" else "red"))
        table.add_row("Kill Switch", Text(kill_status, style="red" if kill_status == "ON" else "green"))
        table.add_row("WebSocket", Text(ws_status, style="green" if ws_status == "Connected" else "red"))
        table.add_row("WS Latency", f"{ws.get('latency_ms', 0):.0f}ms")
        table.add_row("Msg/sec", str(ws.get("msg_per_sec", 0)))
        table.add_row("", "")
        table.add_row("[bold]Recent Trades[/bold]", "")

        for t in data.get("recent_trades", [])[:5]:
            pnl = t.get("pnl", 0)
            style = "green" if pnl >= 0 else "red"
            table.add_row(f"  {t.get('symbol', '')}", Text(f"${pnl:+,.2f}", style=style))

        return Panel(table)
