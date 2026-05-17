"""Bundled echo MCP server fixture (fast startup baseline) for Story 0.2 cleanup spike.

Identifies itself via process command line (`python ... echo_server.py SPIKE-0-2-ECHO`)
so the leak detector can find leaked instances via `ps -eo pid,ppid,comm,args`.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Identifier embedded in argv so ps can find leaked instances of THIS server type.
MARKER = "SPIKE-0-2-ECHO"


def build_server() -> Server[Any]:
    server: Server[Any] = Server("spike-0-2-echo")

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
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    # MARKER is the second argv arg (sys.argv[0] is the script path itself).
    # ps will show the marker so the leak detector can find this exact server type.
    _ = MARKER  # referenced so import-checkers don't flag as unused
    asyncio.run(_run())
    sys.exit(0)
