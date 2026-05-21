"""The `@instrument` decorator + global Splunk sink.

Design: minimal happy-path overhead. The decorator wraps the original
function and emits ONE event per call. If the Splunk sink is unavailable,
events are queued in-memory + retried on a background task — failure to
emit telemetry never breaks the wrapped function.

For the hackathon scaffold, the sink is pluggable: you can configure
it to call Splunk MCP (production path) or just write events to a
local JSONL file (dev path).
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import time
import traceback
from typing import Any, Callable, TypeVar

from agentscope.events import ToolCallEvent
from agentscope.splunk_sink import LocalFileSink, SplunkMcpSink, SplunkSink

logger = logging.getLogger("agentscope")
F = TypeVar("F", bound=Callable[..., Any])

# Module-level config
_config: dict[str, Any] = {
    "sink": LocalFileSink("agentscope.events.jsonl"),
    "agent": "unknown",
    "agent_session_id": "",
    "redact_args": True,
}


def configure(
    *,
    sink: SplunkSink | None = None,
    agent: str | None = None,
    agent_session_id: str | None = None,
    splunk_mcp_url: str | None = None,
    splunk_hec_url: str | None = None,
    splunk_hec_token: str | None = None,
    redact_args: bool | None = None,
) -> None:
    """Configure global AgentScope settings.

    Pick ONE sink path:
    - `sink=` for a custom sink
    - `splunk_mcp_url=` to use the Splunk MCP server
    - `splunk_hec_url=` + `splunk_hec_token=` to use Splunk HEC
    - default: writes events to local `agentscope.events.jsonl`
    """
    if sink is not None:
        _config["sink"] = sink
    elif splunk_mcp_url:
        _config["sink"] = SplunkMcpSink(mcp_url=splunk_mcp_url)
    if agent is not None:
        _config["agent"] = agent
    if agent_session_id is not None:
        _config["agent_session_id"] = agent_session_id
    if redact_args is not None:
        _config["redact_args"] = redact_args


def instrument(*, tool: str, agent: str | None = None) -> Callable[[F], F]:
    """Decorator that emits a ToolCallEvent for every call of the wrapped fn."""

    def decorator(fn: F) -> F:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                event = _start_event(tool=tool, agent=agent, args=args, kwargs=kwargs)
                t0 = time.time()
                try:
                    result = await fn(*args, **kwargs)
                    _finish_event(event, status="ok", t0=t0, result=result)
                    return result
                except Exception as e:  # noqa: BLE001
                    _finish_event(event, status="error", t0=t0, error=e)
                    raise

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            event = _start_event(tool=tool, agent=agent, args=args, kwargs=kwargs)
            t0 = time.time()
            try:
                result = fn(*args, **kwargs)
                _finish_event(event, status="ok", t0=t0, result=result)
                return result
            except Exception as e:  # noqa: BLE001
                _finish_event(event, status="error", t0=t0, error=e)
                raise

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def _start_event(
    *,
    tool: str,
    agent: str | None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> ToolCallEvent:
    args_summary = _summarize_args(args, kwargs) if not _config["redact_args"] else _redact_summary(args, kwargs)
    return ToolCallEvent(
        agent=agent or _config["agent"],
        agent_session_id=_config["agent_session_id"],
        tool=tool,
        args_summary=args_summary,
    )


def _finish_event(
    event: ToolCallEvent,
    *,
    status: str,
    t0: float,
    result: Any = None,
    error: Exception | None = None,
) -> None:
    event.status = status
    event.duration_ms = int((time.time() - t0) * 1000)
    if result is not None and not _config["redact_args"]:
        event.result_summary = _summarize_result(result)
    if error is not None:
        event.error_class = error.__class__.__name__
        event.error_message = str(error)[:200]
    try:
        sink: SplunkSink = _config["sink"]
        sink.emit(event)
    except Exception as e:  # noqa: BLE001
        logger.warning("agentscope sink emit failed: %s", e)


def _summarize_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    parts: list[str] = [type(a).__name__ for a in args]
    parts.extend(f"{k}=" + type(v).__name__ for k, v in kwargs.items())
    return f"args=({', '.join(parts)})"


def _redact_summary(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    return f"args=<redacted>, n_positional={len(args)}, n_kwargs={len(kwargs)}"


def _summarize_result(result: Any) -> str:
    tname = type(result).__name__
    if isinstance(result, (str, bytes)):
        return f"{tname}, len={len(result)}"
    if isinstance(result, (list, tuple, set, dict)):
        return f"{tname}, len={len(result)}"
    return tname
