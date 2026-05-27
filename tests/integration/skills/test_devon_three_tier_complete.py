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

"""Story 12.3: Devon's Three-Tier Stacked Validation — completes Devon's Journey 4.

Builds on Story 7.3's Tier-1 + Tier-3 integration test
(`test_devon_stacked_validation.py`) by plugging in `Judge.Get Score` as the
Tier-2 layer:

  Tier 1 — Static (deterministic):
      Skill.Get Frontmatter + Skill.Should Be Valid Frontmatter  (Story 2.1)

  Tier 2 — Judge (LLM-deterministic at seed+temperature=0):
      Send Prompt → Judge.Get Score against `skill-quality.md` rubric  (Story 12.1)

  Tier 3 — Cohort (stochastic fan-out):
      Skill.Get Discoverability (10 trials/task)  (Story 7.2)

Two stub adapters via `register_adapter()` so the test has zero real-LLM cost:
- `devon_three_tier_agent_stub` — synthesizes the agent's AgentRunResult.
- `devon_three_tier_judge_stub_passing` / `_failing` — return JSON-formatted
  JudgeScore payloads above / below the rubric threshold (7.0) respectively.

Re-derives `JudgeScore.pass_threshold_met` from the parsed rubric rather than
trusting the stub's stated boolean (Story 12.2 review lesson UPSTREAM —
`recommended_threshold` reachability + invariant-not-trusted pattern).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from AgentEval._kernel.discovery import register_adapter
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.judge.library import JudgeLibrary
from AgentEval.judge.rubric import load_rubric
from AgentEval.judge.types import JudgeScore
from AgentEval.skills.library import SkillsLibrary
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
SKILL_PATH = FIXTURES_DIR / "skills" / "example-search.md"
TASKS_PATH = FIXTURES_DIR / "discoverability" / "skill-tasks-basic.yaml"
RUBRIC_PATH = FIXTURES_DIR / "rubrics" / "skill-quality.md"
SKILL_NAME = "example-search-skill"

AGENT_ADAPTER = "devon_three_tier_agent_stub"
JUDGE_ADAPTER_PASSING = "devon_three_tier_judge_stub_passing"
JUDGE_ADAPTER_FAILING = "devon_three_tier_judge_stub_failing"

REPRESENTATIVE_PROMPT = "Search for Python tutorials on the web"


def _make_agent_stub() -> type[InProcessAdapter]:
    """Stub agent: response embeds the skill name (always activates)."""

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
                trace_id="agent-stub-trace",
            )

    return _Stub


def _make_judge_stub(numeric_score: float) -> type[InProcessAdapter]:
    """Stub judge: returns a JSON-formatted JudgeScore payload with the given score."""

    class _Stub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            payload = {
                "numeric_score": numeric_score,
                "reasoning": (f"Stub judge score {numeric_score} for Devon's three-tier integration test."),
                "criteria_breakdown": {
                    "correctness": numeric_score,
                    "completeness": numeric_score,
                    "tool-use-appropriateness": numeric_score,
                    "response-clarity": numeric_score,
                },
            }
            return AgentRunResult(
                response_text=json.dumps(payload),
                tool_calls=[],
                usage=Usage(input_tokens=200, output_tokens=80),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.005,
                latency_seconds=1.0,
                trace_id="judge-stub-trace",
            )

    return _Stub


@pytest.fixture(autouse=True, scope="module")
def _register_stubs() -> None:
    """Register all three stubs once per module (idempotent)."""
    register_adapter(AGENT_ADAPTER, _make_agent_stub())
    register_adapter(JUDGE_ADAPTER_PASSING, _make_judge_stub(numeric_score=8.5))
    register_adapter(JUDGE_ADAPTER_FAILING, _make_judge_stub(numeric_score=4.0))


@pytest.fixture
def skills() -> SkillsLibrary:
    return SkillsLibrary()


@pytest.fixture
def judge() -> JudgeLibrary:
    return JudgeLibrary()


@pytest.fixture
def agent_run() -> AgentRunResult:
    """Run the agent stub once + return its AgentRunResult for judge input.

    Resolves the agent stub via `get_adapter(AGENT_ADAPTER)` to use the
    registered class (per the project's adapter-registration idiom), rather
    than calling `_make_agent_stub()` directly to instantiate an unregistered
    class. Per Story 12.3 Sonnet LOW-1 review — keeps the fixture consistent
    with how Tier-3 cohort runs resolve the same adapter via `adapter=AGENT_ADAPTER`.
    """
    from AgentEval._kernel.discovery import get_adapter

    adapter_cls = get_adapter(AGENT_ADAPTER)
    return adapter_cls().run(REPRESENTATIVE_PROMPT)


class TestDevonThreeTierComplete:
    """Devon's Journey 4 — full three-tier stacked validation."""

    def test_tier1_frontmatter_validation(self, skills: SkillsLibrary) -> None:
        """Tier-1 static: frontmatter is present and valid for example-search.md."""
        fm = skills.get_frontmatter(SKILL_PATH)
        skills.should_be_valid_frontmatter(fm)
        assert fm["name"] == SKILL_NAME

    def test_tier2_judge_get_score_passes_against_stub(self, judge: JudgeLibrary, agent_run: AgentRunResult) -> None:
        """Tier-2 Judge: stub judge returns numeric_score=8.5 → pass_threshold_met=True
        (re-derived from parsed rubric; not trusted blindly).

        Includes `judge_model`/`temperature`/`seed` to mirror the
        recipe's documented `seed + temperature=0` determinism invocation
        (the stub adapter ignores these kwargs but the example must
        match the documented signature per Story 12.3 Opus MED-1 review).
        """
        score = judge.get_score(
            result=agent_run,
            rubric=RUBRIC_PATH,
            judge_adapter=JUDGE_ADAPTER_PASSING,
            judge_model="anthropic/claude-sonnet-4-6",
            temperature=0.0,
            seed=42,
        )
        assert isinstance(score, JudgeScore)
        # Re-derive the invariant from the parsed rubric — Story 12.2 lesson:
        # don't trust the stub's stated boolean; compute it independently.
        rubric = load_rubric(RUBRIC_PATH)
        expected_pass = score.numeric_score >= rubric.threshold
        assert score.pass_threshold_met is expected_pass
        assert score.pass_threshold_met is True
        assert score.numeric_score == 8.5

    def test_tier3_cohort_discoverability(self, skills: SkillsLibrary) -> None:
        """Tier-3 cohort: should-activate tasks reach pass_at_k >= 0.8 across 10 trials."""
        result = skills.get_discoverability(
            SKILL_PATH,
            TASKS_PATH,
            adapter=AGENT_ADAPTER,
            trials_per_task=10,
        )
        for task_result in result.per_task_results:
            if task_result.should_activate:
                assert task_result.pass_at_k >= 0.8, (
                    f"Task '{task_result.task_id}' pass_at_k={task_result.pass_at_k:.3f} < 0.8"
                )

    def test_three_tiers_combined_coherent_pass(
        self, skills: SkillsLibrary, judge: JudgeLibrary, agent_run: AgentRunResult
    ) -> None:
        """Composite assertion: Tier-1 valid + Tier-2 passes + Tier-3 above pass_at_k floor.

        This is the end-to-end Devon's Journey 4 flow — Phase-2 complete.
        """
        # Tier 1
        fm = skills.get_frontmatter(SKILL_PATH)
        skills.should_be_valid_frontmatter(fm)
        tier1_ok = fm.get("name") == SKILL_NAME

        # Tier 2 — passing stub
        score = judge.get_score(
            result=agent_run,
            rubric=RUBRIC_PATH,
            judge_adapter=JUDGE_ADAPTER_PASSING,
        )
        tier2_ok = score.pass_threshold_met

        # Tier 3
        cohort = skills.get_discoverability(SKILL_PATH, TASKS_PATH, adapter=AGENT_ADAPTER, trials_per_task=10)
        tier3_ok = all(task.pass_at_k >= 0.8 for task in cohort.per_task_results if task.should_activate)

        assert tier1_ok and tier2_ok and tier3_ok, (
            f"Three-tier composite assertion failed: tier1={tier1_ok}, tier2={tier2_ok}, tier3={tier3_ok}"
        )

    def test_three_tiers_combined_coherent_fail_when_tier2_fails(
        self, skills: SkillsLibrary, judge: JudgeLibrary, agent_run: AgentRunResult
    ) -> None:
        """Composite assertion: Tier-1 + Tier-3 pass but Tier-2 stub returns
        numeric_score=4.0 (below rubric threshold 7.0) → composite fails coherently.

        Per epics.md L2133: "the test asserts a coherent pass/fail across all 3 tiers."
        """
        # Tier 1 still passes
        fm = skills.get_frontmatter(SKILL_PATH)
        skills.should_be_valid_frontmatter(fm)
        tier1_ok = fm.get("name") == SKILL_NAME

        # Tier 2 — FAILING stub
        score = judge.get_score(
            result=agent_run,
            rubric=RUBRIC_PATH,
            judge_adapter=JUDGE_ADAPTER_FAILING,
        )
        tier2_ok = score.pass_threshold_met

        # Tier 3 still passes (stub always activates)
        cohort = skills.get_discoverability(SKILL_PATH, TASKS_PATH, adapter=AGENT_ADAPTER, trials_per_task=10)
        tier3_ok = all(task.pass_at_k >= 0.8 for task in cohort.per_task_results if task.should_activate)

        # Composite must fail because Tier-2 fails
        composite = tier1_ok and tier2_ok and tier3_ok
        assert composite is False
        # And it must fail FOR THE RIGHT REASON — Tier-2, not Tier-1 or Tier-3.
        assert tier1_ok is True
        assert tier2_ok is False
        assert tier3_ok is True
        assert score.numeric_score == 4.0
        rubric = load_rubric(RUBRIC_PATH)
        assert score.numeric_score < rubric.threshold
