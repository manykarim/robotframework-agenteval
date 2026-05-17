# ADR-004: Hosted-MCP Universal Trace Observation Pattern

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-007 in `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` §ADR-007. Renumbered to ADR-004 per architecture.md project tree (`docs/adr/` subsection of the Complete Project Directory Structure — Hybrid scheme: Architectural Influences Catalog occupies ADR-001, renumbered PRD sidecar ADRs land at ADR-002..018). See ADR-001 §Amendments Log entry for this ratification.

## Context

Trace fidelity varies wildly across coding-agent adapters: structured-output SDKs (Claude Agent SDK, OpenAI Agents SDK) give well-formed traces; CLI agents (Claude Code CLI, Copilot CLI, Codex CLI) vary from structured JSON to free-form text; TUI-first agents (OpenCode) give none at all. The "agent-agnostic" claim that justifies the agenteval library's existence collapses without a per-agent guarantee mechanism for tool-call observation.

The Model Context Protocol (MCP) provides a structural opportunity: when an agent invokes tools via MCP, the tool calls flow through a well-defined JSON-RPC boundary. If the library controls the MCP server the agent connects to, every `tools/call` is observable server-side, independently of the agent's own tracing capabilities.

Story 0.1 (Hosted-MCP Universal Observer Spike) was commissioned to empirically validate the observer pattern before Epic 5 commits to a production `mcp/observer.py` API surface. The spike additionally surfaced findings about (a) the specific observation hook available in the `mcp` Python SDK, (b) behavior under `pabot --processes 4` per-test scope concurrency, (c) cross-transport portability (in-memory + stdio subprocess + streamable HTTP), and (d) `mcp_coverage` field semantics (now ratified in ADR-016).

## Decision

When the library spawns the MCP server the agent connects to, it records every `tools/call` server-side via **handler-wrapping at `Server.request_handlers[CallToolRequest]`** — a runtime dict-mutation pattern. This works for `mcp.server.lowlevel.Server` and `mcp.server.fastmcp.FastMCP` (composes `Server` at the private `_mcp_server` attribute). No subclassing required; no middleware API exists in mcp 1.27.1.

The pattern is validated across THREE transports: in-memory, stdio subprocess (handler-wrap injected at subprocess bootstrap via a wrapper script the library spawns), and streamable HTTP (FastMCP + uvicorn). The pattern survives `pabot --processes 4` per-test scope under Listener v3 — 75/75 runs across 5 smoke iterations × 15 tests captured 100% of expected tool calls with zero drops, zero duplicates, and zero cross-test trace leakage.

Implementation surface is ~250 LoC for the production observer (Epic 5 Story 5.2). Phase 1 effort estimate: 12 working days, at the high edge of the architecture.md Decision-3 L700 ±20% gate.

Empirical evidence captured on Linux 6.8 only; macOS validation is a Phase-1.5 carry-over per the D2.1 architect waiver (2026-05-17). Three independent coding agents (Codex CLI, GitHub Copilot CLI, Claude Sonnet 4.6) reproduced the Story 0.1 smoke loop + edge cases on 2026-05-17 — all three GO/clean for Story 0.1.

**Citation:** see `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` §Observation-hook decision + §Concurrency probe + §Verdict for the complete evidence trail. Synthesis at `_bmad-output/spikes/d5-reproduction-report.md`.

## Consequences

**Implementation contracts:**

- Implementation must route stdio subprocess stderr to a real file (not `sys.stderr`) when running under Robot Framework — RF replaces `sys.stderr` with a non-fd capture buffer, breaking `mcp.client.stdio.stdio_client`'s default. See `docs/contracts/listener-integration.md` (Story 1a.4 skeleton) for the contributor-facing constraint.
- Implementation accesses `Server.request_handlers` and `FastMCP._mcp_server` — both technically internal in the mcp SDK. An `AdapterVersionDriftWarning` MUST be added as part of Epic 5 Story 5.2 (per architecture.md project tree FR reference) to detect mcp SDK major-version bumps that could break this coupling. Recommend filing an upstream issue with mcp asking for a stable observer hook on `FastMCP`.
- For stdio MCP servers the library spawns, observation requires a wrapper script that injects the observer at subprocess bootstrap (the `subprocess_observer_wrapper.py` pattern from the spike). For genuinely third-party stdio MCP binaries that the library cannot wrap, the observer is structurally blind and the run degrades to `mcp_coverage="external_mixed"` per ADR-016. Adapters MUST detect external/uninstrumented MCP configurations and signal via `observer.mark_external_mixed(reason)` per ADR-016's adapter contract.

**Downstream story unblocks:**

- Epic 5 Story 5.2 (`src/AgentEval/mcp/observer.py` production implementation): API surface drafted in spike findings doc §`_kernel/context.py` is the implementation contract.
- Epic 1b Story 1b.2 (Trace + Observability Kernel): `mcp_coverage` semantics ratified in ADR-016 are the kernel-side enforcement contract.
- Epic 3 Story 3.1 (MCP Server Lifecycle Keywords): RF-compat stderr fix MUST be wired into `mcp/transport.py`.

**Production carry-overs (not blockers for ratification; tracked in `_bmad-output/implementation-artifacts/deferred-work.md`):**

- macOS validation (D2.1 architect waiver — Phase-1.5).
- `AdapterVersionDriftWarning` for mcp SDK version compatibility (Story 5.2 deliverable).
- Upstream issue with mcp project requesting stable observer hook on FastMCP.

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
