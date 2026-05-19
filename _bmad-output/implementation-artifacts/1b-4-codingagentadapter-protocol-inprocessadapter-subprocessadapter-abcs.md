# Story 1b.4: CodingAgentAdapter Protocol + InProcessAdapter / SubprocessAdapter ABCs

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **Epic 4 implementer** (Generic LiteLLM + Claude Code CLI adapters) **and Phase-2 adapter author** (Epics 10-11),
I want **the `CodingAgentAdapter` Protocol (single `run()` method per PRD FR12) declared in `src/AgentEval/types.py` + re-exported through `coding_agent/base.py`, plus `InProcessAdapter` (direct-override pattern per ADR-003 L22-23) + `SubprocessAdapter(ABC)` (3-hook template-method pattern with `_spawn`/`_parse_event`/`_finalize` per ADR-003 L24-29 + architecture L1228) ABCs scaffolded with `AgentRunResult` + `AgentRunMetadata` shared types (per ADR-006 `.metadata` nesting) + the `UnsupportedBinaryVersionError(AgentEvalCompatError)` leaf added to `errors.py` (Story 1b.3 errors.py L59 forward-ref retired) + the `_assert_binary_version` helper with FR47-exact error-message format**,
So that **concrete adapters (Generic LiteLLM in Story 4.1, Claude Code CLI in Story 4.2, Anthropic/OpenAI SDKs in Epic 10, Codex/Copilot CLIs in Epic 11) implement against a stable contract that honors PRD FR12 + ADR-003 + ADR-006 + architecture L853 import-discipline; the adapter cap rule (ADR-005 — ≤2 per vendor + 1 universal) has a structural enforcement point; and Story 1b.3's `_kernel/discovery.py` TYPE_CHECKING forward-ref (`from AgentEval.types import CodingAgentAdapter`) resolves cleanly with the `type: ignore[attr-defined]` comment removed**.

## Acceptance Criteria

> **Pre-create-story drift check (8th consecutive use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-19):** Surfaced 14 drifts in the pre-edit Story 1b.4 epics.md spec vs ratified sources (6 HIGH + 4 MED + 4 LOW/clean). Per Many's 2026-05-19 ratification, ALL 14 resolved via the path-of-least-amendment by honoring ratified sources. Key resolutions:
>
> - **(D1 HIGH)** Single `run(prompt, tools=None, mcp_servers=None, **kwargs) -> AgentRunResult` Protocol method per PRD FR12 L1506 (NOT two-method `send_prompt + run_scenario`).
> - **(D2/D15 HIGH)** `AgentRunResult.metadata.{completeness, mcp_coverage}` nested per ADR-006 L15 + PRD FR36a/b L1553-1554 (NOT flat top-level fields). Story 1b.4 lands the `AgentRunMetadata` sub-dataclass alongside `AgentRunResult`.
> - **(D3/D4 MED)** Reuse Story-1b.2 `ToolCallTrace` + `Usage` types (NOT new `ToolCall`/`TokenUsage` aliases). `types.py` L31-32 forward-ref list retired.
> - **(D6/D7 HIGH)** Drop undefined `Scenario`/`MCPServer`/`RawResponse`/`ParsedEvent` types from Protocol. MCP lifecycle stays at Story 1b.1's `MCPLifecycleManager`; adapters CONSUME live `ServerHandle` instances via `run(..., mcp_servers=...)`.
> - **(D8 HIGH)** Protocol class declared in `src/AgentEval/types.py` (re-exported through `coding_agent/base.py`) per architecture L853 cross-sub-library import discipline + Story 1b.3 `discovery.py` L102 TYPE_CHECKING forward-ref. This dissolves the circular-dep risk if Protocol lived in `coding_agent/base.py` while being imported by `_kernel/discovery.py`.
> - **(D9 MED)** `InProcessAdapter` direct-method-override pattern per ADR-003 L22-23 (NO abstract `_invoke_llm` hook + NO `RawResponse` type).
> - **(D10 HIGH)** `SubprocessAdapter` 3-hook template-method pattern per ADR-003 L24-29 + architecture L1228: `_spawn(prompt, **kwargs) -> subprocess.Popen` + `_parse_event(line: str) -> ParsedEvent | None` + `_finalize(events, exit_code) -> AgentRunResult`. NOT 2-hook `_subprocess_command`/`_parse_stream_output`. `ParsedEvent` is a `TypeAlias = Any` in Story 1b.4; concrete adapters declare per-adapter intermediate types.
> - **(D11 MED)** `_agenteval_tier` is set on keyword METHODS via `@tier(3)` per architecture L620 + Story 1b.1's `tier.py` decorator, NOT as a class attribute on the Protocol. Adapters don't carry tier metadata; keywords that USE adapters (e.g., `Send Prompt`) do.
> - **(D13 LOW)** `UnsupportedBinaryVersionError(AgentEvalCompatError)` leaf declaration belongs in Story 1b.4 (per Story 1b.3 errors.py L59 forward-ref) + per-adapter raise sites in Epic 4 Story 4.2 + Epic 11 Story 11.3. `docs/contracts/error-class-hierarchy.md` L81 ownership row amended pre-authoring per fix-the-losing-source-NOW.
> - **(D12 clean)** `trace_id: str` UUID hex string — no drift; format-format decision documented for Phase-2 OTLP migration.
> - **(D14 MED)** Sandbox integration OUT-OF-SCOPE for adapters per architecture L1523 (sandbox routes through `scenarios/` + `security/policy.py`). FR17b `coding_agent=` kwarg on `AgentEval.__init__` deferred to Epic 4 Story 4.1 with forward-ref note in Story 1b.4 dev notes.
>
> Pre-authoring fixes: `_bmad-output/planning-artifacts/epics.md` L973-993 (Story 1b.4 spec) re-authored 2026-05-19. `docs/contracts/error-class-hierarchy.md` L81 ownership row updated 2026-05-19.

### AC-1b.4.1 — `CodingAgentAdapter` Protocol at `src/AgentEval/types.py`

**Given** the kernel modules from Stories 1b.1-1b.3,
**When** Story 1b.4 lands the Protocol + ABCs,
**Then** `src/AgentEval/types.py` exposes the `CodingAgentAdapter` Protocol class (per architecture L853 cross-sub-library import discipline + Story 1b.3 `discovery.py` L102 TYPE_CHECKING forward-ref) with the single ratified method signature `run(prompt: str, tools: list[str] | None = None, mcp_servers: dict[str, ServerHandle] | None = None, **kwargs: Any) -> AgentRunResult` per PRD FR12 L1506, plus read-only properties `name: str` (adapter identifier) + `version: str` (adapter package version). The Protocol uses `typing.Protocol` with `@runtime_checkable` so `isinstance(obj, CodingAgentAdapter)` is supported at runtime for the FR17b composition path. The Protocol does NOT carry a `_agenteval_tier` class attribute — tier semantics apply to library keywords (`Send Prompt`, `Run Scenario`) decorated with `@tier(3)` per Story 1b.1's `tier.py`, NOT to the adapter classes themselves.

### AC-1b.4.2 — `coding_agent/base.py` re-exports the Protocol

**And** `src/AgentEval/coding_agent/base.py` re-exports `CodingAgentAdapter` from `src/AgentEval/types.py` (`from AgentEval.types import CodingAgentAdapter as CodingAgentAdapter`). Contributor-facing imports use the documented path `from AgentEval.coding_agent import CodingAgentAdapter`; `_kernel/discovery.py` continues importing from `AgentEval.types` per its TYPE_CHECKING forward-ref pattern (no circular-dep). Identity check: `AgentEval.coding_agent.CodingAgentAdapter is AgentEval.types.CodingAgentAdapter` returns `True`.

### AC-1b.4.3 — `InProcessAdapter` direct-override pattern (no abstract hooks)

**And** `src/AgentEval/coding_agent/base.py` exposes `InProcessAdapter` as a concrete-by-default base class for SDK-driven adapters per ADR-003 L22-23: "direct method-override pattern; no abstract hooks; SDK behavior is structured enough to populate `AgentRunResult` directly". Subclasses override `run()` directly. The base provides shared helpers — default `name` + `version` properties (overridable; the default `name` reads from `type(self).__name__`, the default `version` reads from `importlib.metadata.version(type(self).__module__.split('.')[0])` with a `"unknown"` fallback when metadata is not available) + a default constructor signature `__init__(self, **kwargs)` capturing adapter-side config into `self._adapter_config: dict[str, Any]` — but ZERO `@abstractmethod`-decorated members.

### AC-1b.4.4 — `SubprocessAdapter(ABC)` 3-hook template-method pattern

**And** `src/AgentEval/coding_agent/base.py` exposes `SubprocessAdapter(ABC)` as an abstract template-method base class for CLI-driven adapters per ADR-003 L24-29 + architecture L1228 with exactly 3 `@abstractmethod` hooks:

- `_spawn(self, prompt: str, **kwargs: Any) -> subprocess.Popen[str]` — launches the CLI subprocess with proper env injection (`stdout=subprocess.PIPE`, `stderr=subprocess.PIPE`, `text=True`, `start_new_session=True` per Story 1b.1 `MCPLifecycleManager` process-group hygiene precedent).
- `_parse_event(self, line: str) -> ParsedEvent | None` — parses one JSONL event line into the adapter's per-adapter intermediate event type `ParsedEvent` (declared as `ParsedEvent: TypeAlias = Any` in `coding_agent/base.py` for Story 1b.4; concrete adapters in Epic 4/11 declare their own concrete intermediate types like `ClaudeCodeEvent` or `CopilotEvent`). Returns `None` to skip non-event lines (e.g., progress chatter, blank lines).
- `_finalize(self, events: list[ParsedEvent], exit_code: int) -> AgentRunResult` — folds the event stream into the final result.

The base class implements `run()` itself as a concrete template method orchestrating `_spawn` → JSONL-line iteration through `_parse_event` (collecting non-None events into a list) → `_finalize`. The base ALSO provides the concrete `_assert_binary_version(self, binary: str, min: str, max: str | None) -> None` helper per FR47 + AC-1b.4.7.

### AC-1b.4.5 — `AgentRunResult` dataclass in `src/AgentEval/types.py`

**And** `AgentRunResult` dataclass is added to `src/AgentEval/types.py` with these 7 fields (all `@dataclass(frozen=True)` per Story 1b.2's stdlib-dataclass pattern):

- `response_text: str` — primary text output from the agent.
- `tool_calls: list[ToolCallTrace]` — tool invocations observed during the run; reuses Story 1b.2's `ToolCallTrace` type per architecture L885 (NOT a new `ToolCall` type).
- `usage: Usage` — token usage; reuses Story 1b.2's `Usage` type per architecture L967 (NOT a new `TokenUsage` alias).
- `metadata: AgentRunMetadata` — sub-dataclass containing the nested `.metadata.completeness` + `.metadata.mcp_coverage` fields per ADR-006 L15 + PRD FR36a/b L1553-1554 (REQUIRED nesting; NOT flat top-level fields).
- `cost_usd: float` — total USD cost reported by the provider (or 0.0 for Phase-1 stubs).
- `latency_seconds: float` — wall-clock duration of the `run()` call.
- `trace_id: str` — UUID hex string linking to the trace artifact at `${OUTPUT_DIR}/agenteval/trace__<suite>__<test>.jsonl` per PRD FR51 L1579. Phase-1 contract is UUID hex; Phase-2 OTLP migration may switch to OTel 32-char hex (documented in dataclass docstring as Phase-2 carry-over).

### AC-1b.4.6 — `AgentRunMetadata` sub-dataclass enforces ADR-006 + ADR-016 value spaces

**And** `AgentRunMetadata` sub-dataclass is added to `src/AgentEval/types.py` with these fields:

- `completeness: Literal["complete", "truncated", "partial"]` per PRD FR36a L1553 — 3-state value space per ADR-006 L15 (NOT 4-state with `"none"`).
- `mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` per PRD FR36b L1554 + ADR-016 §Decision L24-28 — 3-state value space (NO `"none"` value).

**Runtime Literal closed-set validation in `__post_init__` (Story 1b.4 code-review D7 ratification — pre-edit text mentioned a "defensive `dict()` copy" but the dataclass has only Literal string fields, nothing dict-shaped to copy; the actual `__post_init__` purpose ratified at code review is runtime validation that raises `ValueError` on out-of-set inputs).** Python `Literal` types are TYPE-CHECK-only — mypy catches violations at type-check time but the runtime constructor accepts any string. The `__post_init__` adds a closed-set check so jsonl-replay paths + adapter-side construction get the same guarantee mypy provides. Both fields are REQUIRED per ADR-006 + ADR-016 — no Optional, no defaults.

### AC-1b.4.7 — `UnsupportedBinaryVersionError` leaf + `_assert_binary_version` helper

**And** `src/AgentEval/errors.py` is extended with the `UnsupportedBinaryVersionError(AgentEvalCompatError)` leaf with `error_code: ClassVar[str] = "UNSUPPORTED_BINARY_VERSION"`. Module docstring's "remaining 6 leaves" future-list retires `UnsupportedBinaryVersionError` (now 5 remaining future leaves). `__all__` adds the new leaf.

`_assert_binary_version` helper on `SubprocessAdapter`:

```python
def _assert_binary_version(self, binary: str, min: str, max: str | None) -> None:
```

Validates the binary's `--version` output (or equivalent; subclasses may override the version-extraction helper if their CLI uses a different invocation). Composes `<range>` as `f">={min}, <{max}"` when both bounds set, or `f">={min}"` when `max=None`. On mismatch raises `UnsupportedBinaryVersionError` with FR47-EXACT message format:

```
"<binary> version <X> outside tested range <range>"
```

where `<X>` is the detected version. No raise for in-range version.

### AC-1b.4.8 — `coding_agent/__init__.py` re-exports

**And** `src/AgentEval/coding_agent/__init__.py` re-exports the 4 contributor-facing names: `CodingAgentAdapter` (from `AgentEval.types`), `InProcessAdapter` (from `AgentEval.coding_agent.base`), `SubprocessAdapter` (from `AgentEval.coding_agent.base`), `AgentRunResult` (from `AgentEval.types`). Public docstring lists the documented import paths. `__all__` exposes the 4 names.

### AC-1b.4.9 — `_kernel/discovery.py` integration: TYPE_CHECKING forward-ref resolves cleanly

**And** the Story 1b.3 `_kernel/discovery.py` L102 TYPE_CHECKING forward-ref `from AgentEval.types import CodingAgentAdapter` continues to resolve correctly after Story 1b.4 lands the actual Protocol. The pre-edit `type: ignore[attr-defined]` comment on Story 1b.3 discovery.py L102 is REMOVED in Story 1b.4 since the symbol is now resolvable. `uv run mypy src/` remains clean.

### AC-1b.4.10 — Unit-test coverage (`tests/unit/coding_agent/test_base.py`, ~25+ tests)

**And** unit tests in `tests/unit/coding_agent/test_base.py` (new test directory) cover:

- **Protocol structural typing** — a stub class with the right `run()`/`name`/`version` signatures conforms (verified via `typing.runtime_checkable` `isinstance`); a missing-method stub does NOT pass `isinstance`.
- **`runtime_checkable` semantics** — `isinstance(stub_with_run_name_version, CodingAgentAdapter) == True`.
- **`InProcessAdapter` direct instantiation** — subclass override of `run()` returns a valid `AgentRunResult`. Base class methods don't `@abstractmethod`-raise. Default `name`/`version` properties resolve via `type(self).__name__` + `importlib.metadata.version()` fallback.
- **`SubprocessAdapter` abstract enforcement** — direct instantiation FAILS with `TypeError` (3 abstract methods un-implemented); subclass implementing all 3 `@abstractmethod` hooks + inheriting the template-method `run()` succeeds.
- **`SubprocessAdapter.run()` template-method orchestration** — a fake subclass with deterministic `_spawn` (returns a `Popen`-shaped mock with iterable stdout) + `_parse_event` (returns ParsedEvent for valid lines, None for skipped lines) + `_finalize` (returns a fixed `AgentRunResult`) produces the expected output. `_parse_event` returning None correctly skips the line.
- **`_assert_binary_version`** raises `UnsupportedBinaryVersionError` with FR47-exact format for: version below `min` / version above `max` (when set) / unparseable version string. Does NOT raise for in-range version. Composed `<range>` matches `">={min}, <{max}"` when both bounds set, `">={min}"` when `max=None`.
- **`AgentRunResult` construction** — all 7 fields populated, defensive copy on `metadata` sub-dataclass `__post_init__` (mirroring Story 1b.2's pattern: mutating the source dict does NOT leak into the frozen dataclass; `dataclasses.asdict()` round-trips correctly for jsonl serialization).
- **`AgentRunMetadata` Literal enforcement** — invalid values raise `TypeError` (or mypy-flagged at type level — verified via doctest or conventions/ test if infra is ready).
- **Re-export path identity** — `from AgentEval.coding_agent import CodingAgentAdapter` IS `from AgentEval.types import CodingAgentAdapter`. Same for `AgentRunResult`.
- **`_kernel/discovery.py` integration smoke** — `discover_adapters()` returns a `dict[str, type[CodingAgentAdapter]]`; mypy verifies the type hint resolves; runtime `isinstance(next(iter(...)), CodingAgentAdapter)` works for an instance of a registered adapter (via a `register_adapter("test", StubAdapter)` + `get_adapter("test")(...)` round-trip).
- **`UnsupportedBinaryVersionError` hierarchy** — inherits `AgentEvalCompatError` + `AgentEvalError`; `error_code == "UNSUPPORTED_BINARY_VERSION"`; `__str__` formatter from H_R7 yields `"UNSUPPORTED_BINARY_VERSION: <message>"`; `try/except AgentEvalError` catches it.

### AC-1b.4.11 — All-gates pass

**And**:

- `uv run ruff check src/ tests/` clean.
- `uv run ruff format --check src/ tests/` clean.
- `uv run mypy src/` clean (31 source files: Story 1b.3's 30 + new `src/AgentEval/coding_agent/base.py`).
- `uv run python scripts/check-license-headers.py` PASS.
- `uv run pytest tests/unit -q --ignore=tests/unit/conventions` — 220 prior + ~25 new Story 1b.4 tests = ~245+ pass.
- `uv run pytest tests/acceptance/tier1 -q` — Story 1a.6's 6 FR42 tests still pass (regression).
- `uv run robot tests/acceptance/smoke` — RF smoke test still passes (regression).

### AC-1b.4.12 — Project norms applied

**And**:

- Code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)` per `feedback_review_methodology_norms` (8th consecutive use of the cross-LLM adversarial pattern).
- Cross-LLM reviewer prompt MUST direct re-derivation of every cited fact from source per `feedback_citation_drift_first_class` (Story 1b.3 code review demonstrated the 9th consecutive cross-LLM STAR-catch — pattern is load-bearing).
- Honest framing: Phase-1 limitations explicitly documented in module docstrings + this story Dev Notes — (1) sandbox routing through `scenarios/` + `security/policy.py` NOT through adapters (architecture L1523); (2) FR17b `coding_agent=` kwarg on `AgentEval.__init__` deferred to Story 4.1; (3) `ParsedEvent` is `TypeAlias = Any` in Story 1b.4 — concrete adapters declare per-adapter intermediate types in Epic 4/11; (4) `trace_id: str` Phase-1 UUID hex contract; Phase-2 OTLP migration may switch to OTel 32-char hex.

## Tasks / Subtasks

- [x] **Task 1: Extend `src/AgentEval/types.py` with Protocol + AgentRunResult + AgentRunMetadata (AC: 1b.4.1, 1b.4.5, 1b.4.6)**
  - [x] Imports: `from typing import Protocol, runtime_checkable, Literal, Any, TYPE_CHECKING`; `from dataclasses import dataclass, field`. Forward-ref `ServerHandle` from `AgentEval._kernel.context` (TYPE_CHECKING only — runtime accepts the dict shape).
  - [x] `AgentRunMetadata` `@dataclass(frozen=True)` with `completeness: Literal["complete", "truncated", "partial"]` + `mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]`. Defensive `__post_init__` copying any mutable source per Story 1b.2 M_R6 pattern.
  - [x] `AgentRunResult` `@dataclass(frozen=True)` with the 7 fields per AC-1b.4.5. Defensive copy on `tool_calls` (list of frozen dataclasses; defensive `list(...)` wrap is sufficient).
  - [x] `CodingAgentAdapter` `@runtime_checkable Protocol` with the single `run()` method signature per AC-1b.4.1 + `name` / `version` `@property` declarations.
  - [x] Update module docstring's "Subsequent stories ADD types" list: retire `AgentRunResult`/`ToolCall`/`TokenUsage`/`Scenario`/`MCPServer`/`RawResponse` Story-1b.4 forward-ref mentions (Story 1b.4 ships `AgentRunResult` + `AgentRunMetadata` + `CodingAgentAdapter`; the others were undefined drift now resolved).
  - [x] `__all__` extends with: `"CodingAgentAdapter"`, `"AgentRunResult"`, `"AgentRunMetadata"`.

- [x] **Task 2: Extend `src/AgentEval/errors.py` with `UnsupportedBinaryVersionError` leaf (AC: 1b.4.7)**
  - [x] `class UnsupportedBinaryVersionError(AgentEvalCompatError):` with `error_code: ClassVar[str] = "UNSUPPORTED_BINARY_VERSION"`. Docstring cites FR47 + contract L81 (Story 1b.4 declaration + Epic 4/11 raise sites).
  - [x] `__all__` extends with `"UnsupportedBinaryVersionError"` under the existing leaves section.
  - [x] Module docstring's "remaining 6 leaves" future-list retires `UnsupportedBinaryVersionError` (now 5 remaining: `PollingDisallowedError`, `UnsupportedMCPVersionError`, `TierViolationError`, `ValidateOperatorDisallowed`, `AdapterVersionDriftWarning`). Verify count matches list. Bullet for `UnsupportedBinaryVersionError` removed from the future-list AND moved to the "implemented leaves" section above.

- [x] **Task 3: Author `src/AgentEval/coding_agent/base.py` (~250L) with re-export + ABCs (AC: 1b.4.2, 1b.4.3, 1b.4.4)**
  - [x] Apache 2.0 license header.
  - [x] Module docstring citing ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-split.md`) L22-29 + architecture L1226-1228 + PRD FR12 + Story 1b.3 `_kernel/discovery.py` integration.
  - [x] Re-export: `from AgentEval.types import CodingAgentAdapter as CodingAgentAdapter` + `from AgentEval.types import AgentRunResult as AgentRunResult`.
  - [x] `ParsedEvent: TypeAlias = Any` (Story 1b.4 placeholder; Epic 4/11 concrete adapters declare per-adapter intermediate types).
  - [x] `class InProcessAdapter:` (concrete-by-default, NO ABC inheritance, NO `@abstractmethod`):
    - `__init__(self, **kwargs: Any) -> None` capturing `self._adapter_config: dict[str, Any] = dict(kwargs)`.
    - `@property name(self) -> str` default returning `type(self).__name__`.
    - `@property version(self) -> str` default reading `importlib.metadata.version(type(self).__module__.split('.')[0])` with `"unknown"` fallback on `PackageNotFoundError`.
    - No `run()` implementation — subclasses MUST override `run()`. Document the contract in the class docstring.
  - [x] `class SubprocessAdapter(ABC):` (3-hook template-method per ADR-003 L24-29):
    - `__init__(self, **kwargs: Any) -> None` capturing `self._adapter_config: dict[str, Any] = dict(kwargs)`.
    - `@abstractmethod _spawn(self, prompt: str, **kwargs: Any) -> subprocess.Popen[str]`.
    - `@abstractmethod _parse_event(self, line: str) -> ParsedEvent | None`.
    - `@abstractmethod _finalize(self, events: list[ParsedEvent], exit_code: int) -> AgentRunResult`.
    - Concrete `run(self, prompt, tools=None, mcp_servers=None, **kwargs) -> AgentRunResult` orchestrating: call `_spawn` → iterate `proc.stdout` line-by-line through `_parse_event` (collecting non-None into `events`) → `proc.wait()` → `_finalize(events, proc.returncode)`. Wraps the whole sequence in try/finally that ensures `proc.terminate()` on exception (process-group hygiene per Story 1b.1 MCPLifecycleManager precedent).
    - Concrete `_assert_binary_version(self, binary: str, min: str, max: str | None) -> None` helper. Calls `subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5)`. Parses version via regex `r"(\d+\.\d+(?:\.\d+)?)"` (semver-ish). Composes `<range>` per AC-1b.4.7. Raises `UnsupportedBinaryVersionError` with FR47-exact message. Subclasses MAY override the version-extraction helper if their CLI uses a different invocation pattern.
    - Default `name` / `version` properties same as `InProcessAdapter`.
  - [x] `__all__` exports: `["CodingAgentAdapter", "InProcessAdapter", "SubprocessAdapter", "AgentRunResult", "ParsedEvent"]`.

- [x] **Task 4: Update `src/AgentEval/coding_agent/__init__.py` re-exports (AC: 1b.4.8)**
  - [x] Re-export 4 contributor-facing names: `CodingAgentAdapter` (from `AgentEval.types`), `InProcessAdapter`, `SubprocessAdapter`, `AgentRunResult` (from `AgentEval.types`).
  - [x] `__all__ = ["CodingAgentAdapter", "InProcessAdapter", "SubprocessAdapter", "AgentRunResult"]`.
  - [x] Module docstring lists the documented public-import paths.

- [x] **Task 5: Remove `# type: ignore[attr-defined]` from `_kernel/discovery.py` L102 (AC: 1b.4.9)**
  - [x] After Task 1 lands the Protocol in `AgentEval.types`, the discovery.py forward-ref `from AgentEval.types import CodingAgentAdapter` resolves cleanly.
  - [x] Remove the `# type: ignore[attr-defined]  # forward ref; lands in Story 1b.4` comment.
  - [x] Verify with `uv run mypy src/AgentEval/_kernel/discovery.py`.

