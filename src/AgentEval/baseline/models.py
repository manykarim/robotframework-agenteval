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

"""Frozen dataclasses for the regression-baseline surface (design D1 + D8).

Evidence-bearing baselines (design Decision 1): proportion metrics carry
``successes`` + ``trials`` and continuous metrics carry the raw per-trial
sample list, so confidence intervals and rank tests are recomputable at
compare time (never point-only frozen verdicts).

All dataclasses are frozen and JSON-round-trippable; the trend models expose
``.as_dict()`` / ``.values()`` accessors usable directly from Robot Framework
assertions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from AgentEval._heatmap._grid import render_ascii_grid

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "ContinuousEvidence",
    "MetricComparison",
    "MetricsBaseline",
    "ProportionEvidence",
    "RegressionReport",
    "RunContext",
    "TrendGrid",
    "TrendPoint",
    "TrendSeries",
]

# Missing-cell honesty sentinel — matches the `_heatmap` em-dash (Story 10.1).
_MISSING_SENTINEL = " — "


@dataclass(frozen=True)
class ProportionEvidence:
    """Sufficient statistics for a proportion metric (design D1).

    Stores ``successes`` + ``trials`` alongside the derived point ``value`` so
    a Wilson CI is recomputable at any confidence level at compare time. For
    ``pass_at_k`` metrics ``k`` records the requested k (``value`` is the
    HumanEval estimator); for ``pass_rate`` / ``tool_hit_rate`` ``k`` is None
    and ``value == successes / trials``.
    """

    kind: Literal["proportion"] = field(default="proportion", init=False)
    successes: int = 0
    trials: int = 0
    value: float = 0.0
    k: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "successes": self.successes,
            "trials": self.trials,
            "value": self.value,
            "k": self.k,
        }


@dataclass(frozen=True)
class ContinuousEvidence:
    """Raw per-trial samples + derived points for a continuous metric (design D1).

    ``value`` is the designated comparison point for the metric name
    (``cost_usd`` → per-trial mean; ``latency_p95_ms`` → p95). ``samples`` is
    the raw per-trial list that makes a Mann-Whitney U comparison possible
    run-over-run. ``samples_truncated`` is reserved for a future sample cap
    (design D1 — no cap imposed in Phase 1; Phase-2 carry-over DF-RBT-S2 / C111).
    """

    kind: Literal["continuous"] = field(default="continuous", init=False)
    samples: tuple[float, ...] = ()
    value: float = 0.0
    total: float = 0.0
    mean: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    samples_truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "samples": list(self.samples),
            "value": self.value,
            "total": self.total,
            "mean": self.mean,
            "p50": self.p50,
            "p95": self.p95,
            "samples_truncated": self.samples_truncated,
        }


@dataclass(frozen=True)
class RunContext:
    """Reproducibility metadata for a snapshot (design D6 + FR39 parity).

    ``model`` / ``adapter_name`` / ``adapter_version`` are informational and
    NEVER gate a comparison (design D7). ``git_sha`` / ``git_dirty`` are
    best-effort (design D10) and may be ``None`` outside a git repository.
    """

    model: str | None = None
    adapter_name: str | None = None
    adapter_version: str | None = None
    library_version: str | None = None
    timestamp: str | None = None
    git_sha: str | None = None
    git_dirty: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "library_version": self.library_version,
            "timestamp": self.timestamp,
            "git_sha": self.git_sha,
            "git_dirty": self.git_dirty,
        }


@dataclass(frozen=True)
class MetricsBaseline:
    """A schema-versioned, evidence-bearing metric snapshot (design D1 + D6).

    ``metrics`` maps metric name → ``ProportionEvidence`` | ``ContinuousEvidence``.
    ``extra_metrics`` holds user-supplied named scalars (compared point-only).
    """

    schema_version: int
    metrics: dict[str, ProportionEvidence | ContinuousEvidence]
    extra_metrics: dict[str, float]
    run_context: RunContext

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "metrics": {name: ev.as_dict() for name, ev in self.metrics.items()},
            "extra_metrics": dict(self.extra_metrics),
            "run_context": self.run_context.as_dict(),
        }


@dataclass(frozen=True)
class MetricComparison:
    """Per-metric comparison outcome (design D2/D3 — numeric bars, not verdicts).

    Records both points + both CIs + the tolerance applied (with restated
    semantics) + the comparison mode + the three-valued verdict, so the
    failure message can quote every number (per ``feedback_honest_framing``).

    ``verdict`` ∈ {``pass``, ``fail``, ``skipped``}. A tolerance breach whose
    CIs overlap is a ``pass`` with ``warning="PossibleRegressionWarning"``.
    """

    metric: str
    direction: Literal["higher_is_better", "lower_is_better"]
    baseline_value: float | None
    current_value: float | None
    baseline_ci: tuple[float, float] | None
    current_ci: tuple[float, float] | None
    baseline_trials: int | None
    current_trials: int | None
    tolerance: float
    tolerance_semantics: str
    comparison_mode: str
    verdict: Literal["pass", "fail", "skipped"]
    reason: str
    warning: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "direction": self.direction,
            "baseline_value": self.baseline_value,
            "current_value": self.current_value,
            "baseline_ci": list(self.baseline_ci) if self.baseline_ci is not None else None,
            "current_ci": list(self.current_ci) if self.current_ci is not None else None,
            "baseline_trials": self.baseline_trials,
            "current_trials": self.current_trials,
            "tolerance": self.tolerance,
            "tolerance_semantics": self.tolerance_semantics,
            "comparison_mode": self.comparison_mode,
            "verdict": self.verdict,
            "reason": self.reason,
            "warning": self.warning,
        }


@dataclass(frozen=True)
class RegressionReport:
    """The full per-metric comparison report (design D2 + D7).

    ``comparisons`` is ordered by metric name. ``baseline_context`` /
    ``current_context`` are printed side by side (a context mismatch is
    reported, never gated). ``regressed`` is True iff any comparison FAILed.
    """

    comparisons: tuple[MetricComparison, ...]
    baseline_context: RunContext
    current_context: RunContext

    @property
    def regressed(self) -> bool:
        return any(c.verdict == "fail" for c in self.comparisons)

    def failures(self) -> tuple[MetricComparison, ...]:
        return tuple(c for c in self.comparisons if c.verdict == "fail")

    def as_dict(self) -> dict[str, Any]:
        return {
            "regressed": self.regressed,
            "comparisons": [c.as_dict() for c in self.comparisons],
            "baseline_context": self.baseline_context.as_dict(),
            "current_context": self.current_context.as_dict(),
        }


@dataclass(frozen=True)
class TrendPoint:
    """One time-ordered point in a metric trend (design D8).

    ``value`` may be ``None`` when the metric is absent from that snapshot
    (missing point, never zero-filled — ``_heatmap`` honesty precedent).
    ``ci_lower`` / ``ci_upper`` are the recomputed Wilson CI for proportion
    metrics, else ``None``.
    """

    timestamp: str | None
    git_sha: str | None
    value: float | None
    ci_lower: float | None
    ci_upper: float | None
    n_trials: int | None
    model: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "git_sha": self.git_sha,
            "value": self.value,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "n_trials": self.n_trials,
            "model": self.model,
        }


@dataclass(frozen=True)
class TrendSeries:
    """Time-ordered series for one named metric (design D8).

    ``.values()`` returns the ordered value list (with ``None`` for
    missing-in-snapshot points). ``.grid`` is the optional metrics × snapshots
    ``TrendGrid`` built from the SAME history (reuses the ``_heatmap`` ASCII
    renderer) so the trend grid is reachable directly off the returned series.
    """

    metric: str
    points: tuple[TrendPoint, ...]
    grid: TrendGrid | None = None

    def values(self) -> list[float | None]:
        return [p.value for p in self.points]

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "points": [p.as_dict() for p in self.points],
        }


@dataclass(frozen=True)
class TrendGrid:
    """Metrics × snapshots grid rendering (design D8) reusing the `_heatmap` renderer.

    Rows = metric names, columns = snapshot labels, cell = the metric's point
    value in that snapshot (or a missing sentinel). Same ``.as_ascii()`` /
    ``.as_dict()`` surface as ``CohortHeatmap``; missing cells render the
    em-dash sentinel and are omitted (never ``0.0``) from ``.as_dict()``.
    """

    metrics: tuple[str, ...]
    snapshots: tuple[str, ...]
    # (metric, snapshot_label, value) triples — missing cells omitted.
    cells: tuple[tuple[str, str, float], ...]

    def as_dict(self) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {m: {} for m in self.metrics}
        for metric, snapshot, value in self.cells:
            out.setdefault(metric, {})[snapshot] = value
        return out

    def as_ascii(self) -> str:
        if not self.metrics or not self.snapshots:
            return "(empty trend grid)"
        data = self.as_dict()

        def fmt(metric: str, snapshot: str) -> str:
            value = data.get(metric, {}).get(snapshot)
            return _MISSING_SENTINEL if value is None else f"{value:.2f}"

        return render_ascii_grid(
            corner_label="Metric",
            row_labels=self.metrics,
            col_labels=self.snapshots,
            format_cell=fmt,
        )

    @classmethod
    def from_snapshots(
        cls,
        snapshots: Sequence[dict[str, Any]],
        labels: Sequence[str],
    ) -> TrendGrid:
        """Build a grid over every metric present in any snapshot.

        Args:
            snapshots: parsed snapshot dicts (each ``{schema_version, metrics,
                run_context, ...}``) in append order.
            labels: one column label per snapshot (same length/order).

        Missing metric-in-snapshot cells are OMITTED (design D8 honesty), so
        ``as_ascii()`` renders the em-dash sentinel and ``as_dict()`` has no
        entry for that cell.
        """
        metric_order: list[str] = []
        seen: set[str] = set()
        cells: list[tuple[str, str, float]] = []
        for snap, label in zip(snapshots, labels, strict=False):
            metrics = snap.get("metrics", {}) or {}
            for name, payload in metrics.items():
                if name not in seen:
                    seen.add(name)
                    metric_order.append(name)
                value = payload.get("value") if isinstance(payload, dict) else None
                if value is not None:
                    cells.append((name, label, float(value)))
        return cls(metrics=tuple(metric_order), snapshots=tuple(labels), cells=tuple(cells))
