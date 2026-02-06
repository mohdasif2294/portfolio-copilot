"""LLM observability: tracing decorators for provider calls and tool execution."""

import functools
import time

import structlog

log = structlog.get_logger()


def trace_llm_call(func):
    """Decorator to trace LLM API calls with timing and metadata."""

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        provider = self.__class__.__name__
        model = getattr(self, "_model", "unknown")
        start = time.perf_counter()
        try:
            result = await func(self, *args, **kwargs)
            duration_ms = round((time.perf_counter() - start) * 1000)

            log_kwargs: dict = {
                "provider": provider,
                "model": model,
                "duration_ms": duration_ms,
            }

            # CompletionResponse has stop_reason and tool_calls
            if hasattr(result, "stop_reason"):
                log_kwargs["stop_reason"] = result.stop_reason
                log_kwargs["tool_calls"] = len(result.tool_calls) if result.tool_calls else 0

            log.info("llm_call", **log_kwargs)
            return result
        except Exception as e:
            duration_ms = round((time.perf_counter() - start) * 1000)
            log.error(
                "llm_call_failed",
                provider=provider,
                model=model,
                duration_ms=duration_ms,
                error=str(e),
            )
            raise

    return wrapper


def trace_tool_execution(func):
    """Decorator for tool execution tracing."""

    @functools.wraps(func)
    async def wrapper(self, name, args):
        start = time.perf_counter()
        try:
            result = await func(self, name, args)
            duration_ms = round((time.perf_counter() - start) * 1000)
            log.info("tool_executed", tool=name, duration_ms=duration_ms)
            return result
        except Exception as e:
            duration_ms = round((time.perf_counter() - start) * 1000)
            log.error("tool_failed", tool=name, duration_ms=duration_ms, error=str(e))
            raise

    return wrapper
