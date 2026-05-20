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

"""Wilson score interval — pure-stdlib Phase-1 implementation (Story 6.3 AC-6.3.3).

Per architecture L1308: Phase-1 ships Wilson CI without SciPy dependency.
Uses `math.sqrt` + a Halley-method approximation of the inverse normal CDF
for the standard-normal quantile (sufficient for the common confidence
levels 0.90 / 0.95 / 0.99). For Phase-2 advanced primitives that need
exact `scipy.stats.norm.ppf`, the `agenteval[advanced]` extra is the
intended landing.
"""

from __future__ import annotations

import math


def _standard_normal_quantile(p: float) -> float:
    """Approximate inverse standard-normal CDF (quantile function).

    Beasley-Springer-Moro algorithm (1974/1995) — accurate to ~1e-9 for
    `p ∈ (0, 1)`. Sufficient for Wilson CI at typical confidence levels.

    Args:
        p: Probability in the open interval `(0, 1)`.

    Returns:
        z such that `Φ(z) = p`, where `Φ` is the standard-normal CDF.

    Raises:
        ValueError: if `p` is not in `(0, 1)`.
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be in (0, 1); got {p!r}")

    # Beasley-Springer-Moro inverse normal CDF approximation.
    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    p_low = 0.02425
    p_high = 1.0 - p_low

    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
            * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        )
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
    )


def wilson_score_interval(
    successes: int,
    trials: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion (PRD FR10a + Story 6.3 AC-6.3.3).

    Closed-form Wilson formula — preferred over normal-approximation for small N
    or extreme proportions. Reference: Wilson (1927) "Probable inference, the
    law of succession, and statistical inference," JASA 22(158): 209-212.

    Args:
        successes: count of trials where the success predicate is True.
        trials: total number of trials.
        confidence: confidence level in `(0, 1)`; default 0.95 (i.e., 95% CI).

    Returns:
        `(ci_lower, ci_upper)` both in `[0, 1]` such that the true success
        proportion lies in the interval with the requested confidence.

    Raises:
        ValueError: if `successes > trials`, `successes < 0`, `trials < 0`,
            or `confidence` not in `(0, 1)`.
    """
    if trials < 0:
        raise ValueError(f"trials must be >= 0; got {trials!r}")
    if successes < 0:
        raise ValueError(f"successes must be >= 0; got {successes!r}")
    if successes > trials:
        raise ValueError(f"successes must be <= trials; got successes={successes!r} trials={trials!r}")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1); got {confidence!r}")

    if trials == 0:
        # Uniform prior on `[0, 1]` — no evidence either way.
        return (0.0, 1.0)

    # Two-sided z critical value at the requested confidence level.
    z = _standard_normal_quantile((1.0 + confidence) / 2.0)
    n = float(trials)
    p_hat = successes / n
    denom = 1.0 + (z * z) / n
    center = (p_hat + (z * z) / (2.0 * n)) / denom
    margin = (z * math.sqrt(p_hat * (1.0 - p_hat) / n + (z * z) / (4.0 * n * n))) / denom
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return (lower, upper)
