# MCP Coverage Detection

**Status:** accepted.
**Related ADRs:** ADR-016 (MCP Coverage Detection Default — trust-floor), ADR-004 (Hosted-MCP Universal Trace Observation)

> Superseded by the four-surface refocus (2026-07) where the details drifted. The
> trust-floor rule and the `IncompleteTraceError` gate are still exactly how
> MCPLibrary reports and enforces coverage. Gone: the per-vendor detection split
> across Claude Code / Copilot / Codex / LiteLLM adapters, and the conformance-suite
> fixtures. Coverage detection now belongs to MCPLibrary and the single coding-agent
> driver, and lives in `src/MCPLibrary/_coverage.py`.

## Purpose

Governs how agenteval decides `mcp_coverage` — the 3-valued field `hosted_in_process` / `subprocess_with_observer` / `external_mixed` per ADR-016's trust-floor. agenteval's hosted-MCP observer is structurally blind to MCP servers it didn't spawn; whoever configured those external servers is the only party that can detect them and signal degradation. This contract documents the trust-floor decision tree and how detection-failure defaults work.

## Scope

### In-scope

- The 3-valued `mcp_coverage` literal set + per-value semantics (per ADR-016).
- D1 trust-floor: when BOTH `hosted_in_process` AND `subprocess_with_observer` paths fire successfully, report the STRONGER path.
- Whose job detection is: whoever configured external MCP servers must signal them via `mark_external_mixed(reason)`.
- Detection-failure default: `external_mixed` (safer than `hosted_in_process`).
- `IncompleteTraceError` gate behavior: when metric keywords MUST raise vs. when the consumer opted out via `allow_external_mcp_blind=True`.

### Out-of-scope

- The hosted-MCP observer's internal implementation — that's ADR-004's content.

## Contract

### 3-valued literal set

`AgentRunResult.metadata.mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` per ADR-016's trust-floor.

| Value | Semantics |
| --- | --- |
| `hosted_in_process` | Agenteval-hosted in-memory FastMCP/Server with the observer attached. All `tools/call` traffic was observed server-side. Strongest trust path. |
| `subprocess_with_observer` | Agenteval-hosted stdio subprocess MCP server with the observer injected at subprocess bootstrap (ADR-004 §Consequences). Traces serialized as JSONL by the subprocess + grafted by the parent. |
| `external_mixed` | Either (a) the caller signaled that external MCP configs are present, OR (b) the observer is structurally blind to the run (no agenteval-hosted servers attached). agenteval refuses to claim trace truth. |

### Trust-floor decision tree

`compute_coverage()` resolves per the following rules (in priority order):

1. **If ANY `mark_external_mixed(reason)` was called** → `"external_mixed"`. Caller-signaled external presence wins because the observer is structurally blind to external servers; degrading to `"external_mixed"` is the honest answer.
2. **Else, if `"hosted_in_process"` was observed** → `"hosted_in_process"`. Strongest-complete-path wins when multiple instrumented paths fired.
3. **Else, if `"subprocess_with_observer"` was observed** → `"subprocess_with_observer"`.
4. **Else** → `"external_mixed"` (**detection-failure default**).

### `IncompleteTraceError` raise gate

When a metric keyword is called against an `AgentRunResult` with `metadata.mcp_coverage == "external_mixed"`:

- **`allow_external_mcp_blind=False`** (default) → raises `IncompleteTraceError`, telling the caller to opt in via `allow_external_mcp_blind=True` or route all MCP traffic through agenteval-hosted servers.
- **`allow_external_mcp_blind=True`** (opt-out) → the metric keyword proceeds, returning whatever the partial trace records. The caller accepts the honesty trade-off.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The 3-valued literal set is `stable`; additions require a major-version bump (they change the consumer-facing field type).

## References

- ADR-016: MCP Coverage Detection Default
- ADR-004: Hosted-MCP Universal Trace Observation
- `src/MCPLibrary/_coverage.py` — the implementation this contract governs.
