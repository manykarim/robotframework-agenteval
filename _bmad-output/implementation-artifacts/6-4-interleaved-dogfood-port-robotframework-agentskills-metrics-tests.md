# Story 6.4: Interleaved Dogfood — Port `robotframework-agentskills` Metrics Tests

Status: done

## Story

As a **dogfood validator**,
I want a `.robot` dogfood suite at `tests/dogfood/agentskills/` that exercises agenteval's Epic 6 keyword surface (`Metric.*`, `AssertionsLibrary.*`, `Stat.*`, top-level `Get Keyword Tier`) against `AgentRunResult` fixtures parallel-derived from `robotframework-agentskills`' scoring-test corpus,
So that AC-DOGFOOD-01 advances + Raj's primary journey evidence loop closes for the metric/assertion/statistical-primitive surface.

## Pre-create-story drift check (30th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-20)

100% real-drift catch rate intact across 29 prior uses. Story 6.4 caught **8 drifts** + applied 3 in-flight amendments to epics.md L1679-1683:

- **D-1 HIGH structural framing** (AMENDED in epics.md 2026-05-20 — mirrors Story 3.3 D-A + Story 5.5 D-1) — pre-edit epic AC said "`dogfood-integration.yml` runs the new suites in `robotframework-agentskills` head on every PR" implying cross-repo CI wiring + push-to-upstream pattern. **Resolution:** vendor `.robot` suites INTO agenteval at `tests/dogfood/agentskills/` per ratified Story 3.3 + 5.5 pattern; `dogfood-integration.yml` stays smoke-only per Story 1a.2 norm; full cross-repo CI dispatch deferred to Story 9.1+9.2 per architecture L1718 + epic L1564 Epic 6 closing-block framing.

- **D-2 HIGH framing reframe** (mirrors Story 5.5 D-3 — "honest scope") — epic AC says "port `robotframework-agentskills` existing custom Python tests for tool-call metrics + statistical assertions". Empirically the `robotframework-agentskills` corpus at `/home/many/workspace/robotframework-agentskills/tests/eval/*.py` contains DETERMINISTIC SCORING / VERDICT-aggregation tests (`test_scoring_deterministic.py`, `test_scoring_session_based.py`, `test_session_parser_tool_result.py`, `test_grader_robot_runner.py`, `test_domain_run.py`, `test_cli_score_batch.py`) operating on captured agent session JSON — there are NO "tool-call metric tests" in the agenteval sense (no analog of `Metric.Get Tool Call Count`). **Resolution:** reframe Story 6.4 as "dogfood agenteval's Metric/Assertion/Stat surface AGAINST agentskills' scoring-test domain via `AgentRunResult` fixtures parallel-derived from agentskills' captured session corpus" rather than "port agentskills tests verbatim". This is the same reframe pattern Story 5.5 applied successfully (D-3 ratified).

- **D-3 LOW parity-checklist path** (AMENDED in epics.md 2026-05-20) — pre-edit `tests/dogfood/parity-checklist-agentskills-metrics.md` at the root; Story 3.3 + 5.5 established `tests/dogfood/<repo>/parity-checklist-<repo>-<surface>.md` subdir convention. Amended to `tests/dogfood/agentskills/parity-checklist-agentskills-metrics.md`.

- **D-4 MED load-bearing carve-out** (DF-5.5-DOGFOOD-2 / C44 + DF-6.1-S1 / C46) — Phase-1 `Metric.*` keywords read from `AgentRunResult` fields directly (NOT `_kernel/trace_store` spans) because adapter span instrumentation is deferred per C44. **Implication for Story 6.4:** dogfood fixtures must populate `AgentRunResult.tool_calls` / `.usage` / `.cost_usd` / `.latency_seconds` directly (mock-provider pattern from Story 5.5). Cannot drive an end-to-end multi-turn agent loop (DF-5.5-DOGFOOD-1 / C43 multi-turn loop is Phase-2). Honest scope per Story 5.5 precedent.

