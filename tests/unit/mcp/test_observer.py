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

"""`HostedMcpObserver` unit tests (Story 5.2 / FR35 + ADR-004)."""

from __future__ import annotations

import asyncio
import importlib.metadata
from typing import Any

import pytest
from mcp import types as mcp_types
from mcp.server.fastmcp import FastMCP
from mcp.server.lowlevel import Server

from AgentEval.mcp.observer import (
    AdapterVersionDriftWarning,
    HostedMcpObserver,
)


def _make_lowlevel_server_with_handler() -> Server:
    """Build a minimal lowlevel Server with a registered CallToolRequest handler."""
    server: Server = Server("test")

    async def _handler(req: Any) -> Any:
        return mcp_types.ServerResult(mcp_types.CallToolResult(content=[mcp_types.TextContent(type="text", text="ok")]))

    server.request_handlers[mcp_types.CallToolRequest] = _handler
    return server


def test_attach_to_lowlevel_server_wraps_handler() -> None:
    """`attach()` on a lowlevel `Server` replaces the existing handler with a wrap."""
    server = _make_lowlevel_server_with_handler()
    original = server.request_handlers[mcp_types.CallToolRequest]
    observer = HostedMcpObserver()
    observer.attach(server, observation_path="hosted_in_process")
    wrapped = server.request_handlers[mcp_types.CallToolRequest]
    assert wrapped is not original


def test_attach_to_fastmcp_walks_private_mcp_server() -> None:
    """FastMCP composes a lowlevel Server at `_mcp_server` (ADR-004 + mcp SDK self-usage)."""
    fast = FastMCP("test_fast")

    @fast.tool()
    def _echo(text: str) -> str:
        return text

    observer = HostedMcpObserver()
    observer.attach(fast, observation_path="hosted_in_process")
    # After attach: the underlying lowlevel server is wrapped.
    assert mcp_types.CallToolRequest in fast._mcp_server.request_handlers


def test_attach_rejects_non_server_input() -> None:
    """`attach()` on a non-Server/FastMCP instance raises TypeError."""
    observer = HostedMcpObserver()
    with pytest.raises(TypeError, match="Server.*FastMCP"):
        observer.attach("not_a_server", observation_path="hosted_in_process")


def test_attach_is_idempotent_on_repeated_calls() -> None:
    """Re-attaching the same server doesn't double-wrap."""
    server = _make_lowlevel_server_with_handler()
    observer = HostedMcpObserver()
    observer.attach(server, observation_path="hosted_in_process")
    handler_after_first = server.request_handlers[mcp_types.CallToolRequest]
    observer.attach(server, observation_path="hosted_in_process")
    handler_after_second = server.request_handlers[mcp_types.CallToolRequest]
    assert handler_after_first is handler_after_second


def test_compute_coverage_returns_hosted_in_process_when_attached() -> None:
    """`compute_coverage()` resolves to hosted_in_process when only that path fired."""
    server = _make_lowlevel_server_with_handler()
    observer = HostedMcpObserver()
    observer.attach(server, observation_path="hosted_in_process")
    assert observer.compute_coverage() == "hosted_in_process"


def test_compute_coverage_returns_subprocess_when_only_subprocess_attached() -> None:
    server = _make_lowlevel_server_with_handler()
    observer = HostedMcpObserver()
    observer.attach(server, observation_path="subprocess_with_observer")
    assert observer.compute_coverage() == "subprocess_with_observer"


def test_compute_coverage_hosted_wins_over_subprocess_per_d1_trust_floor() -> None:
    """Story 5.2 / ADR-016 D1: stronger path wins when multiple paths fire."""
    server_a = _make_lowlevel_server_with_handler()
    server_b = _make_lowlevel_server_with_handler()
    observer = HostedMcpObserver()
    observer.attach(server_a, observation_path="subprocess_with_observer")
    observer.attach(server_b, observation_path="hosted_in_process")
    assert observer.compute_coverage() == "hosted_in_process"


def test_compute_coverage_returns_external_mixed_when_nothing_attached() -> None:
    """Detection-failure default per ADR-016 D1 is external_mixed."""
    observer = HostedMcpObserver()
    assert observer.compute_coverage() == "external_mixed"


def test_mark_external_mixed_overrides_hosted() -> None:
    """Adapter-signaled external presence wins over hosted observation per D1."""
    server = _make_lowlevel_server_with_handler()
    observer = HostedMcpObserver()
    observer.attach(server, observation_path="hosted_in_process")
    observer.mark_external_mixed("Claude Code CLI detected ~/.claude.json")
    assert observer.compute_coverage() == "external_mixed"


