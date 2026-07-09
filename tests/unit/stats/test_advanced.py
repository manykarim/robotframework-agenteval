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

"""Unit tests for the Phase-2 `[agenteval-advanced]` stats keywords (Story 13.1).

Math correctness tested against scipy reference implementations
(``scipy.stats.mannwhitneyu`` + ``scipy.stats.bootstrap``). Cliff's delta
has no direct scipy equivalent — verified against the closed-form
``δ = (#a>b - #a<b) / (n_a * n_b)`` directly.

ImportError gate (Phase-1 baseline compat without the extra) exercised via
monkeypatch + module reload so the test runs in both the WITH-extras and
WITHOUT-extras CI environments.
"""

from __future__ import annotations

import statistics

import pytest

from AgentEval.stats.types import KeywordRun, MannWhitneyResult

# Phase-2 modules require scipy + numpy. Skip the math + happy-path tests when
# the extra is not installed (ImportError-gate tests still run via monkeypatch).
_scipy = pytest.importorskip("scipy")
_scipy_stats = pytest.importorskip("scipy.stats")
_numpy = pytest.importorskip("numpy")

from AgentEval.stats import bootstrap as _bootstrap  # noqa: E402
from AgentEval.stats import cliffs_delta as _cliffs_delta  # noqa: E402
from AgentEval.stats import mannwhitney as _mannwhitney  # noqa: E402
from AgentEval.stats.library import StatsLibrary  # noqa: E402


def _make_run(value: float, *, trial_index: int = 0) -> KeywordRun:
    """Build a minimal KeywordRun whose `latency_seconds` carries the test value."""
    return KeywordRun(
        trial_index=trial_index,
        test_id=f"test::trial-{trial_index}",
        keyword_name="fake",
        result=None,
        error=None,
        completeness="complete",
        latency_seconds=value,
        seed=None,
    )


# --------------------------------------------------------------------------- #
# MannWhitneyResult dataclass validation (3 tests)                            #
# --------------------------------------------------------------------------- #


def test_mannwhitney_result_in_range_fields_accepted() -> None:
    """Valid fields construct without raising."""
    r = MannWhitneyResult(u_statistic=10.0, p_value=0.05, effect_size_r=0.3, n_a=5, n_b=5)
    assert r.u_statistic == 10.0
    assert r.p_value == 0.05
    assert r.effect_size_r == 0.3


def test_mannwhitney_result_effect_size_out_of_range_raises() -> None:
    """effect_size_r outside [-1.0, 1.0] raises ValueError."""
    with pytest.raises(ValueError, match="effect_size_r"):
        MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=1.5, n_a=5, n_b=5)
    with pytest.raises(ValueError, match="effect_size_r"):
        MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=-1.5, n_a=5, n_b=5)


def test_mannwhitney_result_p_value_out_of_range_raises() -> None:
    """p_value outside [0.0, 1.0] raises ValueError."""
    with pytest.raises(ValueError, match="p_value"):
        MannWhitneyResult(u_statistic=0.0, p_value=1.1, effect_size_r=0.0, n_a=5, n_b=5)


def test_mannwhitney_result_n_below_one_raises() -> None:
    """n_a or n_b < 1 raises ValueError."""
    with pytest.raises(ValueError, match="n_a"):
        MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=0.0, n_a=0, n_b=5)
    with pytest.raises(ValueError, match="n_b"):
        MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=0.0, n_a=5, n_b=0)


def test_mannwhitney_result_is_frozen() -> None:
    """Mutation raises FrozenInstanceError (dataclass(frozen=True))."""
    r = MannWhitneyResult(u_statistic=0.0, p_value=0.5, effect_size_r=0.0, n_a=5, n_b=5)
    with pytest.raises(AttributeError):
        r.u_statistic = 99.0  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Mann-Whitney U math (4 tests)                                               #
# --------------------------------------------------------------------------- #


def test_mannwhitney_identical_samples_p_value_near_one() -> None:
    """Identical samples → high p-value (cannot reject null) + effect_size_r≈0."""
    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
    r = _mannwhitney.compute_mann_whitney_u(samples, samples)
    assert r.p_value > 0.8
    assert abs(r.effect_size_r) < 0.01
    assert r.n_a == 5
    assert r.n_b == 5


