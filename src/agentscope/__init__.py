"""AgentScope — drop-in AI-agent telemetry SDK that emits to Splunk.

Wrap any tool call with `@instrument`:

    from agentscope import instrument

    @instrument(tool="rm_rf", agent="claude-code")
    def rm_rf(path: str) -> None:
        ...

Every call sends a structured event to Splunk via the Splunk MCP server
(or HEC fallback). Dashboards in `splunk_app/` visualize the stream.

Built for the Splunk Agentic Ops Hackathon — track:
Platform & Developer Experience ($3K) + Best Use of Splunk MCP Server ($1K).
"""

from agentscope.instrument import configure, instrument
from agentscope.events import ToolCallEvent

__version__ = "0.1.0"
__all__ = ["configure", "instrument", "ToolCallEvent"]
