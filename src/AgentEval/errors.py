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

"""AgentEval error class hierarchy (ADR-014 / was ADR-A3).

Story 1b.2 ships the MINIMAL subset of the catalog needed by
`_kernel/coverage._check_mcp_coverage()`:

- `AgentEvalError(Exception)` — common base class for all agenteval-raised
  errors. Consumers can `try / except AgentEvalError` to catch any error from
  the library.
- `AgentEvalIntegrityError(AgentEvalError)` — sub-base for errors signaling
  that a run's trace/integrity contract is compromised (e.g., uninstrumented
  MCP usage detected, span data partial). Per ADR-014's 4-sub-base scheme.
- `IncompleteTraceError(AgentEvalIntegrityError)` — raised by the kernel's
  `_check_mcp_coverage` gate per FR37 + ADR-016 L44 when a run reports
  `mcp_coverage == "external_mixed"` without `allow_external_mcp_blind=True`.

The other 8 leaves from `docs/contracts/error-class-hierarchy.md` (Story 1a.4
ratified catalog) are added to this module as subsequent stories need them:

- `PollingDisallowedError` — Story 1b.5 / Epic 6 (tier ACL)
- `CostExceededError`, `RuntimeBudgetExceededError` — Story 1b.3 (`@guarded_fanout`)
- `UnsupportedMCPVersionError` — Epic 3 Story 3.1 (MCP transport)
- `UnsupportedBinaryVersionError` — Story 1b.4 (`_assert_binary_version` helper)
- `TierViolationError` — Story 1b.6 (convention enforcer)
- `ValidateOperatorDisallowed` — Epic 6 Story 6.2 (assertion gate enforcement)
- `SandboxRequiredError` — currently lives at `src/AgentEval/security/policy.py`
  per Story 1a.1's pre-`errors.py` baseline; does NOT yet inherit from
  `AgentEvalError`. Re-homing is a Phase-1.5 hygiene carry-over tracked in
  `_bmad-output/implementation-artifacts/deferred-work.md`.

The 3-class structure in this story is extension-friendly: future stories
ADD leaves (and, if needed, the other 3 sub-bases `AgentEvalSafetyError`,
`AgentEvalBudgetError`, `AgentEvalCompatError`) without refactoring the
existing 3 classes.

`error_code` convention (architecture L902-906):
    Every error class sets a static `error_code: ClassVar[str]` attribute
    matching the pattern `<DOMAIN>_<ACTION>` (uppercase). This is used by the
    JUnit XML emitter (FR49) + exit-code mapper (FR50) for structured
    machine-readable error identification.

References:
    - ADR-014 (was ADR-A3): `docs/adr/ADR-014-error-class-hierarchy.md`
    - ADR-016 L44: `docs/adr/ADR-016-mcp-coverage-detection-default.md`
      (defines the IncompleteTraceError raise contract)
    - docs/contracts/error-class-hierarchy.md (Story 1a.4 ratified catalog)
    - PRD FR37 — `IncompleteTraceError` on `external_mixed` runs
    - architecture L376, L902-930, L1184 — base + sub-base + leaf structure
"""

from __future__ import annotations

from typing import ClassVar

__all__ = [
    "AgentEvalError",
    "AgentEvalIntegrityError",
    "IncompleteTraceError",
]


class AgentEvalError(Exception):
    """Common base class for all errors raised by agenteval.

    Consumers can `try / except AgentEvalError` to catch any error from the
    library, then narrow with `isinstance` on the leaf class for typed
    handling.

    Subclasses MUST set `error_code: ClassVar[str]` matching `<DOMAIN>_<ACTION>`
    uppercase. The base class itself uses an empty string so consumers can
    safely read `error_code` without an AttributeError on the rare instance
    that the base is raised directly (which they shouldn't — always raise a
    leaf).
    """

    error_code: ClassVar[str] = ""


class AgentEvalIntegrityError(AgentEvalError):
    """Sub-base for errors signaling that a run's trace/integrity contract is compromised.

    Per ADR-014's 4-sub-base scheme: `AgentEvalSafetyError`,
    `AgentEvalBudgetError`, `AgentEvalCompatError`, `AgentEvalIntegrityError`.
    Story 1b.2 ships only the Integrity sub-base; others are added by the
    stories that need them.

    Integrity errors typically signal:
        - Partial / missing trace data (e.g., `IncompleteTraceError`)
        - Determinism violations (Story 1b.6 will add `TierViolationError`)
        - Run-state contract violations (e.g., adapter reports impossible state)
    """


class IncompleteTraceError(AgentEvalIntegrityError):
    """Raised when a run's trace coverage is insufficient to compute reliable metrics.

    Per FR37 + ADR-016 L44: the kernel's `_check_mcp_coverage()` gate raises this
    when `AgentRunResult.metadata.mcp_coverage == "external_mixed"` AND the
    Library was NOT constructed with `allow_external_mcp_blind=True`.

    The error message includes:
        - What failed (uninstrumented MCP usage detected)
        - Why it failed (the adapter reported `external_mixed`)
        - One-line remediation (pass `allow_external_mcp_blind=True` OR fix
          the adapter coverage; link to `docs/contracts/mcp-coverage-detection.md`)

    Used as the default-deny posture per ADR-016's "loud refusal beats silent
    half-truth" principle.
    """

    error_code: ClassVar[str] = "INCOMPLETE_TRACE"
