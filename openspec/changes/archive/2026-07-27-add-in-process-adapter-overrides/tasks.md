## 1. Adapter: usage-limit + instruction knobs (`src/AgentEval/_core/agent_adapter.py`)

- [x] 1.1 Add keyword-only params `request_limit: int | None = None`, `usage_limits: Any | None = None`, `instructions: str | None = None` to `InProcessAgentAdapter.__init__`; store them on `self` (`self._request_limit`, `self._usage_limits`, `self._instructions`). Keep the existing `**kwargs` sponge; do NOT revive `self._extra_kwargs` into live forwarding.
- [x] 1.2 Add a pure helper `_resolve_usage_limits(*, run_usage_limits, run_request_limit, init_usage_limits, init_request_limit, usage_limits_cls)` implementing the precedence chain `run_ul > run_rl > init_ul > init_rl > None` (param name `usage_limits_cls` lowercase for ruff N803). Add `_resolve_instructions(run_instructions, init_instructions)` returning `run if run is not None else init`.
- [x] 1.3 In `run()`, pop `request_limit`/`usage_limits`/`instructions` from `kwargs` (like `model`/`base_url`/`api_key`). Extend the existing lazy import block with `from pydantic_ai.usage import UsageLimits`.
- [x] 1.4 Resolve the effective limit via the helper (passing `usage_limits_cls=UsageLimits`) and effective instructions; build `run_kwargs = {"usage_limits": <resolved-or-None>}` and add `instructions` only when not `None`; call `run_async(agent.run(prompt, **run_kwargs))`. Confirm bare `run()` yields `usage_limits=None` and no `instructions` kwarg (byte-identical default path).
- [x] 1.5 Append one honest clause to `_CEILING` (server `instructions` injected only on caller request, never auto-read; `allowed-tools`/`disable-model-invocation` still NOT enforced) — keep the substrings `PROXY` and `NOT enforced` intact — and mirror the one-line PROXY note in the module docstring.

## 2. MCP: capture + expose server instructions (`src/MCPLibrary/`)

- [x] 2.1 `_lifecycle.py`: add `instructions: str | None = None` as the LAST field of the frozen `MCPSession` dataclass; update its docstring to mention the captured instructions.
- [x] 2.2 `_lifecycle.py::_build_session_meta`: capture `instr = getattr(init_result, "instructions", None); instructions = instr if isinstance(instr, str) else None` and pass it into the `MCPSession(...)` kwargs.
- [x] 2.3 `library.py`: add `@keyword(name="MCP.Get Server Instructions") @tier(1) def get_server_instructions(self, session: MCPSession) -> str | None:` returning `session.instructions`, with a runnable pipe-table Example (so `check-keyword-examples` passes).

## 3. Tests (deterministic; extend existing files)

- [x] 3.1 `tests/surfaces/agent/test_agent_adapter.py`: pure-unit precedence matrix over `_resolve_usage_limits` (run_ul > run_rl > init_ul > init_rl > None; full object beats shortcut within a level) and `_resolve_instructions` (run > init; None default). Guard with `pytest.importorskip("pydantic_ai")`.
- [x] 3.2 Passthrough test: monkeypatch `pydantic_ai.Agent` (+ the `OpenAIChatModel`/`OpenAIProvider` `run()` imports) with recording fakes whose `run` is `async def` and returns a `_map_agent_result`-compatible stub (`all_messages=lambda: []`, `output=""`, `usage=…`); assert the resolved `usage_limits.request_limit` and `instructions` reach `agent.run(...)`, and that run-level beats `__init__`-level.
- [x] 3.3 FunctionModel ceiling proof: monkeypatch `pydantic_ai.models.openai.OpenAIChatModel` to an always-call-tool `FunctionModel`; assert `run(prompt, request_limit=N)` raises `UsageLimitExceeded` **matching the value** `request_limit of N` (not just the exception type — else the default 50 would gate identically), with N=3 and N=**120** (above the default 50) so a *raised* cap is proven honored end-to-end.
- [x] 3.4 Non-breaking test: bare `run()` forwards `usage_limits=None` and omits the `instructions` kwarg.
- [x] 3.5 MCP instructions-capture unit test: fake `init_result` with `.instructions` as a str (captured), a non-str (→ `None`), and absent (→ `None`); assert `MCPSession.instructions` and `MCP.Get Server Instructions` agree.

## 4. Docs + gates

- [x] 4.1 Bump the keyword total 64 → 65 in `README.md:45` and `docs/index.md:8` ("N keywords across 6 libraries"); update the MCP per-library subtotals (`README.md` MCP row and `docs/index.md` MCP row), fixing the pre-existing `docs/index.md` `17` → `18` drift on the way to `19`.
- [x] 4.2 Add a short subsection to `docs/recipes/12-in-process-agent-no-cli-metrics.md` covering long scenarios (`request_limit=`) and injecting a server's guidance (`instructions=${session.instructions}`); update the recipe's ceiling blockquote to match the new `_CEILING` text and confirm its `Should Contain` assertions still pass.
- [x] 4.3 Check `docs/contracts/stability-surface.md` "42 keywords across 4 libraries" — bump if the reader keyword is counted in that surface (MCP is one of the four); keep the contract-sections gate green.
- [x] 4.4 Run the full local gate that mirrors CI: `uv run ruff check src/ tests/` · `uv run ruff format --check src/ tests/` · `uv run mypy src/` · `uv run python scripts/check-license-headers.py` · `uv run python scripts/check-contract-sections.py` · `uv run python scripts/check_doc_keyword_count.py` · `uv run python scripts/check-doc-rendering.py` · `uv run python scripts/check-keyword-examples.py` · `uv run pytest tests/`. Fix any failure at root cause (no `--no-verify`).

## 5. Close out

- [x] 5.1 `openspec validate add-in-process-adapter-overrides --strict` (or the repo's validate command) passes.
- [ ] 5.2 (optional, env-gated) Re-run the live in-process smoke and, if rf-mcp is available, verify the long restful-booker scenario now completes with `request_limit` raised — the empirical claim behind this change.
- [ ] 5.3 Archive the change (`openspec archive add-in-process-adapter-overrides`) after implementation lands and gates are green; confirm the two capability baselines absorbed the ADDED requirements.
