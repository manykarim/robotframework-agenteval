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

"""Unit tests for `AssertionsLibrary` (Story 6.2 AC-6.2.10).

~32 tests covering 4 trajectory modes + tool-call match + 3 response
variants + IncompleteTraceError gate + invalid mode.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from AgentEval._assertions.library import AssertionsLibrary
from AgentEval.errors import IncompleteTraceError
from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage


def _trace(
    name: str,
    *,
    args: dict | None = None,
    error: str | None = None,
    sequence_index: int = 0,
) -> ToolCallTrace:
    return ToolCallTrace(
        name=name,
        args=args or {},
        result=None if error else "ok",
        error=error,
        latency_ms=10.0,
        source="hosted_mcp",
        gen_ai_tool_call_id=f"t-{sequence_index}",
        sequence_index=sequence_index,
    )


def _result(
    tool_calls: list[ToolCallTrace] | None = None,
    *,
    response_text: str = "ok",
    mcp_coverage: str = "hosted_in_process",
) -> AgentRunResult:
    return AgentRunResult(
        response_text=response_text,
        tool_calls=tool_calls or [],
        usage=Usage(input_tokens=1, output_tokens=1),
        metadata=AgentRunMetadata(
            completeness="complete",
            mcp_coverage=mcp_coverage,  # type: ignore[arg-type]
        ),
        cost_usd=0.0,
        latency_seconds=0.0,
        trace_id="t-" + "0" * 30,
    )


# --------------------------------------------------------------------------- #
# Trajectory Should Match — 4 modes × happy + fail                            #
# --------------------------------------------------------------------------- #


def test_trajectory_should_match_exact_pass() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("search"), _trace("search", sequence_index=1), _trace("fetch", sequence_index=2)])
    lib.trajectory_should_match(result, expected=["search", "search", "fetch"], mode="exact")


def test_trajectory_should_match_exact_fail_on_wrong_order() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("search"), _trace("fetch", sequence_index=1)])
    with pytest.raises(AssertionError, match=r"Trajectory mismatch"):
        lib.trajectory_should_match(result, expected=["fetch", "search"], mode="exact")


def test_trajectory_should_match_subsequence_pass_with_extras() -> None:
    lib = AssertionsLibrary()
    # Subsequence allows extras between expected matches.
    result = _result(
        [
            _trace("a"),
            _trace("search", sequence_index=1),
            _trace("b", sequence_index=2),
            _trace("fetch", sequence_index=3),
        ]
    )
    lib.trajectory_should_match(result, expected=["search", "fetch"], mode="subsequence")


def test_trajectory_should_match_subsequence_fail_on_wrong_order() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("fetch"), _trace("search", sequence_index=1)])
    with pytest.raises(AssertionError):
        lib.trajectory_should_match(result, expected=["search", "fetch"], mode="subsequence")


def test_trajectory_should_match_set_pass_any_order() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("fetch"), _trace("search", sequence_index=1)])
    lib.trajectory_should_match(result, expected=["search", "fetch"], mode="set")


def test_trajectory_should_match_set_fail_on_missing_tool() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("search")])
    with pytest.raises(AssertionError):
        lib.trajectory_should_match(result, expected=["search", "fetch"], mode="set")


def test_trajectory_should_match_regex_pass_with_name_and_args_concatenation() -> None:
    """Per PRD FR23b verbatim: regex matches `name:json.dumps(args, sort_keys=True)`."""
    lib = AssertionsLibrary()
    result = _result(
        [
            _trace("search", args={"query": "foo"}),
            _trace("fetch", args={"url": "http://x"}, sequence_index=1),
        ]
    )
    lib.trajectory_should_match(
        result,
        expected=[r"search:\{.*\"foo\".*\}", r"fetch:\{.*\"url\".*\}"],
        mode="regex",
    )


def test_trajectory_should_match_regex_fail_on_length_mismatch() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("search")])
    with pytest.raises(AssertionError):
        lib.trajectory_should_match(result, expected=[r"search:.*", r"fetch:.*"], mode="regex")


def test_trajectory_should_match_invalid_mode_raises_value_error() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("a")])
    with pytest.raises(ValueError, match=r"mode must be one of"):
        lib.trajectory_should_match(result, expected=["a"], mode="bogus")


# --------------------------------------------------------------------------- #
# Tool Call Should Have Occurred — dict-subset + exact + error paths          #
# --------------------------------------------------------------------------- #


def test_tool_call_should_have_occurred_name_only_match() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("search", args={"query": "foo", "limit": 10})])
    lib.tool_call_should_have_occurred(result, tool="search")


def test_tool_call_should_have_occurred_subset_match() -> None:
    """Dict-subset default per FR24: `{"query": "foo"}` ⊆ `{"query": "foo", "limit": 10}`."""
    lib = AssertionsLibrary()
    result = _result([_trace("search", args={"query": "foo", "limit": 10})])
    lib.tool_call_should_have_occurred(result, tool="search", args={"query": "foo"})


def test_tool_call_should_have_occurred_exact_match_pass() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("search", args={"query": "foo"})])
    lib.tool_call_should_have_occurred(result, tool="search", args={"query": "foo"}, match_mode="exact")


def test_tool_call_should_have_occurred_subset_fails_on_value_mismatch() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("search", args={"query": "foo"})])
    with pytest.raises(AssertionError, match=r"No tool call matched"):
        lib.tool_call_should_have_occurred(result, tool="search", args={"query": "bar"})


def test_tool_call_should_have_occurred_exact_fails_on_extra_key() -> None:
    """Exact mode requires `tc.args == args` — extra `limit` key in observed fails."""
    lib = AssertionsLibrary()
    result = _result([_trace("search", args={"query": "foo", "limit": 10})])
    with pytest.raises(AssertionError):
        lib.tool_call_should_have_occurred(result, tool="search", args={"query": "foo"}, match_mode="exact")


def test_tool_call_should_have_occurred_missing_tool_fails() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("search")])
    with pytest.raises(AssertionError):
        lib.tool_call_should_have_occurred(result, tool="fetch")


def test_tool_call_should_have_occurred_invalid_match_mode_raises_value_error() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("search")])
    with pytest.raises(ValueError, match=r"match_mode"):
        lib.tool_call_should_have_occurred(result, tool="search", args={}, match_mode="bogus")


def test_tool_call_should_have_occurred_recursive_dict_subset() -> None:
    """Recursive subset: nested dict-value matching."""
    lib = AssertionsLibrary()
    result = _result([_trace("call", args={"opts": {"timeout": 30, "retries": 3}, "key": "v"})])
    lib.tool_call_should_have_occurred(result, tool="call", args={"opts": {"timeout": 30}})


# --------------------------------------------------------------------------- #
# Agent Response Should Contain                                                #
# --------------------------------------------------------------------------- #


def test_agent_response_should_contain_pass() -> None:
    lib = AssertionsLibrary()
    lib.agent_response_should_contain(_result(response_text="The capital is Paris."), "Paris")


def test_agent_response_should_contain_fail() -> None:
    lib = AssertionsLibrary()
    with pytest.raises(AssertionError, match=r"not found"):
        lib.agent_response_should_contain(_result(response_text="The capital is Paris."), "Berlin")


# --------------------------------------------------------------------------- #
# Agent Response Should Match Regex                                            #
# --------------------------------------------------------------------------- #


def test_agent_response_should_match_regex_pass() -> None:
    lib = AssertionsLibrary()
    lib.agent_response_should_match_regex(_result(response_text="The capital is Paris."), r"capital is (\w+)")


def test_agent_response_should_match_regex_fail() -> None:
    lib = AssertionsLibrary()
    with pytest.raises(AssertionError):
        lib.agent_response_should_match_regex(_result(response_text="The capital is Paris."), r"^Berlin")


def test_agent_response_should_match_regex_multiline() -> None:
    """Multi-line text matching via re flag in pattern."""
    lib = AssertionsLibrary()
    lib.agent_response_should_match_regex(
        _result(response_text="line one\nline two\nline three"),
        r"(?m)^line two$",
    )


# --------------------------------------------------------------------------- #
# Agent Response Should Match Schema                                           #
# --------------------------------------------------------------------------- #


def test_agent_response_should_match_schema_dict_pass() -> None:
    lib = AssertionsLibrary()
    lib.agent_response_should_match_schema(
        _result(response_text='{"name": "x", "value": 42}'),
        schema={"type": "object", "required": ["name", "value"]},
    )


def test_agent_response_should_match_schema_dict_fail() -> None:
    lib = AssertionsLibrary()
    with pytest.raises(jsonschema.ValidationError):
        lib.agent_response_should_match_schema(
            _result(response_text='{"name": "x"}'),
            schema={"type": "object", "required": ["name", "value"]},
        )


def test_agent_response_should_match_schema_path_pass(tmp_path: Path) -> None:
    """D-4 dispatch: file-path schema."""
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps({"type": "object", "required": ["a"]}))
    lib = AssertionsLibrary()
    lib.agent_response_should_match_schema(_result(response_text='{"a": 1}'), schema=str(schema_path))


def test_agent_response_should_match_schema_invalid_path_raises_value_error() -> None:
    """D-4 dispatch: string that's not a file path raises ValueError."""
    lib = AssertionsLibrary()
    with pytest.raises(ValueError, match=r"schema must be"):
        lib.agent_response_should_match_schema(
            _result(response_text='{"a": 1}'),
            schema="/definitely/not/a/file.json",
        )


