"""Conformance suite types (Story 1b.5 — architecture Decision-4 + ADR-005 + ADR-017).

Test-infra dataclasses for fixture-shape + harness-result records.

Phase-1 deviation from architecture Decision-4's "Pydantic" wording (per
Story 1b.2 `src/AgentEval/types.py` L46-56 precedent): Story 1b.5 ships
stdlib `@dataclass(frozen=True)` instead of Pydantic. Reasons mirror
Story 1b.2: Pydantic is NOT a direct dep + stdlib dataclasses provide
sufficient field-declaration + `dataclasses.asdict()` for the JSONL
trace-backend serialization path. The Pydantic-migration trigger is
"when Epic 5's OTLP serialization needs validation" — see
`_bmad-output/implementation-artifacts/deferred-work.md` Story 1b.5
section DF-1b.5-S2 for the consolidated Phase-1.5 carry-over entry
covering ToolCallTrace + Usage + RunManifest (Story 1b.2) + AgentRunResult
+ AgentRunMetadata (Story 1b.4) + ConformanceFixture + ConformanceResult
(Story 1b.5).

Cross-sub-library import note (architecture L853): these types live in
`tests/conformance/` (test infra), NOT `src/AgentEval/types.py`, because
the conformance harness is NOT a sub-library — it's the test scaffolding
that exercises sub-libraries. The harness imports FROM `src/AgentEval/`;
sub-libraries do not import from here.

References:
    - Architecture L724-751 Decision-4 (JSON+jsonschema fixture format)
    - Architecture L737 (`load_fixture(path) -> ConformanceFixture` signature)
    - ADR-005 L17-22 (fidelity-oracle contract; allowable variations)
    - ADR-017 L21-43 (per-AC test files + harness fixtures)
    - Story 1b.2 `src/AgentEval/types.py` L46-56 (Pydantic-substitution precedent)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "ConformanceFixture",
    "ConformanceResult",
]


@dataclass(frozen=True)
class ConformanceFixture:
    """Loaded conformance fixture per architecture Decision-4 schema.

    Mirrors the `fixture-schema.json` field set. All fields required EXCEPT
    `expected_errors` and `reproducibility_footer` may be empty/default
    when the fixture doesn't exercise their semantics (e.g., a
    non-truncation scenario has `expected_errors=[]`).
    """

    schema_version: str
    adapter_name: str
    scenario_name: str
    agent_run_result: dict[str, Any]
    expected_tool_calls: list[dict[str, Any]]
    # Story 1b.5 code-review H5 (Codex unique catch): expected_errors entries
    # are structured `{class_name, error_code, message_contains?}` dicts per
    # Decision-4 contract, NOT plain strings (pre-edit type was `list[str]`).
    expected_errors: list[dict[str, Any]] = field(default_factory=list)
    reproducibility_footer: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConformanceResult:
    """Harness result for a single `run_fixture` invocation.

    Phase-1 contract (Story 1b.5): `run_fixture` returns a result with
    `passed=False` and `skip_reason="No concrete adapter implementation yet"`
    when invoked against the empty adapter registry; Story 4.1 + 4.2 wire
    real pass/fail evidence-gathering. The `evidence` dict's concrete shape
    is not pinned in Story 1b.5 — per-AC test files in later epics define
    their own evidence keys.
    """

    passed: bool
    fixture: ConformanceFixture
    evidence: dict[str, Any] = field(default_factory=dict)
    skip_reason: str | None = None