- [x] **Task 6: Author `tests/unit/coding_agent/test_base.py` (~280L, ~25 tests) (AC: 1b.4.10)**
  - [x] Test file's Apache 2.0 license header.
  - [x] Import `pytest`, `subprocess`, `dataclasses.asdict`, the Story 1b.4 Protocol/ABCs/types/errors, Story 1b.2's `ToolCallTrace`/`Usage`.
  - [x] Create test directory `tests/unit/coding_agent/` with `__init__.py`.
  - [x] Test categories:
    - Protocol structural typing (~3 tests).
    - InProcessAdapter direct-override + default properties (~4 tests).
    - SubprocessAdapter abstract enforcement + template-method orchestration (~6 tests, including `_parse_event` returning None to skip lines + termination-on-exception cleanup).
    - `_assert_binary_version` (~5 tests: in-range / below min / above max / max=None / unparseable + FR47-exact format).
    - AgentRunResult + AgentRunMetadata construction + frozen + defensive copy + `asdict` round-trip (~3 tests).
    - Re-export identity (~2 tests).
    - `_kernel/discovery.py` integration smoke (~1 test).
    - `UnsupportedBinaryVersionError` hierarchy + `error_code` + `__str__` (~2 tests).

- [x] **Task 7: All-gates pass (AC: 1b.4.11)**
  - [x] `uv run ruff check src/ tests/` clean.
  - [x] `uv run ruff format --check src/ tests/` clean.
  - [x] `uv run mypy src/` clean (31 source files).
  - [x] `uv run python scripts/check-license-headers.py` PASS.
  - [x] `uv run pytest tests/unit -q --ignore=tests/unit/conventions` — all tests pass (220 prior + ~25 new = ~245+).
  - [x] `uv run pytest tests/acceptance/tier1 -q` — 6 FR42 tests still pass.
  - [x] `uv run robot tests/acceptance/smoke` — RF smoke test still passes.

- [x] **Task 8: Update `docs/contracts/stability-surface.md` (AC: 1b.4.2, 1b.4.5)**
  - [x] Add new section "Coding Agent Adapter Surface (Story 1b.4)" registering `CodingAgentAdapter` Protocol (`provisional`); `InProcessAdapter` ABC (`provisional`); `SubprocessAdapter` ABC + 3 hooks `_spawn`/`_parse_event`/`_finalize` (`provisional`); `_assert_binary_version` helper (`provisional`); `AgentRunResult` dataclass + 7 fields (`provisional`); `AgentRunMetadata` sub-dataclass + 2 fields (`provisional`); `agenteval.coding_agents` entry-points group (`stable` — already registered by Story 1a.4 sandbox surface section).
  - [x] Extend "Top-level errors + types surface" section: add `UnsupportedBinaryVersionError` leaf (`stable`); add `AgentRunResult` + `AgentRunMetadata` dataclasses (`provisional`).

