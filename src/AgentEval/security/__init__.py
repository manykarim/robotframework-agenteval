"""AgentEval.security sub-package.

Sandbox Policy + NullSandbox default + SandboxBackend Protocol per ADR-018
(was ADR-A8; ratified 2026-05-17). Phase 1 ships policy + gate + Protocol;
bundled backend implementations (Docker / ephemeral-worktree / gVisor) ship
in Phase 3 via the `[project.entry-points."agenteval.sandboxes"]` discovery
mechanism.

Authored by Story 1a.1 per ADR-018 §Decision items 3 + 4 (correction applied
2026-05-17 during Story 1a.1 code review — initial 1a.1 deferred to Story
1a.6 in contradiction of the ratified ADR; the ADR takes precedence).
"""