def test_agent_response_should_match_schema_non_json_response_raises() -> None:
    """Non-JSON response_text raises AssertionError with prefix."""
    lib = AssertionsLibrary()
    with pytest.raises(AssertionError, match=r"not valid JSON"):
        lib.agent_response_should_match_schema(
            _result(response_text="this is not JSON"),
            schema={"type": "object"},
        )


# --------------------------------------------------------------------------- #
# IncompleteTraceError gate (4 tests per AC-6.2.6)                            #
# --------------------------------------------------------------------------- #


def test_trajectory_should_match_raises_on_external_mixed_by_default() -> None:
    """Verifies `metric_keyword="Trajectory Should Match"` threads into the FR37 message."""
    lib = AssertionsLibrary()
    result = _result([_trace("a")], mcp_coverage="external_mixed")
    with pytest.raises(IncompleteTraceError, match=r"Trajectory Should Match"):
        lib.trajectory_should_match(result, expected=["a"])


def test_trajectory_should_match_opts_out_via_allow_external_mcp_blind() -> None:
    lib = AssertionsLibrary(allow_external_mcp_blind=True)
    result = _result([_trace("a")], mcp_coverage="external_mixed")
    lib.trajectory_should_match(result, expected=["a"])


def test_tool_call_should_have_occurred_raises_on_external_mixed_by_default() -> None:
    lib = AssertionsLibrary()
    result = _result([_trace("a")], mcp_coverage="external_mixed")
    with pytest.raises(IncompleteTraceError, match=r"Tool Call Should Have Occurred"):
        lib.tool_call_should_have_occurred(result, tool="a")


