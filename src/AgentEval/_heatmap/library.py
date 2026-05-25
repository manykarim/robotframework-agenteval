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

"""``HeatmapLibrary`` — RF library with ``Get Cohort Heatmap`` keyword (Story 8b.2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from robot.api.deco import keyword, library

from AgentEval._heatmap.models import CohortHeatmap
from AgentEval._kernel.tier import tier

if TYPE_CHECKING:
    from AgentEval.discoverability.schema import DiscoverabilityResult

__all__ = ["HeatmapLibrary"]


@library(scope="GLOBAL")
class HeatmapLibrary:
    """Cohort-heatmap RF library (Story 8b.2 / FR55-ASCII + dict).

    Tier-1 (deterministic projection — no LLM calls).
    """

    @keyword(name="Get Cohort Heatmap")
    @tier(1)
    def get_cohort_heatmap(
        self,
        discoverability_result: DiscoverabilityResult,
        *,
        model_name: str = "default",
    ) -> CohortHeatmap:
        """Build a ``CohortHeatmap`` from a Story 4.4 ``DiscoverabilityResult``.

        [Tier 1 — Deterministic] — pure projection over the result's
        ``per_task_results``; no LLM calls.

        Args:
            discoverability_result: result from ``MCP.Get Tool Discoverability``.
            model_name: column label for the single-model column (Phase-1).

        Returns:
            ``CohortHeatmap`` with ``.as_ascii()`` + ``.as_dict()`` methods.
        """
        return CohortHeatmap.from_discoverability(discoverability_result, model_name=model_name)
