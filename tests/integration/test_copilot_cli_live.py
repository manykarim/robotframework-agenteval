# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Env-gated live integration test for `CopilotCLIAdapter` (Story 11.2 AC-11.2.5)."""

from __future__ import annotations

import os
import shutil

import pytest

from AgentEval.coding_agent.copilot_cli import CopilotCLIAdapter


@pytest.mark.skipif(
    os.environ.get("AGENTEVAL_INTEGRATION_TESTS") != "1",
    reason="Live SDK integration tests gated behind AGENTEVAL_INTEGRATION_TESTS=1",
)
@pytest.mark.skipif(
    shutil.which("copilot") is None,
    reason="copilot binary not on $PATH",
)
def test_copilot_cli_live_say_hi() -> None:
    """Drives ``copilot --allow-all-tools -p 'Say hi in one word'`` against
    the real binary + asserts the AgentRunResult is non-empty."""
    adapter = CopilotCLIAdapter(model="claude-sonnet-4.6")
    result = adapter.run("Say hi in one word, no thinking.")
    assert result.response_text, "Expected non-empty response_text from live copilot run"
    assert result.usage.output_tokens > 0, "Expected positive output_tokens from live copilot run"
    assert result.metadata.mcp_coverage == "hosted_in_process"
    assert result.metadata.completeness == "complete"