def test_tool_call_should_have_occurred_opts_out_via_allow_external_mcp_blind() -> None:
    lib = AssertionsLibrary(allow_external_mcp_blind=True)
    result = _result([_trace("a")], mcp_coverage="external_mixed")
    lib.tool_call_should_have_occurred(result, tool="a")


# --------------------------------------------------------------------------- #
# Response assertions do NOT gate on mcp_coverage (3 tests per AC-6.2.1)      #
# --------------------------------------------------------------------------- #


def test_agent_response_should_contain_does_not_gate_on_external_mixed() -> None:
    lib = AssertionsLibrary()
    result = _result(response_text="ok", mcp_coverage="external_mixed")
    lib.agent_response_should_contain(result, "ok")


def test_agent_response_should_match_regex_does_not_gate_on_external_mixed() -> None:
    lib = AssertionsLibrary()
    result = _result(response_text="ok", mcp_coverage="external_mixed")
    lib.agent_response_should_match_regex(result, r"ok")


def test_agent_response_should_match_schema_does_not_gate_on_external_mixed() -> None:
    lib = AssertionsLibrary()
    result = _result(response_text='{"k": 1}', mcp_coverage="external_mixed")
    lib.agent_response_should_match_schema(result, {"type": "object"})


# --------------------------------------------------------------------------- #
# Empty / boundary cases                                                       #
# --------------------------------------------------------------------------- #


