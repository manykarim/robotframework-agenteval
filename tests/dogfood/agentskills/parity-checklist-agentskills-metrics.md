# Parity Checklist: `robotframework-agentskills` Metrics + Assertions + Stats

**VALIDATION-CEILING (added 2026-05-25 per Epic 7 retro `feedback_dogfood_validation_ceiling` norm):** this dogfood VERIFIES that the Epic 6 keyword surface (`MetricsLibrary` + `AssertionsLibrary` + `StatsLibrary`) correctly drives parallel-derived `AgentRunResult` fixtures against vendored agentskills test scenarios — covers metric computation correctness + assertion gate behavior + statistical primitives; does NOT VERIFY live `robotframework-agentskills` upstream test execution (parallel-derived, not upstream-imported), nor cross-version compatibility against unreleased agentskills updates, nor real LLM-driven metric collection (deterministic-scoring scenarios; no LLM in the loop). Full agentskills adoption is `parity-checklist-agentskills-FULL.md` (Story 9.2) + Phase-2 work.


Story 6.4 — Interleaved Dogfood port. Tracks coverage of `robotframework-agentskills`'
scoring-test domain by `.robot` suites exercising agenteval's Epic 6 keyword surface
(Story 6.1 `MetricsLibrary` + Story 6.2 `AssertionsLibrary` + Story 6.3 `StatsLibrary`
+ top-level `Get Keyword Tier`).

**Source corpus:** `/home/many/workspace/robotframework-agentskills/tests/eval/*.py`
**Vendored test suites:** `tests/dogfood/agentskills/test_{metrics,assertions,stats}_parity.robot`
**Fixture helper:** `tests/dogfood/agentskills/fixtures/agentskills_sessions.py`

## Per Story 6.4 D-2 framing reframe (mirrors Story 5.5 D-3)

agentskills' `tests/eval/*.py` corpus contains DETERMINISTIC SCORING / VERDICT-
aggregation tests operating on captured agent session JSON — NOT "tool-call
metric tests" in the agenteval sense. Story 6.4 reframes the port as:

> "Dogfood agenteval's `MetricsLibrary` / `AssertionsLibrary` / `StatsLibrary`
> surface AGAINST agentskills' scoring-test domain semantics via `AgentRunResult`
> fixtures parallel-derived from agentskills' session shape."

This satisfies AC-DOGFOOD-01 (agentskills half) via semantic parity rather
than verbatim test port. Per Story 5.5 D-3 ratified precedent.

## CI wiring deferred per Phase-1 norm

`dogfood-integration.yml` stays smoke-only (Story 1a.2 HIGH-1 ratification).
Full cross-repo CI dispatch deferred to **Story 9.1+9.2** per architecture
L1718 + epic L1564. Story 6.4 ships the `.robot` suites locally + manually
runnable via `uv run robot tests/dogfood/agentskills/`.

## Coverage matrix

### Story 6.1 `MetricsLibrary` (9 keywords) — `test_metrics_parity.robot` (12 tests)

| agentskills semantic | agenteval keyword | dogfood test | Status |
| --- | --- | --- | --- |
| `SessionScorecard.tool_count` | `Get Tool Call Count` | "Get Tool Call Count returns 1 for single-tool session" + "returns 2 for unnecessary-tool" | ✓ |
| `SessionScorecard.tool_names` (chronological) | `Get Tool Call Names` | "Get Tool Call Names preserves chronological order" | ✓ |
| deterministic-scoring expected-tools match | `Get Tool Hit Rate` | "computes correctly when expected tools matched" + "computes partial when missing" | ✓ |
| tool-error rate from session shape | `Get Tool Success Rate` | "is 1.0 for happy-path session" + "is 0.0 for partial-completeness with timeout" | ✓ |
| unnecessary-call detection from expected-set | `Get Unnecessary Call Rate` | "is 0.5 when one of two calls is unnecessary" | ✓ |
| `SessionRecord.usage` (Usage shape) | `Get Token Usage` | "returns Usage dataclass" | ✓ |
| `SessionRecord.latencies[*]` mean | `Get Latency` | "returns mean tool-call latency ms" | ✓ |
| latency percentile (Phase-1 deferred in agentskills) | `Get Latency P95` | "equals max for single-tool runs" | ✓ |
| `SessionRecord.cost_usd` | `Get Cost Total` | "returns the AgentRunResult cost_usd" | ✓ |

