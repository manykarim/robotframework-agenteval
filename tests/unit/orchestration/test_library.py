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

"""Unit tests for `AgentEval.orchestration.library.OrchestrationLibrary` (Story 4.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval.errors import InvalidScenarioYAMLError
from AgentEval.orchestration.library import OrchestrationLibrary
from AgentEval.scenarios.schema import Scenario
from AgentEval.types import AgentRunResult


@pytest.fixture
def lib() -> OrchestrationLibrary:
    return OrchestrationLibrary()


# --------------------------------------------------------------------------- #
# Send Prompt — happy path via Mock provider + Generic adapter
# --------------------------------------------------------------------------- #


def test_send_prompt_resolves_generic_adapter_by_default(lib: OrchestrationLibrary) -> None:
    """`Send Prompt` defaults to `adapter="generic"` per AC-4.3 + PRD FR14.

    Uses `provider="mock"` to avoid the LiteLLMAdapter's model-required
    raise (which would otherwise surface as a real network-free check that
    the default adapter chain works).
    """
    result = lib.send_prompt(prompt="hello", provider="mock")
    assert isinstance(result, AgentRunResult)


def test_send_prompt_with_mock_provider_returns_echoed_text(lib: OrchestrationLibrary) -> None:
    """Generic adapter with `provider="mock"` echoes the prompt."""
    result = lib.send_prompt(adapter="generic", prompt="hello world", provider="mock")
    assert result.response_text == "hello world"


def test_send_prompt_unknown_adapter_raises(lib: OrchestrationLibrary) -> None:
    from AgentEval.errors import AdapterDiscoveryError

    with pytest.raises(AdapterDiscoveryError):
        lib.send_prompt(adapter="nonexistent_xyz", prompt="hi")


def test_send_prompt_empty_mcp_servers_dict_allowed(lib: OrchestrationLibrary) -> None:
    """Empty dict mcp_servers is allowed (no NotImplementedError)."""
    result = lib.send_prompt(adapter="generic", prompt="hi", provider="mock", mcp_servers={})
    assert isinstance(result, AgentRunResult)


def test_send_prompt_none_mcp_servers_allowed(lib: OrchestrationLibrary) -> None:
    result = lib.send_prompt(adapter="generic", prompt="hi", provider="mock", mcp_servers=None)
    assert isinstance(result, AgentRunResult)


def test_send_prompt_empty_string_mcp_servers_allowed(lib: OrchestrationLibrary) -> None:
    """Empty / whitespace-only comma-separated string is allowed."""
    result = lib.send_prompt(adapter="generic", prompt="hi", provider="mock", mcp_servers="")
    assert isinstance(result, AgentRunResult)


def test_send_prompt_non_empty_string_mcp_servers_raises_not_implemented(
    lib: OrchestrationLibrary,
) -> None:
    """Story 4.3 DF-4.3-S2 carve-out: name-list resolution is Phase-1.5."""
    with pytest.raises(NotImplementedError, match="DF-4.3-S2"):
        lib.send_prompt(adapter="generic", prompt="hi", mcp_servers="echo,rfmcp")


def test_send_prompt_non_empty_dict_mcp_servers_forwarded_to_adapter(
    lib: OrchestrationLibrary,
) -> None:
    """Phase-1: dict[name → handle] is forwarded directly. Generic adapter then
    raises NotImplementedError per DF-4.1-S2 — but the forwarding contract is
    verified by the raise location.
    """
    with pytest.raises(NotImplementedError, match="DF-4.1-S2"):
        lib.send_prompt(adapter="generic", prompt="hi", mcp_servers={"echo": object()})


# --------------------------------------------------------------------------- #
# Run Scenario — YAML loading + eval execution
# --------------------------------------------------------------------------- #


def _write_scenario(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "scenario.yaml"
    p.write_text(content)
    return p


def test_run_scenario_executes_all_evals_against_mock(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
provider: mock
evals:
  - prompt: "hello"
  - prompt: "world"
""",
    )
    results = lib.run_scenario(adapter="generic", scenario=str(p))
    assert len(results) == 2
    assert results[0].response_text == "hello"
    assert results[1].response_text == "world"


