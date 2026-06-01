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

"""End-to-end integration test for `Skill.Compare Discoverability` (Story 13.5 AC-13.5.7).

Per Story 13.1 + 13.3 L-4 lesson (empirical correctness verification):
asserts CONCRETE numerical outcomes of the cross-adapter comparison —
known stub activation patterns produce the EXPECTED ranking + p-value
signs + false-activation / missed-activation rate orderings.

3 stubs via `register_adapter()`:
- `skill_compare_stub_a` → activates skill on EVERY trial (100% activation
  on should_activate=True; 100% false-activation on decoys = bad).
  Net activation_accuracy depends on the should/decoy ratio in the YAML.
- `skill_compare_stub_b` → never activates (0% on both).
- `skill_compare_stub_c` → activates with skill-name in response always
  on should_activate=True tasks AND never on decoys → highest accuracy.

Expected outcomes (with 3 should_activate=True + 2 decoy tasks in YAML):
- accuracy(c) > accuracy(a) > accuracy(b) because c is "perfect", a
  always-activates (correct on True, wrong on decoy), b always-misses.
- summary.best_adapter == c; worst_adapter == b.
- 3 pairwise deltas; significance varies by stub.
- heatmap.models has 3 columns + total_cost_usd == 0.0 (epic L2221 zero-cost).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("scipy")
pytest.importorskip("numpy")

from AgentEval._kernel import discovery  # noqa: E402
from AgentEval._kernel.discovery import register_adapter  # noqa: E402
from AgentEval.coding_agent.base import InProcessAdapter  # noqa: E402
from AgentEval.skills.library import SkillsLibrary  # noqa: E402
from AgentEval.skills.types import SkillDiscoverabilityComparisonResult  # noqa: E402
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage  # noqa: E402


@pytest.fixture(autouse=True)
def _restore_adapter_registry() -> Iterator[None]:
    snapshot = dict(discovery._registered_adapters)  # noqa: SLF001
    try:
        yield
    finally:
        discovery._registered_adapters.clear()  # noqa: SLF001
        discovery._registered_adapters.update(snapshot)  # noqa: SLF001


def _make_stub_always_activate(skill_name: str) -> type[InProcessAdapter]:
    """Stub that ALWAYS mentions the skill name in its response (cost=0.0 per epic L2221)."""

    class _Stub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text=f"I'll use {skill_name} for this.",
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.0,
                latency_seconds=0.001,
                trace_id="a" * 32,
            )

    return _Stub


def _make_stub_never_activate() -> type[InProcessAdapter]:
    """Stub that NEVER mentions the skill (cost=0.0)."""

    class _Stub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text="I'll just do this directly.",
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.0,
                latency_seconds=0.001,
                trace_id="a" * 32,
            )

    return _Stub


def _make_stub_perfect_by_prompt(skill_name: str, should_activate_prompts: set[str]) -> type[InProcessAdapter]:
    """Stub that activates ONLY when the prompt matches a should-activate task.

    Encodes the ground truth so it scores 100% activation_accuracy +
    0% false_activation_rate + 0% missed_activation_rate.
    """

    class _Stub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            text = f"I'll use {skill_name}." if prompt in should_activate_prompts else "Doing it directly."
            return AgentRunResult(
                response_text=text,
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.0,
                latency_seconds=0.001,
                trace_id="a" * 32,
            )

    return _Stub


def test_compare_3_stub_adapters_end_to_end_skill() -> None:
    """3-stub Skill cross-adapter comparison produces expected ranking + concrete outcomes."""
    skill_fixture = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
    tasks_fixture = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"

    # Skill name (from frontmatter parsed by the keyword body).
    skill_name = "example-search-skill"

    # Read the tasks YAML to extract the should-activate prompts for the
    # "perfect" stub's prompt-matching logic.
    import yaml

    parsed = yaml.safe_load(tasks_fixture.read_text(encoding="utf-8"))
    should_activate_prompts = {t["prompt"] for t in parsed["tasks"] if t.get("should_activate")}

    register_adapter("skill_compare_stub_a", _make_stub_always_activate(skill_name))
    register_adapter("skill_compare_stub_b", _make_stub_never_activate())
    register_adapter(
        "skill_compare_stub_c",
        _make_stub_perfect_by_prompt(skill_name, should_activate_prompts),
    )

    lib = SkillsLibrary()
    result = lib.get_discoverability_comparison(
        skill=str(skill_fixture),
        tasks=str(tasks_fixture),
        adapters=["skill_compare_stub_a", "skill_compare_stub_b", "skill_compare_stub_c"],
        trials_per_task=3,
    )

    assert isinstance(result, SkillDiscoverabilityComparisonResult)

    accuracies = result.summary.activation_accuracy_per_adapter
    # c is "perfect" → highest accuracy.
    assert accuracies["skill_compare_stub_c"] == pytest.approx(1.0)
    # a always-activates: correct on should_activate=True (3/5), wrong on decoys (2/5).
    assert accuracies["skill_compare_stub_a"] == pytest.approx(3 / 5)
    # b never activates: wrong on should_activate=True (3/5 missed), correct on decoys (2/5).
    assert accuracies["skill_compare_stub_b"] == pytest.approx(2 / 5)

    assert result.summary.best_adapter == "skill_compare_stub_c"
    assert result.summary.worst_adapter == "skill_compare_stub_b"

    # Pairwise deltas keyed.
    assert set(result.cross_adapter_deltas.keys()) == {
        "skill_compare_stub_a_vs_skill_compare_stub_b",
        "skill_compare_stub_a_vs_skill_compare_stub_c",
        "skill_compare_stub_b_vs_skill_compare_stub_c",
    }

    # False-activation deltas: stub_a is worst on decoys (false_activation_rate=1.0),
    # stub_b + stub_c are 0.0. Delta a_vs_c > 0 (a worse).
    delta_a_vs_c = result.cross_adapter_deltas["skill_compare_stub_a_vs_skill_compare_stub_c"]
    assert delta_a_vs_c.false_activation_rate_delta > 0

    # Missed-activation deltas: stub_b is worst (misses all should_activate),
    # stub_c is perfect.
    delta_b_vs_c = result.cross_adapter_deltas["skill_compare_stub_b_vs_skill_compare_stub_c"]
    assert delta_b_vs_c.missed_activation_rate_delta > 0

    # Heatmap.
    assert result.heatmap.models == (
        "skill_compare_stub_a",
        "skill_compare_stub_b",
        "skill_compare_stub_c",
    )

    # Cost: zero per epic L2221 (Story 13.3 Codex MED-1 lesson applied).
    assert result.summary.total_cost_usd == pytest.approx(0.0)

    # Significance assertion per amended AC-13.5.7: `a_vs_b` is the
    # empirically-significant pair (rates_a = [1.0]×5 vs rates_b =
    # [0.0]×5 → Mann-Whitney U = 0, p ≈ 0.008 < 0.05). The original
    # spec promised `a_vs_c` significance but the perfect-by-prompt
    # stub_c yields [1,1,1,0,0] which ties with a's all-ones (U=7.5,
    # not significant at α=0.05 with n=5). Codex MED-2 + Opus LOW-2.
    delta_a_vs_b = result.cross_adapter_deltas["skill_compare_stub_a_vs_skill_compare_stub_b"]
    assert delta_a_vs_b.significant_at_alpha_05 is True
    delta_a_vs_c = result.cross_adapter_deltas["skill_compare_stub_a_vs_skill_compare_stub_c"]
    assert delta_a_vs_c.significant_at_alpha_05 is False


def test_compare_rejects_single_adapter_list() -> None:
    """≥2 adapter requirement enforced at arg validation."""
    register_adapter("only_one_skill", _make_stub_never_activate())
    skill_fixture = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
    tasks_fixture = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"
    lib = SkillsLibrary()
    with pytest.raises(ValueError, match=">= 2 entries"):
        lib.get_discoverability_comparison(
            skill=str(skill_fixture),
            tasks=str(tasks_fixture),
            adapters=["only_one_skill"],
            trials_per_task=1,
        )


def test_compare_rejects_duplicate_adapter_names() -> None:
    """Duplicate adapter names raise ValueError."""
    register_adapter("dup_skill", _make_stub_never_activate())
    skill_fixture = Path(__file__).parent.parent.parent / "fixtures" / "skills" / "example-search.md"
    tasks_fixture = Path(__file__).parent.parent.parent / "fixtures" / "discoverability" / "skill-tasks-basic.yaml"
    lib = SkillsLibrary()
    with pytest.raises(ValueError, match="distinct adapter names"):
        lib.get_discoverability_comparison(
            skill=str(skill_fixture),
            tasks=str(tasks_fixture),
            adapters=["dup_skill", "dup_skill"],
            trials_per_task=1,
        )
