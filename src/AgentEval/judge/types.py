# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Dataclass types for the Judge sub-library (Story 12.1 / PRD FR48).

Per architecture.md L1316 — the Judge sub-package's types live here:
`JudgeRubric` (parsed rubric document) + `JudgeScore` (LLM judge output).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class JudgeRubric:
    """A parsed Judge rubric (Story 12.1).

    Phase-1 Markdown rubric format with two required sections:

    - ``## Criteria`` — one bullet per criterion: ``- <name>: <description>``.
      Order is preserved (the LLM sees criteria in spec order).
    - ``## Threshold`` — single-line ``Pass if numeric_score >= <N>``.

    Optional ``## Examples`` section is preserved verbatim in ``raw_text``
    but not parsed into structured fields (the LLM reads it through the
    raw prompt).

    Phase-1 carve-out (DF-12.1-S1 / C79): YAML schema rubrics deferred.
    """

    criteria: tuple[tuple[str, str], ...]
    threshold: float
    raw_text: str

    def __post_init__(self) -> None:
        # Defensive: validate threshold is in [0.0, 10.0] (JudgeScore range).
        if not 0.0 <= self.threshold <= 10.0:
            raise ValueError(f"JudgeRubric.threshold must be in [0.0, 10.0]; got {self.threshold!r}")
        # Defensive: criteria must be non-empty.
        if not self.criteria:
            raise ValueError("JudgeRubric.criteria must contain at least one criterion")


@dataclass(frozen=True)
class JudgeScore:
    """An LLM judge's score for a single agent run (Story 12.1 / PRD FR48).

    Returned by ``Judge.Get Score`` keyword. Frozen + immutable;
    serializes cleanly via ``dataclasses.asdict()``.

    Fields (per epics.md L2095):
        - ``numeric_score: float`` — overall score in ``[0.0, 10.0]``.
        - ``pass_threshold_met: bool`` — ``numeric_score >= rubric.threshold``.
        - ``reasoning: str`` — the LLM's narrative explanation.
        - ``criteria_breakdown: Mapping[str, float]`` — per-criterion sub-scores
          keyed by criterion name. Defensive ``dict()`` copy in
          ``__post_init__`` per Story 1b.2 M_R6 pattern.
        - ``cost_usd: float`` — provider-reported cost of the single judge
          LLM call (non-negative; validated in ``__post_init__``).
    """

    numeric_score: float
    pass_threshold_met: bool
    reasoning: str
    criteria_breakdown: Mapping[str, float] = field(default_factory=dict)
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.numeric_score <= 10.0:
            raise ValueError(
                f"JudgeScore.numeric_score must be in [0.0, 10.0]; "
                f"got {self.numeric_score!r} (judge model violated the rubric range — fix the prompt or the rubric)"
            )
        if self.cost_usd < 0.0:
            raise ValueError(f"JudgeScore.cost_usd must be non-negative; got {self.cost_usd!r}")
        # M_R6: defensive copy so caller mutations to the source dict don't leak.
        object.__setattr__(self, "criteria_breakdown", dict(self.criteria_breakdown))


