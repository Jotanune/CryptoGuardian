"""Async utilities — retry with exponential backoff, lifecycle management.

This module is used across the entire CryptoGuardian system for:
- Retrying flaky exchange API calls with configurable backoff
- Managing async component lifecycles (start/stop/shutdown)
- Running concurrent tasks with global timeouts
"""

from __future__ import annotations

import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, TypeVar

from loguru import logger

T = TypeVar("T")


@dataclass
class RetryPolicy:
    """Configuration for exponential backoff retry."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True


async def async_retry(
    func: Callable[..., Coroutine[Any, Any, T]],
    policy: RetryPolicy,
    *args: Any,
    **kwargs: Any,
) -> T:
    """Execute an async function with exponential backoff retry.

    Formula: delay = min(base_delay * 2^attempt, max_delay) * jitter

    Raises the original exception after exhausting all retries.
    """
    last_exc: BaseException | None = None
    for attempt in range(policy.max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt == policy.max_retries - 1:
                break
            delay = min(policy.base_delay * (2**attempt), policy.max_delay)
            if policy.jitter:
                delay *= 0.5 + random.random()  # noqa: S311
            logger.warning(
                "Retry {}/{} for {} after {:.1f}s — {}",
                attempt + 1, policy.max_retries, func.__name__, delay, exc,
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


async def gather_with_timeout(
    coros: list[Coroutine[Any, Any, T]],
    timeout: float,
) -> list[T | BaseException]:
    """Run coroutines concurrently with a global timeout."""
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*coros, return_exceptions=True),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.error("gather_with_timeout: exceeded {:.1f}s", timeout)
        raise
    return results  # type: ignore[return-value]


class AsyncComponent(ABC):
    """Base class for components with async lifecycle management.

    Provides start/stop/shutdown event pattern used by:
    - WebSocketClient
    - HealthChecker
    - TelegramAlerter
    - Dashboard
    """

    def __init__(self) -> None:
        self._started = False
        self._shutdown_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._started and not self._shutdown_event.is_set()

    @abstractmethod
    async def start(self) -> None:
        self._started = True

    @abstractmethod
    async def stop(self) -> None:
        self._shutdown_event.set()
        self._started = False

    async def wait_for_shutdown(self) -> None:
        await self._shutdown_event.wait()
