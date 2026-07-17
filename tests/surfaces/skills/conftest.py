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

"""Shared fixtures + fake adapters for the Skills surface tests.

The fakes satisfy the ``Adapter`` protocol (a ``name`` attribute + a
``run(prompt) -> AgentRunResult``) so no real LLM is ever called.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from AgentEval._core import AgentRunResult

VALID_SKILL = """---
name: web-search
description: Search the web for current information and news.
allowed-tools:
  - Bash
  - Read
disable-model-invocation: false
---

# Web Search

Use this skill to look things up online.
"""


@pytest.fixture
def skill_file(tmp_path: Path) -> Path:
    """A valid skill .md file named 'web-search'."""
    path = tmp_path / "web-search.md"
    path.write_text(VALID_SKILL, encoding="utf-8")
    return path


class FixedAdapter:
    """An adapter that always returns the same response text."""

    name = "fake-fixed"

    def __init__(self, response_text: str, *, cost_usd: float = 0.01, latency_seconds: float = 0.5) -> None:
        self._response_text = response_text
        self._cost_usd = cost_usd
        self._latency_seconds = latency_seconds
        self.calls = 0

    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        self.calls += 1
        return AgentRunResult(
            response_text=self._response_text,
            cost_usd=self._cost_usd,
            latency_seconds=self._latency_seconds,
        )


class PromptRoutedAdapter:
    """Activates (echoes ``skill_name``) only when a trigger word is in the prompt."""

    name = "fake-routed"

    def __init__(self, skill_name: str, trigger: str) -> None:
        self._skill_name = skill_name
        self._trigger = trigger.lower()

    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        if self._trigger in prompt.lower():
            text = f"I will use the {self._skill_name} skill for this."
        else:
            text = "I can answer that directly."
        return AgentRunResult(response_text=text, cost_usd=0.02)


class ScriptedAdapter:
    """Returns queued response texts in order, cycling once exhausted."""

    name = "fake-scripted"

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._index = 0

    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        text = self._responses[self._index % len(self._responses)]
        self._index += 1
        return AgentRunResult(response_text=text, cost_usd=0.0)


class JudgeAdapter:
    """A fake judge: returns a fixed JSON score object as the response text."""

    name = "fake-judge"

    def __init__(self, numeric_score: float, reasoning: str = "graded") -> None:
        self._numeric_score = numeric_score
        self._reasoning = reasoning

    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        payload = (
            f'{{"numeric_score": {self._numeric_score}, '
            f'"reasoning": "{self._reasoning}", '
            f'"criteria_breakdown": {{"criteria": {self._numeric_score}}}}}'
        )
        return AgentRunResult(response_text=payload, cost_usd=0.03)