- [x] **Task 9: Apply project norms (AC: 1b.4.12)**
  - [x] Code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)` per `feedback_review_methodology_norms`.
  - [x] Cross-LLM reviewer prompt MUST direct re-derivation of every cited fact from source per `feedback_citation_drift_first_class`.
  - [x] Honest framing: Phase-1 limitations documented per AC-1b.4.12.

### Review Findings (2026-05-19 cross-LLM adversarial — 4 reviewers: Blind Hunter + Edge Case Hunter + Acceptance Auditor + Codex CLI gpt-5.4)

**Raw findings:** 32 Blind + 21 Edge + 12 Auditor + 12 Codex = **77 raw** → **31 unique** after dedup (4 decision-needed bundles resolved into 13 patches + 13 direct patches + 8 deferred + ~10 dismissed as dedup-overlap or convention).

**STAR catches (10th consecutive cross-LLM review with Codex finding what 3 Claude reviewers missed):**
- (Codex unique HIGH) ADR-003 L30 base-class lifecycle ownership violation: ADR-003 verbatim "The base class owns subprocess lifecycle: signal handling, timeout enforcement, stderr capture, exit-code mapping, truncation detection" — impl ships only stdout iteration + wait + raw exit_code.
- (Codex unique MED) `version` property uses module name (`AgentEval`) not distribution name (`robotframework-agenteval`) → always falls back to `"unknown"` for in-tree adapters.
- (Codex unique LOW) `AgentEvalCompatError` docstring still says `UnsupportedBinaryVersionError` is "not yet implemented" after Story 1b.4 lands it.

**4-WAY confirmed HIGH:** Process-group hygiene drift — `proc.terminate()` kills leader only, not the process group; contradicts the docstring promise + cited Story 1b.1 `os.killpg(pid, SIGTERM)` precedent.

**3-WAY confirmed HIGH:**
- `_parse_version_tuple` short-tuple ordering bug — `(1,0) < (1,0,0)` is True; `"1.0" vs "1.0.0"` boundary broken.
- `runtime_checkable` Protocol overclaims signature validation — only checks attribute presence; tests pass stubs with wrong-shape `run()`.
- FR47 vs H_R7 message format drift — H_R7 prefix `"UNSUPPORTED_BINARY_VERSION: ..."` doesn't match FR47-exact format.

**Decisions resolved (all 4 bundles Recommended):**

- [x] [Review][Decision→Patch] D1+D2 Subprocess lifecycle (4-WAY HIGH + Codex STAR HIGH) — Implement `os.killpg(os.getpgid(pid), SIGTERM)` + `proc.wait(timeout=5)` + `proc.kill()` escalation per Story 1b.1 precedent; amend ADR-003 L30 to mark stderr-capture + timeout-enforcement + truncation-detection as Phase-2 carry-over.
- [x] [Review][Decision→Patch] D3+D5 Version handling (3-WAY HIGH + Codex STAR MED) — Pad `_parse_version_tuple` results to fixed-arity 3 + reject prerelease via explicit pre-validation; use `importlib.metadata.packages_distributions()` for distribution-name resolution with fallback to module-name lookup.
- [x] [Review][Decision→Patch] D4+D6 Protocol + FR47 contract clarity (3-WAY HIGH) — Amend `CodingAgentAdapter` Protocol docstring to clarify `runtime_checkable` only verifies attribute presence (Story 1b.5 conformance harness owns signature-shape validation); override `__str__` on `UnsupportedBinaryVersionError` to skip H_R7 prefix (FR47-exact `str(exc)`).
- [x] [Review][Decision→Patch] D7 Runtime validation (3-WAY MED + Codex MED + LOW) — Add `__post_init__` Literal closed-set validation to `AgentRunMetadata`; expose structured attrs (`binary` / `detected` / `min_version` / `max_version`) on `UnsupportedBinaryVersionError`; relax `trace_id` docs to unconstrained `str` (Phase-2 OTLP may add UUID validation).

**Direct patches (13 unchecked):**

- [x] [Review][Patch] P1 `assert proc.stdout is not None` → explicit `if proc.stdout is None: raise TypeError(...)` (Python -O strips asserts) [src/AgentEval/coding_agent/base.py SubprocessAdapter.run]
- [x] [Review][Patch] P2 stderr fd leak — proc.stderr=PIPE never closed on success path; add `proc.stdout.close()` + `proc.stderr.close()` in finally [src/AgentEval/coding_agent/base.py SubprocessAdapter.run]
- [x] [Review][Patch] P3 `_default_version` broaden exception catch from `PackageNotFoundError` only to `(PackageNotFoundError, OSError, KeyError)` [src/AgentEval/coding_agent/base.py:_default_version]
- [x] [Review][Patch] P4 `_assert_binary_version` doesn't check `result.returncode`; add returncode check + non-zero raise [src/AgentEval/coding_agent/base.py:_assert_binary_version]
- [x] [Review][Patch] P5 PermissionError + general OSError on subprocess.run not caught (only FileNotFoundError + TimeoutExpired); broaden tuple [src/AgentEval/coding_agent/base.py:_assert_binary_version]
- [x] [Review][Patch] P6 `mcp_servers` type widening — Protocol says `dict[str, ServerHandle]`, base says `dict[str, Any]`; align both to `dict[str, ServerHandle]` via TYPE_CHECKING import [src/AgentEval/coding_agent/base.py:SubprocessAdapter.run]
- [x] [Review][Patch] P7 `coding_agent/__init__.py` docstring drift: calls `InProcessAdapter` an "ABC for SDK-driven adapters" but ADR-003 + impl say "base class (concrete-by-default)" [src/AgentEval/coding_agent/__init__.py:25]
- [x] [Review][Patch] P8 `AgentEvalCompatError` docstring still says `UnsupportedBinaryVersionError` is "not yet implemented" (Codex LOW catch); update to "implemented in Story 1b.4; per-adapter raise sites in Epic 4/11" [src/AgentEval/errors.py:AgentEvalCompatError]
- [x] [Review][Patch] P9 Spec AC-1b.4.6 stale `__post_init__` defensive-copy claim for AgentRunMetadata — when D7 patch lands runtime Literal validation in __post_init__, update AC text to reflect actual purpose [spec AC-1b.4.6]
- [x] [Review][Patch] P10 New test: `_parse_version_tuple` short-tuple + prerelease boundary cases [tests/unit/coding_agent/test_base.py]
- [x] [Review][Patch] P11 New test: `version` property uses distribution name (not module name) — assert in-tree adapter resolves to `robotframework-agenteval` version [tests/unit/coding_agent/test_base.py]
- [x] [Review][Patch] P12 New test: AgentRunMetadata invalid-Literal raises ValueError + UnsupportedBinaryVersionError structured attrs accessible [tests/unit/coding_agent/test_base.py + tests/unit/test_errors.py]
- [x] [Review][Patch] P13 New test: process-group SIGTERM cleanup path (mock `os.killpg`); update `test_subprocess_adapter_run_terminates_proc_on_exception` to assert killpg called [tests/unit/coding_agent/test_base.py]

**Deferred (8):**

- [x] [Review][Defer] DF1 Async-safety of `_assert_binary_version` — calls blocking `subprocess.run` synchronously; OK in Phase-1 (called at adapter init), but Story 4.1 should wrap in `asyncio.to_thread` for async callers
- [x] [Review][Defer] DF2 `_default_version` namespace-package edge case — concrete adapters in Epic 4/11 will explicitly override `version`; Phase-1 fallback acceptable
- [x] [Review][Defer] DF3 Real-Popen integration test — covered by Story 1b.5 conformance harness (signature-shape + behavioral fixtures)
- [x] [Review][Defer] DF4 Long-stdout / unbounded-events memory test — Phase-1.5 robustness pass; Story 4.2 CLI adapter will be the first real consumer
- [x] [Review][Defer] DF5 Cancellation-mid-stream test — Story 4.1 wires real provider-client cancellation; Story 1b.4 ships only the cleanup-on-exception path
- [x] [Review][Defer] DF6 Test factory-fixture refactor (`conftest.py` for `tool_call_trace_factory` etc.) — cosmetic; Story 1b.5 conformance fixtures may absorb
- [x] [Review][Defer] DF7 `architecture.md` L1226-1228 split-file scheme annotation (`subprocess.py` vs `base.py` consolidation per Story 1b.4 D8) — defer to Epic 1b retrospective doc-cleanup pass
- [x] [Review][Defer] DF8 `_kernel/coverage.py` L55 `type: ignore` cleanup scope-creep documentation in Story 1b.4 File List — already in File List, no further action needed

**Dismissed (~10):**

- Codex L1 `test_base.py` missing Apache 2.0 header — license-headers script docstring explicitly scopes to `src/AgentEval/`; tests intentionally exempt per project convention. No fix needed.
- Blind F19 `min`/`max` shadowing Python builtins — spec AC-1b.4.7 explicitly uses this signature; ruff A002 not enabled; minor style only.
- Blind F29-F30 size estimates off + File List duplication — cosmetic, already in spec.
- Edge various dedupes absorbed by D1+D2 cluster (terminate timeout, stderr close).
- Blind F25 ToolCallTrace coupling — covered by Story 1b.2 baseline; Story 1b.5 conformance fixtures will own.
- Auditor F8 runtime_checkable overstated — covered by D4 patch.
- Blind F31 Protocol attr vs @property LSP-substitution — superseded by D4 docstring clarification.

**Cross-LLM dedup pattern continues:** 10th consecutive review where Codex's citation re-derivation caught structural drift the 3 Claude reviewers missed (ADR-003 L30 lifecycle ownership; distribution-name vs module-name; AgentEvalCompatError stale "not yet implemented"). The norm is load-bearing.

## Dev Notes

### Project context — Story 1b.4's place in Epic 1b

Story 1b.4 is the 4th Epic 1b foundational kernel story. Dependencies:

- **Story 1b.1** `_kernel/{context, tier, run_async}.py` — provides `ServerHandle` (consumed by `run()` mcp_servers kwarg) + `_run_async` (used by InProcessAdapter subclasses calling async SDKs) + `@tier(3)` decorator (used by future library keywords, NOT by adapters per D11).
- **Story 1b.2** `src/AgentEval/types.py` (`ToolCallTrace` + `Usage` + `RunManifest`) + `src/AgentEval/errors.py` (`AgentEvalError` + `AgentEvalIntegrityError` + `IncompleteTraceError` + `DegradedTraceWarning`). Story 1b.4 EXTENDS both files.
- **Story 1b.3** `src/AgentEval/errors.py` (`AgentEvalBudgetError` + `AgentEvalCompatError` + `CostExceededError` + `RuntimeBudgetExceededError` + `AdapterDiscoveryError` + `DuplicateRegistrationError`). Story 1b.4 ADDS `UnsupportedBinaryVersionError(AgentEvalCompatError)` leaf — pure extension.
- **Story 1b.3** `_kernel/discovery.py` TYPE_CHECKING forward-ref `from AgentEval.types import CodingAgentAdapter`. Story 1b.4 RESOLVES this by landing the actual Protocol class.

Story 1b.4 ENABLES:

- **Story 1b.5** (Conformance harness) — fixtures consume `AgentRunResult` shape + `CodingAgentAdapter` Protocol for round-trip tests.
- **Story 1b.6** (Determinism Contract + conventions) — owns `KeywordTierMissingError` enforcer per Story 1b.3's D7 decision; conventions tests verify `@tier(3)` on keyword methods (NOT on adapter classes per Story 1b.4's D11).
- **Epic 4 Story 4.1** (Generic LiteLLM adapter) — first concrete `InProcessAdapter` subclass. Wires the FR17b `coding_agent=` kwarg on `AgentEval.__init__`.
- **Epic 4 Story 4.2** (Claude Code CLI adapter) — first concrete `SubprocessAdapter` subclass. First per-adapter `UnsupportedBinaryVersionError` raise site (validates the FR47 contract end-to-end).
- **Epic 10 Stories 10.x** (Claude Agent SDK + OpenAI Agents SDK) — 2 more `InProcessAdapter` subclasses.
- **Epic 11 Stories 11.x** (Codex CLI + Copilot CLI) — 2 more `SubprocessAdapter` subclasses. Closes the Tier-1 adapter set under ADR-005's "≤2 per vendor + 1 universal" rule. `AdapterVersionDriftWarning` (Epic 11 Story 11.3) goes fully wired once ≥2 Tier-1 CLI adapters ship.

### Architecture compliance

| Architecture reference | Story 1b.4 implementation |
|---|---|
| L620 — `@tier(N)` decorator sets `_agenteval_tier` on wrapped method | Honored: tier semantics on KEYWORD methods, NOT on adapter classes (D11 ratification) |
| L853 — Cross-sub-library imports go through `agenteval/types.py` ONLY | Honored: `CodingAgentAdapter` Protocol declared in `types.py`; `coding_agent/base.py` re-exports |
| L885 — `AgentRunResult` example with `tool_calls: list[ToolCallTrace]` + `usage: Usage` | Honored verbatim: same field names + same type references |
| L967 — `Usage` per architecture's `gen_ai.usage.*` summing convention | Honored: reuse Story 1b.2's `Usage` dataclass |
| L1226 — `base.py # CodingAgentAdapter Protocol + AgentRunResult shape (uses types.py)` | Amended pre-authoring: Protocol DECLARATION in `types.py`; `base.py` re-exports + lands ABCs. epics.md L981 update reflects this. |
| L1228 — `SubprocessAdapter ABC (CLI adapters with _spawn / _parse_event / _finalize hooks)` | Honored verbatim: 3 abstract hooks with exactly those names |
| L1523 — Sandbox routes through `scenarios/` + `security/policy.py` | Honored: sandbox OUT-OF-SCOPE for adapters |
| ADR-003 L22-23 InProcessAdapter direct-override pattern | Honored: NO abstract hooks; subclasses override `run()` directly |
| ADR-003 L24-29 SubprocessAdapter 3-hook template-method | Honored verbatim: `_spawn` / `_parse_event` / `_finalize` abstract |
| ADR-006 L15 `.metadata.completeness` REQUIRED nested | Honored: `AgentRunMetadata` sub-dataclass with REQUIRED 3-state Literal |
| ADR-016 §Decision L24-28 `mcp_coverage` 3-state value space | Honored: `Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` |
| PRD FR12 L1506 single `run(prompt, tools, mcp_servers, **kwargs)` Protocol method | Honored: single method (D1 ratification) |
| PRD FR36a L1553 `completeness` 3-state Literal | Honored verbatim |
| PRD FR36b L1554 `mcp_coverage` 3-state Literal | Honored verbatim |
| PRD FR47 `<binary> version <X> outside tested range <range>` error format | Honored: enforced by `_assert_binary_version` + AC-1b.4.7 |
| PRD FR51 L1579 `trace_id=<uuid>` | Honored: Phase-1 UUID hex string; Phase-2 OTel-hex migration documented |
| `docs/contracts/error-class-hierarchy.md` L81 `UnsupportedBinaryVersionError` Epic 4+11 ownership | Amended pre-authoring: Class declaration in Story 1b.4; per-adapter raise sites in Epic 4 + Epic 11 |

