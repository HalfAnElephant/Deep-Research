import pytest

from app.services.retry import RetryableError, retry_async


@pytest.mark.asyncio
async def test_retry_async_success_after_failures() -> None:
    counter = {"n": 0}

    async def fn():
        counter["n"] += 1
        if counter["n"] < 3:
            raise RuntimeError("temporary")
        return "ok"

    result = await retry_async(fn, max_attempts=3, base_delay_seconds=0.001)
    assert result == "ok"


@pytest.mark.asyncio
async def test_retry_async_raises_after_max_attempts() -> None:
    async def fn():
        raise RuntimeError("always fail")

    with pytest.raises(RetryableError):
        await retry_async(fn, max_attempts=2, base_delay_seconds=0.001)
