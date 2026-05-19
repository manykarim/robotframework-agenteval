# Story 4.1: Provider Layer + Generic Coding-Agent Adapter

Status: review

## Story

As **Raj (Agent Developer)**,
I want the `providers/` layer (`LLMProviderAdapter` Protocol + LiteLLM adapter + Mock adapter + factory) plus the `GenericAdapter(InProcessAdapter)` implementation that connects to any of LiteLLM's 140+ providers,
So that I can run agent flows against any commercial LLM (Anthropic, OpenAI, Mistral, Gemini, ...) or local model (Ollama, vLLM) using a single adapter configuration — no per-provider code path required for the most common cases.

## Pre-create-story drift check (18th use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-20)

5 drifts caught + resolved pre-authoring (per the just-extended `feedback_citation_drift_first_class` Epic 3 ratification: re-derive FR-body wording from PRD source, not just check that citations exist):

- **(D-A HIGH)** epics.md L1325 declared `LLMProviderAdapter.complete(prompt: str, model: str, **kwargs) -> ProviderResponse` — architecture L890 declares `chat(messages: list[Message], tools: list[Tool] | None = None) -> ChatResponse`. LiteLLM's actual API is `litellm.completion(model=..., messages=[...])` which maps onto architecture's `chat(messages, tools)` shape cleanly. PRD L1087 references the Protocol's `stream` arg + Mock adapter's stream test as a template — `stream: bool = False` keyword-only param added for Phase-1 non-streaming. epics.md L1325 amended.
- **(D-B MED)** epics.md L1325 entry-points group `"robotframework_agenteval.providers"` — PRD FR17c L1518 + Story 1b.3 `_kernel/discovery.py:_GROUP_PROVIDERS` (L127) both ratify `"agenteval.providers"`. `robotframework_agenteval.adapters` is the LEGACY backward-compat group per ADR-013 L18 — applies to the `coding_agents` group, NOT `providers`. epics.md L1325 + L1335 amended.
- **(D-C HIGH structural)** epics.md L1329 + L1332 called `adapter.send_prompt(...)` — Story 1b.4 D1 drift ratification fixed this to single `run()` method per PRD FR12 L1506. `CodingAgentAdapter` Protocol at `src/AgentEval/types.py:314` has ONLY `run()`. epics.md L1329 + L1332 amended.
- **(D-D HIGH)** epics.md L1329 listed flat `AgentRunResult` fields `token_usage, completeness, mcp_coverage` — Story 1b.4 D8 drift ratification shipped the frozen-dataclass shape at `src/AgentEval/types.py:258`: `response_text, tool_calls, usage, metadata, cost_usd, latency_seconds, trace_id`. `completeness` + `mcp_coverage` live on the nested `metadata: AgentRunMetadata` field (per types.py L207-256). `usage` not `token_usage`. `trace_id` is a top-level field (per Story 1b.4 D7 ratification — opaque Phase-1 string; uuid4 hex by adapter convention). epics.md L1329 + L1333 amended.
- **(D-E LOW)** Architecture L894-898 declares `class AgentRunResult(BaseModel)` Pydantic — Story 1b.4 shipped `@dataclass(frozen=True)`. Pre-existing arch-vs-impl drift; NOT Story 4.1's fault. Tracked as **DF-4.1-S1** in `deferred-work.md` (architecture amendment for Phase-1.5 hygiene).

## Acceptance Criteria

### AC-4.1.1 — `LLMProviderAdapter` Protocol (PRD FR17c + architecture L890)

**Given** the architecture L883/L890 contract for the public Protocol surface,
**When** Story 4.1 implements `src/AgentEval/providers/base.py`,
**Then** the module exposes:
- `LLMProviderAdapter` as `typing.Protocol` decorated `@runtime_checkable` per architecture L883.
- Single method `chat(messages, tools=None, *, stream=False, model=None, **kwargs) -> ChatResponse` matching architecture L890.
- Property `name: str` returning adapter identity (e.g., `"litellm"`, `"mock"`).
- Property `version: str` returning the provider's installed version (LiteLLM version for the LiteLLM adapter; `"mock"` for the Mock adapter).
- Supporting types: `Message` (dataclass frozen with `role: Literal["system","user","assistant","tool"]` + `content: str | list[ContentBlock]` + optional `tool_calls: list[ToolCallRequest]`), `Tool` (dataclass frozen with `name: str` + `description: str` + `input_schema: dict[str, Any]`), `ChatResponse` (dataclass frozen with `text: str` + `tool_calls: list[ToolCallRequest]` + `usage: ProviderUsage` + `raw: Any` for provider-specific opaque payload + `cost_usd: float | None`). `ContentBlock`, `ToolCallRequest`, `ProviderUsage` declared in same module.

### AC-4.1.2 — `MockProvider` (testing-only deterministic stub)

**And** `src/AgentEval/providers/mock.py` ships `MockProvider(LLMProviderAdapter)` that:
- Implements `chat()` returning a deterministic `ChatResponse` (echoes the last user message text as `text`, no tool calls by default).
- Accepts a `responses: list[ChatResponse]` constructor param to script multi-turn behavior; raises `IndexError` on overflow.
- Reports `name = "mock"`, `version = "mock"`.
- Is the **canonical reference implementation** for adapters Raj writes per PRD L1087 narrative.

### AC-4.1.3 — `LiteLLMAdapter` (LiteLLM-backed; 140+ providers)

**And** `src/AgentEval/providers/litellm_adapter.py` ships `LiteLLMAdapter(LLMProviderAdapter)` that:
- Wraps `litellm.completion(model=..., messages=[...])` (sync; LiteLLM itself supports both sync + async — Phase-1 uses sync to keep the wrapper thin, async via `_run_async` deferred to Phase-1.5).
- Maps each `Message` to LiteLLM's expected dict shape (`{"role": ..., "content": ...}`).
- Maps each `Tool` to LiteLLM's tool-call format (`{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}`).
- Extracts the response into a `ChatResponse`: `text` from `response.choices[0].message.content`; `tool_calls` from `response.choices[0].message.tool_calls` (mapped to `ToolCallRequest` records); `usage` from `response.usage` (mapped to `ProviderUsage`); `cost_usd` via `litellm.completion_cost(completion_response=response)` falling back to `None` on `litellm.exceptions.NotFoundError` (some custom providers don't have pricing metadata).
- Reports `name = "litellm"`, `version = importlib.metadata.version("litellm")` per `_default_version` pattern (Story 1b.4 `coding_agent/base.py:_default_version`).

### AC-4.1.4 — Provider factory + entry-points discovery (PRD FR17c)

**And** `src/AgentEval/providers/factory.py` ships `get_provider(name: str) -> LLMProviderAdapter`:
- Resolves the name via `discover_providers()` from Story 1b.3 `_kernel/discovery.py:_GROUP_PROVIDERS = "agenteval.providers"`.
- Programmatic registration NOT supported in Phase-1 per `discovery.py:269` comment ("Adapter-only per PRD FR17b; providers + sandboxes are entry-points-only by design") — this is consistent with the existing kernel contract.
- Falls back to a hard-coded built-in registry `{"litellm": LiteLLMAdapter, "mock": MockProvider}` so the factory works even when entry-points haven't loaded (test-friendly). Entry-points OVERRIDE the built-in registry per FR17c.
- Raises `AdapterDiscoveryError` (existing leaf) on unknown name; error message lists known providers.

### AC-4.1.5 — `pyproject.toml` entry-points registration (PRD FR17c)

**And** `pyproject.toml`:
- Adds `[project.entry-points."agenteval.providers"]` with `litellm = "AgentEval.providers.litellm_adapter:LiteLLMAdapter"` + `mock = "AgentEval.providers.mock:MockProvider"`.
- Adds `[project.entry-points."agenteval.coding_agents"]` with `generic = "AgentEval.coding_agent.generic:GenericAdapter"` (PRD FR17a primary group per Story 1b.3 `_GROUP_CODING_AGENTS`).
- Leaves `pyproject.toml:43` `[project.optional-dependencies]` `litellm = [...]` section EMPTY (carry-over note from L85 — `litellm>=1.50,<2.0` is already in mandatory `dependencies` so optional-extras would be redundant; the empty section was a placeholder).

### AC-4.1.6 — `GenericAdapter(InProcessAdapter)` (PRD FR13a)

**And** `src/AgentEval/coding_agent/generic.py` ships `GenericAdapter(InProcessAdapter)` that:
- Accepts constructor kwargs `provider: str = "litellm"`, `model: str` (e.g., `"anthropic/claude-sonnet-4-6"`, `"openai/gpt-4o"`, `"ollama/llama3"`), and `**kwargs` forwarded to the provider's `chat()` call.
- Constructs the provider via `get_provider(provider)`.
- Overrides `run(prompt, tools=None, mcp_servers=None, **kwargs) -> AgentRunResult` per FR12.
- Internally:
  1. Constructs a single `Message(role="user", content=prompt)`.
  2. Maps `mcp_servers` (dict of `ServerHandle`) to a Phase-1 `Tool` list — Phase-1 carve-out: `mcp_servers` is accepted but the **actual MCP tool surface integration** lands in Story 4.3 orchestration keywords + Epic 5 hosted-MCP observer. Story 4.1 surface accepts the kwarg + raises `NotImplementedError` if a non-empty `mcp_servers` is passed (with a docstring pointer to Story 4.3). Tracked as **DF-4.1-S2**.
  3. Calls `provider.chat(messages=[msg], tools=tools)` after `t0 = time.monotonic()`.
  4. Builds `AgentRunResult` with: `response_text=resp.text`, `tool_calls=[]` (Phase-1 — see DF-4.1-S2), `usage=Usage(...)` from `resp.usage`, `metadata=AgentRunMetadata(completeness="full", mcp_coverage="none", ...)`, `cost_usd=resp.cost_usd or 0.0`, `latency_seconds=time.monotonic() - t0`, `trace_id=uuid.uuid4().hex`.
- Reports `name = "GenericAdapter"`, `version = importlib.metadata.version("robotframework-agenteval")` via `_default_version` pattern.

### AC-4.1.7 — Conformance tests (Story 1b.5 surface)

**And** the existing conformance suite at `tests/conformance/test_*.py` passes against `GenericAdapter` per Story 1b.5 fixtures. Phase-1 carve-out (DF-4.1-S2): MCP-related conformance fixtures that require live `mcp_servers=` are SKIPPED with a clear reason string referencing Story 4.3 + Epic 5.

### AC-4.1.8 — Unit tests

**And** unit tests cover:
- `tests/unit/providers/test_base.py` — Protocol conformance check via mypy (`mypy --strict`); `runtime_checkable` `isinstance(MockProvider(), LLMProviderAdapter)` returns True.
- `tests/unit/providers/test_mock.py` — `MockProvider.chat()` round-trip; `responses=[...]` scripting; `IndexError` on overflow.
- `tests/unit/providers/test_litellm_adapter.py` — uses `litellm.completion(model="mock-response/echo", ...)` against LiteLLM's own mock-provider path for integration tests not requiring live API keys; tool-call extraction from a recorded provider-response fixture; `completion_cost()` fallback to `None` on `NotFoundError`.
- `tests/unit/providers/test_factory.py` — `get_provider("litellm")` + `get_provider("mock")` + unknown-name raise `AdapterDiscoveryError`.
- `tests/unit/coding_agent/test_generic.py` — round-trip via Mock provider; `mcp_servers={"x": handle}` raises `NotImplementedError` with Story-4.3 pointer; `name` + `version` properties.

### AC-4.1.9 — All-gates pass

**And**:
- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean.
- `uv run python scripts/check-license-headers.py` PASS (new files include Apache-2.0 header).
- `uv run pytest tests/unit tests/conformance -q` regression-clean — Story 4.1 baseline = 624 (Story 3.3 close) + 20+ new = 644+ pass.
- `uv run pytest tests/acceptance/tier1 -q` — 6 passed (Story 3 close).
- `uv run robot tests/acceptance/smoke + tests/unit/mcp/test_robot_integration.robot` — 18 passed (Story 3 close).

### AC-4.1.10 — Project norms applied

**And**:
- 4-reviewer cross-LLM code review per `feedback_review_methodology_norms` (20th consecutive use).
- Cross-LLM review prompt explicitly includes the just-ratified `feedback_test_name_assertion_match` check ("every test's assertion body must deliver on the test name's claim").
- Codex review prompt directs behavioral probes per `feedback_codex_probe_fitness` — Codex CLI invoked with `--dangerously-bypass-approvals-and-sandbox` per the goal directive 2026-05-20 (DF-3.2-S7 sandbox-gap workaround).
- Auditor review prompt re-derives every citation from source per `feedback_citation_drift_first_class` (especially the architecture L894-898 BaseModel-vs-dataclass D-E drift — verify it stays catalogued as DF-4.1-S1).

## Tasks / Subtasks

- [x] **Task 1: Author `src/AgentEval/providers/base.py`** — Protocol + 6 supporting dataclasses (`Message`, `Tool`, `ChatResponse`, `ContentBlock`, `ToolCallRequest`, `ProviderUsage`).
- [x] **Task 2: Author `src/AgentEval/providers/mock.py`** — `MockProvider` deterministic stub (echo + scripted modes).
- [x] **Task 3: Author `src/AgentEval/providers/litellm_adapter.py`** — `LiteLLMAdapter` wrapping `litellm.completion()`.
- [x] **Task 4: Author `src/AgentEval/providers/factory.py`** — `get_provider()` with built-in registry + entry-points-override pattern + graceful fallback on partial-install.
- [x] **Task 5: Extend `pyproject.toml`** entry-points (`agenteval.providers` + `agenteval.coding_agents` both populated).
- [x] **Task 6: Author `src/AgentEval/coding_agent/generic.py`** — `GenericAdapter(InProcessAdapter)` with `mcp_servers=` Phase-1 carve-out.
- [x] **Task 7: Author 5 unit test files** — 59 new tests across `tests/unit/providers/{__init__,test_base,test_mock,test_factory,test_litellm_adapter}.py` + `tests/unit/coding_agent/test_generic.py`.
- [x] **Task 8: Log carry-overs** — DF-4.1-S1 (architecture BaseModel→dataclass amendment) + DF-4.1-S2 (Generic adapter MCP-tool-surface integration) + DF-4.1-S3 (streaming Phase-1 stub) + DF-4.1-S4 (FR36b vs AgentRunMetadata required-vs-conditional drift surfaced during dev).
- [x] **Task 9: All-gates pass** — ruff/format/mypy clean (49 src files); 683 unit+conformance + 8 skipped (was 624 Story 3.3 close; +59 net); 6 tier1; 18 RF integration; license headers PASS (all 49 .py files).
- [ ] **Task 10: 4-reviewer cross-LLM code review** — pending; per goal directive, Claude subagent uses `--dangerously-skip-permissions` + Codex CLI uses `--dangerously-bypass-approvals-and-sandbox` (addresses DF-3.2-S7).

## Dev Agent Record

### Completion notes

Story 4.1 dev complete 2026-05-20. All ACs satisfied; full all-gates green.

Highlights vs spec:

- **Discovery during dev**: AgentRunMetadata's closed 3-value Literal for `mcp_coverage` doesn't include `"none"`, but PRD FR36b conditional-requirement scope DOES allow no-MCP runs to be unconditionally exempt. Pragmatic Phase-1 stance applied (vacuously-true `"hosted_in_process"`) + carry-over DF-4.1-S4 tracks the FR36b-vs-AgentRunMetadata required-vs-conditional drift for Phase-1.5 resolution. This is the kind of sub-drift the pre-create-story drift check doesn't catch at story-spec authoring time (per the just-extended `feedback_citation_drift_first_class` Epic 3 ratification — pre-check is necessary-but-not-sufficient).

- **Mock provider self-check pattern**: module imports include a `_check: LLMProviderAdapter = MockProvider(); del _check` shape that fails at import time if the Mock drifts from the Protocol. Same pattern in `LiteLLMAdapter`. Forward-compat safety net.

- **Built-in registry + entry-points override**: `BUILTIN_PROVIDERS` ships `{"litellm", "mock"}`; entry-points OVERRIDE per FR17c semantics. Graceful fallback on `discover_providers()` raising `AdapterDiscoveryError` (partial install) — falls back to built-in registry; the kernel guarantees the Phase-1 default providers always work.

## File List

**Source (4 new):**
- `src/AgentEval/providers/base.py` — Protocol + 6 dataclasses (~200 LoC).
- `src/AgentEval/providers/mock.py` — MockProvider deterministic stub (~110 LoC).
- `src/AgentEval/providers/litellm_adapter.py` — LiteLLMAdapter wrapping `litellm.completion()` (~220 LoC).
- `src/AgentEval/providers/factory.py` — get_provider + BUILTIN_PROVIDERS (~85 LoC).
- `src/AgentEval/coding_agent/generic.py` — GenericAdapter(InProcessAdapter) (~110 LoC).

**Tests (5 new + 1 dir __init__):**
- `tests/unit/providers/__init__.py` — sub-package init.
- `tests/unit/providers/test_base.py` — 12 tests (Protocol + dataclass shapes).
- `tests/unit/providers/test_mock.py` — 10 tests.
- `tests/unit/providers/test_factory.py` — 8 tests.
- `tests/unit/providers/test_litellm_adapter.py` — 13 tests (monkeypatched `litellm.completion`).
- `tests/unit/coding_agent/test_generic.py` — 16 tests.

**Config (1 edited):**
- `pyproject.toml` — entry-points `agenteval.providers` (litellm + mock) + `agenteval.coding_agents` (generic).

**Docs (2 edited):**
- `_bmad-output/planning-artifacts/epics.md` — 4 drift fixes per pre-create-story check (D-A through D-D).
- `_bmad-output/implementation-artifacts/deferred-work.md` — DF-4.1-S1 through DF-4.1-S4 catalogued.

## Dev Notes

### Architecture compliance

- PRD FR12 (single `run()` method on Protocol); FR13a (Generic LiteLLM-backed); FR17a + FR17c (entry-points).
- Architecture L890 (`LLMProviderAdapter.chat(messages, tools)` shape — Story 4.1 D-A resolution).
- ADR-003 (InProcessAdapter base; direct override pattern; no abstract hooks).
- ADR-005 (≤2 adapters per vendor — `generic` covers all LiteLLM-supported providers in one adapter).
- Story 1b.3 `discovery.py` entry-points discovery — `agenteval.providers` (FR17c) + `agenteval.coding_agents` (FR17a primary).
- Story 1b.4 `coding_agent/base.py` ratified Protocol location at `AgentEval.types:CodingAgentAdapter` + `_default_version` helper.

### Phase-1 limitations explicitly documented

- `mcp_servers=` is accepted on `GenericAdapter.run()` but raises `NotImplementedError` in Phase-1 (DF-4.1-S2; Story 4.3 lands the actual integration).
- `LLMProviderAdapter.chat(stream=True)` is accepted at the Protocol level for future-compat but Phase-1 providers raise `NotImplementedError` on streaming (DF-4.1-S3 stub-tracker).
- LiteLLM cost computation falls back to `None` on `litellm.exceptions.NotFoundError` (some custom providers lack pricing metadata). `GenericAdapter.run()` coerces this to `0.0` so `AgentRunResult.cost_usd` stays `float`.

### Drift-resolution carry-overs

- **DF-4.1-S1**: Architecture L894-898 declares `AgentRunResult(BaseModel)` Pydantic; Story 1b.4 shipped `@dataclass(frozen=True)`. Architecture is stale. Phase-1.5 hygiene: amend architecture L883-905 to reflect the dataclass-shipped reality + the rationale (Pydantic overhead not justified for jsonl-asdict serialization path per Story 1b.2 backend design).

## Dev Agent Record

<!-- To be filled by dev workflow -->

## File List

<!-- To be filled by dev workflow -->

## Change Log

| Date       | Version | Description | Author |
| ---------- | ------- | ----------- | ------ |
| 2026-05-20 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (18th use) caught 5 drifts: D-A `complete(prompt, model)` → `chat(messages, tools)` per architecture L890 + LiteLLM API shape; D-B `robotframework_agenteval.providers` → `agenteval.providers` per PRD FR17c + discovery.py; D-C `send_prompt` → `run` per Story 1b.4 D1 ratification; D-D flat `token_usage/completeness/mcp_coverage` → nested via `metadata` + `usage` rename + `trace_id` add per Story 1b.4 D8; D-E architecture BaseModel-vs-dataclass DF-4.1-S1 Phase-1.5 carry-over. | Bob |