### Phase-1 limitations explicitly documented

- **Sandbox integration OUT-OF-SCOPE for adapters** per architecture L1523. Sandbox routes through `scenarios/` + `security/policy.py` (Story 1a.6 baseline). Adapters do NOT directly invoke sandboxed code; scenarios that need sandbox-execution semantics call the sandbox layer separately.
- **FR17b `coding_agent=` kwarg on `AgentEval.__init__` deferred to Story 4.1** (Generic LiteLLM adapter). Until then, custom adapters register via entry-points (FR17a) or via `register_adapter()` programmatic path (Story 1b.3). Story 1b.4 dev notes carry a forward-ref pointer; Story 4.1 will extend `AgentEval.__init__` to accept `coding_agent: CodingAgentAdapter | None = None`.
- **`ParsedEvent: TypeAlias = Any`** in Story 1b.4 base.py. Concrete CLI adapters (Epic 4 Story 4.2 / Epic 11 Stories 11.x) declare their own concrete intermediate event types (`ClaudeCodeEvent`, `CodexEvent`, `CopilotEvent`) per the architecture L1228 per-adapter pattern.
- **`trace_id: str` Phase-1 UUID hex contract.** Phase-2 OTLP migration may switch to OTel 32-char hex per the OTel semconv (tracked as a Phase-2 carry-over in `deferred-work.md` if it becomes load-bearing).
- **`_assert_binary_version` regex-based version parsing.** The helper uses a semver-ish regex `r"(\d+\.\d+(?:\.\d+)?)"` on the `<binary> --version` stdout. CLIs with non-standard version-output formats (e.g., `npm-style "Claude Code 1.0.9 (build abc)"`) work because the regex captures the first `MAJOR.MINOR[.PATCH]` substring. Subclasses MAY override `_assert_binary_version` (or a future Story-1b.4-extension `_extract_binary_version(stdout: str) -> str` helper) if their CLI doesn't fit the default pattern.

### Story 1b.3 integration — `_kernel/discovery.py` forward-ref resolution

Story 1b.3's `_kernel/discovery.py` at L102 declares:

```python
if TYPE_CHECKING:
    from AgentEval.types import CodingAgentAdapter  # type: ignore[attr-defined]  # forward ref; lands in Story 1b.4
```

Story 1b.4 lands the actual Protocol in `types.py`, after which the `type: ignore` comment is REMOVED. `uv run mypy src/AgentEval/_kernel/discovery.py` continues to pass.

The discovery API's `discover_adapters() -> dict[str, type[CodingAgentAdapter]]` now resolves to a concrete Protocol shape. Test fixtures in `test_discovery.py` already pass duck-typed stubs (`_StubAdapter`, `WeirdShape`) — those continue to work because the Protocol uses `runtime_checkable` and the actual `isinstance` checks in production code paths flow through `register_adapter` (which Story 1b.3 left as `isinstance(cls, type)` — no Protocol check, intentional for the "duck-typed-until-1b.4" period).

**Story 1b.5 conformance harness** (next story) will introduce the explicit Protocol-conformance test fixtures.

### Story 1b.2 integration — types.py extension pattern

Story 1b.2 ships `types.py` with 3 dataclasses (`ToolCallTrace`, `Usage`, `RunManifest`). Story 1b.4 ADDS:

- `CodingAgentAdapter` Protocol class.
- `AgentRunResult` `@dataclass(frozen=True)`.
- `AgentRunMetadata` `@dataclass(frozen=True)`.

Pure addition; no refactor of Story 1b.2's classes. The defensive `dict()` copy in `__post_init__` pattern from Story 1b.2's M_R6 fix is applied to `AgentRunResult` (defensive `list(tool_calls)` wrap) + `AgentRunMetadata` (Literal fields are immutable values, but the metadata dict source if any external code passes one needs the copy).

### Story 1b.3 integration — errors.py extension pattern

Story 1b.3 ships `errors.py` with 2 sub-bases (`AgentEvalBudgetError`, `AgentEvalCompatError`) + 4 leaves (`CostExceededError`, `RuntimeBudgetExceededError`, `AdapterDiscoveryError`, `DuplicateRegistrationError`). Story 1b.4 ADDS:

- `UnsupportedBinaryVersionError(AgentEvalCompatError)` leaf with `error_code: ClassVar[str] = "UNSUPPORTED_BINARY_VERSION"`.

Pure addition. The H_R7 `__str__` formatter is inherited. The module docstring's "remaining 6 leaves" future-list (already 6 after Story 1b.3 retired 3) decrements to 5: `PollingDisallowedError`, `UnsupportedMCPVersionError`, `TierViolationError`, `ValidateOperatorDisallowed`, `AdapterVersionDriftWarning`. (Note: SandboxRequiredError stays in its own Phase-1.5-carry-over paragraph per Story 1b.3 code-review fix.)

### Project norms applied

1. **Norm #1 (cross-LLM adversarial review)** — `/bmad-code-review (Using current Claude + Codex CLI subagent)` per Epic 0 retro Norm #1.
2. **Norm #4 (pre-create-story drift check)** — 8th consecutive use. 14 drifts caught + resolved pre-authoring. Top recommendation honored: path-of-least-amendment to honor ratified sources.
3. **Norm #5 (citation-drift first-class)** — applied to AC-1b.4.12 directive for code-review time. Story 1b.3's review demonstrated the 9th consecutive STAR-catch.
4. **Honest framing** — Phase-1 limitations explicitly documented (sandbox out-of-scope; FR17b deferred; ParsedEvent TypeAlias; trace_id UUID hex; regex-based version parsing).
5. **agentguard inspiration-only** — ratified; no agentguard dependency in Protocol or ABCs.

### References

