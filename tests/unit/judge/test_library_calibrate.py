# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for `JudgeLibrary.calibrate` (Story 12.2)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from AgentEval.judge.library import JudgeLibrary
from AgentEval.judge.types import CalibrationReport
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

FIXTURE_RUBRIC = Path(__file__).resolve().parent.parent.parent / "fixtures" / "rubrics" / "skill-quality.md"
FIXTURE_CALIBRATION = (
    Path(__file__).resolve().parent.parent.parent / "fixtures" / "calibration" / "skill-quality-calibration.yaml"
)


def _make_judge_response(numeric_score: float = 8.0, cost_usd: float = 0.001) -> AgentRunResult:
    payload = {
        "numeric_score": numeric_score,
        "reasoning": "OK",
        "criteria_breakdown": {"correctness": numeric_score},
    }
    return AgentRunResult(
        response_text=json.dumps(payload),
        tool_calls=[],
        usage=Usage(input_tokens=100, output_tokens=50),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=cost_usd,
        latency_seconds=0.5,
        trace_id="calibration-trace",
    )


def _patch_adapter_for_calibrate(monkeypatch: pytest.MonkeyPatch, response_per_call: list[AgentRunResult]) -> MagicMock:
    """Per-call configurable fake adapter using `feedback_monkeypatch_decorator_chain_walk`.

    The conventions test suite re-loads `library.py` via
    `load_module_from_path` and overwrites `sys.modules`. Naive
    `monkeypatch.setattr` patches land on the wrong module dict. Walking
    `JudgeLibrary.calibrate.__wrapped__` chain + `monkeypatch.setitem(
    innermost.__globals__, "get_adapter", ...)` targets the real lookup
    namespace regardless of `sys.modules` state.
    """
    spy = MagicMock()
    call_index = {"i": 0}

    class _SequencedFakeAdapter:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def run(self, *args: Any, **kwargs: Any) -> AgentRunResult:
            spy(*args, **kwargs)
            result = response_per_call[call_index["i"] % len(response_per_call)]
            call_index["i"] += 1
            return result

    innermost = JudgeLibrary.calibrate
    while hasattr(innermost, "__wrapped__"):
        innermost = innermost.__wrapped__

    monkeypatch.setitem(innermost.__globals__, "get_adapter", lambda name: _SequencedFakeAdapter)
    return spy


# --------------------------------------------------------------------------- #
# Happy path                                                                    #
# --------------------------------------------------------------------------- #


