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

"""Story 4.3 PRD FR41 `ConfigValue` surface + `Get Effective Config setting=key` form."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from AgentEval import AgentEval
from AgentEval._kernel.context import ConfigValue


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Isolate AGENTEVAL_* env vars + .env so tests don't see workstation values."""
    for key in list(os.environ):
        if key.startswith("AGENTEVAL_"):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)


def test_get_effective_config_no_arg_returns_dict_str_any_backwards_compat() -> None:
    """Story 4.3 ratified contract: no-arg form preserves Story 1a.6 shape."""
    agent = AgentEval()
    config = agent.get_effective_config()
    assert isinstance(config, dict)
    assert config["provider"] == "litellm"
    assert config["telemetry"] is True
    assert config["max_cost_usd"] == 5.00


def test_get_effective_config_setting_returns_config_value() -> None:
    """Story 4.3 / PRD FR41: setting=key returns ConfigValue with value + source."""
    agent = AgentEval()
    cv = agent.get_effective_config(setting="max_cost_usd")
    assert isinstance(cv, ConfigValue)
    assert cv.value == 5.00
    assert cv.source == "default"


def test_get_effective_config_setting_init_arg_source() -> None:
    """An explicit kwarg → source="init_arg"."""
    agent = AgentEval(max_cost_usd=1.00)
    cv = agent.get_effective_config(setting="max_cost_usd")
    assert cv.value == 1.00
    assert cv.source == "init_arg"


def test_get_effective_config_setting_env_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTEVAL_MAX_COST_USD", "2.50")
    agent = AgentEval()
    cv = agent.get_effective_config(setting="max_cost_usd")
    assert cv.value == 2.50
    assert cv.source == "env"


def test_get_effective_config_setting_unknown_raises_key_error() -> None:
    agent = AgentEval()
    with pytest.raises(KeyError, match="unknown config setting"):
        agent.get_effective_config(setting="nonexistent_key_xyz")


def test_get_effective_config_setting_lists_known_keys_on_error() -> None:
    agent = AgentEval()
    with pytest.raises(KeyError) as exc_info:
        agent.get_effective_config(setting="bogus")
    msg = str(exc_info.value)
    assert "provider" in msg
    assert "max_cost_usd" in msg


def test_get_effective_config_with_provenance_returns_full_dict() -> None:
    """Story 4.3 / PRD FR41-compliant full-shape keyword."""
    agent = AgentEval()
    config = agent.get_effective_config_with_provenance()
    assert isinstance(config, dict)
    assert all(isinstance(v, ConfigValue) for v in config.values())
    # All 9 FR42+FR11b keys present.
    expected_keys = {
        "provider",
        "telemetry",
        "trace_backend",
        "allow_validate_operator",
        "default_temperature",
        "mcp_per_test",
        "allow_external_mcp_blind",
        "max_cost_usd",
        "max_runtime_seconds",
    }
    assert set(config.keys()) == expected_keys


def test_get_effective_config_with_provenance_returns_defensive_copy() -> None:
    """Returned dict is shallow-copied so caller mutation doesn't affect library state."""
    agent = AgentEval()
    config = agent.get_effective_config_with_provenance()
    config["provider"] = ConfigValue(value="MUTATED", source="init_arg")
    # Re-fetch — library state must be unchanged.
    config2 = agent.get_effective_config_with_provenance()
    assert config2["provider"].value == "litellm"


def test_config_value_is_frozen_dataclass() -> None:
    import dataclasses

    cv = ConfigValue(value="litellm", source="default")
    with pytest.raises(dataclasses.FrozenInstanceError):
        cv.value = "mutated"  # type: ignore[misc]


def test_config_value_source_literal_values() -> None:
    """All 4 PRD FR41 source enum values must be accepted at construction."""
    for source in ("init_arg", "env", "dotenv", "default"):
        cv = ConfigValue(value="x", source=source)  # type: ignore[arg-type]
        assert cv.source == source
