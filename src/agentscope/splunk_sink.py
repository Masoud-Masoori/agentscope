"""Sinks: where instrumented events go.

Three implementations:
    LocalFileSink   - appends JSONL to a local file (dev / offline)
    SplunkHecSink   - POSTs to Splunk HTTP Event Collector
    SplunkMcpSink   - calls the Splunk MCP server (hackathon-required path)

The interface is intentionally thin so future sinks (e.g. OpenTelemetry,
Kafka) drop in without changing the decorator.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol

import httpx

from agentscope.events import ToolCallEvent

logger = logging.getLogger("agentscope.sink")


class SplunkSink(Protocol):
    def emit(self, event: ToolCallEvent) -> None: ...


class LocalFileSink:
    """Dev sink: appends one JSON line per event to a local file."""

    def __init__(self, path: str):
        self.path = Path(path)

    def emit(self, event: ToolCallEvent) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")


class SplunkHecSink:
    """Splunk HTTP Event Collector — direct POST."""

    def __init__(self, *, url: str, token: str, verify_tls: bool = True):
        self.url = url.rstrip("/") + "/services/collector"
        self.token = token
        self._client = httpx.Client(timeout=5.0, verify=verify_tls)

    def emit(self, event: ToolCallEvent) -> None:
        try:
            resp = self._client.post(
                self.url,
                headers={"Authorization": f"Splunk {self.token}"},
                data=event.to_json(),
            )
            if resp.status_code >= 400:
                logger.warning("Splunk HEC returned %d: %s", resp.status_code, resp.text[:200])
        except httpx.HTTPError as e:
            logger.warning("Splunk HEC request failed: %s", e)


class SplunkMcpSink:
    """Splunk MCP server — calls index-write tool via MCP protocol.

    THIS IS THE HACKATHON-REQUIRED PATH for the Splunk MCP Server side prize.
    Reference implementation talks to the MCP server over HTTP/SSE.
    """

    def __init__(self, *, mcp_url: str):
        self.mcp_url = mcp_url.rstrip("/")
        self._client = httpx.Client(timeout=5.0)

    def emit(self, event: ToolCallEvent) -> None:
        # MCP servers usually take a JSON-RPC call. This is the conventional shape
        # for index-write; verify against the actual Splunk MCP spec when wiring.
        payload = {
            "jsonrpc": "2.0",
            "id": event.call_id,
            "method": "tools/call",
            "params": {
                "name": "splunk_index_write",
                "arguments": {
                    "index": "agentscope",
                    "sourcetype": "agentscope:toolcall",
                    "events": [event.to_splunk_event()],
                },
            },
        }
        try:
            resp = self._client.post(self.mcp_url, json=payload)
            if resp.status_code >= 400:
                logger.warning("Splunk MCP returned %d: %s", resp.status_code, resp.text[:200])
        except httpx.HTTPError as e:
            logger.warning("Splunk MCP request failed: %s", e)
