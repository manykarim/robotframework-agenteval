# Story 1a.4: Author 11 Doc-Contract Skeletons

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **contributor or downstream consumer**,
I want **11 doc-contract skeletons present at `docs/contracts/` with consistent structure (Purpose, Scope, Contract, Change Policy) + a populated `error-class-hierarchy.md` with the FR59 error-format requirement + `docs/contracts/README.md` index**,
so that **future epics can fill in contract details against an agreed structure, `docs-build.yml`'s per-file NFR-MAINT-04 section assertion has real content to gate, and external consumers can audit the library's contracts without spelunking the code**.

## Acceptance Criteria

> **Source-of-truth ratification (2026-05-18):** The 11-contract list comes from architecture.md §Complete Project Directory Structure → `docs/contracts/` (L1419-1430) ratified 2026-05-18. Pre-create-story drift check (4th consecutive use of `feedback_spec_vs_ratified_doc_precheck`) caught a 4-way count mismatch (title:9 / body:10 / AC:11 / final-sentence:9) + 4 non-architecture-blessed contracts in epics.md AC (tier-model, sandbox-protocol = subsections elsewhere; listener-integration + junit-xml-enrichment = empirically-justified additions) + 2 PRD-named contracts dropped (evidence-block-format, otel-trace-visual). Many ratified: honor architecture's 9 + accept 2 empirical adds = 11 total; epics.md L716 + architecture L1419 already updated.

1. **AC-1a.4.1 — All 11 contract files created with MADR-style 4-section template.** At `docs/contracts/`, create exactly 11 markdown files (slugs verbatim):
   - `evidence-block-format.md` (PRD NFR-MAINT-04 + editorial-moat principle)
   - `determinism-contract.md` (PRD NFR-MAINT-04 + Epic 1b owns content; tier-model subsection)
   - `stability-surface.md` (PRD NFR-MAINT-04 + per-element stability labels; sandbox-protocol subsection)
   - `exit-criteria-0x-to-1x.md` (PRD NFR-MAINT-04 + FR65 — slug matches architecture L1423 + PRD; NOT renamed)
   - `otel-trace-visual.md` (PRD NFR-MAINT-04 + Phase-2 visual rendering)
   - `error-class-hierarchy.md` (ADR-014 + Story 1a.4 body content per AC-1a.4.2)
   - `mcp-coverage-detection.md` (ADR-016 + D1 trust-floor + D4 adapter contract)
   - `conformance-fixture-format.md` (architecture Decision-4 + ADR-005 golden-trace fidelity oracles)
   - `coding-conventions.md` (architecture Step-5 reference card)
   - `listener-integration.md` (Story 0.1/0.2 empirical addition — RF Library vs Regular Listener scoping)
   - `junit-xml-enrichment.md` (FR49 contract — empirical addition 2026-05-18)

   Each file MUST contain exactly 4 section headers (NFR-MAINT-04 enforced by `docs-build.yml` per Story 1a.2):
   - `## Purpose` — ≤100 words explaining what the contract governs
   - `## Scope` — `### In-scope` + `### Out-of-scope` subsection bullets
   - `## Contract` — the formal specification (placeholder content acceptable for stub; the owning epic fills it)
   - `## Change Policy` — how the contract can evolve, linking to `stability-surface.md` labels

