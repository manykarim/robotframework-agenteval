# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Bundled echo MCP server (Story 3.1).

Minimal FastMCP-based echo server exposing a single `echo_back(text)`
tool. Used by:

1. Phase-1 stdio-transport integration tests
   (`python -m AgentEval.mcp.bundled.echo`).
2. Phase-1 in_memory-transport unit tests (the `build_server()`
   factory below; see `mcp/transport.py:open_in_memory_session`).
3. README quickstart + recipe-1 documentation examples.

Determinism contract (per Story 1b.6 determinism-contract.md +
NFR-PERF-02 ratification): the echo server's response is byte-stable
given a byte-stable input. No timestamps, no randomization, no
external I/O beyond MCP stdio.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP


def build_server() -> FastMCP:
    """Build a fresh `FastMCP` instance exposing the `echo_back` tool.

    Used by in-process transport tests (Story 3.1) where the same
    Python process hosts both the client + the server. Subprocess
    invocations (`python -m AgentEval.mcp.bundled.echo`) call
    `build_server().run()` via `__main__`.
    """
    server = FastMCP("agenteval-bundled-echo")

    @server.tool(description="Echo the input text verbatim.")
    def echo_back(text: str) -> str:
        return text

    return server


if __name__ == "__main__":
    # Subprocess entry point — used by stdio-transport integration tests
    # via `MCP.Start Server command=<sys.executable> args=[-m, AgentEval.mcp.bundled.echo]`.
    #
    # Story 3.1 code-review Blind HIGH (2026-05-19): explicit
    # `transport="stdio"` so future FastMCP default-transport changes
    # don't silently break this entry point.
    build_server().run(transport="stdio")