def test_mannwhitney_clearly_separated_samples_p_value_small() -> None:
    """Clearly disjoint samples → p < 0.05 + |effect_size_r| near 1."""
    samples_a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    samples_b = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0]
    r = _mannwhitney.compute_mann_whitney_u(samples_a, samples_b)
    assert r.p_value < 0.05
    # samples_a < samples_b → r near -1 (positive r means a tends to be larger)
    assert r.effect_size_r < -0.9


def test_mannwhitney_minimal_samples_n_equals_one() -> None:
    """n_a=1 or n_b=1 still computes (scipy permits)."""
    r = _mannwhitney.compute_mann_whitney_u([1.0], [5.0, 6.0, 7.0])
    assert r.n_a == 1
    assert r.n_b == 3
    assert 0.0 <= r.p_value <= 1.0


def test_mannwhitney_empty_samples_raises() -> None:
    """Empty samples list raises ValueError."""
    with pytest.raises(ValueError, match="samples_a"):
        _mannwhitney.compute_mann_whitney_u([], [1.0, 2.0])
    with pytest.raises(ValueError, match="samples_b"):
        _mannwhitney.compute_mann_whitney_u([1.0, 2.0], [])


# --------------------------------------------------------------------------- #
# Mann-Whitney U vs scipy reference (3 tests)                                 #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("seed,n", [(42, 10), (123, 30), (7, 100)])
def test_mannwhitney_matches_scipy_reference(seed: int, n: int) -> None:
    """3 seeded sample pairs (n=10/30/100) match scipy reference for u_statistic + p_value + effect_size_r within 1e-9."""
    rng = _numpy.random.default_rng(seed)
    a = rng.normal(loc=0.0, scale=1.0, size=n).tolist()
    b = rng.normal(loc=0.5, scale=1.0, size=n).tolist()

    ours = _mannwhitney.compute_mann_whitney_u(a, b)
    ref = _scipy_stats.mannwhitneyu(a, b, alternative="two-sided", use_continuity=False)

    u1 = float(ref.statistic)  # scipy returns U1 (corresponds to samples_a).
    u2 = float(n * n - u1)
    expected_u_smaller = min(u1, u2)

    # u_statistic: normalized smaller-U form.
    assert abs(ours.u_statistic - expected_u_smaller) < 1e-9
    # p_value: matches scipy exactly.
    assert abs(ours.p_value - float(ref.pvalue)) < 1e-9
    # effect_size_r: signed rank-biserial r = 2*U1/(n_a*n_b) - 1.
    expected_r = 2.0 * u1 / (n * n) - 1.0
    assert abs(ours.effect_size_r - expected_r) < 1e-9


def test_bootstrap_ci_matches_scipy_reference() -> None:
    """Percentile bootstrap CI equals `scipy.stats.bootstrap(..., method='percentile', rng=default_rng(seed))` exactly.

    This is the FR29c-mandated math-reference test. Per Story 13.1 code-review
    Codex HIGH-4: prior tests only verified broad invariants (bracketing,
    reproducibility, width); this test asserts bit-equivalence vs scipy.
    """
    rng = _numpy.random.default_rng(42)
    samples = rng.normal(loc=10.0, scale=2.0, size=200).tolist()
    seed = 42

    ours_lo, ours_hi = _bootstrap.compute_bootstrap_ci(
        samples, statistic=statistics.mean, alpha=0.05, n_resamples=500, seed=seed
    )
    ref = _scipy_stats.bootstrap(
        (samples,),
        statistic=lambda data: float(_numpy.mean(data)),
        n_resamples=500,
        confidence_level=0.95,
        method="percentile",
        rng=_numpy.random.default_rng(seed),
        vectorized=False,
    )
    ref_lo = float(ref.confidence_interval.low)
    ref_hi = float(ref.confidence_interval.high)
    # scipy's bootstrap walks the rng identically to our local resampler when
    # given the same default_rng(seed) + vectorized=False + statistic
    # consumes the same flat array. Bit-equivalence to within float32 noise.
    assert abs(ours_lo - ref_lo) < 1e-6
    assert abs(ours_hi - ref_hi) < 1e-6


# --------------------------------------------------------------------------- #
# Cliff Delta math (5 tests)                                                  #
# --------------------------------------------------------------------------- #


def test_cliff_delta_identical_samples_near_zero() -> None:
    """Identical samples → δ ≈ 0 (all comparisons are ties or symmetric)."""
    samples = [1.0, 2.0, 3.0, 4.0, 5.0]
    delta = _cliffs_delta.compute_cliff_delta(samples, samples)
    assert abs(delta) < 0.01


