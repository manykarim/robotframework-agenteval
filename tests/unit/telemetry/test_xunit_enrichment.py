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

"""Unit tests for `telemetry/_xunit_enrichment.py` (Story 8a.1 AC-8a.1.6).

Covers the 10 enumerated unit-test cases in the story:

1. <properties> injection with all 9 names when full metadata is available.
2. Property omission when metadata source returns None/empty.
3. <system-out> injection with synthetic evidence-block content.
4. <system-err> injection with synthetic DegradedTraceWarning content.
5. Idempotency: re-running enrichment yields identical result (no dupes).
6. Schema shape: ElementTree parses; properties have name + value attrs.
7. Atomic write failure preserves original file.
8. test_id derivation: classname.name correctly maps to lookups.
9. Failure-mode: exception in enrichment is caught + file unchanged.
10. agenteval.tier_breakdown JSON encoding: sorted by key.
"""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from AgentEval.telemetry._xunit_enrichment import (
    PROPERTY_NAMES,
    enrich_xunit_file,
)

FIXTURE_PATH = Path(__file__).parent / "_fixtures" / "junit-pre-enrichment.xml"


def _copy_fixture(tmp_path: Path) -> Path:
    """Copy the canonical pre-enrichment fixture into a tmp dir."""
    target = tmp_path / "junit.xml"
    shutil.copy(FIXTURE_PATH, target)
    return target


def _full_metadata() -> dict[str, Any]:
    """Synthetic full-metadata snapshot covering all 9 properties."""
    return {
        "adapter": "generic",
        "model": "anthropic/claude-sonnet-4-6",
        "cost_usd": 0.0247,
        "completeness": "complete",
        "mcp_coverage": "hosted_in_process",
        "total_tokens": 3421,
        "latency_seconds": 2.8,
        "trace_id": "01HRMK0123456789ABCDEFGHJK",
        "tier_breakdown": {3: 5, 1: 2},
        "evidence_block": "evidence: cost=$0.0247 tokens=3421",
        "warnings": "[DegradedTraceWarning] missing longname",
    }


def _properties_by_name(testcase: ET.Element) -> dict[str, str]:
    """Index <property> elements by name attribute."""
    props_elem = testcase.find("properties")
    if props_elem is None:
        return {}
    return {p.get("name", ""): p.get("value", "") for p in props_elem.findall("property")}


def test_full_metadata_injects_all_9_properties(tmp_path: Path) -> None:
    """AC-8a.1.6 #1: full metadata injects all 9 ratified property names."""
    xunit = _copy_fixture(tmp_path)
    metadata_by_test_id = {"Sample.Test Alpha": _full_metadata()}
    result = enrich_xunit_file(xunit, metadata_by_test_id)
    assert result is True

    tree = ET.parse(xunit)
    alpha = next(tc for tc in tree.iter("testcase") if tc.get("name") == "Test Alpha")
    props = _properties_by_name(alpha)
    for name in PROPERTY_NAMES:
        assert name in props, f"missing {name}"
    # Spot-check formatting.
    assert props["agenteval.cost_usd"] == "0.0247"
    assert props["agenteval.latency_seconds"] == "2.800"
    assert props["agenteval.total_tokens"] == "3421"
    assert props["agenteval.adapter"] == "generic"
    assert props["agenteval.completeness"] == "complete"
    assert props["agenteval.trace_id"] == "01HRMK0123456789ABCDEFGHJK"


def test_missing_metadata_omits_properties(tmp_path: Path) -> None:
    """AC-8a.1.6 #2: None/empty source values cause the property to be omitted."""
    xunit = _copy_fixture(tmp_path)
    # Only cost is populated; everything else should be omitted.
    metadata_by_test_id = {"Sample.Test Alpha": {"cost_usd": 0.001, "adapter": None, "model": ""}}
    enrich_xunit_file(xunit, metadata_by_test_id)
    tree = ET.parse(xunit)
    alpha = next(tc for tc in tree.iter("testcase") if tc.get("name") == "Test Alpha")
    props = _properties_by_name(alpha)
    assert "agenteval.cost_usd" in props
    assert "agenteval.adapter" not in props
    assert "agenteval.model" not in props
    assert "agenteval.trace_id" not in props


def test_system_out_injection(tmp_path: Path) -> None:
    """AC-8a.1.6 #3: evidence_block populates <system-out>."""
    xunit = _copy_fixture(tmp_path)
    metadata = {"Sample.Test Alpha": {"evidence_block": "EVIDENCE BLOCK CONTENT"}}
    enrich_xunit_file(xunit, metadata)
    tree = ET.parse(xunit)
    alpha = next(tc for tc in tree.iter("testcase") if tc.get("name") == "Test Alpha")
    system_out = alpha.find("system-out")
    assert system_out is not None
    assert system_out.text == "EVIDENCE BLOCK CONTENT"


def test_system_err_injection(tmp_path: Path) -> None:
    """AC-8a.1.6 #4: warnings populates <system-err>."""
    xunit = _copy_fixture(tmp_path)
    metadata = {"Sample.Test Alpha": {"warnings": "[DegradedTraceWarning] something"}}
    enrich_xunit_file(xunit, metadata)
    tree = ET.parse(xunit)
    alpha = next(tc for tc in tree.iter("testcase") if tc.get("name") == "Test Alpha")
    system_err = alpha.find("system-err")
    assert system_err is not None
    assert "DegradedTraceWarning" in (system_err.text or "")


