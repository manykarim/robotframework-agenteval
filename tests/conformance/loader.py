"""Conformance fixture loader (Story 1b.5 — architecture L737).

Singular `load_fixture(path) -> ConformanceFixture` per architecture L737:
reads the JSON file, validates against `fixture-schema.json` via stdlib
`jsonschema`, returns a populated `ConformanceFixture` instance.

Schema-violation raises `jsonschema.ValidationError` directly — NO new
agenteval error class added to `src/AgentEval/errors.py` per Story 1b.5
code-review D7 ratification: the conformance harness is test infra at
`tests/conformance/`, NOT library-public surface at `src/AgentEval/`, so
the `AgentEvalError` hierarchy doesn't need a `InvalidConformanceFixtureError`
leaf. Consumers of the harness catch `jsonschema.ValidationError` directly.

Plural enumeration is the per-AC test file's responsibility (parametrize
over a directory glob); this loader handles one file at a time.

References:
    - Architecture L737 (`load_fixture(path) -> ConformanceFixture`)
    - Architecture Decision-4 L724-751 (JSON+jsonschema)
    - ADR-005 L17-22 (fidelity-oracle contract)
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from .types import ConformanceFixture

__all__ = ["load_fixture", "SCHEMA_PATH"]


SCHEMA_PATH = Path(__file__).parent / "fixture-schema.json"


def _load_schema() -> dict:
    """Load + return the parsed fixture-schema.json contents."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_fixture(path: Path) -> ConformanceFixture:
    """Load + schema-validate a single fixture JSON file.

    Args:
        path: Path to a fixture JSON file at
            `tests/conformance/fixtures/<adapter>/<scenario>.json`.

    Returns:
        Populated `ConformanceFixture` instance.

    Raises:
        jsonschema.ValidationError: schema violation (per Story 1b.5 D7
            ratification — no new agenteval error class).
        FileNotFoundError: path does not exist.
        json.JSONDecodeError: malformed JSON.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=raw, schema=_load_schema())
    return ConformanceFixture(
        schema_version=raw["_schema_version"],
        adapter_name=raw["adapter_name"],
        scenario_name=raw["scenario_name"],
        agent_run_result=raw["agent_run_result"],
        expected_tool_calls=raw["expected_tool_calls"],
        expected_errors=raw["expected_errors"],
        reproducibility_footer=raw["reproducibility_footer"],
    )
