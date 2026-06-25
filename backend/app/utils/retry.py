"""Generic async retry decorator with exponential backoff."""

import asyncio
import functools
import logging
from typing import Any, Callable, Type

logger = logging.getLogger(__name__)


def async_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    exponential: bool = True,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
):
    """Decorator that retries an async function on specified exceptions.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds before first retry.
        exponential: If True, delay doubles on each retry.
        exceptions: Tuple of exception types to catch and retry.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                        raise
                    delay = base_delay * (2**attempt if exponential else 1)
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator
