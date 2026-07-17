# ADR-004: Hosted-MCP Universal Trace Observation Pattern

**Status:** accepted
**Date:** 2026-05-17

> Superseded by the four-surface refocus (2026-07). The observer pattern here is
> the still-true heart of MCPLibrary: agenteval controls the MCP server under
> test and records every tool call server-side. The coding-agent-adapter framing
> below (multiple vendor CLIs, `AgentRunResult`, cross-adapter fidelity) is gone —
> MCPLibrary now tests MCP servers directly, and the Tier-3 coding-agent mode
> drives one real agent. Read the Decision for the mechanism; ignore the adapter
> scaffolding.

## Context

Tool-call fidelity is the whole game for MCPLibrary. When you ask an agent whether
it called the right tools, you cannot trust the agent to grade its own homework —
its self-reported trace may be structured JSON, free-form text, or nothing at all.
agenteval needs its own source of truth.

The Model Context Protocol (MCP) provides one. When something invokes a tool via
MCP, the call flows through a well-defined JSON-RPC boundary. If agenteval controls
the MCP server, every `tools/call` is observable server-side — independently of
whatever is on the other end.

Story 0.1 (Hosted-MCP Universal Observer Spike) was commissioned to empirically validate the observer pattern before Epic 5 commits to a production `mcp/observer.py` API surface. The spike additionally surfaced findings about (a) the specific observation hook available in the `mcp` Python SDK, (b) behavior under `pabot --processes 4` per-test scope concurrency, (c) cross-transport portability (in-memory + stdio subprocess + streamable HTTP), and (d) `mcp_coverage` field semantics (now ratified in ADR-016).

## Decision

When the library spawns the MCP server the agent connects to, it records every `tools/call` server-side via **handler-wrapping at `Server.request_handlers[CallToolRequest]`** — a runtime dict-mutation pattern. This works for `mcp.server.lowlevel.Server` and `mcp.server.fastmcp.FastMCP` (composes `Server` at the private `_mcp_server` attribute). No subclassing required; no middleware API exists in mcp 1.27.1.

The pattern is validated across THREE transports: in-memory, stdio subprocess (handler-wrap injected at subprocess bootstrap via a wrapper script the library spawns), and streamable HTTP (FastMCP + uvicorn). The pattern survives `pabot --processes 4` per-test scope under Listener v3 — 75/75 runs across 5 smoke iterations × 15 tests captured 100% of expected tool calls with zero drops, zero duplicates, and zero cross-test trace leakage.

Implementation surface is ~250 LoC for the production observer (Epic 5 Story 5.2). Phase 1 effort estimate: 12 working days, at the high edge of the architecture.md Decision-3 L700 ±20% gate.

Empirical evidence captured on Linux 6.8 only; macOS validation is a Phase-1.5 carry-over per the D2.1 architect waiver (2026-05-17). Three independent coding agents (Codex CLI, GitHub Copilot CLI, Claude Sonnet 4.6) reproduced the Story 0.1 smoke loop + edge cases on 2026-05-17 — all three GO/clean for Story 0.1.

**Citation:** see `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` §Observation-hook decision + §Concurrency probe + §Verdict for the complete evidence trail. Synthesis at `_bmad-output/spikes/d5-reproduction-report.md`.

## Consequences

**Implementation contracts:**

- The implementation must route stdio subprocess stderr to a real file (not `sys.stderr`) when running under Robot Framework — RF replaces `sys.stderr` with a non-fd capture buffer, which breaks `mcp.client.stdio.stdio_client`'s default.
- The implementation reaches into `Server.request_handlers` and `FastMCP._mcp_server` — both technically internal in the mcp SDK. A version-drift warning guards against mcp SDK major bumps that could break this coupling. Filing an upstream issue asking for a stable observer hook on `FastMCP` is the polite long game.
- For stdio MCP servers agenteval spawns, observation needs a wrapper script that injects the observer at subprocess bootstrap. For third-party stdio binaries agenteval cannot wrap, the observer is structurally blind and coverage degrades — see ADR-016 for how that honesty is reported.

**Coverage semantics** ratified in ADR-016 are the enforcement contract on top of this observer.

**Carry-over:** macOS validation (Linux-only evidence at time of ratification).

## Alternatives

- *Require adapter-side trace extraction for all agents* — rejected because it disqualifies TUI-first agents and any future agent without structured output.
- *Wrap agent stdout with a universal log parser* — rejected because log formats are too varied; brittle and high-maintenance.
- *Hook into agent telemetry exporters (OTel)* — rejected because it requires every agent to emit OTel; very few do today.
- *Custom Server subclass with protocol-layer re-implementation* — rejected as 10×–100× the implementation cost. Would give up access to the mcp SDK's transport machinery.
- *Wrap the underlying transport streams* — rejected because tool-call semantics live above JSON-RPC and would require byte-level parsing.
- *Module-level monkey-patch of `Server.call_tool`* — rejected because it pollutes global state and breaks users who construct servers elsewhere.
- *Cooperating-subprocess-server-at-source instrumentation* (the original spike approach) — rejected post-review (D2 decision 2026-05-17) because it is not actually the handler-wrap pattern, just printf-debugging dressed up. The ratified approach is the wrapper-script injection that installs the same `request_handlers` wrap in the subprocess context.

The chosen path — handler-wrapping via `request_handlers` dict mutation, applied via wrapper-script injection for subprocesses — is a "third option" not enumerated in the original proposed ADR. Story 0.1 spike surfaced it empirically.

## References

- Original proposed text: `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` L61–74 (as ADR-007).
- Empirical evidence: `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` §Verdict + §Observation-hook decision + §Concurrency probe.
- Independent reproduction: `_bmad-output/spikes/d5-reproduction-report.md` (3-agent reproduction 2026-05-17, 3/3 GO for Story 0.1).
- Implementation API surface (Story 5.2 lifts from): spike's `observer_prototype.py` + `transports/subprocess_observer_wrapper.py` (under `_bmad-output/spikes/0-1-hosted-mcp-observer/`). Note: the spike findings doc's §`_kernel/context.py` draft belongs to Story 0.2 (cleanup primitive), not Story 0.1.
- Architecture context: `_bmad-output/planning-artifacts/architecture.md` §Decision 3 + project-tree `docs/adr/` subsection.
