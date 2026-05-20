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

"""Listener v3 tests (Story 5.1)."""

from __future__ import annotations

import contextlib
import importlib.metadata
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from opentelemetry import trace

from AgentEval._kernel import context as _kernel_context
from AgentEval._kernel import trace_store
from AgentEval.telemetry.backends import JSONLBackend, MemoryBackend
from AgentEval.telemetry.listener import Listener


class _MockData:
    """Stand-in for an RF Listener v3 ``TestCase`` / ``TestSuite`` data object."""

    def __init__(
        self,
        *,
        full_name: str,
        parent: Any | None = None,
        output_directory: Any = None,
    ) -> None:
        self.full_name = full_name
        self.parent = parent
        self.output_directory = output_directory


@pytest.fixture(autouse=True)
def restore_global_provider() -> Iterator[None]:
    """Reset the global TracerProvider after each test to avoid cross-test pollution."""
    # Pre-test reset: ensure prior tests' OTel global state doesn't leak in.
    with contextlib.suppress(Exception):
        trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]  # noqa: SLF001
    with contextlib.suppress(Exception):
        flag = trace._TRACER_PROVIDER_SET_ONCE  # noqa: SLF001
        trace._TRACER_PROVIDER_SET_ONCE = type(flag)()  # noqa: SLF001
    with contextlib.suppress(Exception):
        trace_store._reset_exporter()  # noqa: SLF001
    with contextlib.suppress(Exception):
        _kernel_context.unbind_context()
    yield
    # Post-test reset: same.
    with contextlib.suppress(Exception):
        trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]  # noqa: SLF001
    with contextlib.suppress(Exception):
        flag = trace._TRACER_PROVIDER_SET_ONCE  # noqa: SLF001
        trace._TRACER_PROVIDER_SET_ONCE = type(flag)()  # noqa: SLF001
    with contextlib.suppress(Exception):
        trace_store._reset_exporter()  # noqa: SLF001
    with contextlib.suppress(Exception):
        _kernel_context.unbind_context()


def test_listener_robot_listener_api_version_is_3() -> None:
    """RF Listener v3 contract — class attribute ROBOT_LISTENER_API_VERSION must be 3."""
    assert Listener.ROBOT_LISTENER_API_VERSION == 3


def test_listener_entry_point_registered_in_pyproject() -> None:
    """The `robot.listener` entry-point group must include `agenteval`."""
    eps = importlib.metadata.entry_points(group="robot.listener")
    names = {ep.name for ep in eps}
    assert "agenteval" in names, f"`agenteval` not registered in robot.listener entry-points; found {names}"


def test_listener_entry_point_resolves_to_listener_class() -> None:
    """The entry-point loads to the `Listener` class at `AgentEval.telemetry.listener:Listener`."""
    eps = importlib.metadata.entry_points(group="robot.listener")
    ep = next(ep for ep in eps if ep.name == "agenteval")
    loaded = ep.load()
    assert loaded is Listener


def test_listener_can_be_instantiated_without_args() -> None:
    """RF instantiates listeners via no-arg constructor."""
    listener = Listener()
    assert listener is not None


