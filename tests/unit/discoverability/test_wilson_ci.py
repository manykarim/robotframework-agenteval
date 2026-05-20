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

"""Wilson score interval math tests (Story 4.4 / AC-DISCOVER-01)."""

from __future__ import annotations

import math

import pytest

from AgentEval.discoverability.wilson_ci import wilson_score_interval


def test_wilson_ci_zero_trials_returns_full_range() -> None:
    """No-information case: trials=0 → (0.0, 1.0)."""
    lower, upper = wilson_score_interval(successes=0, trials=0)
    assert lower == 0.0
    assert upper == 1.0


def test_wilson_ci_all_success_with_small_n() -> None:
    """3/3 successes — Wilson interval is wide, upper bound = 1.0."""
    lower, upper = wilson_score_interval(successes=3, trials=3)
    assert upper == 1.0
    # Lower bound for 3/3 at 95% confidence ≈ 0.439
    assert 0.4 < lower < 0.5


def test_wilson_ci_zero_success_with_small_n() -> None:
    """0/3 successes — lower bound = 0.0, upper bound is roughly 1-of-low."""
    lower, upper = wilson_score_interval(successes=0, trials=3)
    assert lower == 0.0
    # Upper bound for 0/3 at 95% ≈ 0.561
    assert 0.5 < upper < 0.6


def test_wilson_ci_half_success_centered() -> None:
    """50/100 successes — interval is centered around 0.5 ± ~0.1."""
    lower, upper = wilson_score_interval(successes=50, trials=100)
    assert math.isclose(lower, 0.4038, abs_tol=0.001)
    assert math.isclose(upper, 0.5962, abs_tol=0.001)


def test_wilson_ci_bounds_in_unit_interval() -> None:
    """For any valid input, lower and upper are in [0, 1]."""
    for s, t in [(0, 1), (1, 1), (1, 10), (5, 10), (10, 10), (50, 100), (99, 100)]:
        lower, upper = wilson_score_interval(s, t)
        assert 0.0 <= lower <= upper <= 1.0


def test_wilson_ci_negative_trials_raises() -> None:
    with pytest.raises(ValueError, match="trials"):
        wilson_score_interval(successes=0, trials=-1)


def test_wilson_ci_successes_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match="successes"):
        wilson_score_interval(successes=-1, trials=3)
    with pytest.raises(ValueError, match="successes"):
        wilson_score_interval(successes=4, trials=3)


def test_wilson_ci_unsupported_confidence_raises() -> None:
    with pytest.raises(ValueError, match="confidence"):
        wilson_score_interval(successes=1, trials=3, confidence=0.50)


def test_wilson_ci_90_percent_narrower_than_95() -> None:
    """90% CI should be narrower than 95% CI for the same data."""
    l90, u90 = wilson_score_interval(successes=5, trials=10, confidence=0.90)
    l95, u95 = wilson_score_interval(successes=5, trials=10, confidence=0.95)
    assert (u90 - l90) < (u95 - l95)


def test_wilson_ci_99_percent_wider_than_95() -> None:
    """99% CI should be wider than 95% CI for the same data."""
    l95, u95 = wilson_score_interval(successes=5, trials=10, confidence=0.95)
    l99, u99 = wilson_score_interval(successes=5, trials=10, confidence=0.99)
    assert (u99 - l99) > (u95 - l95)
