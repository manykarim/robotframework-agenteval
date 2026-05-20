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

"""End-to-end Listener v3 integration test (Story 5.1 AC-5.1.10).

Drives the Listener through a simulated RF test sequence (start_suite →
start_test → span emission → end_test → next start_test → ...) and verifies:

1. JSONL artifact created at the canonical path when ``trace_backend="jsonl"``.
2. JSONL contains ≥1 ``invoke_agent`` span with the test's ``test_id`` in
   ``attributes``.
3. Memory backend is cleared after ``end_test`` (per-test isolation).
4. Two consecutive tests don't see each other's spans.

This is NOT a full `robot --listener` subprocess test (that would require
fixturing a `.robot` file + invoking the RF CLI); the Listener class is
exercised directly through its hook methods, which gives the same coverage
without the RF runtime overhead. A full subprocess-mode RF integration
test belongs in Story 5.5 (dogfood port).
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from opentelemetry import trace

from AgentEval._kernel import context as _kernel_context
from AgentEval._kernel import trace_store
from AgentEval.telemetry import spans
from AgentEval.telemetry.listener import Listener
from AgentEval.telemetry.semconv import AGENTEVAL_TEST_ID


class _MockData:
    def __init__(self, *, full_name: str, parent: Any | None = None) -> None:
        self.full_name = full_name
        self.parent = parent


@pytest.fixture(autouse=True)
def isolated_tracer_state() -> Iterator[None]:
    """Fully reset OTel global state pre + post each test.

    OTel's `_TRACER_PROVIDER_SET_ONCE` flag is one-shot per process; once any
    other test sets it, the e2e tests' Listener can't install its
    SpanProcessor chain. Reset BOTH the provider AND the set-once flag.
    """
    # Pre-test: reset to clean state (don't trust prior test's cleanup).
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
    # Post-test: same reset.
    with contextlib.suppress(Exception):
        trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]  # noqa: SLF001
    with contextlib.suppress(Exception):
        flag = trace._TRACER_PROVIDER_SET_ONCE  # noqa: SLF001
        trace._TRACER_PROVIDER_SET_ONCE = type(flag)()  # noqa: SLF001
    with contextlib.suppress(Exception):
        trace_store._reset_exporter()  # noqa: SLF001
    with contextlib.suppress(Exception):
        _kernel_context.unbind_context()


def test_e2e_jsonl_artifact_created_and_contains_invoke_agent_span(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """JSONL artifact created at the canonical path; contains the expected span."""
    monkeypatch.setenv("AGENTEVAL_TRACE_BACKEND", "jsonl")
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="MySuite")
    test = _MockData(full_name="MySuite.test_one", parent=suite)
    listener.start_suite(suite, None)
    listener.start_test(test, None)
    with spans.invoke_agent_span("GenericAdapter", model="claude-sonnet-4-6"):
        pass
    listener.end_test(test, None)
    expected_path = tmp_path / "agenteval" / "trace__MySuite__MySuite.test_one.jsonl"
    assert expected_path.exists()
    records = [json.loads(line) for line in expected_path.read_text(encoding="utf-8").strip().split("\n")]
    assert len(records) >= 1
    invoke = next(r for r in records if r["name"] == "invoke_agent")
    assert invoke["attributes"][AGENTEVAL_TEST_ID] == "MySuite.test_one"


def test_e2e_memory_backend_cleared_after_end_test(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Memory backend isolation — after end_test, the test's spans are cleared."""
    monkeypatch.delenv("AGENTEVAL_TRACE_BACKEND", raising=False)
    # Story 5.3: manifest sidecar emission falls back to Path.cwd() when no
    # AGENTEVAL_TRACE_PATH is set, polluting the repo root. Isolate to tmp_path.
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="S")
    test = _MockData(full_name="S.test_memory_clear", parent=suite)
    listener.start_suite(suite, None)
    listener.start_test(test, None)
    with spans.invoke_agent_span("A"):
        pass
    # Before end_test: spans for this test should be present.
    pre = trace_store.get_run_spans("S.test_memory_clear")
    assert len(pre) >= 1
    listener.end_test(test, None)
    # After end_test: cleared.
    post = trace_store.get_run_spans("S.test_memory_clear")
    assert post == []


def test_e2e_two_consecutive_tests_have_isolated_spans(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Per-test isolation — spans from test_a are not visible to test_b queries."""
    monkeypatch.setenv("AGENTEVAL_TRACE_BACKEND", "jsonl")
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="S")
    test_a = _MockData(full_name="S.test_a", parent=suite)
    test_b = _MockData(full_name="S.test_b", parent=suite)
    listener.start_suite(suite, None)
    # Test A
    listener.start_test(test_a, None)
    with spans.invoke_agent_span("AgentA"):
        pass
    listener.end_test(test_a, None)
    # Test B
    listener.start_test(test_b, None)
    with spans.invoke_agent_span("AgentB"):
        pass
    listener.end_test(test_b, None)
    # Two distinct JSONL artifacts.
    artifact_a = tmp_path / "agenteval" / "trace__S__S.test_a.jsonl"
    artifact_b = tmp_path / "agenteval" / "trace__S__S.test_b.jsonl"
    assert artifact_a.exists()
    assert artifact_b.exists()
    # Each artifact contains ONLY its own spans.
    records_a = [json.loads(line) for line in artifact_a.read_text(encoding="utf-8").strip().split("\n")]
    records_b = [json.loads(line) for line in artifact_b.read_text(encoding="utf-8").strip().split("\n")]
    assert all(r["attributes"][AGENTEVAL_TEST_ID] == "S.test_a" for r in records_a)
    assert all(r["attributes"][AGENTEVAL_TEST_ID] == "S.test_b" for r in records_b)


def test_e2e_full_3_level_hierarchy_recorded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """invoke_agent → chat → execute_tool hierarchy survives the listener flow."""
    monkeypatch.setenv("AGENTEVAL_TRACE_BACKEND", "jsonl")
    monkeypatch.setenv("AGENTEVAL_TRACE_PATH", str(tmp_path))
    listener = Listener()
    suite = _MockData(full_name="S")
    test = _MockData(full_name="S.test_hierarchy", parent=suite)
    listener.start_suite(suite, None)
    listener.start_test(test, None)
    with spans.invoke_agent_span("A"), spans.chat_span(model="m"):  # noqa: SIM117 — nested for OTel parent-child clarity
        with spans.execute_tool_span("echo", source="adapter"):  # noqa: SIM117
            pass
    listener.end_test(test, None)
    artifact = tmp_path / "agenteval" / "trace__S__S.test_hierarchy.jsonl"
    records = [json.loads(line) for line in artifact.read_text(encoding="utf-8").strip().split("\n")]
    names = {r["name"] for r in records}
    assert names == {"invoke_agent", "chat", "execute_tool"}
