# AgentScope

> Every AI agent tool call observable in Splunk. Drop-in decorator for Claude Code, Cursor, Codex.

Built for the [Splunk Agentic Ops Hackathon](https://splunk.devpost.com/). Tracks: **Platform & Developer Experience** ($3K) + **Best Use of Splunk MCP Server** ($1K).

## Quick start

```python
from agentscope import configure, instrument

configure(splunk_mcp_url="https://your-splunk-mcp:8443", agent="claude-code")

@instrument(tool="grep")
def grep(pattern: str, path: str) -> int:
    return 42

grep("TODO", "src/")  # → emits a ToolCallEvent to Splunk
```

## What you get

- One Splunk event per tool call (`sourcetype=agentscope:toolcall`, `index=agentscope`)
- Five dashboards out of the box (live stream / tool volume / error funnel / token cost waterfall / high-risk anomaly)
- Drop-in: 3 lines to instrument any agent
- Cost-aware: tokens + dollars per call, per-agent breakdown
- Safe: arg redaction by default (you never leak secrets into Splunk)

## Why Splunk

Splunk MCP exposes index-write as a tool. Our SDK calls it directly — no firewall holes, no API keys per service, schema enforced server-side. Your tool stream joins your existing logs, security, alerting, and retention.

## Architecture

```
[AI agent code]
    |
    | @instrument decorator
    v
[ToolCallEvent created]
    |
    | sink.emit()
    v
[SplunkMcpSink]  ─────────►  [Splunk MCP Server]  ─────►  [Splunk index 'agentscope']
        OR
[LocalFileSink]  ─────────►  agentscope.events.jsonl   (dev / offline)
                                                          |
                                                          v
                              [Splunk app (this repo's splunk_app/)]
                                                          |
                                                          v
                              [5 dashboards: live / volume / errors / cost / anomaly]
```

## Pre-reqs to ship the hackathon submission

- [ ] Splunk Cloud OR Enterprise free trial (60 days) — splunk.com
- [ ] Splunk Developer License requested via Splunk Developer Program
- [ ] Splunk MCP Server installed in your Splunk instance
- [ ] `pip install -e .[dev,splunk]`
- [ ] `python -m agentscope` (smoke run → events.jsonl)
- [ ] Tar the `splunk_app/` directory → install in Splunk → confirm dashboards render

## Files

```
src/agentscope/
├── __init__.py          public API: configure, instrument, ToolCallEvent
├── __main__.py          smoke demo (python -m agentscope)
├── events.py            structured event schema (frozen)
├── instrument.py        @instrument decorator
└── splunk_sink.py       LocalFileSink / SplunkHecSink / SplunkMcpSink
splunk_app/
├── default/
│   ├── app.conf         Splunk app metadata
│   └── savedsearches.conf  5 hackathon dashboards
```

## License

BSD-3-Clause. Use it, fork it, ship it.
