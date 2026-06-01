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

"""Bootstrap confidence interval primitive (PRD FR29c; Story 13.1).

Phase-2 module — requires the `[agenteval-advanced]` extra (scipy + numpy).
Computes a percentile bootstrap CI for any statistic over numeric samples.
Reproducibility via the optional ``seed`` parameter (None → OS entropy).

Math reference: ``scipy.stats.bootstrap`` (method="percentile",
confidence_level=1-alpha). The custom resampler here is implemented directly
for control over the random source — scipy is used for cross-validation in
unit tests.

Phase-1.5/2 carry-overs:
- DF-13.1-S2: CI methods beyond percentile (BCa, BC-corrected). Phase-1 ships
  percentile only.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as _np

__all__ = ["compute_bootstrap_ci"]


def compute_bootstrap_ci(
    samples: list[float],
    statistic: Callable[[list[float]], float],
    alpha: float,
    n_resamples: int,
    seed: int | None,
) -> tuple[float, float]:
    """Compute a percentile bootstrap CI for the given statistic (FR29c).

    Args:
        samples: Non-empty list of numeric samples.
        statistic: Callable mapping a resampled list of floats to a scalar
            statistic (e.g., ``statistics.mean``, ``statistics.median``).
        alpha: Significance level. CI is at ``(1 - alpha) * 100%`` confidence.
            Must satisfy ``0.0 < alpha < 1.0``.
        n_resamples: Number of bootstrap resamples (with replacement). Must be
            ``>= 100`` (lower values produce unstable percentile estimates).
        seed: Optional integer seed for the underlying ``numpy.random.Generator``.
            ``None`` → OS-entropy seeding (non-reproducible).

    Returns:
        ``(ci_lower, ci_upper)`` tuple of floats at the ``(1-alpha) * 100%``
        percentile level.

    Raises:
        ValueError: When ``samples`` is empty, ``alpha`` is out of range, or
            ``n_resamples`` is too small.
    """
    n = len(samples)
    if n < 1:
        raise ValueError(f"samples must be non-empty; got n={n}")
    if not (0.0 < alpha < 1.0):
        raise ValueError(f"alpha must be in (0.0, 1.0); got {alpha!r}")
    if n_resamples < 100:
        raise ValueError(f"n_resamples must be >= 100; got {n_resamples!r}")

    rng = _np.random.default_rng(seed)
    sample_array = _np.asarray(samples, dtype=float)
    # Draw n_resamples bootstrap samples of size n with replacement.
    indices = rng.integers(low=0, high=n, size=(n_resamples, n))
    resampled = sample_array[indices]
    # Apply the statistic to each row. Use a Python loop since `statistic`
    # is an arbitrary Callable[[list[float]], float] (not necessarily
    # numpy-aware).
    stats_values = _np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        stats_values[i] = float(statistic(resampled[i].tolist()))
    lo = float(_np.percentile(stats_values, 100.0 * (alpha / 2.0)))
    hi = float(_np.percentile(stats_values, 100.0 * (1.0 - alpha / 2.0)))
    return (lo, hi)