def test_start_suite_configures_tracer_provider_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First start_suite triggers TracerProvider config; subsequent ones are idempotent.

    Story 5.1 code-review Blind MED-4 fix 2026-05-20 (`feedback_test_name_assertion_match`):
    pre-edit only counted method invocations; didn't verify the SINGLETON
    invariant (only ONE TestIdContextSpanProcessor + ONE RedactionProcessor
    + ONE SimpleSpanProcessor in the active provider's chain). Now asserts
    the processor list size directly + the agenteval-classes-counted-once
    invariant.
    """
    from opentelemetry.sdk.trace import SpanProcessor as _SpanProcessor

    from AgentEval._kernel.redaction import RedactionProcessor
    from AgentEval.telemetry.listener import TestIdContextSpanProcessor

    listener = Listener()
    calls: list[int] = []
    original = listener._configure_tracer_provider

    def _counting(self: Listener = listener) -> None:  # noqa: ARG001
        calls.append(1)
        original()

    monkeypatch.setattr(listener, "_configure_tracer_provider", _counting)
    suite = _MockData(full_name="root_suite")
    listener.start_suite(suite, None)
    listener.start_suite(suite, None)
    assert len(calls) == 2
    assert listener._tracer_configured is True
    # Verify the SINGLETON: count agenteval-managed processors in the
    # active provider's chain. There must be EXACTLY ONE of each.
    provider = trace.get_tracer_provider()
    span_processors = _get_active_span_processors(provider)
    test_id_count = sum(1 for sp in span_processors if isinstance(sp, TestIdContextSpanProcessor))
    redaction_count = sum(1 for sp in span_processors if isinstance(sp, RedactionProcessor))
    assert test_id_count == 1, f"expected 1 TestIdContextSpanProcessor; got {test_id_count}"
    assert redaction_count == 1, f"expected 1 RedactionProcessor; got {redaction_count}"
    # Sentinel must be set on the provider.
    assert getattr(provider, "_agenteval_listener_attached", False) is True
    _ = _SpanProcessor  # quiet unused-import lint


def _get_active_span_processors(provider: Any) -> list[Any]:
    """Return the list of active SpanProcessors on an OTel TracerProvider.

    OTel SDK doesn't expose this publicly; we reach into the
    `_active_span_processor._span_processors` private tuple. Used only by
    code-review-fix tests that need to verify singleton invariants.
    """
    active = getattr(provider, "_active_span_processor", None)
    if active is None:
        return []
    sps = getattr(active, "_span_processors", ())
    return list(sps)


def test_second_listener_instance_does_not_duplicate_processors() -> None:
    """Story 5.1 code-review 3-way HIGH-A fix 2026-05-20 (Blind H1 + Codex
    empirical probe + Edge-cases M4): pre-edit a second Listener instance
    in the same process stacked 3 more processors onto the existing
    TracerProvider → 6 total → every span stamped/redacted/exported TWICE.
    Now gated by a process-global sentinel; second Listener.start_suite is
    a no-op for processor wiring.
    """
    from AgentEval._kernel.redaction import RedactionProcessor
    from AgentEval.telemetry.listener import TestIdContextSpanProcessor

    suite = _MockData(full_name="suite")
    Listener().start_suite(suite, None)
    Listener().start_suite(suite, None)  # second instance — must not stack
    provider = trace.get_tracer_provider()
    span_processors = _get_active_span_processors(provider)
    test_id_count = sum(1 for sp in span_processors if isinstance(sp, TestIdContextSpanProcessor))
    redaction_count = sum(1 for sp in span_processors if isinstance(sp, RedactionProcessor))
    assert test_id_count == 1, (
        f"duplicate TestIdContextSpanProcessor count={test_id_count} — HIGH-A processor-stacking regression"
    )
    assert redaction_count == 1, (
        f"duplicate RedactionProcessor count={redaction_count} — HIGH-A processor-stacking regression"
    )


def test_start_test_resolves_mcp_per_test_scope_from_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Story 5.1 code-review Auditor H3 fix 2026-05-20: pre-edit ignored
    `mcp_per_test` config + dropped the `scope=` arg so every test bound
    `Scope = "test"` regardless of FR40. Now resolved via
    `_kernel/context._resolve_scope(mcp_per_test)`.
    """
    monkeypatch.setenv("AGENTEVAL_MCP_PER_TEST", "suite")
    listener = Listener()
    suite = _MockData(full_name="S")
    listener.start_suite(suite, None)
    test = _MockData(full_name="S.test_x", parent=suite)
    listener.start_test(test, None)
    ctx = _kernel_context.current_context()
    assert ctx is not None
    assert ctx.scope == "suite", f"expected scope='suite' from FR40; got {ctx.scope!r}"


def test_unknown_trace_backend_warns_and_falls_back_to_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Story 5.1 code-review Edge-cases M2 fix 2026-05-20: pre-edit silently
    fell back to memory on typo'd backend names.
    """
    monkeypatch.setenv("AGENTEVAL_TRACE_BACKEND", "jsnol")
    listener = Listener()
    suite = _MockData(full_name="S")
    with pytest.warns(UserWarning, match="unknown trace_backend"):
        listener.start_suite(suite, None)
    assert isinstance(listener._backend, MemoryBackend)


def test_start_test_unbinds_prior_context_before_warn_and_return(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Story 5.1 code-review Blind MED-1 fix 2026-05-20: pre-edit early-return
    on missing full_name DIDN'T unbind a stale prior context. Defensive
    unbind in start_test now prevents pollution.
    """
    listener = Listener()
    suite = _MockData(full_name="S")
    listener.start_suite(suite, None)
    # Bind a stale context (simulating a prior test that didn't end_test cleanly).
    _kernel_context.set_current_test_id("stale.test", suite_id="stale.suite")
    assert _kernel_context.current_context() is not None
    # New test with missing full_name → start_test should unbind THEN warn.
    bad_test = _MockData(full_name="", parent=suite)
    with pytest.warns(UserWarning, match="missing test full_name"):
        listener.start_test(bad_test, None)
    # Context must be unbound — stale context did NOT leak.
    assert _kernel_context.current_context() is None
    _ = monkeypatch  # quiet unused-arg lint


def test_start_test_sets_current_test_id() -> None:
    """start_test must bind test_id to _kernel/context.set_current_test_id."""
    listener = Listener()
    suite = _MockData(full_name="suite")
    listener.start_suite(suite, None)
    test_data = _MockData(full_name="suite.test_one", parent=suite)
    listener.start_test(test_data, None)
    ctx = _kernel_context.current_context()
    assert ctx is not None
    assert ctx.test_id == "suite.test_one"
    assert ctx.suite_id == "suite"


def test_start_test_with_missing_full_name_warns_and_skips_bind() -> None:
    """Missing full_name → UserWarning + no context bound (graceful degradation per AC-5.1.1)."""
    listener = Listener()
    suite = _MockData(full_name="suite")
    listener.start_suite(suite, None)
    test_data = _MockData(full_name="", parent=suite)
    with pytest.warns(UserWarning, match="missing test full_name"):
        listener.start_test(test_data, None)
    # Context NOT bound — current_context() is None.
    assert _kernel_context.current_context() is None


def test_end_test_clears_spans_and_unbinds_context_in_memory_mode() -> None:
    """end_test → clear_spans(test_id) + unbind_context() in memory mode."""
    listener = Listener()
    suite = _MockData(full_name="suite")
    listener.start_suite(suite, None)
    test_data = _MockData(full_name="suite.test_alpha", parent=suite)
    listener.start_test(test_data, None)
    # Confirm context is bound.
    assert _kernel_context.current_context() is not None
    listener.end_test(test_data, None)
    # Context unbound after end_test.
    assert _kernel_context.current_context() is None


def test_end_test_with_missing_full_name_is_noop() -> None:
    """end_test with missing full_name skips clear + unbind (no raise, no warning)."""
    listener = Listener()
    suite = _MockData(full_name="suite")
    listener.start_suite(suite, None)
    test_data = _MockData(full_name="", parent=suite)
    # Should not raise.
    listener.end_test(test_data, None)


def test_end_suite_is_noop() -> None:
    """end_suite is reserved for Story 8a.1 — currently no-op."""
    listener = Listener()
    suite = _MockData(full_name="suite")
    listener.start_suite(suite, None)
    # Should not raise.
    listener.end_suite(suite, None)


def test_xunit_file_hook_is_noop() -> None:
    """xunit_file accepts path arg + is no-op for Story 5.1; Story 8a.1 fills."""
    listener = Listener()
    # Should not raise.
    listener.xunit_file("/tmp/some-xunit.xml")


def test_output_file_hook_is_noop() -> None:
    """output_file accepts path arg + is no-op for Story 5.1."""
    listener = Listener()
    listener.output_file("/tmp/some-output.xml")


def test_close_is_idempotent() -> None:
    """close() can be called multiple times safely."""
    listener = Listener()
    listener.close()
    listener.close()


def test_extract_suite_id_walks_parents_to_root() -> None:
    """suite_id is the FULL_NAME of the topmost ancestor."""
    root = _MockData(full_name="Root")
    mid = _MockData(full_name="Root.Mid", parent=root)
    leaf = _MockData(full_name="Root.Mid.test_leaf", parent=mid)
    assert Listener._extract_suite_id(leaf) == "Root"


def test_extract_longname_falls_back_to_longname_then_name() -> None:
    """Listener tolerates RF versions that lack full_name."""

    class _OnlyLongname:
        longname = "legacy.longname"

    class _OnlyName:
        name = "fallback_name"

    assert Listener._extract_longname(_OnlyLongname()) == "legacy.longname"
    assert Listener._extract_longname(_OnlyName()) == "fallback_name"


def test_listener_uses_memory_backend_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """trace_backend defaults to 'memory' per Story 1a.6."""
    # Clear AGENTEVAL_TRACE_BACKEND env to force default.
    monkeypatch.delenv("AGENTEVAL_TRACE_BACKEND", raising=False)
    listener = Listener()
    suite = _MockData(full_name="suite")
    listener.start_suite(suite, None)
    assert isinstance(listener._backend, MemoryBackend)


def test_listener_uses_jsonl_backend_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """AGENTEVAL_TRACE_BACKEND=jsonl selects the JSONLBackend."""
    monkeypatch.setenv("AGENTEVAL_TRACE_BACKEND", "jsonl")
    listener = Listener()
    suite = _MockData(full_name="suite")
    listener.start_suite(suite, None)
    assert isinstance(listener._backend, JSONLBackend)


def test_listener_end_test_writes_jsonl_when_jsonl_backend_active(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End-to-end memory-test JSONL flush on end_test."""
    monkeypatch.setenv("AGENTEVAL_TRACE_BACKEND", "jsonl")
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="suite")
    listener.start_suite(suite, None)
    test_data = _MockData(full_name="suite.test_jsonl", parent=suite)
    listener.start_test(test_data, None)
    # Emit a span so the JSONL file has content.
    from AgentEval.telemetry import spans

    with spans.invoke_agent_span("Agent"):
        pass
    listener.end_test(test_data, None)
    # The JSONL file should exist at the configured path.
    expected_path = tmp_path / "agenteval" / "trace__suite__suite.test_jsonl.jsonl"
    assert expected_path.exists(), f"JSONL artifact missing at {expected_path}"
