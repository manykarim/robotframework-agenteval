"""Smoke test: loader validates each of the 6 reference fixtures (Story 1b.5).

Per AC-1b.5.9 + Task 6: every fixture under `tests/conformance/fixtures/`
MUST be schema-valid and loadable via `load_fixture(path)`. This is the
single Story 1b.5 conformance test that actually EXERCISES code (vs the
10 per-AC test files which SKIP until owning epics ship). Lives in the
`tests/conformance/` directory but is a unit-style smoke for the
harness/loader/schema triad — runs cleanly in the per-release CI workflow
without requiring any concrete adapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .loader import load_fixture
from .types import ConformanceFixture

FIXTURES_DIR = Path(__file__).parent / "fixtures"
# Story 2.4: static-inspection fixtures use a SEPARATE schema (Epic 2
# scope). Scope this Story-1b.5 adapter-fixture loader test to the
# 2 adapter subdirs only; static-inspection fixtures live under
# `fixtures/static_inspection/` and are exercised by
# `test_ac_static_inspection_fixtures.py` against a different schema.
_ADAPTER_FIXTURE_DIRS: tuple[str, ...] = ("generic", "claude_code_cli")


def _all_fixture_paths() -> list[Path]:
    paths: list[Path] = []
    for adapter_dir in _ADAPTER_FIXTURE_DIRS:
        paths.extend((FIXTURES_DIR / adapter_dir).rglob("*.json"))
    return sorted(paths)


@pytest.mark.parametrize("fixture_path", _all_fixture_paths(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_each_reference_fixture_loads_and_validates(fixture_path: Path) -> None:
    """Every shipped fixture loads + schema-validates without error."""
    fixture = load_fixture(fixture_path)
    assert isinstance(fixture, ConformanceFixture)
    # Adapter + scenario name match the directory structure.
    assert fixture.adapter_name == fixture_path.parent.name
    assert fixture.scenario_name == fixture_path.stem


def test_exactly_six_reference_fixtures_shipped() -> None:
    """Story 1b.5 ships exactly 6 reference fixtures per architecture L739:
    2 adapters × 3 scenarios = 6.
    """
    paths = _all_fixture_paths()
    assert len(paths) == 6, f"Expected 6 reference fixtures, got {len(paths)}: {paths}"
    # The 6 fixtures are explicit per architecture L739.
    expected = {
        ("generic", "echo_simple"),
        ("generic", "echo_truncated"),
        ("generic", "echo_external_mcp"),
        ("claude_code_cli", "echo_simple"),
        ("claude_code_cli", "echo_truncated"),
        ("claude_code_cli", "echo_external_mcp"),
    }
    actual = {(p.parent.name, p.stem) for p in paths}
    assert actual == expected


def test_truncated_fixtures_have_truncated_completeness() -> None:
    """`echo_truncated` fixtures MUST emit `metadata.completeness="truncated"` per FR36a."""
    for adapter in ("generic", "claude_code_cli"):
        fixture = load_fixture(FIXTURES_DIR / adapter / "echo_truncated.json")
        assert fixture.agent_run_result["metadata"]["completeness"] == "truncated"


def test_external_mcp_fixtures_have_external_mixed_coverage() -> None:
    """`echo_external_mcp` fixtures MUST emit `metadata.mcp_coverage="external_mixed"` per ADR-016."""
    for adapter in ("generic", "claude_code_cli"):
        fixture = load_fixture(FIXTURES_DIR / adapter / "echo_external_mcp.json")
        assert fixture.agent_run_result["metadata"]["mcp_coverage"] == "external_mixed"
        # FR37: `expected_errors` includes structured IncompleteTraceError per Decision-4
        # (Story 1b.5 code-review H5 Codex catch: structured `{class_name, error_code}` not plain strings).
        class_names = [err["class_name"] for err in fixture.expected_errors]
        error_codes = [err["error_code"] for err in fixture.expected_errors]
        assert "IncompleteTraceError" in class_names
        assert "INCOMPLETE_TRACE" in error_codes


def test_simple_fixtures_have_complete_completeness() -> None:
    """`echo_simple` fixtures MUST emit `metadata.completeness="complete"`."""
    for adapter in ("generic", "claude_code_cli"):
        fixture = load_fixture(FIXTURES_DIR / adapter / "echo_simple.json")
        assert fixture.agent_run_result["metadata"]["completeness"] == "complete"


def test_loader_raises_validation_error_on_invalid_fixture(tmp_path: Path) -> None:
    """`load_fixture` raises `jsonschema.ValidationError` on schema violation (NOT a new agenteval error class per D7)."""
    import json

    import jsonschema

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"_schema_version": "1.0.0"}))  # missing required fields
    with pytest.raises(jsonschema.ValidationError):
        load_fixture(bad)


# ============================================================ #
# Story 1b.5 code-review patches: negative-path + schema-violation matrix #
# ============================================================ #


def _build_valid_minimal_fixture() -> dict:
    """Return a valid-by-schema minimal fixture dict (modified per test)."""
    return {
        "_schema_version": "1.0.0",
        "adapter_name": "test",
        "scenario_name": "test",
        "agent_run_result": {
            "response_text": "x",
            "tool_calls": [],
            "usage": {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0},
            "metadata": {"completeness": "complete", "mcp_coverage": "hosted_in_process"},
            "cost_usd": 0.0,
            "latency_seconds": 0.0,
            "trace_id": "t1",
        },
        "expected_tool_calls": [],
        "expected_errors": [],
        "reproducibility_footer": {
            "library_version": "0.0.1",
            "redaction_policy_hash": "sha256:test",
            "started_at": "2026-05-19T00:00:00Z",
            "ended_at": "2026-05-19T00:00:01Z",
        },
    }


def test_loader_rejects_invalid_completeness_enum(tmp_path: Path) -> None:
    """Story 1b.5 code-review Blind#12: schema-violation test matrix includes Literal enum violations."""
    import json

    import jsonschema

    bad = tmp_path / "bad.json"
    raw = _build_valid_minimal_fixture()
    raw["agent_run_result"]["metadata"]["completeness"] = "BOGUS"  # not in enum
    bad.write_text(json.dumps(raw))
    with pytest.raises(jsonschema.ValidationError):
        load_fixture(bad)