- **D-5 MED carry-over constraints** — DF-6.2-S1 (C47 FR34a EvidenceBlock not emitted by `MetricsLibrary` + `AssertionsLibrary`) + DF-6.2-S2 (C48 `Get Trajectory` / `Get Agent Response` paired getters absent) + DF-6.3-S1+S2 (C49+C50 AssertionEngine wrap + 6-keyword Path A deferred) constrain dogfood scope. **Resolution:** Story 6.4 dogfood exercises the SHIPPED Phase-1 keyword surface only; FR34a evidence-block visibility + paired-getter ergonomics are out-of-scope (deferred via existing catalog entries; new findings from Story 6.4 dogfood get added as DF-6.4-S* entries).

- **D-6 LOW operational `dogfood-finding` label** — pre-edit epic AC implies a `dogfood-finding` GitHub label tracker. Per Story 3.3 D-F: no such label exists; findings go to `deferred-work.md` + `docs/phase-1-5-carry-overs.md` per project norm.

- **D-7 LOW `Get Trajectory` PRD-vs-shipped drift** — PRD L1079 Raj journey narrative references "Trajectory Should Match (core, paired with Get Trajectory)" but Story 6.2 ships `Trajectory Should Match` only (paired `Get Trajectory` deferred to DF-6.2-S2 / C48). Pre-existing drift, NOT Story 6.4's to fix; documented here so dogfood doesn't try to exercise an absent keyword.

- **D-8 LOW reference precision** — task-brief framing mentioned "FR65 + FR67" but FR67 does NOT exist in PRD. Actual references for Story 6.4 scope are: AC-DOGFOOD-01 (prd.md:308 + L920 + L1290), FR19-22 (prd.md:1523-1526 metrics surface), FR65 (prd.md:1599 exit criteria doc), NFR-REL-05 (prd.md:1626 dogfood loop integrity).

## Acceptance Criteria

### AC-6.4.1 — `tests/dogfood/agentskills/` directory structure mirrors Story 3.3 + 5.5 `tests/dogfood/rf-mcp/`

**Given** the ratified Story 3.3 + 5.5 dogfood-port pattern,
**When** Story 6.4 ships:

```
tests/dogfood/agentskills/
├── test_metrics_parity.robot                       # NEW — primary port suite (Metric.* coverage)
├── test_assertions_parity.robot                    # NEW — AssertionsLibrary.* coverage
├── test_stats_parity.robot                         # NEW — Stat.* coverage (Tier-3 fan-out + Pass@k)
├── parity-checklist-agentskills-metrics.md         # NEW — checklist + deferred-parity + dogfood-finding sections
└── fixtures/
    └── agentskills_sessions.py                     # NEW — Python fixture helpers building AgentRunResult from agentskills session shapes
```

**Then** the directory layout matches Story 3.3's `tests/dogfood/rf-mcp/` structure (vendored fixtures + `.robot` suites + per-surface parity checklist). NO upstream-push to `robotframework-agentskills`. NO cross-repo CI dispatch in Story 6.4 (deferred to 9.1+9.2 per D-1).

### AC-6.4.2 — `test_metrics_parity.robot` exercises all 9 `MetricsLibrary` keywords against `AgentRunResult` fixtures parallel-derived from agentskills' scoring-test corpus

**Given** the 9 Story 6.1 `MetricsLibrary` keywords + the agentskills session-JSON shapes from `tests/eval/test_session_parser_tool_result.py` + `test_scoring_deterministic.py`,
**When** `test_metrics_parity.robot` runs:

- Build `AgentRunResult` fixtures via `fixtures/agentskills_sessions.py` helper that mirrors agentskills' session shape (tool_calls, usage, latency, cost) — this is the parallel-derivation pattern (D-2 reframe).
- Each of the 9 metric keywords gets a happy-path test + an empty-result test:
  - `Metric.Get Tool Call Count` ↔ agentskills' tool-call count in `SessionScorecard.tool_count`
  - `Metric.Get Tool Call Names` ↔ agentskills' tool-name list (chronological, dupes preserved)
  - `Metric.Get Tool Hit Rate`, `Get Tool Success Rate`, `Get Unnecessary Call Rate` ↔ agentskills' deterministic scoring rules
  - `Metric.Get Token Usage` ↔ agentskills' `Usage(input, output, cached_input)` shape
  - `Metric.Get Latency`, `Get Latency P95`, `Get Cost Total` ↔ agentskills' per-trial latency + cost aggregation
