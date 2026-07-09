# Spec: budget-assertions

Tier-1 threshold assertion keywords over provider-reported cost, latency, and
token-usage scalars on `AgentRunResult`, wrapping the existing FR22 metric
computations (PRD 10-keyword-core debt closure).

## ADDED Requirements

### Requirement: Cost Should Be Below keyword

The library SHALL provide a Tier-1 keyword `Cost Should Be Below` on
`AssertionsLibrary` (composed into the top-level `AgentEval` library) that
accepts a single `AgentRunResult` or `list[AgentRunResult]` plus a USD
threshold, computes total provider-reported cost using the same computation as
`Get Cost Total` (single run: `cost_usd`; list: sum across trials), and SHALL
pass if and only if the observed total is strictly less than the threshold.
Dispatch SHALL route through `_assertions/adapter.assert_value()` with the
AssertionEngine `<` operator per ADR-019.

#### Scenario: Cost under budget passes

- **WHEN** `Cost Should Be Below` is called with a run whose `cost_usd` is `0.05` and threshold `0.10`
- **THEN** the keyword returns without raising

#### Scenario: Cost at or over budget fails with actual vs threshold

- **WHEN** `Cost Should Be Below` is called with runs totalling `0.153` USD and threshold `0.10`
- **THEN** the keyword raises an assertion failure whose message contains the observed value (`0.153`), the threshold (`0.1`), and the unit (`USD`)

#### Scenario: Observed equal to threshold fails (strict less-than)

- **WHEN** `Cost Should Be Below` is called with a run whose `cost_usd` exactly equals the threshold
- **THEN** the keyword raises an assertion failure

#### Scenario: Multi-trial aggregation sums cost

- **WHEN** `Cost Should Be Below` is called with a list of 3 runs costing `0.04` each and threshold `0.10`
- **THEN** the keyword fails because the aggregated total `0.12` is not below `0.10`

### Requirement: Latency Should Be Below keyword

The library SHALL provide a Tier-1 keyword `Latency Should Be Below` on
`AssertionsLibrary` that accepts a single `AgentRunResult` or
`list[AgentRunResult]` plus a millisecond threshold, computes mean turn-level
latency using the same computation as `Get Latency` (per-tool-call mean;
fallback `latency_seconds * 1000.0` when a run has no tool calls; multi-trial:
union-then-mean), and SHALL pass if and only if the observed mean is strictly
less than the threshold. Dispatch SHALL route through `assert_value()` with
the `<` operator.

#### Scenario: Mean latency under threshold passes

- **WHEN** `Latency Should Be Below` is called with a run whose mean tool-call latency is `800` ms and threshold `2000`
- **THEN** the keyword returns without raising

#### Scenario: Mean latency over threshold fails with actual vs threshold

- **WHEN** `Latency Should Be Below` is called with a run whose mean latency is `2500` ms and threshold `2000`
- **THEN** the keyword raises an assertion failure whose message contains the observed value, the threshold, and the unit (`ms`)

#### Scenario: Run without tool calls uses run-level latency fallback

- **WHEN** `Latency Should Be Below` is called with a run having zero `tool_calls` and `latency_seconds=1.5`, threshold `2000`
- **THEN** the keyword evaluates `1500.0` ms against the threshold and passes

### Requirement: Latency P95 Should Be Below keyword

The library SHALL provide a Tier-1 keyword `Latency P95 Should Be Below` on
`AssertionsLibrary` that accepts a single `AgentRunResult` or
`list[AgentRunResult]` plus a millisecond threshold, computes P95 latency
using the same computation as `Get Latency P95` (AC-6.1.8 boundary rules:
0 tool calls → `0.0`; 1 tool call → that latency; ≥2 →
`statistics.quantiles(n=100)[94]`; multi-trial: P95 over the union of all
tool-call latencies), and SHALL pass if and only if the observed P95 is
strictly less than the threshold.

#### Scenario: P95 under threshold passes

- **WHEN** `Latency P95 Should Be Below` is called with a list of runs whose union-P95 latency is `1900` ms and threshold `2000`
- **THEN** the keyword returns without raising

#### Scenario: P95 over threshold fails with actual vs threshold

- **WHEN** `Latency P95 Should Be Below` is called with runs whose union-P95 latency is `3100` ms and threshold `2000`
- **THEN** the keyword raises an assertion failure whose message contains the observed P95, the threshold, and the unit (`ms`)