def test_external_mixed_reasons_returns_chronological_defensive_copy() -> None:
    observer = HostedMcpObserver()
    observer.mark_external_mixed("reason A")
    observer.mark_external_mixed("reason B")
    reasons = observer.external_mixed_reasons()
    assert reasons == ["reason A", "reason B"]
    # Defensive copy — mutating the return doesn't affect internal state.
    reasons.append("evil")
    assert observer.external_mixed_reasons() == ["reason A", "reason B"]


def test_tool_calls_returns_defensive_copy() -> None:
    observer = HostedMcpObserver()
    calls = observer.tool_calls()
    calls.append("evil")  # type: ignore[arg-type]
    assert observer.tool_calls() == []


def test_attach_returns_external_mixed_when_no_handler_registered() -> None:
    """Story 5.2 code-review HIGH-I fix 2026-05-20 (Edge-cases H1): pre-edit
    `attach()` recorded the observation_path even when the wrap silently
    no-op'd (no CallToolRequest handler). Now the path is credited ONLY
    when the wrap is actually installed; compute_coverage honestly
    degrades to external_mixed per ADR-016 D1 detection-failure default.
    """
    bare_server: Server = Server("no_tools_yet")  # No request_handlers populated.
    observer = HostedMcpObserver()
    observer.attach(bare_server, observation_path="hosted_in_process")
    assert observer.compute_coverage() == "external_mixed", (
        "HIGH-I regression: attach with no handler must NOT credit hosted_in_process"
    )


def test_attach_second_observer_does_not_stack_wrap() -> None:
    """Story 5.2 code-review 2-way HIGH-B fix 2026-05-20 (Blind H3 + Edge-cases H2):
    pre-edit two HostedMcpObservers attaching to the same Server stacked
    wraps, double-recording every tool call. Sentinel-marked wrap now
    refuses to stack; the FIRST observer remains the recording sink.
    """
    server = _make_lowlevel_server_with_handler()
    obs1 = HostedMcpObserver()
    obs2 = HostedMcpObserver()
    obs1.attach(server, observation_path="hosted_in_process")
    obs2.attach(server, observation_path="hosted_in_process")
    # Both observers credit the observation_path (both compute_coverage
    # report hosted_in_process), but only obs1 should receive trace
    # records — obs2's wrap installation was refused due to the sentinel.
    assert obs1.compute_coverage() == "hosted_in_process"
    assert obs2.compute_coverage() == "hosted_in_process"
    # Invoke the wrapped handler; only obs1 records.
    import asyncio

    req = mcp_types.CallToolRequest(
        method="tools/call",
        params=mcp_types.CallToolRequestParams(name="t", arguments={}),
    )
    wrapped = server.request_handlers[mcp_types.CallToolRequest]
    asyncio.run(wrapped(req))
    assert len(obs1.tool_calls()) == 1, "first observer should record the call"
    assert len(obs2.tool_calls()) == 0, "HIGH-B regression: second observer must NOT receive records — wrap stacking"


def test_clear_resets_records_but_keeps_servers_attached() -> None:
    """`clear()` empties the records list + reasons + sequence counter,
    but leaves the wrap installed on attached servers (per-test scope per
    ADR-009; pabot worker reuse keeps servers across tests).
    """
    server = _make_lowlevel_server_with_handler()
    observer = HostedMcpObserver()
    observer.attach(server, observation_path="hosted_in_process")
    observer.mark_external_mixed("reason")
    assert observer.external_mixed_reasons() == ["reason"]
    observer.clear()
    assert observer.external_mixed_reasons() == []
    assert observer.tool_calls() == []
    # Server wrap is still installed.
    assert mcp_types.CallToolRequest in server.request_handlers