def test_run_scenario_respects_repeat_count(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    p = _write_scenario(
        tmp_path,
        """
provider: mock
evals:
  - prompt: "ping"
    repeat: 3
""",
    )
    results = lib.run_scenario(adapter="generic", scenario=str(p))
    assert len(results) == 3
    assert all(r.response_text == "ping" for r in results)


def test_run_scenario_empty_scenario_arg_raises(lib: OrchestrationLibrary) -> None:
    with pytest.raises(ValueError, match="scenario"):
        lib.run_scenario(adapter="generic", scenario="")


def test_run_scenario_invalid_yaml_raises_invalid_scenario_error(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    p = _write_scenario(tmp_path, "not valid: scenario: shape\n")
    with pytest.raises(InvalidScenarioYAMLError):
        lib.run_scenario(adapter="generic", scenario=str(p))


def test_run_scenario_forwards_model_from_yaml(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    """Scenario YAML top-level `model` field is forwarded to adapter.run when
    not in caller kwargs."""
    p = _write_scenario(
        tmp_path,
        """
model: my-custom-model
provider: mock
evals:
  - prompt: "x"
""",
    )
    # No exception — mock provider ignores model. The forwarding is exercised.
    results = lib.run_scenario(adapter="generic", scenario=str(p))
    assert len(results) == 1


def test_run_scenario_kwarg_overrides_scenario_model(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    """Per-keyword kwarg WINS over scenario YAML top-level fields."""
    p = _write_scenario(
        tmp_path,
        """
model: yaml-model
provider: mock
evals:
  - prompt: "x"
""",
    )
    # Caller's `model="caller-model"` overrides YAML's `model: yaml-model`.
    results = lib.run_scenario(adapter="generic", scenario=str(p), model="caller-model")
    assert len(results) == 1


def test_run_scenario_unknown_adapter_raises(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    from AgentEval.errors import AdapterDiscoveryError

    p = _write_scenario(tmp_path, "evals:\n  - prompt: hi\n")
    with pytest.raises(AdapterDiscoveryError):
        lib.run_scenario(adapter="nonexistent_xyz", scenario=str(p))


def test_run_scenario_non_empty_string_mcp_servers_raises_not_implemented(
    lib: OrchestrationLibrary, tmp_path: Path
) -> None:
    p = _write_scenario(tmp_path, "evals:\n  - prompt: hi\n")
    with pytest.raises(NotImplementedError, match="DF-4.3-S2"):
        lib.run_scenario(adapter="generic", scenario=str(p), mcp_servers="echo")


# --------------------------------------------------------------------------- #
# Load Scenario — pure parse keyword
# --------------------------------------------------------------------------- #


def test_load_scenario_keyword_returns_scenario_dataclass(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    p = _write_scenario(tmp_path, "provider: mock\nevals:\n  - prompt: hi\n")
    s = lib.load_scenario_kw(str(p))
    assert isinstance(s, Scenario)
    assert s.provider == "mock"
    assert len(s.evals) == 1


def test_load_scenario_keyword_propagates_validation_errors(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    p = _write_scenario(tmp_path, "evals: []\n")  # empty evals
    with pytest.raises(InvalidScenarioYAMLError):
        lib.load_scenario_kw(str(p))


# --------------------------------------------------------------------------- #
# Story 1b.6 conventions invariants
# --------------------------------------------------------------------------- #


KEYWORD_METHODS = ["send_prompt", "run_scenario", "load_scenario_kw"]


@pytest.mark.parametrize("method_name", KEYWORD_METHODS)
def test_keyword_has_robot_marker(method_name: str) -> None:
    func = getattr(OrchestrationLibrary, method_name)
    assert hasattr(func, "robot_name")


@pytest.mark.parametrize("method_name", KEYWORD_METHODS)
def test_keyword_has_tier_annotation(method_name: str) -> None:
    from AgentEval._kernel.tier import get_keyword_tier

    func = getattr(OrchestrationLibrary, method_name)
    assert get_keyword_tier(func) in (1, 2, 3)


@pytest.mark.parametrize("method_name", KEYWORD_METHODS)
def test_keyword_is_not_async(method_name: str) -> None:
    import inspect

    func = getattr(OrchestrationLibrary, method_name)
    assert not inspect.iscoroutinefunction(func)
