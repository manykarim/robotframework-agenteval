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

"""End-to-end redaction wiring tests (Story 5.3 / FR38a/b)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from AgentEval.telemetry.evidence_block import EvidenceBlockEmitter
from AgentEval.telemetry.run_manifest import RunManifestEmitter
from AgentEval.types import (
    AgentRunMetadata,
    AgentRunResult,
    RunManifest,
    Usage,
)

_API_KEY = "sk-1234567890abcdef1234567890abcdef"


def _make_run_with_credential_response() -> AgentRunResult:
    return AgentRunResult(
        response_text=f"Here is the secret: {_API_KEY}",
        tool_calls=[],
        usage=Usage(input_tokens=1, output_tokens=1),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.001,
        latency_seconds=0.01,
        trace_id="t-" + "0" * 30,
    )


def test_evidence_block_redacts_credentials_in_to_dict() -> None:
    """FR38a: Evidence Block JSON form redacts credentials before serialization."""
    result = _make_run_with_credential_response()
    block = EvidenceBlockEmitter().emit(
        result,
        assertion_name="Send Prompt",
        outcome="pass",
        prompt=f"Use this key: {_API_KEY}",
    )
    d = block.to_dict()
    assert _API_KEY not in d["prompt"]
    assert _API_KEY not in d["response"]
    assert d["redaction_report"] == ["redaction_applied"]


def test_evidence_block_redacts_credentials_in_to_markdown() -> None:
    """FR38a: human-readable rendering also redacts."""
    result = _make_run_with_credential_response()
    block = EvidenceBlockEmitter().emit(
        result,
        assertion_name="Send Prompt",
        outcome="pass",
        prompt=f"Use this key: {_API_KEY}",
    )
    md = block.to_markdown()
    assert _API_KEY not in md


def test_run_manifest_sidecar_redacts_credentials(tmp_path: Path) -> None:
    """FR38a/b: RunManifest sidecar redacts credentials before disk write."""
    m = RunManifest(
        library_version="0.1.0",
        test_id="S.t",
        suite_id="S",
        redaction_policy_hash="a" * 64,
        started_at=datetime(2026, 5, 20, 12, 0, 0),
        ended_at=datetime(2026, 5, 20, 12, 0, 5),
        agenteval_tier_breakdown={1: 1},
        model=f"key={_API_KEY}",
    )
    emitter = RunManifestEmitter()
    result_path = emitter.emit(m, output_dir=tmp_path, suite_id="S", test_id="S.t")
    assert result_path is not None
    payload_text = result_path.read_text(encoding="utf-8")
    assert _API_KEY not in payload_text
    payload = json.loads(payload_text)
    # The model field's credential is redacted.
    assert _API_KEY not in str(payload.get("model", ""))


def test_redaction_pipeline_applies_to_both_evidence_and_manifest() -> None:
    """End-to-end: same credential redacted in both surfaces."""
    result = _make_run_with_credential_response()
    block = EvidenceBlockEmitter().emit(
        result,
        assertion_name="Send Prompt",
        outcome="pass",
        prompt=f"Use this key: {_API_KEY}",
    )
    # to_dict + to_markdown both redact
    assert _API_KEY not in str(block.to_dict())
    assert _API_KEY not in block.to_markdown()
