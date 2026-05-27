# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for `judge/calibration.py` + `CalibrationReport` (Story 12.2)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from AgentEval.errors import InvalidCalibrationSetError
from AgentEval.judge.calibration import (
    KAPPA_HARD_FAIL_THRESHOLD,
    CalibrationRow,
    compute_cohen_kappa,
    load_calibration_set,
)
from AgentEval.judge.types import CalibrationReport

FIXTURE_CALIBRATION = (
    Path(__file__).resolve().parent.parent.parent / "fixtures" / "calibration" / "skill-quality-calibration.yaml"
)


# --------------------------------------------------------------------------- #
# KAPPA_HARD_FAIL_THRESHOLD constant (AC-12.2.5)                                #
# --------------------------------------------------------------------------- #


def test_kappa_hard_fail_threshold_is_0_7() -> None:
    """architecture.md L199 — Cohen's κ ≥ 0.7 hard-fail discipline."""
    assert KAPPA_HARD_FAIL_THRESHOLD == 0.7


# --------------------------------------------------------------------------- #
# compute_cohen_kappa (AC-12.2.4)                                              #
# --------------------------------------------------------------------------- #


def test_compute_cohen_kappa_perfect_agreement() -> None:
    """Perfect agreement → kappa = 1.0."""
    kappa, reason = compute_cohen_kappa(
        judge_scores=[9.0, 9.0, 3.0, 3.0, 8.0, 8.0],
        human_labels=[9.0, 9.0, 3.0, 3.0, 8.0, 8.0],
        pass_threshold=7.0,
    )
    assert kappa == pytest.approx(1.0)
    assert reason is None


def test_compute_cohen_kappa_perfect_disagreement() -> None:
    """Systematic disagreement → kappa < 0 (worse than chance)."""
    # All judge passes are human fails and vice versa.
    kappa, reason = compute_cohen_kappa(
        judge_scores=[9.0, 9.0, 3.0, 3.0],
        human_labels=[3.0, 3.0, 9.0, 9.0],
        pass_threshold=7.0,
    )
    assert kappa < 0
    assert reason is None


def test_compute_cohen_kappa_chance_level() -> None:
    """Chance-level agreement → kappa near 0 (AC-12.2.8 #3).

    50/50 split where judge and human pass/fail independently → kappa ≈ 0.
    """
    # judge bins: [1, 1, 0, 0] (2 pass / 2 fail); human bins: [1, 0, 1, 0] (interleaved)
    # → observed agreement = 2/4 = 0.5; expected agreement = 0.5*0.5 + 0.5*0.5 = 0.5
    # → kappa = (0.5 - 0.5) / (1 - 0.5) = 0.0
    kappa, reason = compute_cohen_kappa(
        judge_scores=[9.0, 9.0, 3.0, 3.0],
        human_labels=[9.0, 3.0, 9.0, 3.0],
        pass_threshold=7.0,
    )
    assert abs(kappa) < 0.1
    assert reason is None


def test_compute_cohen_kappa_zero_variance_human_labels() -> None:
    """All human labels equal → kappa undefined → nan."""
    kappa, reason = compute_cohen_kappa(
        judge_scores=[8.0, 5.0, 9.0, 6.0],
        human_labels=[9.0, 9.0, 9.0, 9.0],
        pass_threshold=7.0,
    )
    assert math.isnan(kappa)
    assert reason == "human_label_zero_variance"


def test_compute_cohen_kappa_zero_variance_judge_scores() -> None:
    """All judge scores equal → kappa undefined → nan."""
    kappa, reason = compute_cohen_kappa(
        judge_scores=[8.0, 8.0, 8.0, 8.0],
        human_labels=[9.0, 5.0, 3.0, 7.0],
        pass_threshold=7.0,
    )
    assert math.isnan(kappa)
    assert reason == "judge_score_zero_variance"


def test_compute_cohen_kappa_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length mismatch"):
        compute_cohen_kappa(judge_scores=[1.0, 2.0], human_labels=[3.0], pass_threshold=2.0)


def test_compute_cohen_kappa_empty_sequences_raises() -> None:
    with pytest.raises(ValueError, match="empty sequences"):
        compute_cohen_kappa(judge_scores=[], human_labels=[], pass_threshold=2.0)


# --------------------------------------------------------------------------- #
# load_calibration_set (AC-12.2.3 + AC-12.2.6)                                  #
# --------------------------------------------------------------------------- #


def test_load_calibration_set_canonical_fixture() -> None:
    """The shipped 5-row fixture must parse cleanly."""
    rows = load_calibration_set(FIXTURE_CALIBRATION)
    assert len(rows) == 5
    assert all(isinstance(r, CalibrationRow) for r in rows)
    assert rows[0].human_label == 9.0
    assert rows[3].human_label == 1.5


