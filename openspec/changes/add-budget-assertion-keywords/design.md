# Design: add-budget-assertion-keywords

## Context

- The Tier-1 getters already exist and are stable: `Get Cost Total`, `Get Latency`, `Get Latency P95`, `Get Token Usage` (`src/AgentEval/metrics/library.py`, PRD FR22). Each accepts `AgentRunResult | list[AgentRunResult]` and delegates to pure helpers in `AgentEval/metrics/_internal.py` (`_compute_cost_total` / `_aggregate_cost_total`, `_compute_latency_mean` / `_aggregate_latency_mean`, `_compute_latency_p95` / `_aggregate_latency_p95`, `_compute_token_usage` / `_aggregate_token_usage`).
- ADR-019 ratified `robotframework-assertion-engine>=4.0,<5.0` and `_assertions/adapter.assert_value()` as "the canonical assertion dispatcher — future `Should *` keywords route through `adapter.assert_value()` instead of raising `AssertionError` directly from stdlib matchers." The 5 existing assertion keywords predate this and their retrofit is deferred (DF-6.3-S1/S2, C49+C50) — new keywords must NOT repeat that debt.
- Cost / latency / token metrics are provider-reported scalars — observer-independent, NOT `mcp_coverage`-gated (FR22 + AC-6.1.1 precedent in `MetricsLibrary`).
- Conventions suites in `tests/unit/conventions/` auto-walk `@keyword` methods: `@tier(n)` decorator + `[Tier 1 — Deterministic]` docstring badge, Browser-Library-style docstring tables, keyword-name idiom, docstring RF examples must pass `robot --dryrun`.
- PRD AC-SIMPLICITY-01: assertion keywords should leave a legible evidence trail (threshold, observed value) readable off the RF log within 30 seconds.

## Goals / Non-Goals

**Goals:**

- Ship the 4 budget assertion keywords with the same `result` argument convention as the metric getters, byte-identical aggregation semantics to the getters they wrap, and failure messages showing actual vs threshold with units.
- Route dispatch through `assert_value()` per ADR-019 so the new surface starts on the canonical path.
- Close the PRD 10-keyword-core debt for `Cost Should Be Below` / `Latency Should Be Below`.

**Non-Goals:**

- Run-over-run regression tracking (`Metrics Should Not Regress` style) — sibling change `add-regression-baseline-tracking`.
- Fan-out budget *enforcement* — `max_cost_usd` pre-flight/mid-run hard-stop already exists (ADR-015 `@guarded_fanout`). These keywords are post-hoc assertions over completed runs, not spend circuit-breakers.
- Retrofitting the 5 existing `AssertionsLibrary` keywords onto `assert_value()` (C49+C50 stay deferred).
- New operators (`Should Be Above`, ranges, percent-tolerance) — YAGNI until user demand; the getters + `Should Be True` remain available for exotic comparisons.
- Fixing the pre-existing README/docs keyword-count drift (dossier E3) beyond the increments these 4 keywords cause — that is a separate doc-drift change.

## Decisions

### D1 — Home: `AssertionsLibrary`, not `MetricsLibrary`

The keywords are assertions, so they live with the assertion surface (`src/AgentEval/_assertions/library.py`), sibling to `Trajectory Should Match` etc. Both libraries are composed into the top-level `AgentEval` library via `_SUB_LIBRARIES`, so the user-visible surface (bare, unprefixed names — matching the PRD 10-keyword-core spelling) is identical either way; `AssertionsLibrary` is the semantically correct home and keeps `MetricsLibrary` a pure getter surface.

*Alternative considered:* `MetricsLibrary` (next to the getters they wrap). Rejected — mixes assert/get responsibilities and would strand the keywords away from future `assert_value()`-based siblings.

### D2 — Reuse `metrics/_internal` helpers for all computation

Each keyword computes its observed value by calling the same `AgentEval.metrics._internal` helper pair its getter uses (single vs list dispatch identical to the getter). Zero duplicated math means the assertion can never drift from the getter — `Cost Should Be Below` fails exactly when `Get Cost Total` + manual comparison would.

*Alternative considered:* the keyword calls the public getter method cross-library. Rejected — `AssertionsLibrary` holds no `MetricsLibrary` reference and constructing one couples library lifecycles; `_internal` helpers are pure functions and already the shared substrate.

### D3 — Dispatch through `assert_value()` with the `<` operator (strict less-than)

"Below" means strictly below: observed `< threshold` passes, observed `== threshold` fails (an at-budget run has spent the budget). Dispatch goes through `_assertions/adapter.assert_value(actual, "<", threshold, keyword_name=..., tier=1, message=...)` per ADR-019 — this yields the AssertionEngine-standard failure format RF users recognize, and the polling/validate gates for free (no-ops at Tier 1, but the keywords are then already on the canonical path).

