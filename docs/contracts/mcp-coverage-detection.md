# MCP Coverage Detection

**Status:** Phase-1 skeleton — content to be filled by Epic 5 Story 5.2 (Hosted-MCP Observer Honesty Fields + IncompleteTraceError wiring).
**Owning epic:** Epic 5 Story 5.2
**Related ADRs:** ADR-016 (MCP Coverage Detection Default — trust-floor + adapter contract), ADR-007 (mcp_coverage + IncompleteTraceError gate), ADR-004 (Hosted-MCP Universal Trace Observation)
**Related FRs:** FR36b (mcp_coverage field), FR37 (IncompleteTraceError), AC-MCP-OBSERVE-01

## Purpose

Governs the **per-adapter responsibility split** for detecting `mcp_coverage` (the 3-valued field `hosted_in_process` / `subprocess_with_observer` / `external_mixed` per ADR-016 D1 trust-floor). agenteval's hosted-MCP observer is structurally blind to MCP servers it didn't spawn; the **adapter** is the only entity that can detect external MCP configurations and signal degradation. This contract documents what each Tier-1 adapter MUST do, what the trust-floor decision tree is, and how detection failure defaults work.

## Scope

### In-scope

- The 3-valued `mcp_coverage` literal set + per-value semantics (per ADR-016 + ADR-007).
- D1 trust-floor: when BOTH `hosted_in_process` AND `subprocess_with_observer` paths fire successfully, report the STRONGER path.
- D4 per-adapter contract: which adapter parses which external-config file (Claude Code: `~/.claude.json` + `.mcp.json`; Copilot: `~/.copilot/mcp-config.json`; Generic LiteLLM: trivially `hosted_in_process`).
- Detection-failure default: `external_mixed` (safer than `hosted_in_process`).
- `IncompleteTraceError` gate behavior: when metric keywords MUST raise vs. when consumer opted out via `allow_external_mcp_blind=True`.

### Out-of-scope

- The hosted-MCP observer's internal implementation — that's `src/AgentEval/mcp/observer.py` (Epic 5 Story 5.2 lands) + ADR-004's content.
- Per-adapter test fixtures for the conformance suite — those live in `tests/conformance/fixtures/<adapter>/` per `conformance-fixture-format.md`.

## Contract

*Phase-1 skeleton — Epic 5 Story 5.2 fills in the formal specification.*

The contract will at minimum include:

- The 3-valued literal set + semantics.
- D1 trust-floor decision tree (which value wins when multiple paths succeed).
- D4 per-adapter detection-responsibility table.
- Detection-failure default (`external_mixed`).
- `IncompleteTraceError` raise gate + the `allow_external_mcp_blind=True` opt-out semantics.
- Test-injection scenarios for the conformance suite (per ADR-005).

Refer to ADR-016 for the ratified text; this contract surfaces the same content as a publishable per-adapter API contract for community adapter authors.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The 3-valued literal set is `stable` from Phase-1 onward; additions require major-version bump (changes the consumer-facing field type). The per-adapter detection-responsibility table is `provisional` — new adapter entries don't break consumers (an adapter can opt into the default `external_mixed` if its detection logic doesn't ship in time).

## References

- ADR-016: MCP Coverage Detection Default
- ADR-007: mcp_coverage + IncompleteTraceError
- ADR-004: Hosted-MCP Universal Trace Observation
- FR36b / FR37 / AC-MCP-OBSERVE-01 (PRD)
- Story 0.1 spike findings: `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md`
