# ADR-018: Sandbox Policy in Phase 1 — Policy + Gate + Protocol (Backends Deferred to Phase 3)

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-A8 in `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` §ADR-A8. Renumbered to ADR-018 per architecture.md project tree (`docs/adr/` subsection of the Complete Project Directory Structure). **No spike-driven amendments to ADR-A8's substance.** Story 0.2 cross-cutting confirmation only; see §Cross-cutting forward references below for separately-flagged Phase-3 carry-overs that are NOT part of ADR-A8's ratified text.

## Context

Per architecture.md Step-1 decision (frontmatter `step01Decisions.sandboxPolicyScope`), sandbox policy moves from PRD-anticipated Phase 3 deferral into Phase 1 with a tighter scope: Phase 1 ships policy + gate + Protocol; Phase 3 ships bundled backend implementations.

Agenteval inherits the sandbox-gate pattern from agentguard's ADR-013. The Architectural Influences Catalog (`docs/adr/ADR-001-architectural-influences-catalog.md`) will catalog this with an explicit `adopt` decision once Story 1a.3 populates its body (the catalog is currently a stub; the §Amendments Log section is the only populated content as of 2026-05-17).

The pattern: when an evaluation scenario requests code execution that crosses an agent's safety boundary, the library refuses unless a configured sandbox backend is present.

Phase 1's tight implementation scope: ship the policy + gate + Protocol surface, but ship `NullSandbox` as the default backend (which refuses every call). Real backends (Docker, ephemeral worktree, gVisor) are deferred to Phase 3.

## Decision

Phase 1 ships (verbatim from ADR-A8 proposed text):

1. **Sandbox Policy** adopted into agenteval's Architectural Influences Catalog (ADR-001) with `adopt` status — pattern borrowed from agentguard ADR-013, evaluated on merit per agenteval-not-agentguard-dependency principle. (Catalog entry to be authored by Story 1a.3; this ADR forward-references that entry.)
2. **`SandboxRequiredError(AgentEvalSafetyError)`** raised when Tier-3 code-execution scenarios are requested without a configured sandbox backend.
3. **`SandboxBackend` Protocol** published in `agenteval/security/protocols.py` as part of contributor-facing API. Minimal Protocol surface: `execute(code: str, language: str, timeout: float) -> SandboxResult`.
4. **Default backend: `NullSandbox`** — raises `SandboxRequiredError` on every call. Forces the user to either configure a real backend or opt out explicitly.

Phase 3 ships: bundled sandbox backend implementations (Docker, ephemeral worktree, gVisor optionally) — separate ratification cycle when backends are scoped.

## Rationale (verbatim from ADR-A8)

Policy + gate + Protocol have low implementation cost (~3 days) and high security-posture value — Day 1 sandbox-aware behavior even without backends; community contributors get the Protocol to implement their own backends in Phase 2 (any registered via `[project.entry-points."agenteval.sandboxes"]` — adds a 5th entry-point group; ADR-013 entry-points discovery to be updated to reflect this). Deferring backends keeps Phase 1 implementation scope honest.

## Consequences

- Epic 1a Story 1a.1 (Project Bootstrap) creates `src/AgentEval/security/` directory with `protocols.py` + `null_sandbox.py` + `policy.py`.
- Sandbox-aware behavior available from Day 1 of Phase 1, even without backends: agents calling Tier-3 code-execution keywords hit a clear `SandboxRequiredError` rather than executing unsafely.
- Community contributors can implement their own backends in Phase 2 by registering via `[project.entry-points."agenteval.sandboxes"]`. **Adds a 5th entry-point group** to ADR-013's entry-points discovery enumerated list (4 → 5 groups).

## Cross-cutting forward references (NOT amendments to ADR-A8)

The items below are forward-references surfaced during Story 0.3 ratification. They are **NOT amendments** to ADR-A8's ratified substance — they document Phase-3 / Story 1b.1 work that intersects with sandbox-backend design. Future ADRs covering Phase 3 sandbox backends will need to ratify these as their own decisions.

- **Sandbox subprocess lifecycle under per-test scope is UNVALIDATED by Story 0.2.** That spike tested MCP server cleanup only. A separate Phase-3 spike — once real backends ship — must validate that sandbox subprocesses respect per-test cleanup guarantees. This is a Phase-3 carry-over, NOT a Story 0.3 ratification gap.
- **MCP lifecycle manager (Epic 1b Story 1b.1's `src/AgentEval/_kernel/context.py`) integration.** When Phase 3 sandbox backends spawn subprocesses, they may need to integrate with the lifecycle-manager pattern defined by Story 0.2 spike (auto-installed SIGTERM handler converting SIGTERM → `sys.exit(0)` → atexit → reaping; `os.killpg` SIGTERM-then-SIGKILL escalation). Source: `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` §AC-0.2.5 trigger-boundary table. SIGKILL of the parent process is unrecoverable at any userspace layer; operator-level mitigation (systemd cgroup / container teardown) required. Phase-3 backend authors must decide whether to adopt the same model.
- **Real-rf-mcp validation is owed for Story 0.2 evidence** (not for ADR-018 itself; cross-cutting note only). Story 0.2 used `rf_mcp_substitute.py` rather than the real rf-mcp because the spike environment had no git access. The spike findings doc §Substitution disclosures lists this as a primary risk — sandbox-backend authors in Phase 3 should be aware that the per-test cleanup story is Linux-only, substitute-server-only at the time of this ratification.

## Alternatives (verbatim from ADR-A8)

- *Defer everything sandbox-related to Phase 3 (PRD's original framing)* — rejected: leaves security posture incoherent in Phase 1; agenteval borrows agentguard's `validate` operator gate without the parallel sandbox gate, creating an asymmetric safety story.
- *Ship a Docker backend in Phase 1* — rejected: Docker dep adds platform-specific install friction; bloats MVP install size; Windows + macOS Docker setup is non-trivial; conflicts with Phase 1 scope-honesty.
- *Ship no policy, only the Protocol* — rejected: confuses contributors about expected gate behavior.

## References

- Original proposed text: `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` §ADR-A8 (now flagged "⚠️ HISTORICAL — superseded" with breadcrumb pointing here).
- Story 0.2 cross-cutting confirmation that ADR-A8 needs no spike-driven amendments: `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` §Hand-off to Story 0.3 row "ADR-A6 / ADR-A8 amendments needed? ✅ NO new amendments from Story 0.2."
- Lifecycle manager forward-reference (Phase-3 carry-over): `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` §AC-0.2.5 (trigger-boundary table) + §`_kernel/context.py` draft.
- Real-rf-mcp Phase-1 carry-over: `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` §Substitution disclosures (primary risk #1) + `_bmad-output/implementation-artifacts/deferred-work.md`.
- Architecture context: `_bmad-output/planning-artifacts/architecture.md` Step-1 frontmatter (`step01Decisions.sandboxPolicyScope`) + project-tree `docs/adr/` subsection.
