"""Slow-startup MCP server fixture for Story 0.2 cleanup spike.

Per architecture.md Decision-3 L710 ("intentionally slow-starting via time.sleep(2)"):
deliberately slow startup surfaces SIGTERM-race conditions during cleanup.

Identifies itself via process command line (`python ... slow_server.py SPIKE-0-2-SLOW`)
so the leak detector can find leaked instances.
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

MARKER = "SPIKE-0-2-SLOW"


def build_server() -> Server[Any]:
    server: Server[Any] = Server("spike-0-2-slow")

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="echo",
                description="Echo input.",
                inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            ),
            types.Tool(
                name="add",
                description="Add ints.",
                inputSchema={"type": "object", "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}}, "required": ["a", "b"]},
            ),
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        if name == "echo":
            return [types.TextContent(type="text", text=f"echo: {arguments.get('text', '')}")]
        if name == "add":
            return [types.TextContent(type="text", text=f"sum: {int(arguments.get('a', 0)) + int(arguments.get('b', 0))}")]
        raise ValueError(f"unknown tool: {name}")

    return server


async def _run() -> None:
    # Slow-startup simulation per architecture.md Decision-3 L710.
    time.sleep(2.0)
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    _ = MARKER
    asyncio.run(_run())
    sys.exit(0)