def test_trajectory_should_match_subsequence_empty_expected_passes() -> None:
    """Empty expected vacuously satisfies subsequence."""
    lib = AssertionsLibrary()
    lib.trajectory_should_match(_result([_trace("a")]), expected=[], mode="subsequence")


def test_trajectory_should_match_exact_empty_observed_and_expected() -> None:
    """Both empty → trivially equal."""
    lib = AssertionsLibrary()
    lib.trajectory_should_match(_result([]), expected=[], mode="exact")


# --------------------------------------------------------------------------- #
# Story 6.2 code-review HIGH/MED regression tests (8 tests)                   #
# --------------------------------------------------------------------------- #


def test_match_tool_call_invalid_match_mode_with_args_none_raises_value_error() -> None:
    """HIGH-α regression (Edge HIGH-2 + Codex probe 3-way): invalid match_mode
    with `args=None` must raise `ValueError` instead of silently returning True.

    Pre-edit: `_match_tool_call(tc, "search", None, "bogus")` returned True
    when name matched, because the `args is None` short-circuit ran before
    the match_mode validation in the `else` branch.
    """
    lib = AssertionsLibrary()
    result = _result([_trace("search")])
    with pytest.raises(ValueError, match=r"match_mode must be one of"):
        lib.tool_call_should_have_occurred(result, tool="search", match_mode="bogus")


def test_match_tool_call_invalid_match_mode_with_no_name_match_raises_value_error() -> None:
    """HIGH-α / Auditor #8 regression: invalid match_mode + no name match
    must raise `ValueError`, not the confusing `AssertionError("No tool
    call matched")`.

    Pre-edit: loop iterated, `_match_tool_call` returned False for each
    name-mismatch, never reached the inner ValueError; library raised
    AssertionError instead, masking the actual configuration bug.
    """
    lib = AssertionsLibrary()
    result = _result([_trace("search")])
    with pytest.raises(ValueError, match=r"match_mode must be one of"):
        lib.tool_call_should_have_occurred(result, tool="missing", args={"q": "x"}, match_mode="bogus")


def test_resolve_schema_non_str_non_path_input_raises_value_error() -> None:
    """HIGH-β regression (Edge HIGH-3 + Codex probe + Blind HIGH-3 3-way):
    passing a `list`/`int`/`None` schema must raise the documented
    `ValueError`, not a bare `TypeError` from `pathlib`.
    """
    lib = AssertionsLibrary()
    result = _result(response_text='{"k": 1}')
    with pytest.raises(ValueError, match=r"schema must be a dict OR a path"):
        lib.agent_response_should_match_schema(result, schema=[1, 2, 3])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match=r"schema must be a dict OR a path"):
        lib.agent_response_should_match_schema(result, schema=42)  # type: ignore[arg-type]


def test_resolve_schema_file_containing_non_dict_raises_value_error(tmp_path: Path) -> None:
    """HIGH-β regression (Codex probe): schema file containing a JSON list
    (or any non-dict top-level value) must raise `ValueError` instead of
    returning a `list` to the caller. Pre-edit returned `[1, 2, 3]` to
    `jsonschema.validate(schema=[...])` which then raised a confusing
    downstream error.
    """
    lib = AssertionsLibrary()
    schema_path = tmp_path / "bad-schema.json"
    schema_path.write_text("[1, 2, 3]")
    with pytest.raises(ValueError, match=r"must contain a JSON object"):
        lib.agent_response_should_match_schema(
            _result(response_text='{"k": 1}'),
            schema=str(schema_path),
        )


