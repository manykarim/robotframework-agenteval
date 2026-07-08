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

"""Unified host-instance budget plumbing mixin (Story 14.6 / C20+C26+C89+C95 closure).

Single source of truth for the ``_max_cost_usd`` + ``_max_runtime_seconds``
instance attributes that ``@guarded_fanout()`` reads via ``getattr`` per
``_kernel/guardrails.py:265-266``. Inherited by ``MCPLibrary``,
``SkillsLibrary``, and ``OrchestrationLibrary`` so all 3 carry budget
plumbing symmetrically. Closes:

- ``DF-4.4-S1`` / C20 (MCPLibrary ``MCP.Get Tool Discoverability`` budget
  enforcement; Epic 4 retro, 9 epics old at Story 14.6 close).
- ``DF-4.3-S6`` / C26 (OrchestrationLibrary ``Run Scenario`` budget
  enforcement; Epic 4 cross-story back-fill).
- ``DF-13.3-S1`` / C89 (MCPLibrary ``MCP.Compare Tool Discoverability``
  budget enforcement; Epic 13 same-architecture gap).
- ``DF-13.5-S1`` / C95 (SkillsLibrary ``Skill.Compare Discoverability``
  cross-library budget plumbing; Epic 13 final-Phase-2-story carryover).

Closing 3 retro action items + 4 catalog rows = 7 closures (the most of
any Epic 14 story; appropriate for the final Epic 14 story with the
biggest architectural blast radius).

**Composition update (``compose-single-library-import`` change):**
MCPLibrary + SkillsLibrary are now composed into ``_SUB_LIBRARIES`` in
``AgentEval.__init__`` (the former ``Get Frontmatter`` collision was
resolved by namespace-prefix renames). ``AgentEval._build_components``
forwards ``max_cost_usd`` + ``max_runtime_seconds`` to every
``_HostBudgetPlumbing`` subclass, so under a plain ``Library AgentEval``
import all budget-aware libraries inherit the top-level config-resolved
budgets automatically. A standalone module-path import still accepts the
budgets at RF ``Library`` import time (no ``WITH NAME`` needed — the
namespace prefix is baked into each keyword name):

    *** Settings ***
    Library    AgentEval.mcp.library.MCPLibrary    max_cost_usd=10.00
    Library    AgentEval.skills.library.SkillsLibrary    max_cost_usd=20.00

``OrchestrationLibrary`` is likewise auto-wired by
``AgentEval._build_components`` and inherits the top-level config-resolved
budgets.
"""

from __future__ import annotations

from typing import Any


class _HostBudgetPlumbing:
    """Mixin adding ``_max_cost_usd`` + ``_max_runtime_seconds`` instance attrs.

    Subclasses inherit budget plumbing without redeclaring the attrs.
    Uses cooperative-multiple-inheritance ``super().__init__(**kwargs)``
    forwarding so subclasses can layer their own ctor args (e.g.,
    ``OrchestrationLibrary.default_provider`` per Story 4.3 code-review
    HIGH-C 2-way fix 2026-05-20).

    Args:
        max_cost_usd: Per-fan-out cost budget in USD. ``None`` = no
            enforcement (backwards-compatible with pre-Story-14.6
            behavior; identical to a host instance lacking the attr).
        max_runtime_seconds: Per-fan-out runtime budget in seconds.
            ``None`` = no enforcement.

    The attrs are READ by ``@guarded_fanout()`` (per
    ``_kernel/guardrails.py:265-266``):

        max_cost_usd = getattr(self, "_max_cost_usd", None)
        max_runtime_seconds = getattr(self, "_max_runtime_seconds", None)

    so the mixin's only contract is providing the 2 instance attrs. No
    decorator changes or guardrails changes are needed to close
    C20+C26+C89+C95 — that pipeline has been wired since Story 1b.3.
    """

    def __init__(
        self,
        *,
        max_cost_usd: float | None = None,
        max_runtime_seconds: float | None = None,
        **kwargs: Any,
    ) -> None:
        self._max_cost_usd = max_cost_usd
        self._max_runtime_seconds = max_runtime_seconds
        super().__init__(**kwargs)
