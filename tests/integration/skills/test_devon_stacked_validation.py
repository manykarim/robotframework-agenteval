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

"""Story 7.3: Devon's Stacked Validation Recipe integration test.

Devon's three-tier validation pattern (Journey 4):

  Tier 1 — Static (deterministic):
      Skill.Get Frontmatter + Skill.Should Be Valid Frontmatter  (Story 2.1)

  Tier 2 — Judge (LLM, Phase 2):
      # TODO Phase 2: Judge.Get Score here  (Epic 12 Story 12.3)

  Tier 3 — Cohort (stochastic fan-out):
      Skill.Get Discoverability (10 trials/task)  (Story 7.2)
      Skill.Should Activate For spot-check         (Story 7.2)

  Stat.* composition (Story 6.3):
      Stat.Run N Times + Skill.Get Activation Decision + Stat.Get Pass At K

CRITICAL — D-1 drift (DF-7.3-S1/C59):
    Stat.Get Pass At K default predicate checks `r.completeness == "complete"`.
    Skill.Get Activation Decision returns ActivationDecision (no metadata.completeness)
    → _extract_completeness() returns "n/a" → default predicate always False.
    MUST use custom predicate: lambda r: r.result.activated
    Empirically verified 2026-05-21.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from AgentEval._kernel.discovery import register_adapter
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.skills.library import SkillsLibrary
from AgentEval.skills.types import ActivationDecision
from AgentEval.stats.library import StatsLibrary
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
SKILL_PATH = FIXTURES_DIR / "skills" / "example-search.md"
TASKS_PATH = FIXTURES_DIR / "discoverability" / "skill-tasks-basic.yaml"
SKILL_NAME = "example-search-skill"
ADAPTER_NAME = "devon_integration_stub"

RECIPE_PATH = Path(__file__).resolve().parents[3] / "docs" / "recipes" / "04-skill-author-stacked-validation.md"

REPRESENTATIVE_PROMPTS = [
    "Search for Python tutorials on the web",
    "Find information about robotframework-agenteval",
]


def _make_stub() -> type[InProcessAdapter]:
    """Stub adapter: response always contains skill name → activated=True."""

    class _Stub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text=f"I activated the {SKILL_NAME} skill for this search request.",
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.001,
                latency_seconds=0.002,
                trace_id="a" * 32,
            )

    return _Stub


@pytest.fixture(autouse=True, scope="module")
def _register_stub() -> None:
    """Register the Devon stub adapter once per module (idempotent)."""
    register_adapter(ADAPTER_NAME, _make_stub())


@pytest.fixture
def skills() -> SkillsLibrary:
    return SkillsLibrary()


@pytest.fixture
def stats() -> StatsLibrary:
    return StatsLibrary()


class TestDevonStackedValidation:
    """Devon's stacked validation pattern: Tier-1 + Tier-3 + Stat.* composition."""

    def test_tier1_frontmatter_validation(self, skills: SkillsLibrary) -> None:
        """Tier-1 static: frontmatter is present and valid for example-search.md."""
        fm = skills.get_frontmatter(SKILL_PATH)
        skills.should_be_valid_frontmatter(fm)
        assert fm["name"] == SKILL_NAME

    def test_tier3_cohort_discoverability(self, skills: SkillsLibrary) -> None:
        """Tier-3 cohort: should-activate tasks reach pass_at_k >= 0.8 across 10 trials."""
        result = skills.get_discoverability(
            SKILL_PATH,
            TASKS_PATH,
            adapter=ADAPTER_NAME,
            trials_per_task=10,
        )
        for task_result in result.per_task_results:
            if task_result.should_activate:
                assert task_result.pass_at_k >= 0.8, (
                    f"Task '{task_result.task_id}' pass_at_k={task_result.pass_at_k:.3f} < 0.8 "
                    f"({task_result.activations_observed}/{task_result.trials_run} activations)"
                )

    def test_stat_run_n_times_with_activation_decision(self, skills: SkillsLibrary, stats: StatsLibrary) -> None:
        """Stat.* composition: Run N Times → custom predicate → Pass@5 >= 0.8.

        NOTE (DF-7.3-S1/C59): Must use custom predicate because ActivationDecision
        has no metadata.completeness → r.completeness == "n/a" → default predicate
        always False → Pass@k = 0.0 with default. Use r.result.activated instead.
        # TODO Phase 2: Judge.Get Score here — replace predicate with Judge score threshold
        """
        runs = stats.run_n_times(
            n=10,
            keyword=skills.get_activation_decision,
            keyword_args={
                "skill": str(SKILL_PATH),
                "prompt": REPRESENTATIVE_PROMPTS[0],
                "adapter": ADAPTER_NAME,
            },
        )
        assert len(runs) == 10
        pass_at_5 = stats.get_pass_at_k(
            runs=runs,
            k=5,
            predicate=lambda r: isinstance(r.result, ActivationDecision) and r.result.activated,
        )
        assert pass_at_5 >= 0.8

    def test_skill_should_activate_for_spot_check(self, skills: SkillsLibrary) -> None:
        """Tier-2/3 spot-check: Skill.Should Activate For returns None for representative prompts."""
        for prompt in REPRESENTATIVE_PROMPTS:
            result = skills.should_activate_for(prompt, SKILL_PATH, adapter=ADAPTER_NAME)
            assert result is None

    def test_recipe_stub_exists_with_phase2_placeholder(self) -> None:
        """Recipe stub at docs/recipes/04-skill-author-stacked-validation.md exists
        and contains the Phase-2 Judge placeholder (AC-7.3.6 + AC-7.3.7)."""
        assert RECIPE_PATH.exists(), (
            f"Recipe stub missing: {RECIPE_PATH}\nCreate it per Story 7.3 AC-7.3.6 (stub draft, Epic 8b polishes it)."
        )
        content = RECIPE_PATH.read_text()
        assert "TODO Phase 2: Judge.Get Score" in content, (
            "Recipe must contain Phase-2 Judge slot: '# TODO Phase 2: Judge.Get Score here'"
        )
