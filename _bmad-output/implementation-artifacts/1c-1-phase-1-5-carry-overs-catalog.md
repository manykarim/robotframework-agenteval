# Story 1c-1: Phase-1.5 Carry-Overs Catalog

Status: done

**Story-key rename (Codex 2-reviewer code-review MED 2026-05-19):** the pre-edit
key was `1-5-1-` which `bmad-create-story` parses as `epic_num=1`, `story_num=5`
(NOT "epic 1-5, story 1" — the parser uses first-two-dash-separated-segments).
Renamed to `1c-1-` per the existing `1a`/`1b` precedent: Phase-1.5 = Epic 1c
mini-epic. Sprint-status updated: `epic-1c: in-progress`; `1c-1-phase-1-5-carry-overs-catalog: done`.

## Story

As **Many (Project Lead)**,
I want **a single authoritative catalog at `docs/phase-1-5-carry-overs.md` enumerating every Phase-1.5 deferred-work item with owner placeholders + execution criteria**,
So that the ~17 compounded Phase-1.5 items from Epic 0 + Epic 1a + Epic 1b + Epic 2 are visible in ONE place, ownership can be assigned per item, and the Epic 0 Action #6 / Epic 1a Action #5 / Epic 2 Action #4 carry-over chain CLOSES.

## Pre-create-story drift check (15th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-19)

5 drifts caught + resolved pre-authoring:

- **(D-A MED)** Phase-1.5 has no `epic-1-5` entry in sprint-status.yaml. Add `epic-1-5: in-progress` + this tracking story key `1-5-1-phase-1-5-carry-overs-catalog: in-progress`. The story-key convention (`1-5-N-name`) follows the existing project pattern (Epic 0 = `0-N-`, Epic 1a = `1a-N-`, Epic 1b = `1b-N-`). `1-5-` is the only available shape that the `bmad-create-story` auto-discovery glob (`number-number-name`) will pick up.
- **(D-B MED)** Catalog location: existing `_bmad-output/implementation-artifacts/deferred-work.md` already enumerates ~12 items grouped per-source-story. The new catalog at `docs/phase-1-5-carry-overs.md` is a CONSUMER-FACING document (lives under `docs/`, not `_bmad-output/`) with a different shape (one row per item with owner / criteria / source / acceptance). The two coexist: `deferred-work.md` is the source-of-record by source-story; `docs/phase-1-5-carry-overs.md` is the execution catalog with consolidated ownership.
- **(D-C MED)** Epic 2 additions: the 5 items ratified in Epic 2 retro must be added — `exit_code` ClassVar on the 16 leaves; `_parser.py` → `_internal.py` rename hygiene; `_build_pointer` duplication consolidation (3 copies); architecture L854 `MCPKeywords` → `MCPLibrary` rename; rf-mcp sample drift-detection (checksum gate). Plus emergent: `test_loader_smoke.py` adapter-allow-list dynamic discovery.
- **(D-D LOW)** Scope clarification: this story produces the CATALOG. Individual item EXECUTION happens opportunistically during Phase-1.5 (typically as drive-by fixes during related epic work) OR as dedicated micro-stories if any single item grows beyond a 30-minute trivial fix. Story `1-5-1` does NOT execute the 17+ items.
- **(D-E LOW)** No PRD or architecture amendment needed; the catalog is implementation-artifact + consumer doc, not a ratified contract.

## Acceptance Criteria

### AC-1-5-1.1 — Catalog doc exists

`docs/phase-1-5-carry-overs.md` ships with the canonical list of Phase-1.5 carry-overs — each row containing: `id`, `description`, `source` (which story / retro flagged it), `owner` (placeholder OK), `acceptance criteria` (how to verify done), `priority` (`hygiene` / `correctness` / `documentation`), `estimated effort` (XS = 30min trivial / S = under 2h / M = half-day / L = full-day).

### AC-1-5-1.2 — Cross-reference to deferred-work.md

