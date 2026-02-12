from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class RetryableError(RuntimeError):
    pass


async def retry_async(
    fn: Callable[[], Awaitable],
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
) -> object:
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == max_attempts - 1:
                break
            await asyncio.sleep(base_delay_seconds * (2**attempt))
    raise RetryableError(str(last_error)) from last_error
