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

"""Integration smoke tests for the Phase-2 `[agenteval-advanced]` stats keywords.

Exercises the 3 Story 13.1 keywords through the public `StatsLibrary` surface
that the top-level `AgentEval` library composes via `_SUB_LIBRARIES`. Verifies
each keyword returns the documented type when called with synthetic
`KeywordRun` inputs.
"""

from __future__ import annotations

import statistics

import pytest

from AgentEval.stats.types import KeywordRun, MannWhitneyResult

pytest.importorskip("scipy")
pytest.importorskip("numpy")

from AgentEval.stats.library import StatsLibrary  # noqa: E402


def _make_keyword_run(value: float, *, trial_index: int = 0) -> KeywordRun:
    """Construct a minimal `KeywordRun` carrying `value` in `latency_seconds`."""
    return KeywordRun(
        trial_index=trial_index,
        test_id=f"integration::trial-{trial_index}",
        keyword_name="synthetic",
        result=None,
        error=None,
        completeness="complete",
        latency_seconds=value,
        seed=None,
    )


def test_stat_mann_whitney_u_integration_smoke() -> None:
    """`Stat.Mann Whitney U` end-to-end returns well-typed `MannWhitneyResult`."""
    lib = StatsLibrary()
    runs_a = [_make_keyword_run(v, trial_index=i) for i, v in enumerate([1.0, 2.0, 3.0, 4.0, 5.0])]
    runs_b = [_make_keyword_run(v, trial_index=i) for i, v in enumerate([6.0, 7.0, 8.0, 9.0, 10.0])]
    result = lib.compute_mann_whitney_u(runs_a, runs_b, predicate=lambda r: r.latency_seconds)
    assert isinstance(result, MannWhitneyResult)
    assert result.n_a == 5
    assert result.n_b == 5
    assert 0.0 <= result.p_value <= 1.0
    assert -1.0 <= result.effect_size_r <= 1.0


def test_stat_cliff_delta_integration_smoke() -> None:
    """`Stat.Cliff Delta` end-to-end returns a float in [-1, 1]."""
    lib = StatsLibrary()
    runs_a = [_make_keyword_run(v) for v in [1.0, 2.0, 3.0]]
    runs_b = [_make_keyword_run(v) for v in [10.0, 20.0, 30.0]]
    delta = lib.compute_cliff_delta(runs_a, runs_b, predicate=lambda r: r.latency_seconds)
    assert isinstance(delta, float)
    assert -1.0 <= delta <= 1.0
    # Clearly separated samples_a < samples_b → δ near -1.
    assert delta == -1.0


def test_stat_bootstrap_ci_integration_smoke() -> None:
    """`Stat.Bootstrap CI` end-to-end returns a well-ordered (lo, hi) tuple."""
    lib = StatsLibrary()
    runs = [_make_keyword_run(v) for v in [1.0, 2.0, 3.0, 4.0, 5.0] * 10]
    lo, hi = lib.compute_bootstrap_ci(
        runs,
        statistic=statistics.mean,
        predicate=lambda r: r.latency_seconds,
        n_resamples=500,
        seed=42,
    )
    assert isinstance(lo, float)
    assert isinstance(hi, float)
    assert lo <= hi
    # Sample mean is 3.0; CI should bracket it.
    assert lo <= 3.0 <= hi
