## Context

The `in-process` adapter (`src/AgentEval/_core/agent_adapter.py`) drives a prompt
through a pydantic-ai agent loop against any OpenAI-compatible endpoint. Today
`run()` pops only `model`/`base_url`/`api_key` from `kwargs`, builds
`Agent(model, capabilities, toolsets, retries)`, and calls
`run_async(agent.run(prompt))` — with **no** `usage_limits` and **no**
`instructions`. The `self._extra_kwargs` captured in `__init__` is dead. So a
caller cannot (1) raise the request cap or (2) steer the agent with a server's own
guidance. Meanwhile `MCPLibrary._lifecycle._build_session_meta()` captures
`serverInfo` but drops `InitializeResult.instructions`, and `MCPSession` has no
field for it.

This design was grounded by **empirical probes of the installed
`pydantic-ai==2.12.0` wheel** (the project has a standing rule to verify the wheel,
not web docs — three prior API divergences were caught this way). Findings, treated
as ground truth below:

- `pydantic_ai.usage.UsageLimits(request_limit=50, …)` — default request cap is **50**.
- `Agent.run()` accepts both `usage_limits` and `instructions`; `Agent.__init__`
  accepts both `instructions` and `system_prompt`.
- **Deterministic proof (FunctionModel):** a model that always calls a tool trips
  `UsageLimitExceeded` at *exactly* the configured `request_limit` (3→3, 5→5,
  10→10; unset→50). So `run(prompt, usage_limits=UsageLimits(request_limit=N))`
  moves the ceiling to N, and `usage_limits=None` reproduces today's default.
- **Deterministic proof:** both `Agent(instructions=STR)` and
  `run(prompt, instructions=STR)` land `STR` on `ModelRequest.instructions`
  (control: none → empty).
- **Source-confirmed** (`agent/__init__.py::_get_instructions`, ~L2473–2481):
  agent-level + capability(skill) + run-level "additional" instructions are all
  `list.extend`-ed together; **only** `agent.override(instructions=…)` (a test
  helper this change never uses) *replaces* capability contributions. Injecting
  instructions is therefore safe alongside deferred skills.
- `mcp.types.InitializeResult.instructions` is a real `str | None` field.

Constraints: `_core` must never import a surface library or pydantic-ai at module
scope (pydantic-ai lives behind the `[agent]` extra, lazily imported inside `run()`
with `MissingExtraError`); every default must equal today's behavior; the adapter's
honest "PROXY" framing must survive.

## Goals / Non-Goals

**Goals:**

- Let the caller raise the agent's usage/request limit so long MCP scenarios are
  measurable — via a `request_limit` shortcut and a full `usage_limits` escape hatch.
- Let the caller inject a composed instruction string that reaches the model and
  composes with skills.
- Capture the MCP server's `instructions` on connect and expose it (session field +
  `MCP.Get Server Instructions`), so it can feed config-drift checks and the
  injection above.
- Keep the whole change additive, non-breaking, and honestly framed.

**Non-Goals:**

- **No auto-wiring MCP session → adapter.** The caller passes
  `instructions=session.instructions` explicitly. `_core` must not import
  `MCPLibrary`, and `MCPLibrary` must not construct adapters — dependency direction
  *and* honest framing require injection to be caller-driven, not automatic.
- **No per-field `UsageLimits` kwarg explosion.** Only the `request_limit` shortcut
  and the full `usage_limits` object; `tool_calls_limit` / `input_tokens_limit` /
  `output_tokens_limit` / `total_tokens_limit` / `count_tokens_before_request` are
  reachable through the object.
- **No `GenericAdapter` change.** `usage_limits`/`instructions` are pydantic-ai
  concepts; the one-shot LiteLLM path is untouched.
- **No new environment variables this cut.** `AGENTEVAL_REQUEST_LIMIT` is a clean
  future add (int-parse + nullish-fuzz coverage) but is deferred to keep the diff
  additive and off the string-typed `resolve_config` path. The issue's concrete use
  is programmatic.
- **No proxy relabel and no auto-read of server instructions.** Injection stays
  opt-in; `allowed-tools`/`disable-model-invocation` stay unenforced; cost stays derived.
- **No invented "neutral base" system prompt**, and **no `system_prompt` param** —
  the knob is `instructions`, threaded at run level like `usage_limits`.
- **Do not revive `self._extra_kwargs` into live forwarding.** Keep the `**kwargs`
  sponge on both signatures for forward-compat (consistent with `GenericAdapter`),
  but the three new knobs are explicit named params.

## Decisions

### D1 — Two usage-limit knobs; one precedence rule

