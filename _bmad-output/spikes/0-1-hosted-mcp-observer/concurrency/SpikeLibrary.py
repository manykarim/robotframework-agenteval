"""Minimal RF Library wrapping the dual-transport probe for Story 0.1 pabot stress test.

NOT a model for production library shape — production lives in src/AgentEval/library.py
per architecture.md Project Tree (Story 1a.1 creates it).

Per P11 review: exposes keywords for ALL three coverage states (hosted_in_process,
subprocess_with_observer, external_mixed) so the RF suite exercises AC-0.1.1's
"exactly one of" 3-state field under pabot concurrency.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SPIKE_DIR))

from observer_prototype import HostedMcpObserver  # noqa: E402
from run_dual_transport_probe import main as run_dual  # noqa: E402
from transports.in_memory_server import build_in_memory_server  # noqa: E402
from mcp.shared.memory import create_connected_server_and_client_session  # noqa: E402


class SpikeLibrary:
    """Per-test scope. Three probe keywords + assertions, one per coverage state."""

    ROBOT_LIBRARY_SCOPE = "TEST"

    def __init__(self, out_path: str | None = None) -> None:
        # Per-pid file split; pid-recycling risk noted in deferred-work.md.
        default_out = str(SPIKE_DIR / "concurrency" / "pabot_evidence" / f"worker_pid{os.getpid()}.jsonl")
        self.out_path = out_path or default_out
        self._last_result = None

    # ----- Probe keywords -----

    def run_dual_transport_probe(self, test_id: str) -> None:
        """In-memory + stdio subprocess (D2 handler-wrap injection). Expects: hosted_in_process (D1 trust-floor)."""
        self._last_result = None  # invalidate stale state on probe entry
        self._last_result = asyncio.run(run_dual(test_id=test_id, out_path=self.out_path))

    def run_hosted_in_process_probe(self, test_id: str) -> None:
        """In-memory only. Expects: hosted_in_process."""
        self._last_result = None
        self._last_result = asyncio.run(_run_in_memory_only(test_id, self.out_path))

    def run_subprocess_only_probe(self, test_id: str) -> None:
        """Stdio subprocess (D2 handler-wrap injection) only — no in-memory leg.
        Expects: subprocess_with_observer (D1 trust-floor: strongest path that fired)."""
        self._last_result = None
        self._last_result = asyncio.run(_run_subprocess_only(test_id, self.out_path))

    def run_external_mixed_probe(self, test_id: str) -> None:
        """Observer alive but adapter signals external MCP usage. Expects: external_mixed."""
        self._last_result = None
        self._last_result = asyncio.run(_run_external_mixed(test_id, self.out_path))

    # ----- Assertions -----

    def get_last_mcp_coverage(self) -> str:
        if not self._last_result:
            raise RuntimeError("No probe has run yet")
        return self._last_result.mcp_coverage

    def get_last_tool_call_count(self) -> int:
        if not self._last_result:
            raise RuntimeError("No probe has run yet")
        return len(self._last_result.tool_calls)

    def assert_mcp_coverage_was(self, expected: str) -> None:
        actual = self.get_last_mcp_coverage()
        if actual != expected:
            raise AssertionError(f"expected mcp_coverage={expected!r}, got {actual!r}")

    def assert_tool_call_count_was(self, expected: int) -> None:
        actual = self.get_last_tool_call_count()
        if actual != int(expected):
            raise AssertionError(f"expected tool_call_count={expected}, got {actual}")


# ----- Probe helpers -----


from observer_prototype import write_jsonl  # noqa: E402  (after class for clarity)


async def _run_subprocess_only(test_id: str, out_path: str):
    """Stdio subprocess leg only (no in-memory leg). Uses run_dual_transport_probe's
    run_stdio_leg helper, which spawns the wrapper that attaches HostedMcpObserver
    in the subprocess via request_handlers wrap."""
    from run_dual_transport_probe import run_stdio_leg
    obs = HostedMcpObserver(transport="stdio", test_id=test_id)
    await run_stdio_leg(obs, test_id)
    result = obs.finalize()
    write_jsonl(out_path, result)
    return result


async def _run_in_memory_only(test_id: str, out_path: str):
    obs = HostedMcpObserver(transport="in_memory", test_id=test_id)
    server = build_in_memory_server()
    obs.attach(server, observation_path="hosted_in_process")
    async with create_connected_server_and_client_session(server) as client:
        await client.call_tool("echo", {"text": "rf-hosted-only"})
        await client.call_tool("add", {"a": 3, "b": 39})
    result = obs.finalize()
    write_jsonl(out_path, result)
    return result


async def _run_external_mixed(test_id: str, out_path: str):
    obs = HostedMcpObserver(transport="in_memory", test_id=test_id)
    server = build_in_memory_server()
    obs.attach(server, observation_path="hosted_in_process")
    async with create_connected_server_and_client_session(server) as client:
        await client.call_tool("echo", {"text": "rf-external-mixed-leg"})
    # Adapter signals it detected an external MCP server it could not instrument.
    obs.mark_external_mixed("rf-test: adapter detected uninstrumented external MCP")
    result = obs.finalize()
    write_jsonl(out_path, result)
    return result
