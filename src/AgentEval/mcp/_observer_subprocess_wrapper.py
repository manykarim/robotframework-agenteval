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

"""Subprocess wrapper that injects the hosted-MCP observer at stdio bootstrap.

Per ADR-004 Consequences + spike findings §Pattern that works (post-review
D2): for stdio MCP servers the library spawns, observation requires a
wrapper script that injects ``HostedMcpObserver`` at subprocess bootstrap.
Same ``request_handlers[CallToolRequest]`` mechanism as in-memory; just
running in a different process.

CLI surface (Phase-1):

    python -m AgentEval.mcp._observer_subprocess_wrapper \\
        --server-module my_pkg.my_server \\
        --server-factory build_server \\
        --trace-out /tmp/trace.jsonl

Phase-1 carve-out (DF-5.2-S3): real stdio subprocess wrapping integration
with `MCPLifecycleManager.acquire(transport="stdio")` is deferred to
Story 5.5 (interleaved dogfood port — where real stdio MCP servers exist
to exercise this path). Story 5.2 ships the wrapper SHAPE so adapters can
target it, but the lifecycle-manager-to-wrapper plumbing lands later.

References:
    - ADR-004 §Consequences: "For stdio MCP servers the library spawns,
      observation requires a wrapper script that injects the observer at
      subprocess bootstrap (the `subprocess_observer_wrapper.py` pattern
      from the spike)."
    - Spike findings §Pattern that works: in-memory + stdio + streamable
      HTTP all validated.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

from AgentEval.mcp.observer import HostedMcpObserver

_log = logging.getLogger(__name__)


def _load_server(module_path: str, factory_name: str) -> Any:
    """Import the server module + invoke the no-arg factory to construct the server."""
    module = importlib.import_module(module_path)
    factory = getattr(module, factory_name, None)
    if factory is None or not callable(factory):
        raise RuntimeError(
            f"Server factory {module_path}:{factory_name} not found OR not callable; "
            "the subprocess wrapper expects a no-arg callable returning a Server/FastMCP instance"
        )
    return factory()


def _persist_traces(observer: HostedMcpObserver, trace_out: Path) -> None:
    """Write observer-captured ToolCallTrace records to a JSONL file.

    Parent process reads this file + grafts records into its own trace
    store post-subprocess-exit. JSONL shape matches the OTel envelope
    schema used by `telemetry/backends.py:JSONLBackend` so consumers can
    parse uniformly across the hosted + subprocess paths.
    """
    import dataclasses

    trace_out.parent.mkdir(parents=True, exist_ok=True)
    with trace_out.open("w", encoding="utf-8") as fp:
        for trace in observer.tool_calls():
            record = dataclasses.asdict(trace)
            fp.write(json.dumps(record, default=str, ensure_ascii=False))
            fp.write("\n")


def main(argv: list[str] | None = None) -> int:
    """Entry point: import server, attach observer, run stdio, persist traces.

    Phase-1 scope: the actual stdio loop is run by the imported server
    module's own machinery (e.g., ``mcp.server.stdio.stdio_server``); this
    wrapper only injects the observer + persists traces on exit. The
    server module is expected to expose a no-arg factory that constructs
    the server; the factory's return value gets the observer attached.

    Returns:
        Exit code per sysexits.h: ``0`` on success, ``70`` (EX_SOFTWARE)
        on import / factory failures.
    """
    parser = argparse.ArgumentParser(
        prog="agenteval-mcp-observer-subprocess-wrapper",
        description=(
            "Subprocess wrapper injecting HostedMcpObserver into a library-spawned "
            "stdio MCP server. Per ADR-004 + Story 5.2."
        ),
    )
    parser.add_argument(
        "--server-module",
        required=True,
        help="Python import path of the MCP server module (e.g., 'my_pkg.my_server').",
    )
    parser.add_argument(
        "--server-factory",
        default="build_server",
        help="Name of the no-arg callable in --server-module that returns the server instance.",
    )
    parser.add_argument(
        "--trace-out",
        required=True,
        type=Path,
        help="JSONL output path for captured ToolCallTrace records.",
    )
    args = parser.parse_args(argv)

    # Resolve the trace_out path to absolute at startup so a server
    # module changing CWD during construction doesn't move the trace
    # file (Story 5.2 code-review Edge-cases L1 fix 2026-05-20).
    trace_out = args.trace_out.resolve()
    try:
        server = _load_server(args.server_module, args.server_factory)
    except (RuntimeError, ImportError, AttributeError) as exc:
        _log.error("subprocess wrapper failed to load server: %s", exc)
        # Story 5.2 code-review Edge-cases M2 fix 2026-05-20 (+ Codex HIGH-2):
        # do NOT create the trace_out file on bootstrap failure. Parent
        # process can distinguish "subprocess crashed before persist"
        # (no file) from "subprocess ran with zero calls" (file exists +
        # is empty or has a header).
        return 70  # EX_SOFTWARE

    observer = HostedMcpObserver()
    observer.attach(server, observation_path="subprocess_with_observer")

    # Story 5.2 code-review 1-way Codex HIGH-2 fix 2026-05-20: branch by
    # server type. FastMCP's `run()` accepts a `transport=` kwarg + handles
    # stdio internally; `mcp.server.lowlevel.Server` requires explicit
    # `read_stream`, `write_stream`, `initialization_options` arguments AND
    # an async runner — its no-arg `run()` raises TypeError. Pre-edit
    # called `runner()` blindly for both, crashing the lowlevel-Server
    # path with "Server.run() missing 3 required positional arguments".
    # Phase-1 keeps the FastMCP path (which Story 5.5 dogfood port
    # exercises) + raises a clear error for the lowlevel-Server path
    # (DF-5.2-S3 carry-over lifts this when Story 5.5 surfaces real
    # lowlevel-Server stdio usage).
    try:
        from mcp.server.fastmcp import FastMCP

        if isinstance(server, FastMCP):
            server.run(transport="stdio")
        else:
            _log.error(
                "subprocess wrapper Phase-1 only supports FastMCP servers; "
                "%s requires explicit read_stream/write_stream/initialization_options "
                "(DF-5.2-S3 carry-over). Skipping server.run() — trace will be empty.",
                type(server).__name__,
            )
    finally:
        _persist_traces(observer, trace_out)
    return 0


if __name__ == "__main__":  # pragma: no cover — invoked as subprocess only
    sys.exit(main())