### Requirement: Token Usage Should Be Below keyword

The library SHALL provide a Tier-1 keyword `Token Usage Should Be Below` on
`AssertionsLibrary` that accepts a single `AgentRunResult` or
`list[AgentRunResult]` plus an integer token threshold, computes total tokens
as `usage.input_tokens + usage.output_tokens` (using the same per-field
summing as `Get Token Usage` for multi-trial input; `cached_input_tokens` and
`reasoning_output_tokens` sub-fields SHALL NOT be added separately — that
would double-count), and SHALL pass if and only if the observed total is
strictly less than the threshold. The docstring SHALL state the
`input + output` formula.

#### Scenario: Token total under threshold passes

- **WHEN** `Token Usage Should Be Below` is called with a run reporting `Usage(input_tokens=400, output_tokens=100, ...)` and threshold `1000`
- **THEN** the keyword returns without raising

#### Scenario: Token total over threshold fails with actual vs threshold

- **WHEN** `Token Usage Should Be Below` is called with runs totalling `1200` tokens (input + output) and threshold `1000`
- **THEN** the keyword raises an assertion failure whose message contains the observed total, the threshold, and the unit (`tokens`)

#### Scenario: Cached tokens are not double-counted

- **WHEN** `Token Usage Should Be Below` is called with a run reporting `input_tokens=500` of which `cached_input_tokens=300`, `output_tokens=100`, and threshold `700`
- **THEN** the observed total is `600` (not `900`) and the keyword passes

### Requirement: Shared input validation and conventions

All four budget assertion keywords SHALL: (a) raise `ValueError` when the
`result` argument is an empty list (fake-green guard — deliberate divergence
from the getters' AC-6.1.8 vacuous-truth convention, documented in each
docstring); (b) raise `ValueError` when the threshold is not finite or is
`<= 0`, with the caller-typo gate firing before assertion dispatch; (c) carry
the `@tier(1)` decorator and `[Tier 1 — Deterministic]` docstring badge and
satisfy the auto-walking conventions suites (Browser-style docstring tables,
keyword-name idiom, dryrun-clean docstring examples); (d) NOT gate on
`mcp_coverage` (provider-reported scalars, FR22/AC-6.1.1 parity); and (e) emit
a pass-side evidence log line containing observed value, threshold, unit, and
aggregated-run count per AC-SIMPLICITY-01.

#### Scenario: Empty list input raises ValueError

- **WHEN** any budget assertion keyword is called with `result=[]` and a valid threshold
- **THEN** the keyword raises `ValueError` (not a passing assertion and not `AssertionError`)

#### Scenario: Non-positive threshold raises ValueError

- **WHEN** any budget assertion keyword is called with a threshold of `0`, a negative value, or `NaN`
- **THEN** the keyword raises `ValueError` identifying the invalid threshold before any assertion dispatch occurs

#### Scenario: external_mixed coverage does not block budget assertions

- **WHEN** `Cost Should Be Below` is called with a run whose `mcp_coverage` is `"external_mixed"` and `allow_external_mcp_blind=False`
- **THEN** the keyword evaluates normally without raising `IncompleteTraceError`

#### Scenario: Passing assertion logs evidence

- **WHEN** any budget assertion keyword passes
- **THEN** an info-level log line is emitted containing the observed value, the threshold, the unit, and the number of runs aggregated

### Requirement: Documentation surface

The README "Keywords at a glance" `AgentEval` library table SHALL gain one row
per new keyword (with Tier column `1`), the affected keyword counts in that
section SHALL be incremented by 4, and the `docs/keywords/AgentEval.html`
libdoc SHALL be regenerated so all four keywords render with their Tier-1
badges and docstring tables.

#### Scenario: README table lists the four keywords

- **WHEN** a reader opens the README `AgentEval` library keyword table after the change
- **THEN** rows for `Cost Should Be Below`, `Latency Should Be Below`, `Latency P95 Should Be Below`, and `Token Usage Should Be Below` are present with Tier `1` and the section's keyword counts reflect the 4 additions

#### Scenario: Libdoc renders the new keywords

- **WHEN** `docs/keywords/AgentEval.html` is regenerated via the documented libdoc command
- **THEN** all four keywords appear with `[Tier 1 — Deterministic]` badges and argument tables
