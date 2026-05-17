"""rf-mcp-substitute MCP server fixture for Story 0.2 cleanup spike.

The story's Task 4 calls for testing against rf-mcp from https://github.com/manykarim/rf-mcp.
The current execution environment has no git access (`Is a git repository: false`), so
this fixture substitutes a Python-only server that mimics rf-mcp's qualitative profile:

- Multiple tools registered (rf-mcp exposes ~20 RF keywords; we register 8 as a stand-in).
- Moderate startup cost: ~250ms-500ms vs echo_server's <50ms vs slow_server's 2s+.
- Each tool body does ~10ms of synthetic work (string parsing, hashing) to imitate the
  cost of an RF keyword execution.

This is NOT the real rf-mcp. The findings document will note this substitution explicitly
as a Phase-1 carry-over so that any architect re-running the spike against the real rf-mcp
can identify divergences. Identifies itself via MARKER for leak detection.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import time
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

MARKER = "SPIKE-0-2-RFMCPSUB"

# Pretend startup work: import a handful of modules + a bit of computation.
# Tuned to land around 250-500ms on Linux 6.8 / Python 3.12 / glibc 2.39.
_STARTUP_BUDGET_S = 0.30


def _startup_work() -> None:
    """Simulate rf-mcp-ish bootstrap: do some CPU work that takes ~250-500ms."""
    deadline = time.time() + _STARTUP_BUDGET_S
    h = hashlib.sha256(b"agenteval-spike-0-2-startup")
    while time.time() < deadline:
        h.update(h.digest())


def build_server() -> Server[Any]:
    server: Server[Any] = Server("spike-0-2-rf-mcp-substitute")

    # Eight tools to mimic rf-mcp's keyword count (rf-mcp surfaces ~20 RF keywords;
    # the spike only needs enough to inflate ListToolsRequest payload size).
    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        common_schema = {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}
        return [
            types.Tool(name=f"keyword_{i}", description=f"Synthetic RF-like keyword #{i}.", inputSchema=common_schema)
            for i in range(8)
        ] + [
            types.Tool(
                name="echo",
                description="Echo input (same shape as echo_server for cross-server comparability).",
                inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            ),
            types.Tool(
                name="add",
                description="Add ints (same as echo_server).",
                inputSchema={"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]},
            ),
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        # ~10ms synthetic per-call cost to imitate keyword execution.
        h = hashlib.sha256(str(arguments).encode())
        for _ in range(2000):
            h.update(h.digest())
        if name == "echo":
            return [types.TextContent(type="text", text=f"echo: {arguments.get('text', '')}")]
        if name == "add":
            return [types.TextContent(type="text", text=f"sum: {int(arguments.get('a', 0)) + int(arguments.get('b', 0))}")]
        if name.startswith("keyword_"):
            return [types.TextContent(type="text", text=f"{name}: {arguments.get('value', '')}")]
        raise ValueError(f"unknown tool: {name}")

    return server


async def _run() -> None:
    _startup_work()
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    _ = MARKER
    asyncio.run(_run())
    sys.exit(0)
