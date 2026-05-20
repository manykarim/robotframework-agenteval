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

"""Metrics-internal helper types (Story 6.1 AC-6.1.5).

Architecture L1292 enumerates the eventual contents as `Usage,
LatencyStats, CohortHeatmap`. Story 6.1 ships `LatencyStats` only —
`Usage` already lives at `AgentEval.types:132` (Story 1b.2) and is
imported from there; `CohortHeatmap` is FR55 / Epic 7+ Discoverability-
cohort scope and is NOT in Story 6.1's surface.

`LatencyStats` is an internal helper dataclass (NOT a keyword return
type — each latency keyword returns a scalar `float` per PRD FR22).
Phase-1 use case: future "give me all latency stats at once" keyword
surfaces (e.g., `Metric.Get Latency Stats` returning the full triple)
can consume this without re-deriving the computation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LatencyStats:
    """Latency aggregate per architecture L1292.

    Fields:
        mean: arithmetic mean of `tc.latency_ms` across the input set (ms).
        p95: 95th percentile via `statistics.quantiles(n=100)[94]` (ms).
        max: maximum `tc.latency_ms` (ms).

    Phase-1 scope: produced by no current keyword; reserved for Phase-2
    "Get Latency Stats" composite keyword + `metrics/_internal.py` test
    fixtures. Stable contract; frozen for immutability.
    """

    mean: float
    p95: float
    max: float
