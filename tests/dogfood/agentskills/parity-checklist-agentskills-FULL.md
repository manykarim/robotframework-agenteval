# robotframework-agentskills Full-Surface Parity Synthesis (Story 9.2, 2026-05-25)

**VALIDATION-CEILING:** this doc VERIFIES that every `robotframework-agentskills` custom test surface is classified (port / stays-custom / Phase-2-batch / live-provider-deferred); does NOT VERIFY that the cross-repo CI workflow has gated real PR regressions over a 7-day window (DF-9.2-S1 / C66 deferred), nor live LLM activation-quality discrimination (DF-7.4-S1 / C60 Epic 9+ live-provider dogfood).

## Purpose

Phase-1 close gap-analysis for `robotframework-agentskills` dogfood parity. Composes:
- Story 6.4 metrics+assertions+stats parallel-derivation (see `parity-checklist-agentskills-metrics.md`).
- Story 7.4 skill-discoverability dogfood — 3 of 11 skills (see `parity-checklist-agentskills-discoverability.md`).
- Story 9.2 synthesis: classify the **remaining 8 skills + any uncovered custom-test surface** + document the cross-repo workflow handoff.

## Classification of `robotframework-agentskills` custom test surface

agentskills' upstream `tests/` directory uses parallel-derived `AgentRunResult` fixtures rather than running real LLM-driven scoring — the dogfood replicates this **deterministic-scoring** pattern in `.robot` form. Per Story 6.4 D-2 ("agentskills tests are deterministic-SCORING not tool-call metrics — reframe as 'dogfood agenteval surface AGAINST parallel-derived AgentRunResult fixtures'"), the parity surface is the *agenteval keyword-surface coverage of the scoring scenarios*, NOT 1:1 test ports.

| agentskills surface | Coverage status | Phase-1 closure | Phase-2 / deferred |
| --- | --- | --- | --- |
| Metrics computation (token usage, cost, latency p95) | ✅ Story 6.4 `test_metrics_parity.robot` (12 tests) covers agentskills' scoring-metric API via parallel-derived `AgentRunResult` fixtures. | **CLOSED** — Phase-1 keyword surface 100%. | - |
| Trajectory + Tool-call + Response assertions | ✅ Story 6.4 `test_assertions_parity.robot` (11 tests). | **CLOSED** — assertion-engine gate behavior + 4 trajectory modes verified. | - |
| Statistical primitives (Pass@k, Wilson CI, run-determinism) | ✅ Story 6.4 `test_assertions_parity.robot` includes stat-coverage (6 stat tests). | **CLOSED**. | - |
| Skill-discoverability per-skill (11 skills total) | ⚠️ Story 7.4 covers 3 (rf-browser, rf-results, rf-libdoc-search); 8 deferred (rf-appium, rf-keyword-builder, rf-libdoc-explain, rf-requests, rf-resource-architect, rf-restinstance, rf-selenium, rf-testcase-builder). | **Phase-1 partial** — 3 of 11 covered with stub-adapter framing. | Phase-2 / Epic 9+ live-provider dogfood (DF-7.4-S1 / C60) + 8 remaining task-YAML authoring + vendoring. |
| Skill activation reliability (Pass@k against single skill) | ✅ Story 7.1 `Skill.Get Activation Decision` + Story 7.2 cohort exercised against vendored skills in Story 7.3 integration test + Story 7.4 dogfood. Devon's Journey 4 Phase-1 portion (Tier-1 static + Tier-3 cohort) is end-to-end-verified. | **CLOSED** for Devon's Phase-1 Journey 4 per AC L1969. | Phase-2 Judge layer (Tier-2) per Story 12.3. |
| Live LLM provider discrimination quality | ❌ Not verified in Phase-1 (stub adapters embed target skill name → `false_activation_rate=1.0` by design). | DOGFOOD-FINDING-1 documented + accepted as validation-ceiling. | Phase-2 / Epic 9+ live-provider dogfood run (C60). |

**Closure interpretation per AC L1967 / AC-9.2.1:** every agentskills custom surface is either covered, has explicit stays-deferred rationale (with C-entry in `docs/phase-1-5-carry-overs.md`), OR is explicitly out of scope for Phase-1 (live LLM provider work). **No uncategorized custom surface remains.**

## Cross-repo CI workflow status

Per Story 9.2 D-1 + Story 9.1 D-2 (same path-of-least-amendment as rf-mcp):

| Stage | Owner | Status |
| --- | --- | --- |
| Build agenteval wheel | agenteval CI | ✅ |
| Install wheel into clean venv | agenteval CI | ✅ |
| Vendor agentskills skill files | This repo | ✅ Story 7.4 vendored 3 skill .md files + 3 task YAMLs |
| Run agentskills parity suite under agenteval | agenteval CI | ✅ Story 9.2 extends `dogfood-integration.yml` `agentskills-parity-suite-smoke` job — runs the 3 dogfood `.robot` suites locally on the agenteval wheel. |
| Block agenteval PRs on agentskills regression | agenteval CI (cross-repo trigger) | ❌ Out of scope — requires agentskills to add agenteval as dev dep. |
| 8-remaining-skills live-provider coverage | Phase-2 / Epic 9+ live-provider dogfood | ❌ DF-7.4-S1 / C60. |
| 7-consecutive-day monitoring + ≥1 real PR blocked | Phase-1 close validator manual | ❌ DF-9.2-S1 / C66. |

## Devon's Journey 4 Phase-1 closure (AC-9.2.3)

- **Tier 1 (static skill validation):** Story 2.1 `Skill.Get Frontmatter` etc. — exercised in `tests/integration/skills/test_devon_stacked_validation.py` (Story 7.3).
- **Tier 3 (cohort discoverability + activation reliability):** Story 7.1 `Skill.Get Activation Decision` + Story 7.2 `Skill.Get Discoverability` + Story 7.3 stacked recipe + Story 7.4 dogfood against 3 real skills.
- **Tier 2 (Judge layer):** explicitly Phase-2 — Recipe #4 carries the `# TODO Phase 2: Judge.Get Score here` marker.

**Devon's Phase-1 Journey 4 is end-to-end-verified against real agentskills skills (rf-browser, rf-results, rf-libdoc-search).** AC-9.2.3 satisfied.

## Phase-2 handoff (DF-9.2-S1 / C66)

When agentskills adopts agenteval as a dev dep (Phase-2 governance decision):
1. The 8 remaining skills get vendored + task YAMLs authored (mechanical work).
2. Live LLM provider dogfood run validates real discrimination quality (closes C60).
3. Cross-repo dispatch restores the AC L1967 "blocks agenteval PRs" gate.
4. 7-day monitoring evidence collected naturally.

## References

- AC-DOGFOOD-01 (PRD): satisfied for the agentskills half.
- Story 6.4 (`parity-checklist-agentskills-metrics.md`): metrics+assertions+stats.
- Story 7.4 (`parity-checklist-agentskills-discoverability.md`): 3-of-11-skills coverage.
- Story 7.3 (`tests/integration/skills/test_devon_stacked_validation.py`): Devon's Tier-1+Tier-3 stacked validation.
- `_bmad-output/implementation-artifacts/deferred-work.md` DF-7.4-S1, DF-9.2-S1.
- `docs/phase-1-5-carry-overs.md` C60 (Story 7.4 8-skill deferral), C66 (Story 9.2 downstream adoption + 7-day monitoring).