- Each test uses `Library    AgentEval    WITH NAME    AgentEval` + the explicit DynamicCore-composed keyword invocations (NOT the sub-library direct-import bypass).
- Tests carry `[Tags]    slow    dogfood` so the default pytest sweep doesn't pick them up.

**Then** parity coverage achieved — each agentskills scoring rule has at least one equivalent agenteval keyword exercising the same semantic on parallel-derived fixtures.

### AC-6.4.3 — `test_assertions_parity.robot` exercises 5 `AssertionsLibrary` keywords + the `IncompleteTraceError` gate

**Given** the 5 Story 6.2 keywords (`Trajectory Should Match` 4 modes + `Tool Call Should Have Occurred` + 3 `Agent Response Should *`),
**When** `test_assertions_parity.robot` runs:

- `Trajectory Should Match` 4-mode coverage (exact / subsequence / set / regex) per FR23a + FR23b — parallel-derived from agentskills' `test_session_parser_tool_result.py` tool-sequence assertions.
- `Tool Call Should Have Occurred` dict-subset arg-matching parallel to agentskills' deterministic-verdict expected-tool-call rules.
- `Agent Response Should Contain / Match Regex / Match Schema` parallel to agentskills' `test_grader_robot_runner.py` response-text assertions.
- FR37 `IncompleteTraceError` gate behavior verified for tool-call-bearing assertions (Trajectory + Tool Call) on `mcp_coverage="external_mixed"` fixtures.

**Then** every Story 6.2 assertion keyword is exercised from a `.robot` test (operator-facing surface validation).

### AC-6.4.4 — `test_stats_parity.robot` exercises 4 `Stat.*` keywords + `Get Keyword Tier` introspection

**Given** the Story 6.3 `StatsLibrary` (4 keywords) + top-level `Get Keyword Tier`,
**When** `test_stats_parity.robot` runs:

- `Stat.Run N Times` with `n=5` + a deterministic Tier-2 fake-provider wrapped keyword — parallel-derived from agentskills' `test_cli_score_batch.py` batch-Pass@k pattern.
- `Stat.Get Pass At K` with predicate ↔ agentskills' deterministic verdict success-rule.
- `Stat.Get Pass At K Confidence Interval` Wilson CI ↔ agentskills' (currently absent) confidence-interval gap (DOGFOOD-FINDING candidate).
- `Stat.Assert Run Determinism` on a Tier-1 metric keyword (e.g., `Metric.Get Tool Call Count`) — exercises FR31a bit-identical guarantee end-to-end.
- `Get Keyword Tier` introspection on all 6 Epic 6 keyword names + on `Get Effective Config` (Tier-1 baseline).
- FR28 `PollingDisallowedError` gate verified empirically via `Run Keyword And Expect Error PollingDisallowedError* Send Prompt polling=0.5` on a fixture with a Tier-2 wrapped keyword.

**Then** every Story 6.3 keyword is exercised + the FR28+FR30a+FR31a contracts are validated end-to-end through the operator-facing RF surface.

### AC-6.4.5 — `parity-checklist-agentskills-metrics.md` documents coverage + deferred-parity + dogfood-findings

Sections (per Story 3.3 + 5.5 precedent):

1. **Coverage matrix**: agentskills test → agenteval keyword + dogfood `.robot` test mapping.
2. **Deferred parity**: agentskills tests NOT ported (out-of-scope for Story 6.4 surface) with rationale + future-story pointer.
3. **Dogfood findings**: ≥1 actionable agenteval improvement uncovered during the port, catalogued as `DF-6.4-S*` entries in `deferred-work.md` + `docs/phase-1-5-carry-overs.md` per D-6.

### AC-6.4.6 — Fixture helper at `fixtures/agentskills_sessions.py` builds `AgentRunResult` from agentskills session shapes