- **PRD §FR12** (`_bmad-output/planning-artifacts/prd.md` L1506) — `CodingAgentAdapter` Protocol single `run()` method
- **PRD §FR17b** — Programmatic `coding_agent=` kwarg composition path (deferred to Story 4.1)
- **PRD §FR36a** (prd.md L1553) — `completeness` Literal 3-state value space
- **PRD §FR36b** (prd.md L1554) — `mcp_coverage` Literal 3-state value space
- **PRD §FR47** — `<binary> version <X> outside tested range <range>` error message format
- **PRD §FR51** (prd.md L1579) — `trace_id=<uuid>` RF report-line attribute
- **ADR-003** (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-split.md`) — Protocol + InProcessAdapter direct-override + SubprocessAdapter 3-hook template
- **ADR-006** (`docs/adr/ADR-006-agent-run-result-completeness-field.md`) — `.metadata.completeness` REQUIRED nesting
- **ADR-016** (`docs/adr/ADR-016-mcp-coverage-detection-default.md`) — `mcp_coverage` 3-state value space
- **Architecture L620** — `@tier(N)` decorator sets `_agenteval_tier` on wrapped methods
- **Architecture L853** — Cross-sub-library imports go through `agenteval/types.py` ONLY
- **Architecture L885-889** — `AgentRunResult` example with `tool_calls: list[ToolCallTrace]` + `usage: Usage`
- **Architecture L1226-1228** — `coding_agent/base.py` location + SubprocessAdapter hook names
- **Architecture L1523** — Sandbox routes through `scenarios/` + `security/policy.py`
- **docs/contracts/error-class-hierarchy.md L81** — `UnsupportedBinaryVersionError` ownership row (amended pre-authoring: Story 1b.4 declares + Epic 4 / Epic 11 raise sites)
- **Story 1b.1 `_kernel/{context, tier, run_async}.py`** — `ServerHandle` (consumed by `run()` mcp_servers) + `@tier(3)` decorator + `_run_async` async-to-sync bridge
- **Story 1b.2 `src/AgentEval/types.py`** — `ToolCallTrace` + `Usage` + `RunManifest` (Story 1b.4 ADDS `CodingAgentAdapter` + `AgentRunResult` + `AgentRunMetadata`)
- **Story 1b.2 `src/AgentEval/errors.py`** — base + H_R7 `__str__` formatter inherited by `UnsupportedBinaryVersionError`
- **Story 1b.3 `_kernel/discovery.py`** L102 — TYPE_CHECKING forward-ref `from AgentEval.types import CodingAgentAdapter` (Story 1b.4 resolves; `type: ignore` removed)
- **Story 1b.3 `src/AgentEval/errors.py`** — `AgentEvalCompatError` sub-base that `UnsupportedBinaryVersionError` extends
- **`feedback_citation_drift_first_class`** (memory) — applied via AC-1b.4.12 + 8th-consecutive create-story drift sweep

## Dev Agent Record

### Context Reference

- Story spec (this file).
- Architecture L853 (cross-sub-library import discipline) + L885-889 (`AgentRunResult` shape) + L1226-1228 (`coding_agent/base.py` location + SubprocessAdapter hooks) + L1523 (sandbox routes through scenarios/).
- ADR-003 (`docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-split.md`) — Protocol + InProcessAdapter direct-override + SubprocessAdapter 3-hook template.
- ADR-006 — `.metadata.completeness` REQUIRED nesting.
- ADR-016 — `mcp_coverage` 3-state value space.
- PRD FR12 (single `run()` method) + FR36a/b (Literal value spaces) + FR47 (error-message format) + FR51 (`trace_id=<uuid>`).
- `docs/contracts/error-class-hierarchy.md` L81 — `UnsupportedBinaryVersionError` ownership row (amended pre-authoring).
- Story 1b.1 `_kernel/{context, tier, run_async}.py` — `ServerHandle` consumed by `run()` mcp_servers + `@tier(3)` decorator pattern.
- Story 1b.2 `src/AgentEval/types.py` (`ToolCallTrace` + `Usage` + `RunManifest`) + `errors.py` (base + H_R7 `__str__` formatter inherited).
- Story 1b.3 `_kernel/discovery.py` L102 — TYPE_CHECKING forward-ref `from AgentEval.types import CodingAgentAdapter` (resolved by Story 1b.4; `type: ignore` removed).
- Story 1b.3 `src/AgentEval/errors.py` — `AgentEvalCompatError` sub-base that `UnsupportedBinaryVersionError` extends.

### Agent Model Used

Claude Opus 4.7 (1M context) — `claude-opus-4-7[1m]`.

### Debug Log References

None (all-gates clean on first full pass after ruff auto-fixes). Ruff applied 3 auto-fixes during the gate run: (1) removed unused `field` import that crept in via the types.py edit; (2) replaced `try/except/pass` with `contextlib.suppress(OSError, ProcessLookupError)` in `SubprocessAdapter.run()` cleanup path; (3) PEP-695 `type ParsedEvent = Any` (replacing `TypeAlias` form per project's adopted Story 1b.1 PEP-695 convention). Also caught + removed a now-resolvable `# type: ignore[attr-defined]` from `_kernel/coverage.py` L55 (Story 1b.2 forward-ref to `AgentRunResult` that Story 1b.4 lands).

### Completion Notes List

- Task 1 — `src/AgentEval/types.py` extended with `AgentRunMetadata` + `AgentRunResult` + `CodingAgentAdapter` Protocol. `AgentRunMetadata` is `@dataclass(frozen=True)` with 2 REQUIRED Literal fields per ADR-006 + ADR-016. `AgentRunResult` is `@dataclass(frozen=True)` with 7 fields including the `metadata: AgentRunMetadata` nested sub-dataclass per ADR-006 + FR36a/b; defensive `list()` copy on `tool_calls` in `__post_init__` per Story 1b.2 M_R6 pattern. `CodingAgentAdapter` Protocol uses `@runtime_checkable` for FR17b composition path; single `run(prompt, tools, mcp_servers, **kwargs)` method + `name`/`version` properties per FR12 L1506 (NOT 2-method per D1 ratification).
- Task 2 — `src/AgentEval/errors.py` extended with `UnsupportedBinaryVersionError(AgentEvalCompatError)` leaf. `error_code: ClassVar[str] = "UNSUPPORTED_BINARY_VERSION"`. `__all__` extended. Module docstring's "remaining 6 leaves" retired UnsupportedBinaryVersionError → now 5 leaves listed in the future-list (PollingDisallowedError, UnsupportedMCPVersionError, TierViolationError, ValidateOperatorDisallowed, AdapterVersionDriftWarning).
- Task 3 — `src/AgentEval/coding_agent/base.py` (~290L) authored: re-export `CodingAgentAdapter` + `AgentRunResult` from `AgentEval.types`; `type ParsedEvent = Any` (PEP-695 form); `_default_version()` + `_parse_version_tuple()` helpers; `_SEMVER_RE` regex; `InProcessAdapter` concrete-by-default base with `__init__` config-capture + default `name`/`version` properties + zero abstract methods per ADR-003 L22-23; `SubprocessAdapter(ABC)` with exactly 3 `@abstractmethod` hooks (`_spawn` / `_parse_event` / `_finalize`) + concrete template-method `run()` (orchestrates spawn → iterate `_parse_event` → `_finalize` with `contextlib.suppress(OSError, ProcessLookupError)`-guarded `proc.terminate()` cleanup-on-exception per Story 1b.1 process-group hygiene) + concrete `_assert_binary_version()` helper raising `UnsupportedBinaryVersionError` with FR47-exact format `<binary> version <X> outside tested range <range>`.
- Task 4 — `src/AgentEval/coding_agent/__init__.py` rewritten with 4 re-exports + `__all__`. Documents the contributor-facing import path.
- Task 5 — `src/AgentEval/_kernel/discovery.py` L102 `# type: ignore[attr-defined]` removed (Protocol now resolvable). Bonus: `src/AgentEval/_kernel/coverage.py` L55 forward-ref `# type: ignore[attr-defined]` for `AgentRunResult` also removed (Story 1b.2 baseline caught by mypy after Story 1b.4 lands the dataclass).
- Task 6 — `tests/unit/coding_agent/__init__.py` + `tests/unit/coding_agent/test_base.py` (~390L) authored. 29 tests covering: Protocol identity + re-export (3); `runtime_checkable` Protocol semantics (2); InProcessAdapter no-abstract-instantiate + default `name`/`version` + kwargs-capture + subclass override (5); SubprocessAdapter abstract enforcement + partial-impl failure + template-method orchestration (event-line + blank-line + non-event skip + nonzero exit) + cleanup-on-exception (5); `_assert_binary_version` 6 cases (in-range + below-min + at-max + max-None + unparseable + missing-binary) (6); `AgentRunResult` construction + frozen + defensive copy + `asdict` round-trip (4); `AgentRunMetadata` exhaustive value-space iteration (1); `UnsupportedBinaryVersionError` hierarchy + H_R7 `__str__` + base-catches-all (3); `_kernel/discovery.py` integration smoke (1).
- Task 7 — All-gates clean: ruff/format/mypy clean (31 source files); license headers 31/31; `pytest tests/unit -q --ignore=tests/unit/conventions` **249 passed** (220 prior + 29 new); `pytest tests/acceptance/tier1 -q` 6 passed (Story 1a.6 FR42 regression); `robot tests/acceptance/smoke` PASS.
- Task 8 — `docs/contracts/stability-surface.md` extended with new "Coding Agent Adapter Surface (Story 1b.4)" section (Protocol + ABCs + helpers as `provisional`; `ParsedEvent` as `experimental`; 3-hook contract + FR47 message format as `stable`). Top-level errors section extended with `UnsupportedBinaryVersionError` (`stable`); types section extended with `AgentRunResult` + `AgentRunMetadata` (`provisional`); 3-state Literal value spaces + `.metadata` nesting marked `stable` per ADR-006 + ADR-016.
- Task 9 — Project norms applied: code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)`; cross-LLM reviewer prompt will be directed to re-derive cited facts per `feedback_citation_drift_first_class`; Phase-1 limitations documented (sandbox out-of-scope; FR17b deferred to Story 4.1; ParsedEvent TypeAlias=Any; trace_id UUID hex Phase-1).

## File List

**New source files (1):**
- `src/AgentEval/coding_agent/base.py` (291L) — `CodingAgentAdapter` re-export + `InProcessAdapter` direct-override base + `SubprocessAdapter(ABC)` 3-hook template-method + `_assert_binary_version` helper + `type ParsedEvent = Any`

**New test files (2):**
- `tests/unit/coding_agent/__init__.py` (0L, empty)
- `tests/unit/coding_agent/test_base.py` (~390L, 29 tests)

**Modified files (5):**
- `src/AgentEval/types.py` — pure extension: `CodingAgentAdapter` Protocol + `AgentRunResult` + `AgentRunMetadata` dataclasses
- `src/AgentEval/errors.py` — pure extension: `UnsupportedBinaryVersionError(AgentEvalCompatError)` leaf
- `src/AgentEval/coding_agent/__init__.py` — re-export 4 contributor-facing names
- `src/AgentEval/_kernel/discovery.py` — remove `# type: ignore[attr-defined]` from L102 TYPE_CHECKING forward-ref
- `src/AgentEval/_kernel/coverage.py` — remove same `# type: ignore[attr-defined]` from L55 forward-ref (bonus caught by mypy after Protocol declaration lands)
- `docs/contracts/stability-surface.md` — new Coding Agent Adapter Surface section + extended top-level errors/types section

