# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for `judge/library.py` (Story 12.1)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from AgentEval._kernel.tier import get_keyword_tier
from AgentEval.errors import JudgeOutputParseError
from AgentEval.judge.library import JudgeLibrary
from AgentEval.judge.types import JudgeRubric, JudgeScore
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

FIXTURE_RUBRIC = Path(__file__).resolve().parent.parent.parent / "fixtures" / "rubrics" / "skill-quality.md"


def _make_agent_run_result(response_text: str = "the agent's output") -> AgentRunResult:
    """Build a minimal `AgentRunResult` for testing."""
    return AgentRunResult(
        response_text=response_text,
        tool_calls=[],
        usage=Usage(input_tokens=10, output_tokens=20),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.5,
        trace_id="test-trace",
    )


def _make_judge_response(
    numeric_score: float = 8.0,
    reasoning: str = "The agent's response was solid.",
    criteria_breakdown: dict[str, float] | None = None,
    cost_usd: float = 0.0042,
) -> AgentRunResult:
    """Build an `AgentRunResult` whose `response_text` is a valid JudgeScore JSON."""
    if criteria_breakdown is None:
        criteria_breakdown = {
            "correctness": 8.0,
            "completeness": 8.0,
            "tool-use-appropriateness": 8.0,
            "response-clarity": 8.0,
        }
    payload = {
        "numeric_score": numeric_score,
        "reasoning": reasoning,
        "criteria_breakdown": criteria_breakdown,
    }
    return AgentRunResult(
        response_text=json.dumps(payload),
        tool_calls=[],
        usage=Usage(input_tokens=200, output_tokens=80),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=cost_usd,
        latency_seconds=1.0,
        trace_id="judge-trace",
    )


def _patch_adapter(monkeypatch: pytest.MonkeyPatch, judge_response: AgentRunResult) -> MagicMock:
    """Monkeypatch `get_adapter` in the namespace where `JudgeLibrary.get_score`
    actually looks it up, returning a fake adapter whose `run()` yields
    `judge_response`. Returns the spy mock.

    Why patch `get_score.__globals__` rather than `sys.modules["AgentEval.judge.library"]`:
    the conventions test suite (`tests/unit/conventions/_walk.py:load_module_from_path`)
    re-loads `library.py` via `importlib.util.spec_from_file_location` and
    overwrites `sys.modules["AgentEval.judge.library"]` with a freshly-exec'd
    module. After that, `import AgentEval.judge.library` returns the new
    module, but the already-imported `JudgeLibrary` class is still bound to
    the OLD module — and `JudgeLibrary.get_score` performs global lookups
    in the OLD module's `__dict__` via its captured `__globals__`. Patching
    the new module via `monkeypatch.setattr(new_module, "get_adapter", ...)`
    has no effect on the running function. Patching `get_score.__globals__`
    directly via `monkeypatch.setitem` targets the real lookup namespace.
    """
    fake_run = MagicMock(return_value=judge_response)

    class _FakeAdapter:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def run(self, *args: Any, **kwargs: Any) -> AgentRunResult:
            return fake_run(*args, **kwargs)

    # Walk the @tier + @guarded_fanout decorator chain to reach the innermost
    # function — its `__globals__` IS `library.py`'s module dict, which is
    # where the runtime `get_adapter` lookup happens.
    #
    # Use the module-level `JudgeLibrary` (captured at collection time) instead
    # of a fresh `from AgentEval.judge.library import JudgeLibrary` — the
    # conventions test suite re-loads `library.py` via
    # `importlib.util.spec_from_file_location` and overwrites the
    # `sys.modules` entry, so a fresh import returns a DIFFERENT class object
    # whose innermost `__globals__` points to a DIFFERENT module dict than the
    # one tests actually instantiate against.
    innermost = JudgeLibrary.get_score
    while hasattr(innermost, "__wrapped__"):
        innermost = innermost.__wrapped__

    monkeypatch.setitem(
        innermost.__globals__,
        "get_adapter",
        lambda name: _FakeAdapter,
    )
    return fake_run


# --------------------------------------------------------------------------- #
# Happy-path Judge.Get Score                                                    #
# --------------------------------------------------------------------------- #