def test_cliff_delta_strict_dominance_a_over_b_equals_one() -> None:
    """All samples_a > all samples_b → δ = 1.0."""
    delta = _cliffs_delta.compute_cliff_delta([10.0, 20.0, 30.0], [1.0, 2.0, 3.0])
    assert delta == 1.0


def test_cliff_delta_reverse_dominance_equals_neg_one() -> None:
    """All samples_a < all samples_b → δ = -1.0."""
    delta = _cliffs_delta.compute_cliff_delta([1.0, 2.0, 3.0], [10.0, 20.0, 30.0])
    assert delta == -1.0


def test_cliff_delta_small_overlap_small_magnitude() -> None:
    """Substantial overlap → |δ| < 0.5."""
    samples_a = [1.0, 2.0, 3.0, 4.0, 5.0]
    samples_b = [2.0, 3.0, 4.0, 5.0, 6.0]
    delta = _cliffs_delta.compute_cliff_delta(samples_a, samples_b)
    assert abs(delta) < 0.5


def test_cliff_delta_large_separation_large_magnitude() -> None:
    """Mostly-disjoint samples → |δ| > 0.7."""
    samples_a = [1.0, 2.0, 3.0, 4.0, 5.0]
    samples_b = [6.0, 7.0, 8.0, 9.0, 10.0]
    delta = _cliffs_delta.compute_cliff_delta(samples_a, samples_b)
    assert abs(delta) > 0.9


# --------------------------------------------------------------------------- #
# Bootstrap CI math (5 tests)                                                 #
# --------------------------------------------------------------------------- #


def test_bootstrap_ci_known_distribution_brackets_truth() -> None:
    """Uniform [0,1] n=1000 mean → CI brackets 0.5."""
    rng = _numpy.random.default_rng(42)
    samples = rng.uniform(0.0, 1.0, size=1000).tolist()
    lo, hi = _bootstrap.compute_bootstrap_ci(samples, statistic=statistics.mean, alpha=0.05, n_resamples=1000, seed=42)
    assert lo <= 0.5 <= hi
    # CI is reasonably tight for n=1000 (theoretical half-width ≈ 1.96 * 0.289/sqrt(1000) ≈ 0.018).
    assert (hi - lo) < 0.1


def test_bootstrap_ci_seed_reproducibility() -> None:
    """seed=42 → identical CI across 2 invocations."""
    samples = [1.0, 2.0, 3.0, 4.0, 5.0] * 20
    lo1, hi1 = _bootstrap.compute_bootstrap_ci(samples, statistic=statistics.mean, alpha=0.05, n_resamples=500, seed=42)
    lo2, hi2 = _bootstrap.compute_bootstrap_ci(samples, statistic=statistics.mean, alpha=0.05, n_resamples=500, seed=42)
    assert lo1 == lo2
    assert hi1 == hi2


def test_bootstrap_ci_alpha_0_01_wider_than_0_05() -> None:
    """alpha=0.01 (99% CI) wider than alpha=0.05 (95% CI)."""
    rng = _numpy.random.default_rng(42)
    samples = rng.normal(loc=10.0, scale=2.0, size=100).tolist()
    lo95, hi95 = _bootstrap.compute_bootstrap_ci(
        samples, statistic=statistics.mean, alpha=0.05, n_resamples=1000, seed=42
    )
    lo99, hi99 = _bootstrap.compute_bootstrap_ci(
        samples, statistic=statistics.mean, alpha=0.01, n_resamples=1000, seed=42
    )
    assert (hi99 - lo99) > (hi95 - lo95)


def test_bootstrap_ci_invalid_alpha_raises() -> None:
    """alpha outside (0,1) raises ValueError."""
    with pytest.raises(ValueError, match="alpha"):
        _bootstrap.compute_bootstrap_ci([1.0, 2.0], statistics.mean, 0.0, 1000, 42)
    with pytest.raises(ValueError, match="alpha"):
        _bootstrap.compute_bootstrap_ci([1.0, 2.0], statistics.mean, 1.5, 1000, 42)


def test_bootstrap_ci_empty_samples_raises() -> None:
    """Empty samples list raises ValueError."""
    with pytest.raises(ValueError, match="samples"):
        _bootstrap.compute_bootstrap_ci([], statistics.mean, 0.05, 1000, 42)


