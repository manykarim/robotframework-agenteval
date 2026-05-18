# Epic 1a Retrospective — Project Bootstrap + CI + ADR Ratification + Project-Hygiene Documentation

**Date:** 2026-05-18
**Epic:** 1a — Project Bootstrap + CI + ADR Ratification + Project-Hygiene Documentation
**Participants (LLM-agent personas + Project Lead):** Amelia (Developer/facilitator), Winston (Architect), John (PM), Mary (Analyst), Paige (Tech Writer), Sally (UX), Many (Project Lead)
**Previous retrospective:** Epic 0 retro 2026-05-17 — 3 project norms ratified (cross-LLM adversarial review; numeric claims machine-verified; serialized multi-agent reproductions). All 3 carried into Epic 1a.

## Epic 1a Summary

| Metric | Value |
|---|---|
| Stories completed | 6/6 (1a.1 → 1a.6) |
| Code-review findings caught + fixed | ~49 (1a.1: 6 / 1a.2: 10 / 1a.3: 5 / 1a.4: 10 / 1a.5: 9 / 1a.6: 9) |
| Cross-LLM reviews run | 6 consecutive (Claude Opus 4.7 + Codex CLI 0.117.0 every story) |
| Same-family blind spot demonstrations | 5 of 6 reviews (Claude solo 0 substantive findings; Codex caught real issues each time) |
| Pre-create-story drift check applications | 4 (1a.3 / 1a.4 / 1a.5 / 1a.6) — biggest catch 1a.4 (10 pre-existing PRD↔epics↔ADR drifts) + 1a.6 (5 drifts caught pre-authoring) |
| New project norms ratified mid-epic | 3 (CI-log forensics 2026-05-17; pre-create-story drift check 2026-05-17; "fix the losing source NOW" pattern 2026-05-17) |
| FRs wired (Phase-1 surface) | FR42, FR43, FR44, FR59, FR64, FR65 |
| Phase-1.5 carry-overs accumulated | 6 explicit items: macOS validation, full dogfood-integration, DCO check workflow, PR template, SHA-pinning of CI actions, conformance CLI proxy |

## What went well

