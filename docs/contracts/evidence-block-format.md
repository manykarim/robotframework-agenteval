# Evidence Block Format

**Status:** Phase-1 ratified — Story 5.3 filled the Contract section 2026-05-20.
**Owning epic:** Epic 5 — Trace Observability Kernel
**Related ADRs:** ADR-004 (Hosted-MCP Universal Trace Observation), ADR-007 (mcp_coverage + IncompleteTraceError)
**Related FRs:** FR34a (evidence-block format), FR34b (evidence-block visual contract), PRD §Editorial Moat

## Purpose

Governs the structure + content of the **Evidence Block** that agenteval emits with every assertion outcome. The `Get Last Evidence Block` keyword returns this block; CI report renderers + the `agenteval` CLI consume it. The block is the PRD's "editorial moat" — it makes WHY an assertion passed or failed structurally inspectable, not narrated.

## Scope

### In-scope

- Field-level schema of the evidence block (keys, types, optionality).
- Required fields per assertion family (trace-based, metric-based, judge-based).
- Serialization format (JSON-on-the-wire; rendered Markdown in the run report).
- Stability label assignment for each field (`stable` / `provisional` / `experimental`).

### Out-of-scope

- How the block is *rendered* in any specific report format (HTML, JUnit XML, OTel span attributes) — those live in their own contracts (`junit-xml-enrichment.md`, `otel-trace-visual.md`).
- How adapters *capture* the underlying tool-call traces — see `listener-integration.md` (Listener v3 hook surface) + ADR-004 (hosted-MCP observation pattern).
- Span-attribute mapping that drives Epic 5.3 evidence-block production — see [`otel-trace-visual.md`](otel-trace-visual.md).

## Contract

*Phase-1 ratified by Story 5.3 (2026-05-20).*

### Field-level JSON schema

Every assertion outcome that emits an Evidence Block ships a JSON-shaped record at `AgentEval.telemetry.evidence_block.EvidenceBlock` with the following fields:

| Field | Type | Required | Stability | Notes |
| --- | --- | --- | --- | --- |
| `evidence_id` | `str` (UUID4 hex) | Yes | `stable` | Per-emission unique identifier; consumers correlate Evidence Block ↔ JSONL trace artifact via this id. |
| `assertion_name` | `str` | Yes | `stable` | RF keyword that produced the block (e.g., `"Send Prompt"`, `"Get Tool Discoverability"`). |
| `outcome` | `Literal["pass", "fail", "skip", "degraded"]` | Yes | `stable` | `degraded` reserved for Story 5.4's `DegradedTraceWarning` flow. |
| `prompt` | `str` | Yes | `stable` | The user prompt the agent saw (post-redaction). |
| `response` | `str` | Yes | `stable` | The agent's final response text (post-redaction). |
| `tool_calls` | `list[dict]` (each: `ToolCallTrace.asdict`) | Yes | `provisional` | Tool calls observed during the run (per ADR-004 + Story 5.2 hosted-MCP observer). |
| `cost_usd` | `float` | Yes | `stable` | Total cost reported by the provider (USD). |
| `coverage` | `Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` | Yes | `stable` | `AgentRunResult.metadata.mcp_coverage` per FR36b + ADR-016 D1. |
| `completeness` | `Literal["complete", "truncated", "partial"]` | Yes | `stable` | `AgentRunResult.metadata.completeness` per FR36a. |
| `redaction_report` | `list[str]` | Yes | `provisional` | Pattern names of any redactions applied (e.g., `["openai_api_key", "anthropic_api_key"]`). Empty list means no redactions fired. |
| `metadata` | `dict[str, Any]` | No | `provisional` | Free-form extension surface for adapter-specific evidence (e.g., Claude Code CLI's `total_cost_usd` validation). |

### Visual format (markdown)

`EvidenceBlock.to_markdown()` returns a human-readable 80-char-wide rendering per AC-SIMPLICITY-01 ("legibility = simplicity codified as a contract"). The format is:

```
============================ EVIDENCE BLOCK ============================
Assertion: <assertion_name>          Outcome: <outcome>
Evidence:  <evidence_id>
------------------------------------------------------------------------
Prompt:    <prompt> (truncated at 80 chars per line)
Response:  <response> (truncated at 80 chars per line)
------------------------------------------------------------------------
Tool calls: <count> (source: hosted_mcp=<N>, adapter=<M>)
  <tool_name_1>(<args_summary>) → ok in <latency_ms>ms
  ...
------------------------------------------------------------------------
Cost: $<cost_usd>    Coverage: <coverage>    Completeness: <completeness>
Redactions: <pattern_names if any, else "none">
========================================================================
```

Rich visualization (color, syntax highlighting, link previews) is Phase-2 per `docs/contracts/otel-trace-visual.md`.

### Redaction integration

Both `to_dict()` and `to_markdown()` apply `_kernel/redaction.redact()` (via `redact_dict`) to every text field before emission. This is defense-in-depth: even though the OTel `RedactionProcessor` already scrubs span attributes during emission, the Evidence Block is built from `AgentRunResult` fields (NOT span attributes), so the redaction pass at emit time is the only guard for those fields.

### Required fields per assertion family

| Family | Required base fields | Additional required fields |
| --- | --- | --- |
| Trace-based (Phase-1) | All base fields above | None |
| Metric-based (Phase-2) | All base fields above | `metric_name`, `threshold`, `observed_value` |
| Judge-based (Phase-2 via `[judge]` extra) | All base fields above | `judge_rubric_id`, `judge_score`, `judge_calibration_run_id` |

Phase-1 only ships the trace-based family; metric + judge families are Phase-2 carve-outs per PRD §Phase 2 scope.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. Field additions are minor-version-bump safe; field removals or type changes require major-version bump per NFR-MAINT-03. Changes to redaction rules require security review per `SECURITY.md`.

## References

- ADR-004: hosted-MCP universal trace observation
- ADR-007: mcp_coverage + IncompleteTraceError
- PRD §Editorial Moat + FR34a (format) + FR34b (visual contract)
- [`otel-trace-visual.md`](otel-trace-visual.md): span-attribute mapping that drives evidence-block production (Epic 5.3)
- [`listener-integration.md`](listener-integration.md): Listener v3 hook surface that captures the underlying traces
