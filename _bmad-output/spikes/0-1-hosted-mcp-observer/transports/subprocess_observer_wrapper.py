"""Subprocess observer wrapper — proves the handler-wrap pattern works
in subprocess context, not just for in-memory transport.

Per D2 review decision (2026-05-17): the original spike instrumented the
subprocess server at source (baked logging into @server.call_tool()), which
was NOT actually the `request_handlers` wrap pattern — it was a cooperating
server. This wrapper rebuilds the subprocess leg correctly:

1. Import the target server's `build_server()` (the library knows the module
   because the library spawned it).
2. Construct a fresh `HostedMcpObserver` IN THE SUBPROCESS PROCESS.
3. Attach the observer via `request_handlers[CallToolRequest]` wrap — same
   mechanism as the in-memory leg, validated in subprocess context.
4. Run the server over stdio.
5. On EOF (parent disconnects), finalize the subprocess observer and write
   its trace JSONL to OBSERVER_LOG_PATH for the parent to graft.

Environment contract:
    OBSERVER_LOG_PATH     — required; path the subprocess writes its finalized
                            trace JSONL to on shutdown. Parent grafts this.
    OBSERVER_TEST_ID      — optional; carried into trace records as test_id.
    OBSERVER_SERVER_MODULE — optional; defaults to transports.stdio_subprocess_server.
                            Must expose a `build_server() -> Server` callable.

Run as: python -m transports.subprocess_observer_wrapper
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from pathlib import Path

# Spike-relative sys.path so observer_prototype + transports.stdio_subprocess_server resolve
SPIKE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SPIKE_DIR))

from observer_prototype import HostedMcpObserver, write_jsonl  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402


async def _run() -> None:
    log_path = os.environ.get("OBSERVER_LOG_PATH")
    if not log_path:
        # Caller misconfiguration — refuse to start so the parent gets a clear failure.
        sys.stderr.write(
            "subprocess_observer_wrapper: OBSERVER_LOG_PATH env var required\n"
        )
        sys.exit(2)
    test_id = os.environ.get("OBSERVER_TEST_ID")
    module_name = os.environ.get("OBSERVER_SERVER_MODULE", "transports.stdio_subprocess_server")

    target = importlib.import_module(module_name)
    if not hasattr(target, "build_server"):
        sys.stderr.write(
            f"subprocess_observer_wrapper: {module_name} has no build_server() callable\n"
        )
        sys.exit(2)
    server = target.build_server()

    observer = HostedMcpObserver(transport="stdio", test_id=test_id)
    # Attach the observer in the SUBPROCESS process — same request_handlers wrap
    # mechanism as the in-memory leg, just running in a different process.
    observer.attach(server, observation_path="subprocess_with_observer")

    async with stdio_server() as (read, write):
        try:
            await server.run(read, write, server.create_initialization_options())
        finally:
            # Always finalize + persist, even on parent-disconnect, so the parent
            # has evidence to graft. write_jsonl is append-only so this is safe
            # if the wrapper is re-invoked into the same log path.
            result = observer.finalize()
            try:
                write_jsonl(log_path, result)
            except Exception as exc:  # last-resort diagnostics
                sys.stderr.write(
                    f"subprocess_observer_wrapper: failed to write log_path={log_path!r}: {exc}\n"
                )


if __name__ == "__main__":
    asyncio.run(_run())
