# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Judge calibration helpers (Story 12.2).

Ships:
- `KAPPA_HARD_FAIL_THRESHOLD = 0.7` per `architecture.md` L199 (agentguard
  borrow: "Cohen's κ ≥ 0.7 hard-fail" calibration discipline).
- `CalibrationRow` frozen dataclass (one labeled example).
- `load_calibration_set(path)` — strict YAML loader; raises
  `InvalidCalibrationSetError` on any parse / schema / nullish-input failure
  (UPSTREAM Story 12.1 Sonnet HIGH-2 + Opus HIGH-1 2-way boundary-rewrap
  lesson + Sonnet MED-2 nullish-input fuzz lesson).
- `compute_cohen_kappa(judge_scores, human_labels, pass_threshold)` — pure-
  Python (no scipy dependency) Cohen's kappa over binarized
  judge-pass / human-pass labels.

Zero-variance edge cases return `nan` + a `kappa_undefined_reason` so the
keyword surfaces "cannot calibrate" rather than dividing by zero
(Story 12.2 D-7 decision).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml

from AgentEval.errors import InvalidCalibrationSetError

KAPPA_HARD_FAIL_THRESHOLD: Final[float] = 0.7
"""Cohen's kappa hard-fail threshold per `architecture.md` L199.

agentguard ADR-011-borrow: a judge calibration with `kappa < 0.7` is
"unreliable agreement" — surfaces in `CalibrationReport.passes_hard_fail`.
"""

_REQUIRED_ROW_FIELDS: Final[frozenset[str]] = frozenset({"prompt", "response", "human_label"})
"""Per-row schema: exactly these three required fields. Unknown extra keys
raise (strict schema per Story 12.2 D-6)."""


@dataclass(frozen=True)
class CalibrationRow:
    """One labeled example in a calibration set."""

    prompt: str
    response: str
    human_label: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.human_label <= 10.0:
            raise ValueError(f"CalibrationRow.human_label must be in [0.0, 10.0]; got {self.human_label!r}")


