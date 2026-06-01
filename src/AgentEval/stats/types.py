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

"""Statistical primitives — public types (Story 6.3 AC-6.3.2).

`KeywordRun` is the PRD FR26 verbatim return-type element for
`Stat.Run N Times` (per `docs/contracts/determinism-contract.md:55`
ratified by Story 1b.6 Codex STAR catch: `KeywordRun`, NOT
`AgentRunResult`). Each trial of a Tier-3 fan-out produces one
`KeywordRun`; `Stat.Get Pass At K` consumes `list[KeywordRun]` and
applies a predicate to compute the unbiased Pass@k estimate per FR27.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MannWhitneyResult:
    """Mann-Whitney U test result (PRD FR29a; Story 13.1).

    Returned by `Stat.Mann Whitney U` (Phase-2, behind the
    `[agenteval-advanced]` extra). Reports the test statistic, two-sided
    p-value, rank-biserial effect size, and sample sizes.

    Fields:
        u_statistic: The smaller of U1, U2 (the canonical smaller-U form
            widely cited in literature). NOTE: ``scipy.stats.mannwhitneyu``
            with ``alternative="two-sided"`` returns ``U1`` (not the
            smaller); this dataclass normalizes to ``min(U1, U2)``. The
            two-sided ``p_value`` IS symmetric in U1/U2 and matches scipy.
        p_value: Two-sided p-value.
        effect_size_r: Signed rank-biserial correlation
            ``r = 2 * U1 / (n_a * n_b) - 1`` where U1 is the Mann-Whitney
            U for the FIRST sample. Range: ``[-1.0, 1.0]``. Sign convention:
            positive r → samples_a tends to be larger; negative r → samples_b
            tends to be larger; r ≈ 0 → substantial overlap. Matches Cliff's
            delta sign convention shipped by ``Stat.Cliff Delta`` (FR29b).
        n_a: Number of samples in the first group (after predicate extraction).
        n_b: Number of samples in the second group (after predicate extraction).

    Validation (``__post_init__``): ``n_a >= 1``, ``n_b >= 1``,
    ``-1.0 <= effect_size_r <= 1.0``, ``0.0 <= p_value <= 1.0`` —
    all raise ``ValueError`` on violation.
    """

    u_statistic: float
    p_value: float
    effect_size_r: float
    n_a: int
    n_b: int

    def __post_init__(self) -> None:
        import math

        if self.n_a < 1:
            raise ValueError(f"n_a must be >= 1; got {self.n_a!r}")
        if self.n_b < 1:
            raise ValueError(f"n_b must be >= 1; got {self.n_b!r}")
        if not (-1.0 <= self.effect_size_r <= 1.0):
            raise ValueError(f"effect_size_r must be in [-1.0, 1.0]; got {self.effect_size_r!r}")
        # `p_value=nan` is the scipy convention when both samples have
        # identical rank distributions (no variance → no test possible).
        # Permit nan + the [0, 1] range; reject anything else.
        if not (math.isnan(self.p_value) or 0.0 <= self.p_value <= 1.0):
            raise ValueError(
                f"p_value must be in [0.0, 1.0] or nan (scipy identical-samples convention); "
                f"got {self.p_value!r}"
            )


@dataclass(frozen=True, slots=True)
class KeywordRun:
    """Single-trial result from `Stat.Run N Times` (PRD FR26).

    Fields:
        trial_index: 0-indexed trial number within the parent `Stat.Run N Times` call.
        test_id: ContextVar-bound sub-scope id, formatted as
            `{parent_test_id}::trial-{trial_index}` (per Story 4.3 ContextVar precedent).
        keyword_name: RF name of the wrapped keyword (e.g., `Send Prompt`).
        result: Raw return value from the wrapped keyword (commonly an
            `AgentRunResult`, but any return type is preserved).
        error: Exception instance if the trial raised; `None` on success.
            Trial-level errors bubble up to the caller; this field is for
            post-mortem analysis when callers wrap in `Run Keyword And Ignore Error`.
        completeness: Mirrors `result.metadata.completeness` if `result` is an
            `AgentRunResult`; otherwise `"n/a"`. Operator-facing pass-predicate
            convenience (default predicate matches `completeness == "complete"`
            — amended 2026-05-26 per kilo/minimax cross-LLM review FINDING-1;
            pre-Story-6.4 docstring incorrectly cited `"full"`, but the
            `AgentRunMetadata._VALID_COMPLETENESS` literal set is
            `{"complete", "truncated", "partial"}` and Story 6.4 fix-NOW at
            `stats/_internal.py:250` flipped the default predicate to match).
        latency_seconds: Wall-clock duration for this single trial.
        seed: The `int` seed value forwarded to the trial (or `None` if
            OS-entropy seeding was requested).
    """

    trial_index: int
    test_id: str
    keyword_name: str
    result: Any
    error: BaseException | None
    completeness: str
    latency_seconds: float
    seed: int | None