def test_trajectory_should_match_regex_non_json_serializable_arg_does_not_crash() -> None:
    """HIGH-γ regression (Blind HIGH-2 + Edge HIGH-1 2-way): non-JSON-
    serializable arg values (e.g., `datetime`) must NOT crash the keyword
    with TypeError. With `default=str`, the value degrades to `str()` so
    the assertion fails (or passes) but doesn't blow up.
    """
    import datetime as _dt

    lib = AssertionsLibrary()
    result = _result(
        [
            _trace("scheduled", args={"when": _dt.datetime(2026, 5, 20)}),  # non-JSON
        ]
    )
    # `default=str` serializes the datetime via its `str()` repr; regex
    # matches the resulting text — the call must NOT raise TypeError.
    lib.trajectory_should_match(
        result,
        expected=[r"scheduled:\{.*2026-05-20.*\}"],
        mode="regex",
    )


def test_tool_call_should_have_occurred_assertion_error_redacts_credentials() -> None:
    """HIGH-δ regression (Edge HIGH-4 / FR38a Story 5.3): when an
    AssertionError is raised, the `Observed:` dump must be `redact()`-
    scrubbed so secrets in tool args don't leak into RF `output.xml`.
    """
    lib = AssertionsLibrary()
    # Use an `sk-...` API-key-shaped value that the default redactor scrubs.
    result = _result([_trace("call", args={"auth": "sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"})])
    with pytest.raises(AssertionError) as exc_info:
        lib.tool_call_should_have_occurred(result, tool="missing")
    # The literal secret must NOT appear; the redactor's [REDACTED] sentinel must.
    assert "sk-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in str(exc_info.value)
    assert "[REDACTED]" in str(exc_info.value)


def test_agent_response_should_contain_assertion_error_redacts_credentials() -> None:
    """HIGH-δ regression (Edge HIGH-4 / FR38a): response-text echo in
    AssertionError must be `redact()`-scrubbed (agents can echo tokens in
    error messages, which previously would have leaked).
    """
    lib = AssertionsLibrary()
    # Agent erroneously echoed an API-key-shaped value into response_text.
    result = _result(response_text="leaked sk-BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB end")
    with pytest.raises(AssertionError) as exc_info:
        lib.agent_response_should_contain(result, "MISSING")
    assert "sk-BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB" not in str(exc_info.value)
    assert "[REDACTED]" in str(exc_info.value)


def test_trajectory_should_match_set_mode_collapses_duplicates() -> None:
    """MED-6 ratification (Edge MED-6 + Auditor #14 2-way): `mode=set`
    uses set-equality semantics per PRD FR23a verbatim, so duplicate
    names collapse. Pins the implementation choice so a future refactor
    to multiset semantics surfaces as a deliberate AC change.
    """
    lib = AssertionsLibrary()
    # observed=["a","a","a"] vs expected=["a"] → set(observed) == set(expected).
    result = _result(
        [
            _trace("a"),
            _trace("a", sequence_index=1),
            _trace("a", sequence_index=2),
        ]
    )
    lib.trajectory_should_match(result, expected=["a"], mode="set")
    # And the reverse: expected with duplicates → still set-equal.
    lib.trajectory_should_match(_result([_trace("a")]), expected=["a", "a"], mode="set")


def test_trajectory_should_match_invalid_mode_on_external_mixed_raises_value_error_first() -> None:
    """MED ordering fix (Blind LOW-17 + Edge MED-7 + Auditor #7 3-way):
    invalid `mode` on an `external_mixed` run must raise `ValueError`
    (input validation), NOT `IncompleteTraceError` (FR37 gate).

    Pre-edit: gate fired first, so caller typos like `mode="exadt"` were
    masked behind a misleading "set allow_external_mcp_blind=True"
    message that didn't address the actual bug.
    """
    lib = AssertionsLibrary()
    result = _result([_trace("a")], mcp_coverage="external_mixed")
    with pytest.raises(ValueError, match=r"mode must be one of"):
        lib.trajectory_should_match(result, expected=["a"], mode="bogus")


