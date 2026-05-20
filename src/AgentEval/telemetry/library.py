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

"""Telemetry RF-keyword surface (Story 5.4 AC-5.4.5).

Ships the `Get Last Warnings` keyword (PRD FR62) backed by the
`_kernel/warnings` per-test buffer. Sub-library registration honored
via `_SUB_LIBRARIES` in `AgentEval/__init__.py`.

Filename matches the existing sub-library convention (`hooks/library.py`,
`orchestration/library.py`); the Story 5.4 spec's `telemetry/_keywords.py`
working name was a placeholder. The conventional name documents intent
at the same place `_build_components` resolves sub-libraries.
"""

from __future__ import annotations

from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel import warnings as _agenteval_warnings
from AgentEval._kernel.tier import tier

__all__ = ["TelemetryLibrary"]


class TelemetryLibrary:
    """`Get Last Warnings` keyword (Story 5.4 / PRD FR62)."""

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