def test_attach_emits_adapter_version_drift_warning_on_version_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AdapterVersionDriftWarning` raised on first attach when mcp version is out of range."""

    def _fake_version(name: str) -> str:
        if name == "mcp":
            return "0.9.0"  # Below the floor (1.27).
        return importlib.metadata.version(name)

    monkeypatch.setattr(importlib.metadata, "version", _fake_version)
    server = _make_lowlevel_server_with_handler()
    observer = HostedMcpObserver()
    with pytest.warns(AdapterVersionDriftWarning, match="outside the tested range"):
        observer.attach(server, observation_path="hosted_in_process")


def test_attach_version_drift_warning_only_fires_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Multiple attach() calls should warn at most ONCE per observer instance."""

    def _fake_version(name: str) -> str:
        if name == "mcp":
            return "99.0.0"  # Above ceiling.
        return importlib.metadata.version(name)

    monkeypatch.setattr(importlib.metadata, "version", _fake_version)
    server_a = _make_lowlevel_server_with_handler()
    server_b = _make_lowlevel_server_with_handler()
    observer = HostedMcpObserver()
    with pytest.warns(AdapterVersionDriftWarning) as record:
        observer.attach(server_a, observation_path="hosted_in_process")
        observer.attach(server_b, observation_path="hosted_in_process")
    drift_warnings = [w for w in record if issubclass(w.category, AdapterVersionDriftWarning)]
    assert len(drift_warnings) == 1


def test_attach_does_not_warn_when_version_is_in_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """No warning when the installed mcp version is in the tested range."""

    def _fake_version(name: str) -> str:
        if name == "mcp":
            return "1.30.0"  # In range.
        return importlib.metadata.version(name)

    monkeypatch.setattr(importlib.metadata, "version", _fake_version)
    server = _make_lowlevel_server_with_handler()
    observer = HostedMcpObserver()
    import warnings as _warnings

    with _warnings.catch_warnings(record=True) as captured:
        _warnings.simplefilter("always")
        observer.attach(server, observation_path="hosted_in_process")
    drift_warnings = [w for w in captured if issubclass(w.category, AdapterVersionDriftWarning)]
    assert drift_warnings == []


def test_wrapped_handler_records_tool_call_on_success() -> None:
    """When the wrapped handler runs, a `ToolCallTrace` is appended with source=hosted_mcp."""

    async def _original(req: Any) -> Any:
        return mcp_types.ServerResult(mcp_types.CallToolResult(content=[mcp_types.TextContent(type="text", text="ok")]))

    server: Server = Server("test")
    server.request_handlers[mcp_types.CallToolRequest] = _original
    observer = HostedMcpObserver()
    observer.attach(server, observation_path="hosted_in_process")

    # Build a synthetic CallToolRequest + invoke the wrap.
    req = mcp_types.CallToolRequest(
        method="tools/call",
        params=mcp_types.CallToolRequestParams(name="echo", arguments={"text": "hi"}),
    )
    wrapped = server.request_handlers[mcp_types.CallToolRequest]
    asyncio.run(wrapped(req))
    traces = observer.tool_calls()
    assert len(traces) == 1
    assert traces[0].name == "echo"
    assert traces[0].source == "hosted_mcp"
    assert traces[0].args == {"text": "hi"}
    assert traces[0].error is None
    assert traces[0].sequence_index == 1


def test_wrapped_handler_records_error_on_exception() -> None:
    """When the original handler raises, the trace records the error message."""

    async def _failing(req: Any) -> Any:
        raise RuntimeError("simulated tool failure")

    server: Server = Server("test")
    server.request_handlers[mcp_types.CallToolRequest] = _failing
    observer = HostedMcpObserver()
    observer.attach(server, observation_path="hosted_in_process")
    req = mcp_types.CallToolRequest(
        method="tools/call",
        params=mcp_types.CallToolRequestParams(name="boom", arguments={}),
    )
    wrapped = server.request_handlers[mcp_types.CallToolRequest]
    with pytest.raises(RuntimeError, match="simulated tool failure"):
        asyncio.run(wrapped(req))
    traces = observer.tool_calls()
    assert len(traces) == 1
    assert traces[0].name == "boom"
    assert traces[0].error is not None
    assert "simulated tool failure" in traces[0].error
    assert traces[0].source == "hosted_mcp"


def test_wrapped_handler_sequence_index_increments() -> None:
    """`ToolCallTrace.sequence_index` increments monotonically per observer."""

    async def _handler(req: Any) -> Any:
        return mcp_types.ServerResult(mcp_types.CallToolResult(content=[mcp_types.TextContent(type="text", text="ok")]))

    server: Server = Server("test")
    server.request_handlers[mcp_types.CallToolRequest] = _handler
    observer = HostedMcpObserver()
    observer.attach(server, observation_path="hosted_in_process")
    wrapped = server.request_handlers[mcp_types.CallToolRequest]

    async def _run_3() -> None:
        for i in range(3):
            req = mcp_types.CallToolRequest(
                method="tools/call",
                params=mcp_types.CallToolRequestParams(name=f"t{i}", arguments={}),
            )
            await wrapped(req)

    asyncio.run(_run_3())
    indices = [t.sequence_index for t in observer.tool_calls()]
    assert indices == [1, 2, 3]
