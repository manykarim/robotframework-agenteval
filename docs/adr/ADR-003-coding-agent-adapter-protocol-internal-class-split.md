# ADR-003: CodingAgentAdapter Protocol — Internal Class Split

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-006 in `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` §ADR-006. Renumbered to ADR-003 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

agenteval's adapter surface must accommodate two fundamentally different agent-runtime styles:

- **SDK-driven adapters** (Claude Agent SDK, OpenAI Agents SDK, LiteLLM-backed Generic) run in-process: full-fidelity object-returning APIs, structured event streams, no subprocess lifecycle.
- **CLI-driven adapters** (Claude Code CLI, Codex CLI, Copilot CLI) run as subprocesses: JSONL stream parsing, opportunistic field population, subprocess startup/teardown lifecycle, exit-code interpretation, environment-variable injection.

The library's public contract should be a single Protocol that callers can substitute by name (`coding_agent="claude-code-cli"`); the implementation machinery should let CLI-adapter contributors reuse a base class rather than re-implementing subprocess lifecycle ~500 LoC per adapter.

This pattern was reviewed in the agentguard project (`/home/many/workspace/robotframework-agentguard/docs/adr/ADR-009-coding-agent-driver.md`); agenteval evaluates it on merit and adopts a structurally similar split with refinements appropriate to agenteval's `CodingAgentAdapter` Protocol surface.

## Decision

agenteval publishes **one public Protocol** (`CodingAgentAdapter`) as the boundary contract. Internally, two base classes back the Protocol:

1. **`InProcessAdapter`** — base class for SDK-driven adapters. Provides full-fidelity defaults for trace extraction, metadata population, and completeness detection. Direct method-override pattern (no abstract hooks; SDK behavior is structured enough to populate `AgentRunResult` directly).

2. **`SubprocessAdapter(ABC)`** — base class for CLI-driven adapters. Abstract template-method pattern with 3 hooks that subclasses MUST implement:
   - `_spawn(prompt, **kwargs) -> subprocess.Popen` — launches the CLI subprocess with proper env injection
   - `_parse_event(line: str) -> Optional[ParsedEvent]` — parses one JSONL event line into the adapter's intermediate event type
   - `_finalize(events: list[ParsedEvent], exit_code: int) -> AgentRunResult` — folds the event stream into the final result

The base class owns subprocess lifecycle: signal handling, timeout enforcement, stderr capture, exit-code mapping, truncation detection (per ADR-006).

`SubprocessAdapter` is part of the **contributor-facing public API** — community CLI-adapter authors are expected to subclass it, not re-implement subprocess lifecycle. It ships in Phase 1 documented in `docs/contributor-api.md` (separate from `docs/keywords/` libdoc, which targets keyword users).

## Consequences

- Caller-side ergonomics: `coding_agent="<name>"` works identically for SDK and CLI adapters; the user never knows which base the adapter inherits from. Invocation symmetry preserved.
- Contributor-side ergonomics: a new CLI adapter is ~50-150 LoC (3 hook implementations + adapter-specific JSONL schema), not ~500 LoC of subprocess plumbing.
- `SubprocessAdapter` is a Phase-1 deliverable in the published API; breaking changes to its hook signatures require an ADR amendment + a deprecation cycle.
- The Protocol vs base-class distinction means non-agenteval projects can implement `CodingAgentAdapter` from scratch (e.g., as a thin facade over an existing test harness) without inheriting from agenteval's bases — useful for downstream projects that already have their own subprocess machinery.
- Conformance suite (ADR-017) parametrizes over both base styles via a unified `adapter_registry` fixture; subprocess vs in-process is transparent to the test.

## Alternatives

- **Two public Protocols (`SDKAgentAdapter` + `CLIAgentAdapter`)** — rejected. Caller must branch on adapter type (`if isinstance(adapter, SDKAgentAdapter): ...`), which leaks implementation detail into user code and complicates the `coding_agent=` library argument.
- **Single Protocol, no internal classes** — rejected. Every CLI adapter contributor re-implements subprocess lifecycle (~500 LoC each), with divergent timeout semantics, signal-handling, and truncation-detection rules. Conformance suite would have to test each independently rather than testing the shared base.
- **Abstract base class as the public surface (no Protocol)** — rejected. Forces inheritance for non-agenteval-native adapters; breaks the "implement the Protocol, get an adapter" pattern that lets external projects participate.

## References

- PRD §`Adapter Architecture` (sidecar source, 2026-05-15)
- agentguard ADR-009 (Coding Agent Driver) — reviewed pattern; agenteval evaluates on merit + refines for `CodingAgentAdapter` Protocol surface
- ADR-006 (AgentRunResult.metadata.completeness Field Required) — `SubprocessAdapter._finalize` must populate this field per adapter style
- ADR-009 (Per-Test MCP Server Scope) — subprocess adapters bind to per-test MCP servers via env vars injected by `_spawn`
