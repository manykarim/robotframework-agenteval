## Why

The `in-process` adapter is meant to measure a real MCP server end to end on
*just an LLM key* — no coding-agent CLI. Two gaps stop it from faithfully
driving a non-trivial server:

1. **The request/usage limit is fixed at pydantic-ai's default of 50.**
   `InProcessAgentAdapter.run()` calls `agent.run(prompt)` with no
   `usage_limits`, and only pops `model`/`base_url`/`api_key` from `kwargs`, so
   there is **no supported knob** to raise it. Any legitimately long agentic
   scenario (e.g. restful-booker: read → create → authenticate → delete with
   per-step assertions and a suite build ≈ 50–100 model requests) dies on
   `UsageLimitExceeded: request_limit of 50`. *Empirically confirmed:* the wheel's
   default is 50, and a model that keeps calling a tool trips at exactly the
   configured limit.
2. **The MCP server's own `instructions` never reach the agent.** On connect,
   `_build_session_meta()` captures `serverInfo` but discards the top-level
   `instructions` field of the `InitializeResult`, and `MCPSession` has no field
   for it. A compliant MCP client (Claude Code, etc.) surfaces that guidance to
   the model; the adapter measures the server as if the guidance did not exist,
   so it **understates** how a steered agent treats the server.

Both share one root cause: `run()` gives the caller no way to influence what it
passes to `agent.run()`. rf-mcp's own bespoke harness passes the identical long
scenario precisely because it sets `request_limit=100` and injects the server's
`instructions` — the in-process adapter can do neither today.

## What Changes

- **Two usage-limit knobs on `InProcessAgentAdapter`** (`__init__` **and** `run()`,
  keyword-only, defaulting to today's behavior):
  - `request_limit: int | None` — the common shortcut (`get_adapter("in-process", request_limit=120)`).
  - `usage_limits: Any | None` — the full pydantic-ai `UsageLimits` escape hatch
    (token limits, tool-call limit, …), for callers who need more than the request cap.
  - Precedence, stated as one rule: **run-level overrides `__init__` as a whole;
    within a level, the full `usage_limits` object beats the `request_limit`
    shortcut.** All unset ⇒ pydantic-ai's default (50) ⇒ **non-breaking**.
- **An `instructions: str | None` knob** on `__init__`/`run()` that injects a
  caller-composed string as the agent's run-level instructions. Source-confirmed
  to **compose** with deferred-skill teaching (it will not clobber
  `load_capability`). None ⇒ omitted ⇒ **non-breaking**.
- **Capture the MCP server's instructions on connect:** `MCPSession` gains a
  trailing `instructions: str | None` field, populated from
  `InitializeResult.instructions`. Readable as `${session.instructions}` and via a
  new Tier-1 reader keyword **`MCP.Get Server Instructions`** — useful on its own
  for config-drift checks, and the string a caller passes into `instructions=`.
- **One honest clause appended to the adapter's `validation_ceiling`**: injecting
  `instructions` makes it a *steered* proxy; the adapter still never auto-reads a
  server's instructions, and `allowed-tools`/`disable-model-invocation` stay
  **NOT enforced**. The `PROXY` framing is unchanged.

Every default equals today's behavior; the change is purely additive (no **BREAKING**).

## Capabilities

### New Capabilities

- (none) — this change extends two existing capabilities.

### Modified Capabilities

- `in-process-agent-adapter`: ADD two requirements — the caller can raise the
  agent's usage/request limit, and can inject instructions that reach the model
  (composed with skills), with the proxy framing preserved.
- `mcp-testing`: ADD one requirement — `Connect To Server` captures the server's
  `instructions` and exposes them (session field + `MCP.Get Server Instructions`).

## Impact

- **Code:** `src/AgentEval/_core/agent_adapter.py` (three new params + a small
  `_resolve_usage_limits`/`_resolve_instructions` seam + lazy `UsageLimits`
  import inside `run()`); `src/MCPLibrary/_lifecycle.py` (`MCPSession.instructions`
  + capture); `src/MCPLibrary/library.py` (new reader keyword).
- **Dependency direction preserved:** `_core` still never imports a surface lib or
  pydantic-ai at module scope; injection stays caller-driven (no MCP→adapter
  auto-wiring).
- **Docs/gates:** the new keyword moves the count 64→65 — update
  `README.md` + `docs/index.md` totals (and fix the pre-existing MCP subtotal
  drift), plus a short recipe subsection on long scenarios + instruction injection.
- **Tests:** extend `tests/surfaces/agent/test_agent_adapter.py` (precedence
  matrix + a `FunctionModel` ceiling proof + passthrough) and the MCP lifecycle
  tests (instructions capture + reader). All deterministic; the live smoke stays
  env-gated.