**Given** agentskills' session-JSON shape (`SessionRecord` from `src/rf_skill_eval/domain/events.py` + `Scorecard` from `domain/scorecard.py`),
**When** `agentskills_sessions.py` ships:

- Pure Python helper module (no RF deps); imports `AgentEval.types` for `AgentRunResult` + `ToolCallTrace` + `Usage` + `AgentRunMetadata`.
- Function `build_run_from_session(session_dict) -> AgentRunResult` parallel-derives a Phase-1-compatible `AgentRunResult` from a captured agentskills session JSON shape.
- Function `load_fixture_session(name) -> dict` loads a known-good session fixture from `tests/dogfood/agentskills/fixtures/sessions/<name>.json` (vendored from agentskills' `eval/runs/` if non-sensitive examples exist there, OR synthesized).

**Then** the dogfood `.robot` suites can build deterministic `AgentRunResult` fixtures without needing a live MCP server / live LLM provider (Phase-1 carve-out per D-4).

### AC-6.4.7 — Suite Setup/Teardown pattern + env-var indirection mirror Story 3.3 + 5.5 conventions

- `${RF_AGENTSKILLS_REPO_ROOT}` env var defaults to `/home/many/workspace/robotframework-agentskills` (Many's local sibling clone); operator-friendly override via `--variable RF_AGENTSKILLS_REPO_ROOT:/path/to/repo`.
- Suite Setup guards against absent agentskills repo + skips suite with `SKIP` reason (NOT failure) — operator-facing UX consistent with Story 3.3 conventions.
- `[Tags]    slow    dogfood` excludes the suite from default pytest sweep (per Story 3.3 precedent).
- `Library    AgentEval    WITH NAME    AgentEval` — DynamicCore-composed import per Story 2.2 collision norm.

### AC-6.4.8 — ≥1 dogfood-finding catalogued per D-6 (mirrors Story 3.3 + 5.5 DOGFOOD-FINDING pattern)

**Given** the port effort exposes friction points (ergonomic gaps, missing helpers, fake-green hazards),
**When** Story 6.4 ships:

- At least 1 finding is documented in the parity checklist's "Dogfood findings" section + catalogued as `DF-6.4-S*` in `deferred-work.md` + new C-row in `docs/phase-1-5-carry-overs.md`.
- Candidate findings (likely to surface during dogfood):
  - **DF-6.4-S1**: paired-getter `Get Trajectory` absent (currently `Trajectory Should Match` only — closes the gap PRD L1079 predicts).
  - **DF-6.4-S2**: `AgentRunResult` builder DX (Phase-1 requires manual ToolCallTrace construction — agentskills-style session-JSON-to-AgentRunResult helper is project-level utility).
  - **DF-6.4-S3**: pre-write fake-green precheck per `feedback_dogfood_fake_green_precheck` (Story 5.5 ratified — dogfood `.robot` tests have higher fake-green rate).

### AC-6.4.9 — `feedback_dogfood_fake_green_precheck` pre-write check applied before flipping to review

Per Story 5.5 retro NEW norm: dogfood `.robot` tests have higher fake-green base rate (Story 3.3: 2 fake-greens; Story 5.5: 4 fake-greens). Pre-write fake-green precheck saves a code-review cycle. Verification:

- Each `.robot` test's "When/Then" body must assert the actual Phase-1 keyword surface behavior — NOT a trivial `Should Be Equal    True    True` placeholder.
- Each test name promises a specific assertion — `feedback_test_name_assertion_match` Story 3.3 retro norm.

### AC-6.4.10 — `feedback_carry_over_catalog_gate` UPSTREAM applied + `feedback_caller_count_check`

Per Epic 4 retro NEW norms:
- 10th consecutive story applying `feedback_carry_over_catalog_gate` UPSTREAM (Stories 5.1-5.5 + 6.1-6.4).
- New `DF-6.4-S*` entries catalogued in BOTH `deferred-work.md` + `phase-1-5-carry-overs.md` BEFORE `/bmad-code-review`.
- `feedback_caller_count_check`: fixture helper functions have caller count ≥ 2 (helper + at least 1 test).

### AC-6.4.11 — All-gates pass

ruff/format/mypy/license-headers clean (target: **79 src files** unchanged — Story 6.4 is dogfood-only, no new `src/AgentEval/` modules); full `uv run pytest tests/unit tests/conformance tests/integration -q` passes with **1206 tests / 8 skipped** (UNCHANGED — dogfood `.robot` tests are excluded by default via `[Tags] slow dogfood`); `tests/dogfood/agentskills/` directory exists + `.robot` suites parse cleanly via `uv run robot --dryrun tests/dogfood/agentskills/`; new fixture helper has unit-test coverage if it ships any non-trivial Python (≥ 5 LoC).

## Tasks / Subtasks

- [x] **Task 1: `tests/dogfood/agentskills/__init__.py` + `tests/dogfood/agentskills/fixtures/__init__.py`** — directory scaffolding (mirror Story 3.3 layout).
- [x] **Task 2: `tests/dogfood/agentskills/fixtures/agentskills_sessions.py`** — Python helper module with `build_run_from_session()` + `load_fixture_session()` per AC-6.4.6. Pure-Python, no RF deps. Unit-test coverage at `tests/unit/dogfood/test_agentskills_sessions.py` per AC-6.4.11.
- [x] **Task 3: `tests/dogfood/agentskills/fixtures/sessions/`** — vendored / synthesized `.json` fixture files (3-5 representative session shapes covering: deterministic-pass, deterministic-fail, partial-completeness, external-mixed coverage).
- [x] **Task 4: `tests/dogfood/agentskills/test_metrics_parity.robot`** — 9 metric keywords × ≥1 happy + ≥1 empty-result test = ~12-18 tests per AC-6.4.2.
- [x] **Task 5: `tests/dogfood/agentskills/test_assertions_parity.robot`** — 5 assertion keywords × 4 trajectory modes + tool-call subset + 3 response variants + FR37 gate = ~8-10 tests per AC-6.4.3.
- [x] **Task 6: `tests/dogfood/agentskills/test_stats_parity.robot`** — 4 stat keywords + `Get Keyword Tier` introspection + FR28 gate empirical = ~6-8 tests per AC-6.4.4.
- [x] **Task 7: `tests/dogfood/agentskills/parity-checklist-agentskills-metrics.md`** — coverage matrix + deferred-parity + dogfood-findings per AC-6.4.5.
- [x] **Task 8: Catalog ≥1 `DF-6.4-S*` finding** in `deferred-work.md` + `phase-1-5-carry-overs.md` per AC-6.4.8 + AC-6.4.10 + D-6.
- [x] **Task 9: All-gates pass** — `uv run pytest -q --no-header` (default sweep, dogfood excluded by `[Tags] slow dogfood`) → 1206 tests / 8 skipped; `uv run robot --dryrun tests/dogfood/agentskills/` parses cleanly; ruff/format/mypy/license clean per AC-6.4.11.
- [x] **Task 10: Fake-green precheck per `feedback_dogfood_fake_green_precheck`** — grep each `.robot` test body for placeholder patterns (`Should Be Equal    True    True`, `Should Not Be Empty    ${EMPTY}`, etc.) BEFORE flipping to review.
- [x] **Task 11: `feedback_carry_over_catalog_gate` UPSTREAM** — 10th consecutive story applying the gate. Verify DF-6.4-S* entries in BOTH catalog files BEFORE `/bmad-code-review`.
- [ ] **Task 12: 4-reviewer cross-LLM code review** — handled by next skill in `/goal` loop. Expected concerns: D-2 framing reframe accuracy; D-4 fixture-driven scope honesty; fake-green precheck efficacy; convention-test allowlist (likely no extensions needed — dogfood `.robot` files don't go through the `@keyword` walker).

## Dev Notes

### Architecture compliance

- **PRD AC-DOGFOOD-01** (prd.md:308): "The library MUST be capable of replacing existing custom end-to-end tests in Many's two reference projects (`rf-mcp` + `robotframework-agentskills`)" — Story 6.4 advances the agentskills half of this AC. Full closure (cross-repo CI dispatch) is Story 9.1+9.2.
- **PRD FR19-22** (prd.md:1523-1526): all 9 `MetricsLibrary` keywords exercised end-to-end via `.robot` surface.
- **PRD FR23-25** (Story 6.2 surface): all 5 `AssertionsLibrary` keywords exercised.
- **PRD FR26-31a + FR43 + FR56** (Story 6.3 surface): all 4 `Stat.*` keywords + `Get Keyword Tier` + FR28/30b/43 gates exercised.
- **PRD FR65** (prd.md:1599): exit criteria doc tracking — Story 6.4 advances the dogfood half toward Phase-1 close.
- **PRD NFR-REL-05** (prd.md:1626): dogfood-loop integrity — agentskills surface validated parallel to rf-mcp surface (Story 3.3 + 5.5).
- **Architecture L317 + L410 + L1205 + L1402 + L1575 + L1718**: dogfood-integration.yml + AC-DOGFOOD-01 traceability + `mcp_per_test='suite'` default. Story 6.4 doesn't ship workflow changes (deferred to 9.1+9.2 per D-1).
- **Architecture L1564 Epic 6 closing-block framing**: "Metric-assertion dogfood (Epic 6 Story 6.4 candidate) remains for full `rf-mcp` parity per `AC-DOGFOOD-01`. **CI wiring deferred** per Phase-1 norm: `dogfood-integration.yml` stays smoke-only; real cross-repo CI integration is Story 9.1/9.2." — directly ratifies D-1 amendment.

### Existing infrastructure Story 6.4 builds on

- **Story 3.3 dogfood port pattern** at `tests/dogfood/rf-mcp/test_mcp_surface_parity.robot` + `parity-checklist-rf-mcp-mcp-surface.md` — file structure + Suite Setup + `[Tags] slow` + env-var indirection.
- **Story 5.5 dogfood port pattern** at `tests/dogfood/rf-mcp/test_trace_observability_parity.robot` + `parity-checklist-rf-mcp-trace.md` — honest-scope reframe (D-3 mirrored here as D-2) + mock-provider fixture pattern.
- **Story 6.1 `MetricsLibrary`** at `src/AgentEval/metrics/library.py` — 9 keywords.
- **Story 6.2 `AssertionsLibrary`** at `src/AgentEval/_assertions/library.py` — 5 keywords.
- **Story 6.3 `StatsLibrary`** at `src/AgentEval/stats/library.py` — 4 keywords + top-level `Get Keyword Tier`.
- **`src/AgentEval/types.py`** — `AgentRunResult`, `ToolCallTrace`, `Usage`, `AgentRunMetadata` for fixture building.
- **`robotframework-agentskills`** sibling clone at `/home/many/workspace/robotframework-agentskills/` — source corpus at `tests/eval/*.py` + `src/rf_skill_eval/scoring/*.py` + `eval/runs/` (vendored fixture candidates).

### Phase-1 carve-outs explicitly documented

- **CI wiring deferred (D-1)**: `dogfood-integration.yml` stays smoke-only per Story 1a.2 norm. Cross-repo CI dispatch is Story 9.1+9.2.
- **Multi-turn agent loop deferred (D-4 / DF-5.5-DOGFOOD-1 / C43)**: dogfood uses `AgentRunResult` fixtures built via `agentskills_sessions.py` helper, NOT live MCP+LLM driven multi-turn loop.
- **FR34a EvidenceBlock + paired-getter ergonomics (D-5 / C47 + C48)**: out-of-scope; deferred via existing catalog.
- **AssertionEngine wrap (DF-6.3-S1+S2 / C49+C50)**: Phase-1 stdlib backend is what dogfood exercises.

### Files to create / modify

**NEW (4 source files + 5 test files + 1 markdown):**
- `tests/dogfood/agentskills/__init__.py` — package marker.
- `tests/dogfood/agentskills/fixtures/__init__.py` — package marker.
- `tests/dogfood/agentskills/fixtures/agentskills_sessions.py` — Python helper module (~100-150 LoC).
- `tests/dogfood/agentskills/fixtures/sessions/<3-5 .json files>` — vendored fixture data.
- `tests/dogfood/agentskills/test_metrics_parity.robot` — Story 6.1 surface coverage (~12-18 tests).
- `tests/dogfood/agentskills/test_assertions_parity.robot` — Story 6.2 surface coverage (~8-10 tests).
- `tests/dogfood/agentskills/test_stats_parity.robot` — Story 6.3 surface coverage (~6-8 tests).
- `tests/dogfood/agentskills/parity-checklist-agentskills-metrics.md` — coverage matrix + findings.
- `tests/unit/dogfood/__init__.py` + `tests/unit/dogfood/test_agentskills_sessions.py` — unit test coverage for the Python helper.

**MODIFY:**
- `_bmad-output/implementation-artifacts/deferred-work.md` — add `DF-6.4-S*` entries per AC-6.4.8.
- `docs/phase-1-5-carry-overs.md` — add C-row(s) per AC-6.4.8.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Story 6.4 status flip.

**SOURCE DOCS AMENDED PRE-AUTHORING (per fix-the-losing-source-NOW):**
- `_bmad-output/planning-artifacts/epics.md` L1679-1683 — D-1 + D-3 amendments (parity-checklist path + dogfood-integration.yml smoke-only + dogfood-finding catalog).

## Dev Agent Record

### Completion Notes

All 11 dev tasks complete (Task 12 = code-review handled by next skill in `/goal` loop). Story 6.4 ships **29 dogfood `.robot` tests** (12 metrics + 11 assertions + 6 stats) all green when run via `uv run robot tests/dogfood/agentskills/`. **11 fixture-helper unit tests** at `tests/unit/dogfood/test_agentskills_sessions.py` exercise the `agentskills_sessions.py` Python helper (1217 total tests / 8 skipped, was 1206 at Story 6.3 close; +11 net).

**2 dogfood-findings uncovered + catalogued (AC-6.4.8 satisfied):**

- **DF-6.4-S1 (HIGH production bug)** Story 6.3 default Pass@k predicate fake-green — `r.completeness == "full"` is NEVER True for `AgentRunResult`-derived `KeywordRun` (valid values are `complete/partial/truncated`). Default predicate always returns 0.0. Workaround in Story 6.4 dogfood: explicit `build_complete_predicate()` factory. Phase-1.5 fix = C53.
- **DF-6.4-S2 (LOW doc drift)** `Metric.*` namespace prefix documentation drift — PRD + architecture say `Metric.Get Tool Call Count` but Story 6.1 ships `Get Tool Call Count` without prefix. Phase-1.5 decision = C54.

**Convention extensions:** none required — dogfood `.robot` files don't go through the `@keyword` walker. Verb allowlist + `_PHASE_1_SHOULD_CARVE_OUTS` unchanged.

**Phase-1 carve-outs applied per D-4 / D-5:**
- Fixture-driven dogfood scope (no live multi-turn loop — DF-5.5-DOGFOOD-1 / C43 + DF-5.5-DOGFOOD-2 / C44 + DF-6.1-S1 / C46).
- FR34a EvidenceBlock emission visibility deferred (DF-6.2-S1 / C47).
- Paired-getter ergonomics deferred (DF-6.2-S2 / C48).
- AssertionEngine matching-backend swap + 6-keyword Path A wrap deferred (DF-6.3-S1+S2 / C49+C50).

**`feedback_dogfood_fake_green_precheck` Story 5.5 retro applied** — verified pre-flip-to-review via grep for placeholder patterns (`Should Be Equal True True` etc.); none detected. **`feedback_carry_over_catalog_gate` UPSTREAM applied** — 10th consecutive story. **`feedback_caller_count_check` verified** — all 12 helpers in `agentskills_sessions.py` have caller count ≥ 2 (helper + unit test + `.robot` test).

### File List

**NEW (4 src/test infrastructure + 7 test files + 1 markdown):**
- `tests/dogfood/agentskills/__init__.py` — package marker.
- `tests/dogfood/agentskills/fixtures/__init__.py` — package marker.
- `tests/dogfood/agentskills/fixtures/agentskills_sessions.py` — Python fixture helper (~250 lines: 4 session-shape builders + 4 RF-callable getters + KeywordRun builder + Complete-predicate factory + JSON loader).
- `tests/dogfood/agentskills/fixtures/sessions/successful_search.json` — vendored fixture (single-tool happy path).
- `tests/dogfood/agentskills/fixtures/sessions/unnecessary_tool_call.json` — vendored fixture (search + delete, unnecessary call).
- `tests/dogfood/agentskills/fixtures/sessions/partial_completeness.json` — vendored fixture (timeout error + partial completeness).
- `tests/dogfood/agentskills/test_metrics_parity.robot` — 12 tests covering all 9 Story 6.1 `MetricsLibrary` keywords.
- `tests/dogfood/agentskills/test_assertions_parity.robot` — 11 tests covering 5 Story 6.2 `AssertionsLibrary` keywords + FR37 gate.
- `tests/dogfood/agentskills/test_stats_parity.robot` — 6 tests covering 4 Story 6.3 `StatsLibrary` keywords + `Get Keyword Tier` introspection.
- `tests/dogfood/agentskills/parity-checklist-agentskills-metrics.md` — coverage matrix + deferred parity + dogfood findings.
- `tests/unit/dogfood/__init__.py` — package marker.
- `tests/unit/dogfood/test_agentskills_sessions.py` — 11 unit tests for the fixture helper.

**MODIFY:**
- `_bmad-output/planning-artifacts/epics.md` L1679-1683 — D-1/D-3 amendments (vendor INTO agenteval + smoke-only CI + parity-checklist subdir path + `dogfood-finding` catalog convention).
- `_bmad-output/implementation-artifacts/deferred-work.md` — DF-6.4-S1 + DF-6.4-S2 entries added per AC-6.4.8.
- `docs/phase-1-5-carry-overs.md` — C53 + C54 catalog entries added (total 52 → 54).
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Story 6.4 status flip.

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-20 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (30th consecutive use of `feedback_spec_vs_ratified_doc_precheck` — 100% real-drift catch rate intact) caught 8 drifts: **D-1 HIGH structural** (AMENDED epics.md L1679-1683 — mirrors Story 3.3 D-A + Story 5.5 D-1 — vendor INTO agenteval at `tests/dogfood/agentskills/`, dogfood-integration.yml stays smoke-only, cross-repo CI deferred to 9.1+9.2 per architecture L1718 + epic L1564); **D-2 HIGH framing reframe** (mirrors Story 5.5 D-3 — agentskills tests are deterministic-SCORING / verdict-aggregation, NOT tool-call metrics; reframe as "dogfood agenteval surface AGAINST agentskills' scoring-test domain via parallel-derived AgentRunResult fixtures"); **D-3 LOW parity-checklist path** (AMENDED to `tests/dogfood/agentskills/parity-checklist-...md` per Story 3.3 + 5.5 subdir convention); D-4 MED load-bearing carry-out (C44+C46 require fixture-driven dogfood, NOT live multi-turn loop); D-5 MED carry-over constraints (C47+C48+C49+C50 = scope-limit visibility); D-6 LOW operational (`dogfood-finding` label doesn't exist — use deferred-work.md + carry-overs.md per project norm); D-7 LOW `Get Trajectory` PRD-vs-shipped drift (paired getter deferred per DF-6.2-S2 / C48); D-8 LOW reference precision (FR67 doesn't exist — actual references are AC-DOGFOOD-01 + FR19-22 + FR65 + NFR-REL-05). 11 ACs documented covering 4 `.robot` suites + 1 Python fixture helper + 1 parity checklist + DF-6.4-S* catalog entries. Closes AC-DOGFOOD-01 (agentskills half — full closure is Story 9.1+9.2 cross-repo CI). Applies Epic 5 retro NEW norms (`feedback_dogfood_fake_green_precheck` + `feedback_in_flight_spec_amendment` + `feedback_caller_count_check`) + UPSTREAM `feedback_carry_over_catalog_gate` (10th consecutive story). | Bob |
