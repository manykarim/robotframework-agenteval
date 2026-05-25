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

"""Story 6.4 dogfood fixture helper — `AgentRunResult` builders parallel-derived
from `robotframework-agentskills`' scoring-test domain (AC-6.4.6).

Per Story 6.4 D-2 framing reframe + D-4 carry-out (DF-5.5-DOGFOOD-2 / C44 +
DF-6.1-S1 / C46): Phase-1 `Metric.*` keywords read from `AgentRunResult` fields
directly (NOT `_kernel/trace_store` spans), so dogfood `.robot` suites must
fixture `AgentRunResult` objects via this helper rather than driving a live
multi-turn MCP+LLM loop (deferred per C43).

The `build_run_from_session()` shape mirrors `robotframework-agentskills`'
session-event domain (`SessionRecord` from `src/rf_skill_eval/domain/events.py`
+ `Scorecard` from `domain/scorecard.py`) so dogfood tests exercise
parity-of-semantics rather than verbatim test ports.

Three canned scenarios cover the common scoring-test shapes:

- `successful_search_session()` — happy-path single-tool search with full completeness.
- `unnecessary_tool_call_session()` — agent called a tool not in the expected
  set (exercises `Get Unnecessary Call Rate`).
- `partial_completeness_session()` — task incomplete; `Pass At K` predicate
  must explicitly check `completeness == "complete"` (NOT `"full"` — see
  Story 6.4 DOGFOOD-FINDING-1 / DF-6.4-S1 for the upstream Story 6.3 default-
  predicate fake-green bug that this dogfood loop surfaced).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage

_FIXTURE_ROOT = Path(__file__).parent / "sessions"


def build_run_from_session(session: Mapping[str, Any]) -> AgentRunResult:
    """Parallel-derive an `AgentRunResult` from an agentskills-shaped session dict.

    Story 6.4 code-review HIGH-γ fix 2026-05-20 (Blind HIGH-1 + Edge HIGH-4
    3-way): pre-edit docstring listed `"full" | "partial" | "incomplete"` +
    `"hosted_mcp"` as valid values — but `AgentRunMetadata._VALID_COMPLETENESS`
    is `("complete", "truncated", "partial")` + `_VALID_MCP_COVERAGE` is
    `("hosted_in_process", "subprocess_with_observer", "external_mixed")`.
    `"hosted_mcp"` is a `ToolCallTrace.source` value, NOT a metadata coverage
    value. Pre-edit defaults (`completeness="full"`) would have raised
    `ValueError` at runtime on empty session dicts; defaults now use the
    actual ratified values.

    The session shape mirrors `rf_skill_eval/domain/events.SessionRecord`:
      - `tool_calls`: list of `{name, args, result, error, latency_ms}` dicts.
      - `usage`: `{input_tokens, output_tokens, cached_input_tokens}` dict.
      - `response_text`: agent's final reply.
      - `cost_usd`: scalar.
      - `latency_seconds`: scalar.
      - `completeness`: `"complete" | "truncated" | "partial"` per types.py:317.
      - `mcp_coverage`: `"hosted_in_process" | "subprocess_with_observer" | "external_mixed"`
        per types.py:318-320.

    Returns an `AgentRunResult` consumable by Story 6.1-6.3 keywords.
    """
    tool_calls: list[ToolCallTrace] = []
    for idx, raw in enumerate(session.get("tool_calls", [])):
        tool_calls.append(
            ToolCallTrace(
                name=raw["name"],
                args=raw.get("args", {}),
                result=raw.get("result"),
                error=raw.get("error"),
                latency_ms=float(raw.get("latency_ms", 0.0)),
                source=raw.get("source", "hosted_mcp"),
                gen_ai_tool_call_id=raw.get("gen_ai_tool_call_id", f"t-{idx}"),
                sequence_index=idx,
            )
        )
    usage_raw = session.get("usage", {})
    usage = Usage(
        input_tokens=int(usage_raw.get("input_tokens", 0)),
        output_tokens=int(usage_raw.get("output_tokens", 0)),
        cached_input_tokens=int(usage_raw.get("cached_input_tokens", 0)),
    )
    metadata = AgentRunMetadata(
        completeness=session.get("completeness", "complete"),  # type: ignore[arg-type]
        mcp_coverage=session.get("mcp_coverage", "hosted_in_process"),  # type: ignore[arg-type]
    )
    return AgentRunResult(
        response_text=session.get("response_text", ""),
        tool_calls=tool_calls,
        usage=usage,
        metadata=metadata,
        cost_usd=float(session.get("cost_usd", 0.0)),
        latency_seconds=float(session.get("latency_seconds", 0.0)),
        trace_id=session.get("trace_id", "t" + "0" * 30),
    )


def load_fixture_session(name: str) -> dict[str, Any]:
    """Load a known-good session fixture from `tests/dogfood/agentskills/fixtures/sessions/<name>.json`."""
    path = _FIXTURE_ROOT / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"Session fixture {name!r} not found at {path!r}; "
            f"available: {sorted(p.stem for p in _FIXTURE_ROOT.glob('*.json'))!r}"
        )
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def successful_search_session() -> dict[str, Any]:
    """Happy-path: single tool call (`search`) + full completeness + hosted MCP."""
    return {
        "response_text": "Found 3 results for 'paris'.",
        "tool_calls": [
            {
                "name": "search",
                "args": {"query": "paris", "limit": 3},
                "result": "OK: 3 results",
                "error": None,
                "latency_ms": 120.5,
                "source": "hosted_mcp",
                "gen_ai_tool_call_id": "tc-001",
            },
        ],
        "usage": {"input_tokens": 50, "output_tokens": 30, "cached_input_tokens": 0},
        "cost_usd": 0.0042,
        "latency_seconds": 0.85,
        "completeness": "complete",
        "mcp_coverage": "hosted_in_process",
        "trace_id": "t" + "1" * 30,
    }


def unnecessary_tool_call_session() -> dict[str, Any]:
    """Agent called `delete` which wasn't in the expected toolset — exercises Unnecessary Call Rate."""
    return {
        "response_text": "Operation complete.",
        "tool_calls": [
            {
                "name": "search",
                "args": {"query": "x"},
                "result": "OK",
                "error": None,
                "latency_ms": 100.0,
                "source": "hosted_mcp",
                "gen_ai_tool_call_id": "tc-100",
            },
            {
                "name": "delete",  # unnecessary — not in expected toolset
                "args": {"id": "x"},
                "result": "OK",
                "error": None,
                "latency_ms": 80.0,
                "source": "hosted_mcp",
                "gen_ai_tool_call_id": "tc-101",
            },
        ],
        "usage": {"input_tokens": 100, "output_tokens": 50, "cached_input_tokens": 10},
        "cost_usd": 0.0091,
        "latency_seconds": 1.2,
        "completeness": "complete",
        "mcp_coverage": "hosted_in_process",
        "trace_id": "t" + "2" * 30,
    }


