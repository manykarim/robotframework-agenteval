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

"""Cliff's delta non-parametric effect-size primitive (PRD FR29b; Story 13.1).

Phase-2 module — gated by the `[agenteval-advanced]` extra for parity with
the other 2 Story 13.1 modules. The closed-form brute-force computation
(Cliff 1993) is pure-Python and does NOT strictly require scipy/numpy, but
this module imports numpy unconditionally so the keyword surface presents a
unified ``ImportError`` story across all 3 Phase-2 keywords.

Math: ``δ = (#{i,j : a_i > b_j} - #{i,j : a_i < b_j}) / (n_a * n_b)``.
Range: ``[-1.0, 1.0]``; sign convention matches scipy's effect-size
direction (positive = samples_a tends to be larger).

Complexity: O(n_a * n_b). Fine for typical n ≤ 100 trials per group; for
n_a + n_b > 1000 a Phase-2 algorithm-improvement carve-out applies.

Phase-1.5/2 carry-overs: none specific to Cliff's delta (DF-13.1-S* covers
the broader Phase-2 stats surface).
"""

from __future__ import annotations

import numpy as _np  # noqa: F401  # Unified [agenteval-advanced] gate parity.

__all__ = ["compute_cliff_delta"]


def compute_cliff_delta(samples_a: list[float], samples_b: list[float]) -> float:
    """Compute Cliff's delta non-parametric effect size (FR29b).

    Args:
        samples_a: First-group numeric samples; must be non-empty.
        samples_b: Second-group numeric samples; must be non-empty.

    Returns:
        ``float ∈ [-1.0, 1.0]``. Positive values indicate ``samples_a`` tends
        to be larger; negative values indicate ``samples_b`` tends to be
        larger. Magnitude near 0 indicates substantial overlap.

    Raises:
        ValueError: When either samples list is empty.

    Notes:
        Closed-form Cliff (1993) brute-force formula. Pure-Python loop is
        clearest; numpy vectorization is a Phase-2 perf optimization carve-out.
    """
    n_a = len(samples_a)
    n_b = len(samples_b)
    if n_a < 1:
        raise ValueError(f"samples_a must be non-empty; got n_a={n_a}")
    if n_b < 1:
        raise ValueError(f"samples_b must be non-empty; got n_b={n_b}")
    greater = 0
    less = 0
    for a in samples_a:
        for b in samples_b:
            if a > b:
                greater += 1
            elif a < b:
                less += 1
            # ties (a == b) contribute 0 per Cliff 1993.
    return (greater - less) / (n_a * n_b)
