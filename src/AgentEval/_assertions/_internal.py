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

"""Internal projection + matching helpers for `AssertionsLibrary` (Story 6.2).

Per architecture L1291 + Story 6.1 `metrics/_internal.py` precedent:
helpers live here as pure functions so Story 6.3 (`Stat.*`) + Story 6.4
dogfood can re-use without going through the keyword surface.

**Phase-1 backend per Story 6.2 D-1 drift fix (AC-6.2.1):** assertions
use stdlib (`re`, `jsonschema`) for matching; `Should Be Equal` /
`Should Contain` / `Should Match Regexp` RF-builtin integration happens
at the library layer. AssertionEngine integration is Story 6.3 scope.

Per Story 2.1 sub-library discipline: NO re-exports from
`_assertions/__init__.py`.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from AgentEval.metrics import _internal as _metrics_internal
from AgentEval.types import AgentRunResult, ToolCallTrace

# --------------------------------------------------------------------------- #
# Trajectory match helpers (4 modes per PRD FR23a + FR23b)                    #
# --------------------------------------------------------------------------- #


def _match_trajectory_exact(observed: list[str], expected: list[str]) -> bool:
    """`mode=exact` per FR23a: ordered list equality (no extras allowed)."""
    return observed == expected


def _match_trajectory_subsequence(observed: list[str], expected: list[str]) -> bool:
    """`mode=subsequence` per FR23a: `expected` is a subsequence of `observed`.

    Order preserved; extras between/around expected entries allowed. Greedy
    left-to-right walk: advance the `expected` pointer on each match.
    """
    if not expected:
        return True  # Empty expected always satisfies subsequence.
    e_idx = 0
    for name in observed:
        if name == expected[e_idx]:
            e_idx += 1
            if e_idx == len(expected):
                return True
    return False


def _match_trajectory_set(observed: list[str], expected: list[str]) -> bool:
    """`mode=set` per FR23a: unordered, no extras (exact set equality)."""
    return set(observed) == set(expected)


def _match_trajectory_regex(observed_tool_calls: list[ToolCallTrace], expected: list[str]) -> bool:
    """`mode=regex` per PRD FR23b verbatim: each `expected[i]` is a regex
    matched via `re.fullmatch` against the concatenation
    `"<tool_name>:<json.dumps(args, sort_keys=True, default=str)>"` of each step.

    List-length equality required (one regex per tool call). Args are
    serialized with `sort_keys=True` so regex authors can rely on a
    deterministic textual form regardless of input dict ordering.

    Story 6.2 code-review HIGH-γ fix (Blind + Edge 2-way): `default=str` so
    non-JSON-serializable arg values (e.g., `datetime`, `bytes`, custom
    objects) degrade to their `str()` repr instead of raising a confusing
    `TypeError` from inside the assertion keyword. `ToolCallTrace.args` is
    `Mapping[str, Any]` with no JSON-shape constraint at the observer
    boundary, so this matters in practice.
    """
    if len(observed_tool_calls) != len(expected):
        return False
    for tc, pattern in zip(observed_tool_calls, expected, strict=True):
        serialized = f"{tc.name}:{json.dumps(dict(tc.args), sort_keys=True, default=str)}"
        if not re.fullmatch(pattern, serialized):
            return False
    return True


# --------------------------------------------------------------------------- #
# Tool-call match helper (PRD FR24)                                           #
# --------------------------------------------------------------------------- #


def _dict_is_subset(subset: dict[str, Any], superset: dict[str, Any]) -> bool:
    """Recursive dict-subset matcher per FR24 "dict-subset semantics".

    Every key in `subset` must exist in `superset` with an equal value.
    Nested dicts are recursed; non-dict values use `==`. Extra keys in
    `superset` are allowed.
    """
    for key, sub_val in subset.items():
        if key not in superset:
            return False
        sup_val = superset[key]
        if isinstance(sub_val, dict) and isinstance(sup_val, dict):
            if not _dict_is_subset(sub_val, sup_val):
                return False
        elif sub_val != sup_val:
            return False
    return True


_VALID_TOOL_CALL_MATCH_MODES = ("subset", "exact")


def _match_tool_call(
    tc: ToolCallTrace,
    tool: str,
    args: dict[str, Any] | None,
    match_mode: str,
) -> bool:
    """Match a single `ToolCallTrace` against `tool` + optional `args` (PRD FR24).

    - Name must match exactly.
    - `args=None`: name match sufficient.
    - `match_mode="subset"` (default per FR24): `args` is a dict-subset of `tc.args`.
    - `match_mode="exact"`: `args == tc.args` exact equality.

    Story 6.2 code-review HIGH-α fix (Edge HIGH-2 + Codex probe 3-way):
    validate `match_mode` BEFORE the `args is None` short-circuit so an
    invalid mode raises `ValueError` immediately regardless of args value.
    Pre-edit: `match_mode="bogus"` + `args=None` silently returned True
    (when name matched), masking caller typos until args were supplied.
    """
    if match_mode not in _VALID_TOOL_CALL_MATCH_MODES:
        raise ValueError(f"match_mode must be one of: {', '.join(_VALID_TOOL_CALL_MATCH_MODES)}; got {match_mode!r}")
    if tc.name != tool:
        return False
    if args is None:
        return True
    tc_args = dict(tc.args)
    if match_mode == "exact":
        return tc_args == args
    # match_mode == "subset" (validated above).
    return _dict_is_subset(args, tc_args)


# --------------------------------------------------------------------------- #
# Schema resolution helper (PRD FR25 + Story 6.2 D-4 fix)                     #
# --------------------------------------------------------------------------- #


def _resolve_schema(schema: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Resolve a schema argument to a parsed JSON Schema dict (D-4 dispatch).

    - `dict`: returned as-is.
    - `str` or `Path`: treated as a file path; `Path(schema).read_text()`
      then `json.loads`. Raises `ValueError` if not a file.

    Story 6.2 code-review HIGH-β fix (Edge HIGH-3 + Codex probe + Blind
    HIGH-3 3-way): (1) `isinstance(schema, (str, Path))` guard so an
    unexpected input type (`list`, `int`, `None`) raises the documented
    `ValueError` instead of leaking a bare `TypeError` from `pathlib`.
    (2) Validate the loaded JSON IS a dict — Codex probe showed a file
    containing `[1, 2, 3]` previously returned a `list`, breaking the
    declared return type and producing a confusing downstream
    `jsonschema` error.
    """
    if isinstance(schema, dict):
        return schema
    if not isinstance(schema, (str, Path)):
        raise ValueError(
            f"schema must be a dict OR a path to a JSON Schema file (str/Path); got type {type(schema).__name__}"
        )
    path = Path(schema)
    if not path.is_file():
        raise ValueError(f"schema must be a dict OR a path to a JSON Schema file; got: {schema!r}")
    loaded: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(
            f"schema file at {path!r} must contain a JSON object (dict); got top-level {type(loaded).__name__}"
        )
    return loaded


