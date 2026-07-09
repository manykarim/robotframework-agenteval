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

"""Unit tests: the CI-overlap-aware comparison engine (task 6.3).

The statistical-honesty core — a within-CI drop must PASS with a warning, a
real drop must FAIL, degradation/underpower must be loud.
"""

from __future__ import annotations

import warnings

import pytest

from AgentEval.baseline import comparison as _comparison
from AgentEval.baseline.comparison import compare, parse_tolerance
from AgentEval.baseline.models import (
    ContinuousEvidence,
    MetricsBaseline,
    ProportionEvidence,
    RunContext,
)
from AgentEval.errors import (
    DegradedComparisonWarning,
    PossibleRegressionWarning,
    SkippedMetricWarning,
    UnderpoweredComparisonWarning,
)


def _prop_baseline(name: str, successes: int, trials: int, **rc: object) -> MetricsBaseline:
    value = successes / trials
    return MetricsBaseline(
        schema_version=1,
        metrics={name: ProportionEvidence(successes=successes, trials=trials, value=value, k=None)},
        extra_metrics={},
        run_context=RunContext(**rc),  # type: ignore[arg-type]
    )


def _cont_baseline(name: str, samples: list[float], value: float) -> MetricsBaseline:
    return MetricsBaseline(
        schema_version=1,
        metrics={
            name: ContinuousEvidence(
                samples=tuple(samples),
                value=value,
                total=sum(samples),
                mean=(sum(samples) / len(samples)) if samples else value,
                p50=value,
                p95=value,
            )
        },
        extra_metrics={},
        run_context=RunContext(),
    )


# --- tolerance parsing ----------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("5%", 0.05), ("10%", 0.1), (0.05, 0.05), (5, 0.05), ("0.05", 0.05)],
)
def test_parse_tolerance(raw: object, expected: float) -> None:
    assert parse_tolerance(raw) == pytest.approx(expected)  # type: ignore[arg-type]


# --- proportion rule (Decision 2) ------------------------------------------ #


def test_genuine_regression_fails_with_numeric_message() -> None:
    base = _prop_baseline("pass_rate", 45, 50)
    curr = _prop_baseline("pass_rate", 5, 50)
    report = compare(base, curr, tolerance="5%")
    assert report.regressed
    c = report.comparisons[0]
    assert c.verdict == "fail"
    assert c.comparison_mode == "wilson_ci_disjoint"
    # Numeric bars: both points, both CIs, both Ns, tolerance semantics.
    assert "baseline=0.9" in c.reason
    assert "current=0.1" in c.reason
    assert "N=50" in c.reason
    assert "0.05 absolute" in c.reason


def test_noisy_drop_passes_with_possible_regression_warning() -> None:
    base = _prop_baseline("pass_rate", 9, 10)
    curr = _prop_baseline("pass_rate", 7, 10)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report = compare(base, curr, tolerance="5%")
    assert not report.regressed
    c = report.comparisons[0]
    assert c.verdict == "pass"
    assert c.comparison_mode == "wilson_ci_overlap"
    assert c.warning == "PossibleRegressionWarning"
    msgs = [str(w.message) for w in caught if w.category is PossibleRegressionWarning]
    assert msgs, "expected a PossibleRegressionWarning"
    assert "overlap" in msgs[0]
    assert "N=10" in msgs[0]


def test_within_tolerance_clean_pass() -> None:
    base = _prop_baseline("pass_rate", 90, 100)
    curr = _prop_baseline("pass_rate", 89, 100)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report = compare(base, curr, tolerance="5%")
    assert not report.regressed
    c = report.comparisons[0]
    assert c.verdict == "pass"
    assert c.warning is None
    assert not [w for w in caught if w.category is PossibleRegressionWarning]


def test_improvement_never_fails() -> None:
    base = _prop_baseline("pass_rate", 5, 50)
    curr = _prop_baseline("pass_rate", 45, 50)
    report = compare(base, curr, tolerance="5%")
    assert not report.regressed
    assert report.comparisons[0].verdict == "pass"