def test_bootstrap_ci_too_few_resamples_raises() -> None:
    """n_resamples < 100 raises ValueError."""
    with pytest.raises(ValueError, match="n_resamples"):
        _bootstrap.compute_bootstrap_ci([1.0, 2.0, 3.0], statistics.mean, 0.05, 50, 42)


# --------------------------------------------------------------------------- #
# Predicate value-extraction at the keyword surface (2 tests)                 #
# --------------------------------------------------------------------------- #


def test_mannwhitney_keyword_predicate_extracts_from_keyword_run() -> None:
    """predicate=lambda r: r.latency_seconds extracts correctly."""
    lib = StatsLibrary()
    runs_a = [_make_run(v, trial_index=i) for i, v in enumerate([1.0, 2.0, 3.0, 4.0, 5.0])]
    runs_b = [_make_run(v, trial_index=i) for i, v in enumerate([10.0, 11.0, 12.0, 13.0, 14.0])]
    result = lib.compute_mann_whitney_u(runs_a, runs_b, predicate=lambda r: r.latency_seconds)
    assert isinstance(result, MannWhitneyResult)
    assert result.n_a == 5
    assert result.n_b == 5
    assert result.p_value < 0.05  # Clearly separated.


def test_mannwhitney_keyword_predicate_none_raises_value_error() -> None:
    """predicate=None on Mann-Whitney U raises ValueError."""
    lib = StatsLibrary()
    runs = [_make_run(v) for v in [1.0, 2.0, 3.0]]
    with pytest.raises(ValueError, match="predicate is required"):
        lib.compute_mann_whitney_u(runs, runs, predicate=None)


def test_cliff_delta_keyword_predicate_none_raises_value_error() -> None:
    """predicate=None on Cliff Delta raises ValueError."""
    lib = StatsLibrary()
    runs = [_make_run(v) for v in [1.0, 2.0, 3.0]]
    with pytest.raises(ValueError, match="predicate is required"):
        lib.compute_cliff_delta(runs, runs, predicate=None)


def test_bootstrap_keyword_predicate_required_for_keyword_run_input() -> None:
    """Bootstrap CI with list[KeywordRun] input + predicate=None raises."""
    lib = StatsLibrary()
    runs = [_make_run(v) for v in [1.0, 2.0, 3.0, 4.0, 5.0]]
    with pytest.raises(ValueError, match="predicate is required"):
        lib.compute_bootstrap_ci(runs, statistic=statistics.mean, n_resamples=200, seed=42)


def test_bootstrap_keyword_mixed_type_samples_raises_type_error() -> None:
    """Bootstrap CI rejects mixed-type samples (KeywordRun + float) per Codex MED-1 catch.

    Pre-fix the code silently filtered the mismatched type via isinstance
    filtering, producing wrong CIs (e.g. `[KeywordRun(1.0), 2.0, 3.0]` returned
    `(1.0, 1.0)` from the 1-element residual). Now raises TypeError up-front.
    """
    lib = StatsLibrary()
    mixed = [_make_run(1.0), 2.0, 3.0]
    with pytest.raises(TypeError, match="homogeneous"):
        lib.compute_bootstrap_ci(
            mixed,  # type: ignore[arg-type]
            seed=42,
            predicate=lambda r: r.latency_seconds,
            n_resamples=200,
        )
    mixed2 = [1.0, 2.0, _make_run(3.0)]
    with pytest.raises(TypeError, match="homogeneous"):
        lib.compute_bootstrap_ci(
            mixed2,  # type: ignore[arg-type]
            seed=42,
            n_resamples=200,
        )


def test_bootstrap_keyword_raw_floats_input_works() -> None:
    """Bootstrap CI accepts raw list[float] without a predicate."""
    lib = StatsLibrary()
    lo, hi = lib.compute_bootstrap_ci(
        [1.0, 2.0, 3.0, 4.0, 5.0] * 10,
        statistic=statistics.mean,
        n_resamples=500,
        seed=42,
    )
    assert lo <= hi


# ImportError-gate tests moved to `test_advanced_extras_gate.py` per Story 13.1
# code-review Codex HIGH-1 catch (top-level `importorskip("scipy")` would skip
# the gate-coverage tests in the WITHOUT-extras CI environment where they
# matter most).
