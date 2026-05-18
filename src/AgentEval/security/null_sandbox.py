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

"""NullSandbox — the Phase-1 default backend that refuses every call.

Authored in Story 1a.1 per ADR-018 §Decision item 4 (ratified 2026-05-17):

    Default backend: `NullSandbox` raises `SandboxRequiredError` on every call
    (forces user to either configure a real backend or opt out explicitly).

Phase-1 NOTE on the error class: `SandboxRequiredError` is part of the
agenteval error hierarchy per ADR-A3 (renumbered to ADR-014 by Story 1a.3
when it ratifies the non-spike ADRs). That hierarchy lives at
`src/AgentEval/errors.py`, which Epic 1b Story 1b.1 authors. Until Epic 1b
lands `errors.py`, this NullSandbox raises `NotImplementedError` as the
Phase-1-honest stand-in. When `AgentEvalSafetyError` + `SandboxRequiredError`
land in `errors.py`, swap the `raise` line.

See `docs/adr/ADR-018-sandbox-phase-1-policy.md` + `docs/adr/ADR-A3-*.md`
(forthcoming via Story 1a.3) for the full ratification chain.
"""

from __future__ import annotations

from AgentEval.security.protocols import SandboxBackend, SandboxResult


class NullSandbox(SandboxBackend):
    """Refuses every execute() call.

    Phase-1 default. Forces the user to either:
    1. Configure a real sandbox backend (Phase 3 ships Docker / ephemeral-worktree
       / gVisor; community can register backends earlier via entry-points).
    2. Explicitly opt out via library-init kwarg (mechanism TBD per Epic 6 work).
    """

    def execute(self, code: str, language: str, timeout: float) -> SandboxResult:
        """Refuse every call.

        TODO (Epic 1b Story 1b.1): replace `NotImplementedError` with
        `AgentEval.errors.SandboxRequiredError` once `errors.py` ships per
        ADR-A3 (→ ADR-014). The error message + hint surface is FR59-required
        (file path / line / fix suggestion in `__str__`).
        """
        raise NotImplementedError(
            "NullSandbox refuses every execute() call. To run Tier-3 code-execution "
            "scenarios, configure a real SandboxBackend implementation via the "
            "`agenteval.sandboxes` entry-point group (ADR-018). Phase 1 ships no "
            "bundled backends; Phase 3 ships Docker / ephemeral-worktree / gVisor."
        )