def partial_completeness_session() -> dict[str, Any]:
    """Task incomplete — Pass@k default predicate (`completeness == "full"`) fails."""
    return {
        "response_text": "I couldn't complete the task.",
        "tool_calls": [
            {
                "name": "search",
                "args": {"query": "x"},
                "result": None,
                "error": "timeout",
                "latency_ms": 5000.0,
                "source": "hosted_mcp",
                "gen_ai_tool_call_id": "tc-200",
            },
        ],
        "usage": {"input_tokens": 75, "output_tokens": 20, "cached_input_tokens": 0},
        "cost_usd": 0.0028,
        "latency_seconds": 5.1,
        "completeness": "partial",
        "mcp_coverage": "hosted_in_process",
        "trace_id": "t" + "3" * 30,
    }


def external_mixed_coverage_session() -> dict[str, Any]:
    """`mcp_coverage="external_mixed"` — exercises FR37 `IncompleteTraceError` gate."""
    return {
        "response_text": "Done.",
        "tool_calls": [
            {
                "name": "search",
                "args": {"query": "x"},
                "result": "OK",
                "error": None,
                "latency_ms": 200.0,
                "source": "hosted_mcp",
                "gen_ai_tool_call_id": "tc-300",
            },
        ],
        "usage": {"input_tokens": 60, "output_tokens": 25, "cached_input_tokens": 0},
        "cost_usd": 0.0035,
        "latency_seconds": 0.95,
        "completeness": "complete",
        "mcp_coverage": "external_mixed",
        "trace_id": "t" + "4" * 30,
    }


# RF-keyword-friendly entry points (callable from `.robot` Library imports).


def get_successful_search_run() -> AgentRunResult:
    """Build an `AgentRunResult` from the canned `successful_search_session` shape."""
    return build_run_from_session(successful_search_session())


def get_unnecessary_tool_call_run() -> AgentRunResult:
    """Build an `AgentRunResult` from the `unnecessary_tool_call_session` shape."""
    return build_run_from_session(unnecessary_tool_call_session())


def get_partial_completeness_run() -> AgentRunResult:
    """Build an `AgentRunResult` from the `partial_completeness_session` shape."""
    return build_run_from_session(partial_completeness_session())


def get_external_mixed_coverage_run() -> AgentRunResult:
    """Build an `AgentRunResult` carrying `mcp_coverage="external_mixed"`."""
    return build_run_from_session(external_mixed_coverage_session())


