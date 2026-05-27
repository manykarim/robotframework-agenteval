# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for `judge/types.py` (Story 12.1)."""

from __future__ import annotations

import pytest

from AgentEval.judge.types import JudgeRubric, JudgeScore

# --------------------------------------------------------------------------- #
# JudgeScore                                                                    #
# --------------------------------------------------------------------------- #


def test_judge_score_accepts_in_range_numeric_score() -> None:
    score = JudgeScore(
        numeric_score=7.5,
        pass_threshold_met=True,
        reasoning="solid response",
        criteria_breakdown={"correctness": 8.0, "completeness": 7.0},
        cost_usd=0.0042,
    )
    assert score.numeric_score == 7.5
    assert score.criteria_breakdown == {"correctness": 8.0, "completeness": 7.0}


def test_judge_score_rejects_numeric_score_above_10() -> None:
    """`numeric_score=11.0` is outside [0.0, 10.0] — must raise ValueError."""
    with pytest.raises(ValueError, match="must be in \\[0.0, 10.0\\]"):
        JudgeScore(numeric_score=11.0, pass_threshold_met=True, reasoning="x")


def test_judge_score_rejects_numeric_score_below_zero() -> None:
    with pytest.raises(ValueError, match="must be in \\[0.0, 10.0\\]"):
        JudgeScore(numeric_score=-0.1, pass_threshold_met=False, reasoning="x")


def test_judge_score_accepts_boundary_values() -> None:
    """0.0 and 10.0 exactly are in-range."""
    JudgeScore(numeric_score=0.0, pass_threshold_met=False, reasoning="")
    JudgeScore(numeric_score=10.0, pass_threshold_met=True, reasoning="")


def test_judge_score_rejects_negative_cost_usd() -> None:
    with pytest.raises(ValueError, match="cost_usd must be non-negative"):
        JudgeScore(numeric_score=5.0, pass_threshold_met=False, reasoning="x", cost_usd=-0.001)


def test_judge_score_defensive_copy_of_criteria_breakdown() -> None:
    """Story 1b.2 M_R6 pattern: caller mutations don't leak through."""
    breakdown = {"correctness": 8.0, "completeness": 7.0}
    score = JudgeScore(
        numeric_score=7.5,
        pass_threshold_met=True,
        reasoning="x",
        criteria_breakdown=breakdown,
    )
    breakdown["correctness"] = 0.0
    assert score.criteria_breakdown["correctness"] == 8.0


# --------------------------------------------------------------------------- #
# JudgeRubric                                                                   #
# --------------------------------------------------------------------------- #


def test_judge_rubric_accepts_valid_input() -> None:
    rubric = JudgeRubric(
        criteria=(("correctness", "Did the agent produce correct output?"),),
        threshold=7.0,
        raw_text="# Rubric\n\n## Criteria\n- correctness: Did the agent produce correct output?\n\n## Threshold\nPass if numeric_score >= 7.0",
    )
    assert rubric.threshold == 7.0
    assert rubric.criteria[0][0] == "correctness"


def test_judge_rubric_rejects_threshold_above_10() -> None:
    with pytest.raises(ValueError, match="threshold must be in \\[0.0, 10.0\\]"):
        JudgeRubric(criteria=(("x", "y"),), threshold=11.0, raw_text="x")


def test_judge_rubric_rejects_empty_criteria() -> None:
    with pytest.raises(ValueError, match="at least one criterion"):
        JudgeRubric(criteria=(), threshold=7.0, raw_text="x")
