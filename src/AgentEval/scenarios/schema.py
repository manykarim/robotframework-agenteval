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

"""Scenario YAML schema dataclasses (Story 4.3 / PRD FR15).

Story 4.3 Phase-1 scope: YAML maps onto these frozen dataclasses via
`loader.load_scenario(path)`. Schema violations raise
`InvalidScenarioYAMLError` with a JSON-Pointer `field_name` per the
Tier-1 setup-failure convention (parallel to `InvalidMCPServerConfigError`
+ `InvalidHookConfigError`).

Required shape per PRD FR15 L1514:
- Top-level: `evals: list[ScenarioEval]` (REQUIRED).
- Top-level optional: `model: str`, `provider: str`, `agent: str`,
  `mcp_servers: list[str]`.
- Per-eval REQUIRED: `prompt: str`.
- Per-eval optional: `repeat: int = 1`, `expect: dict`, `judge: dict`
  (Phase-2 placeholder).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["ScenarioEval", "Scenario"]


@dataclass(frozen=True)
class ScenarioEval:
    """One evaluation in a scenario's `evals[]` list (Story 4.3)."""

    prompt: str
    repeat: int = 1
    expect: dict[str, Any] = field(default_factory=dict)
    judge: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # M_R6 shallow-copy at construction.
        object.__setattr__(self, "expect", dict(self.expect))
        object.__setattr__(self, "judge", dict(self.judge))


@dataclass(frozen=True)
class Scenario:
    """Parsed scenario YAML (Story 4.3 / PRD FR15).

    Top-level optional fields are `None` when absent; the scenario
    executor in `Run Scenario` falls back to library-level defaults
    OR keyword-level kwargs in that case.
    """

    evals: list[ScenarioEval]
    model: str | None = None
    provider: str | None = None
    agent: str | None = None
    mcp_servers: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # M_R6 shallow-copy at construction.
        object.__setattr__(self, "evals", list(self.evals))
        object.__setattr__(self, "mcp_servers", list(self.mcp_servers))
