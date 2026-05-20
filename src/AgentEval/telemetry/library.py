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


class TelemetryLibrary:
    """`Get Last Warnings` + `Get Spans` + `Get Tool Calls` + `Get Run Manifest`
    keyword surface (Story 5.4 / PRD FR62 + Story 5.5 / AC-5.5.1)."""

    @keyword(name="Get Last Warnings")
    @tier(1)
    def get_last_warnings(self, test_id: str = "current") -> list[dict[str, Any]]:
        """[Tier 1 — Deterministic] Return the list of warnings emitted during the run (PRD FR62).

        Per FR62 ratified 5-field shape (2026-05-20): each record is a
        dict with keys ``warning_type`` (str — fully-qualified Python
        warning class name), ``message`` (str — human-readable warning
        text), ``source`` (str — emitting subsystem identifier),
        ``timestamp`` (str — UTC RFC 3339), ``remediation`` (str | None
        — actionable advice or ``None``).

        Args:
            test_id: ``"current"`` (default) resolves to the current bound
                test via `_kernel_context.current_context()`; returns ``[]``
                if no test is bound. ``"all"`` returns the union across
                every per-test buffer in the active process, sorted by
                ``timestamp`` ascending. Any other value is treated as a
                specific test_id — returns the named buffer or ``[]`` if
                absent.

        Returns:
            Defensive copy of the warning records as JSON-serializable dicts.
            Never raises — buffer-read failures fall back to ``[]``.
        """
        records = _agenteval_warnings.get_warnings(test_id)
        return [_agenteval_warnings.warning_record_to_dict(r) for r in records]

    @keyword(name="Get Spans")
    @tier(1)
    def get_spans(self, test_id: str = "current") -> list[ReadableSpan]:
        """[Tier 1 — Deterministic] Return all spans recorded for the given test_id.

        Story 5.5 AC-5.5.1: thin keyword wrapper around the existing
        `_kernel/trace_store.get_run_spans` projection accessor so
        `.robot` consumers (the rf-mcp dogfood suite per AC-5.5.3) can
        read the OTel span store via the public RF surface rather than
        `Evaluate    trace_store.get_run_spans(...)` Python calls.

        Args:
            test_id: ``"current"`` (default) resolves to the bound test
                via the accessor's own `_resolve_test_id` fallback;
                returns ``[]`` if no test is bound + no explicit id.
                Any other value is forwarded to the projection accessor
                verbatim — returns the named buffer or ``[]`` if absent.

        Returns:
            List of `ReadableSpan` instances in chronological order by
            start_time. Empty list is a valid state (test ran without
            emitting spans).
        """
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
        """[Tier 1 — Deterministic] Return the `ToolCallTrace` records for the given test_id.

        Story 5.5 AC-5.5.1: thin keyword wrapper around the existing
        `_kernel/trace_store.get_tool_calls` projection accessor.
        Mirrors the source-filtering semantics of Story 1b.2's accessor
        (no per-call source filter exposed at the RF surface; consumers
        filter the returned list themselves via `Collections` /
        `Evaluate` if needed).

        Args:
            test_id: As in `Get Spans`. ``"current"`` resolves via the
                projection accessor's fallback.

        Returns:
            List of `ToolCallTrace` frozen dataclasses (Story 1b.2 shape).
            Empty list when no tool calls were captured.
        """
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
        """[Tier 1 — Deterministic] Return the ratified 7-field `RunManifest` for the given test_id.

        Story 5.5 AC-5.5.1: thin keyword wrapper around
        `_kernel/trace_store.get_run_manifest`. Returns the in-memory
        ratified 7-field shape (`library_version`, `test_id`, `suite_id`,
        `redaction_policy_hash`, `started_at`, `ended_at`,
        `agenteval_tier_breakdown`) — NOT the Story-5.3-extended
        operational-metadata dict (which is in the JSON sidecar
        `<output_dir>/agenteval/manifest__<suite>__<test>.json`).

        Args:
            test_id: ``"current"`` (default) resolves to the bound test via
                `current_context().test_id`; returns ``None`` when no
                test is bound (Tier-1 sibling-consistency with
                `Get Spans` / `Get Tool Calls` / `Get Last Warnings`
                non-raising contracts). Any other value is forwarded to
                the projection accessor verbatim — the accessor's
                `ValueError` propagates if the explicit id resolves to
                None per Story 1b.2 semantics.

        Returns:
            `RunManifest | None` — None when `test_id="current"` and no
            test is bound. Story 5.5 code-review 2-way HIGH-F fix
            2026-05-20 (Blind HIGH-10 + Edge-cases HIGH-EC-2): pre-edit
            this raised `ValueError` on the no-bound-test current path,
            inconsistent with sibling Tier-1 keywords.
        """
        if test_id == "current":
            ctx = current_context()
            if ctx is None or not ctx.test_id:
                return None
            return trace_store.get_run_manifest(ctx.test_id)
        return trace_store.get_run_manifest(test_id)