def test_idempotency_re_enrichment(tmp_path: Path) -> None:
    """AC-8a.1.6 #5: re-running enrichment does NOT duplicate properties."""
    xunit = _copy_fixture(tmp_path)
    metadata = {"Sample.Test Alpha": _full_metadata()}
    enrich_xunit_file(xunit, metadata)
    first_bytes = xunit.read_bytes()
    # Second enrichment with identical metadata.
    enrich_xunit_file(xunit, metadata)
    second_bytes = xunit.read_bytes()
    assert first_bytes == second_bytes, "re-enrichment changed bytes"
    # Verify only one agenteval.cost_usd property exists.
    tree = ET.parse(xunit)
    alpha = next(tc for tc in tree.iter("testcase") if tc.get("name") == "Test Alpha")
    cost_props = [
        p
        for p in alpha.find("properties").findall("property")  # type: ignore[union-attr]
        if p.get("name") == "agenteval.cost_usd"
    ]
    assert len(cost_props) == 1


def test_schema_shape_valid_xml(tmp_path: Path) -> None:
    """AC-8a.1.6 #6: enriched XML parses + every <property> has name+value."""
    xunit = _copy_fixture(tmp_path)
    metadata = {"Sample.Test Alpha": _full_metadata()}
    enrich_xunit_file(xunit, metadata)
    # Re-parse — must succeed.
    tree = ET.parse(xunit)
    for prop in tree.iter("property"):
        assert prop.get("name"), f"property missing name: {ET.tostring(prop)!r}"
        # `value` may be empty string but must be present.
        assert prop.get("value") is not None, f"property missing value: {ET.tostring(prop)!r}"


def test_atomic_write_failure_preserves_original(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-8a.1.6 #7: write failure → original file is preserved."""
    xunit = _copy_fixture(tmp_path)
    original_bytes = xunit.read_bytes()

    def _boom(*args: Any, **kwargs: Any) -> None:  # noqa: ARG001
        raise OSError("simulated disk full")

    # Force the os.replace at the end of enrich_xunit_file to fail.
    monkeypatch.setattr("AgentEval.telemetry._xunit_enrichment.os.replace", _boom)
    result = enrich_xunit_file(xunit, {"Sample.Test Alpha": _full_metadata()})
    assert result is False
    assert xunit.read_bytes() == original_bytes, "original file was modified on failure"
    # Tmp file is cleaned up.
    assert not (tmp_path / "junit.xml.tmp").exists()


def test_test_id_derivation_nested_classname(tmp_path: Path) -> None:
    """AC-8a.1.6 #8: test_id = `f'{classname}.{name}'` works for nested suites."""
    xunit = _copy_fixture(tmp_path)
    # Test Gamma has classname="Sample.Nested" + name="Test Gamma"
    # → derived test_id = "Sample.Nested.Test Gamma"
    metadata = {"Sample.Nested.Test Gamma": {"adapter": "claude_code"}}
    enrich_xunit_file(xunit, metadata)
    tree = ET.parse(xunit)
    gamma = next(tc for tc in tree.iter("testcase") if tc.get("name") == "Test Gamma")
    props = _properties_by_name(gamma)
    assert props.get("agenteval.adapter") == "claude_code"
    # Test Alpha gets no enrichment (different test_id).
    alpha = next(tc for tc in tree.iter("testcase") if tc.get("name") == "Test Alpha")
    assert _properties_by_name(alpha) == {}


def test_failure_mode_missing_file_returns_false(tmp_path: Path) -> None:
    """AC-8a.1.6 #9: missing file → return False, no raise."""
    nonexistent = tmp_path / "does-not-exist.xml"
    result = enrich_xunit_file(nonexistent, {"foo": {"adapter": "generic"}})
    assert result is False


def test_failure_mode_corrupt_xml_returns_false(tmp_path: Path) -> None:
    """AC-8a.1.6 #9 (extension): corrupt XML → return False, file untouched."""
    corrupt = tmp_path / "junit.xml"
    corrupt.write_text("not xml <broken<<")
    original_bytes = corrupt.read_bytes()
    result = enrich_xunit_file(corrupt, {"foo": {"adapter": "generic"}})
    assert result is False
    assert corrupt.read_bytes() == original_bytes


def test_tier_breakdown_json_sorted_by_key(tmp_path: Path) -> None:
    """AC-8a.1.6 #10: tier_breakdown JSON keys are sorted (deterministic)."""
    xunit = _copy_fixture(tmp_path)
    metadata = {"Sample.Test Alpha": {"tier_breakdown": {3: 7, 1: 2, 2: 4}}}
    enrich_xunit_file(xunit, metadata)
    tree = ET.parse(xunit)
    alpha = next(tc for tc in tree.iter("testcase") if tc.get("name") == "Test Alpha")
    props = _properties_by_name(alpha)
    assert props["agenteval.tier_breakdown"] == '{"1": 2, "2": 4, "3": 7}'


def test_existing_non_agenteval_properties_preserved(tmp_path: Path) -> None:
    """Bonus: pre-existing non-agenteval <property> elements are preserved."""
    xunit = tmp_path / "junit.xml"
    xunit.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="Sample" tests="1" failures="0" errors="0" time="0.1">
  <testcase classname="Sample" name="Test Alpha" time="0.1">
    <properties>
      <property name="other.foo" value="bar"/>
    </properties>
  </testcase>
</testsuite>
""")
    enrich_xunit_file(xunit, {"Sample.Test Alpha": {"adapter": "generic"}})
    tree = ET.parse(xunit)
    alpha = next(tc for tc in tree.iter("testcase") if tc.get("name") == "Test Alpha")
    props = _properties_by_name(alpha)
    assert props.get("other.foo") == "bar", "non-agenteval property dropped"
    assert props.get("agenteval.adapter") == "generic"