@dataclass(frozen=True)
class CalibrationReport:
    """Result of `Judge.Calibrate` per Story 12.2.

    Fields:
    - `rubric_path`, `calibration_set_path`, `judge_adapter`, `judge_model`:
      provenance.
    - `rows_total`, `rows_processed`: total rows in the YAML vs how many
      the judge actually scored (may be less if a row raised mid-run; in
      Phase-1 these are always equal because mid-run failures abort).
    - `judge_scores`, `human_labels`: parallel tuples of length
      `rows_processed`.
    - `cohen_kappa`: Cohen's kappa over binarized judge-pass / human-pass
      labels at the rubric's threshold. `nan` if zero-variance (see
      `kappa_undefined_reason`).
    - `kappa_undefined_reason`: one of `"human_label_zero_variance"`,
      `"judge_score_zero_variance"`, `"expected_agreement_unity"`, or
      `None`.
    - `passes_hard_fail`: True iff `not isnan(cohen_kappa) and
      cohen_kappa >= 0.7` per `architecture.md` L199.
    - `threshold_tuning`: `{threshold: {precision, recall, f1}}` over a
      sweep of candidate thresholds; lets callers inspect alternate cuts.
    - `recommended_threshold`: threshold maximizing F1 in
      `threshold_tuning`.
    - `systematic_bias_diagnostics`: human-readable bullets surfacing
      patterns (e.g., "judge consistently scores +1.2 above humans").
    - `total_cost_usd`, `total_latency_seconds`: aggregate.

    `judge_scores`, `human_labels`, and `systematic_bias_diagnostics` are
    already immutable tuples (callers cannot mutate them); only the mutable
    `threshold_tuning` nested dict is defensively copied in `__post_init__`
    so caller mutations to the source dict cannot leak (Story 1b.2 M_R6
    lesson).
    """

    rubric_path: str
    calibration_set_path: str
    judge_adapter: str
    judge_model: str | None
    rows_total: int
    rows_processed: int
    judge_scores: tuple[float, ...]
    human_labels: tuple[float, ...]
    cohen_kappa: float
    kappa_undefined_reason: str | None
    passes_hard_fail: bool
    threshold_tuning: dict[float, dict[str, float]]
    recommended_threshold: float
    systematic_bias_diagnostics: tuple[str, ...]
    total_cost_usd: float
    total_latency_seconds: float

    def __post_init__(self) -> None:
        if self.rows_processed > self.rows_total:
            raise ValueError(
                f"CalibrationReport.rows_processed ({self.rows_processed}) must be <= rows_total ({self.rows_total})"
            )
        if len(self.judge_scores) != self.rows_processed:
            raise ValueError(
                f"CalibrationReport.judge_scores length {len(self.judge_scores)} != "
                f"rows_processed {self.rows_processed}"
            )
        if len(self.human_labels) != self.rows_processed:
            raise ValueError(
                f"CalibrationReport.human_labels length {len(self.human_labels)} != "
                f"rows_processed {self.rows_processed}"
            )
        for label in self.human_labels:
            if not 0.0 <= label <= 10.0:
                raise ValueError(
                    f"CalibrationReport.human_labels contains out-of-range value {label!r}; "
                    f"all labels must be in [0.0, 10.0]"
                )
        if not 0.0 <= self.recommended_threshold <= 10.0:
            raise ValueError(
                f"CalibrationReport.recommended_threshold must be in [0.0, 10.0]; got {self.recommended_threshold!r}"
            )
        if self.total_cost_usd < 0.0:
            raise ValueError(f"CalibrationReport.total_cost_usd must be non-negative; got {self.total_cost_usd!r}")
        if self.total_latency_seconds < 0.0:
            raise ValueError(
                f"CalibrationReport.total_latency_seconds must be non-negative; got {self.total_latency_seconds!r}"
            )
        # Story 12.2 2-way MED (Sonnet MED-3 + Opus LOW-1): enforce the
        # `passes_hard_fail` iff `not isnan(kappa) and kappa >= 0.7` invariant
        # documented in the class docstring. Direct construction (the type is
        # `experimental` public) bypasses the JudgeLibrary.calibrate caller's
        # correct derivation; this check prevents inconsistent reports.
        expected_passes_hard_fail = not math.isnan(self.cohen_kappa) and self.cohen_kappa >= 0.7
        if self.passes_hard_fail != expected_passes_hard_fail:
            raise ValueError(
                f"CalibrationReport.passes_hard_fail={self.passes_hard_fail} inconsistent with "
                f"cohen_kappa={self.cohen_kappa!r} (expected passes_hard_fail={expected_passes_hard_fail} "
                f"per architecture.md L199: True iff not isnan(kappa) and kappa >= 0.7)"
            )
        # M_R6 defensive copy.
        object.__setattr__(
            self,
            "threshold_tuning",
            {threshold: dict(metrics) for threshold, metrics in self.threshold_tuning.items()},
        )


__all__ = ["JudgeRubric", "JudgeScore", "CalibrationReport"]
