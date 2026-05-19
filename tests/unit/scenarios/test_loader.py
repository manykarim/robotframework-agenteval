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

"""Unit tests for `AgentEval.scenarios.loader.load_scenario` (Story 4.3 / PRD FR15)."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval.errors import InvalidScenarioYAMLError
from AgentEval.scenarios.loader import load_scenario
from AgentEval.scenarios.schema import Scenario, ScenarioEval


def _write_yaml(tmp_path: Path, content: str, name: str = "scenario.yaml") -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


def test_load_scenario_minimal_evals_only(tmp_path: Path) -> None:
    p = _write_yaml(
        tmp_path,
        """
evals:
  - prompt: "say hi"
""",
    )
    s = load_scenario(p)
    assert isinstance(s, Scenario)
    assert len(s.evals) == 1
    assert s.evals[0].prompt == "say hi"
    assert s.evals[0].repeat == 1
    assert s.model is None
    assert s.provider is None
    assert s.agent is None
    assert s.mcp_servers == []


def test_load_scenario_full_shape(tmp_path: Path) -> None:
    p = _write_yaml(
        tmp_path,
        """
model: anthropic/claude-sonnet-4-6
provider: litellm
agent: generic
mcp_servers:
  - echo
  - rfmcp
evals:
  - prompt: "search for X"
    repeat: 3
    expect:
      tool_call_count: 1
  - prompt: "summarize Y"
    repeat: 1
    expect: {}
    judge:
      model: anthropic/claude-haiku
""",
    )
    s = load_scenario(p)
    assert s.model == "anthropic/claude-sonnet-4-6"
    assert s.provider == "litellm"
    assert s.agent == "generic"
    assert s.mcp_servers == ["echo", "rfmcp"]
    assert len(s.evals) == 2
    assert s.evals[0].repeat == 3
    assert s.evals[0].expect == {"tool_call_count": 1}
    assert s.evals[1].judge == {"model": "anthropic/claude-haiku"}


def test_load_scenario_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(InvalidScenarioYAMLError, match="not found"):
        load_scenario(tmp_path / "missing.yaml")


def test_load_scenario_wrong_extension(tmp_path: Path) -> None:
    p = tmp_path / "scenario.txt"
    p.write_text("evals:\n  - prompt: hi\n")
    with pytest.raises(InvalidScenarioYAMLError, match="extension"):
        load_scenario(p)


def test_load_scenario_malformed_yaml(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals:\n  - prompt: 'unclosed quote\n")
    with pytest.raises(InvalidScenarioYAMLError, match="malformed YAML"):
        load_scenario(p)


def test_load_scenario_non_mapping_top_level(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "- just a list\n")
    with pytest.raises(InvalidScenarioYAMLError, match="top-level must be a mapping"):
        load_scenario(p)


def test_load_scenario_missing_evals(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "model: x\n")
    with pytest.raises(InvalidScenarioYAMLError) as exc_info:
        load_scenario(p)
    assert exc_info.value.field_name == "/evals"


def test_load_scenario_evals_not_list(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals: not_a_list\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be a list"):
        load_scenario(p)


def test_load_scenario_empty_evals(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals: []\n")
    with pytest.raises(InvalidScenarioYAMLError, match="empty"):
        load_scenario(p)


def test_load_scenario_eval_missing_prompt(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals:\n  - repeat: 2\n")
    with pytest.raises(InvalidScenarioYAMLError) as exc_info:
        load_scenario(p)
    assert exc_info.value.field_name == "/evals/0/prompt"


def test_load_scenario_eval_non_string_prompt(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals:\n  - prompt: 42\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be a string"):
        load_scenario(p)


def test_load_scenario_eval_repeat_zero(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals:\n  - prompt: hi\n    repeat: 0\n")
    with pytest.raises(InvalidScenarioYAMLError, match=">= 1"):
        load_scenario(p)


def test_load_scenario_eval_repeat_negative(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals:\n  - prompt: hi\n    repeat: -1\n")
    with pytest.raises(InvalidScenarioYAMLError, match=">= 1"):
        load_scenario(p)


def test_load_scenario_eval_repeat_not_int(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals:\n  - prompt: hi\n    repeat: foo\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be an int"):
        load_scenario(p)


def test_load_scenario_eval_repeat_bool_rejected(tmp_path: Path) -> None:
    """`bool` is subclass of int in Python; explicitly rejected per loader."""
    p = _write_yaml(tmp_path, "evals:\n  - prompt: hi\n    repeat: true\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be an int"):
        load_scenario(p)


def test_load_scenario_eval_expect_not_dict(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals:\n  - prompt: hi\n    expect: not_a_mapping\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be a mapping"):
        load_scenario(p)


def test_load_scenario_eval_judge_not_dict(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals:\n  - prompt: hi\n    judge: not_a_mapping\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be a mapping"):
        load_scenario(p)


def test_load_scenario_mcp_servers_not_list(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals:\n  - prompt: hi\nmcp_servers: echo\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be a list"):
        load_scenario(p)


def test_load_scenario_mcp_servers_non_string_element(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals:\n  - prompt: hi\nmcp_servers:\n  - 42\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be a string"):
        load_scenario(p)


def test_load_scenario_model_non_string(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, "evals:\n  - prompt: hi\nmodel: 42\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be a string"):
        load_scenario(p)


def test_load_scenario_yml_extension_accepted(tmp_path: Path) -> None:
    """Both `.yaml` and `.yml` are accepted."""
    p = _write_yaml(tmp_path, "evals:\n  - prompt: hi\n", name="scenario.yml")
    s = load_scenario(p)
    assert len(s.evals) == 1


def test_scenario_eval_dataclass_is_frozen() -> None:
    import dataclasses

    e = ScenarioEval(prompt="hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.prompt = "mutated"  # type: ignore[misc]


def test_scenario_dataclass_is_frozen() -> None:
    import dataclasses

    s = Scenario(evals=[ScenarioEval(prompt="hi")])
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.model = "mutated"  # type: ignore[misc]


def test_scenario_evals_defensively_copied() -> None:
    evals_list = [ScenarioEval(prompt="hi")]
    s = Scenario(evals=evals_list)
    evals_list.append(ScenarioEval(prompt="mutated"))
    assert len(s.evals) == 1


def test_scenario_eval_expect_defensively_copied() -> None:
    expect = {"k": "v"}
    e = ScenarioEval(prompt="hi", expect=expect)
    expect["k"] = "MUTATED"
    assert e.expect == {"k": "v"}


def test_invalid_scenario_yaml_error_carries_field_name_jsonptr() -> None:
    """`field_name` MUST be an RFC 6901 JSON Pointer."""
    err = InvalidScenarioYAMLError(
        "test",
        file_path="/tmp/test.yaml",
        field_name="/evals/0/prompt",
    )
    assert err.field_name == "/evals/0/prompt"
    assert err.error_code == "INVALID_SCENARIO_YAML"
