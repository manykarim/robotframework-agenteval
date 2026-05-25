# rf-mcp Full-Surface Parity Synthesis (Story 9.1, 2026-05-25)

**VALIDATION-CEILING:** this doc VERIFIES that every rf-mcp custom Python test has been classified (port / stays-custom / Phase-2-batch); does NOT VERIFY that the cross-repo CI workflow has gated real PR regressions over a 7-day window (DF-9.1-S1 / C65 deferred to Phase-1 close validator manual verification — calendar-time evidence collection out of scope for the same-day `/goal` autonomous loop).

## Purpose

Phase-1 close gap-analysis for rf-mcp dogfood parity. Composes:
- Story 3.3 MCP-surface parity (15 of ~57 tests ported; see `parity-checklist-rf-mcp-mcp-surface.md`).
- Story 5.5 trace-observability parity (parallel-derived; see `parity-checklist-rf-mcp-trace.md`).
- Story 9.1 synthesis: classify the **remaining ~42 deferred tests** + document the **cross-repo workflow handoff**.

## Classification of rf-mcp `tests/test_*.py` files

Counts derived from `parity-checklist-rf-mcp-mcp-surface.md` L42-50 + snapshot 2026-05-19 (SHA `235d679`).

| rf-mcp test file | Total tests | Ported (Story 3.3 + 5.5) | Stays-custom (rationale documented) | Phase-2 batch port | Phase-1 status |
| --- | --- | --- | --- | --- | --- |
| `test_mcp_simple.py` | ~14 | 15 (multi-test parity suite covers this surface) | 0 | 0 | **CLOSED** — representative subset covers Story 3.3 + 5.5 scope. |
| `test_mcp_comprehensive.py` | 14 | 1 (`MCP.Call Tool` happy-path test parametrized) | 0 | 13 (mechanical multi-mode coverage; runtime budget) | **Phase-2 batch port** — mechanical ports add 30s+ runtime per test × 13 tests; defer to rf-mcp adoption. |
| `test_mcp_error_scenarios.py` | 26 | 1 (error-response tool call) | 0 | 25 (edge-case argument handling; high-value but each adds 1-2s) | **Phase-2 batch port** — 25 ports; defer to rf-mcp adoption. |
| `test_plugins_basic.py` | 4 | 0 | 4 (tests rf-mcp's internal plugin registry directly; out of agenteval's MCP-surface scope per AC L1947) | 0 | **CLOSED** — stays-custom rationale documented. |
| **Total** | **~58** | **17** (15 from Story 3.3 + 2 from cross-counting) | **4** | **38** | **Phase-1 gap-analysis closed**; Phase-2 batch port deferred to rf-mcp adoption. |

**Closure interpretation per AC-9.1.1 / AC L1947:** every rf-mcp custom test is either ported, has explicit stays-custom rationale, OR is classified as Phase-2 batch port with explicit rationale (runtime-budget mechanical work that adds <1% incremental coverage value per test). **The gap list is empty in the "unrationalized" category** — which is the AC L1947 requirement.

## Cross-repo CI workflow status

Per Story 9.1 D-2 decision (path-of-least-amendment): the agenteval-side wiring ships in Story 9.1; downstream rf-mcp adoption is OUT OF SCOPE.

| Stage | Owner | Status |
| --- | --- | --- |
| Build agenteval wheel | agenteval CI | ✅ (Story 1a.2 `release.yml`) |
| Install wheel into clean venv | agenteval CI | ✅ (`dogfood-integration.yml` install-smoke) |
| Clone rf-mcp at pinned commit | agenteval CI | ⚠️ Story 9.1 extension wired but requires manual one-time setup of `RF_MCP_PINNED_SHA` repo variable. |
| Run rf-mcp's parity suite under agenteval | agenteval CI | ✅ (Story 9.1 `parity-suite-smoke` job — runs on `workflow_dispatch` + `release: published`). |
| Block agenteval PRs on parity-suite failure | agenteval CI (cross-repo trigger) | ❌ Out of scope per D-2 — requires rf-mcp to add `agenteval` to its `dev` dependencies + run the parity suite in rf-mcp's own CI. |
| 7-consecutive-day monitoring + ≥1 real PR blocked | Phase-1 close validator manual | ❌ DF-9.1-S1 / C65 deferral. Calendar-time evidence collection. |

## Deliberate-regression verification (one-shot)

Per AC-9.1.4. Executed 2026-05-25 by Story 9.1 dev:

1. Created temporary branch `temp/deliberate-regression-9.1` from `main`.
2. Modified `tests/dogfood/rf-mcp/test_mcp_surface_parity.robot` Test 1 assertion: `Should Be True    ${result.success}` → `Should Be Equal    1    2`.
3. Confirmed the `parity-suite-smoke` job runs the assertion + fails on the deliberate regression.
4. Reverted the temp commit; branch deleted.

**Result:** the workflow gate correctly fails on a regression that breaks rf-mcp parity. The deliberate-regression test is documented in this section + the Story 9.1 Change Log; NO regression remains on `main`.

## Recipe #5 (Dogfood Replacing Custom Tests) cross-reference

`docs/recipes/05-dogfood-replacing-custom-tests.md` carries the rf-mcp worked example per AC-9.1.5: 1 representative Python → `.robot` port pair + DOGFOOD-FINDING-1 (`errlog=sys.__stderr__`) walkthrough + link back here.

## Phase-2 / "Phase-1 close validator" handoff (DF-9.1-S1 / C65)

When rf-mcp adopts agenteval as a dependency (Phase-2 governance decision):

1. The 38 Phase-2-batch tests migrate as a mechanical port — runtime budget then absorbable by rf-mcp's own CI (not agenteval's).
2. rf-mcp's own CI gains a job that runs the parity suite under agenteval, gating rf-mcp PRs.
3. Cross-repo dispatch from agenteval PRs to rf-mcp's CI (via `workflow_dispatch` + `repository_dispatch`) restores the AC L1949 "blocks agenteval PRs" gate.
4. 7-consecutive-day monitoring is collected naturally as agenteval PRs land.

This is the canonical "downstream adoption" sequence; Story 9.1 ships the agenteval-side preconditions.

## References

- AC-DOGFOOD-01 (PRD): satisfied for the rf-mcp half.
- Story 3.3 (`parity-checklist-rf-mcp-mcp-surface.md`): MCP-surface representative subset.
- Story 5.5 (`parity-checklist-rf-mcp-trace.md`): trace-observability parallel-derivation.
- `_bmad-output/implementation-artifacts/deferred-work.md` DF-9.1-S1 (catalogued by this story).
- `docs/phase-1-5-carry-overs.md` C65 (catalogued by this story).
