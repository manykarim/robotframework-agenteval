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

"""Unit tests for `Skill.Get Activation Decision` (Story 7.1).

Covers AC-7.1.1 through AC-7.1.7 (14 tests):
  - AC-7.1.1: ActivationDecision dataclass shape
  - AC-7.1.2: keyword registered on SkillsLibrary
  - AC-7.1.3: @tier(3) + @guarded_fanout() decoration
  - AC-7.1.4: activated inference via skill name in response_text (case-insensitive)
  - AC-7.1.4 edge: null name in YAML → activated=False (not str(None) = "None")
  - AC-7.1.5: polling= raises PollingDisallowedError (FR28)
  - AC-7.1.6: __agenteval_test_budget__ sentinel consumed by @guarded_fanout()
  - AC-7.1.7: 14 unit tests (exceeds minimum of 10; includes AC item 7 + 10)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from AgentEval._kernel.discovery import register_adapter
from AgentEval._kernel.tier import get_keyword_tier
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.errors import AdapterDiscoveryError, InvalidSkillFrontmatterError, PollingDisallowedError
from AgentEval.skills.library import SkillsLibrary
from AgentEval.skills.types import ActivationDecision
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "skills"
VALID_FIXTURE = FIXTURES_DIR / "example-valid.md"
# example-valid.md has `name: example-valid-skill`
SKILL_NAME = "example-valid-skill"


def _make_stub(response_text: str, cost: float = 0.001, latency: float = 0.002) -> type[InProcessAdapter]:
    """Build a one-shot stub adapter returning a scripted AgentRunResult."""

    class _Stub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text=response_text,
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=cost,
                latency_seconds=latency,
                trace_id="a" * 32,
            )

    return _Stub


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


# --------------------------------------------------------------------------- #
# AC-7.1.1: ActivationDecision dataclass                                      #
# --------------------------------------------------------------------------- #


def test_activation_decision_is_frozen_dataclass() -> None:
    """ActivationDecision is a frozen dataclass with the 4 required fields."""
    ad = ActivationDecision(activated=True, reasoning="response", cost_usd=0.01, latency_seconds=0.5)
    assert ad.activated is True
    assert ad.reasoning == "response"
    assert ad.cost_usd == 0.01
    assert ad.latency_seconds == 0.5
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        ad.activated = False  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# AC-7.1.2: keyword present on SkillsLibrary                                 #
# --------------------------------------------------------------------------- #


def test_get_activation_decision_returns_activation_decision_type(lib: SkillsLibrary) -> None:
    """Happy path: returns an ActivationDecision instance."""
    stub = _make_stub(response_text=f"I activated the {SKILL_NAME} skill.")
    register_adapter("stub_act_happy", stub)
    result = lib.get_activation_decision(VALID_FIXTURE, "Does the skill activate?", adapter="stub_act_happy")
    assert isinstance(result, ActivationDecision)


# --------------------------------------------------------------------------- #
# AC-7.1.3: @tier(3) annotation                                               #
# --------------------------------------------------------------------------- #


def test_get_activation_decision_has_tier_3_annotation(lib: SkillsLibrary) -> None:
    """@tier(3) is present — get_keyword_tier traverses wrappers to find it."""
    assert get_keyword_tier(lib.get_activation_decision) == 3


# --------------------------------------------------------------------------- #
# AC-7.1.4: activated inference via skill name in response_text               #
# --------------------------------------------------------------------------- #


def test_activated_true_when_skill_name_in_response(lib: SkillsLibrary) -> None:
    """activated=True when skill name appears verbatim in response_text."""
    stub = _make_stub(response_text=f"The {SKILL_NAME} skill was chosen.")
    register_adapter("stub_act_true", stub)
    result = lib.get_activation_decision(VALID_FIXTURE, "prompt", adapter="stub_act_true")
    assert result.activated is True


def test_activated_false_when_skill_name_not_in_response(lib: SkillsLibrary) -> None:
    """activated=False when skill name is absent from response_text."""
    stub = _make_stub(response_text="I used a completely different skill instead.")
    register_adapter("stub_act_false", stub)
    result = lib.get_activation_decision(VALID_FIXTURE, "prompt", adapter="stub_act_false")
    assert result.activated is False


def test_case_insensitive_activation_match(lib: SkillsLibrary) -> None:
    """Activation check is case-insensitive (AC-7.1.4 Phase-1 heuristic)."""
    # SKILL_NAME is "example-valid-skill"; response has uppercased version.
    stub = _make_stub(response_text="EXAMPLE-VALID-SKILL was triggered.")
    register_adapter("stub_act_case", stub)
    result = lib.get_activation_decision(VALID_FIXTURE, "prompt", adapter="stub_act_case")
    assert result.activated is True


def test_null_skill_name_in_yaml_gives_activated_false(lib: SkillsLibrary, tmp_path: Path) -> None:
    """name: null in YAML must yield activated=False (HIGH-1 fix: not str(None)='None').

    Without the isinstance guard, str(None)='None' → bool('None')=True, so any
    response containing the word 'none' would spuriously activate. The fix uses
    `name_raw if isinstance(name_raw, str) else ''` so null/missing → ''.
    """
    skill_file = tmp_path / "null-name.md"
    skill_file.write_text(
        "---\n"
        "name: null\n"
        "description: A skill with null name.\n"
        "allowed-tools: []\n"
        "disable-model-invocation: false\n"
        "---\n\n# body\n"
    )
    stub = _make_stub(response_text="I found none of the expected tools.")
    register_adapter("stub_act_null_name", stub)
    result = lib.get_activation_decision(skill_file, "prompt", adapter="stub_act_null_name")
    assert result.activated is False


def test_empty_skill_name_gives_activated_false(lib: SkillsLibrary, tmp_path: Path) -> None:
    """When skill frontmatter has name='', activated=False regardless of response."""
    skill_file = tmp_path / "empty-name.md"
    skill_file.write_text(
        "---\n"
        'name: ""\n'
        "description: A skill with an empty name.\n"
        "allowed-tools: []\n"
        "disable-model-invocation: false\n"
        "---\n\n# body\n"
    )
    stub = _make_stub(response_text="anything at all — name is empty so no match possible")
    register_adapter("stub_act_empty_name", stub)
    result = lib.get_activation_decision(skill_file, "prompt", adapter="stub_act_empty_name")
    assert result.activated is False


# --------------------------------------------------------------------------- #
# AC-7.1.5: polling= raises PollingDisallowedError (FR28)                    #
# --------------------------------------------------------------------------- #


def test_polling_raises_polling_disallowed_error(lib: SkillsLibrary) -> None:
    """Passing polling= raises PollingDisallowedError before any adapter call."""
    with pytest.raises(PollingDisallowedError, match="PollingDisallowedError"):
        lib.get_activation_decision(VALID_FIXTURE, "prompt", polling=1.0)


# --------------------------------------------------------------------------- #
# AC-7.1.6: __agenteval_test_budget__ sentinel consumed by @guarded_fanout() #
# --------------------------------------------------------------------------- #


def test_guarded_fanout_sentinel_not_leaked_to_adapter(lib: SkillsLibrary) -> None:
    """__agenteval_test_budget__ is consumed by @guarded_fanout() and does not
    reach the adapter constructor's kwargs.
    """
    captured: dict[str, Any] = {}

    class _CapturingStub(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            captured.update(self._adapter_config)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return AgentRunResult(
                response_text="no-match",
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.001,
                latency_seconds=0.001,
                trace_id="b" * 32,
            )

    register_adapter("stub_act_sentinel", _CapturingStub)
    result = lib.get_activation_decision(
        VALID_FIXTURE,
        "prompt",
        adapter="stub_act_sentinel",
        __agenteval_test_budget__=(10.0, 60.0),
    )
    assert isinstance(result, ActivationDecision)
    assert "__agenteval_test_budget__" not in captured


# --------------------------------------------------------------------------- #
# AC-7.1.2 / result fidelity: cost and latency forwarded from adapter         #
# --------------------------------------------------------------------------- #


def test_result_carries_cost_and_latency_from_adapter(lib: SkillsLibrary) -> None:
    """cost_usd and latency_seconds in ActivationDecision come from adapter result."""
    stub = _make_stub(response_text="no-match", cost=0.042, latency=1.23)
    register_adapter("stub_act_metrics", stub)
    result = lib.get_activation_decision(VALID_FIXTURE, "prompt", adapter="stub_act_metrics")
    assert abs(result.cost_usd - 0.042) < 1e-9
    assert abs(result.latency_seconds - 1.23) < 1e-9


def test_result_reasoning_equals_response_text(lib: SkillsLibrary) -> None:
    """reasoning field equals the adapter's full response_text."""
    expected = "The agent responded with some text here."
    stub = _make_stub(response_text=expected)
    register_adapter("stub_act_reasoning", stub)
    result = lib.get_activation_decision(VALID_FIXTURE, "prompt", adapter="stub_act_reasoning")
    assert result.reasoning == expected