### Story 6.2 `AssertionsLibrary` (5 keywords) — `test_assertions_parity.robot` (11 tests)

| agentskills semantic | agenteval keyword | dogfood test | Status |
| --- | --- | --- | --- |
| ordered trajectory equality | `Trajectory Should Match` (exact) | "exact mode passes for matching" + "fails for wrong-order" | ✓ |
| trajectory subsequence (extras allowed) | `Trajectory Should Match` (subsequence) | "subsequence mode allows extras between expected" | ✓ |
| trajectory set-equality | `Trajectory Should Match` (set) | "set mode is unordered" | ✓ |
| deterministic-verdict expected-tool-call rule | `Tool Call Should Have Occurred` | "matches name only" + "dict-subset partial args" + "raises on missing" | ✓ |
| `test_grader_robot_runner.py` response-text checks | `Agent Response Should Contain` + `Should Match Regex` | "matches substring" + "matches regex pattern" | ✓ |
| FR37 IncompleteTraceError gate (no agentskills analog) | gate behavior | "raises on external_mixed" × 2 (trajectory + tool-call paths) | ✓ |

### Story 6.3 `StatsLibrary` (4 keywords) + Tier ACL — `test_stats_parity.robot` (6 tests)

| agentskills semantic | agenteval keyword | dogfood test | Status |
| --- | --- | --- | --- |
| FR30a tier introspection (no agentskills analog) | `Get Keyword Tier` | "returns 1 for Get Tool Call Count" + "returns 1 for Tool Call Should Have Occurred" + "returns 3 for Stat.Run N Times" + "raises on unknown keyword" | ✓ |
| `test_cli_score_batch.py` Pass@k batch | `Stat.Get Pass At K` | "with explicit predicate computes correctly" | ✓ (with DOGFOOD-FINDING-1 workaround) |
| Wilson CI for batch scoring (gap in agentskills) | `Stat.Get Pass At K Confidence Interval` | "returns Wilson CI tuple" | ✓ |

### Story 6.3 keywords NOT exercised in Story 6.4 (deferred)

- `Stat.Run N Times` — Tier-3 fan-out requires a callable wrapped keyword that triggers
  the `@guarded_fanout` budget enforcement. Dogfood synthesizes `KeywordRun` trials
  directly from fixture `AgentRunResult`s (skipping the fan-out runner) per the
  D-4 fixture-driven scope. Live fan-out coverage lands when DF-5.5-DOGFOOD-1 (C43)
  ships the multi-turn agent loop in Phase-2.
- `Stat.Assert Run Determinism` — exercised by `tests/conformance/test_tier1_byte_identical_run.py`
  (Story 6.3 AC-6.3.4) rather than dogfood; the conformance fixture is the canonical
  FR31a verification surface.

## Deferred parity (out-of-scope for Story 6.4)

- **Multi-turn agent loop dogfood** — Phase-2 / DF-5.5-DOGFOOD-1 (C43). Dogfood
  cannot drive a live `Send Prompt` → tool_calls → reply loop until adapter span
  instrumentation lands (DF-5.5-DOGFOOD-2 / C44).
- **Cross-repo CI dispatch via `dogfood-integration.yml`** — Story 9.1+9.2 scope
  per architecture L1718. Story 6.4 ships local-runnable suites only.
- **FR34a `EvidenceBlock` emission visibility** — DF-6.2-S1 / C47 (Phase-1.5).
  Dogfood can't yet exercise the operator-facing evidence-block UX.
- **Paired-getter ergonomics (`Get Trajectory` / `Get Agent Response`)** —
  DF-6.2-S2 / C48 (Phase-1.5).
- **AssertionEngine matching-backend swap + 6-keyword Path A wrap** — DF-6.3-S1+S2 /
  C49+C50 (Phase-1.5).

## Dogfood findings (≥1 per AC-6.4.8)

