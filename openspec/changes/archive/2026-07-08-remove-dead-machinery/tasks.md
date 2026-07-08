# Tasks: remove-dead-machinery

Ordered per design.md Migration Plan: ripple-free deletions first, then resolver merge, then errors.py, then guardrails. Each numbered group ends green (`uv run pytest tests/`, `uv run ruff check src/ tests/`, `uv run mypy src/`).

## 1. Ripple-free deletions (security/, reporting/, Wilson dedup)

- [x] 1.1 Pre-deletion dynamic-importer sweep: grep `src/`, `tests/`, `pyproject.toml`, `.github/` for string references to `AgentEval.security`, `AgentEval.reporting`, `wilson_ci` (including quoted module paths); record hits and confirm all are docs/comments only
- [x] 1.2 Delete `src/AgentEval/reporting/` (single docstring-only `__init__.py`)
- [x] 1.3 Delete `src/AgentEval/security/` (4 files); keep the empty `agenteval.sandboxes` entry-point group in `pyproject.toml` and `_kernel/discovery.discover_sandboxes()` untouched
- [x] 1.4 Remove the `"SANDBOX_REQUIRED": 77` planned row from `cli._ERROR_EXIT_CODES` and fix the stale docstring comment at `tests/unit/test_cli.py:109`; update any exit-code-table mirror test
- [x] 1.5 Update `docs/contracts/stability-surface.md` (replace the Sandbox Protocol Surface subsection with a "withdrawn pre-1.0; re-ratified when Phase-3 sandbox lands" note) and add a status annotation to `docs/adr/ADR-018-sandbox-phase-1-policy.md`
- [x] 1.6 Repoint `src/AgentEval/discoverability/_internal.py:41` to `from AgentEval.stats.wilson import wilson_score_interval`; delete `src/AgentEval/discoverability/wilson_ci.py`
- [x] 1.7 Fold `tests/unit/discoverability/test_wilson_ci.py` into `tests/unit/stats/test_wilson.py`: diff both files, move any assertion not already covered, add one test pinning `wilson_ci_lower`/`wilson_ci_upper` through the discoverability call path against pre-dedup values, then delete the old file
- [x] 1.8 Gate: full suite + ruff + mypy green; `python -c "import AgentEval.security"` and `...reporting` and `...discoverability.wilson_ci` all raise `ModuleNotFoundError`

## 2. Config resolver merge + keyword consolidation

- [x] 2.1 Rewrite `resolve_config` in `src/AgentEval/_kernel/context.py` as a value projection over `resolve_config_with_provenance` (delete the duplicated precedence/coercion/dotenv logic; one chain remains)
- [x] 2.2 Update `AgentEval.__init__` (`src/AgentEval/__init__.py:248-269`) to call `resolve_config_with_provenance` exactly once, store the map, and derive bare values from it; add/adjust a unit test asserting unknown-`AGENTEVAL_*`-key warnings are emitted once per key per source on instantiation
- [x] 2.3 Replace the hand-maintained 10-key literal dict in `get_effective_config` with a derivation from the stored provenance map (no behavior change to the no-arg return shape)
- [x] 2.4 Delete the `Get Effective Config With Provenance` keyword and its tests; update `Get Effective Config`'s docstring sibling-reference and the DF-4.3-S1 carry-over notes in both keyword docstrings
- [x] 2.5 Close the resolver-merge carry-over: mark catalog entry **C27** (DF-4.3-S7 `resolve_config_with_provenance` refactor) resolved in `docs/phase-1-5-carry-overs.md` (and `deferred-work.md` if listed), and retire the DF-4.3-S1 in-code TODO in `src/AgentEval/__init__.py` (lines ~446/564), both with the design.md D3 rationale: single precedence chain, no-arg ConfigValue migration REJECTED, twin keyword deleted
- [x] 2.6 Libdoc-render smoke: regenerate/inspect libdoc for the composed library — `Get Effective Config` present, `Get Effective Config With Provenance` absent, no auto-split artifacts
- [x] 2.7 Gate: full suite + ruff + mypy green; `tests/unit/kernel/test_context.py` precedence tests all pass through the merged chain

## 3. errors.py consolidation + contract sync

- [x] 3.1 Fold `DuplicateRegistrationError` into `AdapterDiscoveryError`: rewrite the single raise site in `src/AgentEval/_kernel/discovery.py` to raise `AdapterDiscoveryError` with the colliding entry-point name + both sources in the message (preserve fix-suggestion content); delete the class; update tests that referenced the leaf
- [x] 3.2 Trim internal story/review narration from `errors.py` docstrings (mechanical rule per design.md D4: keep all behavioral contract text, message-format descriptions, attrs, exit codes; cut only story-numerology citations); verify File/Line/Field/Fix blocks byte-unchanged via diff review
- [x] 3.3 Sync `docs/contracts/error-class-hierarchy.md`: leaf count 24 → 22 (drop planned-only `SandboxRequiredError`, fold `DuplicateRegistrationError`), family rows updated, ADR-014 amendment note added in the same commit
- [x] 3.4 Gate: full suite green; exit-code mirror test confirms `cli._ERROR_EXIT_CODES` keys map 1:1 to classes existing in `errors.py` (plus the documented warning-class row)

## 4. @guarded_fanout no-budget fast path

- [x] 4.1 Implement the fast path in `src/AgentEval/_kernel/guardrails.py`: after popping `_TEST_BUDGET_KWARG` and resolving instance budgets, if both `max_cost_usd` and `max_runtime_seconds` are `None`, call the body directly (no meter thread, no `_BreachState`, no cancel-event binding, no Layer-1 comparisons); budgeted path byte-for-byte unchanged
- [x] 4.2 Add unit tests: (a) no thread named `agenteval-guarded-fanout-meter` is created on a no-budget call and the return value passes through; (b) `current_cancel_event()` returns `None` inside a no-budget body; (c) exceptions propagate unchanged on the fast path; (d) a budgeted call still spawns/joins the meter thread; (e) the test-only budget-override kwarg still routes to the metering path
- [x] 4.3 Confirm existing budgeted-path tests (runtime breach, cost breach, fail-closed cost-source, estimator pre-flight) pass unmodified — any test that assumed a meter thread on unbudgeted calls is updated to the new contract
- [x] 4.4 Gate: full suite + ruff + mypy green

## 5. Close-out

- [x] 5.1 Carry-over catalog gate (UPSTREAM per project norm): grep all touched files for `DF-X-SY` patterns; verify every referenced carry-over is present/updated in `docs/phase-1-5-carry-overs.md`
- [x] 5.2 Verify final test-count accounting vs the 1605+10 baseline: every delta is attributable to deleted-code tests removed or new tests added (list them); no unexplained losses
- [x] 5.3 Run `openspec status --change "remove-dead-machinery"` and mark the change ready for archive once all groups are green
