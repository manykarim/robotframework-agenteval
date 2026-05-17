"""Stdio MCP server fixture for Story 0.1 spike — UNCOOPERATING version.

Per D2 review decision (2026-05-17): this server has NO baked-in observation logic.
It's a plain MCP server with echo + add tools. The parent process injects observation
at subprocess bootstrap via `subprocess_observer_wrapper.py`, which:

1. Imports `build_server()` from this module (treating it as a "library-spawned" server).
2. Constructs a `HostedMcpObserver` inside the subprocess process.
3. Attaches the observer via the same `request_handlers[CallToolRequest]` wrap pattern
   used in the in-memory leg — proving the handler-wrap mechanism works in subprocess
   context, not just for cooperating servers that log to JSONL themselves.
4. Runs the server over stdio.
5. On clean shutdown, finalizes the subprocess observer and writes its result to
   OBSERVER_LOG_PATH for the parent process to graft.

Run this server directly (without the wrapper) only for the "no-observer" baseline.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server


def build_server() -> Server[Any]:
    """Build a plain MCP server. NO observation hooks baked in.

    The parent process (subprocess_observer_wrapper.py) attaches HostedMcpObserver
    AFTER calling build_server() and BEFORE calling server.run() — exercising the
    same handler-wrap pattern as the in-memory leg.
    """
    server: Server[Any] = Server("spike-echo-stdio")

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="echo",
                description="Echo the input text back.",
                inputSchema={
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            ),
            types.Tool(
                name="add",
                description="Add two integers.",
                inputSchema={
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                    "required": ["a", "b"],
                },
            ),
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        if name == "echo":
            text = arguments.get("text", "")
            return [types.TextContent(type="text", text=f"echo: {text}")]
        if name == "add":
            a = int(arguments.get("a", 0))
            b = int(arguments.get("b", 0))
            return [types.TextContent(type="text", text=f"sum: {a + b}")]
        raise ValueError(f"unknown tool: {name}")

    return server


async def _run() -> None:
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_run())
    sys.exit(0)
