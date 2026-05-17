# Maintainers

Per NFR-MAINT-01, this document declares the project's maintenance posture.

## Current maintainers

- **Many Kasiriha** (sole maintainer)

## Maintenance posture

**robotframework-agenteval is a solo + AI-agent-assisted project.** That framing is load-bearing for what contributors and users can expect:

- **Reviews + decisions are author-driven.** Many writes the PRD, ratifies architecture, picks ADRs, and authors most ADR amendments. AI agents (Claude Code, Codex CLI, GitHub Copilot CLI) execute implementation, run code review cycles, and reproduce spike findings — but architectural decisions are explicitly human-owned.
- **Adversarial review is the project standard** (Epic 0 retro Norm #1, 2026-05-17). Every story passes through a `/bmad-code-review` cycle with at least one cross-model-family reviewer (e.g., writer's Claude + Codex or Copilot). Same-family reviews have correlated blind spots; cross-family review catches what single-LLM iteration misses.
- **Numeric claims are machine-verified before commit** (Epic 0 retro Norm #2). Word counts, file counts, leak counts, percent margins — pipe through `wc`, `grep -c`, or `find ... | wc -l` rather than eyeballing. Citation drift is the subtlest failure mode in documentation-heavy work.
- **Multi-agent reproductions sharing workspace state are serialized** (Epic 0 retro Norm #3). Never parallel-launch reproducers that compete for shared files, ports, or pabot processes.

## Triage SLA

Per NFR-MAINT-02:

- **Initial triage** within 5 business days for issues + PRs (best-effort; subject to maintainer availability).
- **Security issues**: see [SECURITY.md](./SECURITY.md) — accelerated path with disclosure embargo.
- **"Good first issue" labels** flag contributor-friendly entry points once the project ships its first release.

## Contributor surface

The contributor surface centers on:

- **Coding-agent adapters** — implementations of the `SubprocessAdapter` ABC for CLI-based agents. See `src/AgentEval/coding_agent/subprocess.py` (Epic 4 Story 4.x).
- **MCP server fixtures** — small MCP server implementations for testing agent tool-call behavior. See `tests/fixtures/mcp/`.
- **Sandbox backends** — once Phase 3 ships, third-party `SandboxBackend` Protocol implementations register via the `agenteval.sandboxes` entry-point group (ADR-018).
- **Conformance fixtures** — golden-trace JSON files per adapter per scenario, used by the conformance suite to verify Tier-1 adapter fidelity. See `tests/conformance/fixtures/`.

## Decision records

All architectural decisions live in [`docs/adr/`](./docs/adr/). The Architectural Influences Catalog ([ADR-001](./docs/adr/ADR-001-architectural-influences-catalog.md)) documents which patterns from reviewed reference projects (notably `robotframework-agentguard`) were adopted, adapted, or explicitly diverged from. **agentguard is an inspiration-only reference, not a dependency.** agenteval is free to evolve independently.

## Phase carry-overs

Active Phase-1 / Phase-1.5 / Phase-3 carry-overs are tracked in `_bmad-output/implementation-artifacts/deferred-work.md`. New items append; resolution moves them to per-story Change Log entries.
