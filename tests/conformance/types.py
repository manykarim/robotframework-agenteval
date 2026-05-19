"""Conformance suite types (Story 1b.5 — architecture Decision-4 + ADR-005 + ADR-017).

Test-infra dataclasses for fixture-shape + harness-result records.

Phase-1 deviation from architecture Decision-4's "Pydantic" wording (per
Story 1b.2 `src/AgentEval/types.py` L46-56 precedent): Story 1b.5 ships
stdlib `@dataclass(frozen=True)` instead of Pydantic. Reasons mirror
Story 1b.2: Pydantic is NOT a direct dep + stdlib dataclasses provide
sufficient field-declaration + `dataclasses.asdict()` for the JSONL
trace-backend serialization path. Phase-1.5 carry-over to Pydantic tracked
in `_bmad-output/implementation-artifacts/deferred-work.md`.

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
    expected_errors: list[str] = field(default_factory=list)
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
