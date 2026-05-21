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

"""Story 7.4 dogfood fixture helper — stub adapters for Skill Discoverability.

DF-7.4-S1 CONSTRAINT: Stub-based dogfood cannot measure real activation quality.
Each stub always returns a response_text containing the target skill name, making
activated=True for every trial regardless of prompt content. This means:
  - false_activation_rate = 1.0 (decoy tasks always activate — expected)
  - missed_activation_rate = 0.0 (should_activate tasks always activate — vacuous)

Real activation-quality evidence (false-positive discrimination) requires a live
provider run deferred to Epic 9 (DF-7.4-S1 / C60 in deferred-work.md).

The stub pattern mirrors Story 7.3's stub factory for consistency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.discovery import register_adapter
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

_SKILLS_DIR = Path(__file__).parent.parent / "skills"
_DISC_DIR = Path(__file__).parent.parent / "discoverability"

SKILLS_DIR = _SKILLS_DIR
DISCOVERABILITY_DIR = _DISC_DIR

SKILL_PATH_RF_BROWSER = _SKILLS_DIR / "rf-browser-skill.md"
SKILL_PATH_RF_RESULTS = _SKILLS_DIR / "rf-results-skill.md"
SKILL_PATH_RF_LIBDOC_SEARCH = _SKILLS_DIR / "rf-libdoc-search-skill.md"

TASKS_PATH_RF_BROWSER = _DISC_DIR / "rf-browser-tasks.yaml"
TASKS_PATH_RF_RESULTS = _DISC_DIR / "rf-results-tasks.yaml"
TASKS_PATH_RF_LIBDOC_SEARCH = _DISC_DIR / "rf-libdoc-search-tasks.yaml"


def _make_skill_stub(skill_name: str) -> type[InProcessAdapter]:
    """Factory: creates a stub adapter whose response always contains skill_name.

    Activation heuristic (AC-7.1.4): ``skill_name.lower() in response_text.lower()``.
    Embedding the skill name verbatim in response_text guarantees activated=True
    for every trial — intentional for infrastructure validation (DF-7.4-S1).
    """

    class _Stub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text=f"I'll use the {skill_name} skill to help with this request.",
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(
                    completeness="complete",
                    mcp_coverage="hosted_in_process",
                ),
                cost_usd=0.001,
                latency_seconds=0.002,
                trace_id="a" * 32,
            )

    return _Stub


@keyword(name="Register Skill Stubs")
def register_skill_stubs() -> None:
    """Register stub adapters for the 3 dogfood skills. Call once at Suite Setup.

    DF-7.4-S1: stubs always activate; false_activation_rate=1.0 by design.
    """
    register_adapter("stub_rf_browser", _make_skill_stub("rf-browser"))
    register_adapter("stub_rf_results", _make_skill_stub("rf-results"))
    register_adapter("stub_rf_libdoc_search", _make_skill_stub("rf-libdoc-search"))
