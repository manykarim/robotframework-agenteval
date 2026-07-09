# Proposal: add-budget-assertion-keywords

## Why

The PRD's original 10-keyword core (memorize-or-fail set, `_bmad-output/planning-artifacts/prd.md` MVP scope, ~L951) promised `Latency Should Be Below` and `Cost Should Be Below` as first-class assertion keywords — they never shipped. Only the Tier-1 getters exist today (`Get Cost Total`, `Get Latency`, `Get Latency P95`, `Get Token Usage` in `src/AgentEval/metrics/library.py`), forcing users into the two-step `${cost} = Get Cost Total` + `Should Be True ${cost} < 0.10` idiom with no unit-aware failure message. promptfoo treats cost and latency as first-class assert types, so this is both PRD-debt closure and market parity (exploration dossier E6, "SMALL PRD DEBT").

## What Changes

- Add 4 new Tier-1 assertion keywords to `AssertionsLibrary` (`src/AgentEval/_assertions/library.py`), composed into the top-level `AgentEval` library like the existing 5 assertion keywords:
  - `Cost Should Be Below` — total provider-reported cost strictly below a USD threshold.
  - `Latency Should Be Below` — mean turn-level latency strictly below a millisecond threshold.
  - `Latency P95 Should Be Below` — P95 latency strictly below a millisecond threshold.
  - `Token Usage Should Be Below` — total tokens (input + output) strictly below an integer threshold.
- Same `result` argument convention as the existing metric keywords: each accepts a single `AgentRunResult` OR `list[AgentRunResult]` (multi-trial aggregation), reusing the exact aggregation semantics of the corresponding getter (sum for cost/tokens, union-then-mean for latency, union-P95 for P95).
- Assertion dispatch routes through `_assertions/adapter.assert_value()` per ADR-019 ("future `Should *` keywords route through `adapter.assert_value()`"), using the AssertionEngine `<` operator.
- Clear failure messages showing actual vs threshold with unit and aggregated-run count.
- Fake-green guards: empty `list` input raises `ValueError` (a budget assertion that trivially passes on zero runs is a silent hazard); non-positive/non-finite thresholds raise `ValueError`.
- README "Keywords at a glance" table gains 4 rows (+ per-table count adjustments) and `docs/keywords/AgentEval.html` libdoc is regenerated.

No breaking changes. No new dependencies (`robotframework-assertion-engine>=4.0,<5.0` is already pinned per ADR-019).

## Capabilities

### New Capabilities

- `budget-assertions`: Tier-1 threshold assertion keywords over provider-reported cost, latency, and token-usage scalars carried on `AgentRunResult`, wrapping the existing FR22 metric computations.

### Modified Capabilities

_None._ (`openspec/specs/` has no existing capability specs; no existing keyword's behavior changes.)

## Impact

- **Code:** `src/AgentEval/_assertions/library.py` (4 new `@keyword` methods), possibly a small message-builder helper in `src/AgentEval/_assertions/_internal.py`. Computation reuses `AgentEval/metrics/_internal.py` compute/aggregate helpers — no duplicated math.
- **Tests:** `tests/unit/_assertions/test_assertions_library.py` (new test class/module section); auto-walking conventions suites (`tests/unit/conventions/`) pick up the new keywords for tier-badge, docstring-style, name-idiom, and docstring-example-dryrun enforcement.
- **Docs:** `README.md` keyword table + counts; regenerated `docs/keywords/AgentEval.html`.
- **Out of scope (explicit):** run-over-run regression tracking (sibling change `add-regression-baseline-tracking`); fan-out budget *enforcement* (already exists via `max_cost_usd` / `@guarded_fanout`, ADR-015); retrofitting the 5 existing assertion keywords onto `assert_value()` (deferred DF-6.3-S1/S2, carry-overs C49+C50).