def test_calibrate_happy_path_returns_calibration_report(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-12.2.1 + AC-12.2.2: happy path returns CalibrationReport with kappa."""
    # 5 calibration rows; configure adapter to return scores matching human labels
    # (high agreement → kappa close to 1).
    responses = [
        _make_judge_response(numeric_score=9.0),  # row 0 human=9.0 → both pass
        _make_judge_response(numeric_score=8.0),  # row 1 human=8.5 → both pass
        _make_judge_response(numeric_score=2.5),  # row 2 human=2.0 → both fail
        _make_judge_response(numeric_score=2.0),  # row 3 human=1.5 → both fail
        _make_judge_response(numeric_score=7.0),  # row 4 human=7.0 → both pass (at threshold)
    ]
    spy = _patch_adapter_for_calibrate(monkeypatch, responses)

    judge_lib = JudgeLibrary()
    report = judge_lib.calibrate(
        rubric=FIXTURE_RUBRIC,
        calibration_set=FIXTURE_CALIBRATION,
    )

    assert isinstance(report, CalibrationReport)
    assert report.rows_total == 5
    assert report.rows_processed == 5
    assert spy.call_count == 5
    # All 5 binary judge labels match all 5 binary human labels at threshold 7.0:
    # judge bin = [1,1,0,0,1], human bin = [1,1,0,0,1] → perfect agreement.
    assert report.cohen_kappa == pytest.approx(1.0)
    assert report.passes_hard_fail is True
    # AC-12.2.8 #22 — recommended_threshold is computed (any value at perfect
    # agreement is acceptable; just assert it's reachable in threshold_tuning).
    assert report.recommended_threshold in report.threshold_tuning


def test_calibrate_zero_variance_judge_scores_passes_hard_fail_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All judge scores equal → kappa = nan + passes_hard_fail = False.

    Distinct from a defined-kappa-below-0.7 case (see next test). This is
    the zero-variance edge case per Story 12.2 D-7.
    """
    responses = [_make_judge_response(numeric_score=8.0) for _ in range(5)]
    _patch_adapter_for_calibrate(monkeypatch, responses)

    judge_lib = JudgeLibrary()
    report = judge_lib.calibrate(
        rubric=FIXTURE_RUBRIC,
        calibration_set=FIXTURE_CALIBRATION,
    )
    # judge bin = [1,1,1,1,1] (all pass), human bin = [1,1,0,0,1] → zero-variance judge
    assert math.isnan(report.cohen_kappa)
    assert report.kappa_undefined_reason == "judge_score_zero_variance"
    assert report.passes_hard_fail is False


def test_calibrate_kappa_between_zero_and_threshold_passes_hard_fail_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defined kappa in (0, 0.7) → passes_hard_fail = False (NOT nan path).

    Uses calibration fixture with human labels [9.0, 8.5, 2.0, 1.5, 7.0]
    (binary at 7.0: [1, 1, 0, 0, 1]). Judge scores [9.0, 8.0, 3.0, 8.0, 5.0]
    (binary: [1, 1, 0, 1, 0]). Observed agreement = 3/5 = 0.6; expected
    agreement = 0.6*0.6 + 0.4*0.4 = 0.52; kappa = (0.6 - 0.52)/(1 - 0.52)
    ≈ 0.167 — defined intermediate kappa below the 0.7 hard-fail threshold.
    """
    responses = [
        _make_judge_response(numeric_score=9.0),
        _make_judge_response(numeric_score=8.0),
        _make_judge_response(numeric_score=3.0),
        _make_judge_response(numeric_score=8.0),
        _make_judge_response(numeric_score=5.0),
    ]
    _patch_adapter_for_calibrate(monkeypatch, responses)

    judge_lib = JudgeLibrary()
    report = judge_lib.calibrate(
        rubric=FIXTURE_RUBRIC,
        calibration_set=FIXTURE_CALIBRATION,
    )
    assert not math.isnan(report.cohen_kappa)
    assert 0.0 < report.cohen_kappa < 0.7
    assert report.kappa_undefined_reason is None
    assert report.passes_hard_fail is False


# --------------------------------------------------------------------------- #
# AC-12.2.8 #21: empirical @guarded_fanout budget breach probe                  #
# (UPSTREAM Story 12.1 Opus MED-3 lesson)                                       #
# --------------------------------------------------------------------------- #


def test_calibrate_raises_cost_exceeded_when_budget_breached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empirical guardrail probe: `@guarded_fanout()` on `calibrate` fires
    `CostExceededError` when the Layer-2 cost meter reports cost > budget.

    Synthesizes a breach via `__agenteval_test_budget__=(0.001, None)` +
    monkeypatched `_current_cost_usd_for_run` returning `1.0`. Per UPSTREAM
    Story 12.1 Opus MED-3 lesson — attribute-storage tests are
    insufficient; empirical breach probe is required.
    """
    from AgentEval._kernel import guardrails
    from AgentEval.errors import CostExceededError

    monkeypatch.setattr(guardrails, "_current_cost_usd_for_run", lambda: 1.0)
    _patch_adapter_for_calibrate(monkeypatch, [_make_judge_response()])
    judge_lib = JudgeLibrary()

    with pytest.raises(CostExceededError):
        judge_lib.calibrate(
            rubric=FIXTURE_RUBRIC,
            calibration_set=FIXTURE_CALIBRATION,
            __agenteval_test_budget__=(0.001, None),
        )


# --------------------------------------------------------------------------- #
# AC-12.2.8 #23: systematic bias diagnostic                                     #
# --------------------------------------------------------------------------- #


def test_calibrate_surfaces_systematic_bias_when_judge_scores_high(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Judge consistently scoring > 1.0 above humans → bias diagnostic bullet."""
    # Override every judge call to return 9.5; human labels are 9.0, 8.5, 2.0, 1.5, 7.0
    # → mean judge = 9.5; mean human = 5.6; delta = +3.9 → bullet should fire.
    responses = [_make_judge_response(numeric_score=9.5) for _ in range(5)]
    _patch_adapter_for_calibrate(monkeypatch, responses)

    judge_lib = JudgeLibrary()
    report = judge_lib.calibrate(
        rubric=FIXTURE_RUBRIC,
        calibration_set=FIXTURE_CALIBRATION,
    )
    assert any("above" in bullet for bullet in report.systematic_bias_diagnostics)


# --------------------------------------------------------------------------- #
# Regression: calibration threads the row's `prompt` (context/question) into    #
# the judge prompt (add-judge-criteria-shortcuts codex MED)                      #
# --------------------------------------------------------------------------- #


def test_calibrate_threads_row_prompt_into_judge_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calibrating the faithfulness preset MUST include each row's `prompt`.

    Codex probe observed `has_context_placeholder_in_prompt False`: the judge
    scored "supported by supplied context" with no supplied context. The row's
    `prompt` (where the faithfulness template instructs users to put the
    grounding context) must now render as a distinct `# Input` section.
    """
    responses = [_make_judge_response() for _ in range(5)]
    spy = _patch_adapter_for_calibrate(monkeypatch, responses)

    judge_lib = JudgeLibrary()
    preset_rubric = judge_lib.get_preset_rubric(name="faithfulness")
    report = judge_lib.calibrate(rubric=preset_rubric, calibration_set=FIXTURE_CALIBRATION)
    assert isinstance(report, CalibrationReport)

    # Every calibration row's prompt must reach the judge under `# Input`.
    row_prompts = [
        "Write a Python function that adds two numbers.",
        "Find the largest file in /tmp via the filesystem tool.",
        "Compute the determinant of a 3x3 matrix.",
        "List the top 3 most recent commits in this repo.",
        "Summarize the README in 2 sentences.",
    ]
    assert spy.call_count == len(row_prompts)
    for call, expected_prompt in zip(spy.call_args_list, row_prompts, strict=True):
        composed = call.kwargs.get("prompt") or call.args[0]
        assert "# Input" in composed, "calibration judge prompt is missing the `# Input` context section"
        assert expected_prompt in composed, f"row prompt/context not threaded into judge prompt: {expected_prompt!r}"


def test_calibrate_blank_prompt_adds_no_input_section(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A whitespace-only row prompt must NOT add an empty `# Input` section."""
    calib = tmp_path / "blank-prompt.yaml"
    calib.write_text(
        "rows:\n"
        '  - prompt: "   "\n'
        '    response: "some response text"\n'
        "    human_label: 9.0\n"
        '  - prompt: "a real question"\n'
        '    response: "another response"\n'
        "    human_label: 2.0\n",
        encoding="utf-8",
    )
    spy = _patch_adapter_for_calibrate(monkeypatch, [_make_judge_response(), _make_judge_response()])

    judge_lib = JudgeLibrary()
    preset_rubric = judge_lib.get_preset_rubric(name="faithfulness")
    judge_lib.calibrate(rubric=preset_rubric, calibration_set=calib)

    first_prompt = spy.call_args_list[0].kwargs.get("prompt") or spy.call_args_list[0].args[0]
    assert "# Input" not in first_prompt  # blank prompt -> no empty section
    second_prompt = spy.call_args_list[1].kwargs.get("prompt") or spy.call_args_list[1].args[0]
    assert "# Input" in second_prompt
    assert "a real question" in second_prompt


# --------------------------------------------------------------------------- #
# AC-12.2.7: composition via `_SUB_LIBRARIES`                                   #
# --------------------------------------------------------------------------- #


def test_agenteval_composition_includes_judge_calibrate() -> None:
    """`Judge.Calibrate Rubric` MUST surface in `AgentEval.get_keyword_names()`."""
    from AgentEval import AgentEval

    agent_eval = AgentEval()
    assert "Judge.Calibrate Rubric" in agent_eval.get_keyword_names()
