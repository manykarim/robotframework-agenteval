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

"""Integration tests for the hosted-MCP observer + adapter wiring (Story 5.2)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from mcp import types as mcp_types
from mcp.server.fastmcp import FastMCP

from AgentEval.coding_agent.generic import GenericAdapter
from AgentEval.errors import IncompleteTraceError
from AgentEval.mcp.observer import HostedMcpObserver
from AgentEval.providers.base import ChatResponse, ProviderUsage
from AgentEval.providers.mock import MockProvider


def _mock_provider() -> MockProvider:
    return MockProvider(
        responses=[
            ChatResponse(
                text="ok",
                tool_calls=[],
                usage=ProviderUsage(input_tokens=1, output_tokens=1),
                cost_usd=0.001,
            )
        ]
    )


def _make_fastmcp_with_tool() -> FastMCP:
    fast = FastMCP("integration_test")

    @fast.tool()
    def echo(text: str) -> str:
        return text

    return fast


class _InMemoryHandle:
    """Stand-in for `MCPServerHandle` with `transport="in_memory"` + a factory."""

    def __init__(self, factory: Any) -> None:
        self.transport = "in_memory"
        self.server_factory = factory


def test_generic_adapter_hosted_in_process_path_resolves_correctly() -> None:
    """Generic adapter + in_memory handle → mcp_coverage="hosted_in_process"."""
    handle = _InMemoryHandle(factory=_make_fastmcp_with_tool)
    adapter = GenericAdapter(provider_instance=_mock_provider())
    result = adapter.run("hi", mcp_servers={"echo_server": handle})
    assert result.metadata.mcp_coverage == "hosted_in_process"


def test_generic_adapter_external_mixed_path_when_no_in_memory_handle() -> None:
    """Bare-object handle (no transport) → mcp_coverage="external_mixed"."""
    adapter = GenericAdapter(provider_instance=_mock_provider())
    result = adapter.run("hi", mcp_servers={"unknown": object()})
    assert result.metadata.mcp_coverage == "external_mixed"


def test_generic_adapter_no_mcp_servers_defaults_to_hosted_in_process() -> None:
    """Backward compat: `mcp_servers=None` keeps the trivial hosted_in_process default."""
    adapter = GenericAdapter(provider_instance=_mock_provider())
    result = adapter.run("hi")
    assert result.metadata.mcp_coverage == "hosted_in_process"


def test_incomplete_trace_error_raises_on_external_mixed() -> None:
    """End-to-end: Generic adapter + external_mixed + check_mcp_coverage → IncompleteTraceError."""
    from AgentEval._kernel.coverage import _check_mcp_coverage

    adapter = GenericAdapter(provider_instance=_mock_provider())
    result = adapter.run("hi", mcp_servers={"unknown": object()})
    # External_mixed without allow_external_mcp_blind → IncompleteTraceError.
    with pytest.raises(IncompleteTraceError, match="external_mixed"):
        _check_mcp_coverage(result, allow_external_mcp_blind=False)


def test_incomplete_trace_error_suppressed_when_opted_out() -> None:
    """`allow_external_mcp_blind=True` allows external_mixed runs through."""
    from AgentEval._kernel.coverage import _check_mcp_coverage

    adapter = GenericAdapter(provider_instance=_mock_provider())
    result = adapter.run("hi", mcp_servers={"unknown": object()})
    # No raise — opted out.
    _check_mcp_coverage(result, allow_external_mcp_blind=True)


def test_observer_captures_tool_calls_through_wrapped_handler() -> None:
    """End-to-end: attach observer + invoke wrapped handler + verify trace captured."""
    fast = _make_fastmcp_with_tool()
    observer = HostedMcpObserver()
    observer.attach(fast, observation_path="hosted_in_process")
    # Find the wrapped handler.
    lowlevel = fast._mcp_server
    wrapped = lowlevel.request_handlers[mcp_types.CallToolRequest]
    req = mcp_types.CallToolRequest(
        method="tools/call",
        params=mcp_types.CallToolRequestParams(name="echo", arguments={"text": "hello"}),
    )
    asyncio.run(wrapped(req))
    traces = observer.tool_calls()
    assert len(traces) == 1
    assert traces[0].name == "echo"
    assert traces[0].source == "hosted_mcp"


def test_listener_register_observer_calls_clear_on_end_test(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    """Listener.register_observer + end_test → observer.clear() is invoked."""
    from AgentEval.telemetry.listener import Listener

    # Story 5.3: isolate manifest sidecar emission to tmp_path so CWD isn't polluted.
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))

    class _CountingObserver:
        def __init__(self) -> None:
            self.cleared = 0

        def clear(self) -> None:
            self.cleared += 1

    listener = Listener()
    obs = _CountingObserver()
    listener.register_observer(obs)
    # Simulate the listener flow.

    class _D:
        full_name = "S.test_observer_clear"
        parent = None

    suite = _D()
    listener.start_suite(suite, None)
    test = _D()
    listener.start_test(test, None)
    listener.end_test(test, None)
    assert obs.cleared == 1


def test_generic_adapter_registers_observer_with_active_listener() -> None:
    """Story 5.2 code-review 1-way HIGH-C fix 2026-05-20 (Blind H2): pre-edit
    `Listener.register_observer` was dead code — Generic adapter never
    wired its per-call observer into the Listener. Now `run()` calls
    `register_active_observer()` so end_test → observer.clear() actually
    fires.
    """
    from AgentEval.telemetry.listener import Listener, _active_listeners

    # Snapshot active listeners + register a fresh Listener.
    snapshot = list(_active_listeners)
    listener = Listener()
    assert listener in _active_listeners
    try:
        adapter = GenericAdapter(provider_instance=_mock_provider())
        handle = _InMemoryHandle(factory=_make_fastmcp_with_tool)
        adapter.run("hi", mcp_servers={"echo_server": handle})
        # Listener's _observers list now contains the adapter's observer.
        assert len(listener._observers) >= 1, (
            "HIGH-C regression: GenericAdapter.run did not register its observer with the active Listener"
        )
    finally:
        _active_listeners[:] = snapshot


def test_claude_code_cli_external_config_detection_opt_in_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    """Story 5.2 code-review HIGH-D fix 2026-05-20 (Blind H4 + Edge-cases H3+H4):
    pre-edit `_detect_external_configs` scanned `~/.claude.json` + `./.mcp.json`
    unconditionally → false-positive external_mixed under any test running
    where the user happens to have invoked Claude Code OR a CWD with
    `.mcp.json`. Now opt-in via `discover_external_configs=True` constructor
    flag.
    """
    # Create a fake .mcp.json in tmp_path; chdir there.
    (tmp_path / ".mcp.json").write_text("{}")
    monkeypatch.chdir(tmp_path)
    # Mock the binary version check so we can construct the adapter
    # without a real `claude` binary.
    import subprocess

    def _fake_run(cmd: Any, **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="2.1.144\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    from AgentEval.coding_agent.claude_code_cli import ClaudeCodeCLIAdapter

    # Default: discover_external_configs=False → no ambient detection.
    adapter_default = ClaudeCodeCLIAdapter()
    adapter_default._current_observer = HostedMcpObserver()
    adapter_default._detect_external_configs(None)
    assert adapter_default._current_observer.compute_coverage() == "external_mixed", (
        "default observer (no attach) honestly resolves to external_mixed; "
        "but no `mark_external_mixed(reason)` should have fired from ambient detection"
    )
    assert adapter_default._current_observer.external_mixed_reasons() == [], (
        "HIGH-D regression: default-off ambient scan must NOT mark external_mixed"
    )
    # Opt-in: discover_external_configs=True → scans + flags.
    adapter_opt = ClaudeCodeCLIAdapter(discover_external_configs=True)
    adapter_opt._current_observer = HostedMcpObserver()
    adapter_opt._detect_external_configs(None)
    reasons = adapter_opt._current_observer.external_mixed_reasons()
    assert any(".mcp.json" in r for r in reasons), (
        f"opt-in ambient scan should flag the CWD .mcp.json; got reasons={reasons}"
    )


def test_listener_clears_observers_before_clearing_trace_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    """Story 5.2 code-review 1-way Auditor HIGH-F fix 2026-05-20: spec AC-5.2.5
    says observer.clear() must fire BEFORE trace_store.clear_spans(test_id).
    Pre-edit the order was reversed.
    """
    from AgentEval._kernel import trace_store as _trace_store
    from AgentEval.telemetry.listener import Listener

    # Story 5.3: isolate manifest sidecar emission to tmp_path so CWD isn't polluted.
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))

    order: list[str] = []

    class _OrderTrackingObserver:
        def clear(self) -> None:
            order.append("observer.clear")

    original_clear_spans = _trace_store.clear_spans

    def _tracking_clear_spans(test_id: str) -> int:
        order.append("trace_store.clear_spans")
        return original_clear_spans(test_id)

    listener = Listener()
    listener.register_observer(_OrderTrackingObserver())

    class _D:
        full_name = "S.order_test"
        parent = None

    suite = _D()
    listener.start_suite(suite, None)
    test = _D()
    listener.start_test(test, None)
    # Patch clear_spans to track ordering.
    import AgentEval.telemetry.listener as _listener_mod

    _listener_mod.trace_store.clear_spans = _tracking_clear_spans
    try:
        listener.end_test(test, None)
    finally:
        _listener_mod.trace_store.clear_spans = original_clear_spans
    # HIGH-F invariant: observer.clear must fire BEFORE trace_store.clear_spans.
    assert order == ["observer.clear", "trace_store.clear_spans"], (
        f"HIGH-F regression: clear order is {order}; observer.clear must precede trace_store.clear_spans per AC-5.2.5"
    )


def test_listener_register_observer_idempotent() -> None:
    """Registering the same observer twice is a no-op."""
    from AgentEval.telemetry.listener import Listener

    class _Obs:
        def clear(self) -> None:
            pass

    listener = Listener()
    obs = _Obs()
    listener.register_observer(obs)
    listener.register_observer(obs)
    assert len(listener._observers) == 1
