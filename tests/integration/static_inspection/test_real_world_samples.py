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

"""Story 2.4 integration tests against real-world / representative sample files.

Per Story 2.4 D-C ratification: the rf-mcp `.mcp.json` sample is
a verbatim copy of `/home/many/workspace/rf-mcp/.mcp.json` (same
maintainer; license-OK). The skill / sub-agent / hook samples are
SYNTHETIC-but-representative — patterned after documented Claude Code
conventions but not verbatim copies (license-clean by construction).

Coverage: 4 samples × 4+ keywords ≥ 16 keyword-against-sample
invocations covered.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval.hooks.library import HooksLibrary
from AgentEval.mcp.library import MCPLibrary
from AgentEval.skills.library import SkillsLibrary
from AgentEval.subagents.library import SubagentsLibrary

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"

RF_MCP_SAMPLE = SAMPLES_DIR / "rf-mcp.mcp.json"
SKILL_SAMPLE = SAMPLES_DIR / "claude-code-incident-triage.md"
SUBAGENT_SAMPLE = SAMPLES_DIR / "claude-code-code-reviewer.subagent.md"
HOOK_SAMPLE = SAMPLES_DIR / "claude-code-settings.json"


@pytest.fixture
def skills() -> SkillsLibrary:
    return SkillsLibrary()


@pytest.fixture
def subagents() -> SubagentsLibrary:
    return SubagentsLibrary()


@pytest.fixture
def hooks() -> HooksLibrary:
    return HooksLibrary()


@pytest.fixture
def mcp() -> MCPLibrary:
    return MCPLibrary()


# --------------------------------------------------------------------------- #
# rf-mcp `.mcp.json` (real-world, same maintainer, license-OK)
# --------------------------------------------------------------------------- #


def test_rf_mcp_get_server_config(mcp: MCPLibrary) -> None:
    servers = mcp.get_server_config(RF_MCP_SAMPLE)
    assert "robotmcp" in servers
    assert servers["robotmcp"]["command"] == "uv"
    assert servers["robotmcp"]["args"][:2] == ["run", "-m"]


def test_rf_mcp_preserves_unknown_optional_fields(mcp: MCPLibrary) -> None:
    """rf-mcp's `.mcp.json` declares `autoStart: true` — a field NOT in
    our `command|args|env|transport|tools` set. The parser preserves
    unknown fields via `dict(entry)` passthrough (Story 2.2 hooks +
    Story 2.3 mcp parallel idiom).
    """
    servers = mcp.get_server_config(RF_MCP_SAMPLE)
    assert servers["robotmcp"]["autoStart"] is True


def test_rf_mcp_no_transport_field_accepted(mcp: MCPLibrary) -> None:
    """rf-mcp's `robotmcp` server entry omits `transport` — Phase-1
    parser accepts omitted optional fields per the FR5 contract.
    """
    servers = mcp.get_server_config(RF_MCP_SAMPLE)
    assert "transport" not in servers["robotmcp"]


def test_rf_mcp_env_dict_round_trips(mcp: MCPLibrary) -> None:
    servers = mcp.get_server_config(RF_MCP_SAMPLE)
    env = servers["robotmcp"]["env"]
    assert isinstance(env, dict)
    assert env["ROBOTMCP_TOKENIZER"] == "auto"


# --------------------------------------------------------------------------- #
# Synthetic Claude Code incident-triage skill
# --------------------------------------------------------------------------- #


def test_skill_get_frontmatter_returns_4_required_fields(skills: SkillsLibrary) -> None:
    frontmatter = skills.get_frontmatter(SKILL_SAMPLE)
    assert frontmatter["name"] == "incident-triage"
    assert "description" in frontmatter
    assert isinstance(frontmatter["allowed-tools"], list)
    assert isinstance(frontmatter["disable-model-invocation"], bool)


def test_skill_get_description_starts_with_helps(skills: SkillsLibrary) -> None:
    desc = skills.get_description(SKILL_SAMPLE)
    assert desc.startswith("Helps an on-call engineer")


def test_skill_get_allowed_tools_includes_read_only_tools(skills: SkillsLibrary) -> None:
    tools = skills.get_allowed_tools(SKILL_SAMPLE)
    assert "read_file" in tools
    assert "search_database" in tools


def test_skill_get_disable_model_invocation_false(skills: SkillsLibrary) -> None:
    assert skills.get_disable_model_invocation(SKILL_SAMPLE) is False


# --------------------------------------------------------------------------- #
# Synthetic Claude Code code-reviewer sub-agent
# --------------------------------------------------------------------------- #


def test_subagent_get_frontmatter_required_fields(subagents: SubagentsLibrary) -> None:
    frontmatter = subagents.get_frontmatter(SUBAGENT_SAMPLE)
    assert frontmatter["name"] == "code-reviewer"
    assert "description" in frontmatter


def test_subagent_optional_tools_present(subagents: SubagentsLibrary) -> None:
    frontmatter = subagents.get_frontmatter(SUBAGENT_SAMPLE)
    assert "read_file" in frontmatter["tools"]


def test_subagent_optional_model_present(subagents: SubagentsLibrary) -> None:
    frontmatter = subagents.get_frontmatter(SUBAGENT_SAMPLE)
    assert frontmatter["model"] == "claude-sonnet-4-6"


# --------------------------------------------------------------------------- #
# Synthetic Claude Code settings.json hooks
# --------------------------------------------------------------------------- #


def test_hook_get_config_three_events(hooks: HooksLibrary) -> None:
    config = hooks.get_config(HOOK_SAMPLE)
    assert "hooks.PreToolUse" in config
    assert "hooks.PostToolUse" in config
    assert "hooks.Stop" in config


def test_hook_pretooluse_has_multiple_entries(hooks: HooksLibrary) -> None:
    config = hooks.get_config(HOOK_SAMPLE)
    pre = config["hooks.PreToolUse"]
    assert len(pre) == 2
    assert pre[0]["timeout"] == 10
    assert pre[0]["matcher"] == "shell|file_write"


def test_hook_pretooluse_args_list(hooks: HooksLibrary) -> None:
    config = hooks.get_config(HOOK_SAMPLE)
    pre = config["hooks.PreToolUse"][0]
    assert pre["args"] == ["--mode=structured"]


def test_hook_stop_minimal_entry(hooks: HooksLibrary) -> None:
    """Stop hook has only the required `command` field — verifies the
    optional-field passthrough idiom against a real-world shape.
    """
    config = hooks.get_config(HOOK_SAMPLE)
    stop = config["hooks.Stop"][0]
    assert stop["command"] == "scripts/cleanup_artifacts.sh"
    assert "args" not in stop
    assert "timeout" not in stop


# --------------------------------------------------------------------------- #
# Cross-sample sanity (Epic 2 keyword surface against real-world inputs)
# --------------------------------------------------------------------------- #


def test_all_samples_present() -> None:
    assert RF_MCP_SAMPLE.exists()
    assert SKILL_SAMPLE.exists()
    assert SUBAGENT_SAMPLE.exists()
    assert HOOK_SAMPLE.exists()


def test_dogfood_prep_epic_3_unblocked(mcp: MCPLibrary) -> None:
    """Story 2.4 AC-2.4.7: rf-mcp's `.mcp.json` parses cleanly + Epic-3 dogfood-ready.

    Story 2.4 code-review Edge-cases MED-2 fix 2026-05-19: pre-edit
    `len(servers) >= 1` was fake-green (trivially true for any non-empty
    dict). Tightened to assert the specific Epic-3-relevant invariants:
    BOTH known rf-mcp servers parse + each declares the required
    `command` + (when present) typed `args` per FR5. This is what Epic-3
    actually consumes from the static-inspection surface.
    """
    servers = mcp.get_server_config(RF_MCP_SAMPLE)
    # Known rf-mcp upstream servers (verified pre-edit; if upstream renames
    # or removes one, this test fails loudly + the verbatim-copy maintenance
    # gap surfaces in PR review).
    assert "robotmcp" in servers, f"rf-mcp dropped robotmcp; got: {sorted(servers.keys())!r}"
    assert "claude-flow" in servers, f"rf-mcp dropped claude-flow; got: {sorted(servers.keys())!r}"
    # FR5 entry shape: each server must have a non-empty `command` string;
    # `args` (when declared) must be a list[str].
    for srv_name, entry in servers.items():
        assert isinstance(entry.get("command"), str) and entry["command"], (
            f"rf-mcp server {srv_name!r} missing FR5-required `command` field"
        )
        if "args" in entry:
            assert isinstance(entry["args"], list)
            assert all(isinstance(arg, str) for arg in entry["args"])
