"""Structured event schema for tool calls.

Splunk indexes these as one event per call. The schema is FROZEN — adding
fields is OK, removing or renaming would break dashboards.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_call_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class ToolCallEvent:
    """One event per tool call. Goes into Splunk index `agentscope`."""

    # Identity
    call_id: str = field(default_factory=_new_call_id)
    agent: str = ""                # "claude-code" | "cursor" | "codex" | etc.
    agent_session_id: str = ""     # operator-provided correlation id
    tool: str = ""                 # tool name, e.g. "Bash" / "Edit"

    # Timing
    started_at_ms: int = field(default_factory=_now_ms)
    duration_ms: int = 0

    # Outcome
    status: str = "started"        # "started" | "ok" | "error" | "timeout"
    error_class: str = ""
    error_message: str = ""

    # Cost
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    # Args / result (heavily redacted by default)
    args_summary: str = ""         # one-line description; never raw args (PII risk)
    result_summary: str = ""       # one-line description of return

    # Extension
    tags: dict[str, str] = field(default_factory=dict)

    def to_splunk_event(self) -> dict[str, Any]:
        """Format for Splunk HEC / MCP."""
        return {
            "time": self.started_at_ms / 1000.0,
            "sourcetype": "agentscope:toolcall",
            "source": self.agent,
            "event": asdict(self),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_splunk_event(), separators=(",", ":"))
