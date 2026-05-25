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

"""Integration test for xunit enrichment end-to-end (Story 8a.1 AC-8a.1.8).

Drives the listener's end_test → snapshot → xunit_file pipeline against an
in-memory simulation (no live RF subprocess) so the test stays deterministic +
fast under pytest. The full RF subprocess path is verified by the unit tests +
the explicit Listener API in this module.

A more end-to-end RF-subprocess variant is deferred to Phase-1.5 when a
real-LLM dogfood pass exercises the full `robot --listener ... --xunit ...`
flow in CI (Epic 8a Story 8a.2 + Epic 9 will harden cross-repo CI dispatch).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from AgentEval.telemetry import listener as listener_module
from AgentEval.telemetry.listener import Listener


def _make_test_data(full_name: str, suite_full_name: str) -> Any:
    """Build a Listener-v3-style data object for start_test/end_test."""
    suite = SimpleNamespace(full_name=suite_full_name, parent=None)
    return SimpleNamespace(full_name=full_name, parent=suite)


def _make_result(passed: bool = True) -> Any:  # noqa: FBT001, FBT002
    """Build a Listener-v3-style result object."""
    return SimpleNamespace(passed=passed)


@pytest.fixture
def listener(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Listener:
    """Build a fresh listener with output_dir pointing at tmp_path.

    Run from tmp_path so any sidecar artifact written by `_resolve_backend`'s
    default-path branch (no RF runtime OUTPUTDIR available in this synthetic
    Listener-API integration test) lands in tmp_path rather than polluting
    the project root.
    """
    monkeypatch.chdir(tmp_path)
    # Clear the active-listeners registry between tests so record_active_run_metadata
    # only updates this fixture's listener.
    listener_module._active_listeners.clear()
    inst = Listener()
    inst._output_dir = tmp_path
    return inst


def test_end_to_end_xunit_enrichment_populates_properties(
    listener: Listener,
    tmp_path: Path,
) -> None:
    """AC-8a.1.8: full pipeline end_test → snapshot → xunit_file enrichment."""
    # Simulate: start_suite → start_test → adapter calls record_active_run_metadata
    # → end_test (snapshots) → xunit_file (enriches the RF-written XML).
    suite_data = SimpleNamespace(full_name="Sample", parent=None)
    listener.start_suite(suite_data, _make_result())
    test_data = _make_test_data("Sample.Test Alpha", "Sample")
    listener.start_test(test_data, _make_result())
    # Adapter would call this; simulate.
    # Use `total_cost_usd` to match the production adapter callsite at
    # `src/AgentEval/coding_agent/generic.py:253` + `claude_code_cli.py:249`.
    # Story 8a.1 code-review HIGH-1 caught the prior fake-green that used
    # `cost_usd=` (non-existent key in real adapters).
    listener_module.record_active_run_metadata(
        adapter_name="generic",
        model="anthropic/claude-sonnet-4-6",
        total_cost_usd=0.0247,
        completeness="complete",
        mcp_coverage="hosted_in_process",
    )
    listener.end_test(test_data, _make_result())

    # Verify the snapshot was captured.
    assert "Sample.Test Alpha" in listener._completed_run_metadata
    snapshot = listener._completed_run_metadata["Sample.Test Alpha"]
    assert snapshot["adapter"] == "generic"
    assert snapshot["model"] == "anthropic/claude-sonnet-4-6"
    assert snapshot["cost_usd"] == 0.0247
    assert snapshot["completeness"] == "complete"
    assert snapshot["mcp_coverage"] == "hosted_in_process"

    # Write a synthetic RF-style xunit file + invoke the xunit_file hook.
    xunit_path = tmp_path / "junit.xml"
    xunit_path.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="Sample" tests="1" failures="0" errors="0" time="0.4">
  <testcase classname="Sample" name="Test Alpha" time="0.4"/>
</testsuite>
""")
    listener.xunit_file(str(xunit_path))

    # Parse + verify enrichment landed.
    tree = ET.parse(xunit_path)
    testcase = next(tree.iter("testcase"))
    props_elem = testcase.find("properties")
    assert props_elem is not None
    props = {p.get("name", ""): p.get("value", "") for p in props_elem.findall("property")}
    assert props["agenteval.adapter"] == "generic"
    assert props["agenteval.model"] == "anthropic/claude-sonnet-4-6"
    assert props["agenteval.cost_usd"] == "0.0247"
    assert props["agenteval.completeness"] == "complete"
    assert props["agenteval.mcp_coverage"] == "hosted_in_process"