# --------------------------------------------------------------------------- #
# Budget-assertion helpers (add-budget-assertion-keywords change)             #
#                                                                             #
# Shared validation + evidence-message builders for the four Tier-1 budget    #
# assertion keywords (`Cost Should Be Below`, `Latency Should Be Below`,      #
# `Latency P95 Should Be Below`, `Token Usage Should Be Below`). Computation  #
# reuses the `metrics/_internal` compute/aggregate helper pairs (design D2)   #
# so a budget assertion can never drift from its corresponding getter.        #
# --------------------------------------------------------------------------- #


def _validate_budget_threshold(threshold: float, *, unit: str) -> None:
    """Raise `ValueError` when a budget threshold is non-finite or ``<= 0`` (design D6).

    All four observed budget values are non-negative, so a ``<= 0`` threshold
    can never pass and is always a caller typo; ``NaN`` / ``inf`` thresholds are
    nonsense. This caller-typo gate fires BEFORE assertion dispatch (same
    ordering principle as the Story 6.2 `mode`-validation fix).
    """
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError(f"threshold must be a finite number greater than 0 (unit: {unit}); got {threshold!r}")


def _guard_non_empty_result(result: AgentRunResult | list[AgentRunResult]) -> None:
    """Raise `ValueError` on an empty-`list` result (fake-green guard, design D6).

    Deliberate, documented divergence from the getters' AC-6.1.8 vacuous-truth
    convention: a budget assertion that trivially passes on zero runs is a
    silent hazard (`Cost Should Be Below ${empty_list} 0.10` passing is the
    exact fake-green class this project's dogfood precheck exists to catch).
    """
    if isinstance(result, list) and not result:
        raise ValueError(
            "result must not be an empty list — a budget assertion over zero runs "
            "would trivially pass (fake-green guard; deliberate divergence from the "
            "getters' empty-list vacuous-truth convention per design D6)"
        )


def _budget_run_count(result: AgentRunResult | list[AgentRunResult]) -> int:
    """Number of runs aggregated (``len`` for a list, else ``1``)."""
    return len(result) if isinstance(result, list) else 1


def _budget_message_prefix(label: str, unit: str, run_count: int) -> str:
    """Build the AssertionEngine `message=` prefix (e.g. ``Cost (USD, 3 runs aggregated)``).

    The AssertionEngine 4.x `verify_assertion(message=...)` PREFIXES this text
    before its standard ``'<actual>' (float) should be less than '<expected>'
    (float)`` body (empirically confirmed at implementation time, task 1.1), so
    the full failure message carries the label + unit + run count AND the
    observed value + threshold.
    """
    plural = "s" if run_count != 1 else ""
    return f"{label} ({unit}, {run_count} run{plural} aggregated)"


def _budget_pass_evidence(
    label: str,
    unit: str,
    observed: float,
    threshold: float,
    run_count: int,
) -> str:
    """Build the pass-side `robot.api.logger.info` evidence line (design D7 / AC-SIMPLICITY-01)."""
    return f"{label} assertion passed: observed={observed} {unit}, threshold={threshold} {unit}, runs={run_count}"


def _compute_token_total(result: AgentRunResult) -> int:
    """Single-run total tokens = ``input_tokens + output_tokens`` (design D4).

    Reuses `metrics/_internal._compute_token_usage`. `cached_input_tokens` and
    `reasoning_output_tokens` are accounting sub-fields (cached input is a
    subset view of input; providers report reasoning inside `output_tokens`)
    and are NOT added separately — that would double-count.
    """
    usage = _metrics_internal._compute_token_usage(result)
    return usage.input_tokens + usage.output_tokens


def _aggregate_token_total(results: list[AgentRunResult]) -> int:
    """Multi-trial total tokens: per-field sum first, then ``input + output`` (design D4)."""
    usage = _metrics_internal._aggregate_token_usage(results)
    return usage.input_tokens + usage.output_tokens
