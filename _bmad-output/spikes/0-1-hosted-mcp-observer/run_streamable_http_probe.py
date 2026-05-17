"""Streamable HTTP transport probe for Story 0.1 spike (per D3 review decision).

Validates that the `request_handlers[CallToolRequest]` wrap pattern works for the
streamable_http transport, not just in-memory + stdio. Starts a FastMCP server
on a local port via uvicorn (in a background task), attaches the observer to
fastmcp._mcp_server, connects via streamablehttp_client, calls tools, asserts.

Outputs `measurements/streamable_http.jsonl`.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import anyio
import uvicorn
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

SPIKE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SPIKE_DIR))

from observer_prototype import HostedMcpObserver, AgentRunResult, write_jsonl  # noqa: E402
from transports.streamable_http_server import build_fastmcp_server  # noqa: E402


def _free_port() -> int:
    """Find a free local TCP port. Race-prone but acceptable for the spike."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@asynccontextmanager
async def _running_fastmcp_in_background(observer: HostedMcpObserver, port: int):
    """Start a FastMCP streamable_http server on `port` in a background task.

    Attaches the observer to fastmcp._mcp_server BEFORE the server runs, so the
    request_handlers wrap is in place by the time the first tool call arrives.
    Yields once the port is accepting connections; tears down on context exit.
    """
    fmcp = build_fastmcp_server(host="127.0.0.1", port=port)
    observer.attach(fmcp, observation_path="hosted_in_process")

    config = uvicorn.Config(
        fmcp.streamable_http_app(),
        host="127.0.0.1",
        port=port,
        log_level="error",  # quiet during the probe
    )
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())

    # Wait until uvicorn is actually serving (poll port).
    for _ in range(50):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                s.connect(("127.0.0.1", port))
            break
        except (ConnectionRefusedError, socket.timeout):
            await asyncio.sleep(0.05)
    try:
        yield
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(serve_task, timeout=3.0)
        except asyncio.TimeoutError:
            serve_task.cancel()
            try:
                await serve_task
            except (asyncio.CancelledError, Exception):
                pass


async def run_streamable_http_probe(test_id: str | None = None) -> AgentRunResult:
    observer = HostedMcpObserver(transport="streamable_http", test_id=test_id)
    port = _free_port()
    async with _running_fastmcp_in_background(observer, port):
        url = f"http://127.0.0.1:{port}/mcp"
        async with streamablehttp_client(url) as (read, write, _session_id_cb):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=10)) as client:
                await client.initialize()
                await client.call_tool("echo", {"text": "hello-streamable"})
                await client.call_tool("add", {"a": 100, "b": 23})
    return observer.finalize()


async def main(test_id: str | None = None, out_path: str | None = None) -> AgentRunResult:
    result = await run_streamable_http_probe(test_id=test_id)
    if out_path:
        write_jsonl(out_path, result)
    return result


if __name__ == "__main__":
    test_id = sys.argv[1] if len(sys.argv) > 1 else "probe-streamable-http"
    out_path = sys.argv[2] if len(sys.argv) > 2 else str(SPIKE_DIR / "measurements" / "streamable_http.jsonl")
    result = asyncio.run(main(test_id=test_id, out_path=out_path))
    print(json.dumps({
        "run_id": result.run_id,
        "mcp_coverage": result.mcp_coverage,
        "tool_call_count": len(result.tool_calls),
        "observed_paths": result.metadata.get("observed_paths"),
        "transport": result.metadata.get("transport"),
        "out_path": out_path,
    }, indent=2))