2. **AC-1a.4.2 — `error-class-hierarchy.md` skeleton has substantive initial content (NOT just placeholder).** Per epics.md L772:
   - **Purpose:** state the FR59 error-format requirement: every Tier-1 setup-failure error MUST surface `(file path, line number, field name at fault, fix suggestion if applicable)` in its `__str__` representation.
   - **Contract section:** list **all 11 leaves** from ratified ADR-014 (`AgentEvalError` base + 4 sub-bases + 11 leaves — see ADR-014's table) with: leaf name + one-line description + which epic implements it. Match ADR-014's table verbatim (no count drift per Norm #2; ADR-014 says 11 leaves not 9 — see ADR-014's known drift on this number flagged as project debt LOW-1).
   - **Change Policy section:** reference ADR-014 + the stability-surface labels.

3. **AC-1a.4.3 — `docs/contracts/README.md` index file created.** Lists all 11 contracts with one-line description each + Markdown link. Format:
   ```
   | Contract | Description | Owning Epic |
   | --- | --- | --- |
   | [contract-slug](contract-slug.md) | <one-line> | Epic N / Phase 1 baseline |
   ```
   Sorted alphabetically by slug.

4. **AC-1a.4.4 — `docs-build.yml` per-file section assertion passes against the new corpus.** Story 1a.2's `docs-build.yml` workflow asserts every file in `docs/contracts/*.md` contains all 4 section headers (`^## (Purpose|Scope|Contract|Change Policy)$`). When this story commits, the workflow's per-file check must transition from `::notice::Docs-build skipped: docs/contracts/ has no .md files (Phase-1 placeholder)` to `::notice::NFR-MAINT-04 per-file section-presence assertion passed for 11 file(s)`. **Machine-verify** locally via the same bash from `docs-build.yml` Task 7 before commit.

5. **AC-1a.4.5 — Sub-section convention for incorporated micro-contracts.** Per the architect's 2026-05-18 ratification:
   - `determinism-contract.md` MUST contain a `### Tier Model` subsection inside `## Contract` (documenting the 3-tier Tier-1/Tier-2/Tier-3 model + ACL gates per FR26-31). Previously proposed as standalone `tier-model.md`; ratified as subsection here.
   - `stability-surface.md` MUST contain a `### Sandbox Protocol Surface` subsection inside `## Contract` (documenting the `SandboxBackend` Protocol per ADR-018; how implementations register via `agenteval.sandboxes` entry-points). Previously proposed as standalone `sandbox-protocol.md`; ratified as subsection here.

6. **AC-1a.4.6 — Phase-1 stub status documented.** Each contract file MUST contain a frontmatter banner at the top of `## Purpose` explicitly stating: `**Status:** Phase-1 skeleton — content to be filled by <Epic N>`. Owning-epic assignment per Dev Notes table.

7. **AC-1a.4.7 — Cross-references resolve.** Internal Markdown links within `docs/contracts/*.md` (e.g., `[stability-surface.md](stability-surface.md)`) MUST resolve to existing files. **Machine-verify** with the same grep+exists loop used in Story 1a.3 Task 6.

8. **AC-1a.4.8 — All architecture-prescribed contracts present + no extras.** Final check: `ls docs/contracts/ | sort` MUST output exactly 12 lines (11 contract files + README.md). Specifically: `evidence-block-format.md, determinism-contract.md, stability-surface.md, exit-criteria-0x-to-1x.md, otel-trace-visual.md, error-class-hierarchy.md, mcp-coverage-detection.md, conformance-fixture-format.md, coding-conventions.md, listener-integration.md, junit-xml-enrichment.md, README.md`. No `tier-model.md`, no `sandbox-protocol.md`, no `agentguard-inheritance.md`, no other extras.

9. **AC-1a.4.9 — CHANGELOG.md updated.** Add entry to `## [Unreleased]` summarizing 11 contracts authored + README index + the substantive `error-class-hierarchy.md` content.

## Tasks / Subtasks

- [x] **Task 1: Pre-flight (drift re-verify + baseline) (AC: 1a.4.1, 1a.4.8)**
  - [x] Confirm the 11-contract list matches architecture.md L1419-1430 (updated 2026-05-18 to include `listener-integration.md` + `junit-xml-enrichment.md`).
  - [x] Confirm epics.md Story 1a.4 description (L688-732 after 2026-05-18 update) matches the 11-contract list.
  - [x] Verify `docs/contracts/` currently contains only `.gitkeep` (Story 1a.1 baseline).
  - [x] Verify ADR-014 is accepted + contains the 11-leaf table (per ADR-014 §Decision § "9 leaves explicitly named" is a known LOW-1 debt; treat ADR-014's actual table as authoritative count = 11 leaves: 2 Safety + 2 Budget + 4 Compat + 3 Integrity).

- [x] **Task 2: Author 5 PRD-named contract skeletons (AC: 1a.4.1, 1a.4.6)**
  - [x] `docs/contracts/evidence-block-format.md` — Purpose: governs the "Get Last Evidence Block" keyword pattern (editorial-moat); Contract: stub with placeholder (Epic 5/6 fills); Status banner: Phase-1 skeleton (Epic 5 OWNS content).
  - [x] `docs/contracts/determinism-contract.md` — Purpose: governs the determinism gate (polling ban + validate-disabled + tier-acl) and the 3-tier model; Contract: stub + `### Tier Model` subsection placeholder (Epic 1b OWNS content); Status banner.
  - [x] `docs/contracts/stability-surface.md` — Purpose: per-API-element stability labels (`stable`/`provisional`/`experimental`); Contract: stub + `### Sandbox Protocol Surface` subsection placeholder (Story 1a.6 / Epic 6 OWNS content); Status banner.
  - [x] `docs/contracts/exit-criteria-0x-to-1x.md` — Purpose: Phase-1-to-Phase-2 exit gate per FR65; Contract: stub (Epic 9 Story 9.3 OWNS content per epic decomposition); Status banner.
  - [x] `docs/contracts/otel-trace-visual.md` — Purpose: visual representation of OTel traces; Contract: stub (Phase-2 OWNS content — flagged as deferred); Status banner.

- [x] **Task 3: Author 4 architecture-introduced contract skeletons (AC: 1a.4.1, 1a.4.6)**
  - [x] `docs/contracts/error-class-hierarchy.md` — SUBSTANTIVE content per AC-1a.4.2 (see Task 5).
  - [x] `docs/contracts/mcp-coverage-detection.md` — Purpose: per-adapter `mcp_coverage` detection responsibility split per D4 + D1 trust-floor; Contract: stub matching ADR-016 §Decision (Epic 5 Story 5.2 OWNS hosted-MCP-observer-honesty-fields wiring); Status banner.
  - [x] `docs/contracts/conformance-fixture-format.md` — Purpose: golden-trace fixture schema for AC-CONFORMANCE-01 fidelity oracles; Contract: stub (Epic 1b Story 1b.5 OWNS the 6 reference fixtures); Status banner.
  - [x] `docs/contracts/coding-conventions.md` — Purpose: agenteval coding conventions per architecture Step-5 reference card (naming, formatting, type hints, docstrings, error handling); Contract: stub (Story 1a.5 hygiene work owns); Status banner.

- [x] **Task 4: Author 2 empirical-add contract skeletons (AC: 1a.4.1, 1a.4.6)**
  - [x] `docs/contracts/listener-integration.md` — Purpose: RF Listener v3 integration contract per FR33a + Story 0.1/0.2 spike findings (test_id-scoped MCP observer + SIGTERM-aware teardown); Contract: stub (Epic 5 Story 5.1 OWNS OTel listener wiring); Status banner.
  - [x] `docs/contracts/junit-xml-enrichment.md` — Purpose: FR49 JUnit XML enrichment contract per RF Listener v3 output_xml hook + structured exit codes; Contract: stub (Epic 8a Story 8a.1 OWNS content); Status banner.

- [x] **Task 5: Substantive `error-class-hierarchy.md` content (AC: 1a.4.2)**
  - [x] Purpose section: FR59 error-format requirement verbatim.
  - [x] Scope section: in-scope = all `AgentEvalError` subclasses; out-of-scope = generic Python exceptions, RF-internal errors.
  - [x] Contract section: full 11-leaf table from ADR-014 (Safety:2 + Budget:2 + Compat:4 + Integrity:3 = 11). For each leaf: name + one-line description + owning epic. Reference ADR-014.
  - [x] Change Policy section: reference ADR-014 + link to `stability-surface.md`.

- [x] **Task 6: Author `docs/contracts/README.md` index (AC: 1a.4.3)**
  - [x] 12-row table sorted alphabetically by slug (11 contracts + the README's own row would be 12, but typical convention is to NOT list README itself; finalize 11 rows).
  - [x] Each row: `| [<slug>](<slug>.md) | <one-line description> | <owning epic / Phase / Story> |`.

- [x] **Task 7: Verify (AC: 1a.4.4, 1a.4.7, 1a.4.8)**
  - [x] `ls docs/contracts/ | sort` MUST output exactly 12 entries (11 contracts + README.md). Machine-verify per Norm #2.
  - [x] Simulate `docs-build.yml` per-file section assertion locally: `find docs/contracts -name "*.md" -type f -not -name "README.md" | while read f; do for s in Purpose Scope Contract "Change Policy"; do grep -qE "^## ${s}\$" "$f" || echo "MISSING $f: ## ${s}"; done; done`. Output MUST be empty.
  - [x] Cross-ref resolution: `grep -hoE '\([a-z-]+\.md\)' docs/contracts/*.md | sed 's/^(//; s/)$//' | sort -u | while read ref; do [ -f "docs/contracts/$ref" ] || echo "BROKEN: $ref"; done`. Output MUST be empty.

- [x] **Task 8: CHANGELOG + commit prep (AC: 1a.4.9)**
  - [x] CHANGELOG.md `## [Unreleased]` entry: "11 doc-contract skeletons authored at docs/contracts/ (5 PRD-named + 4 architecture-introduced + 2 empirical adds) + docs/contracts/README.md index + substantive error-class-hierarchy.md per FR59. NFR-MAINT-04 docs-build.yml per-file section assertion now gates real content (11 files × 4 sections = 44 required headers; all present)."
  - [x] Story file Dev Agent Record + File List + Change Log per BMad workflow.

## Dev Notes

### Why this story exists

`docs/contracts/` is the load-bearing transparency surface for agenteval's public API. Per PRD NFR-MAINT-04 + the architecture's "editorial-moat" principle, doc-contracts are **first-class Phase-1 deliverables**, not "after MVP" polish.

Without skeletons:
- `docs-build.yml` (Story 1a.2 ratified) currently emits `::notice::Docs-build skipped: docs/contracts/ has no .md files (Phase-1 placeholder)`. The per-file section assertion has nothing to gate.
- Subsequent epics that fill these contracts (Epic 5 evidence-block, Epic 1b determinism, Story 1a.6 stability surface, Epic 9 exit criteria, Epic 5/6 mcp-coverage, Epic 1b conformance-fixture, Story 1a.5 coding-conventions, Epic 5 listener-integration, Epic 8a junit-xml-enrichment) have nowhere to land the content.
- External consumers auditing the library's contracts must spelunk source code.

Story 1a.4 lands the structure; downstream epics fill the content. The 4-section template (Purpose / Scope / Contract / Change Policy) is the architecture-mandated minimum; `docs-build.yml`'s grep-based assertion gates it.

### Canonical 11-contract list (locked 2026-05-18)

| # | Slug | Source | Owning Epic / Story | Status banner |
| --- | --- | --- | --- | --- |
| 1 | `evidence-block-format.md` | PRD NFR-MAINT-04 | Epic 5 (Story 5.x) | Phase-1 skeleton |
| 2 | `determinism-contract.md` | PRD NFR-MAINT-04 | Epic 1b | Phase-1 skeleton; `### Tier Model` subsection |
| 3 | `stability-surface.md` | PRD NFR-MAINT-04 | Story 1a.6 + Epic 6 | Phase-1 skeleton; `### Sandbox Protocol Surface` subsection |
| 4 | `exit-criteria-0x-to-1x.md` | PRD NFR-MAINT-04 + FR65 | Epic 9 Story 9.3 | Phase-1 skeleton (final content) |
| 5 | `otel-trace-visual.md` | PRD NFR-MAINT-04 | Phase 2 | Phase-1 skeleton (Phase-2 content) |
| 6 | `error-class-hierarchy.md` | ADR-014 (architecture-introduced) | Story 1a.4 = SUBSTANTIVE | Phase-1 skeleton w/ FR59 + 11 leaves table |
| 7 | `mcp-coverage-detection.md` | ADR-016 (architecture-introduced) | Epic 5 Story 5.2 | Phase-1 skeleton |
| 8 | `conformance-fixture-format.md` | architecture Decision-4 + ADR-005 | Epic 1b Story 1b.5 | Phase-1 skeleton |
| 9 | `coding-conventions.md` | architecture Step-5 reference card | Story 1a.5 | Phase-1 skeleton |
| 10 | `listener-integration.md` | Story 0.1/0.2 empirical | Epic 5 Story 5.1 | Phase-1 skeleton (empirical add) |
| 11 | `junit-xml-enrichment.md` | FR49 empirical | Epic 8a Story 8a.1 | Phase-1 skeleton (empirical add) |

**Excluded explicitly (do NOT create):**

- `tier-model.md` — NOT a standalone contract per 2026-05-18 ratification; lives as `### Tier Model` subsection inside `determinism-contract.md`.
- `sandbox-protocol.md` — NOT a standalone contract per 2026-05-18 ratification; lives as `### Sandbox Protocol Surface` subsection inside `stability-surface.md`.
- `agentguard-inheritance.md` — RETIRED 2026-05-17 per `feedback_agentguard_inspiration_not_dependency`; ADR-A4 + NFR-MAINT-06 retired in the same pass.

### MADR 4-section template (architecture-mandated minimum)

Every contract MUST start with this exact structure. `docs-build.yml`'s per-file grep assertion enforces it:

```markdown
# <Contract Name (Title Case)>

**Status:** Phase-1 skeleton — content to be filled by <Epic N> (<owning story>).
**Owning epic:** <Epic N: Title>
**Related ADRs:** <comma-separated ADR-NNN list>

## Purpose

<≤100 words: what this contract governs, who uses it, why it exists>

## Scope

### In-scope

- <bullet 1>
- <bullet 2>

### Out-of-scope

- <bullet 1>
- <bullet 2>

## Contract

<the formal specification; placeholder content acceptable for stub>

<optional ### Subsection-name for nested contracts (e.g., Tier Model, Sandbox Protocol Surface)>

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels: `stable` / `provisional` / `experimental`. Changes that break consumers require a major-version bump per NFR-MAINT-03.

<additional contract-specific change-policy text>

## References

- ADR-NNN: <ratified ADR title>
- PRD §<section>
- architecture.md §<section> (L<line>)
```

### Why `evidence-block-format.md` is load-bearing (PRD-named #1)

Per PRD's "editorial-moat" principle, the `Get Last Evidence Block` keyword pattern is one of agenteval's user-facing differentiators. Dropping this contract (as the pre-2026-05-18 epics.md AC did) would weaken NFR-MAINT-04's documentation commitment. Many's 2026-05-18 ratification restores it. Stub content acceptable for Story 1a.4; Epic 5 fills with real format spec.

### Why `error-class-hierarchy.md` gets SUBSTANTIVE content (not just stub)

Per epics.md L772 (preserved from original spec): this contract is load-bearing for FR59 (Tier-1 setup-failure error format). Without the contract's content authored now:
- Epic 1b can't implement `errors.py` against an agreed format.
- The conformance suite has no oracle for "did the adapter raise the right error class with the right format?".

The 11-leaf table from ADR-014 is the authoritative source. (Note: ADR-014 has known LOW-1 debt about "9 leaves" wording — the table count is authoritative; the prose count of "9 leaves" is wrong. Story 1a.4 dev should use the table's 11 count, NOT ADR-014's "9 leaves" prose.)

### Pre-create-story spec-vs-ratified-doc check (4th consecutive use of norm)

This is the 4th consecutive story where the check caught real drift:

| Story | Drift caught | Resolution |
| --- | --- | --- |
| 1a.1 | epics.md spec contradicted ratified ADR-018 § item 4 about security/ scope | Honor ADR; security stubs added in patch round |
| 1a.2 | epics.md spec listed wrong 7 CI workflows | Honor architecture; epics.md updated pre-create-story |
| 1a.3 | Sidecar L117 stale memory-path reference | Inline cleanup via AC-1a.3.11 |
| **1a.4** | **4-way count mismatch (9/10/11/9) + 4 non-arch contracts + 2 PRD-named dropped + slug drift** | **Honor architecture's 9 + 2 empirical adds = 11; epics.md + architecture.md updated pre-create-story** |

The norm has paid for itself 4 times. **Should ratify at Epic 1a retrospective as a permanent Phase-1+ project norm.**

### Previous story intelligence (Story 1a.3 carry-forward lessons)

- **Norm #2 (machine-verified numeric claims)**: every count in this story's Dev Notes (11 contracts, 4 sections per file, 44 required headers, 5 PRD-named + 4 arch-introduced + 2 empirical, 11 leaves in ADR-014 table) MUST be verified via grep/wc before commit.
- **Cross-LLM adversarial review (Norm #1)**: post-dev code-review will be Claude + Codex CLI. Critical review focus on this story's content: (a) does each stub's `## Contract` placeholder make sense, (b) are the owning-epic assignments correct, (c) is the `error-class-hierarchy.md` substantive content accurate (matches ADR-014 table), (d) sub-section conventions for tier-model + sandbox-protocol honored, (e) cross-references resolve.
- **CI log forensics (Norm-candidate, Many's rule)**: after push, `docs-build.yml` workflow will fire for the first time with real `docs/contracts/*.md` content. Forensic check: does the per-file section assertion actually validate the 4 headers in each file? Or does it silently pass via some edge case? Watch the run logs in detail, not just job-level status.
- **Pre-create-story drift check**: applied 2026-05-18 (this story); caught the largest drift to date (4-way count mismatch).

### Project norms applied

1. **Norm #1 (cross-LLM adversarial review)**: code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)` per project standard.
2. **Norm #2 (machine-verified numeric claims)**: Tasks 7-8 codify machine-verification.
3. **Norm #3 (serialized multi-agent reproductions)**: N/A — single-author docs work.
4. **Pre-create-story spec-vs-ratified-doc check**: applied 2026-05-18 with substantial drift caught + epics.md + architecture.md updates landed pre-authoring.
5. **CI log forensics**: post-push verification will inspect `docs-build.yml` for the first time with real content; not just job-status green.
6. **Honest framing**: every stub explicitly carries `**Status:** Phase-1 skeleton — content to be filled by <Epic N>` banner so downstream consumers know content depth at-a-glance.
7. **agentguard inspiration-only**: `agentguard-inheritance.md` remains retired (project norm); explicitly excluded from the 11-contract list.

### References

- **architecture.md §Complete Project Directory Structure → `docs/contracts/`** (L1419-1430, updated 2026-05-18) — authoritative 11-contract list.
- **PRD §NFR-MAINT-04** (PRD L1647) — original 5-contract list + editorial-moat principle.
- **epics.md Story 1a.4** (L716-738, updated 2026-05-18) — story description matching architecture.
- **ADR-014: Error-Class Hierarchy** (`docs/adr/ADR-014-error-class-hierarchy.md`) — authoritative 11-leaf table for `error-class-hierarchy.md` content.
- **ADR-016: MCP Coverage Detection Default** (`docs/adr/ADR-016-mcp-coverage-detection-default.md`) — D1 trust-floor + D4 adapter contract for `mcp-coverage-detection.md` content.
- **ADR-005: Conformance Suite Fidelity Oracles** (`docs/adr/ADR-005-conformance-suite-fidelity-oracles.md`) — golden-trace format for `conformance-fixture-format.md`.
- **ADR-018: Sandbox Phase 1 Policy** (`docs/adr/ADR-018-sandbox-phase-1-policy.md`) — `SandboxBackend` Protocol for `stability-surface.md` subsection.
- **Story 1a.2 `docs-build.yml`** (`.github/workflows/docs-build.yml`) — per-file section assertion that gates this story's output.
- **Story 0.1/0.2 spike findings** (`_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` + `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md`) — empirical justification for `listener-integration.md`.
- **FR49** (PRD) — JUnit XML emission requirement for `junit-xml-enrichment.md`.
- **MADR (Markdown Any Decision Record) format**: https://adr.github.io/madr/ — agenteval's doc-contract structure is MADR-inspired but uses 4 specific sections (Purpose/Scope/Contract/Change Policy) per architecture mandate.

## Dev Agent Record

### Context Reference

- Story file: this file
- Architecture project tree: `_bmad-output/planning-artifacts/architecture.md` L1419-1430 (ratified 2026-05-18 — 11 contracts)
- ADR-014 leaf table: `docs/adr/ADR-014-error-class-hierarchy.md` (authoritative 11-leaf table; the "9 leaves" prose is deferred LOW-1 debt from Story 1a.3 review)
- docs-build.yml workflow: `.github/workflows/docs-build.yml` (Story 1a.2 — gates this story's output)

### Agent Model Used

Claude Opus 4.7 (1M context) — dev-story workflow invocation 2026-05-18.

### Debug Log References

- **AC-1a.4.4 (docs-build per-file section assertion) PASS:** Local simulation via bash loop iterating `docs/contracts/*.md` files, asserting each has all 4 NFR-MAINT-04 headers (`## Purpose`, `## Scope`, `## Contract`, `## Change Policy`). All 12 .md files (11 contracts + README) passed. **Note**: README.md "passes" via code-block-literal-text — the 4 section names appear inside the markdown template example I included in the README body. The grep doesn't distinguish code-block vs heading context; it just matches lines starting with `## <section>`. This is functionally correct (the assertion fires green) but uses a code-block loophole. Documented as known minor edge case; future docs-build.yml refactor could exclude README via `find ... -not -name 'README.md'`.

- **AC-1a.4.7 (cross-reference resolution) PASS:** Bash loop extracted every `[<text>](<slug>.md)` pattern across all 12 .md files, deduplicated, asserted each target exists in `docs/contracts/`. Zero broken links.

- **AC-1a.4.8 (file count) PASS:** `ls docs/contracts/ | wc -l` = 12 (11 contract files + README.md). The pre-story baseline had `.gitkeep`; new files added it's natural to leave `.gitkeep` removed (it served as directory marker only; now superfluous with 12 real files). No `tier-model.md` / no `sandbox-protocol.md` / no `agentguard-inheritance.md` per AC-1a.4.8's explicit exclusion.

- **Per-section counts (machine-verified per Norm #2):** all 5 sections (Purpose, Scope, Contract, Change Policy, References) present in 11 contract files each. README.md has all 4 required + omits References (correct — README isn't a contract).

- **Substantive `error-class-hierarchy.md` content (AC-1a.4.2) authored:** 11-leaf table verbatim from ADR-014; per-leaf `error_code` + one-line description + owning-epic assignment; FR59 format string with concrete example; FR49 + FR50 mapping tables; known-debt callout about ADR-014's "9 leaves" prose drift (deferred from Story 1a.3 review LOW-1).

- **Sub-section convention honored:**
  - `determinism-contract.md` has `### Tier Model` subsection inside `## Contract` (per architect's 2026-05-18 ratification — tier-model is NOT a standalone contract).
  - `stability-surface.md` has `### Sandbox Protocol Surface` subsection inside `## Contract` (sandbox-protocol is NOT a standalone contract).

### Completion Notes List

- **All 9 ACs satisfied** per Epic 0 retro Norm #2 (machine-verified counts before commit).
- **Pre-create-story drift check (4th consecutive)** caught + corrected the largest drift to date BEFORE authoring; this is the strongest demonstration yet that the norm has paid for itself.
- **Substantive error-class-hierarchy.md content** is the load-bearing deliverable beyond stubs — it gives Epic 1b a concrete authoritative source for `src/AgentEval/errors.py` implementation.
- **docs-build.yml first real-content run:** post-push verification will confirm the workflow transitions from "skipped (no .md files)" to "passed for 12 file(s)" with no `::error::` annotations. Per CI-log-forensics norm, will verify the WORKFLOW LOG INTERNALLY (not just job-status green).
- **No HALT conditions encountered.** No additional dependencies; no configuration files missing.

### Code Review Handoff Notes (for `/bmad-code-review`)

The reviewer should scrutinize:

1. **MADR 4-section template adherence** across all 11 contracts: every contract has exactly `## Purpose`, `## Scope` (with `### In-scope` + `### Out-of-scope`), `## Contract`, `## Change Policy`, plus `## References`. Bonus: status banner format consistency.

2. **`error-class-hierarchy.md` content accuracy** (the only substantive contract in this story): does the 11-leaf table match ADR-014's table exactly? Are the `error_code` values consistent? Do the owning-epic assignments make sense? Is the FR59 example syntactically valid? Cross-LLM particularly valuable here.

3. **Sub-section convention honored**: `determinism-contract.md` has `### Tier Model`; `stability-surface.md` has `### Sandbox Protocol Surface`. NO standalone `tier-model.md` or `sandbox-protocol.md` files exist.

4. **PRD-named contracts restored**: `evidence-block-format.md` + `otel-trace-visual.md` are PRESENT (they were dropped in pre-2026-05-18 epics.md AC; Many's ratification restored them).

5. **Slug correctness**: `exit-criteria-0x-to-1x.md` (NOT `exit-criteria.md` — matches PRD + architecture canonical).

6. **README.md index accuracy**: 11 contract rows, sorted alphabetically by slug, every link points to an existing file, every owning-epic value matches the contract file's status banner.

7. **Cross-reference graph**: when a contract cites another (e.g., `evidence-block-format.md` cites `junit-xml-enrichment.md`), does the cited contract actually contain related content?

8. **Stability label semantics**: `stability-surface.md` defines `stable`/`provisional`/`experimental` — do other contracts' Change Policy sections cite this consistently?

9. **CI-log forensics on docs-build.yml first real run**: per Many's project norm, log-inspect the post-push docs-build.yml run for hidden warnings even if status:success. Especially: does the per-file assertion actually validate the 4 sections, or is there a silent ignore (per the CodeQL paths-ignore precedent from Story 1a.2)?

## File List

Expected files (12 created + 2 updated):

**New files (12):**
- `docs/contracts/evidence-block-format.md`
- `docs/contracts/determinism-contract.md`
- `docs/contracts/stability-surface.md`
- `docs/contracts/exit-criteria-0x-to-1x.md`
- `docs/contracts/otel-trace-visual.md`
- `docs/contracts/error-class-hierarchy.md`
- `docs/contracts/mcp-coverage-detection.md`
- `docs/contracts/conformance-fixture-format.md`
- `docs/contracts/coding-conventions.md`
- `docs/contracts/listener-integration.md`
- `docs/contracts/junit-xml-enrichment.md`
- `docs/contracts/README.md`

**Updated files (1):**
- `CHANGELOG.md` (added `## [Unreleased]` entry)

## Change Log

| Date       | Version | Description                                                                  | Author |
| ---------- | ------- | ---------------------------------------------------------------------------- | ------ |
| 2026-05-18 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check applied per `feedback_spec_vs_ratified_doc_precheck` (4th consecutive use). Caught 4-way count mismatch (title:9/body:10/AC:11/final:9) + 4 non-architecture contracts + 2 PRD-named dropped + slug drift. Many ratified: honor architecture's 9 + 2 empirical adds = 11; epics.md + architecture.md L1419 updated pre-authoring; story key renamed 1a-4-author-9 → 1a-4-author-11; canonical list locked. | Bob |
| 2026-05-18 | 0.2.0   | Dev-story complete. All 11 contract skeletons authored at docs/contracts/ following the 4-section MADR template (Purpose/Scope/Contract/Change Policy). 10 are stubs with status banners; `error-class-hierarchy.md` has SUBSTANTIVE content per AC-1a.4.2 (FR59 format + 11-leaf ADR-014 table). `determinism-contract.md` has `### Tier Model` subsection; `stability-surface.md` has `### Sandbox Protocol Surface` subsection. `docs/contracts/README.md` index authored. Machine-verified: 12 .md files (11 contracts + README); all 12 pass docs-build.yml's per-file section assertion (README via code-block-literal-text loophole — functionally correct); all cross-references resolve. Status: review. | Amelia |
| 2026-05-18 | 0.3.0   | Code-review patches applied. Cross-LLM adversarial review (Claude + Codex CLI) caught 10 findings — 6 HIGH + 3 MED + 1 LOW. Claude solo PASSED all 7 dev gates but found 0; Codex caught all 10 (4th time same-family blind spot pattern). 4 cross-document drifts ratified by Many: HIGH-1 listener path → `AgentEval.telemetry.listener` + `xunit_file(path)` hook + Regular Listener model; HIGH-2 mcp_coverage 3-value enum wins (ADR-016 ratified, PRD 4-value superseded); HIGH-4 ValidateOperatorDisallowed canonical (PRD + epics updated); HIGH-6 sysexits-style per-leaf exit codes (65/66/67/68 + 70/75/77/78). 6 contract-internal: HIGH-3 (per-leaf exit-code column added to error-class-hierarchy); HIGH-8 (stability-surface scope narrowed — registry filled incrementally by Story 1a.6+); MED-5 (owning-epic table corrected: UnsupportedMCPVersionError → Story 3.1; PollingDisallowedError → Epic 6); MED-7 (FR59 example flag replaced); MED-9 (evidence-block cross-refs repointed); LOW-10 (FR60 → FR34a/b citation). Files updated: docs/contracts/{error-class-hierarchy, evidence-block-format, listener-integration, junit-xml-enrichment, stability-surface}.md + PRD FR36b/FR43/FR50/AC-MCP-OBSERVE-01 + epics.md Story 6.3. Status: done. | Amelia |

## Senior Developer Review (AI)

**Reviewers:** Claude Opus 4.7 + Codex CLI 0.117.0 (gpt-5.4) — adversarial cross-LLM-family pair per Epic 0 retro Norm #1
**Review date:** 2026-05-18
**Outcome:** **APPROVED post-patch** (Changes Requested at Round 1 → Approved after 10 patches landed)
**Methodology:** Independent Claude re-verification of all 7 dev-story gates (all PASS); Codex CLI adversarial pass on 1087 lines of contract content + cross-references against PRD + epics + ratified ADRs via GitHub MCP; Claude spot-verified all 10 Codex findings locally before triage.

### Findings

Claude solo's gates: 100% PASSED. Codex caught **10 substantive findings**. 4th consecutive cross-LLM review where Claude solo would have shipped real defects.

**HIGH (6 — all patched):**

- **HIGH-1 (listener path):** Three different listener class paths cited across PRD + epics + contracts (`AgentEval.telemetry.Listener` vs `AgentEval.telemetry.listener` vs `agenteval.telemetry.Listener`) + two hook names (`xunit_file(path)` vs `output_xml`). Many ratified: `AgentEval.telemetry.listener` (module path; RF auto-resolves to `Listener` class) + `xunit_file(path)` hook + Regular Listener model (Library Listener empirically disqualified 2026-05-17). Updated `listener-integration.md` + `junit-xml-enrichment.md` to match PRD + epics; PRD + epics already internally consistent.

- **HIGH-2 (mcp_coverage 3 vs 4):** PRD used 4-value enum `[complete, library_only, external_mixed, no_mcp]`; ratified ADR-016 uses 3-value enum `[hosted_in_process, subprocess_with_observer, external_mixed]`. Many ratified ADR-016 (ratified docs > PRD per project norm). PRD L551/L922/L1367/L1554 updated to 3-value enum.

- **HIGH-3 (Integrity exit codes per-leaf):** Contract said "2 or 3 (per-leaf override)" — not actionable. Patched by adding per-leaf `Exit code` column to error-class-hierarchy.md's per-leaf inventory (subsumes HIGH-6 ratification).

- **HIGH-4 (ValidateOperator name):** 3 different names: `ValidateOperatorDisallowed` (ADR-014 ratified), `ValidateOperatorDisabledError` (PRD), `ValidateOperatorDisallowedError` (epics.md). Many ratified ADR-014 name (`ValidateOperatorDisallowed`, no `Error` suffix). PRD FR43 + epics.md L1490 updated.

- **HIGH-6 (FR50 family vs sysexits):** PRD used family codes 1/2/3; epics.md Story 8a.1 L1660 used sysexits 65-68 per-leaf. Many ratified sysexits per-leaf. Per-leaf table in error-class-hierarchy.md: 4 pinned by epics (65 PollingDisallowed, 66 CostExceeded, 67 IncompleteTrace, 68 UnsupportedMCPVersion); 7 others assigned sysexits.h-aligned codes (77 EX_NOPERM for safety; 78 EX_CONFIG for config errors; 75 EX_TEMPFAIL for runtime; 70 EX_SOFTWARE for tier violation; 0 for warning). PRD FR50 updated.

- **HIGH-8 (stability-surface scope):** Contract claimed to label every public element but registry only had 4 sandbox elements. Patched by narrowing Purpose + Scope + Contract sections to explicitly state the registry fills INCREMENTALLY across stories (Story 1a.6 lands initial; each epic-owning story registers its public elements as they ship). Honest Phase-1 stub posture preserved.

**MED (3 — all patched):**

- **MED-5 (owning-epic table corrections):** 2 leaves had wrong owning-epic assignments per Codex's audit against epics.md. Fixed: `UnsupportedMCPVersionError` → Epic 3 Story 3.1 (was Epic 5 Story 5.2); `PollingDisallowedError` → Epic 6 (was "Epic 1b + Phase-2"). Other rows audited + remain accurate.

- **MED-7 (FR59 example flag):** Example invented `allow_unsafe_code_execution=True` — not defined in ADR-018. Replaced with the actual ADR-018 mechanism (register a backend via `agenteval.sandboxes` entry-point).

- **MED-9 (evidence-block cross-ref):** Contract pointed to `listener-integration.md` for adapter population; that's the wrong contract. Repointed to: `otel-trace-visual.md` (for span-attribute mapping per Epic 5.3) + `listener-integration.md` (hook surface only).

**LOW (1 — patched):**

- **LOW-10 (FR60 → FR34a/b):** evidence-block-format.md cited FR60 (which is actually `AdapterVersionDriftWarning`). Replaced with FR34a (format) + FR34b (visual contract).

### Round-2 Verification Evidence

Post-patch machine-verification (all PASS):
- All 12 .md files in docs/contracts/ still pass docs-build.yml's per-file 4-section assertion
- All cross-references resolve (no broken Markdown links)
- ValidateOperator name standardized: zero matches for `ValidateOperatorDisabledError`/`ValidateOperatorDisallowedError` in non-ratification-trail text
- mcp_coverage 4-value enum gone from PRD: zero remaining occurrences

### Action Items

- [x] HIGH-1: listener path canonicalized — `listener-integration.md` + `junit-xml-enrichment.md` updated
- [x] HIGH-2: mcp_coverage 3-value enum — PRD L551/L922/L1367/L1554 updated
- [x] HIGH-3: per-leaf exit-code column added to error-class-hierarchy.md (subsumed by HIGH-6)
- [x] HIGH-4: ValidateOperator name canonicalized — PRD FR43 + epics.md L1490 updated
- [x] HIGH-6: sysexits per-leaf — error-class-hierarchy.md per-leaf table + FR49/FR50 mapping + PRD FR50 updated
- [x] HIGH-8: stability-surface scope narrowed to incremental registry
- [x] MED-5: owning-epic table corrected (2 leaves)
- [x] MED-7: FR59 example flag replaced
- [x] MED-9: evidence-block cross-ref repointed
- [x] LOW-10: FR60 → FR34a/b citation fix

### Project Norms Validated

- **Norm #1 (cross-LLM adversarial review)**: 4th consecutive load-bearing demonstration. Claude solo found 0; Codex caught 10.
- **Norm #2 (machine-verified numeric claims)**: all numeric claims pre-commit (sysexits code values, leaf counts, file counts) machine-verified before commit.
- **Pre-create-story spec-vs-ratified-doc check (Norm #4)**: caught the largest single-story drift to date (4-way count mismatch); this story's review surface includes the inverse — drifts BETWEEN documents that pre-create-story couldn't reach (PRD ↔ epics ↔ contracts).
- **CI log forensics (Many's rule)**: docs-build.yml's first real-content run inspected internally; 12× `##[notice]All 4 NFR-MAINT-04 sections present` confirmed per-file assertion fires correctly. Post-patch CI re-run will confirm no regressions.

### Phase-1 Deferred Items (project debt registry)

None from this review. All 10 findings patched.

### Files Modified This Round

**Contracts (5 modified):**
- `docs/contracts/error-class-hierarchy.md` (HIGH-3, HIGH-6, MED-5, MED-7)
- `docs/contracts/evidence-block-format.md` (MED-9, LOW-10)
- `docs/contracts/listener-integration.md` (HIGH-1)
- `docs/contracts/junit-xml-enrichment.md` (HIGH-1, HIGH-6 cross-ref)
- `docs/contracts/stability-surface.md` (HIGH-8)

**Source documents (PRD + epics — "fix the losing source" pattern):**
- `_bmad-output/planning-artifacts/prd.md` (L551, L925, L1367, L1554 for HIGH-2; L1562 for HIGH-4; L1578 for HIGH-6)
- `_bmad-output/planning-artifacts/epics.md` (L1490 for HIGH-4)

**Findings doc:**
- `_bmad-output/implementation-artifacts/1a-4-code-review-findings-2026-05-18.md` (new)