1. **Cross-LLM adversarial review pattern (Many's biggest-win pick) is load-bearing — confirmed across 6 consecutive applications.** 5 of 6 reviews where Claude solo found 0 substantive issues + Codex caught real ones (5/9, 10/10, 9/9, 9/9 in stories 1a.3 → 1a.6 respectively). Story 1a.1 (the only one where Claude solo also found things) was where both reviewers *independently* caught the same H1+H2 — proving the value when both families converge on the same finding rather than one family rubber-stamping. **The pattern is structurally load-bearing**, not anecdotally useful.

2. **Pre-create-story drift check (Norm #4, ratified 2026-05-17) earned its cost on every application.** Story 1a.4: caught the title:9 / body:10 / AC:11 / final:9 doc-contract count mismatch + 4 non-architecture contracts in AC + 2 PRD-named drops. Story 1a.6: caught 5 drifts including `mcp_per_test` default mismatch + FR42 set count + stability label set + exit-criteria slug + max_runtime_seconds Library default. **All drifts caught BEFORE story authoring; upstream sources fixed via the "fix the losing source NOW" pattern.**

3. **CI-log forensics norm (Norm #5, ratified 2026-05-17) caught fake-green CI twice.** Story 1a.2 HIGH-1 (`continue-on-error: true` masked dogfood failures while showing "completed: success"); Story 1a.6 HIGH-1 (`--collect-only` collected the 6 FR42 tests but never executed their assertions in CI). Both load-bearing — without forensics norm, both regressions would have shipped invisibly.

4. **"Fix the losing source NOW" pattern proved consistently applicable.** Story 1a.2 established it for ratified-source-vs-spec drift; Stories 1a.3 → 1a.6 applied it 4+ more times. Drift caught is drift fixed, upstream, before authoring proceeds. No accumulation of "we'll fix it later."

5. **License-header enforcement hardened defense-in-depth at Story 1a.5.** Substring search → canonical-block validation at file prologue + shebang/encoding-cookie preservation. Pre-commit hook + ci.yml step both fire. The script + the CI step caught a real regression mid-epic.

6. **Honest framing held under pressure.** SECURITY.md NFR-SEC-05's "eliminates egress" Phase-1 reframe (1a.6 MED-6); exit-criteria-0x-to-1x.md 11→12 doc count fix (1a.6 LOW-7); 1a.2 dogfood-integration downgrade to placeholder rather than ship a misleading green. No quietly-dismissed LOW findings.

7. **Norm-emergence midstream worked.** Epic 0 retro ratified 3 norms; Epic 1a ratified 2 MORE (CI-log forensics; pre-create-story drift check) PLUS the "fix-the-losing-source-NOW" pattern. Norms are emergent from execution, not preordained.

## What challenged us

1. **Citation / inter-document drift (Many's biggest-pain pick) was the single most-common review-finding category.** Stories 1a.3, 1a.4, 1a.5, 1a.6 ALL had 2+ findings of this shape. Story 1a.4's 10 findings were mostly **pre-existing PRD↔epics↔ADR drift** that Epic 1a *surfaced* by being the first prose-heavy work to read everything against everything — not drift Epic 1a introduced. **Insight:** prose work is the canary that exposes silent drift in upstream specs.

2. **Same-family blind spot is structurally load-bearing.** Without Codex CLI, ~39 of the ~49 findings would not have been caught. If Codex CLI becomes unavailable or pricing-incompatible, the project needs a substitute cross-family reviewer (GitHub Copilot CLI, Claude Sonnet alternates, or human spot-checks). **Real risk:** the pattern depends on a tool the project doesn't control.

3. **Self-induced bug in Story 1a.1 — classic citation drift, caught by both reviewers.** ADR-018 was ratified during Story 0.3, then Story 1a.1's spec text contradicted ADR-018 by deferring `security/protocols.py` to Story 1a.6. Dev-story honored the spec, not the ADR. **Same-author-as-ADR + same-author-as-spec + same-family-review would have missed this.** Cross-LLM caught it because both families independently re-read ADR-018 against the spec against filesystem state.

4. **Story 1a.6 HIGH-1 is the canonical "single-LLM fake-green" case study.** Locally `pytest tests/acceptance/tier1 -q` reported `6 passed`. Author interpreted CI's collect-only exit-0 as "real tests now run" — wrong reading. Exit 0 from `--collect-only` means "collection succeeded," not "assertions passed." Codex caught it; author would have closed the story as done with a fake-green CI.

5. **Phase-1.5 carry-over accumulation has no explicit owner.** 6 carry-overs tracked across stories: macOS validation (D2.1 waiver, inherited from Epic 0), full dogfood-integration, DCO check workflow, PR template, SHA-pinning of CI actions, conformance CLI proxy. All tracked in story files; **no Phase-1.5 backlog story or owner assigned.** Risk: at Phase-1 close, they could slip past Epic 9 Story 9.3 retrospective if not surfaced.

6. **Spec authoring overhead grew with discipline.** Each story spec required deep cross-reference work pre-authoring; drift checks added quality but also pre-authoring overhead. **Acceptable trade-off given the cost of not doing it** (Story 1a.4 surfaced 10 pre-existing drifts that would have compounded), but worth tracking if overhead becomes a bottleneck.

7. **CI not retroactively forensic.** Story 1a.6 HIGH-1 was caught because Codex was prompted to look. The "collect-only-everywhere" pattern was Story 1a.2 baseline; nothing surfaced it for 4 stories until 1a.6 was the first story with real tests in that directory. **Implication:** norms catch incidents at the boundary; mid-stream silent dysfunction can persist for stories.

## Key insights

- **Cross-LLM family diversity matters MORE for prose + spec work than for code.** Code has tests; prose doesn't. Drift between specs is invisible without re-derivation, and same-family review skims past it.
- **Drift is mostly pre-existing, not story-introduced.** Story 1a.4 surfaced ~8 pre-existing PRD↔epics↔ADR drift cases. Future stories will continue to surface upstream drift; the "fix-the-losing-source-NOW" pattern is the right resolution path.
- **Norm-emergence midstream is a project-style insight.** Epic 0 ratified 3 norms; Epic 1a's stories ratified 2 more PLUS one pattern. Project will likely keep adding norms as new failure modes surface. Don't preordain the full norm set; let it emerge.
- **The pre-create-story drift check is roughly half the cross-LLM review's value, captured earlier in the cycle.** Catching drift pre-authoring is cheaper than catching it in review (no implementation rework). Worth amplifying.
- **Phase-1.5 carry-overs need a story-owned backlog.** Tracking-in-story-files is OK but risks slippage. Suggestion: create a Phase-1.5 backlog story at Epic 9 close (Story 9.3 or sibling) that catalogs all carry-overs + scopes them as Phase-1.5 work.

## Previous-retro follow-through (Epic 0 retro 2026-05-17)

| Epic 0 retro action item | Status in Epic 1a | Evidence |
|---|---|---|
| 1. Adversarial review pattern is project standard (mixed-family review) | ✅ Applied 6/6 stories | All 6 Epic 1a stories ran `/bmad-code-review (Using current Claude + Codex CLI subagent)`; ~39 of ~49 findings came from Codex; 5/6 had Claude-solo-0-findings |
| 2. Numeric claims machine-verified before commit | ✅ Applied each story; saved repeated rework | Examples: license-header count (20/20 verified), test count (6 tests verified pre-commit-msg), 4 NFR-MAINT-04 sections verified per file, doc-contract count (11 + README = 12) caught by 1a.6 LOW-7 (mid-stream drift, not commit-time miss) |
| 3. Serialize multi-agent reproductions sharing workspace | ✅ Not triggered (no multi-agent reproduction in Epic 1a) | Norm holds; will re-trigger when Story 1b.5 or similar runs reproductions |
| 4. Story 1a.3 create-story prompt must include ADR-001 stub coordination | ✅ Preserved | ADR-001 §Stub Notice + Amendments Log byte-identical sha256 verified post-Story-1a.3 |
| 5. Story 1a.4 create-story prompt must verify listener-integration.md + mcp-coverage-detection.md | ✅ Both contracts shipped + listener-integration ratified | 11 contracts total (9 architecture-canonical + 2 empirical adds: listener-integration + junit-xml-enrichment) |
| 6. Story 1b.1 create-story prompt must lift 12 production-relevant deferred items | ⏳ PENDING — this is the FIRST Epic 1b action item below | Owner: Story 1b.1 create-story prompt; applies next |

**6/6 Epic 0 commitments addressed.** Action item 6 carries forward as Epic 1b's primary prep item.

## Epic 1b preview + dependencies

**Epic 1b: Cross-Cutting Kernel + Conformance Scaffolding + Determinism Contract** (6 stories)

| Story | Scope | Epic 1a dependency |
|---|---|---|
| 1b.1 | `_kernel/{context, tier, run_async}.py` foundational | Story 0.2 deferred-work items (12+), Story 1a.2 ci.yml (split unit-test path same as tier1) |
| 1b.2 | `_kernel/{trace_store, redaction, coverage}.py` observability | ADR-016 trust-floor semantic (1a.3 ratified) |
| 1b.3 | `_kernel/{discovery, guardrails}.py` adapter discovery + `@guarded_fanout` | ADR-013 entry-points (1a.3 ratified) + ADR-015 (1a.3 ratified) |
| 1b.4 | CodingAgentAdapter Protocol + InProcessAdapter / SubprocessAdapter ABCs | ADR-012 Protocol (1a.3 ratified) |
| 1b.5 | Conformance harness + loader + fixture schema + 6 reference fixtures | conformance-fixture-format.md (1a.4 stub) |
| 1b.6 | Determinism Contract doc (FR63) + 5 CI-enforcement conventions tests | determinism-contract.md (1a.4 stub), tests/unit/conventions/ placeholder (1a.1 baseline + 1a.2 ci.yml convention enforcer step) |

**All Epic 1a dependencies satisfied.** Epic 1b starts cleanly.

## Significant discoveries check

**No.** Epic 1b plan stands. Architecture L429-434 ratified pre-Epic-1a; deferred-work.md tracks all 12+ Story 0.2 items already; ADR amendments all done; HIGH-1 ci.yml fix from 1a.6 partially anticipates 1b.1's needs. No fundamental assumption shifts. The 4 prep items below are story-spec inputs, not epic-replan triggers.

## Action items (carrying into Epic 1b)

| # | Action | Owner | Applied at | Source |
|---|---|---|---|---|
| 1 | **Lift the 12+ Story 0.2 deferred-work items into Story 1b.1 Dev Notes UP-FRONT.** Threading.RLock, killpg+pid directly, EPERM/ESRCH distinction, atexit-on-SIGKILL gap acknowledgement, env minimization, MappingProxyType for ServerSpec.env, startup_timeout_s implement-or-remove, latency split (terminate_to_signal_delivered_ms + signal_to_reaped_ms), startup_latency_ms → process_lifetime_ms rename, post-kill liveness verification, state-transition release event recording, auto-installed SIGTERM handler default. | bmad-create-story prompt for Story 1b.1 | Next: Story 1b.1 create-story | Carries forward Epic 0 retro action #6; many's biggest-prep-concern pick |
| 2 | **ci.yml unit-test path: replicate the Story 1a.6 HIGH-1 pattern.** When Story 1b.1 lands real `tests/unit/kernel/test_*.py` files, split `tests/unit` from the collect-only sweep into a dedicated `uv run pytest tests/unit -q` execute step. No exit-5 leniency for any dir that now has real tests. Convention enforcer dir (`tests/unit/conventions`) too once Story 1b.6 lands its 5 enforcement tests. | Story 1b.1 Dev Notes (ci.yml restructure task) | Story 1b.1 implementation | Story 1a.6 HIGH-1 lesson generalized |
| 3 | **Apply pre-create-story drift check to Story 1b.1 (5th consecutive use of `feedback_spec_vs_ratified_doc_precheck`).** Sources to cross-check: architecture L429-434, ADR-009 / ADR-A1 / ADR-A5 / ADR-016 / ADR-018, deferred-work.md, Story 0.2 findings doc, PRD FR11b/FR41/FR42. Surface drift via AskUserQuestion BEFORE story authoring. | bmad-create-story workflow norm | Story 1b.1 create-story | `feedback_spec_vs_ratified_doc_precheck` — proven 4/4 in Epic 1a |
| 4 | **New norm: inter-document citation drift is a first-class review category.** Cross-LLM review prompt for Story 1b.1 onward MUST explicitly ask the cross-family reviewer to *re-derive each cited fact from the cited source*, not just check that citations exist. The "fix-the-losing-source-NOW" pattern remains the resolution. | Project methodology; applied starting Story 1b.1 review | Every future code-review | New norm emergent from Epic 1a Story 1a.4 (8 of 10 findings were citation drift) |
| 5 | **Phase-1.5 carry-over backlog needs explicit ownership.** Create a Phase-1.5 backlog story under Epic 9 (or a sibling tracking story) that catalogs all 6+ Phase-1.5 carry-overs from Epic 0 + Epic 1a: macOS validation, full dogfood-integration, DCO check workflow, PR template, SHA-pinning of CI actions, conformance CLI proxy. Owner: future PM/architect alignment session at Epic 9 close. | Epic 9 planning (deferred) | Phase-1 close (Story 9.3 or sibling) | Emergent risk from Epic 1a carry-over count |

## Readiness assessment

| Dimension | Status |
|---|---|
| All 6 Epic 1a stories `done` in sprint-status | ✅ |
| Latest commit pushed + CI green (SHA `344ccc1` review-patches commit) | ✅ ci + security-scan + docs-build all PASS |
| AgentEval class wired + Get Effective Config discoverable via RF static-library | ✅ verified locally + in CI tier1 + smoke steps |
| Apache 2.0 license headers on all 20 .py files + canonical-block validation | ✅ pre-commit + ci.yml both fire |
| 14 non-spike ADRs ratified + ADR-001 catalog body | ✅ |
| 11 doc-contract skeletons + error-class-hierarchy substantive content | ✅ |
| CONTRIBUTING.md + SECURITY.md + 3 issue templates | ✅ |
| stability-surface.md Phase-1 registry populated (AgentEval surface + sandbox surface) | ✅ |
| exit-criteria-0x-to-1x.md 4-criteria stub filled | ✅ |
| Phase-1.5 carry-overs tracked in story files | ✅ (no owner — action item #5) |
| Epic 1b Story 1b.1 plan validated against architecture L429-434 | ✅ |
| Stakeholder acceptance (Many) | ✅ via this retro |
| Unresolved blockers | None |
| Significant discoveries requiring Epic 1b replan | None |

**Verdict:** Epic 1a is fully complete. Many's choice — start Epic 1b Story 1b.1 immediately via `/bmad-create-story`. Action items 1-4 feed directly into the Story 1b.1 spec; action item 5 is deferred to Epic 9 planning.

## Next steps

1. **Sprint-status updated:** `epic-1a-retrospective: optional` → `done`; `epic-1a: done` (already flipped on 2026-05-18 in prior commit).
2. **Begin `/bmad-create-story` for Story 1b.1** (Foundational Kernel — Context + Tier + Async Bridge). Many's choice: chain immediately.
3. **Story 1b.1 create-story must execute action items #1, #3, #4 inline:** lift deferred-work items as Dev Notes; apply pre-create-story drift check; ensure cross-LLM-review prompt at story-review-time will include the citation-drift-re-derivation directive.
4. **Story 1b.1 dev-story must execute action item #2 inline:** ci.yml restructure for `tests/unit` path concurrent with landing the first real unit tests.
5. **Action item #5 (Phase-1.5 carry-over backlog) is deferred to Epic 9 planning** — no immediate action needed; track in `deferred-work.md` as a meta-concern.
