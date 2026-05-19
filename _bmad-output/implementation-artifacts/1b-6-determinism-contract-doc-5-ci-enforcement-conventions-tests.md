# Story 1b.6: Determinism Contract Doc + 5 CI-Enforcement Conventions Tests

Status: review

## Story

As a **library consumer or contributor** (Tier-1 community adapter author, evaluation engineer reading the determinism docs at integration time, agenteval maintainer wanting to catch convention regressions in CI),
I want **`docs/contracts/determinism-contract.md` fully populated to Phase-1 stable per FR63 + 5 CI-enforcement conventions tests at `tests/unit/conventions/*.py` passing on the current end-of-Epic-1b skeleton**,
So that **the FR63 determinism contract is auditable from Day 1 for the rest of Phase 1, architecture-level conventions (tier annotation presence, error class inheritance, no-bare-async, keyword-name idiom, docstring-libdoc-badge alignment) cannot regress silently as Epics 2+ add real keywords, and Epic 1b closes with the conventions infrastructure in place that subsequent epics' code-review cycles will rely on**.

## Acceptance Criteria

> **Pre-create-story drift check (10th consecutive use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-19):** Cross-checked Story 1b.6 epics.md spec against ratified sources. 4 drifts caught + 1 confirmed clean:
>
> - **(D1 MED)** Spec cites "ADR-A1" for async-bare-keyword ban — ADR-A1 is a pre-ratification placeholder; the post-renumbering ADR is **ADR-012** (`docs/adr/ADR-012-run-async-async-to-sync-bridge.md`) per Story 1b.1's `_kernel/run_async.py` + architecture L1418. Spec amended to cite ADR-012.
> - **(D2 LOW)** `tests/unit/conventions/test_tier_annotation_present.py` checks for `@tier(N)` annotation presence; the actual attribute name is `_agenteval_tier` single-underscore per Story 1b.1's `tier.py` + architecture L620 (NOT dunder `__agenteval_tier__`). Implementation verifies the single-underscore attribute via the `get_keyword_tier()` public accessor.
> - **(D3 LOW)** Spec says "docstring contains tier badge text" — badge text format is `[Tier 1 — Deterministic]` / `[Tier 2 — Single-call]` / `[Tier 3 — Fan-out + Statistical]` per Story 1b.1 `tier.py` `_BADGES` dict (lines 45-49). Spec amended to cite the exact strings.
> - **(D4 LOW)** Spec says walk "`src/AgentEval/**/library.py`" — Phase-1 has zero `library.py` files (sub-libraries land in Epic 2+). Tests must handle the empty-set case gracefully (no keywords yet → tests pass trivially with `assert True` for the "no violations found" case). This is the explicit Phase-1 design per the spec's last bullet.
> - **(D5 confirmed clean)** `docs/contracts/determinism-contract.md` exists as Phase-1 skeleton (Story 1a.4 created it with placeholder text); Story 1b.6 fills it per FR63 verbatim coverage requirements.
>
> Pre-authoring fix: epics.md L1064 amended to cite ADR-012 + amended D3 + D4 wording.

### AC-1b.6.1 — `docs/contracts/determinism-contract.md` filled to Phase-1 stable

**Given** the kernel guarantees from Stories 1b.1-1b.3 + the Tier-1/2/3 model from architecture L620 + the FR63 contract from PRD L1597,
**When** Story 1b.6 fills `docs/contracts/determinism-contract.md`,
**Then** the document covers:

