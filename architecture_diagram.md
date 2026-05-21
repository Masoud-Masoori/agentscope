# AgentScope — Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│   AI agent code (Claude Code / Cursor / Codex / your app)           │
│                                                                       │
│   @instrument(tool="rm_rf", agent="claude-code")                    │
│   def rm_rf(path): ...                                              │
└─────────────────────────────────────┬───────────────────────────────┘
                                      │
                          ┌───────────▼───────────┐
                          │  agentscope.instrument │
                          │  (sync + async wrapper)│
                          └───────────┬───────────┘
                                      │
                          ┌───────────▼───────────────────┐
                          │   ToolCallEvent (frozen schema)│
                          │   sourcetype:                  │
                          │     agentscope:toolcall         │
                          │   index: agentscope             │
                          └───────────┬───────────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
    ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
    │  LocalFileSink   │   │   SplunkHecSink   │   │  SplunkMcpSink   │
    │  (dev / offline) │   │   (HEC POST)      │   │  ★ MAIN PATH ★   │
    │  events.jsonl    │   │                   │   │  (hackathon req) │
    └──────────────────┘   └─────────┬────────┘   └─────────┬────────┘
                                     │                      │
                                     │   JSON-RPC tools/call│
                                     ▼                      ▼
                          ┌────────────────────────────────────┐
                          │   Splunk MCP Server                 │
                          │   • Tool: splunk_index_write        │
                          │   • Schema enforced server-side     │
                          └─────────────────┬───────────────────┘
                                            │
                                            ▼
                          ┌─────────────────────────────────────┐
                          │   Splunk index `agentscope`         │
                          │   (joins existing logs, alerts,     │
                          │    retention, RBAC)                 │
                          └─────────────────┬───────────────────┘
                                            │
                                            ▼
                          ┌─────────────────────────────────────┐
                          │   AgentScope Splunk App             │
                          │   (splunk_app/default/savedsearches │
                          │    .conf — 5 dashboards)            │
                          │                                     │
                          │   1. Live Agent Stream              │
                          │   2. Tool Call Volume by Service    │
                          │   3. Error Funnel                   │
                          │   4. Token Cost Waterfall           │
                          │   5. High-Risk Anomaly Spike        │
                          └─────────────────────────────────────┘
```

## Component table

| Component | Responsibility | File |
|---|---|---|
| `@instrument` decorator | Wraps any tool fn; emits one event per call | `src/agentscope/instrument.py` |
| `ToolCallEvent` schema | Frozen event format (FIRST-PARTY contract) | `src/agentscope/events.py` |
| `LocalFileSink` | JSONL append for dev | `src/agentscope/splunk_sink.py` |
| `SplunkHecSink` | Direct HEC POST fallback | `src/agentscope/splunk_sink.py` |
| `SplunkMcpSink` | **Hackathon-required path** — calls Splunk MCP `splunk_index_write` tool via JSON-RPC | `src/agentscope/splunk_sink.py` |
| Splunk app | 5 saved searches preconfigured | `splunk_app/default/savedsearches.conf` |

## Data flow

1. **Instrumented tool fires** → decorator creates `ToolCallEvent` (started_at_ms, agent, tool, agent_session_id, args_summary)
2. **Tool returns** → decorator finalizes the event (status, duration_ms, cost_usd, result_summary)
3. **Sink emits** → SplunkMcpSink POSTs JSON-RPC `tools/call` for `splunk_index_write`
4. **Splunk MCP** → indexes the event under `index=agentscope, sourcetype=agentscope:toolcall`
5. **Dashboards query** → 5 saved searches join the live stream into operator-facing visualizations

## Why Splunk MCP, not HEC

| Concern | HEC | Splunk MCP |
|---|---|---|
| Token sprawl | One HEC token per service | Single MCP auth at the MCP server |
| Schema enforcement | Client-side only | Server-side via MCP tool definition |
| Firewall holes | Open inbound HTTP to indexer | MCP server is a single ingress point |
| RBAC | HEC token = bearer auth | MCP server can enforce per-tool ACLs |

## Failure modes + degradation

- **Splunk MCP down** → sink logs warning, event is dropped. Wrapped function is not affected.
- **Rate limit (100/sec)** → sink batches via in-memory queue
- **Arg contains secret** → arg redaction is ON by default; raw args never serialized

## Security posture

- Arg redaction is the default — secrets are never serialized into the event payload (test-verified: `tests/test_instrument.py::test_redacted_args_summary`)
- All deps pinned exact per the operator's NPM/PyPI safety policy
- BSD-3-Clause licensed; published to PyPI and Splunkbase