def test_get_score_returns_judge_score_with_valid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: rubric loads, adapter returns valid JSON, JudgeScore returns."""
    spy = _patch_adapter(monkeypatch, _make_judge_response(numeric_score=8.5))
    judge_lib = JudgeLibrary()
    result = _make_agent_run_result()

    score = judge_lib.get_score(result=result, rubric=FIXTURE_RUBRIC)

    assert isinstance(score, JudgeScore)
    assert score.numeric_score == 8.5
    assert score.pass_threshold_met is True  # 8.5 >= 7.0 (fixture threshold)
    assert "correctness" in score.criteria_breakdown
    assert spy.call_count == 1


def test_get_score_accepts_pre_loaded_judge_rubric(monkeypatch: pytest.MonkeyPatch) -> None:
    """`rubric` can be a `JudgeRubric` instance directly (not just a path)."""
    _patch_adapter(monkeypatch, _make_judge_response())
    judge_lib = JudgeLibrary()
    rubric = JudgeRubric(
        criteria=(("correctness", "did it work?"),),
        threshold=5.0,
        raw_text="# Rubric\n\n## Criteria\n- correctness: did it work?\n\n## Threshold\nPass if numeric_score >= 5.0",
    )
    score = judge_lib.get_score(result=_make_agent_run_result(), rubric=rubric)
    assert isinstance(score, JudgeScore)


def test_get_score_computes_pass_threshold_met_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    """`pass_threshold_met = numeric_score >= rubric.threshold`."""
    _patch_adapter(monkeypatch, _make_judge_response(numeric_score=6.9))
    judge_lib = JudgeLibrary()
    score = judge_lib.get_score(result=_make_agent_run_result(), rubric=FIXTURE_RUBRIC)
    # 6.9 < 7.0 (fixture threshold) → False
    assert score.pass_threshold_met is False


def test_get_score_forwards_judge_model_to_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """`judge_model` kwarg MUST be forwarded to adapter.run(model=...)."""
    spy = _patch_adapter(monkeypatch, _make_judge_response())
    judge_lib = JudgeLibrary()
    judge_lib.get_score(
        result=_make_agent_run_result(),
        rubric=FIXTURE_RUBRIC,
        judge_model="anthropic/claude-sonnet-4-6",
    )
    call_kwargs = spy.call_args.kwargs
    assert call_kwargs.get("model") == "anthropic/claude-sonnet-4-6"


def test_get_score_forwards_adapter_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Additional kwargs (e.g. seed, temperature) MUST be forwarded to adapter.run()."""
    spy = _patch_adapter(monkeypatch, _make_judge_response())
    judge_lib = JudgeLibrary()
    judge_lib.get_score(
        result=_make_agent_run_result(),
        rubric=FIXTURE_RUBRIC,
        seed=42,
        temperature=0.0,
    )
    call_kwargs = spy.call_args.kwargs
    assert call_kwargs.get("seed") == 42
    assert call_kwargs.get("temperature") == 0.0


def test_get_score_includes_tool_calls_in_judge_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tool-call trajectory MUST be included in the prompt so behavioral
    criteria can be scored."""
    spy = _patch_adapter(monkeypatch, _make_judge_response())
    judge_lib = JudgeLibrary()
    # Build an AgentRunResult with 2 tool calls.
    from AgentEval.types import ToolCallTrace

    result = AgentRunResult(
        response_text="agent output",
        tool_calls=[
            ToolCallTrace(
                name="search_web",
                args={"query": "x"},
                result=None,
                error=None,
                latency_ms=0.0,
                source="adapter",
                gen_ai_tool_call_id="c1",
                sequence_index=0,
            ),
            ToolCallTrace(
                name="open_file",
                args={"path": "/tmp"},
                result=None,
                error=None,
                latency_ms=0.0,
                source="adapter",
                gen_ai_tool_call_id="c2",
                sequence_index=1,
            ),
        ],
        usage=Usage(input_tokens=0, output_tokens=0),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.0,
        trace_id="x",
    )
    judge_lib.get_score(result=result, rubric=FIXTURE_RUBRIC)
    prompt = spy.call_args.kwargs.get("prompt") or spy.call_args.args[0]
    assert "search_web" in prompt
    assert "open_file" in prompt


# --------------------------------------------------------------------------- #
# Error paths — JudgeOutputParseError + ValueError                              #
# --------------------------------------------------------------------------- #


def test_get_score_raises_on_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adapter response is not valid JSON → JudgeOutputParseError."""
    bad_response = AgentRunResult(
        response_text="this is not JSON, just plain text",
        tool_calls=[],
        usage=Usage(input_tokens=0, output_tokens=0),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.0,
        trace_id="x",
    )
    _patch_adapter(monkeypatch, bad_response)
    judge_lib = JudgeLibrary()
    with pytest.raises(JudgeOutputParseError) as exc_info:
        judge_lib.get_score(result=_make_agent_run_result(), rubric=FIXTURE_RUBRIC)
    assert "not valid JSON" in str(exc_info.value)


