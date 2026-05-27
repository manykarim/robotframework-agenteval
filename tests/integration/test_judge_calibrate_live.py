# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Env-gated live integration test for `Judge.Calibrate` (Story 12.2 AC-12.2.8).

Skipped unless ``AGENTEVAL_INTEGRATION_TESTS=1`` AND ``ANTHROPIC_API_KEY``
(or another live provider key) is set. CI does NOT run this; manual
validation only. This is the calibration sibling to `test_judge_live.py`
shipped in Story 12.1.

A full calibration run against 5 rows at `anthropic/claude-sonnet-4-6` is
typically ~$0.02-0.05 USD per run (judge invokes once per row + composes
the rubric system-prompt on each); set `max_cost_usd` accordingly.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import pytest

from AgentEval.judge.library import JudgeLibrary
from AgentEval.judge.types import CalibrationReport

FIXTURE_RUBRIC = Path(__file__).resolve().parent.parent / "fixtures" / "rubrics" / "skill-quality.md"
FIXTURE_CALIBRATION = (
    Path(__file__).resolve().parent.parent / "fixtures" / "calibration" / "skill-quality-calibration.yaml"
)


@pytest.mark.skipif(
    os.environ.get("AGENTEVAL_INTEGRATION_TESTS") != "1",
    reason="Live calibrate integration test gated behind AGENTEVAL_INTEGRATION_TESTS=1",
)
@pytest.mark.skipif(
    os.environ.get("ANTHROPIC_API_KEY") is None,
    reason="ANTHROPIC_API_KEY not set",
)
def test_judge_calibrate_live_against_anthropic_claude_sonnet() -> None:
    """Drives `Judge.Calibrate` against `anthropic/claude-sonnet-4-6` with the
    canonical Phase-1 rubric + 5-row calibration fixture. Asserts a valid
    `CalibrationReport` returns + Cohen's kappa is computable + cost is
    non-zero.

    Does NOT assert `passes_hard_fail=True` — that depends on the actual
    judge behavior against this small fixture and would make the test
    flaky against legitimate model drift.
    """
    judge_lib = JudgeLibrary(max_cost_usd=0.50, max_runtime_seconds=120)
    report = judge_lib.calibrate(
        rubric=FIXTURE_RUBRIC,
        calibration_set=FIXTURE_CALIBRATION,
        judge_adapter="generic",
        judge_model="anthropic/claude-sonnet-4-6",
        temperature=0.0,
        seed=42,
    )

    assert isinstance(report, CalibrationReport)
    assert report.rows_total == 5
    assert report.rows_processed == 5
    assert len(report.judge_scores) == 5
    assert len(report.human_labels) == 5

    # Either a defined kappa OR a documented undefined reason — both are
    # acceptable outcomes for a 5-row calibration. What we won't accept:
    # silent nan with no reason explaining why.
    if math.isnan(report.cohen_kappa):
        assert report.kappa_undefined_reason in (
            "human_label_zero_variance",
            "judge_score_zero_variance",
            "expected_agreement_unity",
        )
    else:
        assert -1.0 <= report.cohen_kappa <= 1.0
        # `passes_hard_fail` consistent with kappa per architecture L199
        assert report.passes_hard_fail == (report.cohen_kappa >= 0.7)

    assert report.total_cost_usd > 0.0, "Expected non-zero cost from live calibrate"
    assert report.recommended_threshold in report.threshold_tuning, (
        "recommended_threshold MUST be a key in threshold_tuning per CalibrationReport contract"
    )
