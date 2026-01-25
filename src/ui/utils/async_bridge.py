"""Bridge between Streamlit's sync model and async backend."""

import asyncio
import threading
from concurrent.futures import Future
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")

# Background thread with its own event loop for async operations
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None


def _start_background_loop() -> asyncio.AbstractEventLoop:
    """Start a background thread with an event loop."""
    global _loop, _thread

    if _loop is not None and _thread is not None and _thread.is_alive():
        return _loop

    _loop = asyncio.new_event_loop()

    def run_loop():
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    _thread = threading.Thread(target=run_loop, daemon=True)
    _thread.start()

    return _loop


def run_async(coro: Coroutine[Any, Any, T], timeout: float | None = 30.0) -> T:
    """Execute an async coroutine in Streamlit context.

    Streamlit runs in a synchronous context, but our backend is async.
    This function runs coroutines in a background thread's event loop
    to avoid conflicts with any existing event loops.

    Args:
        coro: The coroutine to execute
        timeout: Maximum seconds to wait (default 30s, None for no timeout)

    Returns:
        The result of the coroutine

    Raises:
        TimeoutError: If the operation exceeds the timeout
    """
    loop = _start_background_loop()

    # Submit the coroutine to the background loop and wait for result
    future: Future[T] = asyncio.run_coroutine_threadsafe(coro, loop)

    # Wait for the result with timeout
    try:
        return future.result(timeout=timeout)
    except TimeoutError:
        future.cancel()
        raise TimeoutError(
            f"Operation timed out after {timeout} seconds. "
            "The service may be slow or unavailable."
        )


async def gather_async(*coros: Coroutine[Any, Any, Any]) -> list[Any]:
    """Run multiple coroutines concurrently.

    Args:
        *coros: Coroutines to run

    Returns:
        List of results from each coroutine
    """
    return await asyncio.gather(*coros, return_exceptions=True)