def test_get_score_raises_on_missing_numeric_score_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM returns JSON missing `numeric_score` → JudgeOutputParseError."""
    bad_response = AgentRunResult(
        response_text=json.dumps({"reasoning": "no score here"}),
        tool_calls=[],
        usage=Usage(input_tokens=0, output_tokens=0),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.0,
        trace_id="x",
    )
    _patch_adapter(monkeypatch, bad_response)
    judge_lib = JudgeLibrary()
    with pytest.raises(JudgeOutputParseError) as exc_info:
        judge_lib.get_score(result=_make_agent_run_result(), rubric=FIXTURE_RUBRIC)
    assert "missing required field 'numeric_score'" in str(exc_info.value)


def test_get_score_raises_on_missing_reasoning_field(monkeypatch: pytest.MonkeyPatch) -> None:
    bad_response = AgentRunResult(
        response_text=json.dumps({"numeric_score": 8.0}),
        tool_calls=[],
        usage=Usage(input_tokens=0, output_tokens=0),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.0,
        trace_id="x",
    )
    _patch_adapter(monkeypatch, bad_response)
    judge_lib = JudgeLibrary()
    with pytest.raises(JudgeOutputParseError) as exc_info:
        judge_lib.get_score(result=_make_agent_run_result(), rubric=FIXTURE_RUBRIC)
    assert "missing required field 'reasoning'" in str(exc_info.value)


def test_get_score_raises_on_non_numeric_numeric_score(monkeypatch: pytest.MonkeyPatch) -> None:
    bad_response = AgentRunResult(
        response_text=json.dumps({"numeric_score": "high", "reasoning": "x"}),
        tool_calls=[],
        usage=Usage(input_tokens=0, output_tokens=0),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.0,
        trace_id="x",
    )
    _patch_adapter(monkeypatch, bad_response)
    judge_lib = JudgeLibrary()
    with pytest.raises(JudgeOutputParseError, match="not numeric"):
        judge_lib.get_score(result=_make_agent_run_result(), rubric=FIXTURE_RUBRIC)


def test_get_score_raises_on_numeric_score_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM returns `numeric_score=11.0` (out of [0.0, 10.0]) → JudgeOutputParseError.

    Re-wrap of `JudgeScore.__post_init__`'s `ValueError` into the documented
    `JudgeOutputParseError` honours the `error-class-hierarchy.md` L25
    boundary contract — untrusted LLM runtime data crossing a public
    keyword boundary surfaces as an `AgentEvalError` leaf so consumers can
    `except JudgeOutputParseError` per the keyword docstring.
    """
    bad_response = _make_judge_response(numeric_score=11.0)
    _patch_adapter(monkeypatch, bad_response)
    judge_lib = JudgeLibrary()
    with pytest.raises(JudgeOutputParseError, match=re.escape("out of range [0.0, 10.0]")):
        judge_lib.get_score(result=_make_agent_run_result(), rubric=FIXTURE_RUBRIC)


