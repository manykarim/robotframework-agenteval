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

"""RunManifest extension + sidecar emitter tests (Story 5.3)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from AgentEval.telemetry.run_manifest import RunManifestEmitter
from AgentEval.types import RunManifest


def _make_manifest(**overrides: Any) -> RunManifest:
    base = {
        "library_version": "0.1.0",
        "test_id": "S.t",
        "suite_id": "S",
        "redaction_policy_hash": "a" * 64,
        "started_at": datetime(2026, 5, 20, 12, 0, 0),
        "ended_at": datetime(2026, 5, 20, 12, 0, 5),
        "agenteval_tier_breakdown": {1: 5, 2: 2, 3: 1},
    }
    base.update(overrides)
    return RunManifest(**base)


def test_run_manifest_backward_compat_seven_fields() -> None:
    """Pre-Story-5.3 RunManifest with only the 7 ratified fields still works."""
    m = _make_manifest()
    assert m.library_version == "0.1.0"
    assert m.test_id == "S.t"
    # New fields default to None / empty.
    assert m.adapter_name is None
    assert m.model is None
    assert m.mcp_servers == []
    assert m.total_cost_usd is None
    assert m.warnings == []
    assert m.prompt_hashes == []


def test_run_manifest_extended_fields_populated() -> None:
    """Story 5.3 extended fields populate correctly."""
    m = _make_manifest(
        adapter_name="GenericAdapter",
        adapter_version="0.1.0",
        model="claude-sonnet-4-6",
        mcp_servers=[{"name": "echo", "transport": "in_memory", "version_or_sha": "<TBD>"}],
        trace_backend="jsonl",
        total_cost_usd=0.01,
        completeness="complete",
        mcp_coverage="hosted_in_process",
        warnings=[
            {
                "warning_type": "AgentEval.errors.DegradedTraceWarning",
                "message": "stale span",
                "source": "telemetry.listener",
                "timestamp": "2026-05-20T00:00:00+00:00",
                "remediation": None,
            }
        ],
        seed=42,
        prompt_hashes=["a" * 64],
    )
    assert m.adapter_name == "GenericAdapter"
    assert m.model == "claude-sonnet-4-6"
    assert m.mcp_servers[0]["name"] == "echo"
    assert m.trace_backend == "jsonl"
    assert m.total_cost_usd == 0.01
    assert m.completeness == "complete"
    assert m.mcp_coverage == "hosted_in_process"
    # Story 5.4: warnings now list[dict] not list[str]; verify the WarningRecord shape.
    assert len(m.warnings) == 1
    assert m.warnings[0]["message"] == "stale span"
    assert m.warnings[0]["warning_type"] == "AgentEval.errors.DegradedTraceWarning"
    assert m.seed == 42


def test_run_manifest_defensive_copy_on_construction() -> None:
    """`__post_init__` defensively copies mutable fields per M_R6 pattern."""
    source_mcp_servers = [{"name": "x", "transport": "in_memory"}]
    # Story 5.4: warnings is now list[dict[str, Any]] per AC-5.4.10.
    source_warnings = [
        {
            "warning_type": "X",
            "message": "w1",
            "source": "s",
            "timestamp": "2026-05-20T00:00:00+00:00",
            "remediation": None,
        }
    ]
    source_prompt_hashes = ["a"]
    m = _make_manifest(
        mcp_servers=source_mcp_servers,
        warnings=source_warnings,
        prompt_hashes=source_prompt_hashes,
    )
    # Mutate sources — manifest's copies unaffected.
    source_mcp_servers.append({"name": "y", "transport": "in_memory"})
    source_warnings.append(
        {
            "warning_type": "Y",
            "message": "w2",
            "source": "s",
            "timestamp": "2026-05-20T00:00:01+00:00",
            "remediation": None,
        }
    )
    source_prompt_hashes.append("b")
    assert len(m.mcp_servers) == 1
    assert len(m.warnings) == 1
    assert m.warnings[0]["message"] == "w1"
    assert m.prompt_hashes == ["a"]


def test_run_manifest_backward_compat_list_str_warnings_coerced() -> None:
    """Story 5.4 code-review 1-way Blind HIGH-D regression: stale fixtures
    passing `list[str]` warnings (Story 5.3 placeholder shape) must NOT
    crash `RunManifest()` construction. The `__post_init__` shim coerces
    each str → 5-key dict with the str as the `message` field.
    """
    m = _make_manifest(warnings=["legacy-DegradedTraceWarning-string"])  # type: ignore[list-item]
    # The str entry coerced into a 5-key dict.
    assert len(m.warnings) == 1
    record = m.warnings[0]
    assert record["message"] == "legacy-DegradedTraceWarning-string"
    assert record["warning_type"] == "AgentEval.errors.DegradedTraceWarning"
    assert record["source"] == "<legacy-str-warning>"
    assert record["timestamp"] == ""
    assert record["remediation"] is None


def test_emitter_writes_json_sidecar_at_canonical_path(tmp_path: Path) -> None:
    """JSON sidecar lands at `<output_dir>/agenteval/manifest__<suite>__<test>.json`
    per PRD FR39 L1558 verbatim path (Story 5.3 code-review Auditor HIGH-E fix).
    """
    m = _make_manifest()
    emitter = RunManifestEmitter()
    result_path = emitter.emit(m, output_dir=tmp_path, suite_id="MySuite", test_id="MySuite.test_a")
    assert result_path is not None
    expected = tmp_path / "agenteval" / "manifest__MySuite__MySuite.test_a.json"
    assert result_path == expected
    assert expected.exists()
    payload = json.loads(expected.read_text(encoding="utf-8"))
    assert payload["test_id"] == "S.t"
    assert payload["library_version"] == "0.1.0"


def test_emitter_skips_phantom_file_on_none_manifest(tmp_path: Path) -> None:
    """`manifest=None` → no file written (Story 5.2 Codex HIGH-J pattern carried into 5.3)."""
    emitter = RunManifestEmitter()
    result_path = emitter.emit(None, output_dir=tmp_path, suite_id="S", test_id="S.t")
    assert result_path is None
    assert not (tmp_path / "agenteval").exists()


def test_emitter_warns_and_returns_none_on_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """OSError during write → UserWarning + None return; does NOT raise."""
    m = _make_manifest()
    emitter = RunManifestEmitter()

    def _explode_open(self: Path, *args: Any, **kwargs: Any) -> Any:  # noqa: ARG001
        raise OSError("simulated disk failure")

    monkeypatch.setattr(Path, "open", _explode_open)
    with pytest.warns(UserWarning, match="RunManifest JSON sidecar write failed"):
        result_path = emitter.emit(m, output_dir=tmp_path, suite_id="S", test_id="S.t")
    assert result_path is None


def test_emitted_sidecar_passes_json_schema_validation(tmp_path: Path) -> None:
    """AC-5.3.8: emitted JSON validates against `docs/contracts/run-manifest-schema.json`."""
    schema_path = Path(__file__).resolve().parents[3] / "docs" / "contracts" / "run-manifest-schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    m = _make_manifest(
        adapter_name="GenericAdapter",
        adapter_version="0.1.0",
        model="anthropic/claude-sonnet-4-6",
        mcp_servers=[{"name": "echo", "transport": "in_memory", "version_or_sha": "<TBD Phase-1.5>"}],
        trace_backend="jsonl",
        total_cost_usd=0.01,
        completeness="complete",
        mcp_coverage="hosted_in_process",
        seed=42,
        prompt_hashes=["a" * 64],
    )
    emitter = RunManifestEmitter()
    result_path = emitter.emit(m, output_dir=tmp_path, suite_id="S", test_id="S.t")
    assert result_path is not None
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    # Schema validation — should not raise.
    jsonschema.validate(instance=payload, schema=schema)


def test_emitter_redacts_text_fields_in_sidecar(tmp_path: Path) -> None:
    """AC-5.3.7: redaction wired through manifest emission."""
    m = _make_manifest(
        model="key=sk-1234567890abcdef1234567890abcdef",  # contrived: model name w/ embedded key
    )
    emitter = RunManifestEmitter()
    result_path = emitter.emit(m, output_dir=tmp_path, suite_id="S", test_id="S.t")
    assert result_path is not None
    payload_text = result_path.read_text(encoding="utf-8")
    assert "sk-1234567890abcdef" not in payload_text


def test_emitter_path_sanitization_for_unsafe_test_id(tmp_path: Path) -> None:
    """Path-traversal attempts in test_id are sanitized."""
    m = _make_manifest(test_id="../../../etc/passwd")
    emitter = RunManifestEmitter()
    result_path = emitter.emit(m, output_dir=tmp_path, suite_id="ok", test_id="../../../etc/passwd")
    assert result_path is not None
    # Path must NOT escape tmp_path/agenteval/.
    assert tmp_path in result_path.parents
    assert result_path.parent == tmp_path / "agenteval"
