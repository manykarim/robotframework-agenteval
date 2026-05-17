"""Edge-case probes for ADR-A6 `mcp_coverage="external_mixed"` safe default.

Per D1 trust-floor semantic (2026-05-17): external_mixed is reserved for runs with a
KNOWN uninstrumented gap (explicit signal from adapter OR empty observations OR path
failure). Successful multi-path observation reports the strongest complete path.

Per P12 (review): probe_subprocess_dies_midtest now exercises the actual partial-log
crash path (truncated last JSON line), not just the missing-file case.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SPIKE_DIR))

from observer_prototype import HostedMcpObserver, AgentRunResult  # noqa: E402
from transports.in_memory_server import build_in_memory_server  # noqa: E402
from mcp.shared.memory import create_connected_server_and_client_session  # noqa: E402


# ----- Probe 1: NO instrumented servers — observer should default to external_mixed -----


async def probe_no_attach() -> AgentRunResult:
    """Observer instantiated but never attach()ed; finalize() with zero traces."""
    obs = HostedMcpObserver(transport="none", test_id="probe-no-attach")
    return obs.finalize()


# ----- Probe 2: Agent uses an external MCP server the observer did NOT see -----


async def probe_external_server_blind() -> AgentRunResult:
    """Observer is alive, but agent talks to a server the observer did NOT attach to."""
    obs = HostedMcpObserver(transport="dual", test_id="probe-external-blind")
    server_a = build_in_memory_server("attached-server")
    server_b = build_in_memory_server("external-server")
    obs.attach(server_a, observation_path="hosted_in_process")
    async with create_connected_server_and_client_session(server_b) as client_b:
        await client_b.call_tool("echo", {"text": "this is invisible to observer"})
    async with create_connected_server_and_client_session(server_a) as client_a:
        await client_a.call_tool("echo", {"text": "this is visible"})
    obs.mark_external_mixed(
        "agent connected to external-server which observer did not attach to"
    )
    return obs.finalize()


# ----- Probe 3: Real partial-log scenario (subprocess crashed after partial write) -----


async def probe_subprocess_dies_midtest() -> AgentRunResult:
    """Subprocess wrote 1.5 records then crashed: a complete record + truncated tail.

    This exercises the REAL partial-log failure mode (review P12). The graft must
    detect the JSONDecodeError on the truncated line and degrade to external_mixed,
    NOT crash the probe.
    """
    obs = HostedMcpObserver(transport="stdio", test_id="probe-subproc-dies")
    # Pretend the in-memory leg ran first and observed two tool calls.
    server = build_in_memory_server()
    obs.attach(server, observation_path="hosted_in_process")
    async with create_connected_server_and_client_session(server) as client:
        await client.call_tool("echo", {"text": "before-crash"})

    # Now simulate a subprocess that wrote one complete record + a truncated next line.
    from run_dual_transport_probe import _graft_subprocess_observer_log
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, prefix="partial_log_"
    ) as tmp:
        partial_log_path = tmp.name
        complete_record = json.dumps({
            "run_id": "subproc-pre-crash",
            "mcp_coverage": "subprocess_with_observer",
            "tool_call_count": 1,
            "metadata": {"transport": "stdio", "test_id": "probe-subproc-dies"},
            "tool_calls": [{
                "sequence_index": 1,
                "tool_name": "echo",
                "arguments": {"text": "subproc-call-1"},
                "result_summary": "echo: subproc-call-1",
                "latency_ms": 1.0,
                "transport": "stdio",
                "observation_path": "subprocess_with_observer",
                "started_at_unix": 0,
                "test_id": "probe-subproc-dies",
            }],
        })
        tmp.write(complete_record + "\n")
        # Truncated tail — simulates SIGKILL mid-write
        tmp.write('{"run_id": "subproc-partial", "mcp_coverage": "subprocess_with_obse')

    try:
        _graft_subprocess_observer_log(obs, partial_log_path)
    finally:
        os.unlink(partial_log_path)
    return obs.finalize()


# ----- Probe 4: All-good baseline (in-memory only) — should report hosted_in_process -----


async def probe_baseline_all_attached() -> AgentRunResult:
    """In-memory only — observer attaches, no degradation, no external_mixed."""
    obs = HostedMcpObserver(transport="dual", test_id="probe-baseline")
    server = build_in_memory_server()
    obs.attach(server, observation_path="hosted_in_process")
    async with create_connected_server_and_client_session(server) as client:
        await client.call_tool("echo", {"text": "ok"})
    return obs.finalize()


# ----- Probe 5: D1 trust-floor — dual paths fired successfully, expect hosted_in_process -----


async def probe_dual_path_trust_floor() -> AgentRunResult:
    """Both observation paths fire successfully; D1 trust-floor reports hosted_in_process."""
    from run_dual_transport_probe import main as run_dual
    return await run_dual(test_id="probe-trust-floor")


async def main() -> None:
    results = {
        "probe_no_attach": await probe_no_attach(),
        "probe_external_server_blind": await probe_external_server_blind(),
        "probe_subprocess_dies_midtest": await probe_subprocess_dies_midtest(),
        "probe_baseline_all_attached": await probe_baseline_all_attached(),
        "probe_dual_path_trust_floor": await probe_dual_path_trust_floor(),
    }
    out_path = SPIKE_DIR / "measurements" / "edge_cases.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for name, result in results.items():
            f.write(json.dumps({
                "probe": name,
                "mcp_coverage": result.mcp_coverage,
                "tool_call_count": len(result.tool_calls),
                "metadata": result.metadata,
            }) + "\n")
    expected = {
        "probe_no_attach": "external_mixed",
        "probe_external_server_blind": "external_mixed",
        "probe_subprocess_dies_midtest": "external_mixed",  # partial log → safe degradation
        "probe_baseline_all_attached": "hosted_in_process",
        "probe_dual_path_trust_floor": "hosted_in_process",  # D1 trust-floor
    }
    print(f"{'probe':<40} {'expected':<28} {'actual':<28} verdict")
    fails = 0
    for name, result in results.items():
        exp = expected[name]
        act = result.mcp_coverage
        ok = "PASS" if exp == act else "FAIL"
        if ok == "FAIL":
            fails += 1
        print(f"{name:<40} {exp:<28} {act:<28} {ok}")
    print(f"\n{'-' * 80}\nedge cases: {len(results) - fails}/{len(results)} passed")
    sys.exit(0 if fails == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
