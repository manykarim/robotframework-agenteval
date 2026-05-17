# ADR-009: Per-Test MCP Server Scope (Listener v3 `test_id`)

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-012 in `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` §ADR-012. Renumbered to ADR-009 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

Under `pabot --processes N` (parallel Robot Framework execution), two RF tests using the same library-hosted MCP server interleave `tools/call` traces server-side. Both tests' `mcp_coverage` claims become wrong: the server-side trace is polluted with the other test's tool calls, and the per-`AgentRunResult` tool-call list contains foreign entries.

Story 0.2 (Per-Test MCP Cleanup Spike) empirically confirmed this concurrency hazard under `pabot --processes 4`: cross-test trace bleed occurs without per-test scoping. The spike also confirmed that per-test isolation via Listener v3's `test_id` resolves the pollution — at the cost of MCP server startup latency per test (~100-500ms depending on server complexity).

## Decision

The MCP observer scopes traces **per RF test** by reading the Listener v3 `test_id` from the active RF context. Each test gets a **unique library-hosted MCP server instance** by default. The mapping is `test_id → mcp_server_instance`; the server lifecycle is bound to the test lifecycle (started at test-start hook, torn down at test-end hook).

The library `__init__` accepts an `mcp_per_test: bool = True` argument:

- **`mcp_per_test=True` (default)** — per-test scope as described above. Correct under all parallel/serial execution modes; pays the startup latency cost per test.
- **`mcp_per_test=False`** — opt-out for users who explicitly want shared MCP server instances across tests within a suite. Documented trade-off: pollution under parallel execution; only correct under serial execution. Users who choose this MUST understand the consequence; the keyword libdoc + `docs/contracts/` doc surfaces the risk explicitly.

The teardown path is hardened against the issues surfaced in Story 0.2:

- SIGTERM handler auto-installed in `MCPLifecycleManager.__init__` (default-on) ensures `atexit` handlers fire even when pabot worker processes are SIGTERM-ed at suite end. Python's default SIGTERM handler bypasses `atexit`; the auto-installed `signal.signal(signal.SIGTERM, sys.exit)` lets `atexit` cleanup run.
- Per-test stderr file path passed as `errlog=open(stderr_path, 'w')` to `stdio_client` — works around the RF/pabot stderr-fd issue where RF replaces `sys.stderr` with a non-fd buffer that breaks subprocess spawn (the spike-load-bearing fix).

## Consequences

- MCP server startup is per-test → adds 100-500ms latency per test depending on server. Acceptable for Tier 1 (rarely parallelized) and Tier 2 (small-N parallelism). Tier 3 (heavily parallelized via `Stat.Run N Times` Pass@k flows) should consider `mcp_per_test=False` with documented pollution caveat.
- The observer's `test_id` lookup gracefully degrades for non-RF callers (e.g., a Python script using agenteval directly outside RF): the observer falls back to a per-process server when no Listener v3 context is detected. Direct callers don't get parallel-safety guarantees, which is correct: they're not running under pabot.
- The 75/75 spike runs (Story 0.1, `pabot --processes 4`) validated this scope mechanism end-to-end: zero cross-test trace bleed, zero duplicates, zero drops.
- The teardown hardening (SIGTERM handler + stderr fd workaround) is documented in the public `MCPLifecycleManager` API per ADR-004's consequences.

## Alternatives

- **Shared MCP server per suite** — rejected. pabot operates at suite-level too (parallel suites); same pollution problem.
- **Trace tagging with `test_id`, single shared server** — rejected. Works in theory but brittle under server crashes: one bad test poisons the server's state for all other tests routing through it. Per-test instance gives natural isolation; crash blast-radius = 1 test.
- **Block pabot entirely** — rejected. Breaks legitimate parallel-test workflows. The whole point of supporting RF in agenteval is that RF users have pabot in their existing workflow.

## References

- PRD §`Per-Test MCP Scope` + AC-MCP-OBSERVE-03 (sidecar source, 2026-05-15)
- ADR-004 (Hosted-MCP Universal Trace Observation Pattern) — the observer that this ADR scopes
- ADR-016 (MCP Coverage Detection Default) — `mcp_coverage` field values rely on per-test scoping for correctness under parallel execution
- Story 0.1 + 0.2 spike findings (`_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` + `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md`) — empirical confirmation of the scoping mechanism + teardown hardening