# --------------------------------------------------------------------------- #
# AC-7.1.10: invalid skill path raises InvalidSkillFrontmatterError           #
# --------------------------------------------------------------------------- #


def test_invalid_skill_path_raises(lib: SkillsLibrary) -> None:
    """Providing a non-existent path raises InvalidSkillFrontmatterError."""
    with pytest.raises(InvalidSkillFrontmatterError):
        lib.get_activation_decision("/does/not/exist.md", "prompt")


# --------------------------------------------------------------------------- #
# AC-7.1.7 item 10: model kwarg forwarded to adapter ctor                     #
# --------------------------------------------------------------------------- #


def test_model_kwarg_forwarded_to_adapter_ctor(lib: SkillsLibrary) -> None:
    """model= kwarg is added to ctor_kwargs and forwarded to the adapter constructor.

    Verifies that `model=` is NOT silently dropped and does NOT appear in
    the `run()` kwargs (it belongs to the constructor, not the run call).
    """
    ctor_kwargs_seen: dict[str, Any] = {}
    run_kwargs_seen: dict[str, Any] = {}

    class _KwargsCapture(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            ctor_kwargs_seen.update(self._adapter_config)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            run_kwargs_seen.update(kwargs)
            return AgentRunResult(
                response_text="no-match",
                tool_calls=[],
                usage=Usage(input_tokens=1, output_tokens=1),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.001,
                latency_seconds=0.001,
                trace_id="c" * 32,
            )

    register_adapter("stub_act_model_forward", _KwargsCapture)
    lib.get_activation_decision(
        VALID_FIXTURE,
        "prompt",
        adapter="stub_act_model_forward",
        model="anthropic/claude-sonnet-4-6",
    )
    assert ctor_kwargs_seen.get("model") == "anthropic/claude-sonnet-4-6"
    assert "model" not in run_kwargs_seen


# --------------------------------------------------------------------------- #
# AC-7.1.7 item 7: unknown adapter raises AdapterDiscoveryError               #
# --------------------------------------------------------------------------- #


def test_unknown_adapter_raises_adapter_discovery_error(lib: SkillsLibrary) -> None:
    """adapter= that is not registered raises AdapterDiscoveryError."""
    with pytest.raises(AdapterDiscoveryError):
        lib.get_activation_decision(VALID_FIXTURE, "prompt", adapter="__nonexistent_7_1__")
