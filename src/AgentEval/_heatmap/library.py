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

# ruff: noqa: E501
# Browser-Library-style docstring tables can carry long descriptions on a
# single physical line. Per-line 120-char limit waived for this file per
# Phase 5 docstring-refresh proposal (2026-05-26).

"""``HeatmapLibrary`` — RF library with ``Get Cohort Heatmap`` keyword (Story 8b.2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from robot.api.deco import keyword, library

from AgentEval._heatmap.models import CohortHeatmap
from AgentEval._kernel.tier import tier

if TYPE_CHECKING:
    from AgentEval.discoverability.schema import DiscoverabilityResult

__all__ = ["HeatmapLibrary"]

# Browser-Library-style docstring migration marker (Phase 5, 2026-05-26).
_BROWSER_STYLE_MIGRATED = True


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
        """Builds a ``CohortHeatmap`` from a ``DiscoverabilityResult`` (Story 8b.2 / FR55).

        [Tier 1 — Deterministic] — pure projection over the result's
        ``per_task_results``; no LLM calls. Returns a ``CohortHeatmap``
        instance with ``.as_ascii()`` (box-drawing rendered grid) +
        ``.as_dict()`` (nested ``{task: {model: pass_at_k}}`` mapping)
        methods.

        | =Arguments= | =Description= |
        | ``discoverability_result`` | Result from `MCP.Get Tool Discoverability` (Story 4.4 / FR10a). Carries ``per_task_results`` list of per-task ``pass_rate`` values. |
        | ``model_name`` | Column label for the single-model column. Phase-1: single-model heatmaps only. Defaults to ``"default"``. |

        Phase-1 scope: single-model heatmap (one column). Multi-model
        comparison (rows = tasks × columns = models) is Phase-2 work.
        Missing cells render as ``" — "`` sentinel (em-dash with spaces)
        rather than silently substituting ``0.0`` per the Story 10.1
        kilo/minimax review HIGH-1 honesty patch.

        Example:
        | ${task} =    Evaluate    type('R', (), {'task_id': 'task-1', 'pass_rate': 0.5})()
        | ${disc} =    Evaluate    type('D', (), {'per_task_results': [$task]})()
        | ${heatmap} =    `Get Cohort Heatmap`    ${disc}    model_name=claude-sonnet-4-5
        | ${ascii} =    Evaluate    $heatmap.as_ascii()
        | Log    ${ascii}                                                                           # Box-drawing render.
        | ${cells} =    Evaluate    $heatmap.as_dict()
        | Should Not Be Empty    ${cells}

        Notes:
        - Story 8b.2 ratifies the ``CohortHeatmap`` data class + ``Get Cohort Heatmap`` keyword surface.
        - FR55 ratifies ASCII + dict renderers; missing-cell honesty patch per Story 10.1 review (em-dash sentinel).
        - Sibling keyword: `MCP.Get Tool Discoverability` produces the ``DiscoverabilityResult`` input.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return CohortHeatmap.from_discoverability(discoverability_result, model_name=model_name)
