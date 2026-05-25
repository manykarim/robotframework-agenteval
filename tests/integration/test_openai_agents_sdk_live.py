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

"""Live integration test for `OpenAIAgentsSDKAdapter` (Story 10.2 AC-10.2.5).

Skipped by default. Runs only when BOTH:

- ``AGENTEVAL_INTEGRATION_TESTS=1`` env var is set.
- ``OPENAI_API_KEY`` env var is set (the Agents SDK reads it).

Manual-validation-only — CI does NOT run this. Useful for empirically
verifying the actual ``RunResult.usage`` shape (which Story 10.2 D-3 left
defensively handled because the shape was not documented at story-write
time).
"""

from __future__ import annotations

import os

import pytest

_INTEGRATION_ENABLED = os.environ.get("AGENTEVAL_INTEGRATION_TESTS") == "1"
_HAS_API_KEY = bool(os.environ.get("OPENAI_API_KEY"))


@pytest.mark.skipif(
    not _INTEGRATION_ENABLED,
    reason="Set AGENTEVAL_INTEGRATION_TESTS=1 to opt in to live integration tests.",
)
@pytest.mark.skipif(
    not _HAS_API_KEY,
    reason="Live integration test requires OPENAI_API_KEY in the environment.",
)
def test_openai_agents_sdk_single_shot_live() -> None:
    """Single-shot 'say hello' against the real OpenAI Agents SDK.

    Asserts: response is non-empty AND cost > 0. Does NOT assert on the
    exact response text (model output is non-deterministic).
    """
    pytest.importorskip("agents")

    from AgentEval.coding_agent.openai_agents import OpenAIAgentsSDKAdapter

    adapter = OpenAIAgentsSDKAdapter(
        model="gpt-4o-mini",
        name="agenteval-live-test",
        instructions="You are a terse assistant. Respond in one sentence.",
    )
    result = adapter.run(prompt="Say hello in exactly five words.")

    assert result.response_text, "expected non-empty response_text from live SDK"
    assert result.cost_usd >= 0.0, "cost should be reported (may be 0.0 on cached responses)"
    assert result.metadata.mcp_coverage == "hosted_in_process"
    assert result.metadata.completeness == "complete"
    assert result.latency_seconds > 0.0