Expose `request_limit: int | None = None` (shortcut) and `usage_limits: Any | None = None`
(escape hatch), keyword-only, on both `__init__` and `run()`. A tiny pure helper
resolves them so the precedence is unit-testable in isolation:

```python
def _resolve_usage_limits(*, run_usage_limits, run_request_limit,
                          init_usage_limits, init_request_limit, usage_limits_cls):
    if run_usage_limits is not None:   return run_usage_limits
    if run_request_limit is not None:  return usage_limits_cls(request_limit=run_request_limit)
    if init_usage_limits is not None:  return init_usage_limits
    if init_request_limit is not None: return usage_limits_cls(request_limit=init_request_limit)
    return None
```

**Precedence, one sentence:** run-level overrides `__init__` as a whole, and within
a level the full `usage_limits` object beats the `request_limit` shortcut. `None`
result ⇒ `agent.run(prompt, usage_limits=None)` ⇒ pydantic-ai's default (50) ⇒
non-breaking. `usage_limits_cls` (the real `UsageLimits`) is passed in from `run()`
after the lazy import, so the helper stays pydantic-ai-free (parameter named
lowercase to satisfy ruff `N803`).

- *Why this rule* (the adversarial review flagged this as the one genuinely
  contested point): it is the only rule that reads as the plain "run() wins over
  `__init__`" users expect and mirrors the adapter's existing model/base_url/api_key
  OR-fallback idiom. The rejected alternative (a run-level `request_limit` shadowed
  by an `__init__`-level `usage_limits` object) silently drops the caller's most
  recent, most specific value.
- *`request_limit <= 0`* is passed through unvalidated — the library owns its own
  limit semantics (a non-positive limit raises `UsageLimitExceeded` immediately;
  caller responsibility, documented). A boundary guard raising `AdapterError` is a
  possible friendliness add but is deliberately out of this minimal cut.
- *Alternatives considered:* a single `request_limit` int only (rejected — shuts out
  token-limit users needlessly); exposing every `UsageLimits` field as a kwarg
  (rejected — surface explosion, see Non-Goals).

### D2 — `instructions` injected at run level

Expose `instructions: str | None = None` on both `__init__` and `run()`; resolve
`run_instructions if run_instructions is not None else init_instructions`; pass it
to **`agent.run(prompt, instructions=…)`** (run level), omitting the kwarg entirely
when `None`. Run level is chosen because it is source-confirmed to *compose* with
capability teaching (D-context), so skills keep working; it also keeps one code path
(everything threaded at `run()`, like `usage_limits`).

- *Why `instructions`, not `system_prompt` or `server_instructions`:* `instructions`
  is pydantic-ai's modern term and matches the vocabulary already used for
  skills/capabilities; `server_instructions` would bake MCP provenance into a
  generic adapter that must not own it (the caller composes the string, often but not
  always from `session.instructions`); `system_prompt` is the older term and the
  run-level kwarg is `instructions`.
- *Empty string* is treated as a set value (only `None` means "off"); harmless and
  keeps the surface minimal.

### D3 — Capture `MCPSession.instructions` + add `MCP.Get Server Instructions`

Add `instructions: str | None = None` as the **last** field of the frozen
`MCPSession` dataclass (default keeps it backward-compatible; the sole construction
site is `_build_session_meta`, which uses kwargs). Capture with a type guard:
`instr = getattr(init_result, "instructions", None); instructions = instr if isinstance(instr, str) else None`.

Add a Tier-1 reader keyword in `src/MCPLibrary/library.py`:

```python
@keyword(name="MCP.Get Server Instructions")
@tier(1)
def get_server_instructions(self, session: MCPSession) -> str | None:
    ...  # returns session.instructions, with a runnable Example
```

- *Why include the keyword* (the review panel split here): the issue explicitly
  requests it as a first-class Tier-1 config-drift check; the MCP surface is already
  reader-keyword-rich (Get Tool Call Count, Was Tool Called, …); it gives libdoc a
  documented home for the config-drift use. The field alone would also work via
  `${session.instructions}` (like `${session.protocol_version}`) — that is the
  minimal alternative if the maintainer prefers zero new keyword surface (see Open
  Questions). Cost of including it is mechanical and enumerated in tasks: the
  doc-keyword-count gate moves 64→65.

### D4 — Lazy import + typing purity

`usage_limits` is typed `Any | None` (opaque escape hatch), `request_limit`
`int | None`, `instructions` `str | None` — all plain, no module-scope pydantic-ai
import. `UsageLimits` is imported inside `run()`'s existing lazy block (the same
`try/except ImportError → MissingExtraError(extra="agent")` that already imports
`Agent`/`OpenAIChatModel`/`OpenAIProvider`). `from __future__ import annotations` is
already in the file, so annotations never trigger an import; `Any` is chosen for the
escape hatch on dependency-direction grounds (keep the opaque object untyped at the
`_core` boundary), not because a `TYPE_CHECKING` import would break mypy.

