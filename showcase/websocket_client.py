"""WebSocket client for Hyperliquid Info API with auto-reconnection.

This is a sanitized excerpt from the production CryptoGuardian bot.
Demonstrates async WebSocket management with exponential backoff,
heartbeat monitoring, and channel-based message dispatching.

Full system uses this to maintain 29 concurrent subscriptions across
14 cryptocurrency perpetuals on Hyperliquid DEX.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from websockets import ClientConnection

import orjson
import websockets
from loguru import logger

# ── Endpoints ────────────────────────────────────────────────────────
HL_WS_MAINNET = "wss://api.hyperliquid.xyz/ws"
HL_WS_TESTNET = "wss://api.hyperliquid-testnet.xyz/ws"


class WebSocketClient:
    """Persistent WebSocket connection to Hyperliquid Info API.

    Features:
    - Auto-reconnection with exponential backoff (5s → 120s cap)
    - Heartbeat/ping to detect dead connections
    - Channel-based message dispatching to registered async handlers
    - Rate-limited subscription management with auto-resubscribe
    - Connection stability tracking (reset counter after 60s uptime)
    """

    def __init__(
        self,
        testnet: bool = False,
        max_reconnect_attempts: int = 10,
        reconnect_delay: float = 5.0,
        heartbeat_interval: float = 30.0,
    ) -> None:
        self._url = HL_WS_TESTNET if testnet else HL_WS_MAINNET
        self._max_reconnect = max_reconnect_attempts
        self._reconnect_delay = reconnect_delay
        self._heartbeat_interval = heartbeat_interval
        self._ws: ClientConnection | None = None
        self._handlers: dict[str, list[Callable[..., Coroutine[Any, Any, None]]]] = {}
        self._subscriptions: list[dict[str, Any]] = []
        self._reconnect_count = 0
        self._messages_received = 0
        self._last_message_time: float = 0.0
        self._shutdown_event = asyncio.Event()

    # ── Properties ────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        if self._ws is None:
            return False
        return self._ws.close_code is None

    @property
    def messages_received(self) -> int:
        return self._messages_received

    @property
    def last_message_age(self) -> float:
        """Seconds since last message was received."""
        if self._last_message_time == 0:
            return float("inf")
        return time.time() - self._last_message_time

    # ── Public API ────────────────────────────────────────────────────

    def on(
        self,
        channel: str,
        handler: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        """Register an async handler for a specific channel (l2Book, trades, etc.)."""
        self._handlers.setdefault(channel, []).append(handler)

    async def subscribe(self, subscription: dict[str, Any]) -> None:
        """Subscribe to a Hyperliquid channel.

        Example: {"type": "l2Book", "coin": "BTC"}
        """
        msg = {"method": "subscribe", "subscription": subscription}
        self._subscriptions.append(subscription)
        if self.is_connected:
            await self._send(msg)

    async def unsubscribe(self, subscription: dict[str, Any]) -> None:
        """Unsubscribe from a channel."""
        msg = {"method": "unsubscribe", "subscription": subscription}
        if subscription in self._subscriptions:
            self._subscriptions.remove(subscription)
        if self.is_connected:
            await self._send(msg)

    async def start(self) -> None:
        """Start the WebSocket connection loop."""
        logger.info("WebSocket client starting — {}", self._url)
        await self._connection_loop()

    async def stop(self) -> None:
        """Gracefully close the WebSocket connection."""
        logger.info("WebSocket client stopping")
        self._shutdown_event.set()
        if self._ws:
            await self._ws.close()
            self._ws = None

    # ── Connection Loop (exponential backoff) ─────────────────────────

    async def _connection_loop(self) -> None:
        """Main connection loop with auto-reconnection.

        Key design decisions:
        - Exponential backoff: 5s → 10s → 20s → ... → 120s cap
        - Reset reconnect counter after 60s of stable connection
        - Concurrent resubscribe + receive to avoid message loss
        - Critical log + exit after max attempts exhausted
        """
        while not self._shutdown_event.is_set():
            connect_time: float = 0.0
            try:
                async with websockets.connect(
                    self._url,
                    ping_interval=self._heartbeat_interval,
                    ping_timeout=10,
                    max_size=10 * 1024 * 1024,  # 10 MB
                ) as ws:
                    self._ws = ws
                    connect_time = asyncio.get_event_loop().time()
                    logger.info("WebSocket connected to {}", self._url)

                    # Run resubscribe concurrently with receive_loop
                    # so incoming data is consumed while we send subscriptions
                    resub_task = asyncio.create_task(self._resubscribe())
                    try:
                        await self._receive_loop(ws)
                    finally:
                        if not resub_task.done():
                            resub_task.cancel()

            except websockets.ConnectionClosed as e:
                logger.warning(
                    "WebSocket disconnected: code={} reason={}",
                    e.code,
                    e.reason,
                )
            except Exception as e:
                logger.error("WebSocket error: {}", e)
            finally:
                self._ws = None
                # Reset reconnect counter if connection was stable (>60s)
                loop_time = asyncio.get_event_loop().time()
                uptime = loop_time - connect_time if connect_time else 0
                if uptime > 60:
                    self._reconnect_count = 0

            if self._shutdown_event.is_set():
                break

            # Reconnect with exponential backoff
            self._reconnect_count += 1
            if self._reconnect_count > self._max_reconnect:
                logger.critical(
                    "Max reconnection attempts ({}) reached — giving up",
                    self._max_reconnect,
                )
                break

            delay = min(
                self._reconnect_delay * (2 ** (self._reconnect_count - 1)),
                120.0,  # Cap at 2 minutes
            )
            logger.info(
                "Reconnecting in {:.1f}s (attempt {}/{})",
                delay,
                self._reconnect_count,
                self._max_reconnect,
            )
            await asyncio.sleep(delay)

    # ── Message Processing ────────────────────────────────────────────

    async def _receive_loop(self, ws: ClientConnection) -> None:
        """Process incoming messages until disconnect."""
        async for raw in ws:
            if self._shutdown_event.is_set():
                break
            self._messages_received += 1
            self._last_message_time = time.time()

            try:
                data = orjson.loads(raw)
            except (orjson.JSONDecodeError, ValueError):
                preview = raw[:200] if isinstance(raw, (str, bytes)) else raw
                logger.error("Malformed JSON: {}", preview)
                continue

            channel = data.get("channel")
            if channel:
                await self._dispatch(channel, data)

    async def _dispatch(self, channel: str, data: dict[str, Any]) -> None:
        """Dispatch a parsed message to all registered handlers for a channel."""
        handlers = self._handlers.get(channel, [])
        for handler in handlers:
            try:
                await handler(data)
            except Exception:
                logger.exception("Handler error for channel {}", channel)

    async def _resubscribe(self) -> None:
        """Re-subscribe to all channels after reconnection."""
        for sub in self._subscriptions:
            msg = {"method": "subscribe", "subscription": sub}
            await self._send(msg)
            await asyncio.sleep(0.2)  # Pace subscriptions to avoid rate limits

    async def _send(self, msg: dict[str, Any]) -> None:
        """Send a JSON message over the WebSocket."""
        if self._ws is not None:
            try:
                # Use str (text frame) — Hyperliquid rejects binary frames
                await self._ws.send(orjson.dumps(msg).decode())
            except Exception as e:
                logger.warning("WS send error: {}", e)