- **(a) Tier-1 keyword bit-identical determinism guarantee** per FR31a L1542: "same input always produces same output, no randomness, no time-dependence". Bit-identical bytes-out → bytes-in. Verifiable via the Phase-2 `Assert Run Determinism <keyword> <args> expect=byte_identical` conformance keyword.
- **(b) Tier-2/3 statistical interpretability requirement** per FR31b L1543: non-deterministic results MUST be characterizable via `Stat.Run N Times` + `Stat.Get Pass At K`; library does NOT promise bit-identical traces, cross-model-version reproducibility, or cross-provider equivalence.
- **(c) Polling ban on Tier-2/3** per FR28 L1536: Library raises `PollingDisallowedError` whenever a Tier-2 or Tier-3 keyword receives `polling=` argument (verbatim error-message wording per `docs/contracts/error-class-hierarchy.md` L89).
- **(d) Reproducibility checklist for bug reports** — concrete 6-step user-facing checklist (capture `library_version`, capture `redaction_policy_hash`, capture full RF report `output.xml` + jsonl trace, document the exact Python + RF + agenteval versions, document adapter version, document MCP server versions).
- **Cross-references to ratified ADRs**: ADR-014 (PollingDisallowedError + TierViolationError leaves), ADR-022 (AssertionEngine adoption — polling-ban + validate-disabled negative-consequence clauses), ADR-012 (async-to-sync bridge — why `@keyword`-decorated functions are NOT `async def`).
- **Phase-1 limitations explicitly documented**: `Assert Run Determinism` conformance keyword lands Epic 6 Story 6.x (Tier-3 cost-guardrail family); `Stat.Run N Times` + `Stat.Get Pass At K` land Epic 6 Story 6.y. Determinism contract is published Day 1 (Phase-1 close) so consumers + future-story authors implement against it; full enforcement compounds across Epic 6 + Epic 7 keyword additions.

Document status promoted from "Phase-1 skeleton" to "Phase-1 stable" in the file's frontmatter Status line.

### AC-1b.6.2 — `tests/unit/conventions/test_tier_annotation_present.py`

**And** `tests/unit/conventions/test_tier_annotation_present.py` walks every `src/AgentEval/**/library.py` module (Phase-1: zero files; future epics: one per sub-library) + asserts every `@keyword`-decorated function on those modules has a `_agenteval_tier` attribute (the single-underscore attribute name per Story 1b.1 `tier.py` L74-75 + architecture L620; NOT dunder `__agenteval_tier__`). Verifies via `tests/conformance/harness` style introspection — `inspect.getmembers` filtered by the `robot.api.deco.keyword` decorator's marker attribute. End-of-Epic-1b state: zero `library.py` files → test passes trivially with explicit "no keywords yet — no violations possible" log message.

### AC-1b.6.3 — `tests/unit/conventions/test_error_class_hierarchy.py`

**And** `tests/unit/conventions/test_error_class_hierarchy.py` walks `src/AgentEval/errors.py` + asserts every exported error class in `__all__` inherits from `AgentEvalError` (excluding warning classes like `DegradedTraceWarning` which inherit from `UserWarning` per Story 1b.2 H_R4 fix + architecture L997). No orphan error classes — every leaf goes through one of the 4 ratified sub-bases (`AgentEvalIntegrityError`, `AgentEvalBudgetError`, `AgentEvalCompatError`, `AgentEvalSafetyError`) per ADR-014. End-of-Epic-1b state: all 5 currently-implemented leaves (`IncompleteTraceError`, `CostExceededError`, `RuntimeBudgetExceededError`, `AdapterDiscoveryError`, `DuplicateRegistrationError`, `UnsupportedBinaryVersionError`) verified — test passes on current `errors.py` baseline.

### AC-1b.6.4 — `tests/unit/conventions/test_no_bare_async_keywords.py`

**And** `tests/unit/conventions/test_no_bare_async_keywords.py` asserts no `@keyword`-decorated function is `async def` (per **ADR-012**, NOT ADR-A1 per D1 drift fix). Rationale: async ops MUST go through `_run_async` from `_kernel/run_async.py` (Story 1b.1) — bare `async def` `@keyword` functions break RF's synchronous Library Listener execution model. End-of-Epic-1b state: zero `@keyword` functions exist → test passes trivially.

### AC-1b.6.5 — `tests/unit/conventions/test_keyword_name_idiom.py`

