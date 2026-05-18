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

"""SandboxBackend Protocol — contributor-facing API for Phase 3 sandbox backends.

Authored in Story 1a.1 per ADR-018 §Decision item 3 (ratified 2026-05-17):

    `SandboxBackend` Protocol published in `agenteval/security/protocols.py`
    as part of contributor-facing API. Minimal Protocol surface:
    `execute(code: str, language: str, timeout: float) -> SandboxResult`.

Phase 1 ships the Protocol + NullSandbox default; bundled backend
implementations (Docker, ephemeral worktree, gVisor) ship in Phase 3 via the
`[project.entry-points."agenteval.sandboxes"]` discovery mechanism.

See `docs/adr/ADR-018-sandbox-phase-1-policy.md` for the full ratification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SandboxResult:
    """Result of a sandboxed code execution.

    Phase-1 minimal surface; Phase 3 backends may extend with structured
    exit-code / stderr / metrics fields as backends ship.
    """

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


@runtime_checkable
class SandboxBackend(Protocol):
    """Contract for sandbox backends that execute Tier-3 code-execution scenarios.

    Phase 1 ships `NullSandbox` (refuses every call); Phase 3 ships Docker /
    ephemeral-worktree / gVisor backends. Community contributors implement this
    Protocol and register via the `[project.entry-points."agenteval.sandboxes"]`
    discovery group (ADR-013 + ADR-018).
    """

    def execute(self, code: str, language: str, timeout: float) -> SandboxResult:
        """Execute `code` (written in `language`) with a wall-clock `timeout` (seconds).

        Returns a `SandboxResult`. Backends MUST NOT execute code in the host
        environment — that's what makes a sandbox a sandbox. The Phase-1
        default (`NullSandbox`) refuses every call by raising NotImplementedError;
        contributors substitute their backend via entry-point discovery.
        """
        ...
