# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Env-gated live integration test for `Judge.Get Score` (Story 12.1 AC-12.1.7).

Skipped unless ``AGENTEVAL_INTEGRATION_TESTS=1`` AND ``ANTHROPIC_API_KEY``
(or another live provider key) is set. CI does NOT run this; manual
validation only.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from AgentEval.judge.library import JudgeLibrary
from AgentEval.judge.types import JudgeScore
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

FIXTURE_RUBRIC = Path(__file__).resolve().parent.parent / "fixtures" / "rubrics" / "skill-quality.md"


@pytest.mark.skipif(
    os.environ.get("AGENTEVAL_INTEGRATION_TESTS") != "1",
    reason="Live judge integration test gated behind AGENTEVAL_INTEGRATION_TESTS=1",
)
@pytest.mark.skipif(
    os.environ.get("ANTHROPIC_API_KEY") is None,
    reason="ANTHROPIC_API_KEY not set",
)
def test_judge_live_against_anthropic_claude_sonnet() -> None:
    """Drives `Judge.Get Score` against `anthropic/claude-sonnet-4-6` with the
    canonical Phase-1 rubric + a small synthetic agent run. Asserts a
    valid `JudgeScore` returns + the cost is non-zero."""
    judge_lib = JudgeLibrary()
    synthetic_run = AgentRunResult(
        response_text=(
            "I searched the filesystem with `du -sh /tmp/*` and identified the "
            "3 largest files: foo.log (120MB), bar.dump (95MB), baz.bin (80MB)."
        ),
        tool_calls=[],
        usage=Usage(input_tokens=50, output_tokens=80),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=0.001,
        latency_seconds=2.0,
        trace_id="live-judge-test",
    )
    score = judge_lib.get_score(
        result=synthetic_run,
        rubric=FIXTURE_RUBRIC,
        judge_adapter="generic",
        judge_model="anthropic/claude-sonnet-4-6",
        temperature=0.0,
        seed=42,
    )
    assert isinstance(score, JudgeScore)
    assert 0.0 <= score.numeric_score <= 10.0
    assert score.reasoning, "Expected non-empty reasoning from live judge"
    assert score.cost_usd > 0.0, "Expected non-zero cost from live judge call"
