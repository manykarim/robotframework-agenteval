"""In-memory MCP server fixture for Story 0.1 spike.

Uses the lowlevel mcp.server.Server directly + create_connected_server_and_client_session
from mcp.shared.memory to wire a client to it in-process.

Tools: echo(text), add(a, b) — minimal but real semantics.
"""

from __future__ import annotations

from typing import Any

import mcp.types as types
from mcp.server import Server


def build_in_memory_server(server_name: str = "spike-echo-in-memory") -> Server[Any]:
    server: Server[Any] = Server(server_name)

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
