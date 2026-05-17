# Story 1a.3: Ratify Non-Spike ADRs + Author ADR-001 Architectural Influences Catalog

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **architect**,
I want **14 new non-spike ADRs ratified into `docs/adr/` with `status: accepted` (renumbered from PRD + architecture sidecars per architecture.md's hybrid scheme) + ADR-001 Architectural Influences Catalog body authored (preserving Story 0.3's §Amendments Log verbatim) + `docs/adr/README.md` index file created**,
so that **every subsequent Phase-1 epic implements against ratified decisions, agenteval's architectural inheritance is transparent without implying any dependency on `robotframework-agentguard` or any other source, and contributors can navigate the 18-ADR namespace via the index**.

## Acceptance Criteria

> **Pre-create-story drift check (2026-05-17):** Verified counts + renumbering plan reconcile (10 PRD-backlog ADRs + 7 active architecture-backlog ADRs - 3 Epic 0 ratified = 14 new + ADR-001 catalog body = 15 deliverables → final `docs/adr/` namespace = 18 ADRs total). Per `feedback_spec_vs_ratified_doc_precheck` project norm. One minor stale reference flagged: `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` L117 points to `_bmad-output/planning-artifacts/memory/feedback_agentguard_inspiration_not_dependency.md` which does NOT exist (actual memory lives in `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/`). Fix as part of this story's cleanup tasks.

1. **AC-1a.3.1 — 9 new PRD-renumbered ADRs created.** From `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` (10 ADRs total: ADR-005..014), renumber to agenteval ADR-002..011 per architecture.md L431. Excluding `prd-ADR-007 → agenteval ADR-004` (already Epic 0 ratified). Result: 9 new files at `docs/adr/ADR-002-*.md`, `ADR-003-*.md`, `ADR-005-*.md`, `ADR-006-*.md`, `ADR-007-*.md`, `ADR-008-*.md`, `ADR-009-*.md`, `ADR-010-*.md`, `ADR-011-*.md`. Each MUST contain MADR template sections (Status, Date, Context, Decision, Consequences, Alternatives) AND a `**Renumbering history:**` line citing source sidecar section.

2. **AC-1a.3.2 — 5 new architecture-renumbered ADRs created.** From `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` (8 ADR headers but A4 marked RETIRED → 7 active: A1, A2, A3, A5, A6, A7, A8), renumber to agenteval ADR-012..018 per architecture.md L432. Excluding `arch-ADR-A6 → agenteval ADR-016` and `arch-ADR-A8 → agenteval ADR-018` (already Epic 0 ratified). Result: 5 new files at `docs/adr/ADR-012-*.md`, `ADR-013-*.md`, `ADR-014-*.md`, `ADR-015-*.md`, `ADR-017-*.md`. MADR template + renumbering history per AC-1a.3.1.

3. **AC-1a.3.3 — ADR-001 catalog body filled; §Amendments Log preserved verbatim.** Update `docs/adr/ADR-001-architectural-influences-catalog.md`:
   - Replace `## Stub notice` section with the real ADR Context.
   - Fill `## §Body` with the catalog table (per AC-1a.3.8 + AC-1a.3.9).
   - Preserve `## §Amendments Log` section's 3 existing entries (ADR-004, ADR-016, ADR-018 ratifications) **byte-identical** — Story 0.3 ratifications must not be overwritten. Verify with `git diff` or sha256sum of the §Amendments Log block before commit.
   - Append 14 new entries to §Amendments Log — one per ADR ratified in this story (pattern: `YYYY-MM-DD — ADR-NNN ratified. <one-line summary>. See <evidence>.`).
   - Status updated from `stub` to `accepted`; Date to `2026-05-17`.

4. **AC-1a.3.4 — `docs/adr/README.md` index file created.** A new file at `docs/adr/README.md` containing:
   - Title: `# Architecture Decision Records`
   - One-paragraph explanation of the agenteval ADR convention (MADR template; status workflow Proposed → Accepted → Superseded; numbering scheme per architecture.md L282; renumbering history convention).
   - Tabular index of all 18 ADRs: number | title | status | date | source. Sorted by ADR number.
   - Cross-reference note that ADR-001 is the Architectural Influences Catalog cataloging ~14 reviewed agentguard patterns.

5. **AC-1a.3.5 — MADR template consistency across all 14 new ADRs.** Every new ADR file MUST contain these section headers in this order: `## Context`, `## Decision`, `## Consequences`, `## Alternatives`. Header text MUST match Epic 0 ratified ADRs (`docs/adr/ADR-004-hosted-mcp-observation.md`, `ADR-016-mcp-coverage-detection-default.md`, `ADR-018-sandbox-phase-1-policy.md`) as the reference format. **Machine-verify** via `grep -c -E '^## (Context|Decision|Consequences|Alternatives)$' docs/adr/ADR-*.md` → output must be `4` for every file.

6. **AC-1a.3.6 — Every renumbered ADR documents its renumbering history.** Each new ADR file MUST contain a `**Renumbering history:** Originally proposed as <old-id> in <source-sidecar-path> §<section>. Renumbered to <new-id> per architecture.md project tree (L429-434).` line in its front-matter block (after `**Status:**` + `**Date:**`). Format matches Epic 0's existing renumbering-history lines.

7. **AC-1a.3.7 — Cross-references between ADRs resolve.** Every `[ADR-NNN](ADR-NNN-*.md)` or `see ADR-NNN` reference in any ADR's body MUST point to an existing file. **Machine-verify** with a grep + readlink loop: for every `(ADR-[0-9]{3}-[a-z-]+\.md)` match, assert the referenced file exists in `docs/adr/`.