def load_calibration_set(path: str | Path) -> tuple[CalibrationRow, ...]:
    """Strict YAML calibration set loader.

    Schema:

    ```yaml
    rows:
      - prompt: "..."
        response: "..."
        human_label: 9.0
    ```

    Failure modes raise `InvalidCalibrationSetError`:
    - file not found / extension not `.yaml`/`.yml`
    - YAML parse failure
    - top-level not a mapping or missing `rows` key
    - `rows` not a list
    - per-row missing required field, unknown extra key, nullish-input
      variant (`None`/`""`/`False`/missing-key), or `human_label` out of
      `[0.0, 10.0]`
    """
    rubric_path = Path(path) if not isinstance(path, Path) else path

    if not rubric_path.exists():
        raise InvalidCalibrationSetError(
            f"Judge calibration set file not found: {rubric_path}",
            file_path=str(rubric_path),
            line_number=None,
            field_name="",
            fix_suggestion="Create the calibration set YAML file with a `rows:` list.",
        )
    if rubric_path.suffix.lower() not in (".yaml", ".yml"):
        raise InvalidCalibrationSetError(
            f"Judge calibration set must have `.yaml` or `.yml` extension; got {rubric_path.suffix!r}",
            file_path=str(rubric_path),
            line_number=None,
            field_name="",
            fix_suggestion="Rename the file with a `.yaml` or `.yml` extension.",
        )

    raw_text = rubric_path.read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise InvalidCalibrationSetError(
            f"Judge calibration set YAML parse failed: {exc}",
            file_path=str(rubric_path),
            line_number=getattr(getattr(exc, "problem_mark", None), "line", None),
            field_name="",
            fix_suggestion="Validate the YAML syntax (https://yamllint.com).",
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidCalibrationSetError(
            f"Judge calibration set top-level value must be a mapping; got {type(parsed).__name__}",
            file_path=str(rubric_path),
            line_number=None,
            field_name="",
            fix_suggestion="Wrap your data in a top-level `rows:` mapping.",
        )

    rows_raw = parsed.get("rows")
    if rows_raw is None:
        raise InvalidCalibrationSetError(
            "Judge calibration set missing required `rows:` key",
            file_path=str(rubric_path),
            line_number=None,
            field_name="rows",
            fix_suggestion="Add a top-level `rows:` list of row mappings.",
        )
    if not isinstance(rows_raw, list):
        raise InvalidCalibrationSetError(
            f"Judge calibration set `rows` must be a list; got {type(rows_raw).__name__}",
            file_path=str(rubric_path),
            line_number=None,
            field_name="rows",
            fix_suggestion="Format `rows:` as a YAML list of row mappings.",
        )

    # Story 12.2 D-6 strict schema (UPSTREAM Story 12.1 Opus MED-4 lesson):
    # unknown top-level keys raise (no silent alias drop). Per-row strict
    # schema check is below; this is the document-level parallel.
    extra_top_keys = set(parsed.keys()) - {"rows"}
    if extra_top_keys:
        raise InvalidCalibrationSetError(
            f"Judge calibration set has unknown top-level keys: {sorted(extra_top_keys)!r}",
            file_path=str(rubric_path),
            line_number=None,
            field_name="",
            fix_suggestion="Only `rows:` is accepted at the top level.",
        )

    rows: list[CalibrationRow] = []
    for index, row_raw in enumerate(rows_raw):
        rows.append(_parse_row(row_raw, index, rubric_path))

    if not rows:
        raise InvalidCalibrationSetError(
            "Judge calibration set `rows` list is empty",
            file_path=str(rubric_path),
            line_number=None,
            field_name="rows",
            fix_suggestion="Add at least one row mapping with `prompt`, `response`, `human_label`.",
        )

    return tuple(rows)


def _parse_row(row_raw: object, index: int, rubric_path: Path) -> CalibrationRow:
    """Validate one row and return a `CalibrationRow`."""
    if not isinstance(row_raw, dict):
        raise InvalidCalibrationSetError(
            f"Judge calibration set `rows[{index}]` must be a mapping; got {type(row_raw).__name__}",
            file_path=str(rubric_path),
            line_number=None,
            field_name=f"rows[{index}]",
            fix_suggestion="Format each row as a mapping with `prompt`, `response`, `human_label`.",
        )

    extra_keys = set(row_raw.keys()) - _REQUIRED_ROW_FIELDS
    if extra_keys:
        raise InvalidCalibrationSetError(
            f"Judge calibration set `rows[{index}]` has unknown extra keys: {sorted(extra_keys)!r}",
            file_path=str(rubric_path),
            line_number=None,
            field_name=f"rows[{index}]",
            fix_suggestion=("Remove the extra keys; only `prompt`, `response`, `human_label` are accepted."),
        )

    missing_keys = _REQUIRED_ROW_FIELDS - set(row_raw.keys())
    if missing_keys:
        raise InvalidCalibrationSetError(
            f"Judge calibration set `rows[{index}]` missing required keys: {sorted(missing_keys)!r}",
            file_path=str(rubric_path),
            line_number=None,
            field_name=f"rows[{index}]",
            fix_suggestion="Add the missing keys; each row needs `prompt`, `response`, `human_label`.",
        )

    # Nullish-input fuzz (UPSTREAM Story 12.1 Sonnet MED-2 lesson +
    # `feedback_nullish_input_fuzz_checklist`): None, "", False all coerce
    # to falsy `str()`/`float()`; explicit type-and-truthiness guards.
    for str_field in ("prompt", "response"):
        value = row_raw[str_field]
        if value is None or value is False or value == "":
            raise InvalidCalibrationSetError(
                f"Judge calibration set `rows[{index}].{str_field}` is empty / None / False",
                file_path=str(rubric_path),
                line_number=None,
                field_name=f"rows[{index}].{str_field}",
                fix_suggestion=f"Provide a non-empty string for `{str_field}`.",
            )
        if not isinstance(value, str):
            raise InvalidCalibrationSetError(
                f"Judge calibration set `rows[{index}].{str_field}` must be a string; got {type(value).__name__}",
                file_path=str(rubric_path),
                line_number=None,
                field_name=f"rows[{index}].{str_field}",
                fix_suggestion=f"Provide a string for `{str_field}`.",
            )

    raw_label = row_raw["human_label"]
    # Boolean check BEFORE float() — `bool` is `int` subclass; `float(False)
    # == 0.0` would silently coerce a YAML boolean into a 0.0 label
    # (Story 12.1 Sonnet MED-2 lesson).
    if isinstance(raw_label, bool) or raw_label is None:
        raise InvalidCalibrationSetError(
            f"Judge calibration set `rows[{index}].human_label` is boolean/None; expected a float",
            file_path=str(rubric_path),
            line_number=None,
            field_name=f"rows[{index}].human_label",
            fix_suggestion="Provide a float in [0.0, 10.0] for `human_label`.",
        )
    try:
        human_label = float(raw_label)
    except (TypeError, ValueError) as exc:
        raise InvalidCalibrationSetError(
            f"Judge calibration set `rows[{index}].human_label` not numeric: {raw_label!r}",
            file_path=str(rubric_path),
            line_number=None,
            field_name=f"rows[{index}].human_label",
            fix_suggestion="Provide a float in [0.0, 10.0] for `human_label`.",
        ) from exc
    if not 0.0 <= human_label <= 10.0:
        raise InvalidCalibrationSetError(
            f"Judge calibration set `rows[{index}].human_label` out of range [0.0, 10.0]: {human_label}",
            file_path=str(rubric_path),
            line_number=None,
            field_name=f"rows[{index}].human_label",
            fix_suggestion="Use a value in [0.0, 10.0]; same range as `JudgeScore.numeric_score`.",
        )

    return CalibrationRow(
        prompt=row_raw["prompt"],
        response=row_raw["response"],
        human_label=human_label,
    )


def compute_cohen_kappa(
    judge_scores: tuple[float, ...] | list[float],
    human_labels: tuple[float, ...] | list[float],
    pass_threshold: float,
) -> tuple[float, str | None]:
    """Compute Cohen's kappa over binarized judge-pass / human-pass labels.

    Each sequence is binarized via `value >= pass_threshold → 1, else → 0`.
    Returns `(kappa, undefined_reason)`:
    - On zero-variance human labels: `(nan, "human_label_zero_variance")`
    - On zero-variance judge scores: `(nan, "judge_score_zero_variance")`
    - Otherwise: `(kappa_value, None)`

    Per Story 12.2 D-7: zero-variance edge cases return `nan` instead of
    dividing by zero so callers can surface "cannot calibrate" diagnostics
    via `passes_hard_fail=False`.

    Raises `ValueError` on length-mismatch or empty sequences (programmer
    error — caller must validate first).

    Pure-Python (no scipy) per PRD L864 — Cohen's kappa is on the
    `agenteval-core` surface, not behind the `agenteval-advanced` extra.
    """
    if len(judge_scores) != len(human_labels):
        raise ValueError(
            f"compute_cohen_kappa: judge_scores and human_labels length mismatch "
            f"({len(judge_scores)} vs {len(human_labels)})"
        )
    n = len(judge_scores)
    if n == 0:
        raise ValueError("compute_cohen_kappa: cannot compute kappa over empty sequences")

    judge_bin = [1 if score >= pass_threshold else 0 for score in judge_scores]
    human_bin = [1 if label >= pass_threshold else 0 for label in human_labels]

    if len(set(human_bin)) == 1:
        return math.nan, "human_label_zero_variance"
    if len(set(judge_bin)) == 1:
        return math.nan, "judge_score_zero_variance"

    p_observed = sum(1 for j, h in zip(judge_bin, human_bin, strict=True) if j == h) / n
    p_judge_1 = sum(judge_bin) / n
    p_human_1 = sum(human_bin) / n
    p_expected = (p_judge_1 * p_human_1) + ((1 - p_judge_1) * (1 - p_human_1))

    if p_expected == 1.0:
        # Defensive belt-and-braces: this branch is unreachable for
        # `p_judge_1, p_human_1 ∈ (0, 1)` because the two zero-variance
        # guards above (`set(human_bin) == 1` and `set(judge_bin) == 1`)
        # exhaustively cover the cases where `p_expected == 1.0`.
        # Algebra: `p_e = p_j*p_h + (1-p_j)*(1-p_h) < 1` iff `p_j ∈ (0,1)
        # AND p_h ∈ (0,1)`. Kept as a defensive guard against future
        # refactors that might widen the early-return conditions.
        return math.nan, "expected_agreement_unity"

    kappa = (p_observed - p_expected) / (1.0 - p_expected)
    return kappa, None
