# Phase 1 Retrospective — robotframework-agenteval

**Date:** 2026-05-25
**Facilitator:** Amelia (Developer) — synthesizing across all 11 Phase-1 epic slots autonomously per `/goal` execution model.
**Project owner:** Many Kasiriha (solo + AI-agent-assisted execution model).
**Phase 1 scope:** Epics 0 → 9 (≈11 epic slots; ~50 stories).

---

## What shipped vs planned

| Dimension | PRD plan | Phase-1 actual | Delta |
| --- | --- | --- | --- |
| Calendar | 10–12 weeks at human-pace solo + AI-agent-assisted throughput (PRD honest-framing estimate 2026-05-17). | Single-day calendar autonomous-loop delivery (2026-05-25). | The 10–12 week estimate assumed human-pace dev with AI assistance. The autonomous `/goal` loop is faster than the estimate by an order of magnitude — but per `feedback_honest_framing`, this is NOT a "Phase-1 shipped in a day" claim, because the *quality bar* (cross-LLM review, drift checks, integration tests, retros) was front-loaded into per-story workflow. The day-of-delivery is a downstream consequence of months of norm-ratification + tooling investment. |
| Stories | ~50 stories across 11 epics. | All shipped done per sprint-status.yaml. | 0 dropped stories. |
| Tests | Target: green pytest + conformance + integration. | 1353 pass + 8 skipped + 5 warnings. Ruff/format/mypy clean on 94 src files. | Met. |
| Catalog | Target: documented carry-over registry (Story 1c.1 ratification). | 66 catalog entries as of Phase-1 close. | Met. |
| Ratified norms | None planned (norms emerge from retros). | 23 ratified `feedback_*` records across Epics 0–8 retros. | Beyond plan — norms are the load-bearing system memory. |

## Top 3 successes

### 1. Cross-LLM adversarial review project standard (Epic 0 retro ratification) → 30+ STAR catches across Epics 2–7

`feedback_review_methodology_norms` (Epic 0 retro) ratified cross-LLM-family adversarial review as the project standard. Operationally: Codex CLI + Claude CLI as parallel reviewers; N-way agreement triage; integration with `feedback_codex_probe_fitness` (Epic 2 retro) for behavioral probes.

Concrete impact across Epics 2–7:
- Story 1b.1 Codex STAR: `acquire()` always spawned regardless of `scope=` (silent bug; all 3 Claude reviewers missed it).
- Story 1b.2 Codex C1: resource-vs-span attribute model bug (production would have silently returned empty).
- Stories 3.2 + 3.3 Codex behavioral probes: `MCPConnectionLostError` mapping + `errlog=sys.__stderr__` crash.
- Story 6.4 DOGFOOD-FINDING-1 fix-NOW: `_default_pass_predicate` `"full"` → `"complete"`.
- 12+ consecutive Auditor-1-way HIGH TPs on PRD/ADR/spec re-derivation across Epics 4–7 (the "near-certain band" extension).

