# agent-run-metrics Specification

## Purpose
TBD - created by archiving change add-e2e-agent-metrics-and-cli-adapters. Update Purpose after archive.
## Requirements
### Requirement: GenericAdapter captures tool calls and cached tokens

`GenericAdapter._map_completion` SHALL parse `response.choices[0].message.tool_calls` into `ToolCallTrace` records and SHALL populate `Usage.cached_input_tokens` from the completion response, replacing the hard-coded `tool_calls=[]`. The adapter SHALL record on `AgentRunMetadata` whether the run's cost and token numbers are *native* (reported by the provider) or *derived* (computed via `litellm.completion_cost`). The captured calls represent the model's *requested* tool calls (a one-shot, non-loop adapter), which SHALL be documented as the honest limit of this adapter.

#### Scenario: A real-model run records its requested tool calls
- **WHEN** a completion response contains one or more `message.tool_calls`
- **THEN** `GenericAdapter` returns an `AgentRunResult` whose `tool_calls` list carries one `ToolCallTrace` per requested call (name and args from the response), rather than an empty list

#### Scenario: Cached input tokens are populated
- **WHEN** a completion response reports cached input tokens in its usage payload
- **THEN** the resulting `AgentRunResult.usage.cached_input_tokens` reflects that value rather than defaulting to `0`

#### Scenario: Cost/token provenance is recorded
- **WHEN** cost is taken natively from the provider versus computed via `litellm.completion_cost`
- **THEN** `AgentRunMetadata` records which source (native vs derived) supplied the cost/token numbers so downstream metrics never overstate provenance

### Requirement: ToolCallTrace carries per-tool token and cost attribution

`ToolCallTrace` SHALL gain `input_tokens`, `output_tokens`, and `cost_usd` fields to provide a home for per-tool numeric attribution. Adapters that can supply per-tool numbers SHALL populate them; adapters that cannot SHALL leave them at their defaults. These fields SHALL be sourced from the recorded trace, never from model self-report.

#### Scenario: An adapter attributes tokens to a single tool call
- **WHEN** an adapter can attribute token counts and cost to an individual tool call
- **THEN** the corresponding `ToolCallTrace` carries that call's `input_tokens`, `output_tokens`, and `cost_usd`

#### Scenario: Per-tool numbers are absent when unavailable
- **WHEN** an adapter cannot attribute per-tool tokens or cost
- **THEN** the `ToolCallTrace` per-tool numeric fields remain at their default (zero/unset) values and are not fabricated

### Requirement: Tier-1 reader keywords expose run metrics

A metrics surface SHALL provide deterministic Tier-1 reader keywords over an `AgentRunResult`: `Get Token Usage`, `Get Cost USD`, and `Get Latency Seconds`. Each SHALL be a thin reader over the existing `AgentRunResult` fields (`usage`, `cost_usd`, `latency_seconds`) and SHALL return ground-truth values from the recorded run.

#### Scenario: Read token usage
- **WHEN** a test calls `Get Token Usage` on a recorded `AgentRunResult`
- **THEN** it returns the run's token usage (input, output, cached) from `AgentRunResult.usage`

#### Scenario: Read cost and latency
- **WHEN** a test calls `Get Cost USD` or `Get Latency Seconds` on a recorded run
- **THEN** each returns the run's `cost_usd` / `latency_seconds` value unchanged from the recorded result

### Requirement: Get Tool Call Metrics reports per-task and per-tool rollups

`Get Tool Call Metrics` SHALL report a per-task rollup and a per-tool rollup over a recorded run's `tool_calls`. Each rollup SHALL include: call `count`, `passed` (calls where `error is None`), `failed` (calls where `error` is set), aggregated `tokens`, aggregated `cost`, and aggregated `latency`. All values SHALL be derived from the recorded `ToolCallTrace` records, never from model self-report.

#### Scenario: Per-task rollup
- **WHEN** a test calls `Get Tool Call Metrics` on a run with several tool calls
- **THEN** the per-task rollup reports total count, passed count (`error is None`), failed count, and summed tokens/cost/latency across all calls

#### Scenario: Per-tool rollup groups by tool name
- **WHEN** the run called the same tool name more than once
- **THEN** the per-tool rollup groups calls by tool name and reports that tool's count, passed, failed, tokens, cost, and latency

#### Scenario: Passed and failed derive from the error field
- **WHEN** a `ToolCallTrace` has `error is None` versus a non-None `error`
- **THEN** it is counted as `passed` in the former case and `failed` in the latter, with no reliance on any model-reported success flag

### Requirement: Budget-assertion keywords fail below a threshold

The metrics surface SHALL provide budget-assertion keywords `Tokens Used Should Be Below` and `Cost Should Be Below` that pass when the recorded run's total tokens / cost is strictly below a supplied threshold and fail with a clear message otherwise. The compared values SHALL come from the recorded `AgentRunResult`.

#### Scenario: Token budget passes under threshold
- **WHEN** a run's total tokens used is below the threshold passed to `Tokens Used Should Be Below`
- **THEN** the keyword passes

#### Scenario: Cost budget fails over threshold
- **WHEN** a run's `cost_usd` meets or exceeds the threshold passed to `Cost Should Be Below`
- **THEN** the keyword fails with a message naming the actual cost and the threshold

### Requirement: StatLibrary exposes the statistical estimators

A `StatLibrary` SHALL wrap `stats.py` and expose `Stat.Run N Times`, `Stat.Get Pass At K`, and `Stat.Wilson Interval` as keywords over the existing `run_n`, `pass_at_k`, and `wilson_interval` functions. This SHALL make the previously-phantom `Stat.Run N Times` example (referenced by `Skill.Get Activation Pass At K`) a real, runnable keyword.