# --------------------------------------------------------------------------- #
# Budget assertions — Cost / Latency / Latency P95 / Token Usage              #
# (add-budget-assertion-keywords change / PRD 10-keyword-core debt)           #
# --------------------------------------------------------------------------- #


def _lat_trace(latency_ms: float, *, sequence_index: int = 0) -> ToolCallTrace:
    return ToolCallTrace(
        name="t",
        args={},
        result="ok",
        error=None,
        latency_ms=latency_ms,
        source="hosted_mcp",
        gen_ai_tool_call_id=f"t-{sequence_index}",
        sequence_index=sequence_index,
    )


def _budget_result(
    *,
    cost_usd: float = 0.0,
    latency_seconds: float = 0.0,
    tool_calls: list[ToolCallTrace] | None = None,
    usage: Usage | None = None,
    mcp_coverage: str = "hosted_in_process",
) -> AgentRunResult:
    return AgentRunResult(
        response_text="ok",
        tool_calls=tool_calls or [],
        usage=usage or Usage(input_tokens=0, output_tokens=0),
        metadata=AgentRunMetadata(
            completeness="complete",
            mcp_coverage=mcp_coverage,  # type: ignore[arg-type]
        ),
        cost_usd=cost_usd,
        latency_seconds=latency_seconds,
        trace_id="t-" + "0" * 30,
    )


# ---- Cost Should Be Below ---- #


def test_cost_should_be_below_under_passes() -> None:
    lib = AssertionsLibrary()
    lib.cost_should_be_below(_budget_result(cost_usd=0.05), 0.10)


def test_cost_should_be_below_over_fails_with_actual_threshold_unit() -> None:
    lib = AssertionsLibrary()
    with pytest.raises(AssertionError) as exc:
        lib.cost_should_be_below(_budget_result(cost_usd=0.153), 0.10)
    msg = str(exc.value)
    assert "0.153" in msg
    assert "0.1" in msg
    assert "USD" in msg


def test_cost_should_be_below_equal_fails_strict_less_than() -> None:
    lib = AssertionsLibrary()
    with pytest.raises(AssertionError):
        lib.cost_should_be_below(_budget_result(cost_usd=0.10), 0.10)


def test_cost_should_be_below_multi_trial_sums_like_getter() -> None:
    lib = AssertionsLibrary()
    runs = [_budget_result(cost_usd=0.04) for _ in range(3)]
    # Aggregated total 0.12 is NOT below 0.10 — matches Get Cost Total sum semantics.
    with pytest.raises(AssertionError) as exc:
        lib.cost_should_be_below(runs, 0.10)
    assert "0.12" in str(exc.value)
    # And a headroom threshold passes on the same aggregate.
    lib.cost_should_be_below(runs, 0.20)


# ---- Latency Should Be Below ---- #


def test_latency_should_be_below_under_passes() -> None:
    lib = AssertionsLibrary()
    lib.latency_should_be_below(_budget_result(tool_calls=[_lat_trace(800.0)]), 2000.0)


def test_latency_should_be_below_over_fails_with_actual_threshold_unit() -> None:
    lib = AssertionsLibrary()
    with pytest.raises(AssertionError) as exc:
        lib.latency_should_be_below(_budget_result(tool_calls=[_lat_trace(2500.0)]), 2000.0)
    msg = str(exc.value)
    assert "2500" in msg
    assert "2000" in msg
    assert "ms" in msg


def test_latency_should_be_below_equal_fails_strict_less_than() -> None:
    lib = AssertionsLibrary()
    with pytest.raises(AssertionError):
        lib.latency_should_be_below(_budget_result(tool_calls=[_lat_trace(2000.0)]), 2000.0)


def test_latency_should_be_below_no_tool_calls_uses_run_level_fallback() -> None:
    lib = AssertionsLibrary()
    # No tool calls → latency_seconds * 1000.0 = 1500.0 ms, under 2000 → passes.
    lib.latency_should_be_below(_budget_result(latency_seconds=1.5, tool_calls=[]), 2000.0)