def test_load_calibration_set_raises_on_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(InvalidCalibrationSetError) as exc_info:
        load_calibration_set(missing)
    assert "not found" in str(exc_info.value)


def test_load_calibration_set_raises_on_wrong_extension(tmp_path: Path) -> None:
    bad_ext = tmp_path / "calib.txt"
    bad_ext.write_text("rows: []")
    with pytest.raises(InvalidCalibrationSetError) as exc_info:
        load_calibration_set(bad_ext)
    assert "must have `.yaml` or `.yml`" in str(exc_info.value)


def test_load_calibration_set_raises_on_non_dict_top_level(tmp_path: Path) -> None:
    yaml_file = tmp_path / "list-top.yaml"
    yaml_file.write_text("- prompt: p\n  response: r\n  human_label: 5.0")
    with pytest.raises(InvalidCalibrationSetError) as exc_info:
        load_calibration_set(yaml_file)
    assert "top-level value must be a mapping" in str(exc_info.value)


def test_load_calibration_set_raises_on_missing_rows_key(tmp_path: Path) -> None:
    yaml_file = tmp_path / "no-rows.yaml"
    yaml_file.write_text("some_other_key: 1")
    with pytest.raises(InvalidCalibrationSetError) as exc_info:
        load_calibration_set(yaml_file)
    assert "missing required `rows:` key" in str(exc_info.value)


def test_load_calibration_set_raises_on_non_list_rows(tmp_path: Path) -> None:
    yaml_file = tmp_path / "bad-rows.yaml"
    yaml_file.write_text("rows: not_a_list")
    with pytest.raises(InvalidCalibrationSetError) as exc_info:
        load_calibration_set(yaml_file)
    assert "`rows` must be a list" in str(exc_info.value)


def test_load_calibration_set_raises_on_empty_rows(tmp_path: Path) -> None:
    yaml_file = tmp_path / "empty-rows.yaml"
    yaml_file.write_text("rows: []")
    with pytest.raises(InvalidCalibrationSetError) as exc_info:
        load_calibration_set(yaml_file)
    assert "`rows` list is empty" in str(exc_info.value)


def test_load_calibration_set_raises_on_missing_required_field(tmp_path: Path) -> None:
    yaml_file = tmp_path / "missing-field.yaml"
    yaml_file.write_text("rows:\n  - prompt: p\n    response: r\n")  # no human_label
    with pytest.raises(InvalidCalibrationSetError) as exc_info:
        load_calibration_set(yaml_file)
    assert "missing required keys" in str(exc_info.value)


def test_load_calibration_set_raises_on_unknown_extra_field(tmp_path: Path) -> None:
    yaml_file = tmp_path / "extra-field.yaml"
    yaml_file.write_text("rows:\n  - prompt: p\n    response: r\n    human_label: 5.0\n    label: 5.0\n")
    with pytest.raises(InvalidCalibrationSetError) as exc_info:
        load_calibration_set(yaml_file)
    assert "unknown extra keys" in str(exc_info.value)


def test_load_calibration_set_raises_on_human_label_out_of_range(tmp_path: Path) -> None:
    yaml_file = tmp_path / "range-violation.yaml"
    yaml_file.write_text("rows:\n  - prompt: p\n    response: r\n    human_label: 15.0\n")
    with pytest.raises(InvalidCalibrationSetError) as exc_info:
        load_calibration_set(yaml_file)
    assert "out of range [0.0, 10.0]" in str(exc_info.value)


def test_load_calibration_set_raises_on_human_label_none(tmp_path: Path) -> None:
    """Nullish-fuzz: None human_label → InvalidCalibrationSetError."""
    yaml_file = tmp_path / "null-label.yaml"
    yaml_file.write_text("rows:\n  - prompt: p\n    response: r\n    human_label: null\n")
    with pytest.raises(InvalidCalibrationSetError) as exc_info:
        load_calibration_set(yaml_file)
    assert "boolean/None" in str(exc_info.value)


def test_load_calibration_set_raises_on_human_label_false(tmp_path: Path) -> None:
    """Nullish-fuzz: false human_label → InvalidCalibrationSetError (bool is int subclass)."""
    yaml_file = tmp_path / "false-label.yaml"
    yaml_file.write_text("rows:\n  - prompt: p\n    response: r\n    human_label: false\n")
    with pytest.raises(InvalidCalibrationSetError) as exc_info:
        load_calibration_set(yaml_file)
    assert "boolean/None" in str(exc_info.value)


