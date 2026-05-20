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
            convenience (default predicate matches `completeness == "full"`).
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
