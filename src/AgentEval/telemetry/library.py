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

# ruff: noqa: E501
# Browser-Library-style docstring tables can carry long descriptions on a
# single physical line. Per-line 120-char limit waived for this file per
# Phase 4 docstring-refresh proposal (2026-05-26).

"""Telemetry RF-keyword surface (Story 5.4 AC-5.4.5 + Story 5.5 AC-5.5.1).

Ships the public RF keyword surface for Epic 5:
- `Get Last Warnings` (Story 5.4 / PRD FR62) — structured WarningRecord
  per-test buffer accessor.
- `Get Spans` / `Get Tool Calls` / `Get Run Manifest` (Story 5.5
  AC-5.5.1) — thin keyword wrappers around the `_kernel/trace_store`
  projection accessors so `.robot` consumers (including the rf-mcp
  dogfood suite per Story 5.5 AC-5.5.3) can read trace state without
  dropping into `Evaluate` Python calls.

Sub-library registration honored via `_SUB_LIBRARIES` in
`AgentEval/__init__.py`. Filename matches the existing sub-library
convention (`hooks/library.py`, `orchestration/library.py`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from robot.api.deco import keyword

from AgentEval._kernel import trace_store
from AgentEval._kernel import warnings as _agenteval_warnings
from AgentEval._kernel.context import current_context
from AgentEval._kernel.tier import tier

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import ReadableSpan

    from AgentEval.types import RunManifest, ToolCallTrace

__all__ = ["TelemetryLibrary"]

# Browser-Library-style docstring migration marker (Phase 4, 2026-05-26).
_BROWSER_STYLE_MIGRATED = True


class TelemetryLibrary:
    """`Get Last Warnings` + `Get Spans` + `Get Tool Calls` + `Get Run Manifest`
    keyword surface (Story 5.4 / PRD FR62 + Story 5.5 / AC-5.5.1)."""

    @keyword(name="Get Last Warnings")
    @tier(1)
    def get_last_warnings(self, test_id: str = "current") -> list[dict[str, Any]]:
        """Returns warnings emitted during the test run as JSON-serializable dicts (PRD FR62).

        [Tier 1 — Deterministic] — returns ``list[dict]``. Each record
        has the FR62 ratified 5-field shape: ``warning_type`` (str —
        fully-qualified Python warning class), ``message`` (str — human-
        readable text), ``source`` (str — emitting subsystem),
        ``timestamp`` (str — UTC RFC 3339), ``remediation`` (str | None
        — actionable advice).

        | =Arguments= | =Description= |
        | ``test_id`` | ``"current"`` (default) — resolves to the bound test via the listener context; returns ``[]`` if no test is bound. ``"all"`` — union across every per-test buffer in the process, sorted by ``timestamp`` ascending. Any other value is treated as a specific test_id (returns the named buffer or ``[]`` if absent). |

        Defensive copy of records. Never raises — buffer-read failures
        fall back to ``[]``.

        Example:
        | @{warnings} =    `Get Last Warnings`
        | Length Should Be    ${warnings}    0                                                   # Clean run: zero warnings.
        | @{all_warnings} =    `Get Last Warnings`    test_id=all
        | FOR    ${w}    IN    @{all_warnings}
        |     Log    [${w}[timestamp]] ${w}[warning_type]: ${w}[message]
        | END

        Notes:
        - PRD FR62 ratifies the 5-field ``WarningRecord`` shape.
        - Story 5.4 ratified the per-test buffer + ``"all"`` aggregation contract.
        - Sibling keywords: `Get Spans`, `Get Tool Calls`, `Get Run Manifest` — companion trace-store accessors.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        records = _agenteval_warnings.get_warnings(test_id)
        return [_agenteval_warnings.warning_record_to_dict(r) for r in records]

    @keyword(name="Get Spans")
    @tier(1)
    def get_spans(self, test_id: str = "current") -> list[ReadableSpan]:
        """Returns all OTel spans recorded for the given test_id (Story 5.5 AC-5.5.1).

        [Tier 1 — Deterministic] — returns ``list[ReadableSpan]`` in
        chronological order by ``start_time``. Empty list is a valid
        state (test ran without emitting spans). Thin keyword wrapper
        around the ``_kernel/trace_store.get_run_spans`` projection
        accessor.

        | =Arguments= | =Description= |
        | ``test_id`` | ``"current"`` (default) — resolves to the bound test; returns ``[]`` if no test is bound. Any other value is forwarded to the projection accessor verbatim. |

        Example:
        | @{spans} =    `Get Spans`
        | Should Not Be Empty    ${spans}
        | FOR    ${span}    IN    @{spans}
        |     ${duration_ns} =    Evaluate    ${span.end_time} - ${span.start_time}
        |     Log    ${span.name} took ${duration_ns} ns
        | END
        | @{spans_specific} =    `Get Spans`    test_id=My Suite.Specific Test

        Notes:
        - Story 5.5 AC-5.5.1 ratifies the keyword wrapper. AC-5.5.3 covers the rf-mcp dogfood consumer.
        - Story 5.5 code-review 3-way HIGH-A established the no-bound-test → ``[]`` non-raising contract.
        - Sibling keywords: `Get Tool Calls` (projection over execute_tool spans); `Get Run Manifest` (resource-attribute projection); `Get Last Warnings`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if test_id == "current":
            # Story 5.5 code-review 3-way HIGH-A fix 2026-05-20 (Blind HIGH-2 +
            # Edge-cases HIGH-EC-1 + Auditor HIGH-1): when no test is bound,
            # the underlying accessor raises `ValueError`. The AC-5.5.1
            # contract + docstring promise `[]`. Resolve current_context()
            # locally so the keyword honors the documented contract without
            # propagating ValueError on the no-bound-test path.
            ctx = current_context()
            if ctx is None or not ctx.test_id:
                return []
            return trace_store.get_run_spans(ctx.test_id)
        return trace_store.get_run_spans(test_id)

    @keyword(name="Get Tool Calls")
    @tier(1)
    def get_tool_calls(self, test_id: str = "current") -> list[ToolCallTrace]:
        """Returns ``ToolCallTrace`` records projected from the trace store (Story 5.5 AC-5.5.1).

        [Tier 1 — Deterministic] — returns ``list[ToolCallTrace]``. Thin
        keyword wrapper around ``_kernel/trace_store.get_tool_calls``.
        Mirrors the source-filtering semantics of the Story 1b.2 accessor
        (no per-call source filter exposed at the RF surface; consumers
        filter the returned list themselves).

        | =Arguments= | =Description= |
        | ``test_id`` | ``"current"`` (default) resolves to the bound test; returns ``[]`` if no test is bound. Any other value is forwarded to the projection accessor verbatim. |

        Returns ``list[ToolCallTrace]`` frozen dataclasses (Story 1b.2
        shape): each record carries ``name``, ``args``, ``result``,
        ``error``, ``latency_ms``, ``source``, ``gen_ai_tool_call_id``,
        ``sequence_index``.

        Example:
        | @{tool_calls} =    `Get Tool Calls`
        | Should Not Be Empty    ${tool_calls}
        | Should Be Equal    ${tool_calls}[0].name    web_search
        | Should Be Equal As Integers    ${tool_calls}[0].sequence_index    0

        Notes:
        - Story 5.5 AC-5.5.1 ratifies the keyword wrapper.
        - `ToolCallTrace` shape ratified at Story 1b.2 + FR35 OTel GenAI semconv per architecture L975.
        - Sibling keywords: `Get Spans` (full span list); `Get Tool Call Count` (metrics-library count over `AgentRunResult`); `Get Run Manifest`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if test_id == "current":
            # Story 5.5 code-review 3-way HIGH-A fix 2026-05-20: see `get_spans`.
            # Same defensive resolution for the no-bound-test current path.
            ctx = current_context()
            if ctx is None or not ctx.test_id:
                return []
            return trace_store.get_tool_calls(ctx.test_id)
        return trace_store.get_tool_calls(test_id)

    @keyword(name="Get Run Manifest")
    @tier(1)
    def get_run_manifest(self, test_id: str = "current") -> RunManifest | None:
        """Returns the in-memory 7-field ``RunManifest`` for the given test_id (Story 5.5 AC-5.5.1).

        [Tier 1 — Deterministic] — returns ``RunManifest | None``.
        ``None`` when ``test_id="current"`` and no test is bound (Tier-1
        sibling-consistency with `Get Spans` / `Get Tool Calls` /
        `Get Last Warnings` non-raising contracts). The in-memory
        manifest is the **ratified 7-field shape** (``library_version``,
        ``test_id``, ``suite_id``, ``redaction_policy_hash``,
        ``started_at``, ``ended_at``, ``agenteval_tier_breakdown``) —
        NOT the Story-5.3-extended operational metadata dict (which
        lives in the JSON sidecar at
        ``<output_dir>/agenteval/manifest__<suite>__<test>.json``).

        | =Arguments= | =Description= |
        | ``test_id`` | ``"current"`` (default) resolves to the bound test; returns ``None`` if no test is bound. Any other value is forwarded to the projection accessor verbatim — that accessor's ``ValueError`` propagates if the explicit id resolves to None per Story 1b.2 semantics. |

        Example:
        | ${manifest} =    `Get Run Manifest`
        | Should Not Be Equal    ${manifest}    ${NONE}
        | Should Not Be Empty    ${manifest.library_version}
        | Length Should Be    ${manifest.redaction_policy_hash}    64                # SHA-256 hex.

        Notes:
        - Story 5.5 AC-5.5.1 ratifies the keyword wrapper.
        - 7-field shape ratified at Story 1b.2 per FR39.
        - Story 5.5 code-review 2-way HIGH-F established the ``None`` (not raise) contract on no-bound-test current path.
        - For the Story-5.3-extended operational shape, read the JSON sidecar directly.
        - Sibling keywords: `Get Spans`, `Get Tool Calls`, `Get Last Warnings`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if test_id == "current":
            ctx = current_context()
            if ctx is None or not ctx.test_id:
                return None
            return trace_store.get_run_manifest(ctx.test_id)
        return trace_store.get_run_manifest(test_id)