def test_load_calibration_set_raises_on_empty_prompt(tmp_path: Path) -> None:
    """Nullish-fuzz: empty prompt → InvalidCalibrationSetError."""
    yaml_file = tmp_path / "empty-prompt.yaml"
    yaml_file.write_text('rows:\n  - prompt: ""\n    response: r\n    human_label: 5.0\n')
    with pytest.raises(InvalidCalibrationSetError) as exc_info:
        load_calibration_set(yaml_file)
    assert "empty / None / False" in str(exc_info.value)


# --------------------------------------------------------------------------- #
# CalibrationReport.__post_init__ validation (AC-12.2.2)                        #
# --------------------------------------------------------------------------- #


def _make_report(
    *,
    rows_processed: int = 2,
    rows_total: int = 2,
    judge_scores: tuple[float, ...] = (8.0, 5.0),
    human_labels: tuple[float, ...] = (9.0, 4.0),
    cohen_kappa: float = 1.0,
    recommended_threshold: float = 7.0,
) -> CalibrationReport:
    return CalibrationReport(
        rubric_path="rubric.md",
        calibration_set_path="calib.yaml",
        judge_adapter="generic",
        judge_model="anthropic/claude-sonnet-4-6",
        rows_total=rows_total,
        rows_processed=rows_processed,
        judge_scores=judge_scores,
        human_labels=human_labels,
        cohen_kappa=cohen_kappa,
        kappa_undefined_reason=None,
        passes_hard_fail=cohen_kappa >= 0.7,
        threshold_tuning={7.0: {"precision": 1.0, "recall": 1.0, "f1": 1.0}},
        recommended_threshold=recommended_threshold,
        systematic_bias_diagnostics=(),
        total_cost_usd=0.0,
        total_latency_seconds=0.0,
    )


def test_calibration_report_passes_hard_fail_at_kappa_0_7() -> None:
    """Boundary check: kappa = 0.7 exactly → passes_hard_fail = True."""
    report = _make_report(cohen_kappa=0.7)
    assert report.passes_hard_fail is True


def test_calibration_report_passes_hard_fail_false_at_kappa_nan() -> None:
    """kappa = nan (zero-variance) → passes_hard_fail = False."""
    report = CalibrationReport(
        rubric_path="r.md",
        calibration_set_path="c.yaml",
        judge_adapter="generic",
        judge_model=None,
        rows_total=2,
        rows_processed=2,
        judge_scores=(8.0, 8.0),
        human_labels=(9.0, 9.0),
        cohen_kappa=math.nan,
        kappa_undefined_reason="human_label_zero_variance",
        passes_hard_fail=False,
        threshold_tuning={},
        recommended_threshold=7.0,
        systematic_bias_diagnostics=(),
        total_cost_usd=0.0,
        total_latency_seconds=0.0,
    )
    assert report.passes_hard_fail is False


def test_calibration_report_validates_rows_processed_le_total() -> None:
    with pytest.raises(ValueError, match="rows_processed.*must be <= rows_total"):
        _make_report(rows_processed=5, rows_total=2)


def test_calibration_report_validates_judge_scores_length() -> None:
    with pytest.raises(ValueError, match="judge_scores length"):
        _make_report(
            rows_processed=3,
            rows_total=3,
            judge_scores=(8.0, 5.0),
            human_labels=(9.0, 4.0, 7.0),
        )


def test_calibration_report_validates_human_labels_in_range() -> None:
    with pytest.raises(ValueError, match="out-of-range value"):
        _make_report(human_labels=(9.0, 15.0))


def test_calibration_report_validates_recommended_threshold_in_range() -> None:
    with pytest.raises(ValueError, match="recommended_threshold"):
        _make_report(recommended_threshold=20.0)


def test_calibration_report_threshold_tuning_defensive_copy() -> None:
    """Mutating the source `threshold_tuning` dict after construction
    MUST NOT mutate the report's `threshold_tuning` (M_R6 defensive copy)."""
    source = {7.0: {"precision": 1.0, "recall": 1.0, "f1": 1.0}}
    report = CalibrationReport(
        rubric_path="r.md",
        calibration_set_path="c.yaml",
        judge_adapter="generic",
        judge_model=None,
        rows_total=1,
        rows_processed=1,
        judge_scores=(9.0,),
        human_labels=(9.0,),
        cohen_kappa=1.0,
        kappa_undefined_reason=None,
        passes_hard_fail=True,
        threshold_tuning=source,
        recommended_threshold=7.0,
        systematic_bias_diagnostics=(),
        total_cost_usd=0.0,
        total_latency_seconds=0.0,
    )
    source[7.0]["f1"] = 0.0
    source[5.0] = {"precision": 0.5, "recall": 0.5, "f1": 0.5}
    assert report.threshold_tuning[7.0]["f1"] == 1.0
    assert 5.0 not in report.threshold_tuning