8. **AC-1a.3.8 — ADR-001 catalog body covers ≥14 reviewed agentguard patterns + competitor projects + standards.** The §Body table MUST include at minimum:
   - The 14 agentguard ADRs called out in architecture.md L290 (ADR-001/002/004/005/009/010/011/012/013/014/019 from agentguard's docs/adr/) PLUS the 4 PRD-claimed influenced concepts (architecture L289 notes "all 4 PRD-claimed influenced concepts have prior art" — these may overlap with the 11). Reviewer to walk `/home/many/workspace/robotframework-agentguard/docs/adr/` to enumerate the full agentguard ADR list + cross-reference architecture.md `reconciliationMatrix`.
   - Competitor MCP-eval projects: `wolfeidau/mcp-evals`, `lastmile-ai/mcp-eval` (referenced by URL — no clones needed in this story).
   - Relevant standards: OpenTelemetry GenAI semantic conventions, Model Context Protocol specification.
   - Each row has 4 columns: source project + reference (URL / commit / ADR ID), what the pattern does, decision (exactly one of `adopt-verbatim` / `adapt` / `borrow-concept` / `explicitly-diverge` / `not-applicable`), one-line rationale.

9. **AC-1a.3.9 — Catalog explicit on no-obligation framing.** The §Body MUST contain a section header (e.g., `## Scope + obligation framing`) explicitly stating:
   > This catalog credits influences but creates **no obligation** to stay aligned with any source project. agenteval is free to evolve its decisions independently of any catalogued source. Per `feedback_agentguard_inspiration_not_dependency` project norm: agentguard is INSPIRATION ONLY, not a dependency.

10. **AC-1a.3.10 — All 18 ADRs have `status: accepted`; zero remaining stub status.** **Machine-verify**: `grep -c '^\*\*Status:\*\* accepted$' docs/adr/ADR-*.md` MUST output one match per file (18 total). `grep '^\*\*Status:\*\* stub' docs/adr/ADR-*.md` MUST output zero matches.

11. **AC-1a.3.11 — Sidecar stale-ref cleanup.** Fix `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` L117's stale reference to `_bmad-output/planning-artifacts/memory/feedback_agentguard_inspiration_not_dependency.md` (non-existent path). Either: (a) remove the reference, (b) update to the correct path under `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/`, or (c) replace with a citation of the new ADR-001 catalog's `feedback_agentguard_inspiration_not_dependency` section.

## Tasks / Subtasks

- [x] **Task 1: Pre-flight (drift check + baseline + agentguard repo access) (AC: 1a.3.1, 1a.3.2)**
  - [x] **Pre-create-story drift check** (already done by create-story facilitator 2026-05-17; documented in story header). Re-confirm: `ls docs/adr/` shows the 4 existing files (ADR-001 stub + ADR-004 + ADR-016 + ADR-018). Run `wc -l docs/adr/ADR-001-architectural-influences-catalog.md` and capture line count BEFORE editing, so the §Amendments Log preservation check at AC-1a.3.3 has a baseline.
  - [x] Verify agentguard repo accessible: `ls /home/many/workspace/robotframework-agentguard/docs/adr/ | wc -l` MUST output `≥20` (per architecture.md L24 `actualAdrCount: 20`). If agentguard repo is missing, HALT — Story 1a.3 cannot author the catalog without walking agentguard's ADR set.
  - [x] Verify both sidecars present: `ls _bmad-output/planning-artifacts/adr-backlog-from-prd.md` + `ls _bmad-output/planning-artifacts/adr-backlog-from-architecture.md` MUST both succeed.
  - [x] Print the canonical renumbering table (from this story's Dev Notes) at the start of the dev-story log for human-readable verification.

- [x] **Task 2: Author 9 PRD-renumbered ADRs (AC: 1a.3.1, 1a.3.5, 1a.3.6)**
  - [x] For each of the 10 ADRs in `_bmad-output/planning-artifacts/adr-backlog-from-prd.md`, copy the seed content to a new file at `docs/adr/ADR-NNN-<slug>.md` using the renumbering mapping in Dev Notes (PRD ADR-005..014 → agenteval ADR-002..011, with ADR-007 → ADR-004 already Epic 0 ratified, skipped here).
  - [x] Each file's front matter MUST contain (exact format from Epic 0 ADRs):
    ```
    # ADR-NNN: <Title>

    **Status:** accepted
    **Date:** 2026-05-17
    **Renumbering history:** Originally proposed as ADR-NNN in `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` §ADR-NNN. Renumbered to ADR-NNN per architecture.md project tree (L429-434, Hybrid scheme).
    ```
  - [x] Each file's body MUST contain `## Context`, `## Decision`, `## Consequences`, `## Alternatives` sections expanding the seed sidecar's content. Use the sidecar's "Context", "Decision", "Rationale", "Alternatives_rejected" YAML keys as starting points for prose.
  - [x] **Per-file numeric verification**: `grep -c -E '^## (Context|Decision|Consequences|Alternatives)$' docs/adr/ADR-NNN-*.md` MUST output `4` for each new file. **Per Epic 0 retro Norm #2: machine-verify before commit.**

- [x] **Task 3: Author 5 architecture-renumbered ADRs (AC: 1a.3.2, 1a.3.5, 1a.3.6)**
  - [x] Same pattern as Task 2, sourcing from `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md`. Mapping per Dev Notes (A1→012, A2→013, A3→014, A5→015, A7→017; A4 retired skipped; A6→016 + A8→018 Epic 0 ratified skipped).
  - [x] Renumbering-history line cites `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md §ADR-AN`.
  - [x] **Per-file numeric verification**: same MADR section count check.

- [x] **Task 4: Fill ADR-001 catalog body (AC: 1a.3.3, 1a.3.8, 1a.3.9)**
  - [x] **CRITICAL: Snapshot §Amendments Log BEFORE editing.** Run `awk '/^## §Amendments Log/,/^$/' docs/adr/ADR-001-architectural-influences-catalog.md > /tmp/adr-001-amendments-log.snapshot` to capture the 3 existing entries.
  - [x] Walk `/home/many/workspace/robotframework-agentguard/docs/adr/` and enumerate all agentguard ADRs. Cross-reference with architecture.md L290 (lists 11 directly-relevant) + architecture.md `reconciliationMatrix` frontmatter (17-entry mapping).
  - [x] Author the §Body section as a markdown table: `| Source | Reference | What it does | Decision | Rationale |` with rows for each agentguard ADR + each competitor project + each standard. Decision column MUST use one of: `adopt-verbatim`, `adapt`, `borrow-concept`, `explicitly-diverge`, `not-applicable`.
  - [x] Add the `## Scope + obligation framing` section per AC-1a.3.9.
  - [x] Replace `## Stub notice` section content with the real ADR-001 Context section. (The §Body section header stays — its content was the placeholder "(Story 1a.3 fills this section.)" which is now obsolete.)
  - [x] Update front matter: `**Status:** stub` → `**Status:** accepted`; rewrite the Date line to a clean `**Date:** 2026-05-17`.
  - [x] **Append 14 new entries** to §Amendments Log — one per ADR ratified in this story (ADR-002, 003, 005-011, 012-015, 017). Use the existing pattern from Story 0.3's 3 entries as the template.
  - [x] **CRITICAL: Verify §Amendments Log preservation via sha256.** Before commit, run `awk '/^## §Amendments Log/,/^- \*\*2026-05-17 — ADR-018/' docs/adr/ADR-001-architectural-influences-catalog.md | sha256sum` and compare against the corresponding range from the snapshot. The 3 Story 0.3 entries MUST be byte-identical. If hashes mismatch, halt and restore from snapshot.

- [x] **Task 5: Author `docs/adr/README.md` index (AC: 1a.3.4)**
  - [x] Create new file `docs/adr/README.md` with title + ADR convention paragraph + 18-row index table + ADR-001 cross-reference note (per AC-1a.3.4 spec).
  - [x] Table columns: `| ADR | Title | Status | Date | Source |`. Source values: `agenteval-original`, `renumbered from PRD-backlog ADR-NNN`, `renumbered from architecture-backlog ADR-AN`.
  - [x] Sort rows by ADR number ascending.

- [x] **Task 6: Cross-reference resolution + machine verification (AC: 1a.3.5, 1a.3.7, 1a.3.10)**
  - [x] Run `grep -nE '\(ADR-[0-9]{3}-[a-z-]+\.md\)' docs/adr/ADR-*.md` to enumerate all internal Markdown links. For each, assert the target file exists in `docs/adr/` via `[ -f docs/adr/ADR-NNN-*.md ]`. Document any unresolvable references + fix.
  - [x] Run AC-1a.3.5 machine-verify: `for f in docs/adr/ADR-*.md; do c=$(grep -c -E '^## (Context|Decision|Consequences|Alternatives)$' "$f"); [ "$c" -ne 4 ] && echo "FAIL: $f has $c MADR sections (expected 4)"; done`. Output should be empty.
  - [x] Run AC-1a.3.10 machine-verify: `grep -c '^\*\*Status:\*\* accepted$' docs/adr/ADR-*.md | grep -v ':1$' | head -5` — output empty means every file has exactly 1 "Status: accepted" line. AND `grep -lE '^\*\*Status:\*\* stub' docs/adr/ADR-*.md` MUST be empty.

- [x] **Task 7: Sidecar stale-ref cleanup (AC: 1a.3.11)**
  - [x] Edit `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` L117 to fix the broken reference to the non-existent `_bmad-output/planning-artifacts/memory/` path. Replace with citation of ADR-001 §Body's `feedback_agentguard_inspiration_not_dependency` row (now that the catalog body exists).

- [x] **Task 8: Verify + commit prep**
  - [x] Run `ls docs/adr/ | wc -l` MUST output `19` (18 ADRs + README.md).
  - [x] Run `grep -lE '^\*\*Status:\*\* accepted$' docs/adr/ADR-*.md | wc -l` MUST output `18`.
  - [x] Update `CHANGELOG.md` `## [Unreleased]` section with summary of 14 new ADRs + ADR-001 body fill + README.md index.
  - [x] Story file Dev Agent Record + File List + Change Log entry per BMad dev-story workflow.

## Dev Notes

### Why this story exists

Story 1a.3 is the architectural foundation for every Phase-1+ epic. Without ratified ADRs:
- Epic 1b (kernel modules) implements against unratified decisions — risk of rework when an ADR's substance shifts during ratification.
- Epic 5 (telemetry) has no ratified ADR-012 (OTel listener) or ADR-013 (entry-points discovery) to bind against.
- Epic 4 (provider layer + adapters) has no ratified ADR-009 (subprocess adapter base) to derive its protocol from.
- Contributors have no ADR-001 catalog explaining which agentguard patterns agenteval adopted, adapted, or diverged from — leaving open the misperception that agenteval is "an agentguard fork".

The catalog (ADR-001) is the **transparency mechanism** for the project's architectural inheritance. Per `feedback_agentguard_inspiration_not_dependency`, agentguard is INSPIRATION ONLY — agenteval is a separate project that catalogues reviewed patterns and is free to diverge anywhere. The catalog makes that posture explicit and reviewable.

### Architecture compliance — canonical renumbering plan

Authoritative source: **architecture.md L429-434** (the §"Final agenteval ADR numbering" subsection).

#### PRD-backlog → agenteval (10 slots: ADR-002..011)

| PRD-backlog ADR | Title hint (from sidecar header) | agenteval new ID | Epic 0 ratified? |
| --- | --- | --- | --- |
| ADR-005 | Tier-1 Adapter Ceiling Rule | ADR-002 | No — create |
| ADR-006 | CodingAgentAdapter Protocol — Internal Class Split | ADR-003 | No — create |
| ADR-007 | Hosted-MCP Universal Trace Observation Pattern | ADR-004 | **Yes** — skip |
| ADR-008 | Conformance Suite Includes Fidelity Oracles | ADR-005 | No — create |
| ADR-009 | `AgentRunResult.metadata.completeness` Field Required | ADR-006 | No — create |
| ADR-010 | `AgentRunResult.metadata.mcp_coverage` + `IncompleteTraceError` | ADR-007 | No — create |
| ADR-011 | MCP Spec Version Validation | ADR-008 | No — create |
| ADR-012 | Per-Test MCP Server Scope (Listener v3 `test_id`) | ADR-009 | No — create |
| ADR-013 | Copilot CLI Adapter — Trace Extraction Strategy | ADR-010 | No — create |
| ADR-014 | Three-Persona Model + Persona-Split Test | ADR-011 | No — create |

Result: **9 new ADRs to create** (ADR-002, 003, 005, 006, 007, 008, 009, 010, 011).

#### Architecture-backlog → agenteval (7 active slots: ADR-012..018)

| Arch-backlog ADR | Title hint (from sidecar header) | agenteval new ID | Epic 0 ratified? |
| --- | --- | --- | --- |
| ADR-A1 | Async-to-Sync Bridge as Kernel Module | ADR-012 | No — create |
| ADR-A2 | Entry-Points Discovery Infrastructure | ADR-013 | No — create |
| ADR-A3 | Error-Class Hierarchy | ADR-014 | No — create |
| ADR-A4 | **RETIRED 2026-05-17** | (skipped) | N/A — retired |
| ADR-A5 | Cost + Runtime Guardrail as `@guarded_fanout` Decorator | ADR-015 | No — create |
| ADR-A6 | Honesty Fields — Detection-failure Defaults | ADR-016 | **Yes** — skip |
| ADR-A7 | Conformance Suite Organization — Per-AC Test Files | ADR-017 | No — create |
| ADR-A8 | Sandbox Policy in Phase 1 | ADR-018 | **Yes** — skip |

Result: **5 new ADRs to create** (ADR-012, 013, 014, 015, 017).

**Total new files: 14 ADRs + ADR-001 body fill + docs/adr/README.md = 16 deliverables.**
**Final `docs/adr/` namespace: 18 ADRs + 1 README index = 19 files.**

### MADR template specification

All new ADRs MUST follow the format established by Epic 0's 3 ratified ADRs (`docs/adr/ADR-004-hosted-mcp-observation.md`, `docs/adr/ADR-016-mcp-coverage-detection-default.md`, `docs/adr/ADR-018-sandbox-phase-1-policy.md`):

```markdown
# ADR-NNN: <Title>

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as <old-id> in `<source-sidecar-path>` §<section>. Renumbered to ADR-NNN per architecture.md project tree (L429-434, Hybrid scheme).

## Context

<2-4 paragraphs of background, source citations, motivation>

## Decision

<the decision in 1-3 paragraphs; clear directives, not waffle>

## Consequences

<positive + negative consequences as bullet lists or prose>

## Alternatives

<alternatives considered + why rejected>
```

The renumbering-history line is REQUIRED for every renumbered ADR (i.e., every new ADR except agenteval-original ones — but Story 1a.3 doesn't author any new agenteval-original ADRs, only renumbers existing seeds). This convention matches Epic 0's existing ADR-004 (line 4), ADR-016 (line 4), ADR-018 (line 4).

### ADR-001 §Amendments Log preservation rule (CRITICAL)

Per Story 0.3's coordination rule 2 (documented in `docs/adr/ADR-001-architectural-influences-catalog.md` L14):
> When Story 1a.3 executes, it MUST preserve the §Amendments Log section below verbatim — entries in that log are ratifications by Story 0.3 (Epic 0) and must not be overwritten.

The 3 existing entries (lines 24-26 of ADR-001 stub) are:
- 2026-05-17 — ADR-004 (renumbered from proposed ADR-007) ratified
- 2026-05-17 — ADR-016 (renumbered from proposed ADR-A6) ratified
- 2026-05-17 — ADR-018 (renumbered from proposed ADR-A8) ratified

**Story 1a.3's job:** APPEND 14 new entries (one per newly-ratified ADR). DO NOT touch the existing 3. Use `sha256sum` or `diff` against the snapshot to verify byte-identical preservation before commit. This is documented as AC-1a.3.3 + Task 4's critical step.

### ADR-001 catalog scope — reviewed projects

Per epics.md L730 + architecture.md L290:

- **Primary review target: `robotframework-agentguard`** at `/home/many/workspace/robotframework-agentguard`. Walk its `docs/adr/` (20 ADRs per architecture.md L24) + cross-reference architecture.md `reconciliationMatrix` (17-entry mapping at L98-280) to enumerate ALL relevant agentguard patterns. Architecture.md L290 explicitly names 11 directly-relevant agentguard ADRs; the catalog should include ALL of those + add any others found during the walk.

- **Competitor MCP-eval projects:**
  - `wolfeidau/mcp-evals` — https://github.com/wolfeidau/mcp-evals
  - `lastmile-ai/mcp-eval` — https://github.com/lastmile-ai/mcp-eval

  No local clones — reference by URL only.

- **Relevant standards:**
  - OpenTelemetry GenAI semantic conventions — https://opentelemetry.io/docs/specs/semconv/gen-ai/
  - Model Context Protocol specification — https://spec.modelcontextprotocol.io/

Each catalog row: 5 columns (`Source | Reference | What it does | Decision | Rationale`). Decision MUST be one of `adopt-verbatim` / `adapt` / `borrow-concept` / `explicitly-diverge` / `not-applicable`. agenteval is free to diverge anywhere; the catalog credits influences without binding future decisions.

### Cross-references between ADRs

Existing Epic 0 ADRs already cross-reference each other:
- ADR-004 references ADR-016 (`mcp_coverage` field semantics).
- ADR-016 references ADR-018 (sandbox subprocess lifecycle — Phase-3 carry-over).
- ADR-018 references ADR-001 (catalog will catalogue with `adopt` decision once body filled).
- ADR-001 (stub) references ADR-004, ADR-016, ADR-018 in §Amendments Log.

Story 1a.3's new ADRs will add MORE cross-references (e.g., ADR-009 subprocess adapter base will reference ADR-014 error hierarchy; ADR-005 conformance fidelity oracles will reference ADR-017 conformance organization). Every internal `[ADR-NNN](ADR-NNN-*.md)` link MUST point to an existing file post-Story-1a.3 (AC-1a.3.7).

### Sidecar stale reference (minor drift caught by pre-create-story check)

`_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` L117 reads:
> See `_bmad-output/planning-artifacts/memory/feedback_agentguard_inspiration_not_dependency.md` for the reframing that retired this ADR.

That path does **NOT exist**. The actual memory lives at `~/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/feedback_agentguard_inspiration_not_dependency.md` (user-private auto-memory).

**Fix** (AC-1a.3.11): replace the broken reference. Recommended replacement: cite the new ADR-001 §Body row for `agentguard inspiration-only` decision, which will be the ratified location for this framing.

### Previous story intelligence (1a.2 learnings carried forward)

Story 1a.2's code-review surfaced 4 project-norm-relevant lessons that Story 1a.3 dev should internalize:

1. **CI-log forensics** (`feedback_ci_log_forensics`): irrelevant for Story 1a.3 (no CI work; pure markdown authoring). But applies to the verification step — if Story 1a.3 dev runs any `gh` command output validation, log-inspect for hidden issues.

2. **Cross-LLM adversarial review** (`feedback_review_methodology_norms` Norm #1): post-dev code-review will be Claude + Codex CLI per project standard. Story 1a.3's primary review surface is markdown content quality — agentguard pattern enumeration, MADR template consistency, ADR-001 catalog completeness.

3. **Machine-verified numeric claims** (`feedback_review_methodology_norms` Norm #2): every numeric claim in Story 1a.3's Dev Notes (14 new ADRs, 9 PRD-renumbered, 5 arch-renumbered, ≥14 reviewed agentguard patterns) MUST be verified via `grep | wc -l` or equivalent before commit.

4. **Pre-create-story drift check** (`feedback_spec_vs_ratified_doc_precheck`): applied 2026-05-17 to this story; no critical drift found. Demonstrates the norm is mature.

### Project norms applied to this story

1. **Norm #1 (cross-LLM adversarial review)**: Story 1a.3 will be reviewed via `/bmad-code-review (Using current Claude + Codex CLI subagent)` post-dev. Critical review focus: ADR-001 catalog completeness (did dev walk all of agentguard's 20 ADRs? are decisions reasonable? is `feedback_agentguard_inspiration_not_dependency` scope-framing intact?), MADR template consistency, cross-reference resolution, §Amendments Log preservation.
2. **Norm #2 (machine-verified numeric claims)**: Tasks 2-7 explicitly call out per-file grep verifications. AC-1a.3.5 + AC-1a.3.7 + AC-1a.3.10 codify machine-verification as gate criteria.
3. **Norm #3 (serialized multi-agent reproductions)**: N/A — no multi-agent reproduction needed for ADR authoring.
4. **Pre-create-story spec-vs-ratified-doc check**: applied 2026-05-17 with no significant drift; documented at top of this story file.
5. **Honest framing**: trade-offs documented — ADR-001 catalog inherits 14+ patterns from agentguard but agenteval is "INSPIRATION ONLY, free to diverge" (catalog scope framing at AC-1a.3.9 makes this explicit).
6. **agentguard inspiration-only**: AC-1a.3.9 enforces the no-obligation framing. Architecture.md §Reviewed-pattern summary L285-291 establishes the methodology agenteval applies (review on merit, document each decision, retain freedom to diverge).
7. **CI-log forensics**: irrelevant for ADR authoring; flagged for completeness.

### References

- **architecture.md L429-434** — authoritative renumbering plan.
- **architecture.md L282** — ADR numbering scheme (locked at Step 1): Hybrid — ADR-001 = Catalog; ADR-002 onwards = original/extended.
- **architecture.md L285-291** — Reviewed-pattern summary methodology + 11 directly-relevant agentguard ADRs listed.
- **architecture.md L98-280** — `reconciliationMatrix` frontmatter (17-entry mapping agenteval concepts → reviewed agentguard ADRs + code locations).
- **architecture.md L579-580** — final state: "docs/adr/ contains 10 ratified ADRs from adr-backlog-from-prd.md + 7 from adr-backlog-from-architecture.md + 1 Architectural Influences Catalog (agenteval ADR-001) — total 18 ADRs in renumbered agenteval namespace."
- **epics.md L714-734** — Story 1a.3 description.
- **`_bmad-output/planning-artifacts/adr-backlog-from-prd.md`** — 10 PRD-originated ADR seeds (working IDs ADR-005..014).
- **`_bmad-output/planning-artifacts/adr-backlog-from-architecture.md`** — 7 active architecture-originated ADR seeds (working IDs ADR-A1..A8, A4 retired).
- **`docs/adr/ADR-001-architectural-influences-catalog.md`** — current stub; §Amendments Log to preserve verbatim.
- **`docs/adr/ADR-004-hosted-mcp-observation.md`** — format reference (renumbering-history line, MADR sections).
- **`docs/adr/ADR-016-mcp-coverage-detection-default.md`** — format reference.
- **`docs/adr/ADR-018-sandbox-phase-1-policy.md`** — format reference.
- **`_bmad-output/implementation-artifacts/0-3-amend-and-ratify-spike-dependent-adrs.md` §Coordination with Story 1a.3** — coordination rules (Story 0.3 spec L121-128).
- **`/home/many/workspace/robotframework-agentguard/docs/adr/`** — primary review target for ADR-001 catalog (20 ADRs to walk).
- **MEMORY.md entries:**
  - `feedback_agentguard_inspiration_not_dependency.md` — scope framing for catalog.
  - `feedback_review_methodology_norms.md` — Epic 0 retro norms.
  - `feedback_honest_framing.md` — name trade-offs explicitly.
  - `feedback_spec_vs_ratified_doc_precheck.md` — pre-create-story drift check (applied 2026-05-17).
  - `feedback_ci_log_forensics.md` — post-dev verification methodology (applies if any `gh` output is used).
- **MADR (Markdown Any Decision Record) format:** https://adr.github.io/madr/

## Dev Agent Record

### Context Reference

- Story file: this file (`_bmad-output/implementation-artifacts/1a-3-ratify-non-spike-adrs-author-adr-001-architectural-influences-catalog.md`)
- Renumbering authority: architecture.md L429-434
- Sidecar sources: `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` + `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md`
- §Amendments Log preservation baseline: `/tmp/adr-001-amendments-log.snapshot` (sha256 `9ff36b0bb2f8488c79cb188aaff7cdf19d23ade66341a5838e52d4ba8d7f0c86`)

### Agent Model Used

Claude Opus 4.7 (1M context) — dev-story workflow invocation 2026-05-17.

### Debug Log References

- **§Amendments Log byte-identical preservation gate (CRITICAL):** Snapshot captured pre-edit via `awk '/^## §Amendments Log/,0' docs/adr/ADR-001-architectural-influences-catalog.md > /tmp/adr-001-amendments-log.snapshot`. Post-edit verification: `awk '/^## §Amendments Log$/,/^\(Story 1a\.3 may append/' docs/adr/ADR-001-architectural-influences-catalog.md | sha256sum` produced `9ff36b0bb2f8488c79cb188aaff7cdf19d23ade66341a5838e52d4ba8d7f0c86` — identical to snapshot. **PASS**: 3 Story 0.3 ratification entries (ADR-004, ADR-016, ADR-018) preserved byte-for-byte.

- **AC-1a.3.7 cross-reference resolution (machine-verified):** All `(ADR-NNN-*.md)` Markdown links across all 18 ADRs + README.md resolve to existing files. Zero broken references.

- **AC-1a.3.5 MADR section consistency (machine-verified):** 17/18 ADRs have exactly 4 strict-match section headers (`^## (Context|Decision|Consequences|Alternatives)$`). The 1 exception is `ADR-018-sandbox-phase-1-policy.md` (Epic 0 ratified, uses verbatim variant `## Alternatives (verbatim from ADR-A8)` per Story 0.3's coordination rules — explicitly allowed by AC-1a.3.5 "Header text MUST match Epic 0 ratified ADRs as the reference format").

- **AC-1a.3.10 status enforcement (machine-verified):** `grep -l '^\*\*Status:\*\* accepted$' docs/adr/ADR-*.md | wc -l` outputs `18`. Zero `**Status:** stub` matches across all ADR files. **PASS**.

- **AC-1a.3.6 renumbering history (verified per file):** Every renumbered ADR (ADR-002, 003, 005-011, 012-015, 017) has a `**Renumbering history:**` line in its front matter citing the source sidecar path + section. ADR-001 (catalog, not renumbered) has no history line by design.

- **AC-1a.3.8 catalog coverage:** ADR-001 §Body table has 22 agentguard-ADR rows (≥14 required) + 2 competitor MCP-eval rows + 2 industry-standard rows = 26 catalog entries total. Walked `/home/many/workspace/robotframework-agentguard/docs/adr/` (23 files = 22 ADRs + README) on 2026-05-17.

- **AC-1a.3.11 sidecar cleanup:** Updated `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` L117 to replace the broken `_bmad-output/planning-artifacts/memory/feedback_agentguard_inspiration_not_dependency.md` reference with a citation of `docs/adr/ADR-001-architectural-influences-catalog.md §Scope + obligation framing`. Also updated L51 to reflect Story 1a.3 ratification status.

### Completion Notes List

- **All 11 ACs satisfied** with machine-verified evidence per Epic 0 retro Norm #2.

- **§Amendments Log preservation passed sha256 gate** — the most critical preservation rule held byte-for-byte. The 3 Story 0.3 entries (ADR-004, ADR-016, ADR-018 ratifications) are unchanged in the new ADR-001.

- **14 new ratification entries appended** to §Amendments Log in source-renumbered order (ADR-002 through ADR-017, skipping ADR-016 which Epic 0 already filled).

- **Catalog coverage exceeds the minimum:** 22 agentguard ADRs reviewed (architecture.md L290 listed 11 directly-relevant; the actual catalog enumerates all 22 with explicit decisions including `not-applicable` for the 4 Ruflo-internal ADRs that don't map to agenteval's domain).

- **Pre-create-story drift check (3rd consecutive story using the norm):** caught the L117 stale-ref before the story authored content, allowing inline cleanup via AC-1a.3.11 rather than discovery during code-review.

- **No HALT conditions encountered.** No additional dependencies required beyond Story 1a.1's `pyproject.toml`. No configuration files missing.

- **Cross-LLM code-review expected to scrutinize:**
  - ADR-001 catalog decision-column accuracy (did we correctly mark agentguard patterns as adopt/adapt/diverge?)
  - MADR-template prose quality (Context/Decision/Consequences/Alternatives in each new ADR)
  - Cross-reference graph completeness (do ADRs that conceptually depend on each other actually cross-reference?)
  - §Amendments Log preservation invariant (cross-LLM should re-verify sha256 against snapshot)

### Code Review Handoff Notes (for `/bmad-code-review`)

The reviewer should specifically scrutinize:

1. **ADR-001 catalog decisions** — for each of the 22 agentguard ADR rows, is the assigned decision (`adopt-verbatim` / `adapt` / `borrow-concept` / `explicitly-diverge` / `not-applicable`) defensible? Particularly: are the 4 Ruflo-* / Aidefence / Swarm-Test-Generation rows correctly marked `not-applicable`? Is `explicitly-diverge` for ADR-006 (skill discovery default-deny) accurately reasoned?

2. **§Amendments Log byte-identical preservation** — the dev verified via sha256, but reviewer should independently re-extract using the same `awk` boundaries and verify hash matches the documented baseline `9ff36b0bb2f8488c79cb188aaff7cdf19d23ade66341a5838e52d4ba8d7f0c86`.

3. **MADR template consistency across the 14 new ADRs** — every file uses the exact section order `## Context`, `## Decision`, `## Consequences`, `## Alternatives` (+ optional `## References`)? Check that no ADR drifted into MADR-extended-template variants.

4. **Cross-reference accuracy** — for each ADR's `## References` section, do the cited cross-references actually appear in the cited ADRs? (e.g., ADR-007 cites ADR-014 for `IncompleteTraceError`; does ADR-014 list `IncompleteTraceError` as a leaf?)

5. **Renumbering history line correctness** — every renumbered ADR cites the correct source sidecar + section. Spot-check 3-4 against the sidecar files.

6. **README.md index accuracy** — 18 rows present + sorted by ADR number + every Source column entry matches the renumbering history?

7. **Sidecar cleanup** — `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` L117 + L51 updates accurate? Original reference to non-existent path replaced with valid pointer?

## File List

Expected files (16 created + 3 updated):

**New ADR files (14):**
- `docs/adr/ADR-002-tier-1-adapter-ceiling-rule.md`
- `docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-split.md`
- `docs/adr/ADR-005-conformance-suite-fidelity-oracles.md`
- `docs/adr/ADR-006-agent-run-result-completeness-field.md`
- `docs/adr/ADR-007-agent-run-result-mcp-coverage-incomplete-trace-error.md`
- `docs/adr/ADR-008-mcp-spec-version-validation.md`
- `docs/adr/ADR-009-per-test-mcp-server-scope.md`
- `docs/adr/ADR-010-copilot-cli-adapter-trace-extraction.md`
- `docs/adr/ADR-011-three-persona-model.md`
- `docs/adr/ADR-012-async-to-sync-bridge-kernel-module.md`
- `docs/adr/ADR-013-entry-points-discovery-infrastructure.md`
- `docs/adr/ADR-014-error-class-hierarchy.md`
- `docs/adr/ADR-015-cost-runtime-guardrail-decorator.md`
- `docs/adr/ADR-017-conformance-suite-organization-per-ac-test-files.md`

(Exact slugs may differ — derive from each source sidecar's `## ADR-NNN: <Title>` heading. Use kebab-case.)

**Index file (1):**
- `docs/adr/README.md`

**Updated files (2):**
- `docs/adr/ADR-001-architectural-influences-catalog.md` (body filled; §Amendments Log preserved + 14 new entries appended; status: stub → accepted)
- `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` (L117 stale-ref cleanup)
- `CHANGELOG.md` (added `## [Unreleased]` entry)

## Change Log

| Date       | Version | Description                                                                  | Author |
| ---------- | ------- | ---------------------------------------------------------------------------- | ------ |
| 2026-05-17 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check applied per `feedback_spec_vs_ratified_doc_precheck`: counts + renumbering plan reconcile (10 + 7 - 3 = 14 + 1 = 15 deliverables → 18 ADRs in final namespace). One minor stale ref flagged in sidecar L117 — addressed via AC-1a.3.11. | Bob    |
| 2026-05-17 | 0.2.0   | Dev-story complete. 14 new ADRs authored + ADR-001 catalog body filled (22 agentguard ADRs + 2 competitor MCP-evals + 2 standards = 26 catalog rows) + §Amendments Log preserved byte-identical (sha256 gate passed) + 14 new ratification entries appended + docs/adr/README.md index authored + sidecar L117 cleanup applied. Final state: 19 files in docs/adr/, 18 with Status: accepted, zero stubs, all cross-refs resolve. Status: review. | Amelia |
| 2026-05-17 | 0.3.0   | Code-review patches applied. Cross-LLM adversarial review (Claude + Codex CLI) caught 5 findings: HIGH-1 (sandbox classification `adopt-verbatim` overstated inheritance), HIGH-2 (conformance entry-point path incoherent — `tests/conformance/` outside the shipped wheel), MED-1 (entry-point group count wording 5→4 in namespace), MED-2 (wrong ADR cross-reference in ADR-010), LOW-1 (numeric drift "9 leaves"→11 in ADR-014). Many approved HIGH-1, HIGH-2 (Option B), MED-1 patches; MED-2 + LOW-1 deferred. After patches: agentguard catalog section has 0 `adopt-verbatim` rows (5 N/A + 4 borrow-concept + 1 explicitly-diverge + 12 adapt = 22; more honest framing — agentguard is INSPIRATION ONLY). All 14 new ADRs still have 4 MADR sections; sha256 gate still passes. Status: done. | Amelia |

## Senior Developer Review (AI)

**Reviewers:** Claude Opus 4.7 + Codex CLI 0.117.0 (gpt-5.4) — adversarial cross-LLM-family pair per Epic 0 retro Norm #1
**Review date:** 2026-05-17
**Outcome:** **APPROVED post-patch** (Changes Requested at Round 1 → Approved after 3 patches landed)
**Methodology:** Independent Claude re-verification of all 8 dev-story gates (all PASS); Codex CLI adversarial pass on 1136 lines of ADR content using GitHub MCP for cross-referencing against agentguard's source ADRs; spot-verification of each Codex finding before triage.

### Findings

Claude solo's independent verification: all 8 dev-story gates PASSED on re-check. Cross-LLM coverage was load-bearing — Claude's same-LLM-family blind spots prevented it from catching its own consistency drift. **Codex caught all 5 findings; Claude solo would have shipped the catalog + ADR-013 + ADR-017 + ADR-010 + ADR-014 inaccuracies.**

**HIGH (2 — both patched):**

- **HIGH-1**: ADR-001 catalog row for agentguard ADR-013 (sandbox policy) labeled `adopt-verbatim`. Codex verified against agentguard's actual ADR-013: agentguard requires Inspect AI integration + `--allow-code-execution` flag; agenteval ADR-018 drops both for `NullSandbox` + entry-points sandbox plugins. The label materially overstates inheritance. **Patched**: decision label changed to `adapt`; rationale rewritten to name what's preserved (sandbox-required posture, error-on-refusal gate) vs what's diverged (Inspect AI dep, opt-in mechanism, error-class hierarchy).

- **HIGH-2**: ADR-017 documented `python -m agenteval.conformance` as the community entry point, but `tests/conformance/` is not shipped in the wheel (`pyproject.toml` `[tool.hatch.build.targets.wheel] packages = ["src/AgentEval"]`). Advertised UX is impossible. **Patched (Option B)**: changed Phase-1 entry-point invocation to `pytest tests/conformance --adapter <name>` (what `conformance.yml` actually runs); added Phase-2-deferred note about future `src/AgentEval/conformance/` CLI proxy.

**MEDIUM (2 — 1 patched, 1 deferred):**

- **MED-1**: ADR-013 said "5 `agenteval.*` entry-point groups" but pyproject.toml has 4 in the `agenteval.*` namespace + 1 legacy `robotframework_agenteval.adapters` + 1 RF-owned `robot.listener` = 6 tables (5 agenteval-owned). **Patched**: normalized wording in Decision + Consequences sections to use the "4 in namespace + 1 legacy + 1 RF-owned = 6 tables (5 agenteval-owned)" framing throughout.

- **MED-2** (deferred per Many): ADR-010 line 37 cites "ADR-013" for the Generic LiteLLM-backed adapter, but ADR-013 is Entry-Points Discovery. Wrong cross-reference. Trivial 1-line fix; will be addressed in a future cleanup pass.

**LOW (1 — deferred per Many):**

- **LOW-1** (deferred): ADR-014 says "9 leaves explicitly named" but the table names 11 (`SafetyError: 2` + `BudgetError: 2` + `CompatError: 4` + `IntegrityError: 3` = 11). Numeric drift caught by Codex (Norm #2 violation). Will be addressed in a future cleanup pass.

### Action Items

- [x] HIGH-1: ADR-001 catalog row for agentguard ADR-013 → `adapt`
- [x] HIGH-2: ADR-017 Phase-1 entry point → `pytest tests/conformance`; Phase-2 CLI proxy deferred
- [x] MED-1: ADR-013 entry-point group count wording normalized
- [ ] MED-2 (deferred): ADR-010 line 37 wrong cross-reference
- [ ] LOW-1 (deferred): ADR-014 "9 leaves" → "11 leaves"

### Round-2 Verification Evidence

Post-patch machine-verification:
- All 14 new ADRs still have 4 strict-match MADR section headers (no patches broke the template structure)
- §Amendments Log sha256 still `9ff36b0bb2f8488c79cb188aaff7cdf19d23ade66341a5838e52d4ba8d7f0c86` (preservation invariant intact)
- Catalog decision distribution after HIGH-1: **12 `adapt` + 5 `not-applicable` + 4 `borrow-concept` + 1 `explicitly-diverge` + 0 `adopt-verbatim`** in the agentguard ADR section (= 22 rows). 2 `adopt-verbatim` rows remain in the industry-standards section (OTel GenAI semconv, MCP spec) which is the correct place for verbatim adoption.
- All cross-references resolve; no broken links introduced by patches.

### Project Norms Validated

- **Norm #1 (cross-LLM adversarial review)**: load-bearing again — Codex 5, Claude solo 0 on this round. Same-family blind spots are real.
- **Norm #2 (machine-verified numeric claims)**: Codex caught LOW-1 (deferred) and MED-1 (patched). The "9 leaves" drift in ADR-014 would have shipped without Norm #2 enforcement; reinforces the rule.
- **Pre-create-story spec-vs-ratified-doc check**: applied 2026-05-17 with no critical drift.
- **CI log forensics**: post-patch CI (`ci` + `security-scan`) green; 0 open CodeQL alerts.

### Phase-1 Deferred Items (project debt registry)

- **MED-2 (cleanup)**: ADR-010 L37 wrong cross-reference to ADR-013 (should cite ADR-003 or drop). Single-line fix.
- **LOW-1 (cleanup)**: ADR-014 leaf count drift (9 → 11). Single-line fix.

Both will be addressed in a future cleanup pass — possibly as part of Story 1a.5 (project hygiene) or a dedicated debt-cleanup batch.
