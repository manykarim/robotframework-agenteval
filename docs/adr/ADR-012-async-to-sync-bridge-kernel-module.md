# ADR-012: Async-to-Sync Bridge as Kernel Module (`_run_async`)

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-A1 in `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` §ADR-A1. Renumbered to ADR-012 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

Four or more agenteval sub-libraries call async libraries directly: the MCP Python SDK (`mcp.client.stdio.stdio_client` + handlers), LiteLLM's async API paths, the OpenTelemetry async exporter (Phase 2), and SDK-driven coding-agent adapters (Claude Agent SDK, OpenAI Agents SDK). Each path needs consistent sync-to-async bridging because Robot Framework's keyword model is synchronous — keywords return values; they don't expose `await`.

Without a single canonical bridge, each sub-library would invent its own async-to-sync glue, with potentially incompatible fallback strategies when running under a nested event loop (e.g., Jupyter notebook execution, IDE test runners that pre-install an event loop).

agenteval evaluated the agentguard precedent (single `_run_async` helper at the kernel level — see agentguard `src/agentguard/_kernel/run_async.py`) on merit and adopts a structurally similar pattern with refinements specific to agenteval's surface.

## Decision

agenteval exposes a single async-to-sync bridge at `src/AgentEval/_kernel/run_async.py`:

```python
def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine to completion from a sync context.

    Strategy:
      1. If no running event loop: `asyncio.run(coro)` (fast path).
      2. If a loop is already running (nested context, e.g., Jupyter):
         spawn a worker thread, create a new loop there, run the coro.
    """
```

`nest_asyncio` is an opt-in workaround documented for IDE-integrated runners only (e.g., PyCharm test runner that pre-installs an event loop in the main thread). It is NOT imported by default — the worker-thread fallback covers the same case without monkey-patching the global event-loop policy.

PRD-locked constraints reflected in this decision:
- `async def` keywords using RF 6.1+ experimental async support are explicitly banned: too rough, complicates Listener v3 interactions per RF issue #4803.
- `robotframework-async` third-party dependency is explicitly banned: unclear maintenance trajectory; not on the project's dependency tree.

## Consequences

- One kernel module to maintain (`src/AgentEval/_kernel/run_async.py`). All sub-libraries import `_run_async` from this single location.
- `nest_asyncio` opt-in workaround documented in `docs/troubleshooting/async-bridge.md` (to be authored when first user reports the nested-loop case).
- Per-keyword unit tests can mock async paths via dependency injection (`_run_async` is small enough to be a clean seam).
- Touches every sub-library that calls async libs — cross-cutting concern #9 from the architecture's Project Context Analysis. Listed as a kernel deliverable in architecture.md §Project Tree.
- Conformance suite (ADR-017) tests `_run_async` against both fast-path (no running loop) and nested-loop (worker-thread fallback) scenarios.

## Alternatives

- **`async def` keywords using RF 6.1+ experimental support** — rejected. RF's async support is too rough for production use; it complicates Listener v3 interactions (the listener context becomes ambiguous under awaitable keywords) per RF issue #4803.
- **`robotframework-async` third-party dependency** — rejected. Unclear maintenance trajectory; adds a transitive dependency to a project whose ownership is uncertain.
- **Per-sub-library async bridging** — rejected. Duplication; each sub-library would invent its own glue with subtly different fallback behavior. Drift over time becomes inevitable.
- **No bridge; require all sub-libraries to expose sync-only APIs** — rejected. MCP Python SDK is async-only at its main surface (`stdio_client` is an async context manager); LiteLLM's async paths are the maintained ones (sync paths exist but lag).

## References

- Architecture L429-434 (renumbering plan) + §Cross-Cutting Concerns
- agentguard `_kernel/run_async.py` — reviewed pattern; agenteval evaluates on merit + refines for kernel namespace
- ADR-013 (Entry-Points Discovery Infrastructure) — companion kernel module
- RF issue #4803 (async keyword support roughness) — cited as motivation for the explicit `async def` ban
