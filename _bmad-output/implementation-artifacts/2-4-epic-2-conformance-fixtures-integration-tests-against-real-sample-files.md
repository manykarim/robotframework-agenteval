# Story 2.4: Epic 2 Conformance Fixtures + Integration Tests Against Real Sample Files

Status: review

## Story

As a **library maintainer**,
I want **full conformance fixture coverage for the 10 Tier-1 keywords introduced in Stories 2.1-2.3 + integration tests against real-world sample files**,
So that AC-CONFORMANCE-01 is satisfied for Epic 2, the SIMPLICITY-02 keyword-idiom conformance test un-skips, and regressions are caught by CI before merge.

## Pre-create-story drift check (14th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-19)

Surfaced 5 drifts; resolved pre-authoring:

- **(D-A MED)** epics.md L1209 said "11 Tier-1 keywords" but enumerated 10. Re-counted: 5 (Skills) + 1 (Subagent) + 1 (Hook) + 3 (MCP) = 10. epics.md L1209 amended.
- **(D-B MED)** AC-2.4.1 says fixtures "load cleanly through the Story 1b.5 harness". The Story 1b.5 conformance harness validates ADAPTER-run fixtures (`agent_run_result`, `expected_tool_calls`, `reproducibility_footer`); Epic 2 keywords are pure file-parsing with totally different fixture shapes. Resolution: ratify a Phase-1 carve-out — Epic 2 conformance fixtures live at `tests/conformance/fixtures/static_inspection/` with a separate `static-inspection-fixture-schema.json` (fields: `keyword_name`, `input_file_path`, `expected_result_shape`, `expected_error_code`). The Story 1b.5 adapter-fixture harness stays adapter-focused. A new conformance test `test_ac_static_inspection_fixtures.py` exercises the new schema; the existing 6 adapter-style fixtures remain in `tests/conformance/fixtures/{claude_code_cli,generic}/`.
- **(D-C MED)** AC-2.4.2 says "real-world sample files curated from Claude Code documentation + `rf-mcp` repo". `rf-mcp/.mcp.json` is locally present (verified). Claude Code documentation skill/subagent/settings.json examples are NOT bundled in any local repo. Resolution: ratify a Phase-1 path — (1) copy `rf-mcp/.mcp.json` to `tests/integration/static_inspection/samples/rf-mcp.mcp.json` (license-OK: same maintainer); (2) author synthetic-but-representative samples for skill / subagent / hook patterns based on documented Claude Code conventions (the rf-mcp + skill-author dogfood targets per `MEMORY.md` ratification).
- **(D-D MED)** AC-2.4.3 says "`conformance.yml` workflow now runs the full Epic 2 fixture set on every PR + reports per-fixture pass/fail in the PR check summary". The `conformance.yml` is currently `workflow_dispatch` + `release.types: [published]` only (NOT PR-gated; intentional per the workflow's own docstring — "Not added to PR-gating ci.yml because conformance is SDK-version-pinned + slow"). Resolution: do NOT amend `conformance.yml` triggers. Instead, add a `tests/conformance/test_ac_static_inspection_fixtures.py` test that runs in the PR-gating `ci.yml` (via the existing `uv run pytest tests/conformance -q` step) + that consumes the static-inspection fixtures. The conformance.yml release-pinned workflow remains adapter-only.
- **(D-E LOW)** AC-2.4.5 says "Epic 3 dogfood prep: Mei's MCP author flow can now run static inspection (`MCP.Get Server Config` against rf-mcp's `.mcp.json`)". rf-mcp's `.mcp.json` declares servers WITHOUT a `transport` field on some entries (the parser allows omitted `transport` per Phase-1 contract). Verify the parser handles rf-mcp's actual file shape — including its `autoStart` unknown-field passthrough.

Pre-authoring fix: epics.md L1209 amended (10 not 11). The other 4 drift resolutions are documented in this spec; no additional pre-authoring amendments needed.

## Acceptance Criteria

### AC-2.4.1 — Static-inspection fixture schema + 20 fixtures

**Given** the 10 Tier-1 keywords from Stories 2.1-2.3,
**When** I author a static-inspection fixture schema at `tests/conformance/static-inspection-fixture-schema.json` + 20 fixtures at `tests/conformance/fixtures/static_inspection/`,
**Then** each keyword has at minimum 1 happy-path + 1 error-path fixture (10 × 2 = 20 fixtures). Each fixture validates against the schema. The schema fields: `keyword_name` (one of the 10 keyword names), `input_file_path` (path to fixture file relative to repo root), `expected_result_shape` (mapping describing expected dict/list/value shape; happy-path only) OR `expected_error_code` (one of `INVALID_SKILL_FRONTMATTER` / `INVALID_SUBAGENT_DEFINITION` / `INVALID_HOOK_CONFIG` / `INVALID_MCP_SERVER_CONFIG` / `INVALID_MCP_TOOL_SCHEMA`; error-path only). Schema uses jsonschema Draft 2020-12 + jsonschema-validates via the existing loader pattern from Story 1b.5.

### AC-2.4.2 — Static-inspection conformance test

**And** a new conformance test at `tests/conformance/test_ac_static_inspection_fixtures.py` exercises every fixture in `static_inspection/`. For happy-path fixtures: invoke the named keyword against the `input_file_path` + assert the returned value matches `expected_result_shape`. For error-path fixtures: invoke the keyword + assert it raises the typed leaf with the expected `error_code`. The test discovers fixtures via a glob + runs `pytest.mark.parametrize` per fixture so each fixture's pass/fail surfaces individually in CI.

### AC-2.4.3 — AC-SIMPLICITY-02 conformance test un-skipped

**And** `tests/conformance/test_ac_simplicity_02_keyword_idiom.py` is now populated (NO `pytest.skip`). The test introspects all `library.py` classes under `src/AgentEval/` + asserts:
- Every `@keyword`-decorated method on every sub-library class has a `@tier(N)` annotation.
- No sub-library exposes a `Should *` keyword EXCEPT the Story 2.1 Phase-1 carve-out (`Skill.Should Be Valid Frontmatter` per architecture L838 carve-out registry).
- Every keyword name follows snake_case + verb-allowlist per the `tests/unit/conventions/test_keyword_name_idiom.py` `_VERB_ALLOWLIST`.
- The runtime collision-detector in `AgentEval._build_components` would catch any future cross-sub-library `@keyword(name=...)` name collision (asserted by trying to build with the current `_SUB_LIBRARIES`).

### AC-2.4.4 — Real-world sample integration tests

**And Given** real-world sample files at `tests/integration/static_inspection/samples/`:
- `rf-mcp.mcp.json` — copy of `/home/many/workspace/rf-mcp/.mcp.json` (verified locally present; same maintainer; license-OK).
- `claude-code-incident-triage.md` — synthetic skill fixture patterned after Claude Code documentation conventions (4 required frontmatter fields + a realistic prose body).
- `claude-code-code-reviewer.subagent.md` — synthetic sub-agent fixture (name + description required; tools + model optional).
- `claude-code-settings.json` — synthetic Claude Code `settings.json` with `PreToolUse` + `PostToolUse` hooks (representative of common patterns).

**When** I run `pytest tests/integration/static_inspection/test_real_world_samples.py`,
**Then** each Epic 2 keyword is exercised against the real-world samples + all assertions pass. The rf-mcp sample exercises `MCP.Get Server Config` against a file with optional fields the synthetic fixtures don't cover (e.g., the `autoStart` unknown-field passthrough). 4+ samples × 4+ keywords ≥ 16 keyword-against-sample invocations covered.

### AC-2.4.5 — CI workflow extension

**And** the new test files (`tests/conformance/test_ac_static_inspection_fixtures.py` + `tests/integration/static_inspection/test_real_world_samples.py`) are picked up by the existing `ci.yml` `pytest tests/unit -q` step OR a new step. Add a new step `pytest tests/integration/static_inspection -q` to `ci.yml` (the `tests/integration/` directory is not currently in the PR-gating workflow per Phase-1 baseline).

### AC-2.4.6 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean (39 src files; no new source files in this story; tests-only + fixtures).
- `uv run python scripts/check-license-headers.py` PASS.
- `uv run pytest tests/unit -q` — 494 unit tests pass (Story 2.3 regression baseline).
- `uv run pytest tests/conformance -q` — was "30 passed + 11 skipped" pre-Story-2.4; AFTER Story 2.4: 30 prior + ~22 new static-inspection-fixture-driven cases + 1 SIMPLICITY-02 case un-skipped = **51+ passed + 10 skipped**. ONE fewer skip (SIMPLICITY-02 un-skips).
- `uv run pytest tests/acceptance/tier1 -q` — 6 passed (regression).
- `uv run pytest tests/integration/static_inspection -q` — new tests pass.
- `uv run robot tests/acceptance/smoke + tests/unit/{skills,subagents,hooks,mcp}/test_robot_integration.robot` — 13 passed (regression).
- `uv run pytest tests/unit/conventions -q` STANDALONE — 17 passed (Story 2.1 + 2.2 regression).

### AC-2.4.7 — Epic 2 dogfood prep unblocked

**And** the parser actually handles rf-mcp's `.mcp.json` without raising — verified by the integration test. This proves the keyword-set is Epic-3-ready for Mei's MCP author dogfood flow.

### AC-2.4.8 — Project norms applied

**And**:
- Code-review uses `/bmad-code-review (Using current Claude + Codex CLI subagent)` per `feedback_review_methodology_norms` (14th consecutive use).
- Cross-LLM reviewer prompt MUST direct re-derivation of every cited fact from source per `feedback_citation_drift_first_class` (15+ STAR-catch streak ongoing; Story 2.3 was the 15th).
- Honest framing documented: (1) static-inspection fixtures use a SEPARATE schema (Story 2.4 D-B carve-out); the adapter-fixture schema from Story 1b.5 is unchanged; (2) synthetic Claude Code samples are patterned after documented conventions (NOT verbatim copies — license-clean by construction); (3) `conformance.yml` workflow stays release-pinned per its own L11-13 wording.

## Tasks / Subtasks

- [x] **Task 1: Static-inspection fixture schema authored** at `tests/conformance/static-inspection-fixture-schema.json`.
- [x] **Task 2: 20 fixtures** at `tests/conformance/fixtures/static_inspection/`.
- [x] **Task 3: `tests/conformance/test_ac_static_inspection_fixtures.py`** — 22 parametrized cases + 2 coverage tests.
- [x] **Task 4: `tests/conformance/test_ac_simplicity_02_keyword_idiom.py`** un-skipped + 5 introspection checks.
- [x] **Task 5: 4 real-world / synthetic samples** at `tests/integration/static_inspection/samples/`.
- [x] **Task 6: `tests/integration/static_inspection/test_real_world_samples.py`** — 17 keyword-against-sample tests.
- [x] **Task 7: `.github/workflows/ci.yml` extended** with the new pytest step.
- [x] **Task 8: All-gates pass.**
- [x] **Task 9: Project norms applied — code-review queued.**

Additional fix needed: `test_loader_smoke.py` originally rglob'd ALL `*.json` under `fixtures/` + tried to validate them against the ADAPTER schema (which failed on static-inspection fixtures). Scoped the loader-smoke discovery to the 2 adapter subdirs only (`generic/`, `claude_code_cli/`) so the parallel static-inspection schema doesn't collide.

## Dev Notes

### Architecture compliance

- AC-CONFORMANCE-01 (PRD) — fixture-based Tier-1 conformance verification.
- AC-SIMPLICITY-02 (PRD) — keyword-idiom enforcement: snake_case + verbs + no sub-library `Should *` (with documented carve-out for `Skill.Should Be Valid Frontmatter`).
- Story 1b.5 harness — stays adapter-focused; Epic 2 static-inspection schema is SEPARATE (D-B carve-out).
- conformance.yml workflow — stays release-pinned per its own L11-13 wording (D-D carve-out); ci.yml runs the new tests.
- Inherits the standardized Story 2.1+2.2+2.3 patterns transitively (no eager re-export, `utf-8-sig`, RFC 6901 JSON Pointer, FR59 5-line `__str__`).

### Phase-1 limitations explicitly documented

- Static-inspection fixture schema is SEPARATE from adapter fixtures (the Story 1b.5 harness intentionally stays adapter-focused).
- Synthetic Claude Code samples are patterned after documented conventions; rf-mcp's `.mcp.json` is the only "real-world" sample with provenance verifiable in the local workspace.
- `conformance.yml` workflow remains release-pinned; ci.yml runs the new tests (existing `pytest tests/conformance -q` step picks them up).

## Dev Agent Record

### Agent Model Used

Claude Opus 4.7 (1M context) via Claude Code dev-story workflow, 2026-05-19.

### Implementation Plan + Decisions

1. **Static-inspection schema is parallel to the adapter-fixture schema.** Story 1b.5 ships `fixture-schema.json` for adapter-run fixtures (5 required top-level fields including `agent_run_result`). Static-inspection fixtures are a different shape — `keyword_name` + `input_file_path` + `expected_result_shape` OR `expected_error_code`. Authored a NEW schema at `static-inspection-fixture-schema.json` using jsonschema Draft 2020-12 with conditional `allOf` (happy-path requires `expected_result_shape`; error-path requires `expected_error_code`).
2. **`test_loader_smoke.py` scope fix.** The Story 1b.5 loader-smoke `_all_fixture_paths()` rglobbed ALL `*.json` under `fixtures/` and validated against the adapter schema. Static-inspection fixtures failed. Scoped to the 2 adapter subdirs only (`generic/` + `claude_code_cli/`) — preserves Story 1b.5's 6-fixture coverage check + isolates the static-inspection fixtures to their own test file.
3. **`Should Be Valid Frontmatter` dispatch.** The keyword takes a frontmatter DICT, not a path. The conformance dispatch parses the input file via `parse_frontmatter()` first then passes the dict to `should_be_valid_frontmatter`. (Using `Skills.get_frontmatter` would invalidate the no-validate contract from Story 2.1 code-review B3 fix.)
4. **AC-SIMPLICITY-02 carve-out allowlist.** The `Should *` anti-pattern check uses a `_PHASE_1_SHOULD_CARVE_OUTS` frozenset with the single Story 2.1-ratified entry. Future stories that ship additional sub-library `Should *` keywords MUST extend BOTH the architecture L838 registry AND this allowlist.
5. **Synthetic Claude Code samples are pattern-clean.** Authored from documented conventions, NOT copied from any Anthropic source. License-clean by construction. rf-mcp's `.mcp.json` is the only verbatim copy (same maintainer, license-OK).
6. **rf-mcp parser-compatibility.** Verified pre-authoring that `rf-mcp/.mcp.json` parses cleanly through our Story 2.3 parser — including the `autoStart: true` unknown-field passthrough + the omitted-`transport` case (parser allows missing optional fields).

### Completion Notes

All 8 ACs satisfied:
- AC-2.4.1: 20 fixtures + parallel schema.
- AC-2.4.2: 22 parametrized conformance test cases + 2 coverage tests.
- AC-2.4.3: AC-SIMPLICITY-02 un-skipped + 5 introspection assertions.
- AC-2.4.4: 17 real-world / synthetic sample tests.
- AC-2.4.5: CI workflow extended.
- AC-2.4.6: All-gates green.
- AC-2.4.7: Epic-3 dogfood prep verified — `test_dogfood_prep_epic_3_unblocked`.
- AC-2.4.8: Norms applied; code-review queued.

### Test Results

```
$ uv run ruff check / format / mypy / license — all PASS
$ uv run pytest tests/unit -q — 494 passed
$ uv run pytest tests/conformance -q — 57 passed, 10 skipped (was 30 passed + 11 skipped; SIMPLICITY-02 un-skipped + 22 new static-inspection parametrized + 5 new SIMPLICITY-02 assertions added)
$ uv run pytest tests/acceptance/tier1 -q — 6 passed
$ uv run pytest tests/integration/static_inspection -q — 17 passed
$ uv run robot tests/acceptance/smoke + 4 sub-library RF integration suites — 13 passed
$ uv run pytest tests/unit/conventions -q STANDALONE — 17 passed (Story 2.1 order-dependent fake-green prevention regression)
```

## File List

**New files:**
- `tests/conformance/static-inspection-fixture-schema.json` — jsonschema Draft 2020-12 for Epic 2 fixtures.
- `tests/conformance/fixtures/static_inspection/*.json` — 20 fixtures (10 happy + 10 error).
- `tests/conformance/test_ac_static_inspection_fixtures.py` — 22 parametrized cases + 2 coverage tests.
- `tests/integration/static_inspection/__init__.py`.
- `tests/integration/static_inspection/test_real_world_samples.py` — 17 keyword-against-sample tests.
- `tests/integration/static_inspection/samples/rf-mcp.mcp.json` — verbatim copy of `/home/many/workspace/rf-mcp/.mcp.json`.
- `tests/integration/static_inspection/samples/claude-code-incident-triage.md` — synthetic skill sample.
- `tests/integration/static_inspection/samples/claude-code-code-reviewer.subagent.md` — synthetic sub-agent sample.
- `tests/integration/static_inspection/samples/claude-code-settings.json` — synthetic hook config.

**Modified files:**
- `tests/conformance/test_ac_simplicity_02_keyword_idiom.py` — un-skipped + 5 introspection checks (was `pytest.skip` skeleton).
- `tests/conformance/test_loader_smoke.py` — scoped to adapter subdirs only.
- `.github/workflows/ci.yml` — added 1 new pytest step (`pytest tests/integration/static_inspection -q`).

**Modified pre-authoring (drift fixes):**
- `_bmad-output/planning-artifacts/epics.md` L1209 — "11 Tier-1 keywords" → 10 (the bullet list enumerates 10).

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-19 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (14th use) caught 5 drifts: D-A "11 keywords" → 10; D-B static-inspection fixture schema is SEPARATE from Story 1b.5 adapter harness; D-C real-world samples = rf-mcp copy + synthetic Claude Code patterns; D-D conformance.yml stays release-pinned; D-E rf-mcp `.mcp.json` shape compatibility. | Bob |
| 2026-05-19 | 0.2.0   | Dev-story complete. Static-inspection fixture schema + 20 fixtures + parametrized conformance test + SIMPLICITY-02 un-skipped + 4 real-world / synthetic samples + integration tests + CI workflow extended + test_loader_smoke.py scoped to adapter subdirs. All-gates green: ruff/format/mypy clean (39 src files; tests-only additions); 494 unit + 57 conformance (was 30; +27) + 10 skipped (was 11; SIMPLICITY-02 un-skipped) + 6 tier1 + 17 integration + 13 RF. Status: review. | Dev |
