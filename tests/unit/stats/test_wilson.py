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

"""Unit tests for `wilson.py` Wilson score interval (Story 6.3 AC-6.3.3)."""

from __future__ import annotations

import pytest

from AgentEval.stats.wilson import _standard_normal_quantile, wilson_score_interval


def test_wilson_zero_trials_returns_uniform() -> None:
    """n=0 → (0.0, 1.0) uniform prior."""
    assert wilson_score_interval(0, 0) == (0.0, 1.0)


def test_wilson_all_success_at_95pct() -> None:
    """10/10 successes at 95% CI: upper bound = 1.0, lower bound around 0.72."""
    lo, hi = wilson_score_interval(10, 10, confidence=0.95)
    assert hi == 1.0
    assert 0.70 < lo < 0.74  # Wilson(1.0, 10, 95%) ≈ 0.7225


def test_wilson_zero_success_at_95pct() -> None:
    """0/10 successes at 95% CI: lower bound = 0.0, upper bound around 0.28."""
    lo, hi = wilson_score_interval(0, 10, confidence=0.95)
    assert lo == 0.0
    assert 0.26 < hi < 0.30  # Wilson(0.0, 10, 95%) ≈ 0.2775


def test_wilson_half_success_at_95pct_centered_around_half() -> None:
    """5/10 successes at 95% CI: interval roughly centered around 0.5."""
    lo, hi = wilson_score_interval(5, 10, confidence=0.95)
    assert 0.0 < lo < 0.5
    assert 0.5 < hi < 1.0


def test_wilson_higher_confidence_is_wider() -> None:
    """99% CI is wider than 95% CI for the same data."""
    lo_95, hi_95 = wilson_score_interval(7, 10, confidence=0.95)
    lo_99, hi_99 = wilson_score_interval(7, 10, confidence=0.99)
    assert lo_99 < lo_95
    assert hi_99 > hi_95


def test_wilson_successes_gt_trials_raises() -> None:
    with pytest.raises(ValueError, match=r"successes must be <= trials"):
        wilson_score_interval(11, 10)


def test_wilson_negative_inputs_raise() -> None:
    with pytest.raises(ValueError, match=r"trials must be >= 0"):
        wilson_score_interval(0, -1)
    with pytest.raises(ValueError, match=r"successes must be >= 0"):
        wilson_score_interval(-1, 10)


def test_wilson_confidence_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match=r"confidence must be in"):
        wilson_score_interval(5, 10, confidence=0.0)
    with pytest.raises(ValueError, match=r"confidence must be in"):
        wilson_score_interval(5, 10, confidence=1.0)
    with pytest.raises(ValueError, match=r"confidence must be in"):
        wilson_score_interval(5, 10, confidence=1.5)


def test_standard_normal_quantile_known_values() -> None:
    """`Φ⁻¹(0.5) = 0`, `Φ⁻¹(0.975) ≈ 1.96`, `Φ⁻¹(0.995) ≈ 2.576`."""
    assert _standard_normal_quantile(0.5) == pytest.approx(0.0, abs=1e-6)
    assert _standard_normal_quantile(0.975) == pytest.approx(1.96, abs=1e-3)
    assert _standard_normal_quantile(0.995) == pytest.approx(2.576, abs=1e-3)


def test_standard_normal_quantile_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match=r"p must be in"):
        _standard_normal_quantile(0.0)
    with pytest.raises(ValueError, match=r"p must be in"):
        _standard_normal_quantile(1.0)