The streak broke in Epic 8 (cross-LLM pipeline degradation; see "Top 3 surprises" #1) — but the streak existed, and the catches were real.

### 2. Pre-create-story drift check (Epic 1a retro ratification) → 41 consecutive uses, 100% catch rate

`feedback_spec_vs_ratified_doc_precheck` (Epic 1a retro) ratified the pre-create-story drift check — every new story's spec is re-derived from PRD + architecture + ADRs BEFORE authoring. Catches "your story is wrong" before any code is written.

Stats: 41 consecutive uses (Story 1b.1 through Story 9.2), 100% real-drift catch rate (every use surfaced 3–8 drifts that would otherwise have shipped). Notable scope extensions:

- Originally a citation-drift check; Epic 7 retro extended scope to usability + concept-disambiguation + heuristic-limitation gates (the broader definition is the operational reality).
- Story 8a.1 D-2 path-of-least-amendment decisions emerged from this check.
- Story 8a.2 D-6 listener class-path drift was caught at story-create time, propagated to 7 downstream artifacts via `feedback_citation_drift_first_class` fix-NOW pattern.

This is the most load-bearing norm in the project.

### 3. Interleaved dogfood (Epic 3 retro ratification) → real production bugs caught at week-3-equivalent

`feedback_interleaved_dogfood_load_bearing` (Epic 3 retro) ratified that real downstream libraries are the highest-yield bug-finding surface. Operationally: every epic ships a dogfood story alongside its API surface.

Concrete impact:
- Story 3.3 DOGFOOD-FINDING-1 caught the `errlog=sys.__stderr__` SDK crash that Story 3.1's 4-reviewer code review missed (because unit tests used `in_memory` transport).
- Story 5.5 DOGFOOD-2 caught the adapter-span-instrumentation gap that latent across all of Epic 5 (5 stories of detection latency without dogfood).
- Story 6.4 DOGFOOD-FINDING-1 caught the `_default_pass_predicate` `"full"` enum drift via real dogfood (parallel-derived from agentskills' deterministic-scoring tests).
- Story 7.4 DOGFOOD-FINDING-1 caught the stub-adapter `false_activation_rate=1.0`-by-design limitation, which then ratified the `feedback_dogfood_validation_ceiling` norm (Epic 7 retro NEW).

The dogfood pattern alone justifies the 11-epic Phase-1 calendar.

## Top 3 surprises

### 1. Cross-LLM review pipeline degradation in Epic 8 — broke the 30+ STAR streak

Epic 8 ran with Codex CLI rate-limited from Story 8a.1 onward; Claude CLI returned 0-byte / missing artifacts for 4 of 5 stories (8a.2, 8b.1, 8b.2, 8b.3). The 30+ STAR catch streak from Epics 2–7 BROKE because the reviewer slot was empty — not because the code got better.

Mitigation: end-to-end integration tests as forcing function (`feedback_integration_test_forcing_function` Epic 8 retro NEW). Caught 5 empirical bugs across 4 stories. **But the source-doc drift detection lane (Auditor 1-way HIGHs) was effectively dark for 4 of 5 stories** — a measurement gap that must be addressed before Epic 9 / Phase-2 / 1.0 promotion.

Action item: Epic 8 retro Action #1 — fix cross-LLM review pipeline + add in-loop circuit-breaker. The Epic 7 retro retro-of-retro discovered `claude -p --dangerously-skip-permissions --model opus` works as a replacement invocation (162-line response on a long prompt).

### 2. Listener resolution gotcha — 5 stories shipped using broken canonical invocation

`docs/contracts/listener-integration.md` L38 documented `--listener AgentEval.telemetry.listener` (module-path-only) as canonical since Story 5.1 (2026-05-19). The short form is *accepted* by RF 7.x without error but the `Listener` class hooks (`start_suite`, `start_test`, `xunit_file`) do NOT fire — RF takes the module-as-listener path which expects a top-level `ROBOT_LISTENER_API_VERSION` (not present). Explicit `Module.Class` path is required.

**5 stories shipped using this broken canonical invocation** because their listener hooks were no-ops at the time (Stories 5.1, 5.2, 5.3, 5.4, 5.5). Story 8a.2 was the first story with a directly-observable listener-hook side effect (the `trace_id` tag in `output.xml`) — surfaced the bug.

Resolution: 3 contract docs + 7 scaffolded files / recipes amended in-place per `feedback_citation_drift_first_class` fix-NOW pattern. New norm `feedback_contract_doc_invocation_smoke_test` ratified (Epic 8 retro NEW) — contract docs documenting CLI invocations MUST carry subprocess-based integration smoke tests.

### 3. `data.tags` vs `result.tags` empirical API-surface ambiguity (Story 8a.2 D-5)

RF Listener v3's `start_test(data, result)` gives two candidate objects with similar `tags` APIs. RF docs are ambiguous. Empirical truth: only `result.tags.add(...)` surfaces in `output.xml`; `data.tags.add(...)` is a no-op.

Story 8a.2 initially used `data.tags.add(...)` based on docs + unit-test mocks. Integration test against real RF subprocess caught the bug. DebugListener probe pattern (`tests/integration/probes/debug_listener.py`) committed as canonical reference for future API-surface ambiguity checks.

New norm `feedback_listener_hook_api_surface_empirical_check` ratified (Epic 8 retro NEW).

## What would change for Phase 2

1. **Lock in cross-LLM review fallback invocation early.** Epic 8 retro Action #1 — the `claude -p --dangerously-skip-permissions --model opus` pattern works (Epic 7 retro-of-retro proved it on 162-line response). Pre-validate Codex quota + budget tracking + third LLM family (Gemini-CLI / Mistral-CLI) BEFORE first Phase-2 story.

2. **Contract-doc invocation smoke tests (Epic 8 retro NEW norm).** Every `docs/contracts/*.md` documenting a CLI / subprocess invocation MUST carry a subprocess-based integration smoke test. The listener-resolution gotcha (Surprise #2) was a 5-story-old contract drift that this norm catches at contract-author time.

3. **Circuit-breaker in autonomous `/goal` loop for degraded cross-LLM review.** Epic 8's review-pipeline failure was not surfaced for operator intervention until THIS retro — the loop happily proceeded through 4 stories with zero cross-LLM review. Add an in-loop check that aborts to operator on ≥2 consecutive empty review artifacts.

4. **Same-PR closure for XS-effort carry-overs.** Story 5.5 retro #4 ratified the dogfood-finding severity-differentiation. Phase-1.5 work that's XS-effort + same-PR closeable should close in-flight, NOT catalog (per Story 6.4 fix-NOW precedent on DOGFOOD-FINDING-1). Epic 8 Action #7 identified C59 (Stat.Get Pass At K predicate compat) as a candidate — apply the norm more aggressively in Phase-2.

5. **Promote stability-surface entries earlier.** 9 of `AgentEval`'s public config params are `provisional` (Story 1a.6 registry). Criterion #4 of exit-criteria-0x-to-1x.md gates 1.0 on zero `provisional`. **Resolve these as early Phase-2 work** so the 3-month-no-break window can start.

## Hidden labor that emerged

- **Retro-on-retro (Epic 7 retro NEW pattern):** the Epic 7 retro itself was subject to cross-LLM critical review + caught 2 HIGH + 2 MED. Applied at Epic 8 retro (2 HIGH + 2 MED + 4 LOW + 6 missing-content). This is the load-bearing pattern that catches retro-author confirmation bias.

- **23 ratified norms across Epics 0–8.** Each retro produced 2–4 ratified norms. The norms ARE the project's procedural memory — `feedback_spec_vs_ratified_doc_precheck` + `feedback_carry_over_catalog_gate` UPSTREAM together catch 22+ drifts per epic on average.

- **In-flight spec amendments (Epic 5 retro NEW).** Stories 8a.2 + 8b.1 + 8b.2 each carried in-flight amendments — the dev decisions diverged from AC text during implementation, and the norm forces same-commit amendment to keep spec + impl in lockstep.

- **Cross-doc citation drift fix-NOW (Epic 1a retro):** Story 8a.2 D-6 propagated to 3 contract docs + 7 scaffolds; Story 6.4 DOGFOOD-FINDING-1 fix-NOW pattern was extended to Epic 8.

## Dogfood findings logged (Phase-1 cumulative)

13+ findings catalogued across rf-mcp + agentskills ports:

| Source story | Severity | Disposition |
| --- | --- | --- |
| Story 3.3 DOGFOOD-FINDING-1 | HIGH | Fixed in-PR (`errlog=sys.__stderr__`) |
| Story 3.3 DOGFOOD-FINDING-A | MED | Workaround applied; real fix DF-3.3-S1 Phase-1.5 |
| Story 5.5 DOGFOOD-1 | MED | C43 multi-turn agent loop → Phase-2 |
| Story 5.5 DOGFOOD-2 | HIGH | C44 adapter span instrumentation → Phase-1.5 |
| Story 5.5 DOGFOOD-3 | INFO | Doc-only ADR-016 D1 clarification |
| Story 5.5 DOGFOOD-4 | MED | C45 — CLOSED same-PR (Listener-less `Get Last Warnings`) |
| Story 6.4 DOGFOOD-FINDING-1 | HIGH | Fixed in-PR fix-NOW (`_default_pass_predicate` `"full"` → `"complete"`) |
| Story 6.4 DOGFOOD-FINDING-2 | LOW | C54 — Metric.* namespace doc drift → Phase-1.5 |
| Story 7.4 DOGFOOD-FINDING-1 | MED | C60 — stub-adapter limitation + 8 remaining skills → Phase-2 / Epic 9 |
| Story 7.4 DOGFOOD-FINDING-2 | LOW | C61 — caller-gap on path constants → Phase-1.5 |
| Story 9.1 / 9.2 — no NEW findings (gap-analysis closure stories) | — | Documented existing findings + ceiling lines. |

**2 in-PR fixes** (Story 3.3, Story 6.4) + **1 same-PR close** (Story 5.5 DOGFOOD-4 → C45) + **10+ catalogued** as Phase-1.5 / Phase-2 carry-overs. Pattern: `feedback_dogfood_finding_severity_differentiation` (Epic 5 retro #4) categorizes (a) doc-only / (b) same-PR / (c) Phase-1.5 / (d) Phase-2 — applied cleanly across Epics 3–7.

## Phase-1 success criteria status

| AC reference | Status | Notes |
| --- | --- | --- |
| AC-DOGFOOD-01 (rf-mcp) | ✅ Closed Story 9.1 | 17/58 ported + 4 stays-custom + 38 Phase-2 batch port. |
| AC-DOGFOOD-01 (agentskills) | ✅ Closed Story 9.2 | Metrics/assertions/stats 100% + 3-of-11 skills + 8 remaining at C60. |
| AC-CONFORMANCE-01/02 | ⚠ Schema shipped Story 8a.2; real adapter dispatch C63 Phase-1.5 | Conformance CLI emits well-formed reports; per-fixture execution is deferred. |
| AC-MCP-OBSERVE-01/02/03 | ✅ Story 3.1 + Story 5.2 | Stdio + in-memory + hosted-mcp observer paths. |
| AC-SIMPLICITY-01/02 | ✅ Story 5.3 + Story 5.4 | Evidence block + paired-getter pattern. |
| AC-DISCOVER-01 (MVP) | ✅ Story 4.4 | Cohort cost guardrail + Tool Discoverability. |
| AC-DISCOVER-02 (cost guardrail) | ✅ Story 4.4 | `@guarded_fanout` decorator. |
| All 11 epics | ✅ done | per sprint-status. |
| 19 ADRs | ✅ accepted | per `docs/adr/` README. |

## Open issues flagged at Phase-1 close

- **66 catalog entries** at `docs/phase-1-5-carry-overs.md` — none ship-blocking individually; collectively define the Phase-1.5 + Phase-2 backlog.
- **Cross-LLM review pipeline** (Epic 8 retro Action #1) — load-bearing for the project's 30+ STAR catch streak. Restore before Epic 10 (Phase-2 Native SDK Adapters).
- **`@guarded_fanout` MCPLibrary legacy gap** (Epic 4 retro Action #6 inherited, 5+ epics old) — must resolve OR formally retire as Phase-2 carve-out.
- **2 ❌ exit criteria** (external contributors + downstream use cases beyond rf-mcp / agentskills) — explicitly Phase-2 work; 1.0 promotion blocked on these.

## References

- [`docs/contracts/exit-criteria-0x-to-1x.md`](../../docs/contracts/exit-criteria-0x-to-1x.md) — 6 promotion criteria (Story 9.3 final content).
- [`docs/phase-1-5-carry-overs.md`](../../docs/phase-1-5-carry-overs.md) — 66 catalog entries.
- All per-epic retros at `_bmad-output/implementation-artifacts/epic-{0,1a,2,3,4,5,7,8}-retro-*.md`.
- 23 ratified norms at `/home/many/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/MEMORY.md`.

## Closure

Phase 1 closes 11/11 epic slots done, ~50 stories shipped, 1353 tests, 94 src files, 66 catalog entries, 23 ratified norms, 13+ dogfood findings, 6 exit criteria documented (4 ⚠ + 2 ❌ at Phase-1 close).

Phase-1 is technically complete; **0 of 6 exit criteria are fully satisfied for 1.0 promotion** (sustained-window evidence + community work + downstream-adoption work all explicitly Phase-2). The project is at the boundary between Phase-1 (build the system) and Phase-1.5 / Phase-2 (validate it in the world).

Onward to Phase 2.
