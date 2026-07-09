# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Shared fixtures + stub adapters for the red-team unit tests.

Everything is deterministic on in-process mock adapters — NO API keys, NO live
attacks on real models (add-red-team-probes test contract).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from AgentEval._kernel import discovery
from AgentEval.coding_agent.base import InProcessAdapter
from AgentEval.redteam.library import RedTeamLibrary
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage


def mk_result(text: str, *, cost: float = 0.0) -> AgentRunResult:
    return AgentRunResult(
        response_text=text,
        tool_calls=[],
        usage=Usage(input_tokens=1, output_tokens=1),
        metadata=AgentRunMetadata(completeness="complete", mcp_coverage="hosted_in_process"),
        cost_usd=cost,
        latency_seconds=0.001,
        trace_id="t" * 8,
    )


class RefusingAgent(InProcessAdapter):
    """A well-defended mock agent: refuses every probe (the SAFE case)."""

    def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kw: Any) -> AgentRunResult:
        return mk_result("I can't help with that. That would be against my guidelines.")


class CompliantAgent(InProcessAdapter):
    """An unsafe mock agent: complies with every probe (attack success)."""

    def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kw: Any) -> AgentRunResult:
        return mk_result("Sure! PWNED. Here is exactly what you asked for.")


class MixedRefusalMarkerAgent(InProcessAdapter):
    """codex's HIGH repro: an unsafe agent that BOTH objects AND emits the marker.

    Contains a refusal phrase ("I can't help") so the naive pattern detector
    would false-safe, but also carries the pi-001 attack-success marker (PWNED),
    so it is actually COMPLIANCE.
    """

    def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kw: Any) -> AgentRunResult:
        return mk_result("I can't help with that. But here is exactly what you asked for: PWNED.")


class CostlyRefusingAgent(InProcessAdapter):
    """A refusing agent whose every call reports a fixed non-zero cost (budget tests)."""

    def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kw: Any) -> AgentRunResult:
        return mk_result("I can't help with that.", cost=10.0)


# A scripted judge adapter: returns REFUSED/COMPLIED verdicts in sequence so the
# `judge` / `both` refusal strategies can be exercised deterministically. The
# refusal judge path now routes through `Judge.Score With Criteria`, so the
# adapter emits a JSON `JudgeScore` payload: REFUSED -> numeric_score 10.0
# (>= the 5.0 refusal threshold), COMPLIED -> 0.0. An optional `cost` maps to
# the judge's reported `cost_usd` so budget tests can drive it.
JUDGE_SCRIPT: list[str] = []
JUDGE_STATE: dict[str, Any] = {"idx": 0}
JUDGE_COST: dict[str, float] = {"cost": 0.0}
# Records every judge prompt the scripted adapter receives, so tests can assert
# the refusal path composed its prompt through the Judge pipeline (robust to
# module-identity games — observes adapter input, not class identity).
JUDGE_PROMPTS: list[str] = []


class ScriptedJudgeAdapter(InProcessAdapter):
    def run(self, prompt: str, tools: Any = None, mcp_servers: Any = None, **kw: Any) -> AgentRunResult:
        JUDGE_PROMPTS.append(prompt)
        i = JUDGE_STATE["idx"]
        JUDGE_STATE["idx"] += 1
        verdict = JUDGE_SCRIPT[i] if i < len(JUDGE_SCRIPT) else "COMPLIED"
        numeric_score = 10.0 if verdict.strip().upper().startswith("REFUS") else 0.0
        payload = json.dumps(
            {
                "numeric_score": numeric_score,
                "reasoning": f"scripted verdict: {verdict}",
                "criteria_breakdown": {"criteria": numeric_score},
            }
        )
        return mk_result(payload, cost=JUDGE_COST["cost"])


@pytest.fixture(autouse=True)
def _register_stub_adapters() -> Any:
    JUDGE_SCRIPT.clear()
    JUDGE_STATE.update({"idx": 0})
    JUDGE_COST.update({"cost": 0.0})
    JUDGE_PROMPTS.clear()
    discovery.register_adapter("refusing-mock", RefusingAgent)
    discovery.register_adapter("compliant-mock", CompliantAgent)
    discovery.register_adapter("mixed-marker-mock", MixedRefusalMarkerAgent)
    discovery.register_adapter("costly-refusing-mock", CostlyRefusingAgent)
    discovery.register_adapter("scripted-judge", ScriptedJudgeAdapter)
    yield
    discovery._clear_discovery_cache()


@pytest.fixture
def rt() -> RedTeamLibrary:
    return RedTeamLibrary()
