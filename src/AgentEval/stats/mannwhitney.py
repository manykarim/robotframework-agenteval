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

"""Mann-Whitney U statistical primitive (PRD FR29a; Story 13.1).

Phase-2 module — requires the `[agenteval-advanced]` optional extra (scipy +
numpy). Imported lazily by
`AgentEval.stats.library.StatsLibrary.compute_mann_whitney_u` behind an
`_ADVANCED_AVAILABLE` gate; importing this module without scipy installed
raises `ImportError` at the `import scipy.stats` line.

Math reference: ``scipy.stats.mannwhitneyu`` (alternative="two-sided",
use_continuity=False). Effect size: rank-biserial correlation
``r = 2 * U1 / (n_a * n_b) - 1`` (signed convention where U1 is the
Mann-Whitney U for samples_a; positive r → samples_a tends to be larger
than samples_b). This matches the Cliff's delta sign convention shipped
by `Stat.Cliff Delta` (Story 13.1 FR29b).

Phase-1.5/2 carry-overs:
- DF-13.1-S1: one-sided alternatives ("greater"/"less"). Phase-1 ships
  two-sided only.
- DF-13.1-S3: ``MannWhitneyResult.effect_size_interpretation`` Cohen-band
  Literal field. Phase-1 returns the raw ``effect_size_r``.
"""

from __future__ import annotations

import scipy.stats as _scipy_stats

from AgentEval.stats.types import MannWhitneyResult

__all__ = ["compute_mann_whitney_u"]


def compute_mann_whitney_u(
    samples_a: list[float],
    samples_b: list[float],
) -> MannWhitneyResult:
    """Compute the Mann-Whitney U statistic + p-value + effect size (FR29a).

    Args:
        samples_a: First-group numeric samples; must be non-empty.
        samples_b: Second-group numeric samples; must be non-empty.

    Returns:
        ``MannWhitneyResult`` with ``u_statistic`` (the smaller of U1, U2 —
        the canonical smaller-U form), two-sided ``p_value`` (matches
        ``scipy.stats.mannwhitneyu`` default), rank-biserial ``effect_size_r``,
        and the sample sizes ``n_a`` and ``n_b``.

    Raises:
        ValueError: When either samples list is empty.

    Notes:
        - ``scipy.stats.mannwhitneyu(..., alternative="two-sided",
          use_continuity=False).statistic`` returns ``U1`` (the U-statistic
          for ``samples_a``). This implementation NORMALIZES the return to
          ``min(U1, U2)`` — the smaller-U canonical form widely cited in
          literature — and DOES NOT match scipy's ``.statistic`` value
          directly. The ``effect_size_r`` computation still uses ``U1``
          (so the sign carries the directionality of the effect); consumers
          needing scipy's U1 can recover it via
          ``U1 = (1 + effect_size_r) * n_a * n_b / 2``.
        - The two-sided ``p_value`` IS symmetric in U1/U2 and matches scipy
          exactly.
    """
    n_a = len(samples_a)
    n_b = len(samples_b)
    if n_a < 1:
        raise ValueError(f"samples_a must be non-empty; got n_a={n_a}")
    if n_b < 1:
        raise ValueError(f"samples_b must be non-empty; got n_b={n_b}")
    result = _scipy_stats.mannwhitneyu(
        samples_a,
        samples_b,
        alternative="two-sided",
        use_continuity=False,
    )
    u1 = float(result.statistic)
    u2 = float(n_a * n_b - u1)
    u_smaller = min(u1, u2)
    # Signed rank-biserial correlation r = 2 * U1 / (n_a * n_b) - 1. U1 is
    # the count of pairs where samples_a > samples_b (with 0.5 for ties), so:
    #   - U1 = 0 (samples_a strictly < samples_b) → r = -1.0
    #   - U1 = n_a * n_b / 2 (no separation) → r = 0.0
    #   - U1 = n_a * n_b (samples_a strictly > samples_b) → r = +1.0
    # Matches Cliff's delta sign convention shipped by `Stat.Cliff Delta`.
    effect_size_r = 2.0 * u1 / (n_a * n_b) - 1.0
    return MannWhitneyResult(
        u_statistic=u_smaller,
        p_value=float(result.pvalue),
        effect_size_r=effect_size_r,
        n_a=n_a,
        n_b=n_b,
    )