def test_get_score_raises_on_numeric_score_boolean(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM returns JSON `numeric_score: false` → JudgeOutputParseError.

    `bool` is an `int` subclass in Python, so `float(False) == 0.0` would
    silently coerce a JSON boolean into a 0.0 score. Explicit boolean
    type-guard surfaces the malformed LLM output instead.
    Per `feedback_nullish_input_fuzz_checklist`.
    """
    bad_response = AgentRunResult(
        response_text=json.dumps({"numeric_score": False, "reasoning": "x"}),
        tool_calls=[],
        usage=Usage(input_tokens=0, output_tokens=0),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.0,
        trace_id="x",
    )
    _patch_adapter(monkeypatch, bad_response)
    judge_lib = JudgeLibrary()
    with pytest.raises(JudgeOutputParseError, match="boolean"):
        judge_lib.get_score(result=_make_agent_run_result(), rubric=FIXTURE_RUBRIC)


def test_get_score_raises_on_non_dict_top_level_json(monkeypatch: pytest.MonkeyPatch) -> None:
    bad_response = AgentRunResult(
        response_text=json.dumps([1, 2, 3]),
        tool_calls=[],
        usage=Usage(input_tokens=0, output_tokens=0),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.0,
        trace_id="x",
    )
    _patch_adapter(monkeypatch, bad_response)
    judge_lib = JudgeLibrary()
    with pytest.raises(JudgeOutputParseError, match="not a JSON object"):
        judge_lib.get_score(result=_make_agent_run_result(), rubric=FIXTURE_RUBRIC)


def test_get_score_raises_on_non_dict_criteria_breakdown(monkeypatch: pytest.MonkeyPatch) -> None:
    bad_response = AgentRunResult(
        response_text=json.dumps({"numeric_score": 8.0, "reasoning": "x", "criteria_breakdown": "not an object"}),
        tool_calls=[],
        usage=Usage(input_tokens=0, output_tokens=0),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.0,
        latency_seconds=0.0,
        trace_id="x",
    )
    _patch_adapter(monkeypatch, bad_response)
    judge_lib = JudgeLibrary()
    with pytest.raises(JudgeOutputParseError, match="not a JSON object"):
        judge_lib.get_score(result=_make_agent_run_result(), rubric=FIXTURE_RUBRIC)


# --------------------------------------------------------------------------- #
# Tier annotation + Decorator wiring                                            #
# --------------------------------------------------------------------------- #


def test_get_score_is_tier_2() -> None:
    """`@tier(2)` annotation MUST be present + introspectable."""
    judge_lib = JudgeLibrary()
    # JudgeLibrary keywords are registered with RF name "Judge.Get Score"
    # but Python-attribute name is "get_score".
    assert get_keyword_tier(judge_lib.get_score) == 2


def test_get_score_carries_robot_name() -> None:
    """RF keyword name MUST be `Judge.Get Score` per AC-12.1.1."""
    judge_lib = JudgeLibrary()
    # The @keyword decorator sets `robot_name` on the underlying function.
    underlying = getattr(judge_lib.get_score, "__func__", judge_lib.get_score)
    robot_name = getattr(underlying, "robot_name", None)
    assert robot_name == "Judge.Get Score"


# --------------------------------------------------------------------------- #
# `_SUB_LIBRARIES` integration (AC-12.1.5)                                       #
# --------------------------------------------------------------------------- #


def test_judge_library_appears_in_sub_libraries_tuple() -> None:
    """AC-12.1.5: JudgeLibrary MUST be registered in `_SUB_LIBRARIES`."""
    from AgentEval import _SUB_LIBRARIES

    judge_entry = ("AgentEval.judge.library", "JudgeLibrary")
    assert judge_entry in _SUB_LIBRARIES


def test_agenteval_composition_includes_judge_get_score(monkeypatch: pytest.MonkeyPatch) -> None:
    """Top-level `AgentEval` Library composition MUST expose `Judge.Get Score`
    via the DynamicCore keyword surface."""
    from AgentEval import AgentEval

    agent_eval = AgentEval()
    # The DynamicCore composition picks up every @keyword across composed
    # libraries. We verify the keyword name is registered.
    keyword_names = agent_eval.get_keyword_names()
    assert "Judge.Get Score" in keyword_names


# --------------------------------------------------------------------------- #
# Host-instance budget plumbing (AC-12.1.5)                                     #
# --------------------------------------------------------------------------- #


def test_judge_library_accepts_budgets() -> None:
    """AC-12.1.5: JudgeLibrary `__init__` accepts `max_cost_usd` + `max_runtime_seconds`
    (forwarded by `AgentEval._build_components`)."""
    judge_lib = JudgeLibrary(max_cost_usd=5.0, max_runtime_seconds=30.0)
    assert judge_lib._max_cost_usd == 5.0
    assert judge_lib._max_runtime_seconds == 30.0


def test_get_score_raises_cost_exceeded_when_budget_breached(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-12.1.6 empirical guardrail probe: `@guarded_fanout()` enforcement on
    `Judge.Get Score` actually fires `CostExceededError` when the Layer-2 cost
    meter observes cumulative cost > budget.

    Synthesizes a breach by (a) injecting a `__agenteval_test_budget__=(0.001, None)`
    sentinel kwarg for a near-zero cost budget + (b) monkeypatching
    `guardrails._current_cost_usd_for_run` to return a value above the budget.
    Confirms the decorator order + budget plumbing is wired correctly — a
    regression that no-ops the guard would fail this probe.

    Per Story 12.1 Tier-2 Opus MED-3: attribute-storage tests are insufficient
    to verify `@guarded_fanout` enforcement; an empirical breach test is required.
    """
    from AgentEval._kernel import guardrails
    from AgentEval.errors import CostExceededError

    # Force the Layer-2 cost meter to report a cost > budget.
    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 1.0)

    _patch_adapter(monkeypatch, _make_judge_response())
    judge_lib = JudgeLibrary()

    with pytest.raises(CostExceededError):
        judge_lib.get_score(
            result=_make_agent_run_result(),
            rubric=FIXTURE_RUBRIC,
            __agenteval_test_budget__=(0.001, None),
        )
