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

"""Shared types for the skills sub-library (Story 7.1).

Exported:
    ActivationDecision — frozen dataclass returned by `Skill.Get Activation Decision`.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ActivationDecision"]


@dataclass(frozen=True)
class ActivationDecision:
    """Result of `Skill.Get Activation Decision` [Tier 3].

    Fields:
        activated: True iff the skill name was found in the agent response text
            (case-insensitive substring match — Phase-1 heuristic per AC-7.1.4).
        reasoning: Full agent response text used for the activation inference.
        cost_usd: LLM call cost in USD from the adapter run.
        latency_seconds: Wall-clock seconds for the adapter run.
    """

    activated: bool
    reasoning: str
    cost_usd: float
    latency_seconds: float