def test_underpowered_emits_warning_with_n_estimate() -> None:
    base = _prop_baseline("pass_rate", 9, 10)
    curr = _prop_baseline("pass_rate", 8, 10)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        compare(base, curr, tolerance="5%")
    under = [str(w.message) for w in caught if w.category is UnderpoweredComparisonWarning]
    assert under
    assert "n>=" in under[0]


# --- continuous rule (Decision 3) ------------------------------------------ #


def test_continuous_regression_fails_with_mann_whitney() -> None:
    pytest.importorskip("scipy")
    base = _cont_baseline("latency_p95_ms", [100.0 + i for i in range(20)], value=100.0)
    curr = _cont_baseline("latency_p95_ms", [200.0 + i for i in range(20)], value=200.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        report = compare(base, curr, tolerance="5%")
    c = report.comparisons[0]
    assert c.verdict == "fail"
    assert c.comparison_mode == "mann_whitney"
    assert "latency_p95_ms" in c.metric
    assert "relative" in c.tolerance_semantics


def test_continuous_improvement_passes() -> None:
    pytest.importorskip("scipy")
    base = _cont_baseline("latency_p95_ms", [200.0 + i for i in range(20)], value=200.0)
    curr = _cont_baseline("latency_p95_ms", [100.0 + i for i in range(20)], value=100.0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        report = compare(base, curr, tolerance="5%")
    assert report.comparisons[0].verdict == "pass"


def test_point_only_fallback_emits_degraded_warning_when_advanced_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        _comparison, "_advanced_available", lambda: (False, "the [agenteval-advanced] extra is not installed")
    )
    base = _cont_baseline("cost_usd", [0.10, 0.11, 0.12], value=0.11)
    curr = _cont_baseline("cost_usd", [0.30, 0.31, 0.32], value=0.31)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report = compare(base, curr, tolerance="5%")
    c = report.comparisons[0]
    assert c.comparison_mode == "point_only"
    # Big rise beyond 5% relative tolerance still fails point-only.
    assert c.verdict == "fail"
    degraded = [str(w.message) for w in caught if w.category is DegradedComparisonWarning]
    assert degraded
    assert "advanced" in degraded[0]


def test_point_only_when_samples_missing() -> None:
    # No samples on either side → degraded regardless of advanced availability.
    base = _cont_baseline("cost_usd", [], value=0.10)
    curr = _cont_baseline("cost_usd", [], value=0.30)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report = compare(base, curr, tolerance="5%")
    assert report.comparisons[0].comparison_mode == "point_only"
    assert [w for w in caught if w.category is DegradedComparisonWarning]


# --- asymmetric + context (Decisions 6/7) ---------------------------------- #


def test_metric_missing_on_one_side_is_skipped_not_failed() -> None:
    base = MetricsBaseline(
        schema_version=1,
        metrics={
            "pass_rate": ProportionEvidence(successes=9, trials=10, value=0.9),
            "tool_hit_rate": ProportionEvidence(successes=8, trials=10, value=0.8),
        },
        extra_metrics={},
        run_context=RunContext(),
    )
    curr = _prop_baseline("pass_rate", 9, 10)  # no tool_hit_rate
    report = compare(base, curr, tolerance="5%")
    by_metric = {c.metric: c for c in report.comparisons}
    assert by_metric["tool_hit_rate"].verdict == "skipped"
    assert "baseline" in by_metric["tool_hit_rate"].reason
    assert not report.regressed  # skipped never fails the gate


def test_disappearing_metric_emits_skipped_warning_but_still_passes() -> None:
    # MED-1: baseline has pass_rate + cost_usd; current only produces pass_rate
    # (e.g. results stopped unwrapping to AgentRunResult). The cost gate must NOT
    # silently vanish — the skip is loud via SkippedMetricWarning — yet the
    # keyword still PASSES (never auto-fail on skip).
    base = MetricsBaseline(
        schema_version=1,
        metrics={
            "pass_rate": ProportionEvidence(successes=10, trials=10, value=1.0),
            "cost_usd": ContinuousEvidence(samples=(0.1, 0.1, 0.1), value=0.1, total=0.3, mean=0.1),
        },
        extra_metrics={},
        run_context=RunContext(),
    )
    curr = MetricsBaseline(
        schema_version=1,
        metrics={"pass_rate": ProportionEvidence(successes=10, trials=10, value=1.0)},
        extra_metrics={},
        run_context=RunContext(),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report = compare(base, curr, tolerance="5%")
    assert not report.regressed  # skipped never fails the gate
    by_metric = {c.metric: c for c in report.comparisons}
    assert by_metric["cost_usd"].verdict == "skipped"
    skipped = [str(w.message) for w in caught if w.category is SkippedMetricWarning]
    assert skipped, "expected a SkippedMetricWarning for the disappearing cost_usd metric"
    assert "cost_usd" in skipped[0]
    assert "baseline" in skipped[0]  # names why it was skipped


def test_current_only_metric_emits_skipped_warning() -> None:
    # A metric present only in the current run (not baseline) is also skipped loudly.
    base = _prop_baseline("pass_rate", 9, 10)
    curr = MetricsBaseline(
        schema_version=1,
        metrics={
            "pass_rate": ProportionEvidence(successes=9, trials=10, value=0.9),
            "tool_hit_rate": ProportionEvidence(successes=8, trials=10, value=0.8),
        },
        extra_metrics={},
        run_context=RunContext(),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        compare(base, curr, tolerance="5%")
    skipped = [str(w.message) for w in caught if w.category is SkippedMetricWarning]
    assert any("tool_hit_rate" in m for m in skipped)


def test_evidence_kind_mismatch_emits_skipped_warning() -> None:
    base = MetricsBaseline(
        schema_version=1,
        metrics={"m": ProportionEvidence(successes=9, trials=10, value=0.9)},
        extra_metrics={},
        run_context=RunContext(),
    )
    curr = MetricsBaseline(
        schema_version=1,
        metrics={"m": ContinuousEvidence(samples=(1.0,), value=1.0, total=1.0, mean=1.0)},
        extra_metrics={},
        run_context=RunContext(),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report = compare(base, curr, tolerance="5%")
    assert report.comparisons[0].verdict == "skipped"
    skipped = [str(w.message) for w in caught if w.category is SkippedMetricWarning]
    assert any("evidence kind mismatch" in m for m in skipped)


def test_context_mismatch_reported_not_gated() -> None:
    base = _prop_baseline("pass_rate", 9, 10, model="claude-sonnet-4-6")
    curr = _prop_baseline("pass_rate", 9, 10, model="claude-sonnet-4-7")
    report = compare(base, curr, tolerance="5%")
    assert not report.regressed
    assert report.baseline_context.model == "claude-sonnet-4-6"
    assert report.current_context.model == "claude-sonnet-4-7"


def test_per_metric_tolerance_override() -> None:
    pytest.importorskip("scipy")
    base = _cont_baseline("cost_usd", [0.10] * 10, value=0.10)
    curr = _cont_baseline("cost_usd", [0.108] * 10, value=0.108)  # +8% rise
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # Default 5% would breach; override to 10% → within tolerance.
        report = compare(base, curr, tolerance="5%", tolerances={"cost_usd": "10%"})
    assert report.comparisons[0].verdict == "pass"


def test_extra_metrics_compared_point_only() -> None:
    base = MetricsBaseline(1, {}, {"judge_score": 0.9}, RunContext())
    curr = MetricsBaseline(1, {}, {"judge_score": 0.5}, RunContext())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        report = compare(base, curr, tolerance="5%")
    c = report.comparisons[0]
    assert c.metric == "judge_score"
    assert c.comparison_mode == "point_only"
    assert c.verdict == "fail"  # 0.9 → 0.5 is a big drop, higher_is_better default
