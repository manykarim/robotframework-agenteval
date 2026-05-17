"""Streamable HTTP MCP server fixture for Story 0.1 spike (per D3 review decision).

Uses FastMCP + uvicorn to host an MCP server on a local HTTP port. The observer
attaches via the same `request_handlers[CallToolRequest]` wrap pattern as the
in-memory and stdio paths — proving the pattern is transport-agnostic.

Run as a library: `build_fastmcp_server(name, port)` returns a configured FastMCP.
Or run as a module: `python -m transports.streamable_http_server [port]` for manual testing.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP


def build_fastmcp_server(name: str = "spike-echo-streamable", host: str = "127.0.0.1", port: int = 8765) -> FastMCP:
    """Build a FastMCP server with echo + add tools. NO observer attached yet —
    the caller is expected to attach HostedMcpObserver to fastmcp._mcp_server
    before calling run_streamable_http_async()."""
    fmcp = FastMCP(name=name, host=host, port=port)

    @fmcp.tool()
    def echo(text: str) -> str:
        return f"echo: {text}"

    @fmcp.tool()
    def add(a: int, b: int) -> str:
        return f"sum: {a + b}"

    return fmcp


async def _run(port: int = 8765) -> None:
    fmcp = build_fastmcp_server(port=port)
    await fmcp.run_streamable_http_async()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    asyncio.run(_run(port))