The new catalog cites the existing `_bmad-output/implementation-artifacts/deferred-work.md` as the by-source-story breakdown; the two docs are complementary, not redundant. Items appear in BOTH but indexed differently.

### AC-1-5-1.3 — Sprint-status entry

`_bmad-output/implementation-artifacts/sprint-status.yaml` has:
- `epic-1-5: in-progress` (under a new `# Phase-1.5: Hygiene + Carry-overs` heading, inserted between `epic-2-retrospective: done` and `epic-3: backlog`).
- `1-5-1-phase-1-5-carry-overs-catalog: review` (will flip to `done` after code review).
- `epic-1-5-retrospective: optional`.

### AC-1-5-1.4 — Minimum 15 items enumerated

The catalog includes at minimum 15 items spanning these source clusters:
- Epic 0 retro carry-overs (macOS validation, real rf-mcp clone testing, ...).
- Epic 1a retro carry-overs (Phase-1.5 backlog ownership — Action #5; this story IS its closure).
- Epic 1b retro carry-overs (Pydantic-migration consolidated tracker DF-1b.5-S2; FR63 doc-build CI gate DF-1b.6-S1; verb allowlist into coding-conventions.md DF-1b.6-S2; convention-tests empty-set hardening DF-1b.6-S4).
- Epic 2 additions per retro Action #4: `exit_code` ClassVar on 16 leaves; `_parser.py` → `_internal.py` rename; `_build_pointer` duplication (3 copies → shared `_kernel/jsonptr.py`); architecture L854 `MCPKeywords` → `MCPLibrary`; rf-mcp checksum gate; `test_loader_smoke.py` adapter-allow-list dynamic discovery.
- Epic 0 D2.1 architect waiver (macOS validation deferred to Phase-1.5).

### AC-1-5-1.5 — Each item has an `acceptance criteria` line

Every catalog row's `acceptance criteria` field describes HOW to verify the item is done (e.g., `exit_code ClassVar`: "all 16 leaves in `src/AgentEval/errors.py` have `exit_code: ClassVar[int] = N` matching the per-leaf table in `docs/contracts/error-class-hierarchy.md` L60-95"). This makes the catalog actionable, not just descriptive.

### AC-1-5-1.6 — Norm applied: cross-LLM code review

Code-review uses 2 reviewers minimum (Codex CLI + Claude Auditor) per `feedback_review_methodology_norms`. The full 4-reviewer pair is overkill for a documentation-only story; a 2-reviewer pair is sufficient and matches the project's "scale review depth to risk" rationale.

## Tasks / Subtasks

- [ ] **Task 1: Author `docs/phase-1-5-carry-overs.md`** with the table-shaped catalog per AC-1-5-1.1 + AC-1-5-1.4 + AC-1-5-1.5.
- [ ] **Task 2: Cross-reference to `deferred-work.md`** per AC-1-5-1.2.
- [ ] **Task 3: Update `sprint-status.yaml`** per AC-1-5-1.3.
- [ ] **Task 4: Code review** per AC-1-5-1.6 (2-reviewer pair).
- [ ] **Task 5: Apply review patches.**

## Dev Notes

- This is a DOCUMENTATION-ONLY story. No source code changes. `mypy`, `ruff`, etc. all trivially clean (no new `.py` files).
- The 17+ items are NOT executed by this story. Execution is opportunistic during related epic work, OR a future Epic 9 closeout story.
- Sprint-status convention: the `1-5-N` story-key prefix lets `bmad-create-story` auto-discovery find the next backlog story in this mini-epic if more Phase-1.5 stories materialize.

## Dev Agent Record

### Context Reference / Agent Model Used / Debug Log References / Completion Notes List

<!-- To be filled by dev-story workflow -->

## File List

<!-- To be filled by dev-story workflow -->

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-19 | 0.1.0   | Initial story creation (ready-for-dev). Closes Epic 0 Action #6 / Epic 1a Action #5 / Epic 2 Action #4 carry-over chain. 5 pre-create-story drifts (15th consecutive use of `feedback_spec_vs_ratified_doc_precheck`). | Bob |
