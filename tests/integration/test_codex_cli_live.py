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

"""Env-gated live integration test for `CodexCLIAdapter` (Story 11.1 AC-11.1.5).

Skipped unless ``AGENTEVAL_INTEGRATION_TESTS=1`` AND the `codex` binary
is on ``$PATH`` AND a Codex login session exists. CI does NOT run this;
manual-validation-only.

Per Story 4.2 precedent (`tests/integration/test_claude_code_cli_live.py`):
single-shot "say hi" against the real binary + assert non-empty response
+ usage > 0.
"""

from __future__ import annotations

import os
import shutil

import pytest

from AgentEval.coding_agent.codex_cli import CodexCLIAdapter


@pytest.mark.skipif(
    os.environ.get("AGENTEVAL_INTEGRATION_TESTS") != "1",
    reason="Live SDK integration tests gated behind AGENTEVAL_INTEGRATION_TESTS=1",
)
@pytest.mark.skipif(
    shutil.which("codex") is None,
    reason="codex binary not on $PATH",
)
def test_codex_cli_live_say_hi() -> None:
    """Drives ``codex exec --json 'Say hi in one word, no thinking.'`` against
    the real binary + asserts the AgentRunResult is non-empty + reports
    positive usage."""
    adapter = CodexCLIAdapter()
    result = adapter.run("Say hi in one word, no thinking.")
    assert result.response_text, "Expected non-empty response_text from live codex run"
    assert result.usage.output_tokens > 0, "Expected positive output_tokens from live codex run"
    # Empty mcp_servers path → trivially honest hosted_in_process per ADR-016
    assert result.metadata.mcp_coverage == "hosted_in_process"
    assert result.metadata.completeness == "complete"