def test_latency_should_be_below_multi_trial_union_mean_like_getter() -> None:
    lib = AssertionsLibrary()
    runs = [
        _budget_result(tool_calls=[_lat_trace(1000.0), _lat_trace(2000.0, sequence_index=1)]),
        _budget_result(tool_calls=[_lat_trace(3000.0)]),
    ]
    # union-then-mean = mean(1000, 2000, 3000) = 2000.0 → NOT below 2000, below 2500.
    with pytest.raises(AssertionError) as exc:
        lib.latency_should_be_below(runs, 2000.0)
    assert "2000" in str(exc.value)
    lib.latency_should_be_below(runs, 2500.0)


# ---- Latency P95 Should Be Below ---- #


def test_latency_p95_should_be_below_under_passes() -> None:
    lib = AssertionsLibrary()
    # Single tool call → P95 is that latency (AC-6.1.8).
    lib.latency_p95_should_be_below(_budget_result(tool_calls=[_lat_trace(1900.0)]), 2000.0)


def test_latency_p95_should_be_below_over_fails_with_actual_threshold_unit() -> None:
    lib = AssertionsLibrary()
    with pytest.raises(AssertionError) as exc:
        lib.latency_p95_should_be_below(_budget_result(tool_calls=[_lat_trace(3100.0)]), 2000.0)
    msg = str(exc.value)
    assert "3100" in msg
    assert "2000" in msg
    assert "ms" in msg


def test_latency_p95_should_be_below_multi_trial_matches_getter() -> None:
    from AgentEval.metrics import _internal as m_internal

    lib = AssertionsLibrary()
    runs = [
        _budget_result(tool_calls=[_lat_trace(float(x), sequence_index=x) for x in range(100)]),
    ]
    observed_p95 = m_internal._aggregate_latency_p95(runs)
    # A threshold just above the getter's P95 must pass; just below must fail.
    lib.latency_p95_should_be_below(runs, observed_p95 + 1.0)
    with pytest.raises(AssertionError):
        lib.latency_p95_should_be_below(runs, observed_p95)


# ---- Token Usage Should Be Below ---- #


def test_token_usage_should_be_below_under_passes() -> None:
    lib = AssertionsLibrary()
    lib.token_usage_should_be_below(_budget_result(usage=Usage(input_tokens=400, output_tokens=100)), 1000)


def test_token_usage_should_be_below_over_fails_with_actual_threshold_unit() -> None:
    lib = AssertionsLibrary()
    runs = [
        _budget_result(usage=Usage(input_tokens=500, output_tokens=100)),
        _budget_result(usage=Usage(input_tokens=500, output_tokens=100)),
    ]  # total = 1200
    with pytest.raises(AssertionError) as exc:
        lib.token_usage_should_be_below(runs, 1000)
    msg = str(exc.value)
    assert "1200" in msg
    assert "1000" in msg
    assert "tokens" in msg


def test_token_usage_should_be_below_equal_fails_strict_less_than() -> None:
    lib = AssertionsLibrary()
    with pytest.raises(AssertionError):
        lib.token_usage_should_be_below(_budget_result(usage=Usage(input_tokens=600, output_tokens=400)), 1000)


def test_token_usage_should_be_below_cached_not_double_counted() -> None:
    lib = AssertionsLibrary()
    # input=500 (of which cached=300), output=100 → total = 600, NOT 900. Passes under 700.
    usage = Usage(input_tokens=500, output_tokens=100, cached_input_tokens=300)
    lib.token_usage_should_be_below(_budget_result(usage=usage), 700)
    # Confirms the sub-field was not added: 600 < 700 passes; if it were 900 it would fail.
    with pytest.raises(AssertionError):
        lib.token_usage_should_be_below(_budget_result(usage=usage), 600)


def test_token_usage_should_be_below_reasoning_not_double_counted() -> None:
    lib = AssertionsLibrary()
    # reasoning_output_tokens is reported inside output_tokens — must not be added again.
    usage = Usage(input_tokens=100, output_tokens=200, reasoning_output_tokens=150)
    # total = 300 (not 450). Passes under 400.
    lib.token_usage_should_be_below(_budget_result(usage=usage), 400)


