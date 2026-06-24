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

"""Env-gated live integration test for `OpenCodeCLIAdapter` (OpenSpec `add-opencode-support`).

Skipped unless ``AGENTEVAL_INTEGRATION_TESTS=1`` AND the `opencode` binary
is on ``$PATH`` AND a provider is configured (``opencode providers login``).
CI does NOT run this; manual-validation-only.

Mirrors `tests/integration/test_codex_cli_live.py`: single-shot "say hi"
against the real binary + assert non-empty response + positive usage.

Model selection: defaults to a free opencode provider model so the live
run incurs zero cost; override via ``AGENTEVAL_OPENCODE_MODEL`` (read with
``os.environ.get`` — never RF `Get Environment Variable`, per CLAUDE.md, to
keep any credential-bearing override out of logs).
"""

from __future__ import annotations

import os
import shutil

import pytest

from AgentEval.coding_agent.opencode_cli import OpenCodeCLIAdapter

_DEFAULT_FREE_MODEL = "opencode/deepseek-v4-flash-free"


@pytest.mark.skipif(
    os.environ.get("AGENTEVAL_INTEGRATION_TESTS") != "1",
    reason="Live integration tests gated behind AGENTEVAL_INTEGRATION_TESTS=1",
)
@pytest.mark.skipif(
    shutil.which("opencode") is None,
    reason="opencode binary not on $PATH",
)
def test_opencode_cli_live_say_hi() -> None:
    """Drives ``opencode run --format json 'Say exactly: hello world...'`` against
    the real binary + asserts the AgentRunResult is non-empty + reports
    positive usage."""
    model = os.environ.get("AGENTEVAL_OPENCODE_MODEL", _DEFAULT_FREE_MODEL)
    adapter = OpenCodeCLIAdapter(model=model)
    result = adapter.run("Say exactly: hello world. Do not use any tools.")
    assert result.response_text, "Expected non-empty response_text from live opencode run"
    assert result.usage.output_tokens > 0, "Expected positive output_tokens from live opencode run"
    # Empty mcp_servers path → trivially honest hosted_in_process per ADR-016.
    assert result.metadata.mcp_coverage == "hosted_in_process"
    assert result.metadata.completeness == "complete"
