# Tool-Call Metrics Contract — MCPLibrary

> Superseded by the four-surface refocus (2026-07) where the surface moved. Tool-call
> metrics are no longer a standalone `Metric.*` library; they live on **MCPLibrary**
> as `MCP.Get *` keywords. The token/latency/cost getters and the `Stat.*` aggregation
> siblings were removed. What stands: the boundary rules, the multi-trial aggregation
> semantics, and the `IncompleteTraceError` coverage gate documented below.

## Purpose

Defines the stable contract for MCPLibrary's tool-call metric keywords — the guarantees callers of the `MCP.Get *` metric keywords may rely on for values, boundaries, aggregation, and incomplete-trace handling.

## Scope

Applies to the metric keywords enumerated in the Surface section below and their boundary, multi-trial aggregation, and `IncompleteTraceError` behavior. Does not cover MCPLibrary's server-lifecycle or schema keywords, and does not cover the LLM-judge or coding-agent surfaces.

## Contract

The keyword surface, the AC-6.1.8 boundary rules, the AC-6.1.1 multi-trial aggregation rules, and the `IncompleteTraceError` gate documented below are the stable contract. Metric values and their aggregation semantics do not change without a Change Policy bump.

## Change Policy

Changes to this contract follow the pre-1.0 stability rules in [`stability-surface.md`](./stability-surface.md); breaking changes to `stable` metric surfaces are constrained by the 3-month-no-break window.


**Phase-1 stability label:** provisional
**Library:** `MCPLibrary` (`src/MCPLibrary/library.py`)

## Surface (tool-call metrics)

| # | Keyword | Input | Return |
| --- | --- | --- | --- |
| 1 | `MCP.Get Tool Call Count` | `AgentRunResult \| list[AgentRunResult] \| list[ToolCallTrace]` | `int` |
| 2 | `MCP.Get Tool Call Names` | `AgentRunResult \| list[AgentRunResult] \| list[ToolCallTrace]` | `list[str]` |
| 3 | `MCP.Get Tool Hit Rate    expected_tools=<list>` | `AgentRunResult \| list[AgentRunResult]` + `list[str]` | `float` |
| 4 | `MCP.Get Tool Success Rate` | `AgentRunResult \| list[AgentRunResult]` | `float` |
| 5 | `MCP.Get Unnecessary Call Rate    expected_tools=<list>` | `AgentRunResult \| list[AgentRunResult]` + `list[str]` | `float` |
| 6 | `MCP.Was Tool Called    tool_name=<str>` | `AgentRunResult \| list[AgentRunResult]` + `str` | `bool` |

All tool-call metric keywords:
- Tier-1 deterministic (no LLM invocation; read from already-captured data).
- Single-run / multi-trial dispatch via `isinstance(result, list)`.

The old standalone token-usage, latency, and cost getters were removed in the refocus.

## Boundary contract

| Input | Keyword | Return |
| --- | --- | --- |
| Empty `list[]` | `MCP.Get Tool Call Count` | `0` |
| Empty `list[]` | `MCP.Get Tool Call Names` | `[]` |
| Single run with zero tool_calls | `MCP.Get Tool Success Rate` | `0.0` (vacuous-truth) |
| Single run with zero tool_calls | `MCP.Get Unnecessary Call Rate` | `0.0` (vacuous-truth) |
| `expected_tools=[]` | `MCP.Get Tool Hit Rate` | `0.0` (vacuous-truth convention; 0/0 → 0.0 not NaN) |

## Multi-trial aggregation rules

| Metric | Aggregation rule |
| --- | --- |
| Count | sum per trial |
| Names | union preserving order-of-first-appearance |
| Hit Rate | mean of per-trial hit rates |
| Success Rate | mean of per-trial success rates |
| Unnecessary Call Rate | mean of per-trial unnecessary-call rates |

## `IncompleteTraceError` gate

Tool-call-bearing keywords gate on `mcp_coverage`:

| `mcp_coverage` | `allow_external_mcp_blind` | Outcome |
| --- | --- | --- |
| `hosted_in_process` | any | proceed |
| `subprocess_with_observer` | any | proceed |
| `external_mixed` | `False` (default) | **raise `IncompleteTraceError`** |
| `external_mixed` | `True` (opt-in) | proceed (blind run; result trust degraded) |

For multi-trial input, the gate fires on the FIRST trial that violates the coverage contract (fail-fast).

## Data source

The metric keywords read from `AgentRunResult` fields directly:
- `result.tool_calls` — populated by the hosted-MCP observer or captured when driving a coding agent.
- `result.metadata.mcp_coverage` — populated per ADR-016's trust-floor.

## Stability + change log

- Tool-call metrics on MCPLibrary; token/latency/cost getters and the `Stat.*` aggregation siblings removed in the four-surface refocus (2026-07). Provisional stability.