The `message` argument carries a keyword-built prefix with unit + run count (e.g. `Cost (USD, 3 runs aggregated)`), so the AssertionEngine failure reads actual-vs-threshold with units, e.g.:

```
Cost (USD, 3 runs aggregated) '0.153' (float) should be lower than '0.1' (float)
```

The exact prefix-vs-override behavior of `assertionengine.verify_assertion(message=...)` under the pinned 4.x must be verified empirically at implementation time (task 1.1); the spec requirement is on message *content* (observed value + threshold + unit), not exact wording.

*Alternative considered:* direct `if actual >= threshold: raise AssertionError(...)` like the 5 existing keywords. Rejected — ADR-019 explicitly directs future `Should *` keywords through `assert_value()`; hand-rolling would mint new instances of deferred debt C49/C50.

### D4 — Token total = `input_tokens + output_tokens`

`Token Usage Should Be Below` compares against `usage.input_tokens + usage.output_tokens`. `cached_input_tokens` and `reasoning_output_tokens` are accounting sub-fields of the `Usage` dataclass (cached input is a subset view of input; providers that bill reasoning report it inside `output_tokens` per the Story 1b.2 summing convention) — adding them would double-count. The docstring states the formula explicitly. Multi-trial input sums per field first (via `_aggregate_token_usage`), then totals.

### D5 — No `mcp_coverage` gate; no `redact()` on failure messages

Parity with the getters being wrapped: cost/latency/token scalars are provider-reported and observer-independent (FR22 + AC-6.1.1), so no `_check_mcp_coverage` call. Failure messages contain only numeric values, units, and run counts — no agent artifacts — so the FR38a `redact()` scrub is not required (unlike the trajectory/response assertions, which echo tool args and response text).

### D6 — Fake-green guards: empty list and bad thresholds raise `ValueError`

- **Empty `list` input → `ValueError`.** The getters' vacuous-truth convention (AC-6.1.8: empty → `0.0`) is correct for getters but hazardous for assertions: `Cost Should Be Below ${empty_list} 0.10` passing silently is the exact fake-green class this project's dogfood precheck exists to catch. Deliberate, documented divergence from getter semantics.
- **Threshold must be finite and `> 0` → `ValueError` otherwise.** All four observed values are non-negative, so `< 0` can never pass and `<= 0` thresholds are always caller typos; NaN/inf thresholds are nonsense. Caller-typo gates fire before dispatch (same ordering principle as the Story 6.2 `mode`-validation fix).
- **Docstring note (not a guard):** Mock-provider runs report `cost_usd=0.0`, so `Cost Should Be Below` trivially passes on mock — the docstring must say so to keep AC-SIMPLICITY-01 legibility honest.

### D7 — Pass-side evidence line per AC-SIMPLICITY-01

On pass, each keyword emits one `robot.api.logger.info` line with the same evidence the failure message carries (`observed=…, threshold=…, unit=…, runs=…`). This satisfies AC-SIMPLICITY-01's "evidence block on both pass and fail" for the new surface without retrofitting the 5 existing keywords (out of scope, noted as pre-existing gap).

## Risks / Trade-offs

- [AssertionEngine message wording changes across 4.x patch releases] → Spec pins message *content* (observed + threshold + unit present), not exact string; unit tests assert on substrings (`"0.153"`, `"0.1"`, `"USD"`), not full-message equality.
- [`verify_assertion(message=...)` semantics differ from assumption (override vs prefix)] → Task 1.1 empirically probes the pinned version before the keyword bodies are written; if `message` overrides rather than prefixes, the keyword pre-formats the complete actual-vs-threshold message itself.
- [RF passes thresholds as strings in some call styles] → Type hints `float` / `int` let RF's argument conversion coerce; unit tests include string-typed threshold input through the RF-conversion path (dryrun example + direct-call test with pre-converted types).
- [Strict `<` surprises users expecting `<=`] → Docstrings state "strictly below; observed == threshold fails" in the first paragraph; the failure message's "should be lower than" wording matches.
- [Empty-list `ValueError` diverges from getter vacuous-truth convention] → Deliberate (D6); docstrings cross-reference the getter behavior so the asymmetry is documented, not discovered.

## Migration Plan

Pure addition — no existing keyword changes, no config, no data migration. Rollback = revert the commit. README count increments ride the same commit as the code so the CI-enforced conventions stay green.

## Open Questions

- None blocking. (AssertionEngine `message` prefix-vs-override behavior is an implementation-time probe, task 1.1, with both outcomes designed for in D3/Risks.)
