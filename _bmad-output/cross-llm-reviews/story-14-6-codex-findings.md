# Story 14.6 Codex Findings

## HIGH

1. `src/AgentEval/orchestration/library.py:239-241` — `Run Scenario` is still missing `@guarded_fanout()`, so C26 is not actually closed. `_HostBudgetPlumbing` only adds `_max_cost_usd` / `_max_runtime_seconds`; without the decorator, `run_scenario()` never reads those attrs and cannot enforce either budget. The false closure then propagates into `docs/contracts/stability-surface.md:141-144`, `docs/phase-1-5-carry-overs.md:49`, and `_bmad-output/implementation-artifacts/14-6-unified-host-instance-budget-plumbing-c20-c26-c89-c95-close.md:361`. Concrete fix: import `guarded_fanout` into `orchestration/library.py`, add `@guarded_fanout()` between `@tier(3)` and `def run_scenario(...)`, then regenerate the affected docs/catalog rows so C26 only reads closed once the decorator is actually present.

2. `src/AgentEval/mcp/library.py:460-471`, `src/AgentEval/mcp/library.py:601-636`, `src/AgentEval/skills/library.py:560-594`, `src/AgentEval/discoverability/_internal.py:81-83`, and `docs/contracts/stability-surface.md:167` still carry pre-closure “tracked, NOT enforced” / “enforcement DEFERRED” language, or stale DF-13.3-S1 / DF-13.5-S1 carry-over notes, after Story 14.6 claims those rows are closed. This fails D-5 directly and leaves the public contract internally contradictory: some lines say Story 14.6 enforces budgets, others still say it does not. Concrete fix: remove the stale DF-4.4-S1 / DF-13.3-S1 / DF-13.5-S1 non-enforcement text everywhere it remains and replace it with one consistent statement: the mechanism is now wired, while live estimator-driven pre-flight evidence remains deferred only under `DF-14.6-S1`.

## MED

1. `tests/unit/kernel/test_host_budget_plumbing.py:162-171` is false-green for C26. The docstring says `Run Scenario` closes the `@guarded_fanout` contract, but the test only checks that the host attrs exist and that `run_scenario` is present; it passes whether the decorator exists or not, which is exactly how the missing `@guarded_fanout()` escaped. Concrete fix: add a regression that asserts the real method is wrapped (for example `hasattr(OrchestrationLibrary.run_scenario, "__wrapped__")`) and, after adding the decorator, exercise observable wrapper behavior on the live method instead of only checking attribute presence.

2. `_bmad-output/implementation-artifacts/14-6-unified-host-instance-budget-plumbing-c20-c26-c89-c95-close.md:179` still points AC-14.6.8 at `tests/unit/_kernel/test_host_budget_plumbing.py`, but the shipped file is `tests/unit/kernel/test_host_budget_plumbing.py`. Concrete fix: correct the path in the story artifact so the acceptance criterion matches the actual test location.

## LOW

1. `docs/phase-1-5-carry-overs.md:4` still says `Last updated: 2026-05-25` even though C20/C26/C89/C95 were edited on 2026-06-04. Concrete fix: bump the header date when updating the catalog so the document metadata stays trustworthy.
