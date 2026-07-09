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

"""Shared test doubles for the skill A/B benchmark suites (add-skill-ab-benchmark).

NO live API keys — every adapter here is a scripted `InProcessAdapter` whose
`run()` is deterministic. The judge double returns canned JSON so the blind
grading path is exercised without an LLM.
"""

from __future__ import annotations

import json
from typing import Any

from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage

# Marker the injected-skill block carries (see `_benchmark.compose_arm_prompt`).
SKILL_MARKER = "BEGIN SKILL"


def _result(text: str, cost: float = 0.0, in_tok: int = 5, out_tok: int = 5) -> AgentRunResult:
    return AgentRunResult(
        response_text=text,
        tool_calls=[],
        usage=Usage(input_tokens=in_tok, output_tokens=out_tok),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=cost,
        latency_seconds=0.001,
        trace_id="a" * 32,
    )


def make_conditional_stub(
    *,
    with_skill_text: str,
    without_skill_text: str,
    cost: float = 0.0,
    in_tok_with: int = 20,
    in_tok_without: int = 5,
) -> type[InProcessAdapter]:
    """Adapter that returns a different response depending on skill injection.

    When the prompt contains the injected-skill marker, returns
    `with_skill_text` (and a larger input-token count reflecting the injected
    context). Otherwise returns `without_skill_text`. This lets a benchmark
    demonstrate `skill_improves` deterministically.
    """

    class _Conditional(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            if SKILL_MARKER in prompt:
                return _result(with_skill_text, cost=cost, in_tok=in_tok_with, out_tok=8)
            return _result(without_skill_text, cost=cost, in_tok=in_tok_without, out_tok=5)

    return _Conditional


def make_constant_stub(text: str, cost: float = 0.0) -> type[InProcessAdapter]:
    """Adapter that ALWAYS returns `text` regardless of skill injection.

    Used to demonstrate `skill_unnecessary` (baseline already passes; the skill
    adds nothing).
    """

    class _Constant(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            return _result(text, cost=cost)

    return _Constant


def make_flaky_stub(*, fail_on_call: int, text: str) -> type[InProcessAdapter]:
    """Adapter that RAISES `RuntimeError` on the `fail_on_call`-th run (1-indexed).

    A module-level call counter is shared across every constructed instance (the
    engine builds a fresh adapter per trial), so exactly ONE trial across the
    whole benchmark fan-out raises. Every other run returns `text`. Used to prove
    a single runtime trial failure is recorded as a non-passing failed trial in
    the evidence WITHOUT aborting the whole benchmark (codex MED).
    """
    state = {"calls": 0}

    class _Flaky(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            state["calls"] += 1
            if state["calls"] == fail_on_call:
                raise RuntimeError("scripted trial failure")
            return _result(text)

    return _Flaky


def make_recording_stub(sink: list[str], text: str) -> type[InProcessAdapter]:
    """Adapter that records every prompt it receives (for prompt-content asserts)."""

    class _Recorder(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            sink.append(prompt)
            return _result(text)

    return _Recorder


def make_judge_stub(
    *,
    score: float,
    reasoning: str = "canned judge reasoning",
    prompt_sink: list[str] | None = None,
    cost: float = 0.0,
) -> type[InProcessAdapter]:
    """Judge adapter returning canned `JudgeScore` JSON.

    When `prompt_sink` is provided, every judge prompt is appended so tests can
    assert the blind-grading contract (no arm label / no harness-injected skill
    name).
    """

    payload = json.dumps(
        {
            "numeric_score": score,
            "reasoning": reasoning,
            "criteria_breakdown": {},
        }
    )

    class _Judge(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            if prompt_sink is not None:
                prompt_sink.append(prompt)
            return _result(payload, cost=cost)

    return _Judge


def make_content_sensitive_judge(
    *,
    pass_marker: str,
    prompt_sink: list[str] | None = None,
    pass_score: float = 9.0,
    fail_score: float = 2.0,
) -> type[InProcessAdapter]:
    """Judge whose score depends on whether the graded RESPONSE contains a marker.

    The judge only ever sees the composed judge prompt (rubric + task +
    response_text). Because the marker lives in the trial response, this judge
    grades candidate-vs-baseline differently ONLY through the legitimate
    response content — never through an arm label (which the harness never
    adds).
    """

    class _Judge(InProcessAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

        def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
            if prompt_sink is not None:
                prompt_sink.append(prompt)
            score = pass_score if pass_marker.lower() in prompt.lower() else fail_score
            payload = json.dumps({"numeric_score": score, "reasoning": "graded", "criteria_breakdown": {}})
            return _result(payload)

    return _Judge
