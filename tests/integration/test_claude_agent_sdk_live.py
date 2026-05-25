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

"""Live integration test for `ClaudeAgentSDKAdapter` (Story 10.1 AC-10.1.5).

Skipped by default. Runs only when BOTH:

- ``AGENTEVAL_INTEGRATION_TESTS=1`` env var is set.
- ``ANTHROPIC_API_KEY`` env var is set (the Agent SDK reads it).

Manual-validation-only — CI does NOT run this. Documented in Story 10.1
File List + the test docstring so contributors can opt-in locally before
shipping changes that touch the adapter.
"""

from __future__ import annotations

import os

import pytest

_INTEGRATION_ENABLED = os.environ.get("AGENTEVAL_INTEGRATION_TESTS") == "1"
_HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))


@pytest.mark.skipif(
    not _INTEGRATION_ENABLED,
    reason="Set AGENTEVAL_INTEGRATION_TESTS=1 to opt in to live integration tests.",
)
@pytest.mark.skipif(
    not _HAS_API_KEY,
    reason="Live integration test requires ANTHROPIC_API_KEY in the environment.",
)
def test_claude_agent_sdk_single_shot_live() -> None:
    """Single-shot 'say hello' against the real Claude Agent SDK.

    Asserts: response is non-empty AND cost > 0. Does NOT assert on the
    exact response text (model output is non-deterministic).
    """
    # Skip if the SDK isn't installed in the test env.
    pytest.importorskip("claude_agent_sdk")
    pytest.importorskip("anyio")

    from AgentEval.coding_agent.claude_agent_sdk import ClaudeAgentSDKAdapter

    adapter = ClaudeAgentSDKAdapter(
        model="claude-sonnet-4-5",
        max_turns=1,
        system_prompt="You are a terse assistant. Respond in one sentence.",
    )
    result = adapter.run(prompt="Say hello in exactly five words.")

    assert result.response_text, "expected non-empty response_text from live SDK"
    assert result.cost_usd > 0.0, "expected non-zero cost from live SDK call"
    assert result.metadata.mcp_coverage == "hosted_in_process"
    assert result.metadata.completeness == "complete"
    assert result.latency_seconds > 0.0
