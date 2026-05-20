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

"""Wilson score interval (Story 4.4 / AC-DISCOVER-01).

Closed-form Wilson score interval for proportion confidence. No `scipy`
dependency (Story 4.4 D-C drift resolution; Phase-1.5 may switch to
`scipy.stats.beta.ppf` if precision matters at small N).

Reference: Wilson, E. B. (1927). "Probable inference, the law of
succession, and statistical inference". J. American Statistical Assoc.
"""

from __future__ import annotations

import math

__all__ = ["wilson_score_interval"]


# 95% confidence z-score for the standard normal distribution.
_Z_BY_CONFIDENCE = {
    0.90: 1.6448536269514722,
    0.95: 1.959963984540054,
    0.99: 2.5758293035489004,
}


def wilson_score_interval(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]:
    """Compute the Wilson score interval for a binomial proportion.

    Closed-form (no scipy dependency); supports 90% / 95% / 99% confidence.

    Args:
        successes: Number of successful trials (0 <= successes <= trials).
        trials: Total number of trials (>= 0).
        confidence: Confidence level. Phase-1 supports 0.90, 0.95, 0.99.

    Returns:
        `(lower, upper)` bounds in [0.0, 1.0]. When `trials == 0` the
        interval is `(0.0, 1.0)` (no information). When `confidence` is
        unsupported, raises `ValueError`.
    """
    if trials < 0:
        raise ValueError(f"trials must be >= 0; got {trials}")
    if successes < 0 or successes > trials:
        raise ValueError(f"successes must be in [0, {trials}]; got {successes}")
    if confidence not in _Z_BY_CONFIDENCE:
        raise ValueError(f"confidence must be one of {sorted(_Z_BY_CONFIDENCE)}; got {confidence}")
    if trials == 0:
        return (0.0, 1.0)

    z = _Z_BY_CONFIDENCE[confidence]
    n = float(trials)
    p_hat = successes / n
    z_squared = z * z
    denominator = 1.0 + z_squared / n
    center = (p_hat + z_squared / (2.0 * n)) / denominator
    margin = (z / denominator) * math.sqrt(p_hat * (1.0 - p_hat) / n + z_squared / (4.0 * n * n))
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return (lower, upper)