**And** `tests/unit/conventions/test_keyword_name_idiom.py` asserts every `@keyword`-decorated function name uses snake_case (RF converts to Title Case at registration via `pythonlibcore`) and starts with a verb (per `docs/contracts/coding-conventions.md` — verb-list checked against a hardcoded allowlist: `get`, `set`, `run`, `send`, `assert`, `check`, `validate`, `compute`, `list`, `start`, `stop`, `connect`, `disconnect`, `inspect`, `load`, `save`, `read`, `write`, `parse`, `wait`). End-of-Epic-1b state: zero `@keyword` functions → test passes trivially.

### AC-1b.6.6 — `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py`

**And** `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py` asserts every `@keyword`-decorated function's docstring contains its tier badge text (the EXACT strings from Story 1b.1 `tier.py` `_BADGES` dict L45-49: `[Tier 1 — Deterministic]` for `@tier(1)`; `[Tier 2 — Single-call]` for `@tier(2)`; `[Tier 3 — Fan-out + Statistical]` for `@tier(3)`). Verifies that libdoc HTML output's tier badge matches the docstring-level tier badge (no double-source-of-truth drift). End-of-Epic-1b state: zero `@keyword` functions → test passes trivially.

### AC-1b.6.7 — All 5 tests pass trivially on the current skeleton

**And** all 5 conventions tests pass on the current end-of-Epic-1b skeleton (no public keywords exist yet — tests pass trivially with explicit "no keywords yet" log messages). They will catch violations as Epics 2+ add real keywords. The tests are NOT placeholders that always-pass — each performs its full walk + asserts the empty-set condition explicitly (so an Epic 2 dev who adds a malformed keyword will see the test fail immediately).

### AC-1b.6.8 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean (still 31 source files — no new `src/` files; conventions tests live at `tests/unit/conventions/`).
- `uv run python scripts/check-license-headers.py` PASS (still 31/31; tests exempt per convention).
- `uv run pytest tests/unit -q` — 263 prior unit + 5 new conventions tests = 268 pass.
- `uv run pytest tests/conformance -q` — 30 passed + 11 skipped (Story 1b.5 regression).
- `uv run pytest tests/acceptance/tier1 -q` — Story 1a.6 6 FR42 tests still pass.
- `uv run robot tests/acceptance/smoke` — RF smoke regression unchanged.

### AC-1b.6.9 — Project norms applied