def test_xunit_file_with_no_snapshots_is_noop(
    listener: Listener,
    tmp_path: Path,
) -> None:
    """When no tests ran (no snapshots), xunit_file leaves the file untouched."""
    xunit_path = tmp_path / "junit.xml"
    original_text = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="Empty" tests="0" failures="0" errors="0" time="0"/>
"""
    xunit_path.write_text(original_text)
    listener.xunit_file(str(xunit_path))
    # File unchanged.
    assert xunit_path.read_text() == original_text


def test_xunit_file_failure_does_not_raise(
    listener: Listener,
    tmp_path: Path,
) -> None:
    """Failure-mode contract: xunit_file never propagates exceptions."""
    # Populate a snapshot so the lazy-import path is taken.
    listener._completed_run_metadata["Some.Test"] = {"adapter": "generic"}
    # Point at a non-existent file (the helper logs WARN + returns False).
    listener.xunit_file(str(tmp_path / "nonexistent.xml"))
    # Reaching here without exception is the assertion.


def test_trace_store_projections_flow_into_snapshot(
    listener: Listener,
    tmp_path: Path,
) -> None:
    """Trace-store-sourced properties (`total_tokens`, `latency_seconds`,
    `trace_id`, `tier_breakdown`) actually populate the snapshot when the
    listener has captured spans.

    Story 8a.1 code-review MED-2 (Claude CLI 2026-05-25): the prior
    `test_end_to_end_xunit_enrichment_populates_properties` only exercised
    the adapter-metadata path; 4 of 9 properties had zero integration-test
    coverage. This test plugs that gap by emitting a real OTel span
    carrying `gen_ai.usage.*` + `agenteval.tier` attributes.
    """
    from opentelemetry import trace as otel_trace

    from AgentEval._kernel import context as kernel_context

    suite_data = SimpleNamespace(full_name="TraceSuite", parent=None)
    listener.start_suite(suite_data, _make_result())
    test_data = _make_test_data("TraceSuite.TraceTest", "TraceSuite")
    listener.start_test(test_data, _make_result())

    # Emit a synthetic span carrying gen_ai.usage attributes + agenteval.tier
    # so the snapshot pulls non-None values from `trace_store.get_usage` +
    # `get_run_manifest`.
    tracer = otel_trace.get_tracer("test")
    test_id_ctx = kernel_context.current_context()
    assert test_id_ctx is not None and test_id_ctx.test_id == "TraceSuite.TraceTest"
    # `trace_store.get_usage` only sums spans named "chat" (FR35) — use
    # the canonical name. tier_breakdown reads `agenteval.tier` attr
    # from any tier-annotated span.
    with tracer.start_as_current_span("chat") as span:
        span.set_attribute("gen_ai.usage.input_tokens", 100)
        span.set_attribute("gen_ai.usage.output_tokens", 200)
        span.set_attribute("agenteval.tier", 3)
        # span auto-closes here.

    listener.end_test(test_data, _make_result())

    snapshot = listener._completed_run_metadata["TraceSuite.TraceTest"]
    # total_tokens populated from gen_ai.usage.* attributes via trace_store.
    assert snapshot["total_tokens"] == 300, snapshot
    # latency_seconds populated (small positive value from the span duration).
    assert snapshot["latency_seconds"] is not None
    assert snapshot["latency_seconds"] >= 0.0
    # trace_id mirrors the test_id (canonical RF full_name).
    assert snapshot["trace_id"] == "TraceSuite.TraceTest"
    # tier_breakdown: at least one tier-3 span counted.
    assert snapshot["tier_breakdown"] == {3: 1}, snapshot