def get_tier_1_tagged_successful_search_run() -> Any:
    """Wrap `get_successful_search_run` as a `@tier(1)`-tagged callable.

    Story 6.4 code-review HIGH-α fix 2026-05-20 (Edge HIGH-1 + Auditor HIGH-1):
    `Stat.Assert Run Determinism` callable-form path (Story 6.3) checks the
    callable's `_agenteval_tier` attribute. This factory exposes a Python
    callable that's tagged Tier-1 so the dogfood test can exercise
    `Stat.Assert Run Determinism` per AC-6.4.4 verbatim.
    """

    def _tier_1_callable() -> AgentRunResult:
        return get_successful_search_run()

    _tier_1_callable._agenteval_tier = 1  # type: ignore[attr-defined]
    return _tier_1_callable


def build_json_response_run() -> AgentRunResult:
    """AgentRunResult with a JSON-shaped `response_text` for schema-validation dogfood tests.

    Story 6.4 code-review HIGH-β fix 2026-05-20 (Edge HIGH-2): exercises
    `Agent Response Should Match Schema` per AC-6.4.3 verbatim — pre-edit
    assertions suite missed this keyword entirely.
    """
    session = successful_search_session()
    session["response_text"] = '{"name": "paris", "result_count": 3, "tags": ["city", "capital"]}'
    return build_run_from_session(session)


def get_runs_with_mixed_outcomes(n: int = 10, pass_count: int = 6) -> list[AgentRunResult]:
    """Build `n` runs where `pass_count` have `completeness="full"` (rest are `"partial"`).

    Used by `Stat.Get Pass At K` dogfood tests to exercise the HumanEval
    unbiased estimator against a known c/n ratio.
    """
    if pass_count < 0 or pass_count > n:
        raise ValueError(f"pass_count must be in [0, n]; got pass_count={pass_count!r} n={n!r}")
    runs: list[AgentRunResult] = []
    for i in range(n):
        is_pass = i < pass_count
        session = successful_search_session() if is_pass else partial_completeness_session()
        # `AgentRunMetadata.completeness` valid values are `complete/partial/truncated`
        # (NOT `"full"` — Story 6.4 DOGFOOD-FINDING-1: Story 6.3 default
        # Pass@k predicate uses `"full"` which never matches AgentRunResult
        # output; tracked as DF-6.4-S1).
        session["completeness"] = "complete" if is_pass else "partial"
        session["trace_id"] = f"t{i:031d}"
        runs.append(build_run_from_session(session))
    return runs


def build_keyword_runs_from_fixtures(
    fixture_runs: list[AgentRunResult],
) -> list[Any]:
    """Build `KeywordRun` trials directly from a list of `AgentRunResult` fixtures.

    Story 6.4 helper: `Stat.Run N Times` wraps a CALLABLE not a list of pre-built
    results, but the dogfood suites want to compute `Pass@k` over PRE-BUILT
    fixture runs (no live trials needed). This synthesizes the `KeywordRun`
    shape directly so `Stat.Get Pass At K` can consume them.
    """
    from AgentEval.stats.types import KeywordRun

    keyword_runs: list[Any] = []
    for i, run in enumerate(fixture_runs):
        completeness = getattr(run.metadata, "completeness", "n/a") if run.metadata else "n/a"
        keyword_runs.append(
            KeywordRun(
                trial_index=i,
                test_id=f"dogfood::trial-{i}",
                keyword_name="fixture_run",
                result=run,
                error=None,
                completeness=completeness,
                latency_seconds=run.latency_seconds,
                seed=None,
            )
        )
    return keyword_runs


def build_complete_predicate() -> Any:
    """Predicate factory: returns `lambda r: r.completeness == "complete"`.

    Story 6.4 dogfood ORIGINALLY shipped this as a DOGFOOD-FINDING-1 workaround
    for Story 6.3's `_default_pass_predicate` returning `r.completeness == "full"`
    (which is never True since valid values are `complete/partial/truncated`).
    **The upstream bug was fixed in lockstep via Story 6.4 code-review fix-NOW
    pattern** (`feedback_citation_drift_first_class`): `stats/_internal.py:_default_pass_predicate`
    + `stats/library.py` docstring + epic AC-2 verbatim wording all flipped
    `"full"` → `"complete"`. This factory remains as an explicit-predicate
    convenience for dogfood tests that want to make the pass-criterion textually
    visible in the `.robot` source.
    """
    return lambda r: r.completeness == "complete"


__all__ = [
    "build_run_from_session",
    "load_fixture_session",
    "successful_search_session",
    "unnecessary_tool_call_session",
    "partial_completeness_session",
    "external_mixed_coverage_session",
    "get_successful_search_run",
    "get_unnecessary_tool_call_run",
    "get_partial_completeness_run",
    "get_external_mixed_coverage_run",
    "get_runs_with_mixed_outcomes",
    "build_keyword_runs_from_fixtures",
    "build_complete_predicate",
    "build_json_response_run",
    "get_tier_1_tagged_successful_search_run",
]