**And**:
- Code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)` per `feedback_review_methodology_norms` (10th consecutive use of the cross-LLM adversarial pattern).
- Cross-LLM reviewer prompt MUST direct re-derivation of every cited fact from source per `feedback_citation_drift_first_class` (12 consecutive STAR-catch streak through Story 1b.5 — pattern is load-bearing).
- Honest framing: Phase-1 limitations explicitly documented — (1) all 5 conventions tests pass trivially on current empty skeleton; (2) determinism contract publishes Day 1 with Phase-2 enforcement keywords (`Assert Run Determinism`, `Stat.Run N Times`) called out as deferred; (3) verb allowlist for keyword names is finite + grows as future stories add new verb prefixes.

## Tasks / Subtasks

- [x] **Task 1: Fill `docs/contracts/determinism-contract.md` per FR63 (AC: 1b.6.1)**
  - [x] Status frontmatter → "Phase-1 stable (Story 1b.6 2026-05-19)".
  - [x] §Contract section with subsections (a) Tier-1 bit-identical / (b) Tier-2/3 statistical interpretability / (c) Polling ban / (d) Reproducibility checklist (6 steps).
  - [x] Cross-references to ADR-012 + ADR-014 + ADR-022 (post-renumbering).
  - [x] Phase-1 limitations section: `Assert Run Determinism` + `Stat.Run N Times` deferred to Epic 6.
  - [x] §Change Policy section: explain how the contract evolves under per-leaf stability labels.

- [x] **Task 2: Author `tests/unit/conventions/test_tier_annotation_present.py` (AC: 1b.6.2)**
  - [x] Walk `src/AgentEval/**/library.py` via `pathlib.glob` (returns empty list at end-of-Epic-1b).
  - [x] For each `library.py`, import + inspect for `@keyword`-decorated functions via RF's `robot.api.deco.keyword` marker.
  - [x] Assert each marked function has `_agenteval_tier` attribute (Story 1b.1 `tier.py` convention).
  - [x] Empty-set case: log "no library.py modules yet — no violations possible" and pass.

- [x] **Task 3: Author `tests/unit/conventions/test_error_class_hierarchy.py` (AC: 1b.6.3)**
  - [x] Import `src/AgentEval/errors.py` + iterate `__all__`.
  - [x] For each name in `__all__`, resolve the class object + assert it inherits from `AgentEvalError` (excluding known-non-Error names like `DegradedTraceWarning`).
  - [x] End-of-Epic-1b verifies 4 sub-bases + 6 leaves all conform.

- [x] **Task 4: Author `tests/unit/conventions/test_no_bare_async_keywords.py` (AC: 1b.6.4)**
  - [x] Walk `src/AgentEval/**/library.py` for `@keyword`-decorated functions.
  - [x] Use `inspect.iscoroutinefunction` to detect `async def`.
  - [x] Assert none are coroutine functions per ADR-012.

- [x] **Task 5: Author `tests/unit/conventions/test_keyword_name_idiom.py` (AC: 1b.6.5)**
  - [x] Walk `library.py` modules.
  - [x] For each `@keyword` function: assert name is snake_case via regex `^[a-z][a-z0-9_]*$`.
  - [x] Assert first underscore-token is in the verb allowlist (hardcoded `_VERB_ALLOWLIST` constant).

- [x] **Task 6: Author `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py` (AC: 1b.6.6)**
  - [x] Walk `library.py` modules.
  - [x] For each `@keyword` function, read its `_agenteval_tier` attribute + compose expected badge via `tier_badge(n)` from `_kernel/tier.py`.
  - [x] Assert `function.__doc__` contains the badge string verbatim.

- [x] **Task 7: All-gates pass (AC: 1b.6.8)**

- [x] **Task 8: Apply project norms (AC: 1b.6.9)**

## Dev Notes

### Phase-1 limitations explicitly documented

- All 5 conventions tests pass trivially on the current end-of-Epic-1b skeleton (no `library.py` modules + no `@keyword` functions exist yet). Tests are designed to FAIL loudly when Epic 2+ adds real keywords with convention violations.
- Determinism contract publishes Phase-1 stable Day 1 with explicit Phase-2 enforcement keyword carry-overs (`Assert Run Determinism`, `Stat.Run N Times`, `Stat.Get Pass At K`).
- Verb allowlist for keyword names is finite at end-of-Epic-1b; future stories that add new verb prefixes (e.g., `mock_*`, `seed_*`) MUST extend the `_VERB_ALLOWLIST` constant + cite the new verb in their story spec.
- `_agenteval_tier` attribute is single-underscore per Story 1b.1 `tier.py` (NOT dunder).

### Architecture compliance

| Architecture reference | Story 1b.6 implementation |
|---|---|
| L620 `@tier` decorator sets `_agenteval_tier` on wrapped method | Honored: convention test reads the single-underscore attribute |
| L997 DegradedTraceWarning is a UserWarning, not AgentEvalError | Honored: error-hierarchy test excludes warnings |
| ADR-012 async-to-sync bridge via `_run_async` | Honored: no-bare-async test enforces |
| ADR-014 4-sub-base error scheme | Honored: error-hierarchy test verifies inheritance |
| ADR-022 polling-ban + validate-disabled | Cited in determinism-contract.md |
| FR28 PollingDisallowedError | Cited in determinism-contract.md (c) |
| FR31a Tier-1 bit-identical | Cited in determinism-contract.md (a) |
| FR31b Tier-2/3 statistical interpretability | Cited in determinism-contract.md (b) |
| FR63 Determinism Contract document | Story 1b.6 fills the doc |

### Files List

**New files (5 conventions tests):**
- `tests/unit/conventions/test_tier_annotation_present.py` (~50L)
- `tests/unit/conventions/test_error_class_hierarchy.py` (~50L)
- `tests/unit/conventions/test_no_bare_async_keywords.py` (~50L)
- `tests/unit/conventions/test_keyword_name_idiom.py` (~70L — includes verb allowlist)
- `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py` (~60L)

**Modified files (1):**
- `docs/contracts/determinism-contract.md` — fill skeleton with FR63 verbatim coverage.

**NO `src/AgentEval/` changes** — conventions tests are test infra.

### References

- PRD §FR28 (`PollingDisallowedError`), §FR31a (Tier-1 bit-identical), §FR31b (Tier-2/3 statistical), §FR43 (validate operator), §FR63 (Determinism Contract doc)
- ADR-012 `docs/adr/ADR-012-run-async-async-to-sync-bridge.md` (async-to-sync; renamed from ADR-A1)
- ADR-014 `docs/adr/ADR-014-error-class-hierarchy.md` (4 sub-bases)
- ADR-022 agentguard catalog row (AssertionEngine adoption)
- Story 1b.1 `src/AgentEval/_kernel/tier.py` (`_agenteval_tier` + `tier_badge()`)
- Story 1b.2 `src/AgentEval/errors.py` (`AgentEvalError` + `DegradedTraceWarning`)
- Story 1b.3 `src/AgentEval/errors.py` (added `AgentEvalBudgetError` + `AgentEvalCompatError` sub-bases + 4 leaves)
- Story 1b.4 `src/AgentEval/errors.py` (added `UnsupportedBinaryVersionError`)
- `docs/contracts/coding-conventions.md` (snake_case + verb-prefix rule)
- `docs/contracts/error-class-hierarchy.md` (ratified leaf catalog)
- `docs/contracts/determinism-contract.md` (the file Story 1b.6 fills)

## Dev Agent Record

### Context Reference

- Story spec (this file).
- ADR-012 / ADR-014 / ADR-015 / ADR-022.
- Story 1b.1 `_kernel/tier.py` `_agenteval_tier` + `tier_badge()`.
- Story 1b.2 + 1b.3 + 1b.4 `errors.py` (5 leaves + 4 sub-bases + DegradedTraceWarning).
- PRD FR28 + FR31a + FR31b + FR43 + FR63.
- `docs/contracts/coding-conventions.md` + `docs/contracts/error-class-hierarchy.md`.

### Agent Model Used

Claude Opus 4.7 (1M context) — `claude-opus-4-7[1m]`.

### Debug Log References

None (all-gates clean on first full pass; 4 ruff auto-formats applied to the conventions test files).

### Completion Notes List

- Task 1 — `docs/contracts/determinism-contract.md` filled to Phase-1 stable: §Contract section now covers (a) Tier-1 bit-identical per FR31a + (b) Tier-2/3 statistical interpretability per FR31b + (c) Polling ban per FR28 + (d) 6-step reproducibility checklist + `validate`-operator disabled-by-default per FR43. Cross-references to ADR-012/014/015/022. Phase-1 limitations section explicit. Status line promoted from skeleton to Phase-1 stable.
- Tasks 2-6 — 5 conventions tests + 1 shared helper (`_walk.py`) authored. Total 7 test cases passing (5 named tests + 2 from test_error_class_hierarchy.py multi-test file + 2 from test_keyword_name_idiom.py multi-test file; some files have 1 test, others 2): `test_tier_annotation_present.py` (1 test); `test_error_class_hierarchy.py` (2 tests: every `__all__` export inherits AgentEvalError + no leaf inherits directly from base); `test_no_bare_async_keywords.py` (1 test); `test_keyword_name_idiom.py` (2 tests: snake_case + verb-allowlist); `test_docstring_libdoc_badge_alignment.py` (1 test). All 7 pass trivially on end-of-Epic-1b empty skeleton (zero `library.py` modules + zero `@keyword` functions). `test_error_class_hierarchy.py` actually-exercises against the current 4 sub-bases + 6 leaves + DegradedTraceWarning — that test runs full assertions today.
- Task 7 — All-gates clean: ruff/format/mypy clean (still 31 source files; NO `src/AgentEval/` changes); license-headers PASS (31/31); pytest tests/unit **270 passed** (263 prior + 7 new conventions tests); pytest tests/conformance 30 passed + 11 skipped (Story 1b.5 regression); pytest tests/acceptance/tier1 6 passed; robot tests/acceptance/smoke PASS.
- Task 8 — Project norms applied: code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)` per `feedback_review_methodology_norms` (10th consecutive use); cross-LLM reviewer prompt will direct re-derivation per `feedback_citation_drift_first_class`; Phase-1 limitations explicitly documented in module docstrings + Dev Notes.