**New source files (1):**
- `src/AgentEval/coding_agent/base.py` (~250L) — `CodingAgentAdapter` re-export + `InProcessAdapter` direct-override base + `SubprocessAdapter(ABC)` 3-hook template-method + `_assert_binary_version` helper + `ParsedEvent: TypeAlias = Any`

**New test files (1):**
- `tests/unit/coding_agent/test_base.py` (~280L) — ~25 tests covering Protocol structural typing + InProcessAdapter direct-override + SubprocessAdapter abstract enforcement + template-method orchestration + `_assert_binary_version` 5-case coverage + AgentRunResult/AgentRunMetadata construction + re-export identity + discovery integration smoke + UnsupportedBinaryVersionError hierarchy

**Modified files (4):**
- `src/AgentEval/types.py` — pure extension: `CodingAgentAdapter` Protocol + `AgentRunResult` + `AgentRunMetadata` dataclasses
- `src/AgentEval/errors.py` — pure extension: `UnsupportedBinaryVersionError(AgentEvalCompatError)` leaf
- `src/AgentEval/coding_agent/__init__.py` — re-export 4 contributor-facing names
- `src/AgentEval/_kernel/discovery.py` — remove `# type: ignore[attr-defined]` from L102 TYPE_CHECKING forward-ref (now resolvable)
- `docs/contracts/stability-surface.md` — new Coding Agent Adapter Surface section + extended errors/types section

## Change Log

| Date       | Version | Description                                                                  | Author |
| ---------- | ------- | ---------------------------------------------------------------------------- | ------ |
| 2026-05-19 | 0.3.0   | Cross-LLM code-review patches applied; status → done. 4 reviewers (Blind Hunter + Edge Case Hunter + Acceptance Auditor + Codex CLI gpt-5.4): 77 raw findings → 31 unique after dedup → 4 decision-needed bundles (all Recommended) + 13 direct patches applied + 8 deferred + ~10 dismissed. **10th consecutive cross-LLM STAR catch**: Codex caught ADR-003 L30 base-class lifecycle ownership violation (impl ships only stdout iteration + wait + raw exit_code; ADR ratifies signal handling + timeout enforcement + stderr capture + exit-code mapping + truncation detection); `version` property uses module name not distribution name (`AgentEval` vs `robotframework-agenteval`); AgentEvalCompatError docstring still said "not yet implemented" after Story 1b.4 lands the leaf. **4-WAY HIGH**: process-group hygiene drift (`proc.terminate()` kills leader only; contradicts cited Story 1b.1 `os.killpg(pid, SIGTERM)` precedent). **3-WAY HIGH**: `_parse_version_tuple` short-tuple ordering bug (`(1,0) < (1,0,0)` True → `"1.0" vs "1.0.0"` boundary broken; real correctness bug for Stories 4.2/11.3); `runtime_checkable` Protocol overclaims signature validation; FR47 vs H_R7 `__str__` format drift. Path-of-least-amendment: implement `os.killpg + wait/kill escalation` per Story 1b.1; amend ADR-003 L30 to ratify Phase-1 minimum + Phase-2 carry-over for stderr/timeout/truncation; pad version tuples to fixed-arity 3 + reject prerelease; use `packages_distributions()` for distribution-name resolution; override `__str__` on UnsupportedBinaryVersionError for FR47-exact format; add `__post_init__` Literal validation on AgentRunMetadata; expose structured attrs on UnsupportedBinaryVersionError. Bonus patches: explicit `if/raise` instead of `assert proc.stdout` (python -O strips asserts); stdout + stderr fd close in finally; broader OSError catch on subprocess.run + `_default_version`; returncode check in `_assert_binary_version`; `mcp_servers` Protocol/base type alignment; coding_agent/__init__.py docstring drift fix. 14 new tests added. All-gates clean: ruff/format/mypy/license (31 source files / 31 of 31 license-headers); **263 unit passed** (220 prior + 43 in coding_agent dir); 6 tier1 + RF smoke regression PASS. `deferred-work.md` updated with 8 Phase-1.5 carry-over items. `docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-split.md` L29 amended pre-patch to ratify Phase-1 minimum + Phase-2 carry-over split. | Amelia |
| 2026-05-19 | 0.2.0   | Dev-story implementation pass complete; status → review. Tasks 1-9 done. New module `src/AgentEval/coding_agent/base.py` (~290L) ships `InProcessAdapter` (direct-override per ADR-003 L22-23, zero abstract methods) + `SubprocessAdapter(ABC)` (3-hook template-method per ADR-003 L24-29 + architecture L1228: `_spawn`/`_parse_event`/`_finalize`) + concrete `_assert_binary_version` helper with FR47-exact error-message format. `src/AgentEval/types.py` extended with `CodingAgentAdapter` Protocol (single `run(prompt, tools, mcp_servers, **kwargs)` per FR12, `@runtime_checkable` for FR17b composition) + `AgentRunResult` 7-field dataclass + `AgentRunMetadata` sub-dataclass with `.metadata.{completeness, mcp_coverage}` nested per ADR-006 L15 + FR36a/b L1553-1554. `src/AgentEval/errors.py` extended with `UnsupportedBinaryVersionError(AgentEvalCompatError)` leaf (declaration in Story 1b.4 per Story 1b.3 errors.py L59 forward-ref; per-adapter raise sites in Epic 4/11). `_kernel/discovery.py` L102 `# type: ignore[attr-defined]` removed (Protocol now resolvable); bonus: same removed from `_kernel/coverage.py` L55. PEP-695 `type ParsedEvent = Any` adopted per project's Story 1b.1 PEP-695 convention. `tests/unit/coding_agent/test_base.py` (29 tests) covers Protocol identity + re-export + runtime_checkable + InProcessAdapter direct-override + SubprocessAdapter abstract enforcement + template-method orchestration + cleanup-on-exception via `contextlib.suppress` + 6 `_assert_binary_version` cases + AgentRunResult/AgentRunMetadata + UnsupportedBinaryVersionError hierarchy + discovery integration smoke. All-gates clean: ruff/format/mypy clean (31 source files); license headers 31/31; **249 unit passed** (220 prior + 29 new); 6 tier1 acceptance + RF smoke regression PASS. `docs/contracts/stability-surface.md` extended with new Coding Agent Adapter Surface section. Phase-1 limitations preserved (sandbox out-of-scope; FR17b deferred to Story 4.1; ParsedEvent TypeAlias=Any; trace_id UUID hex Phase-1). | Amelia |
| 2026-05-19 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (8th consecutive use of `feedback_spec_vs_ratified_doc_precheck`) caught 14 drifts in Story 1b.4 epics.md spec vs ratified sources (6 HIGH + 4 MED + 4 LOW/clean). All 14 resolved via path-of-least-amendment by honoring ratified sources per Many's 2026-05-19 ratification: (D1) single `run()` Protocol method per FR12 L1506; (D2/D15) `AgentRunResult.metadata.{completeness, mcp_coverage}` nested per ADR-006 + FR36a/b; (D3/D4) reuse Story-1b.2 `ToolCallTrace`/`Usage` types; (D6/D7) drop undefined `Scenario`/`MCPServer`/`RawResponse`/`ParsedEvent` types — MCP lifecycle stays at Story 1b.1's MCPLifecycleManager; (D8) Protocol declared in `types.py` (re-exported through `coding_agent/base.py`) per architecture L853 + Story 1b.3 discovery.py L102 forward-ref; (D9) InProcessAdapter no abstract hooks per ADR-003 L22-23; (D10) SubprocessAdapter 3-hook `_spawn`/`_parse_event`/`_finalize` per ADR-003 L24-29 + architecture L1228; (D11) `_agenteval_tier` on keyword methods only per L620; (D13) UnsupportedBinaryVersionError class declaration in Story 1b.4 + per-adapter raise sites in Epic 4/11. Scope-edges ratified: FR47 exact error format; sandbox out-of-scope for adapters; FR17b kwarg deferred to Story 4.1; ParsedEvent TypeAlias=Any until concrete adapters. Pre-authoring fixes: epics.md L973-993 + `docs/contracts/error-class-hierarchy.md` L81 amended 2026-05-19. NEW NORM from Epic 1a retro embedded in AC-1b.4.12: cross-LLM reviewer prompt MUST direct re-derivation of every cited fact from source. | Bob |
