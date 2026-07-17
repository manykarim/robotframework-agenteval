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

"""Unit + gated-live tests for the SKILL.md -> pydantic-ai Capability bridge.

The unit tests never call a model: `Skill.Get Activated Skills` is exercised
over a stub ``AgentRunResult`` carrying a ``load_capability`` tool call, and the
shim is exercised against a real pydantic-ai ``Capability`` (the [agent] extra
is installed in this env). The live smoke is skipped unless creds are present.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from AgentEval._core import AgentRunResult
from AgentEval._core.types import ToolCallTrace
from SkillsLibrary import SkillsLibrary

pytest.importorskip("pydantic_ai", reason="the [agent] extra (pydantic-ai) is required for the bridge tests")


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


REFUNDS_SKILL = """---
name: refunds
description: Use for refund eligibility and return-window questions.
allowed-tools:
  - Read
disable-model-invocation: false
---

# Refunds

Confirm the order ID, then check the 30-day return window.
"""

WEATHER_SKILL = """---
name: weather-lookup
description: Use for current weather and forecast questions.
---

# Weather

Look up the forecast for the named city.
"""


@pytest.fixture
def refunds_file(tmp_path: Path) -> Path:
    path = tmp_path / "refunds.md"
    path.write_text(REFUNDS_SKILL, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Shim: SKILL.md -> deferred Capability.                                       #
# --------------------------------------------------------------------------- #


def test_as_capability_maps_name_description_body(lib: SkillsLibrary, refunds_file: Path) -> None:
    cap = lib.as_capability(refunds_file)
    assert cap.id == "refunds"  # name -> id
    assert cap.description == "Use for refund eligibility and return-window questions."
    assert cap.defer_loading is True  # deferred is the whole point


def test_as_capability_body_becomes_instructions(lib: SkillsLibrary, refunds_file: Path) -> None:
    cap = lib.as_capability(refunds_file)
    # pydantic-ai stores the ctor `instructions=` string in `_instructions` (a list);
    # confirm the markdown body from below the frontmatter is what we mapped in.
    stored = " ".join(str(part) for part in cap._instructions)
    assert "return window" in stored.lower()
    assert "Confirm the order ID" in stored  # full body, not just the description


def test_load_capabilities_from_dir_sorted(lib: SkillsLibrary, tmp_path: Path) -> None:
    (tmp_path / "refunds.md").write_text(REFUNDS_SKILL, encoding="utf-8")
    (tmp_path / "weather.md").write_text(WEATHER_SKILL, encoding="utf-8")
    caps = lib.load_capabilities_from_dir(tmp_path)
    assert sorted(c.id for c in caps) == ["refunds", "weather-lookup"]
    assert all(c.defer_loading is True for c in caps)


def test_load_capabilities_from_missing_dir_raises(lib: SkillsLibrary, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        lib.load_capabilities_from_dir(tmp_path / "nope")


# --------------------------------------------------------------------------- #
# Reader: Skill.Get Activated Skills over an AgentRunResult.                   #
# --------------------------------------------------------------------------- #


def _run_with_calls(*calls: ToolCallTrace) -> AgentRunResult:
    return AgentRunResult(response_text="done", tool_calls=list(calls))


def test_get_activated_skills_reads_load_capability_id(lib: SkillsLibrary) -> None:
    result = _run_with_calls(
        ToolCallTrace(name="load_capability", args={"id": "refunds"}, tool_call_id="1"),
        ToolCallTrace(name="lookup", args={"order": "4821"}, result="eligible", tool_call_id="2"),
    )
    assert lib.get_activated_skills(result) == ["refunds"]


def test_get_activated_skills_empty_when_no_activation(lib: SkillsLibrary) -> None:
    result = _run_with_calls(ToolCallTrace(name="lookup", args={"order": "4821"}, tool_call_id="1"))
    assert lib.get_activated_skills(result) == []


def test_get_activated_skills_dedupes_preserving_order(lib: SkillsLibrary) -> None:
    result = _run_with_calls(
        ToolCallTrace(name="load_capability", args={"id": "weather-lookup"}, tool_call_id="1"),
        ToolCallTrace(name="load_capability", args={"id": "refunds"}, tool_call_id="2"),
        ToolCallTrace(name="load_capability", args={"id": "weather-lookup"}, tool_call_id="3"),
    )
    assert lib.get_activated_skills(result) == ["weather-lookup", "refunds"]


def test_get_activated_skills_skips_malformed_args(lib: SkillsLibrary) -> None:
    result = _run_with_calls(
        ToolCallTrace(name="load_capability", args={}, tool_call_id="1"),  # missing id
        ToolCallTrace(name="load_capability", args={"id": ""}, tool_call_id="2"),  # empty id
        ToolCallTrace(name="load_capability", args={"id": 123}, tool_call_id="3"),  # non-string id
        ToolCallTrace(name="load_capability", args={"id": "refunds"}, tool_call_id="4"),
    )
    assert lib.get_activated_skills(result) == ["refunds"]


# --------------------------------------------------------------------------- #
# Gated live smoke: two Claude-style skills, activate the matching one only.   #
# --------------------------------------------------------------------------- #


def _load_minimax_env() -> bool:
    """Map MINIMAX_* creds from .env onto AGENTEVAL_* in-process. Never prints the key."""
    if os.environ.get("AGENTEVAL_API_KEY") and os.environ.get("AGENTEVAL_MODEL"):
        return True
    try:
        from dotenv import dotenv_values
    except ImportError:
        return False
    env_path = Path(__file__).resolve().parents[3] / ".env"
    values = dotenv_values(env_path) if env_path.exists() else {}
    api_key = values.get("MINIMAX_API_KEY")
    base_url = values.get("MINIMAX_BASE_URL")
    model = values.get("MINIMAX_MODEL")
    if not (api_key and model):
        return False
    os.environ["AGENTEVAL_API_KEY"] = api_key
    os.environ["AGENTEVAL_MODEL"] = model
    if base_url:
        os.environ["AGENTEVAL_BASE_URL"] = base_url
    return True


_LIVE = pytest.mark.skipif(
    not _load_minimax_env(),
    reason="set AGENTEVAL_MODEL/AGENTEVAL_BASE_URL/AGENTEVAL_API_KEY (or MINIMAX_* in .env) for the live skill smoke",
)


@_LIVE
def test_live_matching_skill_activates_unrelated_does_not(lib: SkillsLibrary, tmp_path: Path) -> None:
    from AgentEval._core.adapter import get_adapter

    (tmp_path / "refunds.md").write_text(REFUNDS_SKILL, encoding="utf-8")
    (tmp_path / "weather.md").write_text(WEATHER_SKILL, encoding="utf-8")
    caps = lib.load_capabilities_from_dir(tmp_path)

    result = get_adapter("in-process", capabilities=caps).run("Is order #4821 eligible for a refund?")
    activated = lib.get_activated_skills(result)

    assert "refunds" in activated, f"expected refunds skill to activate; got {activated!r}"
    assert "weather-lookup" not in activated, f"unrelated weather skill should stay quiet; got {activated!r}"