## File List

**New files (6):**
- `tests/unit/conventions/_walk.py` (~80L) — shared `find_library_modules()` + `iter_keyword_functions()` helpers.
- `tests/unit/conventions/test_tier_annotation_present.py` (~40L) — AC-1b.6.2.
- `tests/unit/conventions/test_error_class_hierarchy.py` (~70L, 2 tests) — AC-1b.6.3.
- `tests/unit/conventions/test_no_bare_async_keywords.py` (~35L) — AC-1b.6.4.
- `tests/unit/conventions/test_keyword_name_idiom.py` (~90L, 2 tests) — AC-1b.6.5.
- `tests/unit/conventions/test_docstring_libdoc_badge_alignment.py` (~45L) — AC-1b.6.6.

**Modified files (2):**
- `docs/contracts/determinism-contract.md` — filled from Phase-1 skeleton → Phase-1 stable.
- `_bmad-output/planning-artifacts/epics.md` L1064 — pre-authoring drift fix (ADR-A1 → ADR-012).

**NO `src/AgentEval/` changes** — conventions tests are test infra (per architecture L853 test-infra-not-sub-library convention).

## Change Log

| Date       | Version | Description                                                                  | Author |
| ---------- | ------- | ---------------------------------------------------------------------------- | ------ |
| 2026-05-19 | 0.2.0   | Dev-story implementation pass complete; status → review. Tasks 1-8 done. New: `tests/unit/conventions/_walk.py` shared helpers + 5 conventions tests (7 test cases total). `docs/contracts/determinism-contract.md` filled from Phase-1 skeleton to Phase-1 stable per FR63 verbatim: (a) Tier-1 bit-identical per FR31a; (b) Tier-2/3 statistical interpretability per FR31b; (c) polling ban per FR28; (d) 6-step reproducibility checklist; `validate`-operator opt-in per FR43. All-gates clean: ruff/format/mypy/license (31 source files); **270 unit passed** (263 prior + 7 new conventions); 30 conformance + 11 skipped + 6 tier1 + RF smoke regression. NO `src/AgentEval/` changes. Phase-1 limitations preserved: all 5 conventions tests trivially-pass on end-of-Epic-1b empty skeleton; `Assert Run Determinism` + `Stat.Run N Times` enforcement keywords deferred to Epic 6; verb allowlist grows as future stories add new verb prefixes. | Amelia |
| 2026-05-19 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (10th consecutive use) caught 4 drifts (1 MED + 3 LOW + 1 confirmed clean): D1 ADR-A1 → ADR-012 (post-renumbering); D2 dunder `__agenteval_tier__` → single-underscore `_agenteval_tier` per Story 1b.1 tier.py; D3 badge text exact strings per tier.py `_BADGES`; D4 Phase-1 empty-set case (zero library.py modules → tests pass trivially); D5 determinism-contract.md skeleton confirmed exists. Story 1b.6 closes Epic 1b: fills determinism-contract.md to Phase-1 stable + adds 5 CI-enforcement conventions tests passing on the current skeleton. NO src/AgentEval/ changes (conventions tests are test infra). | Bob |