# ---- Shared validation + conventions ---- #


@pytest.mark.parametrize(
    "call",
    [
        lambda lib: lib.cost_should_be_below([], 0.10),
        lambda lib: lib.latency_should_be_below([], 2000.0),
        lambda lib: lib.latency_p95_should_be_below([], 2000.0),
        lambda lib: lib.token_usage_should_be_below([], 1000),
    ],
)
def test_budget_empty_list_raises_value_error(call) -> None:
    lib = AssertionsLibrary()
    with pytest.raises(ValueError, match=r"empty list"):
        call(lib)


@pytest.mark.parametrize("bad_threshold", [0, -0.5, float("nan"), float("inf"), -float("inf")])
def test_cost_bad_threshold_raises_value_error_before_dispatch(bad_threshold) -> None:
    lib = AssertionsLibrary()
    # Even with an over-budget observed value, the threshold gate fires first
    # → ValueError, not AssertionError (caller-typo gate precedes dispatch).
    with pytest.raises(ValueError, match=r"threshold must be"):
        lib.cost_should_be_below(_budget_result(cost_usd=999.0), bad_threshold)


@pytest.mark.parametrize(
    "call",
    [
        lambda lib, t: lib.latency_should_be_below(_budget_result(tool_calls=[_lat_trace(5000.0)]), t),
        lambda lib, t: lib.latency_p95_should_be_below(_budget_result(tool_calls=[_lat_trace(5000.0)]), t),
        lambda lib, t: lib.token_usage_should_be_below(_budget_result(usage=Usage(input_tokens=9, output_tokens=9)), t),
    ],
)
@pytest.mark.parametrize("bad_threshold", [0, -1, float("nan")])
def test_budget_bad_threshold_raises_value_error_before_dispatch(call, bad_threshold) -> None:
    lib = AssertionsLibrary()
    with pytest.raises(ValueError, match=r"threshold must be"):
        call(lib, bad_threshold)


def test_cost_external_mixed_does_not_raise_incomplete_trace() -> None:
    # Provider-reported scalar — NOT mcp_coverage-gated (design D5). external_mixed
    # + allow_external_mcp_blind=False must NOT raise IncompleteTraceError.
    lib = AssertionsLibrary(allow_external_mcp_blind=False)
    result = _budget_result(cost_usd=0.01, mcp_coverage="external_mixed")
    lib.cost_should_be_below(result, 0.10)  # no raise
    with pytest.raises(AssertionError):  # sanity: over-budget still fails via assertion, not coverage
        lib.cost_should_be_below(_budget_result(cost_usd=0.5, mcp_coverage="external_mixed"), 0.10)


def _capture_logger_info(monkeypatch) -> list[str]:
    import AgentEval._assertions.library as lib_mod

    captured: list[str] = []
    monkeypatch.setattr(lib_mod.logger, "info", lambda msg, *a, **k: captured.append(msg))
    return captured


def test_budget_pass_logs_evidence_line(monkeypatch) -> None:
    captured = _capture_logger_info(monkeypatch)
    lib = AssertionsLibrary()
    lib.cost_should_be_below(_budget_result(cost_usd=0.05), 0.10)
    assert len(captured) == 1
    line = captured[0]
    assert "0.05" in line  # observed
    assert "0.1" in line  # threshold
    assert "USD" in line  # unit
    assert "runs=1" in line  # aggregated-run count


def test_budget_pass_logs_run_count_for_multi_trial(monkeypatch) -> None:
    captured = _capture_logger_info(monkeypatch)
    lib = AssertionsLibrary()
    lib.token_usage_should_be_below(
        [_budget_result(usage=Usage(input_tokens=10, output_tokens=10)) for _ in range(3)],
        1000,
    )
    assert len(captured) == 1
    assert "runs=3" in captured[0]
    assert "tokens" in captured[0]
