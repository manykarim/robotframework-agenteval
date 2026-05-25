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

Active Phase-1 / Phase-1.5 / Phase-2 / Phase-3 carry-overs are tracked at [`docs/phase-1-5-carry-overs.md`](./docs/phase-1-5-carry-overs.md). 71 entries at Phase-1 close (2026-05-25), categorised XS/S/M/L by effort + owner. New items append per the `feedback_carry_over_catalog_gate` UPSTREAM gate; resolution moves them to per-story Change Log entries.

The Phase-1 retrospective at [`_bmad-output/planning-artifacts/phase-1-retrospective-2026-05-25.md`](./_bmad-output/planning-artifacts/phase-1-retrospective-2026-05-25.md) is the canonical Phase-1 scorecard. Per-epic retros live at `_bmad-output/implementation-artifacts/epic-*-retro-*.md`.

## Review methodology

The project's quality bar is enforced through 23 ratified `feedback_*` review-methodology norms (the project's auto-memory at `/home/many/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/MEMORY.md`; a public mirror at `docs/methodology/feedback-norms.md` is a deferred work item). Key load-bearing norms:

### Pre-create-story gates (Epic 1a retro + Epic 5 retro)

- **`feedback_spec_vs_ratified_doc_precheck`** — every story spec is cross-checked against ADRs + architecture + PRD before authoring. **44 consecutive uses with 100% real-drift catch rate** at Phase-1 close. Drift surfaced via AskUserQuestion BEFORE story commits.
- **`feedback_in_flight_spec_amendment`** — when dev decisions diverge from AC text mid-story, amend AC in SAME commit (no orphan drift).

### Carry-over discipline (Epic 4 + Epic 5 retros)

- **`feedback_carry_over_catalog_gate` UPSTREAM** — before flipping a story to `done`, grep new files for `DF-X-SY` markers + verify each is catalogued at `docs/phase-1-5-carry-overs.md` AND `deferred-work.md`. **24 consecutive stories** at Phase-1 close. Gate moved upstream to `/bmad-dev-story` Task N-1 per Epic 5 retro.
- **`feedback_caller_count_check`** — at story-close, grep new public helpers for caller count; 0 callers = `DF-X-SY` caller-gap entry. Derived from DF-5.5-DOGFOOD-2 (span helpers shipped Story 5.1, 0 callers, surfaced 5 stories later).

### Cross-LLM adversarial review (Epic 0 retro)

- **`feedback_review_methodology_norms`** (2026-05-17 ratification) — cross-LLM adversarial review is the project standard. Single-LLM review is insufficient; ≥2 LLM families required.
- **`feedback_codex_probe_fitness`** (Epic 2 retro) — Codex behavioral probes catch what type-system review can't (e.g., `Counter(names)` keyword collision false-clean).
- **`feedback_n_way_agreement_weight`** (Epic 2/4/5 retros) — 3-way HIGH findings = near-certain bugs (100% TP across Epics 2-5; extended to 11+ consecutive TPs by Epic 5 retro).
- **`feedback_citation_drift_first_class`** (Epic 1b retro) — cross-LLM review prompt MUST ask reviewer to re-derive each cited fact from source. 5/6 Epic 1a reviews had Claude solo 0 substantive findings while Codex caught real citation drift.
- **`feedback_third_llm_family_fallback`** (CANDIDATE Epic 10 retro, 2026-05-26) — when Claude + Codex CLIs degrade, kilocode/minimax substitutes. **9 consecutive substantive cross-LLM reviews** across Epic 8 + 9 + 10 retro-batch. Promote to ratified NEW at next retrospective. Operational invocation: `~/.kilo/bin/kilo run --auto --model minimax/MiniMax-M2.7 "$(cat /tmp/review-prompt.md)"`.

### Fake-green prevention (Epic 3 retro + Epic 5/8/9 retros)