### DOGFOOD-FINDING-1 / DF-6.4-S1 — Pass@k default predicate fake-green

**Severity:** HIGH (production bug uncovered by Story 6.4 dogfood)
**Surface:** Story 6.3 `src/AgentEval/stats/_internal.py:_default_pass_predicate`

`Stat.Get Pass At K`'s default predicate is `lambda r: r.completeness == "full"`
(per epic AC-2 wording at `epics.md:1646` + Story 6.3 implementation). But
`AgentRunMetadata.completeness` valid values per `src/AgentEval/types.py:323-324`
are `("complete", "truncated", "partial")` — `"full"` is NOT a valid value.

**Consequence:** Any caller of `Stat.Get Pass At K` who relies on the default
predicate (operator-facing PRD-verbatim form `Stat.Get Pass At K ${runs} k=${k}`
without an explicit `predicate=` argument) gets `0.0` REGARDLESS of how many
trials passed — because `r.completeness == "full"` is never True for an
`AgentRunResult`-derived `KeywordRun`. Silent fake-green.

**Story 6.4 workaround:** dogfood tests use an explicit predicate factory
`build_complete_predicate()` returning `lambda r: r.completeness == "complete"`
(the correct value). Tracked as **DF-6.4-S1** for Phase-1.5 amendment to
Story 6.3's `_default_pass_predicate()` + the epic AC-2 verbatim wording.

### DOGFOOD-FINDING-2 / DF-6.4-S2 — Metric.* namespace prefix documentation drift

**Severity:** LOW (documentation drift, not a runtime bug)
**Surface:** Story 6.1 `src/AgentEval/metrics/library.py` `@keyword(name=...)` registrations

PRD + architecture documents repeatedly refer to metric keywords as
`Metric.Get Tool Call Count`, `Metric.Get Tool Hit Rate`, etc. — but Story 6.1
ships them WITHOUT the `Metric.` namespace prefix in their `@keyword(name=...)`
registration (`Get Tool Call Count`, `Get Tool Hit Rate`, etc.). Only Story 6.3's
`Stat.*` keywords use a namespace prefix in the actual RF surface.

**Consequence:** Operators reading PRD/architecture docs expecting to call
`Metric.Get Tool Call Count` will hit `ValueError: keyword 'Metric.Get Tool Call Count'
not found in AgentEval library` from `Get Keyword Tier`. The dogfood test
"Get Keyword Tier returns 1 for Get Tool Call Count" empirically surfaces this.

**Resolution paths:**
- (a) Amend PRD + architecture docs to drop the `Metric.` prefix (operator-facing
  surface matches docs).
- (b) Amend Story 6.1 to add the `Metric.` prefix to all 9 keywords (operator surface
  matches docs).

Tracked as **DF-6.4-S2** for Phase-1.5 decision + execution.

## Story 6.4 execution notes

- **Fixture-driven scope (D-4):** `AgentRunResult` fixtures via `agentskills_sessions.py`
  helper; no live MCP+LLM driven multi-turn loop (deferred per DF-5.5-DOGFOOD-1 / C43).
- **Local repo path:** `/home/many/workspace/robotframework-agentskills` (sibling clone).
  `RF_AGENTSKILLS_REPO_ROOT` env-var override pattern mirrors Story 3.3's
  `RF_MCP_REPO_ROOT` but Story 6.4 doesn't currently require live agentskills
  invocation (fixtures are vendored). Reserved for Phase-2 dogfood expansion.
- **Tags:** `[Force Tags] slow dogfood epic-6` excludes the suites from the default
  pytest sweep — run via `uv run robot tests/dogfood/agentskills/`.
- **Fake-green precheck:** per `feedback_dogfood_fake_green_precheck` Story 5.5 retro
  ratified — each `.robot` test's assertion body delivers on the test name's promise.
  Verified pre-flip-to-review.

## Status

- **Phase-1 close:** dogfood suites pass locally (29/29 tests = 12 metrics + 11
  assertions + 6 stats). DF-6.4-S1 + DF-6.4-S2 catalogued for Phase-1.5.
- **Full AC-DOGFOOD-01 closure:** Story 9.1+9.2 (cross-repo CI dispatch).
