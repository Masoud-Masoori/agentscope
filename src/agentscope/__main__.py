"""Smoke demo: run a handful of instrumented tool calls + emit to local JSONL.

Use:
    python -m agentscope
"""

from __future__ import annotations

import time

from agentscope import configure, instrument


@instrument(tool="grep")
def grep(pattern: str, path: str) -> int:
    """Pretend to grep — return a hit count."""
    time.sleep(0.05)
    return 42


@instrument(tool="write_file")
def write_file(path: str, content: str) -> None:
    time.sleep(0.02)


@instrument(tool="rm_rf")
def rm_rf(path: str) -> None:
    """A high-risk tool. Watch the agentscope dashboard for this one."""
    time.sleep(0.01)


def main() -> int:
    configure(agent="demo-agent", agent_session_id="local-smoke", redact_args=True)
    grep("TODO", "src/")
    write_file("out.txt", "hello")
    try:
        rm_rf("/")
    except Exception:  # noqa: BLE001
        pass
    rm_rf("/tmp/safe")
    print("Wrote events to agentscope.events.jsonl (open it to inspect).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
