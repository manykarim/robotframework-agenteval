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


def test_get_effective_config_setting_unknown_raises_value_error() -> None:
    """Story 4.3 code-review Blind MED-1 fix 2026-05-20: KeyError → ValueError
    (typed-input-validation idiom).
    """
    agent = AgentEval()
    with pytest.raises(ValueError, match="unknown config setting"):
        agent.get_effective_config(setting="nonexistent_key_xyz")


def test_get_effective_config_setting_lists_known_keys_on_error() -> None:
    agent = AgentEval()
    with pytest.raises(ValueError) as exc_info:
        agent.get_effective_config(setting="bogus")
    msg = str(exc_info.value)
    assert "provider" in msg
    assert "max_cost_usd" in msg


def test_config_value_rejects_invalid_source_at_runtime() -> None:
    """Story 4.3 code-review 2-way MED-B fix 2026-05-20 (Blind M4 + Edge-cases M2):
    `__post_init__` validates source against the closed Literal set so typos
    fail loud per M_R11 instead of silently producing invalid records.
    """
    with pytest.raises(ValueError, match="source must be one of"):
        ConfigValue(value="x", source="invalid")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ConfigValue(value="x", source="initarg")  # type: ignore[arg-type] -- typo


def test_config_value_accepts_all_four_literal_sources() -> None:
    """The 4 PRD FR41 source enum values must construct cleanly."""
    for source in ("init_arg", "env", "dotenv", "default"):
        cv = ConfigValue(value="x", source=source)  # type: ignore[arg-type]
        assert cv.source == source


def test_get_effective_config_no_arg_covers_all_config_keys() -> None:
    """remove-dead-machinery D3: the no-arg form is derived from the provenance
    map, so it now covers every FR42+FR11b key (11 after Story 5.1 added
    `trace_path` + Story 13.2 added `otlp_endpoint`) as plain values.

    Replaces the deleted `Get Effective Config With Provenance` keyword's
    full-map coverage test — the twin keyword was removed (design D3); the
    per-key `setting=` form is the provenance surface.
    """
    agent = AgentEval()
    config = agent.get_effective_config()
    assert isinstance(config, dict)
    # Plain values, NOT ConfigValue (no-arg shape preserved per design D3).
    assert not any(isinstance(v, ConfigValue) for v in config.values())
    expected_keys = {
        "provider",
        "telemetry",
        "trace_backend",
        "trace_path",
        "allow_validate_operator",
        "default_temperature",
        "mcp_per_test",
        "allow_external_mcp_blind",
        "max_cost_usd",
        "max_runtime_seconds",
        "otlp_endpoint",
    }
    assert set(config.keys()) == expected_keys


def test_get_effective_config_per_key_provenance_covers_all_keys() -> None:
    """Per-key provenance (the surviving provenance surface) is available for every key."""
    agent = AgentEval()
    for key in agent.get_effective_config():
        cv = agent.get_effective_config(setting=key)
        assert isinstance(cv, ConfigValue)
        assert cv.source in {"init_arg", "env", "dotenv", "default"}


def test_unknown_env_key_warning_emitted_once_on_instantiation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """remove-dead-machinery D3: ONE resolution pass per instantiation → exactly
    one UserWarning per unknown key per source.

    Before the merge, `AgentEval.__init__` called both `resolve_config` and
    `resolve_config_with_provenance`, so each unknown-`AGENTEVAL_*`-key warning
    fired twice per source. The single-pass merge collapses that to one.
    """
    import warnings

    monkeypatch.setenv("AGENTEVAL_PROVDER", "anthropic")  # typo, unknown key
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        AgentEval()
    provder_warnings = [
        w for w in caught if "AGENTEVAL_PROVDER" in str(w.message) and "os.environ" in str(w.message)
    ]
    assert len(provder_warnings) == 1, (
        f"expected exactly one unknown-key warning for the os.environ source; "
        f"got {[str(w.message) for w in provder_warnings]}"
    )


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