- **`feedback_test_name_assertion_match`** — every test name MUST match its assertion body. **3 new violations caught in Epic 8 + 9 retro-batch** (kilocode/minimax review) beyond the 2 caught in Epic 3.
- **`feedback_dogfood_fake_green_precheck`** (Epic 5 retro) — dogfood `.robot` tests have higher fake-green base rate; pre-write fake-green precheck before flipping to review.
- **`feedback_ci_log_forensics`** (Epic 1a retro) — "passed" status is hypothesis not verdict; log-inspect `continue-on-error` steps + verify workflow inputs accepted.

### Empirical-shape forensics (Epic 2 + Epic 8 retros)

- **`feedback_listener_hook_api_surface_empirical_check`** (Epic 8 retro) — when extending an SDK hook, empirically verify the API surface via a probe (e.g., `dataclasses.fields()`, `dir()`). Story 8a.2 `data.tags` vs `result.tags` was load-bearing. Story 10.1 + 10.2 `usage` dict-shape probe caught silent zero-token bugs.
- **`feedback_contract_doc_invocation_smoke_test`** (Epic 8 retro) — contract docs documenting CLI/RF invocations MUST carry subprocess integration smoke test (caught broken `--listener AgentEval.telemetry.listener` module-path-only invocation).

### Interleaved dogfood (Epic 3 retro)

- **`feedback_interleaved_dogfood_load_bearing`** — interleaved dogfood is production correctness layer, NOT milestone gate. Story 3.3 caught DOGFOOD-FINDING-1 (stdio errlog crash) that escaped Story 3.1's 4-reviewer cross-LLM code review.
- **`feedback_dogfood_validation_ceiling`** (Epic 7 retro) — every `tests/dogfood/**/parity-checklist-*.md` MUST carry a top-of-file VALIDATION-CEILING line stating what the dogfood DOES and does NOT verify.

### Recovery + meta-norms (Epic 7 + Epic 8 retros)

- **`feedback_integration_test_forcing_function`** (Epic 8 retro) — when cross-LLM review degrades, end-to-end integration tests substitute as empirical-truth check. IS the mitigation, not the fix.
- **`feedback_retro_on_retro`** (Epic 7 retro) — BMAD retros benefit from the same cross-LLM adversarial review as story code-review (caught 2 HIGH on the Epic 7 retro draft + 3 HIGH + 5 MED + 3 LOW on the Epic 8 retro draft).
- **`feedback_honest_framing`** — atmospheric/honest positioning over hype; numeric bars not vibes; name trade-offs explicitly. The Phase-1 retro's "0 of 6 exit criteria fully satisfied" framing is the canonical example.

### Cross-LLM pipeline degradation + restoration (Epic 8 retro Action #1)

- **Degradation observed (Epic 8 close)**: Claude CLI returned 0-byte output on long prompts; Codex CLI rate-limited from Story 8a.1 onward. 8 consecutive stories shipped without substantive cross-LLM review across Epic 8 + 9.
- **Restoration (Epic 10 retro batch, 2026-05-26)**: third-LLM-family kilocode/minimax delivered substantive cross-reviews where Claude + Codex CLIs both failed silently. 8 HIGH patches applied across 7 retro-cross-reviewed stories (commit `16ee936`).
- **Open Action #1 follow-ups**: Codex quota check (step ii), in-loop circuit-breaker on ≥2 consecutive empty review artifacts (step iv). Both Phase-2 work-items.

For canonical worked examples: [Story 10.1 v0.4.0 review](./_bmad-output/implementation-artifacts/10-1-claude-agent-sdk-adapter.md#senior-developer-review-ai) + [Story 10.2 v0.5.0 3-stage review](./_bmad-output/implementation-artifacts/10-2-openai-agents-sdk-adapter.md#senior-developer-review-ai) + [Epic 8 + 9 kilo/minimax retro batch](./_bmad-output/implementation-artifacts/epic-8-9-kilo-minimax-cross-review-2026-05-26.md).
