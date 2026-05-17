"""Dual-transport probe for Story 0.1 spike (post-D1+D2 rewrite).

Exercises:
1. In-memory MCP server with HostedMcpObserver attached in-process (observation_path="hosted_in_process")
2. Stdio subprocess MCP server spawned via subprocess_observer_wrapper.py, which
   attaches a HostedMcpObserver IN THE SUBPROCESS using the same request_handlers
   wrap pattern as the in-memory leg (observation_path="subprocess_with_observer")
3. Parent grafts the subprocess observer's finalized JSONL into the parent observer
   to produce a single AgentRunResult per probe run.

D1 trust-floor semantic: when both paths fire successfully, result reports
`hosted_in_process` (the strongest complete path observed).

Outputs a JSONL record per logical run to `measurements/dual_transport.jsonl`.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

SPIKE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SPIKE_DIR))

from observer_prototype import (  # noqa: E402
    AgentRunResult,
    HostedMcpObserver,
    ToolCallTrace,
    write_jsonl,
)
from transports.in_memory_server import build_in_memory_server  # noqa: E402


async def run_in_memory_leg(observer: HostedMcpObserver) -> None:
    """Connect a client to an in-memory MCP server, call both tools, return."""
    server = build_in_memory_server()
    observer.attach(server, observation_path="hosted_in_process")
    async with create_connected_server_and_client_session(server) as client:
        await client.call_tool("echo", {"text": "hello-in-memory"})
        await client.call_tool("add", {"a": 7, "b": 35})


async def run_stdio_leg(observer: HostedMcpObserver, test_id: str) -> None:
    """Spawn the subprocess wrapper that attaches its own HostedMcpObserver
    inside the subprocess, runs the server, dumps JSONL on shutdown.

    Parent grafts the subprocess's finalized trace records into `observer`.

    NOTE: stdio_client defaults `errlog=sys.stderr` which breaks under RF
    execution because RF replaces sys.stderr with a non-fd capture buffer.
    Workaround: route subprocess stderr to a real file. This is a load-bearing
    finding for ADR-007 — see spike-hosted-mcp-observer-findings.md §RF-Compat.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, prefix="stdio_obs_"
    ) as tmp_log:
        log_path = tmp_log.name
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".log", delete=False, prefix="stdio_stderr_"
    ) as tmp_err:
        stderr_path = tmp_err.name
    try:
        env = os.environ.copy()
        env["OBSERVER_LOG_PATH"] = log_path
        env["OBSERVER_TEST_ID"] = test_id
        # Defaults to transports.stdio_subprocess_server.build_server(); override
        # via OBSERVER_SERVER_MODULE if you want to probe a different target.
        env.setdefault("OBSERVER_SERVER_MODULE", "transports.stdio_subprocess_server")
        env["PYTHONPATH"] = str(SPIKE_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "transports.subprocess_observer_wrapper"],
            env=env,
            cwd=str(SPIKE_DIR),
        )
        # Real file for subprocess stderr — works under RF + pabot
        stderr_file = open(stderr_path, "w", encoding="utf-8")
        try:
            async with stdio_client(params, errlog=stderr_file) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=10)) as client:
                    await client.initialize()
                    await client.call_tool("echo", {"text": "hello-stdio"})
                    await client.call_tool("add", {"a": 1, "b": 41})
            # The subprocess wrapper writes its finalized JSONL on stdio-stream shutdown.
            # Give the subprocess a moment to flush (its `finally` ran but the file may not
            # be fsync'd yet); subprocess teardown is awaited above, so this should be safe.
            _graft_subprocess_observer_log(observer, log_path)
        finally:
            stderr_file.close()
    finally:
        for p in (log_path, stderr_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def _graft_subprocess_observer_log(observer: HostedMcpObserver, log_path: str) -> None:
    """Read the subprocess HostedMcpObserver's finalized JSONL (one record produced by
    write_jsonl on the wrapper's shutdown) and append its tool_calls to the parent observer.

    Per P12 (review): handle missing-file AND corrupt-line scenarios — both degrade to
    external_mixed safely with an accumulated reason in the parent observer.
    """
    if not os.path.exists(log_path) or os.path.getsize(log_path) == 0:
        observer.mark_external_mixed(
            f"subprocess observer log missing or empty at {log_path}"
        )
        return
    try:
        records = []
        with open(log_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    # Partial / truncated last line (real subprocess-crash failure mode).
                    # Degrade to external_mixed honestly rather than crashing the probe.
                    observer.mark_external_mixed(
                        f"subprocess observer log line {line_no} malformed: {exc}"
                    )
                    return
    except OSError as exc:
        observer.mark_external_mixed(
            f"subprocess observer log unreadable at {log_path}: {exc}"
        )
        return

    if not records:
        observer.mark_external_mixed(
            f"subprocess observer log at {log_path} contained no valid records"
        )
        return

    # Forward each captured tool_call into the parent observer via _record(), preserving
    # the encapsulation invariant (review F-edge-15 + F-blind-2). Each subprocess record
    # is one AgentRunResult emitted by the wrapper's observer.finalize() → write_jsonl().
    for record in records:
        for tc in record.get("tool_calls", []):
            observer._record(
                tool_name=tc["tool_name"],
                arguments=tc.get("arguments") or {},
                result_summary=tc.get("result_summary", "<subprocess>"),
                latency_ms=tc.get("latency_ms", 0.0),
                observation_path=tc.get("observation_path", "subprocess_with_observer"),
                started=tc.get("started_at_unix", time.time()),
            )
        # Forward any external_mixed signals from the subprocess observer to the parent
        for reason in record.get("metadata", {}).get("external_mixed_reasons", []) or []:
            observer.mark_external_mixed(f"[subprocess] {reason}")


async def main(test_id: str | None = None, out_path: str | None = None) -> AgentRunResult:
    observer = HostedMcpObserver(transport="dual", test_id=test_id)
    await run_in_memory_leg(observer)
    await run_stdio_leg(observer, test_id or "probe-default")
    result = observer.finalize()
    if out_path:
        write_jsonl(out_path, result)
    return result


if __name__ == "__main__":
    test_id = sys.argv[1] if len(sys.argv) > 1 else "probe-cli"
    out_path = sys.argv[2] if len(sys.argv) > 2 else str(SPIKE_DIR / "measurements" / "dual_transport.jsonl")
    result = asyncio.run(main(test_id=test_id, out_path=out_path))
    print(json.dumps({
        "run_id": result.run_id,
        "mcp_coverage": result.mcp_coverage,
        "tool_call_count": len(result.tool_calls),
        "observed_paths": result.metadata.get("observed_paths"),
        "external_mixed_reasons": result.metadata.get("external_mixed_reasons"),
        "out_path": out_path,
    }, indent=2))
