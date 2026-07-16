# ADR-008: MCP Spec Version Validation

**Status:** accepted
**Date:** 2026-05-17

> Superseded by the four-surface refocus (2026-07) only where the details drifted.
> The decision stands: MCPLibrary checks the negotiated MCP spec version and fails
> loud when it falls outside the supported range. Mentions of the retired
> conformance suite and the old `IncompleteTraceError` companion gate no longer
> apply.

## Context

The Model Context Protocol (MCP) spec evolves: new primitives land (`Tasks` is incoming), old transports deprecate (SSE), JSON-RPC method names occasionally rename. agenteval's MCP observer (ADR-004) parses `tools/call` JSON-RPC requests by structural pattern. If the spec changes a method name or field, the observer silently returns empty `tool_calls` lists — the conformance suite passes the empty shape; users get nonsense traces (no tool calls observed where many actually fired).

MCP-spec drift is a high-likelihood risk on the existing project risk register. agenteval's promise of "agent-agnostic tool-call observation" depends on the observer staying in lock-step with the MCP spec it's interpreting.

## Decision

The MCP observer validates the negotiated MCP spec version at session start. The validation runs on every observer attach:

1. The observer reads the MCP protocol-version field from the initial `initialize` handshake exchange.
2. If the negotiated version is outside agenteval's supported range (currently `mcp>=1.0,<2.0` — the major-version pin is the structural-stability gate), the observer raises an unsupported-version error carrying the `MCP_ERROR` code (see the error-class hierarchy, ADR-014).
3. The error message includes the observed version, the supported range, and a pointer to the agenteval upgrade docs.

A future-spec MCP server that announces a version outside the supported range trips this gate — the observer refuses loudly rather than silently returning empty traces.

Each agenteval release pins the supported MCP spec version range explicitly in `pyproject.toml`. The version-range gate in this ADR is the *semantic* gate: even if the `mcp` SDK accepts a future-spec server, the observer's parsing logic doesn't, and agenteval surfaces that clearly.

## Consequences

- Each agenteval release pins the supported MCP spec version range. Users on cutting-edge MCP servers get a clear error pointing to an agenteval upgrade path, not silent trace truncation.
- This ADR is a forcing function for keeping agenteval current with the MCP spec: when the MCP spec increments, the observer's range needs review and a bump.
- The unsupported-version error maps to the standard exit-code path via its `MCP_ERROR` code.
- A "future-spec rejection" test runs in every CI cycle, catching observer-parsing drift before it ships to users.

## Alternatives

- **Best-effort parse with warnings on unknown spec version** — rejected. Warnings get filtered in CI; users wouldn't see them. The whole point of a version-validation step is to fail loud.
- **Library tracks MCP spec via online registry** — rejected. Adds a network dependency + a spec-fetch failure mode the library has to handle. Static `pyproject.toml` pin + ADR-prescribed bump cadence is simpler.
- **Pin MCP SDK only and let the SDK enforce** — rejected. The SDK may accept future-version servers that don't break the SDK's own surface but DO break agenteval's parsing assumptions. agenteval's observer logic is its own contract; needs its own gate.

## References

- ADR-004 (Hosted-MCP Universal Trace Observation Pattern) — the observer is the entity that fires this gate
- ADR-014 (Error-Class Hierarchy) — the `MCP_ERROR` leaf this gate raises
- The `mcp` version pin in `pyproject.toml` — the currently supported range
