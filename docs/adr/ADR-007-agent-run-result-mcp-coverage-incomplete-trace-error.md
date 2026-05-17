# ADR-007: `AgentRunResult.metadata.mcp_coverage` + `IncompleteTraceError`

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-010 in `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` §ADR-010. Renumbered to ADR-007 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

When a coding agent connects to BOTH library-hosted MCP servers (the ones agenteval spawns and observes per ADR-004) AND external ones (e.g., `~/.claude.json`-registered MCP servers Claude Code reads, or the user's `~/.copilot/mcp-config.json`), the library can only observe the hosted half. Tool-call truth via hosted-MCP observation (ADR-004) becomes partial: metric keywords reporting on tool-call counts (`Get Tool Call Count`, `Get Tool Hit Rate`) silently understate the agent's actual tool usage.

This is the "external MCP blind spot": agenteval is structurally unable to observe tool calls flowing through MCP servers it didn't spawn. The metric keywords that report tool-call counts MUST signal when this blindness is in play, or users get silent half-truths reported as full truths.

Note: this ADR governs the *field value semantics* and *enforcement gate*. The *detection-failure default* (what value to assign when the adapter can't determine whether external MCP is in play) is governed by the spike-ratified ADR-016 (D1 trust-floor + D4 adapter contract).

## Decision

Every `AgentRunResult` produced by a keyword using `mcp_servers=` populates `metadata.mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` per the ADR-016 ratified literal set.

Metric keywords that report tool-call statistics (`Get Tool Call Count`, `Get Tool Hit Rate`, `Get Tool Latency`, ...) inspect `metadata.mcp_coverage` at entry. If the value is `"external_mixed"`, the keyword raises `IncompleteTraceError` (per FR37) UNLESS the user has opted in via either:

- `allow_external_mcp_blind=True` keyword argument on the metric-keyword call, OR
- `allow_external_mcp_blind=True` on the library `__init__` (sets project-wide default).

`IncompleteTraceError` is a leaf of `AgentEvalIntegrityError(AgentEvalError)` per the error hierarchy (ADR-014). Its `error_code = "INCOMPLETE_TRACE"` drives FR50 exit-code mapping (exit 3).

The "loud refusal beats silent half-truth" principle: the user who explicitly accepts the blindness via `allow_external_mcp_blind=True` keeps shipping; the user who doesn't know external MCP is in play gets stopped before tests pass wrongly.

## Consequences

- Adapter implementations (per ADR-003) must detect "external MCP in play" before each run. Claude Code CLI: parse `~/.claude.json` + project-local `.mcp.json`. Copilot CLI: parse `~/.copilot/mcp-config.json`. Generic LiteLLM: trivially `"hosted_in_process"` (LiteLLM doesn't speak MCP at all).
- Detection-failure default is `"external_mixed"` (per ADR-016 D4 adapter contract): safer than `"hosted_in_process"` (silent partial truth) AND more honest than refusing to run entirely.
- `allow_external_mcp_blind=True` is a documented opt-out that surfaces in `docs/keywords/` libdoc. Use case: CI runs with no user-level MCP config files; the user knows external MCP can't be in play but the detection logic can't prove it from the filesystem alone.
- Metric keywords that don't report tool-call statistics (e.g., `Skill.Should Activate For`, `Subagent.Get Test Plan`) don't gate on `mcp_coverage` — the field is informational for them, not load-bearing.

## Alternatives

- **Always merge external MCP traces opportunistically** — rejected. Most coding agents don't expose external MCP traffic. The "merge" would be reading the agent's local logs and hoping the format is parseable; brittle and per-agent custom.
- **Warning instead of error on `external_mixed`** — rejected. CI environments filter warnings. The honest signal must be a failure-mode the test runner can't ignore.
- **Library blocks `mcp_servers=` calls when external MCP is detected** — rejected. Too aggressive; users running Claude Code with their own `.mcp.json` for project-specific tools are common and legitimate. The `allow_external_mcp_blind=True` opt-out preserves their workflow.

## References

- PRD §`MCP Observation Strategy` + FR37 + AC-MCP-OBSERVE-01 (sidecar source, 2026-05-15)
- ADR-004 (Hosted-MCP Universal Trace Observation Pattern) — the structural basis for `mcp_coverage` reporting
- ADR-016 (MCP Coverage Detection Default) — D1 trust-floor + D4 adapter contract; ratified by Story 0.1 spike
- ADR-014 (Error-Class Hierarchy) — `IncompleteTraceError` is a leaf of `AgentEvalIntegrityError`
- ADR-008 (MCP Spec Version Validation) — parallel honesty gate at session-start time
