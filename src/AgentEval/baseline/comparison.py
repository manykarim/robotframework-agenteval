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

"""CI-overlap-aware regression comparison engine (design Decisions 2-4, 7).

The statistical-honesty core. A naive point-compare that hard-fails on
within-CI noise is exactly the fake-precision the project rejects; a
comparison that silently degrades to point-only without warning is fake-green.
This module implements the three-valued, direction-aware rule:

- **Proportions** (design D2): FAIL iff tolerance breach (absolute percentage
  points) AND the Wilson CIs are disjoint in the regressing direction.
  Breach-with-overlap → PASS + ``PossibleRegressionWarning``.
- **Continuous** (design D3): relative-tolerance breach + one-sided
  Mann-Whitney U (when both sample sets present AND ``[agenteval-advanced]``
  importable) → FAIL; else tolerance-only + ``DegradedComparisonWarning``.
- **Underpower** (design D2): Wilson half-width > tolerance →
  ``UnderpoweredComparisonWarning`` with the approximate ``n`` required.
- **Asymmetric / run-context** (design D6/D7): metric present on one side only
  → ``skipped`` (never auto-fail, never silent-drop); context mismatch
  reported, never gated.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

from AgentEval.baseline.models import (
    ContinuousEvidence,
    MetricComparison,
    ProportionEvidence,
    RegressionReport,
)
from AgentEval.errors import (
    DegradedComparisonWarning,
    PossibleRegressionWarning,
    SkippedMetricWarning,
    UnderpoweredComparisonWarning,
)
from AgentEval.stats.wilson import _standard_normal_quantile, wilson_score_interval

if TYPE_CHECKING:
    from AgentEval.baseline.models import MetricsBaseline, RunContext

__all__ = ["compare"]

_MANN_WHITNEY_ALPHA = 0.05

# Phase-2 carry-overs (see docs/phase-1-5-carry-overs.md):
#   DF-RBT-S1 (C110): exact two-proportion z / Fisher test as an opt-in
#     alternative to the CI-overlap AND-rule below.
#   DF-RBT-S4 (C113): multiple-comparison / family-wise correction across the
#     compared metric set (Phase-1 fixes a per-metric alpha, named in the report).

# Direction registry (design D3). Prefix match on the metric name so any
# `pass_at_k` / `latency_*` variant inherits the family direction.
_HIGHER_IS_BETTER_PREFIXES = ("pass_rate", "pass_at_", "tool_hit_rate")
_LOWER_IS_BETTER_PREFIXES = ("cost_usd", "latency_")


def _direction(metric: str, overrides: dict[str, str] | None) -> str:
    if overrides and metric in overrides:
        return overrides[metric]
    if any(metric.startswith(p) for p in _HIGHER_IS_BETTER_PREFIXES):
        return "higher_is_better"
    if any(metric.startswith(p) for p in _LOWER_IS_BETTER_PREFIXES):
        return "lower_is_better"
    # Unknown metric families (extra_metrics) default to higher_is_better.
    return "higher_is_better"


def parse_tolerance(value: str | float) -> float:
    """Parse ``"5%"`` / ``0.05`` / ``5`` → a fraction (``0.05``).

    ``"5%"`` → 0.05. A bare float is taken as an already-normalized fraction
    (``0.05``). A bare int/float ``>= 1`` is treated as a percentage
    (``5`` → 0.05) for RF ergonomics.
    """
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            return float(text[:-1]) / 100.0
        num = float(text)
        return num / 100.0 if num >= 1.0 else num
    num = float(value)
    return num / 100.0 if num >= 1.0 else num


def _advanced_available() -> tuple[bool, str | None]:
    """Return ``(available, reason)`` for the ``[agenteval-advanced]`` extra."""
    try:
        import numpy  # noqa: F401
        import scipy  # noqa: F401
    except ImportError as exc:
        return (False, f"the [agenteval-advanced] extra is not installed ({exc})")
    return (True, None)


def _mann_whitney_one_sided_reject(
    current: list[float],
    baseline: list[float],
    *,
    lower_is_better: bool,
) -> bool | None:
    """One-sided Mann-Whitney U rejection for "current is worse than baseline".

    For a lower-is-better metric, "worse" = current > baseline. Returns True
    when the one-sided test rejects at ``alpha`` in the regressing direction,
    False when it does not, ``None`` when the test is unavailable/undecidable.
    """
    from AgentEval.stats.mannwhitney import compute_mann_whitney_u

    try:
        result = compute_mann_whitney_u(current, baseline)
    except Exception:  # noqa: BLE001 — defensive; degrade rather than crash the gate
        return None
    if math.isnan(result.p_value):
        return None
    # effect_size_r > 0 ⇒ current tends larger than baseline.
    current_larger = result.effect_size_r > 0
    worse = current_larger if lower_is_better else (not current_larger)
    p_one_sided = result.p_value / 2.0 if worse else 1.0 - result.p_value / 2.0
    return worse and (p_one_sided < _MANN_WHITNEY_ALPHA)


def _required_n_for_tolerance(tolerance: float, confidence: float) -> int:
    """Approximate trials needed for a Wilson half-width ≈ tolerance (worst-case p=0.5)."""
    if tolerance <= 0:
        return 0
    z = _standard_normal_quantile((1.0 + confidence) / 2.0)
    # half-width ≈ z * sqrt(p(1-p)/n); worst case p=0.5 ⇒ p(1-p)=0.25.
    return math.ceil((z * z) * 0.25 / (tolerance * tolerance))


@dataclass
class _Emitter:
    """Collects warnings so the keyword can emit them once, in order."""

    def possible_regression(self, msg: str) -> None:
        warnings.warn(msg, PossibleRegressionWarning, stacklevel=3)

    def underpowered(self, msg: str) -> None:
        warnings.warn(msg, UnderpoweredComparisonWarning, stacklevel=3)

    def degraded(self, msg: str) -> None:
        warnings.warn(msg, DegradedComparisonWarning, stacklevel=3)

    def skipped_metric(self, msg: str) -> None:
        warnings.warn(msg, SkippedMetricWarning, stacklevel=3)


def _compare_proportion(
    metric: str,
    direction: str,
    base: ProportionEvidence,
    curr: ProportionEvidence,
    tolerance: float,
    confidence: float,
    emit: _Emitter,
) -> MetricComparison:
    base_ci = wilson_score_interval(base.successes, base.trials, confidence)
    curr_ci = wilson_score_interval(curr.successes, curr.trials, confidence)
    semantics = (
        f"tolerance {tolerance:.4g} = {tolerance:.4g} absolute on {metric} "
        f"(proportion, {int(confidence * 100)}% Wilson CI)"
    )

    higher_better = direction == "higher_is_better"
    # Regressing delta (positive ⇒ moved in the bad direction).
    delta = (base.value - curr.value) if higher_better else (curr.value - base.value)
    breach = delta > tolerance

    # CI disjoint in the regressing direction: higher-is-better ⇒ current
    # upper < baseline lower; lower-is-better ⇒ current lower > baseline upper.
    disjoint = (curr_ci[1] < base_ci[0]) if higher_better else (curr_ci[0] > base_ci[1])

    # Underpower: Wilson half-width (worst of the two sides) vs tolerance.
    half_width = max((base_ci[1] - base_ci[0]) / 2.0, (curr_ci[1] - curr_ci[0]) / 2.0)
    if half_width > tolerance:
        n_req = _required_n_for_tolerance(tolerance, confidence)
        emit.underpowered(
            f"{metric}: comparison is UNDERPOWERED — Wilson half-width {half_width:.4g} exceeds "
            f"tolerance {tolerance:.4g} at baseline N={base.trials} / current N={curr.trials}. "
            f"Approximately n>={n_req} trials per side are needed to detect a {tolerance:.4g} drop. "
            f"Raise n in `Stat.Run N Times` rather than raising tolerance."
        )

    numbers = (
        f"baseline={base.value:.4g} (CI [{base_ci[0]:.4g}, {base_ci[1]:.4g}], N={base.trials}); "
        f"current={curr.value:.4g} (CI [{curr_ci[0]:.4g}, {curr_ci[1]:.4g}], N={curr.trials}); "
        f"{semantics}"
    )

    if breach and disjoint:
        return MetricComparison(
            metric=metric,
            direction=direction,  # type: ignore[arg-type]
            baseline_value=base.value,
            current_value=curr.value,
            baseline_ci=base_ci,
            current_ci=curr_ci,
            baseline_trials=base.trials,
            current_trials=curr.trials,
            tolerance=tolerance,
            tolerance_semantics=semantics,
            comparison_mode="wilson_ci_disjoint",
            verdict="fail",
            reason=f"REGRESSION: drop {delta:.4g} exceeds tolerance AND Wilson CIs disjoint. {numbers}",
        )
    if breach and not disjoint:
        emit.possible_regression(
            f"{metric}: PossibleRegressionWarning — drop {delta:.4g} exceeds tolerance {tolerance:.4g} "
            f"BUT the Wilson CIs overlap (likely noise, not a confirmed regression). {numbers}. "
            f"Raise n in `Stat.Run N Times` to tighten the CIs before trusting the drop."
        )
        return MetricComparison(
            metric=metric,
            direction=direction,  # type: ignore[arg-type]
            baseline_value=base.value,
            current_value=curr.value,
            baseline_ci=base_ci,
            current_ci=curr_ci,
            baseline_trials=base.trials,
            current_trials=curr.trials,
            tolerance=tolerance,
            tolerance_semantics=semantics,
            comparison_mode="wilson_ci_overlap",
            verdict="pass",
            reason=f"PASS-with-warning: tolerance breached but CIs overlap. {numbers}",
            warning="PossibleRegressionWarning",
        )
    return MetricComparison(
        metric=metric,
        direction=direction,  # type: ignore[arg-type]
        baseline_value=base.value,
        current_value=curr.value,
        baseline_ci=base_ci,
        current_ci=curr_ci,
        baseline_trials=base.trials,
        current_trials=curr.trials,
        tolerance=tolerance,
        tolerance_semantics=semantics,
        comparison_mode="wilson_ci",
        verdict="pass",
        reason=f"PASS: within tolerance (or improved). {numbers}",
    )


def _compare_continuous(
    metric: str,
    direction: str,
    base: ContinuousEvidence,
    curr: ContinuousEvidence,
    tolerance: float,
    emit: _Emitter,
) -> MetricComparison:
    lower_better = direction == "lower_is_better"
    # Relative tolerance to the baseline value (design D4).
    tol_abs = abs(base.value) * tolerance
    dollars = f"= {tol_abs:.4g} on {metric} baseline {base.value:.4g}"
    semantics = f"tolerance {tolerance:.4g} relative to baseline ({dollars})"

    delta = (curr.value - base.value) if lower_better else (base.value - curr.value)
    breach = delta > tol_abs

    both_samples = bool(base.samples) and bool(curr.samples)
    available, reason = _advanced_available()

    comparison_mode = "point_only"
    rank_rejected: bool | None = None
    if both_samples and available:
        rank_rejected = _mann_whitney_one_sided_reject(
            list(curr.samples), list(base.samples), lower_is_better=lower_better
        )
        if rank_rejected is None:
            comparison_mode = "point_only"
            emit.degraded(
                f"{metric}: DegradedComparisonWarning — Mann-Whitney U was undecidable "
                f"(identical rank distributions); falling back to point-only tolerance. "
                f"comparison_mode=point_only."
            )
        else:
            comparison_mode = "mann_whitney"
    else:
        why = reason if not available else "raw samples are missing on one or both sides"
        emit.degraded(
            f"{metric}: DegradedComparisonWarning — the rank-test noise guard was SKIPPED because "
            f"{why}. Falling back to point-only tolerance comparison; comparison_mode=point_only. "
            f"Install robotframework-agenteval[agenteval-advanced] and capture raw samples to "
            f"enable the Mann-Whitney U guard."
        )

    numbers = (
        f"baseline={base.value:.4g} (N={len(base.samples)}); "
        f"current={curr.value:.4g} (N={len(curr.samples)}); {semantics}"
    )

    if comparison_mode == "mann_whitney":
        fail = breach and bool(rank_rejected)
        detail = f"Mann-Whitney one-sided reject={rank_rejected}"
    else:
        fail = breach
        detail = "point-only (degraded)"

    verdict = "fail" if fail else "pass"
    reason = (
        f"REGRESSION: rise {delta:.4g} exceeds relative tolerance ({detail}). {numbers}"
        if fail
        else f"PASS: within relative tolerance (or {detail}). {numbers}"
    )
    return MetricComparison(
        metric=metric,
        direction=direction,  # type: ignore[arg-type]
        baseline_value=base.value,
        current_value=curr.value,
        baseline_ci=None,
        current_ci=None,
        baseline_trials=len(base.samples),
        current_trials=len(curr.samples),
        tolerance=tolerance,
        tolerance_semantics=semantics,
        comparison_mode=comparison_mode,
        verdict=verdict,  # type: ignore[arg-type]
        reason=reason,
        warning=("DegradedComparisonWarning" if comparison_mode == "point_only" else None),
    )


def _skipped(metric: str, direction: str, reason: str, emit: _Emitter) -> MetricComparison:
    # Never a silent-drop (design D6/D7): a skipped metric still PASSES the gate
    # per the "never auto-fail on skip" rule, but the skip is made LOUD so a CI
    # gate that silently vanishes (e.g. the current run stops producing
    # `cost_usd`) is visible without the caller inspecting `report.comparisons`.
    emit.skipped_metric(
        f"{metric}: SkippedMetricWarning — {reason}. This metric is NOT gated; if it was "
        f"serving as a CI gate it has silently vanished. Restore the metric on both sides "
        f"(matching evidence kind) so the comparison can gate it again."
    )
    return MetricComparison(
        metric=metric,
        direction=direction,  # type: ignore[arg-type]
        baseline_value=None,
        current_value=None,
        baseline_ci=None,
        current_ci=None,
        baseline_trials=None,
        current_trials=None,
        tolerance=0.0,
        tolerance_semantics="n/a",
        comparison_mode="skipped",
        verdict="skipped",
        reason=reason,
    )


def compare(
    baseline: MetricsBaseline,
    current: MetricsBaseline,
    *,
    tolerance: str | float = "5%",
    tolerances: dict[str, str | float] | None = None,
    directions: dict[str, str] | None = None,
    confidence: float = 0.95,
) -> RegressionReport:
    """Compare ``current`` against ``baseline`` per the honest three-valued rule.

    Emits ``PossibleRegressionWarning`` / ``UnderpoweredComparisonWarning`` /
    ``DegradedComparisonWarning`` as side effects (via ``warnings.warn``) so
    the residual uncertainty is loud, not silent.
    """
    default_tol = parse_tolerance(tolerance)
    per_metric_tol = {k: parse_tolerance(v) for k, v in (tolerances or {}).items()}
    emit = _Emitter()

    comparisons: list[MetricComparison] = []
    all_metrics = sorted(set(baseline.metrics) | set(current.metrics))
    for metric in all_metrics:
        direction = _direction(metric, directions)
        tol = per_metric_tol.get(metric, default_tol)
        base_ev = baseline.metrics.get(metric)
        curr_ev = current.metrics.get(metric)

        if base_ev is None:
            comparisons.append(
                _skipped(metric, direction, f"skipped: {metric!r} present in current run but not in baseline", emit)
            )
            continue
        if curr_ev is None:
            comparisons.append(
                _skipped(metric, direction, f"skipped: {metric!r} present in baseline but not in current run", emit)
            )
            continue

        if isinstance(base_ev, ProportionEvidence) and isinstance(curr_ev, ProportionEvidence):
            comparisons.append(_compare_proportion(metric, direction, base_ev, curr_ev, tol, confidence, emit))
        elif isinstance(base_ev, ContinuousEvidence) and isinstance(curr_ev, ContinuousEvidence):
            comparisons.append(_compare_continuous(metric, direction, base_ev, curr_ev, tol, emit))
        else:
            comparisons.append(
                _skipped(
                    metric,
                    direction,
                    f"skipped: {metric!r} evidence kind mismatch "
                    f"(baseline={type(base_ev).__name__}, current={type(curr_ev).__name__})",
                    emit,
                )
            )

    # Extra metrics — point-only comparison (design D5). Phase-2 carry-over
    # DF-RBT-S3 / C112: first-class evidence-bearing judge/activation metric
    # families would gate with the full CI/rank rule instead of point-only here.
    for metric in sorted(set(baseline.extra_metrics) | set(current.extra_metrics)):
        direction = _direction(metric, directions)
        tol = per_metric_tol.get(metric, default_tol)
        base_val = baseline.extra_metrics.get(metric)
        curr_val = current.extra_metrics.get(metric)
        if base_val is None or curr_val is None:
            comparisons.append(
                _skipped(metric, direction, f"skipped: extra metric {metric!r} present on only one side", emit)
            )
            continue
        base_ce = ContinuousEvidence(samples=(), value=base_val, total=base_val, mean=base_val)
        curr_ce = ContinuousEvidence(samples=(), value=curr_val, total=curr_val, mean=curr_val)
        comparisons.append(_compare_continuous(metric, direction, base_ce, curr_ce, tol, emit))

    _log_context_mismatch(baseline.run_context, current.run_context)

    return RegressionReport(
        comparisons=tuple(comparisons),
        baseline_context=baseline.run_context,
        current_context=current.run_context,
    )


def _log_context_mismatch(base: RunContext, curr: RunContext) -> None:
    """Reported, never gated (design D7)."""
    import logging

    logger = logging.getLogger("AgentEval.baseline")
    for field_name in ("model", "adapter_name", "adapter_version", "library_version"):
        b = getattr(base, field_name)
        c = getattr(curr, field_name)
        if b != c:
            logger.info(
                "Metrics Should Not Regress: run-context %s differs — baseline=%r current=%r "
                "(reported, not gated — cross-context comparison is the primary use case).",
                field_name,
                b,
                c,
            )
