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
from typing import Any

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


def test_run_scenario_forwards_model_from_yaml_via_introspection(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    """Story 4.3 code-review Blind H4 fix 2026-05-20: pre-edit only asserted
    `len(results) == 1` — Mock ignores model so precedence was unverified
    per `feedback_test_name_assertion_match` 5th catch. Now probes via the
    constructed adapter's `_model` field state.
    """
    from AgentEval.coding_agent.generic import GenericAdapter

    p = _write_scenario(
        tmp_path,
        """
model: yaml-model-xyz
provider: mock
evals:
  - prompt: "x"
""",
    )

    captured: dict[str, str | None] = {}
    original_init = GenericAdapter.__init__

    def _capture_init(self: GenericAdapter, **kwargs: Any) -> None:
        captured["model"] = kwargs.get("model")
        original_init(self, **kwargs)

    GenericAdapter.__init__ = _capture_init  # type: ignore[method-assign]
    try:
        lib.run_scenario(adapter="generic", scenario=str(p))
    finally:
        GenericAdapter.__init__ = original_init  # type: ignore[method-assign]
    assert captured["model"] == "yaml-model-xyz"


def test_run_scenario_kwarg_overrides_scenario_model(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    """Story 4.3 code-review Blind H4 fix 2026-05-20: real precedence probe."""
    from AgentEval.coding_agent.generic import GenericAdapter

    p = _write_scenario(
        tmp_path,
        """
model: yaml-model
provider: mock
evals:
  - prompt: "x"
""",
    )
    captured: dict[str, str | None] = {}
    original_init = GenericAdapter.__init__

    def _capture_init(self: GenericAdapter, **kwargs: Any) -> None:
        captured["model"] = kwargs.get("model")
        original_init(self, **kwargs)

    GenericAdapter.__init__ = _capture_init  # type: ignore[method-assign]
    try:
        lib.run_scenario(adapter="generic", scenario=str(p), model="caller-model")
    finally:
        GenericAdapter.__init__ = original_init  # type: ignore[method-assign]
    assert captured["model"] == "caller-model"


def test_run_scenario_scenario_yaml_agent_field_used_when_no_caller_adapter(
    lib: OrchestrationLibrary, tmp_path: Path
) -> None:
    """Story 4.3 code-review 3-way HIGH-A fix 2026-05-20 (Blind H2 + Edge-cases
    H1 + Codex HIGH-3): pre-edit `_UNSET` sentinel honestly distinguishes
    "no caller adapter" from "caller passed adapter=generic" — scenario YAML
    `agent:` field wins ONLY when caller didn't pass adapter.
    """
    p = _write_scenario(
        tmp_path,
        """
agent: nonexistent_xyz_adapter
provider: mock
evals:
  - prompt: "x"
""",
    )
    from AgentEval.errors import AdapterDiscoveryError

    # No `adapter=` kwarg → YAML's `agent:` is resolved → AdapterDiscoveryError.
    with pytest.raises(AdapterDiscoveryError, match="nonexistent_xyz_adapter"):
        lib.run_scenario(scenario=str(p))


def test_run_scenario_explicit_adapter_generic_wins_over_yaml_agent(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    """Story 4.3 code-review 3-way HIGH-A fix 2026-05-20: caller's explicit
    `adapter="generic"` MUST override YAML's `agent:` field — pre-edit string
    comparison to `"generic"` couldn't distinguish default-vs-explicit, so
    YAML always won. Sentinel fix corrects this.
    """
    p = _write_scenario(
        tmp_path,
        """
agent: nonexistent_xyz_adapter
provider: mock
evals:
  - prompt: "x"
""",
    )
    # Caller's explicit adapter="generic" overrides YAML's agent — no raise.
    results = lib.run_scenario(adapter="generic", scenario=str(p))
    assert len(results) == 1


def test_run_scenario_propagates_yaml_mcp_servers_field(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    """Story 4.3 code-review 2-way HIGH-B fix 2026-05-20 (Blind H1 + Codex
    HIGH-4): pre-edit silently dropped `scenario_obj.mcp_servers`. Loader
    parsed the field; executor never read it. Now if caller didn't pass
    `mcp_servers=`, YAML's mcp_servers list flows through the same
    name-resolution path (which today raises NotImplementedError per DF-4.3-S2).
    """
    p = _write_scenario(
        tmp_path,
        """
provider: mock
mcp_servers:
  - echo
  - rfmcp
evals:
  - prompt: "x"
""",
    )
    with pytest.raises(NotImplementedError, match="DF-4.3-S2"):
        lib.run_scenario(adapter="generic", scenario=str(p))


def test_run_scenario_caller_mcp_servers_wins_over_yaml(lib: OrchestrationLibrary, tmp_path: Path) -> None:
    """Caller's explicit `mcp_servers={}` (empty dict, no-op) wins over YAML's
    non-empty `mcp_servers:` list (pre-edit logic): caller's None is the
    default → YAML fills in. But caller's explicit empty dict signals "no MCP".
    """
    p = _write_scenario(
        tmp_path,
        """
provider: mock
mcp_servers:
  - echo
evals:
  - prompt: "x"
""",
    )
    # Caller passes empty dict → no NotImplementedError; YAML field is
    # ONLY consulted when caller's mcp_servers is None.
    results = lib.run_scenario(adapter="generic", scenario=str(p), mcp_servers={})
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


# --------------------------------------------------------------------------- #
# Story 4.3 code-review patches 2026-05-20 — Library-level propagation +
# adapter-kwarg-split + UnicodeDecodeError + falsy-coerce
# --------------------------------------------------------------------------- #


def test_library_provider_propagates_to_send_prompt(tmp_path: Path) -> None:
    """Story 4.3 code-review 2-way HIGH-C fix 2026-05-20 (Blind H3 + Codex
    HIGH-1): pre-edit `AgentEval(provider="mock").send_prompt(prompt="hi")`
    bypassed library-level config + hit LiteLLM with no model (ValueError).
    Fix: AgentEval._build_components forwards `provider` to OrchestrationLibrary.
    """
    from AgentEval import AgentEval as AgentEvalLib

    agent = AgentEvalLib(provider="mock")
    # Should NOT raise — mock provider is used per library-level config.
    result = agent.send_prompt(prompt="hello")
    assert isinstance(result, AgentRunResult)
    assert result.response_text == "hello"


def test_send_prompt_per_call_provider_overrides_library_default() -> None:
    """PRD FR41 precedence: per-keyword kwarg wins over library default."""
    from AgentEval import AgentEval as AgentEvalLib

    # Library default is litellm; per-call mock should win.
    agent = AgentEvalLib(provider="litellm")
    result = agent.send_prompt(prompt="hi", provider="mock")
    assert result.response_text == "hi"


def test_send_prompt_splits_ctor_kwargs_via_signature_introspection(
    lib: OrchestrationLibrary,
) -> None:
    """Story 4.3 code-review 2-way HIGH-D fix 2026-05-20 (Codex HIGH-2):
    per-call kwargs that the adapter `__init__` doesn't accept are forwarded
    to `run()` rather than the constructor. Validates the `_split_adapter_kwargs`
    introspection path against `GenericAdapter` (which accepts `**kwargs` →
    everything goes to ctor) and a strict-signature stub class.
    """
    from AgentEval._kernel.discovery import register_adapter
    from AgentEval.coding_agent.base import InProcessAdapter

    captured_run_kwargs: dict[str, Any] = {}

    class _StrictAdapter(InProcessAdapter):
        """Strict-signature adapter — only accepts `provider` + `model` in ctor."""

        def __init__(self, provider: str = "mock", model: str | None = None) -> None:
            super().__init__()
            self._provider = provider
            self._model = model

        def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kwargs: Any) -> AgentRunResult:
            captured_run_kwargs.update(kwargs)
            from AgentEval.types import AgentRunMetadata, Usage

            return AgentRunResult(
                response_text="strict",
                tool_calls=[],
                usage=Usage(input_tokens=0, output_tokens=0),
                metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
                cost_usd=0.0,
                latency_seconds=0.001,
                trace_id="strict-id-0000000000000000000000000000",
            )

    register_adapter("strict_split_test", _StrictAdapter)
    # `temperature` is NOT a ctor kwarg on StrictAdapter — must route to run().
    result = lib.send_prompt(adapter="strict_split_test", prompt="hi", temperature=0.5)
    assert result.response_text == "strict"
    # temperature must have reached run() via run_kwargs split, NOT ctor.
    assert captured_run_kwargs.get("temperature") == 0.5


def test_load_scenario_rejects_non_utf8_file(tmp_path: Path, lib: OrchestrationLibrary) -> None:
    """Story 4.3 code-review Edge-cases H3 fix 2026-05-20: UnicodeDecodeError
    (ValueError subclass) was uncaught pre-edit. Now wrapped as
    InvalidScenarioYAMLError.
    """
    p = tmp_path / "binary.yaml"
    p.write_bytes(b"\xff\xff\xff\xff non-utf-8 bytes \xfe\xfe")
    with pytest.raises(InvalidScenarioYAMLError, match="UTF-8"):
        lib.load_scenario_kw(str(p))


def test_load_scenario_rejects_empty_prompt(tmp_path: Path, lib: OrchestrationLibrary) -> None:
    """Story 4.3 code-review Edge-cases L2 + Codex MED-1 fix 2026-05-20:
    `prompt: ""` rejected at load time (fail-loud) rather than silently
    dispatching an empty prompt to the adapter.
    """
    p = tmp_path / "scenario.yaml"
    p.write_text('evals:\n  - prompt: ""\n')
    with pytest.raises(InvalidScenarioYAMLError, match="non-empty"):
        lib.load_scenario_kw(str(p))


def test_load_scenario_rejects_whitespace_only_prompt(tmp_path: Path, lib: OrchestrationLibrary) -> None:
    p = tmp_path / "scenario.yaml"
    p.write_text('evals:\n  - prompt: "   "\n')
    with pytest.raises(InvalidScenarioYAMLError, match="non-empty"):
        lib.load_scenario_kw(str(p))


def test_load_scenario_rejects_falsy_non_dict_expect(tmp_path: Path, lib: OrchestrationLibrary) -> None:
    """Story 4.3 code-review 3-way MED-A fix 2026-05-20 (Blind M2 + Edge-cases
    M1 + Codex MED-1): pre-edit `entry.get("expect") or {}` silently coerced
    `expect: []`, `expect: 0`, `expect: false` to `{}`. Now type-validated.
    """
    p = tmp_path / "scenario.yaml"
    p.write_text("evals:\n  - prompt: hi\n    expect: []\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be a mapping"):
        lib.load_scenario_kw(str(p))


def test_load_scenario_rejects_falsy_non_dict_judge(tmp_path: Path, lib: OrchestrationLibrary) -> None:
    p = tmp_path / "scenario.yaml"
    p.write_text("evals:\n  - prompt: hi\n    judge: 0\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be a mapping"):
        lib.load_scenario_kw(str(p))


def test_load_scenario_falsy_non_list_mcp_servers_rejected(tmp_path: Path, lib: OrchestrationLibrary) -> None:
    """Story 4.3 code-review 3-way MED-A fix: `mcp_servers: {}` (empty dict)
    was silently coerced to `[]` pre-edit; now type-validated.
    """
    p = tmp_path / "scenario.yaml"
    p.write_text("evals:\n  - prompt: hi\nmcp_servers: {}\n")
    with pytest.raises(InvalidScenarioYAMLError, match="must be a list"):
        lib.load_scenario_kw(str(p))


def test_load_scenario_null_expect_treated_as_absent(tmp_path: Path, lib: OrchestrationLibrary) -> None:
    """Story 4.3 code-review 3-way MED-A: explicit `null` IS treated as absent
    (returns empty dict). Distinguished from falsy non-None values.
    """
    p = tmp_path / "scenario.yaml"
    p.write_text("evals:\n  - prompt: hi\n    expect: null\n")
    scenario = lib.load_scenario_kw(str(p))
    assert scenario.evals[0].expect == {}


def test_load_scenario_root_errors_use_empty_string_field_name(tmp_path: Path) -> None:
    """Story 4.3 code-review Edge-cases M4 + Codex LOW-1 fix 2026-05-20:
    RFC 6901 §5 root pointer is `""` not `"/"` (which would resolve to the
    empty-string-keyed child of root).
    """
    from AgentEval.scenarios.loader import load_scenario

    # Wrong extension — root-level error.
    p = tmp_path / "bad.txt"
    p.write_text("evals:\n  - prompt: hi\n")
    with pytest.raises(InvalidScenarioYAMLError) as exc_info:
        load_scenario(p)
    assert exc_info.value.field_name == ""