def test_loader_rejects_invalid_mcp_coverage_enum(tmp_path: Path) -> None:
    """ADR-016 3-state Literal enforced; "none" (the pre-ADR-016 4th value) rejected."""
    import json

    import jsonschema

    bad = tmp_path / "bad.json"
    raw = _build_valid_minimal_fixture()
    raw["agent_run_result"]["metadata"]["mcp_coverage"] = "none"
    bad.write_text(json.dumps(raw))
    with pytest.raises(jsonschema.ValidationError):
        load_fixture(bad)


def test_loader_rejects_additional_properties_in_agent_run_result(tmp_path: Path) -> None:
    """Story 1b.5 code-review fix: agent_run_result has additionalProperties: false."""
    import json

    import jsonschema

    bad = tmp_path / "bad.json"
    raw = _build_valid_minimal_fixture()
    raw["agent_run_result"]["unknown_field"] = "leak"
    bad.write_text(json.dumps(raw))
    with pytest.raises(jsonschema.ValidationError):
        load_fixture(bad)


def test_loader_rejects_malformed_iso8601_timestamp(tmp_path: Path) -> None:
    """Story 1b.5 code-review Blind#22 + Edge: format: date-time enforced via FormatChecker."""
    import json

    import jsonschema

    bad = tmp_path / "bad.json"
    raw = _build_valid_minimal_fixture()
    raw["reproducibility_footer"]["started_at"] = "yesterday"
    bad.write_text(json.dumps(raw))
    with pytest.raises(jsonschema.ValidationError):
        load_fixture(bad)


def test_loader_rejects_invalid_expected_error_shape(tmp_path: Path) -> None:
    """Story 1b.5 code-review H5 (Codex): expected_errors items are structured dicts, not plain strings."""
    import json

    import jsonschema

    bad = tmp_path / "bad.json"
    raw = _build_valid_minimal_fixture()
    raw["expected_errors"] = ["IncompleteTraceError"]  # OLD plain-string shape
    bad.write_text(json.dumps(raw))
    with pytest.raises(jsonschema.ValidationError):
        load_fixture(bad)


def test_fixture_trace_ids_unique_across_all_fixtures() -> None:
    """Story 1b.5 code-review Blind#18: trace_ids must be unique to prevent collision."""
    fixtures = [load_fixture(p) for p in _all_fixture_paths()]
    trace_ids = [f.agent_run_result["trace_id"] for f in fixtures]
    assert len(set(trace_ids)) == len(trace_ids), f"Duplicate trace_ids found: {trace_ids}"
