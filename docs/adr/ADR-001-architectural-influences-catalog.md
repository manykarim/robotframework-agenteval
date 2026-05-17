# ADR-001: Architectural Influences Catalog

**Status:** stub (Amendments Log populated by Story 0.3; catalog body to be filled by Story 1a.3)
**Date:** 2026-05-17 (Amendments Log section); catalog body date pending Story 1a.3 ratification

## Stub notice

This file is intentionally a **partial stub** at the moment Story 0.3 (`amend-and-ratify-spike-dependent-adrs`) executed. Per the Story 0.3 ↔ Story 1a.3 coordination rules documented in the Story 0.3 spec file (§Coordination with Story 1a.3, rule 2):

> If Story 0.3 executes BEFORE Story 1a.3: Story 0.3 creates a minimal ADR-001 stub with only the Amendments Log populated. Story 1a.3 then fills in the rest of the catalog AROUND that stub — does NOT overwrite the Amendments Log.

Story 1a.3 (currently in `backlog` status as of 2026-05-17) owns the body of this catalog: the per-pattern table covering ~14 reviewed agentguard patterns + competitor MCP-eval projects + relevant standards, each with `adopt-verbatim` / `adapt` / `borrow-concept` / `explicitly-diverge` / `not-applicable` decisions and one-line rationale.

When Story 1a.3 executes, it MUST preserve the §Amendments Log section below verbatim — entries in that log are ratifications by Story 0.3 (Epic 0) and must not be overwritten.

## §Body (to be filled by Story 1a.3)

(Story 1a.3 fills this section. Story 0.3 leaves it empty by design.)

## §Amendments Log

Date-ordered log of ratifications that amended catalog entries OR ratified ADRs that depend on catalog patterns. Story 0.3 (Epic 0) writes ratifications for the 3 spike-dependent ADRs (ADR-004, ADR-016, ADR-018) here.

- **2026-05-17 — ADR-004 (renumbered from proposed ADR-007) ratified.** Hosted-MCP universal trace observation pattern accepted with empirical findings from Story 0.1 spike: handler-wrap at `Server.request_handlers[CallToolRequest]` validated across 3 transports (in-memory, stdio subprocess, streamable HTTP) under `pabot --processes 4` (75/75 runs clean). See `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` + `docs/adr/ADR-004-hosted-mcp-observation.md`.
- **2026-05-17 — ADR-016 (renumbered from proposed ADR-A6) ratified.** `mcp_coverage` field semantics ratified with D1 trust-floor (strongest complete path wins) + D4 adapter contract (Claude Code CLI / Copilot CLI / Generic LiteLLM detection responsibility split). See `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` §Related ADR-A6 amendment + `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` (cross-cutting confirmation) + `docs/adr/ADR-016-mcp-coverage-detection-default.md`.
- **2026-05-17 — ADR-018 (renumbered from proposed ADR-A8) ratified.** Sandbox Phase 1 policy + gate + Protocol accepted with NO spike-driven amendments to ADR-A8's substance. Story 0.2 confirmed cross-cuttingly (via the §Hand-off to Story 0.3 table row "ADR-A6 / ADR-A8 amendments needed? ✅ NO new amendments from Story 0.2") that per-test cleanup primitives do not conflict with the sandbox Protocol surface. Real sandbox subprocess lifecycle is a Phase-3 carry-over flagged in ADR-018 §Cross-cutting forward references. See `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` §Hand-off to Story 0.3 + `docs/adr/ADR-018-sandbox-phase-1-policy.md`.

(Story 1a.3 may append further entries when ratifying the other 15 non-spike ADRs; each entry follows the pattern `YYYY-MM-DD — ADR-NNN ratified. <one-line summary>. See <evidence>.`)
