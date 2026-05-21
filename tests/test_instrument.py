"""Smoke tests for the @instrument decorator + LocalFileSink."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from agentscope import configure, instrument
from agentscope.splunk_sink import LocalFileSink


def _read_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_sync_call_emits_one_ok_event() -> None:
    with tempfile.TemporaryDirectory() as td:
        log = Path(td) / "events.jsonl"
        configure(sink=LocalFileSink(str(log)), agent="t", redact_args=True)

        @instrument(tool="probe")
        def probe(x: int) -> int:
            return x * 2

        result = probe(21)
        assert result == 42

        events = _read_events(log)
        assert len(events) == 1
        assert events[0]["event"]["status"] == "ok"
        assert events[0]["event"]["tool"] == "probe"
        assert events[0]["sourcetype"] == "agentscope:toolcall"


def test_exception_marks_event_as_error() -> None:
    with tempfile.TemporaryDirectory() as td:
        log = Path(td) / "events.jsonl"
        configure(sink=LocalFileSink(str(log)), agent="t", redact_args=True)

        @instrument(tool="blow_up")
        def blow_up() -> None:
            raise ValueError("nope")

        try:
            blow_up()
        except ValueError:
            pass

        events = _read_events(log)
        assert len(events) == 1
        assert events[0]["event"]["status"] == "error"
        assert events[0]["event"]["error_class"] == "ValueError"
        assert events[0]["event"]["error_message"] == "nope"


def test_redacted_args_summary() -> None:
    with tempfile.TemporaryDirectory() as td:
        log = Path(td) / "events.jsonl"
        configure(sink=LocalFileSink(str(log)), agent="t", redact_args=True)

        @instrument(tool="secret_tool")
        def secret_tool(api_key: str, payload: dict) -> int:
            return 1

        secret_tool("sk-PLEASE-DO-NOT-LEAK", {"private": "data"})
        events = _read_events(log)
        # Secret value never appears in the event
        assert "sk-PLEASE-DO-NOT-LEAK" not in json.dumps(events[0])
        # But we DO record arg count
        assert "n_positional=2" in events[0]["event"]["args_summary"]