### D5 — Honest framing: a *steered* proxy, still a proxy

Append one clause to `_CEILING` (and mirror the module-docstring PROXY note), e.g.:
"MCP server `instructions` are injected only when the caller passes `instructions=`
(the adapter never auto-reads them); `allowed-tools` / `disable-model-invocation`
are still NOT enforced." The existing substrings `PROXY` and `NOT enforced` **must
remain** (a unit test asserts `"PROXY" in …`; the recipe asserts both substrings and
prints the exact ceiling text — the recipe blockquote is updated to match). The
class-attribute name and `name` metadata are untouched.

### D6 — Deterministic tests, extend the existing file

Extend `tests/surfaces/agent/test_agent_adapter.py` (guarded with
`pytest.importorskip("pydantic_ai")`), matching its `SimpleNamespace`-fake +
env-gated `_LIVE` style:

1. Pure-unit precedence matrix on `_resolve_usage_limits` (run_ul > run_rl > init_ul
   > init_rl > None; object-beats-shortcut within a level) and `_resolve_instructions`
   (run > init; None default).
2. A **passthrough** test that monkeypatches `pydantic_ai.Agent` (and the
   `OpenAIChatModel`/`OpenAIProvider` the run imports) with recording fakes and
   asserts the resolved `usage_limits.request_limit` and `instructions` actually
   reach `agent.run(...)`. The fake `run` **must be `async def`** (real gotcha:
   `run()` does `run_async(agent.run(...))`, which `asyncio.run`s the awaitable) and
   must return a `_map_agent_result`-compatible stub (`all_messages=lambda: []`,
   `output=""`, `usage=…`).
3. One **FunctionModel end-to-end ceiling proof** through `run()`: monkeypatch
   `pydantic_ai.models.openai.OpenAIChatModel` to an always-call-tool `FunctionModel`;
   `run(prompt, request_limit=3)` raises `UsageLimitExceeded` at 3, moves to 5, and a
   bare `run()` proves the default (50) is not lowered.
4. Non-breaking: bare `run()` forwards `usage_limits=None` and omits `instructions`.

MCP side: an instructions-capture unit test (fake `init_result` with `.instructions`
str / non-str / absent) and a `MCP.Get Server Instructions` reader test. The live
in-process smoke stays env-gated; optionally note the long-scenario + injection path
in a docstring without adding cost.

## Risks / Trade-offs

- **Precedence surprise** (run-level `request_limit` discards an `__init__`-level
  `usage_limits` object's other fields) → Mitigation: the single-sentence rule is in
  both docstrings and pinned by a dedicated unit test; it is documented behavior, not
  a bug.
- **`usage_limits: Any`** means a wrong-typed object fails deep inside `agent.run()`
  rather than at the boundary → accepted escape-hatch cost.
- **Instructions compose** — a caller who passes instructions duplicating a skill's
  teaching double-informs the model → a fidelity nuance, documented, not a defect.
- **Doc-count gate** (CI-only) will fail if the reader keyword lands without bumping
  the totals → Mitigation: explicit tasks update `README.md` + `docs/index.md`
  totals and fix the pre-existing MCP subtotal drift (`docs/index.md` reads `17`
  where the true HEAD count is `18`).
- **mypy** now type-checks `agent.run(usage_limits=…, instructions=…)` against
  pinned stubs → low risk given live-acceptance proof, but `uv run mypy src/` is in
  the gate and must pass.

## Migration Plan

Additive and non-breaking — no migration. Every new parameter defaults to today's
behavior; existing callers, tests, and the default `get_adapter("in-process")` path
are unaffected. Rollback is a straight revert (no data or format changes).

## Open Questions

- **Reader keyword vs attribute-only (D3).** Recommended: ship
  `MCP.Get Server Instructions` (issue-requested, discoverable). Minimal alternative:
  the `MCPSession.instructions` field alone (`${session.instructions}`), keeping the
  keyword count at 64. Decision taken: ship it; flagged here because the design panel
  split.
- **`AGENTEVAL_REQUEST_LIMIT` env var.** Deferred (Non-Goal). Worth a follow-up if CI
  wants to raise the ceiling globally without code, with int-parse + nullish-fuzz
  coverage per the project's nullish-input norm.
- **Boundary validation of `request_limit <= 0`.** Currently pass-through; a friendly
  `AdapterError` at the boundary is a possible small add if desired.