#### Scenario: Run a stochastic keyword N times
- **WHEN** a test calls `Stat.Run N Times` with a keyword and a repeat count
- **THEN** it executes the keyword that many times and returns the per-run outcomes for downstream estimation

#### Scenario: Compute pass@k
- **WHEN** a test calls `Stat.Get Pass At K` over a set of run outcomes
- **THEN** it returns the pass@k estimate computed by `stats.pass_at_k`

#### Scenario: Compute a Wilson interval
- **WHEN** a test calls `Stat.Wilson Interval` over a success count and total
- **THEN** it returns the Wilson score confidence interval computed by `stats.wilson_interval`

### Requirement: Normalized run-metrics record with declarative expected-tool contract

The change SHALL define a normalized run-metrics record modeled on rf-mcp's `ScenarioResult` shape — carrying `tool_calls[]`, `total_tool_calls`, `tool_hit_rate`, `expected_met`/`expected_total`, `errors[]`, `execution_time`, `usage`, and `cost`. The record SHALL support a declarative expected-tool contract expressed as `ExpectedToolCall{tool, min_calls, max_calls, required_args}` entries, and SHALL compute a `tool_hit_rate` measuring how many expected-tool contract entries were satisfied by the recorded trace. Every adapter (LiteLLM or CLI) SHALL normalize into this one record from ground-truth trace data.

#### Scenario: Expected-tool contract is satisfied
- **WHEN** a run's recorded trace calls a tool between its `min_calls` and `max_calls` with the `required_args` present
- **THEN** that `ExpectedToolCall` entry counts as met, and `tool_hit_rate` reflects the met/total ratio

#### Scenario: Expected-tool contract is unmet
- **WHEN** a run never calls an expected tool, calls it outside the `min_calls`/`max_calls` bounds, or omits a `required_args` key
- **THEN** that entry counts as unmet and `tool_hit_rate` decreases accordingly

#### Scenario: Every adapter normalizes into one record
- **WHEN** a run is produced by the in-process LiteLLM adapter or by a CLI subprocess adapter
- **THEN** both emit the same normalized run-metrics record shape so numbers are directly comparable

### Requirement: Export the run-metrics record to JSON

The metrics surface SHALL provide a keyword to write the normalized run-metrics record to a JSON file for real-world-number collection. The exported JSON SHALL contain only ground-truth values from the recorded run and SHALL preserve the record's fields (tool calls, totals, hit-rate, expected met/total, errors, execution time, usage, cost).

#### Scenario: Write metrics to a JSON file
- **WHEN** a test calls the JSON export keyword with a destination path after a recorded run
- **THEN** a JSON file is written containing the normalized run-metrics record's fields for that run

#### Scenario: Exported numbers are ground-truth only
- **WHEN** the record is exported
- **THEN** every metric value in the JSON originates from the recorded trace / `AgentRunResult`, and no model self-reported metric is written

### Requirement: Usage carries prompt-cache-creation tokens with a TTL split

`Usage` SHALL carry prompt-cache **creation** (write) token counts in addition to the
existing cache **read** count (`cached_input_tokens`): a flat total
`cache_creation_input_tokens`, and the two ephemeral-TTL buckets
`cache_creation_1h_input_tokens` and `cache_creation_5m_input_tokens`. All three SHALL
default to `0`, so existing `Usage` construction is unaffected, and SHALL be validated
as non-negative. The `claude-code` adapter (and other Anthropic-shaped CLI payloads that
report a cache-creation breakdown) SHALL populate them from ground-truth CLI output;
adapters that do not report an Anthropic-shaped cache-creation count SHALL leave them at
`0`, which means "not reported," not "no cache writes" (this SHALL be documented on the
fields). When all three creation counts are reported non-zero, the total SHALL equal the
sum of the 1h and 5m buckets (`cache_creation_input_tokens == cache_creation_1h_input_tokens
+ cache_creation_5m_input_tokens`), matching Anthropic's accounting; when the split is
absent the flat total stands alone and the identity check is skipped. The Tier-1
token-usage reader and the JSON metrics export SHALL surface these fields (each in its
existing key convention) so cache-write spend can be attributed and priced (the 1h and
5m buckets price at different multipliers, which is why the split is preserved). No model
self-reported number SHALL be used; the counts come from the recorded run.

#### Scenario: Cache-creation tokens are populated from the claude-code payload

- **WHEN** the claude-code adapter runs against a CLI whose settled usage reports
  `cache_creation_input_tokens` (and, when present, a `cache_creation` TTL breakdown)
- **THEN** the resulting `AgentRunResult.usage` carries that flat creation count and the
  1h/5m split, rather than dropping them

#### Scenario: Adapters without an Anthropic-shaped count default to zero

- **WHEN** a run comes from an adapter whose output carries no Anthropic-shaped
  cache-creation breakdown
- **THEN** the three cache-creation fields on `Usage` are `0`, not fabricated

#### Scenario: The reported split matches the total

- **WHEN** a payload reports the flat total and both the 1h and 5m buckets as non-zero
- **THEN** the total equals the sum of the 1h and 5m buckets, and a mismatch fails
  validation rather than being silently accepted

#### Scenario: The token-usage reader and export surface cache-creation

- **WHEN** a test calls `Get Token Usage` on a recorded run, or exports the run-metrics
  record to JSON
- **THEN** the returned usage / exported JSON includes the cache-creation total and the
  1h/5m split alongside the input, output, and cached (read) counts

#### Scenario: Cache-creation counts are non-negative

- **WHEN** a `Usage` is constructed with any negative cache-creation value
- **THEN** construction fails validation, consistent with the other token fields

