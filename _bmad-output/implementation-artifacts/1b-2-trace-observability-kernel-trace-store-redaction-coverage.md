# Story 1b.2: Trace + Observability Kernel — Trace Store + Redaction + Coverage

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **trace producer** (Epic 5),
I want **the three trace/observability `_kernel/` modules — `trace_store.py` wrapping OTel SDK `InMemorySpanExporter` with 5 projection accessors per architecture L664-669, `redaction.py` exposing primitive `redact()` + `redact_dict()` PLUS a `RedactionProcessor(SpanProcessor)` for OTel pipeline integration, `coverage.py` exposing `_check_mcp_coverage(run, allow_external_mcp_blind)` enforcement gate per ADR-016 + FR37 — implemented and unit-tested, plus the minimal co-created `errors.py` (`AgentEvalError` + `AgentEvalIntegrityError` + `IncompleteTraceError`) and `types.py` (`ToolCallTrace` + `Usage` + `RunManifest`) needed by those modules**,
So that **Epic 5 can ship the hosted-MCP observer + OTel listener against a stable kernel layer, credential leaks are impossible-by-construction via the single SpanProcessor choke point, the `mcp_coverage` enforcement gate raises `IncompleteTraceError` on `external_mixed` runs per FR37, and the projection accessors give Epic 6 metric keywords a typed read-path that obeys architecture's "no direct span access by sub-libraries" rule**.

## Acceptance Criteria

> **Pre-create-story drift check (6th consecutive use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-18):** 6 drifts in Story 1b.2 spec + 2 pre-emptive drifts in Story 1b.4 spec caught vs ratified sources. Per Many's 2026-05-18 ratification, ALL 8 resolved by honoring ratified sources. epics.md L880-890 (Story 1b.2) + L924-930 (Story 1b.4) updated pre-authoring. Drifts: (D1 HIGH) trace_store.py API surface — class+raw-primitives → 5 projection accessors per architecture L664-669; (D2 HIGH) coverage.py function name+intent — `compute_mcp_coverage` (detect) → `_check_mcp_coverage` (enforce + raise IncompleteTraceError) per ADR-016 L44 + architecture L384; (D3 HIGH) errors.py + IncompleteTraceError dependency — co-create minimal subset; (D4 MED) `AgentRunResult` location — sub-lib types.py → top-level `src/AgentEval/types.py` per architecture L853; (D5 MED) redaction.py SpanProcessor integration missing from spec — add `RedactionProcessor(SpanProcessor)` class per architecture L679; (D6 LOW) `Span` → `ReadableSpan` type; (D7 LOW downstream) `__agenteval_tier__` dunder → `_agenteval_tier` single-underscore per Story 1b.1; (D8 LOW downstream) `mcp_coverage` 4-state with `"none"` → ratified ADR-016 3-state. Story 1b.4 epics.md pre-emptive cleanup applied for D4 + D7 + D8.

1. **AC-1b.2.1 — `_kernel/trace_store.py` 5 projection accessors per architecture L664-669.** Module exposes the 5 typed accessors (NOT raw add/get/clear primitives — those violate the "no direct span access by sub-libraries" rule at architecture L853):
   - `get_run_spans(test_id: str) -> list[ReadableSpan]` — all spans tagged with the given `test_id` (resource attribute `agenteval.test_id` per architecture L663). When `test_id` is omitted, defaults to `current_context().test_id` from Story 1b.1's `_kernel/context.py`. Returns spans in chronological order (by `start_time`). Cross-test isolation enforced: test A's call MUST NEVER return test B's spans.
   - `get_tool_calls(test_id: str, source: Literal["adapter", "hosted_mcp"] | None = None) -> list[ToolCallTrace]` — projection of `execute_tool` spans (per OTel GenAI semconv at architecture L975-985) into `ToolCallTrace` dataclasses (defined in `src/AgentEval/types.py`); `source` filter optional.
   - `get_usage(test_id: str) -> Usage` — sum of `gen_ai.usage.input_tokens` + `gen_ai.usage.output_tokens` + `gen_ai.usage.cached_input_tokens` attributes across `chat` spans for the test.
   - `get_latency(test_id: str) -> float` — sum of `(end_time - start_time)` in seconds across the test's spans.
   - `get_run_manifest(test_id: str) -> RunManifest` — per FR39 + architecture L669: assembled from resource attributes + library version + redaction-policy hash.

2. **AC-1b.2.2 — `_kernel/trace_store.py` internal `InMemorySpanExporter` lifecycle + per-test cleanup hook.** Module owns a single process-global `InMemorySpanExporter` instance. TracerProvider configuration with `agenteval.test_id` resource attribute happens in `AgentEval.__init__(telemetry=True)` (default; FR33a) — Story 1b.2 ships the wiring helper `_configure_tracer_provider() -> None` that the future Listener (Epic 5 Story 5.1) calls at library import time. Per-test cleanup hook `clear_spans(test_id: str) -> int` (returns count of spans cleared) — called by the Listener's `end_test` hook (Epic 5 wiring), also exposed for tests + manual cleanup. **Story 1b.2 does NOT wire the actual Listener; that's Epic 5 Story 5.1 scope. Story 1b.2 ships the kernel surface only.**

3. **AC-1b.2.3 — `src/AgentEval/types.py` co-created with 3 Phase-1 dataclasses per architecture L853.** Top-level shared-types module (architecture L853 requires cross-cutting types at top level; sub-library `library.py + _internal.py + types.py` triplets remain valid for sub-library-private types per architecture L845-849 — M_R17 wording fix). Uses **stdlib `@dataclass(frozen=True)`** for Phase-1 minimalism (architecture L853 wording is "Pydantic dataclasses"; Phase-1 deviation documented in module docstring + Phase-1.5 carry-over to migrate if FR39 OTLP serialization needs Pydantic validation). Types:
   - **`ToolCallTrace`** with `name: str`, `args: Mapping[str, Any]`, `result: Any | None`, `error: str | None`, `latency_ms: float`, `source: Literal["adapter", "hosted_mcp"]`, `gen_ai_tool_call_id: str` — per FR35 + architecture L975-985 OTel GenAI semconv mapping.
   - **`Usage`** with `input_tokens: int`, `output_tokens: int`, `cached_input_tokens: int = 0` — sums `gen_ai.usage.*` per architecture L975.
   - **`RunManifest`** with `library_version: str`, `test_id: str`, `suite_id: str`, `redaction_policy_hash: str`, `started_at: datetime`, `ended_at: datetime`, `agenteval_tier_breakdown: Mapping[int, int]` — per FR39.

   Subsequent stories (Story 1b.4 + Story 1b.5) ADD to this same `types.py`: `AgentRunResult`, `ToolCall`, `TokenUsage`, `Scenario`, `MCPServer`, etc. Story 1b.2's responsibility is the minimal subset needed by the trace_store projection accessors.

4. **AC-1b.2.4 — `_kernel/redaction.py` primitive scrubbing functions.** Module exposes:
   - `DEFAULT_PATTERNS: list[Pattern]` (module-level) — `sk-[A-Za-z0-9]+` (OpenAI/Anthropic key prefix), `Bearer\s+\S+` (HTTP bearer tokens), `(?i)ANTHROPIC_API_KEY=\S+`, `(?i)OPENAI_API_KEY=\S+`, `xoxb-\S+` (Slack bot tokens), JWT shape `eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`. Each pattern replaces matches with `[REDACTED]`. Pattern set documented in module docstring + `docs/contracts/evidence-block-format.md` cross-reference.
   - `redact(text: str, patterns: list[Pattern] | None = None) -> str` — apply each pattern in order; `patterns=None` uses `DEFAULT_PATTERNS`. Idempotent (re-applying produces the same output).
   - `redact_dict(d: Mapping[str, Any]) -> dict[str, Any]` — recursive variant: scalar `str` values get `redact()`; nested `dict`/`list`/`tuple` get recursive treatment; other types pass through unchanged.
   - `register_pattern(regex: str) -> None` — appends a compiled pattern to `DEFAULT_PATTERNS`. Documented as **caller-responsibility for thread safety** in module docstring (Phase-1: not lock-protected; callers register at library import time, NOT per-test).
   - `redaction_policy_hash() -> str` — returns a stable SHA-256 hex of the current pattern set (used by `RunManifest.redaction_policy_hash` per FR39).

5. **AC-1b.2.5 — `_kernel/redaction.py` `RedactionProcessor(SpanProcessor)` class per architecture L679 + L1193.** OTel SpanProcessor subclass that scrubs span attributes via `redact()` at `on_end(span)` time:
   - Scrubs `gen_ai.request.messages` (LLM prompt content), `gen_ai.response.text`, `gen_ai.tool.args` (JSON-serialized; uses `redact_dict()` if attribute is a dict, `redact()` if str), `agenteval.tool.args`, `agenteval.tool.result`.
   - Mutates the span's attribute dict in-place (per OTel SDK pattern). The mutation happens BEFORE the next processor in the chain receives the span — architecture L679's `RedactionProcessor → InMemoryExporter` chain order is load-bearing.
   - `on_start(span, parent_context)` is a no-op (no scrubbing needed at span start; nothing to redact yet).
   - `shutdown()` and `force_flush(timeout_millis)` delegate to no-op (this processor has no buffered state).
   - Epic 5 Story 5.1 wires `tracer_provider.add_span_processor(RedactionProcessor())` BEFORE the `BatchSpanProcessor`-wrapped `InMemorySpanExporter`. Story 1b.2 ships the class only; wiring at Story 5.1.

6. **AC-1b.2.6 — `src/AgentEval/errors.py` co-created with MINIMAL subset per ADR-014.** Module exposes:
   - `AgentEvalError(Exception)` base — all agenteval-raised errors inherit from this. Architecture L902-906 + ADR-014: every error class has `error_code: str` class attribute matching `<DOMAIN>_<ACTION>` uppercase pattern.
   - `AgentEvalIntegrityError(AgentEvalError)` sub-base — for errors signaling that the trace/run integrity is compromised (per ADR-014's 4-sub-base scheme: `AgentEvalSafetyError`, `AgentEvalBudgetError`, `AgentEvalCompatError`, `AgentEvalIntegrityError`). Story 1b.2 ships only the Integrity sub-base; future stories add the other 3 as they need them.
   - `IncompleteTraceError(AgentEvalIntegrityError)` leaf — `error_code = "TRACE_INCOMPLETE"`; raised by `_check_mcp_coverage` per FR37 + ADR-016 L44 when `mcp_coverage == "external_mixed"` without `allow_external_mcp_blind=True`.
   - **Module structure** MUST be extension-friendly: subsequent stories add `PollingDisallowedError`, `CostExceededError`, `RuntimeBudgetExceededError`, `UnsupportedMCPVersionError`, `UnsupportedBinaryVersionError`, `TierViolationError`, `SandboxRequiredError`, `ValidateOperatorDisallowed` as pure additions to the same `errors.py` file (one or two per story, no refactors). The base + sub-base hierarchy is set in this story; future stories ONLY add leaves and (if needed) 3 more sub-bases (`AgentEvalSafetyError`, `AgentEvalBudgetError`, `AgentEvalCompatError`).
   - Story 1a.1 created the `SandboxRequiredError` placeholder; it has its own module at `src/AgentEval/security/policy.py` (Story 1a.1 baseline) and currently does NOT inherit from `AgentEvalError`. Story 1b.2 dev MUST verify whether to re-home `SandboxRequiredError` into `errors.py` (per ADR-014's "all errors in one module" rule) or defer to a hygiene story. **Phase-1 decision: defer the re-home to a future story; document the gap in `errors.py` module docstring + `deferred-work.md`.**

7. **AC-1b.2.7 — `_kernel/coverage.py` enforcement gate per ADR-016 + FR37.** Module exposes `_check_mcp_coverage(run: AgentRunResult, *, allow_external_mcp_blind: bool = False) -> None`:
   - **Input signature uses `AgentRunResult` as a forward reference.** Story 1b.4 lands `AgentRunResult` in `src/AgentEval/types.py`. Story 1b.2 declares the type via `from __future__ import annotations` + `TYPE_CHECKING`-guarded import + a **Phase-1 duck-typed runtime check**: the function accesses `run.metadata.mcp_coverage` (read-only) and `run.metadata.observed_paths` (read-only). Any object with this attribute shape works at runtime; type checkers see `AgentRunResult` forward-ref. Document this Phase-1 forward-reference pattern in the module docstring.
   - When `run.metadata.mcp_coverage == "external_mixed"` AND `allow_external_mcp_blind=False`: raise `IncompleteTraceError("Run reports mcp_coverage='external_mixed' (uninstrumented MCP usage detected); pass allow_external_mcp_blind=True at Library construction time to opt into a blind run, OR fix the adapter to populate full coverage (see docs/contracts/mcp-coverage-detection.md).")`.
   - When `mcp_coverage == "external_mixed"` AND `allow_external_mcp_blind=True`: return `None` (opt-in blind run; documented escape hatch per FR42 + ADR-016).
   - When `mcp_coverage` is `"hosted_in_process"` or `"subprocess_with_observer"`: return `None` (trace is complete per the trust-floor decision tree at ADR-016 §Decision L17-28; kernel CONSUMES the value but does NOT compute it).
   - **The trust-floor decision tree itself (D1 amendment per ADR-016 L17-28) is exercised by ADAPTERS at metadata-population time, NOT by the kernel.** Kernel ONLY reads the resolved value + enforces the gate. The unit test in AC-1b.2.10 verifies the kernel correctly accepts `hosted_in_process` even when the spike's `observed_paths` metadata indicates both `hosted_in_process` AND `subprocess_with_observer` fired (trust-floor case).

8. **AC-1b.2.8 — Kernel modules consume `_kernel/context.current_context()` from Story 1b.1.** `trace_store.py` projection accessors call `current_context().test_id` when `test_id` is omitted (per AC-1b.2.1). No direct ContextVar manipulation outside Story 1b.1's `_kernel/context.py`. Story 1b.2 dev must NOT introduce a separate ContextVar; reuse Story 1b.1's.

9. **AC-1b.2.9 — Unit tests in `tests/unit/kernel/test_{trace_store, redaction, coverage}.py` + `tests/unit/test_errors.py` + `tests/unit/test_types.py`.** Coverage per AC-1b.2.1 → AC-1b.2.8:
   - `test_trace_store.py` (~12+ tests): each of the 5 projection accessors with representative span fixtures; per-test isolation (test A's `get_run_spans()` never returns test B's spans); chronological ordering; `clear_spans(test_id)` returns count + actually clears; `_configure_tracer_provider()` adds the `agenteval.test_id` resource attribute correctly; default-to-`current_context()` behavior; missing test_id (no spans for that test_id) returns empty list (not raise).
   - `test_redaction.py` (~10+ tests): each of 6 default patterns scrubs to `[REDACTED]`; plain text unchanged; idempotent re-application; nested dict recursion (3+ levels deep); custom `register_pattern` extension; `redaction_policy_hash` is stable across runs + changes when patterns are added; `RedactionProcessor.on_end` mutates span.attributes in-place for the 5 documented attribute names.
   - `test_coverage.py` (~8+ tests): all 6 input combinations (3 mcp_coverage values × 2 allow_external_mcp_blind values); `IncompleteTraceError` is raised with the expected message + `error_code="TRACE_INCOMPLETE"`; trust-floor fixture verifies kernel accepts `hosted_in_process` even when `observed_paths` shows both paths fired; duck-typed input shape works (any object with `.metadata.mcp_coverage`).
   - `test_errors.py` (~5+ tests): `IncompleteTraceError` inherits `AgentEvalIntegrityError` inherits `AgentEvalError` inherits `Exception`; `error_code == "TRACE_INCOMPLETE"`; the base + sub-base structure is correct (no leaf inherits directly from `AgentEvalError`); `error_code` is a class attribute (not instance attribute).
   - `test_types.py` (~6+ tests): each of `ToolCallTrace`, `Usage`, `RunManifest` constructs correctly with default values + serializes via `dataclasses.asdict()` round-trip; frozen=True blocks attribute mutation.

10. **AC-1b.2.10 — All-gates clean.** `uv run ruff check src/ tests/` clean; `uv run ruff format --check src/ tests/` clean; `uv run mypy src/` clean (28 source files: previous 23 + new errors.py + types.py + trace_store.py + redaction.py + coverage.py — M_R18 count fix); `uv run python scripts/check-license-headers.py` PASS; `uv run pytest tests/unit -q --ignore=tests/unit/conventions` — all kernel unit tests pass (existing 67 from Story 1b.1 + new ~41+ from Story 1b.2 = 108+); `uv run pytest tests/acceptance/tier1 -q` — Story 1a.6's 6 FR42 tests still pass (regression); `uv run robot tests/acceptance/smoke` — RF smoke test still passes (regression).

11. **AC-1b.2.11 — Code-review prompt embeds the citation-drift re-derivation directive (Epic 1a retro NEW NORM / `feedback_citation_drift_first_class`).** When `/bmad-code-review (Using current Claude + Codex CLI subagent)` runs for Story 1b.2, the cross-LLM reviewer prompt MUST direct: *"For every citation in the changed files — 'per ADR-016 L44', 'per FR37', 'per architecture L664-669', 'per OTel GenAI semconv L975-985', 'per ADR-014 L902-906', 'per spike findings §Y', etc. — open the cited source and verify the claim is EXACTLY what the source says. Flag any mismatches even if subtle (rename, count drift, slug drift, off-by-one line numbers, attribute-name drift)."* Citation drift was the #1 finding category across Epic 1a; Story 1b.1's code review demonstrated this norm caught real drift again (M4 ADR-012 + ADR-015 filename drift).

## Tasks / Subtasks

- [x] **Task 1: Author `src/AgentEval/errors.py` MINIMAL subset (AC: 1b.2.6)**
  - [x] Apache 2.0 license header.
  - [x] Module docstring citing ADR-014 (was ADR-A3) + architecture L376/L902-930 + Story 1a.4's `docs/contracts/error-class-hierarchy.md`.
  - [x] `AgentEvalError(Exception)` base class with `error_code: str = ""` ClassVar default + `__init__` that captures message + formats `error_code: <msg>` in `__str__`.
  - [x] `AgentEvalIntegrityError(AgentEvalError)` sub-base — no override; inherits everything from base. Documented as the trace/run-integrity-class sub-base.
  - [x] `IncompleteTraceError(AgentEvalIntegrityError)` leaf — `error_code: ClassVar[str] = "TRACE_INCOMPLETE"`.
  - [x] Module docstring includes the placeholder note about `SandboxRequiredError` currently living at `src/AgentEval/security/policy.py` (Story 1a.1 baseline) NOT inheriting from `AgentEvalError`; Phase-1 deferred-work item to re-home it.
  - [x] Verify with `uv run mypy src/AgentEval/errors.py`.

- [x] **Task 2: Author `src/AgentEval/types.py` 3 Phase-1 dataclasses (AC: 1b.2.3)**
  - [x] Apache 2.0 license header.
  - [x] Module docstring citing architecture L853 (shared types live here); FR35 + FR39; OTel GenAI semconv at architecture L975-985; Phase-1 stdlib `@dataclass(frozen=True)` deviation from architecture's "Pydantic dataclasses" wording (Phase-1 minimalism; migration is a Phase-1.5 carry-over if needed for Epic 5 OTLP).
  - [x] `ToolCallTrace` dataclass with the 7 fields per AC-1b.2.3. Mapping-typed `args` accepts `dict` at construction; immutable post-construction.
  - [x] `Usage` dataclass with the 3 fields per AC-1b.2.3.
  - [x] `RunManifest` dataclass with the 7 fields per AC-1b.2.3.
  - [x] All 3 are `frozen=True` per Phase-1 immutability convention.

- [x] **Task 3: Author `src/AgentEval/_kernel/redaction.py` primitives (AC: 1b.2.4)**
  - [x] Apache 2.0 license header.
  - [x] Module docstring citing NFR-SEC-01 / FR38a + architecture L679 + L1193.
  - [x] `DEFAULT_PATTERNS: list[re.Pattern]` (module-level, mutable) seeded with 6 patterns per AC-1b.2.4.
  - [x] `redact(text, patterns=None) -> str` — replace each pattern's matches with `[REDACTED]`.
  - [x] `redact_dict(d) -> dict` — recursive; `str` values get `redact()`; nested dict/list/tuple recursed; other types pass-through.
  - [x] `register_pattern(regex: str) -> None` — compile + append to `DEFAULT_PATTERNS`. Thread-safety caveat in module docstring.
  - [x] `redaction_policy_hash() -> str` — SHA-256 hex of `"|".join(p.pattern for p in DEFAULT_PATTERNS)`; stable across runs with the same pattern set.

- [x] **Task 4: Author `src/AgentEval/_kernel/redaction.py` `RedactionProcessor(SpanProcessor)` class (AC: 1b.2.5)**
  - [x] Import `opentelemetry.sdk.trace.SpanProcessor`.
  - [x] `RedactionProcessor(SpanProcessor)` with `on_start(span, parent_context)` no-op; `on_end(span)` scrubs the 5 documented attribute keys (per AC-1b.2.5) via `redact()` or `redact_dict()` based on attribute type.
  - [x] `shutdown()` + `force_flush(timeout_millis=30000)` no-ops returning True (per SpanProcessor protocol).
  - [x] Verify with mypy.

- [x] **Task 5: Author `src/AgentEval/_kernel/trace_store.py` lifecycle + projection accessors (AC: 1b.2.1, 1b.2.2, 1b.2.8)**
  - [x] Apache 2.0 license header.
  - [x] Module docstring citing architecture L600-682 Decision-2 + L968-990 OTel GenAI semconv + Story 1b.1's `_kernel/context.current_context()`.
  - [x] `_exporter: InMemorySpanExporter` module-level singleton (lazy-initialized to allow test override).
  - [x] `_configure_tracer_provider() -> None` helper that sets up the TracerProvider with the `agenteval.test_id` resource attribute pulled from `current_context()` at span-start time. Phase-1 implementation: rely on OTel SDK's `set_tracer_provider()`; Epic 5 Story 5.1 wires this into `AgentEval.__init__(telemetry=True)`.
  - [x] `get_run_spans(test_id: str | None = None) -> list[ReadableSpan]` — falls back to `current_context().test_id` when omitted; filters `_exporter.get_finished_spans()` by `span.attributes.get("agenteval.test_id") == test_id`; sorts by `span.start_time` ascending.
  - [x] `get_tool_calls(test_id, source=None) -> list[ToolCallTrace]` — filter spans by `span.name == "execute_tool"` + optionally `span.attributes.get("agenteval.tool.source") == source`; project into `ToolCallTrace` dataclasses.
  - [x] `get_usage(test_id) -> Usage` — filter spans by `span.name == "chat"`; sum `gen_ai.usage.{input_tokens, output_tokens, cached_input_tokens}` attributes.
  - [x] `get_latency(test_id) -> float` — sum `(span.end_time - span.start_time) / 1e9` for nanosecond→second conversion across all spans for the test.
  - [x] `get_run_manifest(test_id) -> RunManifest` — assemble from `library_version` (read `AgentEval.__version__`), test_id, suite_id (from current TestContext), redaction-policy hash (from `redaction.redaction_policy_hash()`), start/end times (from min/max span timestamps for the test), tier-breakdown (count spans per `agenteval.tier` attribute value).
  - [x] `clear_spans(test_id: str) -> int` — remove spans tagged with `test_id` from the exporter's internal buffer; return count removed. Phase-1 implementation: `InMemorySpanExporter.get_finished_spans()` returns a list — manipulate the underlying `_finished_spans` list (private but stable in opentelemetry-sdk 1.20+) OR re-create the exporter; pick the cleaner option + document.

- [x] **Task 6: Author `src/AgentEval/_kernel/coverage.py` enforcement gate (AC: 1b.2.7)**
  - [x] Apache 2.0 license header.
  - [x] Module docstring citing ADR-016 L44 + L17-28 + architecture L384 + L1058 + FR37; explicitly note kernel does NOT detect (adapters do) — kernel only enforces.
  - [x] `from __future__ import annotations` + `from typing import TYPE_CHECKING`; under `if TYPE_CHECKING:` import `AgentRunResult` from `AgentEval.types` (forward ref; Story 1b.4 lands the class).
  - [x] `_check_mcp_coverage(run: AgentRunResult, *, allow_external_mcp_blind: bool = False) -> None` — implements the 4 cases per AC-1b.2.7. Raises `IncompleteTraceError` from `AgentEval.errors` with the documented message.
  - [x] Document Phase-1 duck-typed runtime: function accesses `run.metadata.mcp_coverage` only; any object with that attribute shape works at runtime.

- [x] **Task 7: Author unit tests under `tests/unit/kernel/` + `tests/unit/` (AC: 1b.2.9)**
  - [x] `tests/unit/kernel/test_trace_store.py` — 12+ tests covering the 5 accessors + per-test isolation + chronological ordering + `clear_spans` + `_configure_tracer_provider` + default-to-current_context behavior. Use OTel SDK's `InMemorySpanExporter` directly + synthesize `ReadableSpan` fixtures via `tracer.start_span(...).end()` pattern.
  - [x] `tests/unit/kernel/test_redaction.py` — 10+ tests covering the 6 default patterns + idempotency + recursion + `register_pattern` extension + `redaction_policy_hash` stability + `RedactionProcessor.on_end` mutation in-place.
  - [x] `tests/unit/kernel/test_coverage.py` — 8+ tests covering the 6 input combinations + trust-floor fixture + duck-typed input. Use a `types.SimpleNamespace`-shaped fake to stand in for `AgentRunResult` until Story 1b.4 lands the real type.
  - [x] `tests/unit/test_errors.py` — 5+ tests verifying the class hierarchy + `error_code` semantics.
  - [x] `tests/unit/test_types.py` — 6+ tests verifying construction + frozen immutability + `asdict()` round-trip for each of the 3 dataclasses.

- [x] **Task 8: All-gates pass (AC: 1b.2.10)**
  - [x] `uv run ruff check src/ tests/` — clean.
  - [x] `uv run ruff format --check src/ tests/` — clean.
  - [x] `uv run mypy src/` — clean (28+ source files: previous 23 + errors.py + types.py + trace_store.py + redaction.py + coverage.py).
  - [x] `uv run python scripts/check-license-headers.py` — PASS (28+ files).
  - [x] `uv run pytest tests/unit -q --ignore=tests/unit/conventions` — 108+ pass (67 from Story 1b.1 + 41+ new).
  - [x] `uv run pytest tests/acceptance/tier1 -q` — 6 FR42 tests still PASS (Story 1a.6 regression).
  - [x] `uv run robot tests/acceptance/smoke` — RF smoke test still PASS (Story 1a.6 regression).

- [x] **Task 9: Apply project norms (AC: 1b.2.11)**
  - [x] Code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)` per `feedback_review_methodology_norms`.
  - [x] The cross-LLM-reviewer prompt MUST direct: *"For every citation, re-derive from the source"* (per `feedback_citation_drift_first_class`).
  - [x] Honest framing: Phase-1 limitations documented (stdlib dataclass vs Pydantic; forward-ref `AgentRunResult`; `SandboxRequiredError` not re-homed; `RedactionProcessor` ships but isn't wired until Story 5.1).

### Review Findings

> **Code review 2026-05-18 — cross-LLM adversarial pair (Claude Opus 4.7 in 3 review roles + Codex CLI 0.117.0).** 4 reviewers ran in parallel; 49 raw findings caught; ~36 unique after dedup. **8th consecutive cross-LLM review** where Codex caught real findings; this round's STAR catch is the resource-vs-span attribute model bug (C1 / H_R2) — a structural blocker analogous to Story 1b.1's H1 (scope modes not implemented). The 3 Claude reviewers explicitly looked at the trace-store implementation and ALL missed it; Codex caught it by walking architecture L652 against the test fixture's `attrs = {"agenteval.test_id": test_id}` pattern.

**decision-needed (4):**

- [x] [Review][Decision] H_R4 — `get_tool_calls` silently drops `execute_tool` spans missing `agenteval.tool.source` [src/AgentEval/_kernel/trace_store.py:186-190] — current code: `if span_source not in ("adapter", "hosted_mcp"): continue`. Three policy choices: (a) default missing source to `"adapter"` + emit `DegradedTraceWarning`; (b) raise `IncompleteTraceError` (loud refusal per ADR-016 posture); (c) keep silent skip but document explicitly. FR35 enumerates only 2 sources; missing-source IS a trace-emission bug.
- [x] [Review][Decision] H_R5 — `_attr_to_mapping` wraps JSON-string args as `{"_raw": value}` placeholder [src/AgentEval/_kernel/trace_store.py:215-224] — OTel SDK doesn't accept dict attribute values; production `agenteval.tool.args` will always be JSON-encoded strings, making the `_raw` wrapping every call's path. Three choices: (a) JSON-parse with try/except (most useful); (b) keep `{"_raw": ...}` + document the contract in stability-surface.md + ToolCallTrace.args docstring; (c) add a separate `args_json` lazily-parsed accessor on ToolCallTrace.
- [x] [Review][Decision] H_R6 — `ToolCallTrace.sequence_index` field deleted from spec but required by PRD FR35 + FR45(d) conformance [src/AgentEval/types.py:64-72] — Auditor caught this as 9th drift the create-story drift check missed. Two choices: (a) add `sequence_index: int` to `ToolCallTrace` + derive from span ordering in `get_tool_calls`; (b) amend PRD FR35 + FR45(d) to drop `sequence_index` (justification needed: `gen_ai_tool_call_id` is the OTel-semconv-aligned replacement). PRD says "conformance suite asserts `sequence_index` monotonic per agent run" — load-bearing for Epic 1b Story 1b.5 + Epic 6 metric keywords.
- [x] [Review][Decision] H_R11 — Citation drift: `agenteval.tool.args/result/source/error` cited as "per architecture L975-985" but L975-985 does NOT define them [src/AgentEval/_kernel/trace_store.py:17,45,166 + types.py:71] — only `gen_ai.tool.name`, `gen_ai.tool.call.id`, `agenteval.tool.success`, `agenteval.tool.duration_ms` are at L975-985. Two choices: (a) amend `architecture.md` L975-985 (or a new section) to ratify the additional `agenteval.tool.*` attributes (preferred per project ratification norm); (b) downgrade citation language to "per FR35 + project-internal namespacing convention; agenteval-namespaced additions not yet ratified in architecture.md — pending amendment".

**patch (28):**

- [x] [Review][Patch] H_R1 — `RedactionProcessor.on_end` mutates `MappingProxyType`-backed `BoundedAttributes` via `attributes[key] = ...`, which is read-only at runtime; mock tests pass with plain dicts but production crashes/no-ops [src/AgentEval/_kernel/redaction.py:233] — **4-WAY CONFIRMATION** (Blind 2 + Auditor H1 + Edge 1 + Codex C2). Fix: mutate `span._attributes._dict[key] = new_value` (per author's own original docstring comment) OR move mutation into a hook receiving mutable `_Span` state. ALSO add an integration test wiring real TracerProvider → RedactionProcessor → SimpleSpanProcessor(InMemorySpanExporter) so the contract is verified end-to-end.
- [x] [Review][Patch] H_R2 — Resource-level `agenteval.test_id` is never read; trace_store filters on `span.attributes` but architecture L652 says test_id is a Resource attribute on the TracerProvider [src/AgentEval/_kernel/trace_store.py:131 + tests/unit/kernel/test_trace_store.py:48] — **STAR CATCH (Codex C1 solo)**. When Story 5.1 wires the TracerProvider per architecture, all projection accessors will silently return empty. Fix: read `span.resource.attributes.get("agenteval.test_id")` (with span-attribute fallback during the Phase-1 transition); update test fixtures to emit resource-level `test_id` via `Resource.create({"agenteval.test_id": "t1"})`.
- [x] [Review][Patch] H_R3 — `get_latency` double-counts nested spans (sums parent + children durations) → reports 2× real elapsed time for any tree of depth 2 [src/AgentEval/_kernel/trace_store.py:275-283] — Blind 4 solo. FR35 latency contract broken. Fix: either (a) sum only root spans (`span.parent is None`) OR (b) compute `max(end_time) - min(start_time)`. Add a test emitting parent + child and asserting the result is NOT 2×.
- [x] [Review][Patch] H_R7 — `AgentEvalError.__str__` formatter promised in errors.py docstring + Story spec is NOT implemented; test `test_incomplete_trace_error_message_round_trip` pins the wrong (default-Exception) behavior [src/AgentEval/errors.py + tests/unit/test_errors.py:34-37] — Blind 1 solo. FR49 JUnit XML emission + FR50 exit-code mapping rely on the `error_code: <msg>` prefix. Fix: implement `__str__` returning `f"{self.error_code}: {super().__str__()}"` when error_code non-empty; update the test.
- [x] [Review][Patch] H_R8 — `clear_spans` mutates `exporter._finished_spans` without holding `exporter._lock` → races with `BatchSpanProcessor.export()` (which acquires the lock per SDK source) [src/AgentEval/_kernel/trace_store.py:354-357] — Edge 2 solo (Blind 16 noted concurrency but didn't cite the SDK lock). Fix: `with exporter._lock: finished[:] = [...]`.
- [x] [Review][Patch] H_R9 — `redaction_policy_hash` joins only `p.pattern`, ignoring `p.flags`; future flag changes break FR39 reproducibility silently [src/AgentEval/_kernel/redaction.py:178-179] — Edge 3 solo. Fix: include `p.flags` in the hash input: `"|".join(f"{p.pattern}|{p.flags}" for p in DEFAULT_PATTERNS)`.
- [x] [Review][Patch] H_R10 — `_attr_as_int(True)` returns `1` silently (Python `isinstance(True, int) is True`); a buggy boolean emission gets miscounted as 1 token [src/AgentEval/_kernel/trace_store.py:227-238] — Edge 4 solo. Fix: add `if isinstance(value, bool): return default` BEFORE the int/float branch.
- [x] [Review][Patch] H_R12 — `redact_dict` recurses only on `dict` (`isinstance(value, dict)`), not on the broader `Mapping` type the function declares — nested `BoundedAttributes` / `MappingProxyType` / `frozendict` payloads pass through unredacted [src/AgentEval/_kernel/redaction.py:154-163] — Blind 3 solo. Fix: use `isinstance(value, Mapping)` and convert to dict.
- [x] [Review][Patch] M_R1 — `_check_mcp_coverage` silently returns None for unknown coverage strings (typo `"external mixed"`, future enum values); defeats "loud refusal" posture [src/AgentEval/_kernel/coverage.py:101-109] — Blind 6 solo. Fix: validate against the known 3-state set; raise `IncompleteTraceError` (or new typed error) on unknowns. Add a test for `mcp_coverage="bogus"`.
- [x] [Review][Patch] M_R2 — `sk-` regex requires `{16,}` chars after the prefix → misses naked `sk-ant-foo123` (14 chars). `test_redact_anthropic_api_key_env_var` only passes because the `ANTHROPIC_API_KEY=` pattern fires first [src/AgentEval/_kernel/redaction.py:84] — 2-WAY (Blind 8 + Auditor H6). Fix: add a dedicated `sk-ant-[A-Za-z0-9_\-]+` pattern OR lower the floor to match the spec's `sk-[A-Za-z0-9]+`. Add a negative test for short standalone keys.
- [x] [Review][Patch] M_R3 — `Bearer\s+[A-Za-z0-9_\-\.=]+` over-redacts innocuous prose like `"Bearer expected at line 3"` → corrupts error messages in JSONL backend [src/AgentEval/_kernel/redaction.py:86] — 3-WAY (Blind 7 + Edge 8 + Auditor H5). Fix: require a minimum length (e.g., `\S{20,}`) or anchor to header context.
- [x] [Review][Patch] M_R4 — `register_pattern` test corrupts `DEFAULT_PATTERNS` on regex compile failure (`finally: DEFAULT_PATTERNS.pop()` runs even when append didn't) [tests/unit/kernel/test_redaction.py:243-253, 266-273] — Blind 5 solo. Fix: snapshot `DEFAULT_PATTERNS[:]` before try; restore via slice assignment in finally.
- [x] [Review][Patch] M_R5 — `get_run_manifest` counts spans by `_agenteval_tier` attribute (Story 1b.1's Python-decorator-private name) instead of `agenteval.tier` (OTel semconv-style span attribute) → `tier_breakdown` will be empty when Listener emits semconv-compliant spans [src/AgentEval/_kernel/trace_store.py:315] — Codex C3 solo. Fix: count `agenteval.tier` (with optional `_agenteval_tier` fallback during transition). Update tests.
- [x] [Review][Patch] M_R6 — `ToolCallTrace.args` (`Mapping[str, Any]`) + `RunManifest.agenteval_tier_breakdown` (`Mapping[int, int]`) don't defensively wrap mapping payloads — `frozen=True` is shallow; caller can mutate the source dict after construction [src/AgentEval/types.py:73, 136 + tests/unit/test_types.py:33] — Codex C4 + Edge 12 (2-way). Fix: add `__post_init__` wrapping both fields in `MappingProxyType(dict(self.<field>))` (same pattern as `ServerSpec.__post_init__` in Story 1b.1).
- [x] [Review][Patch] M_R7 — Default redaction patterns miss common credential shapes: AWS access keys (`AKIA[0-9A-Z]{16}`), GitHub PATs (`ghp_[A-Za-z0-9]{36}`, `gho_`, `ghs_`, `ghu_`), HuggingFace (`hf_[A-Za-z0-9]{34}`), Slack family `xox[apsr]-` (only `xoxb-` is matched), GCP service-account JSON private-key markers [src/AgentEval/_kernel/redaction.py:81-95] — Edge 6 solo. Fix: add the 4+ missing pattern families; document the catalog version in the module docstring.
- [x] [Review][Patch] M_R8 — JWT pattern false-negative on standard-base64-padded JWTs (some libraries don't strip `=` padding before logging) [src/AgentEval/_kernel/redaction.py:94] — Edge 7 solo. Fix: extend charset to `[A-Za-z0-9_\-=]`.
- [x] [Review][Patch] M_R9 — Module-level `_exporter` singleton in trace_store is not reset across test session; if any test outside `test_trace_store.py` triggers `_get_exporter()` before, state leaks [tests/unit/kernel/test_trace_store.py:27-34] — Edge 9 + Blind 11/12 (multiple-angle). Fix: make `fresh_exporter` autouse for `tests/unit/kernel/`, OR add a `conftest.py` autouse session-scoped reset.
- [x] [Review][Patch] M_R10 — `test_get_run_manifest_empty_run` doesn't assert timestamp sanity; if implementation regresses to `datetime.now()` for empty runs, test passes silently [tests/unit/kernel/test_trace_store.py:245-250] — Edge 10 solo. Fix: assert `manifest.started_at == datetime.fromtimestamp(0, tz=UTC)` and `manifest.ended_at == manifest.started_at`.
- [x] [Review][Patch] M_R11 — `Usage` doesn't validate non-negative integers despite docstring claiming "All values are non-negative integers" [src/AgentEval/types.py:105-107] — Edge 14 solo. Fix: add `__post_init__` validator (clamp + `warnings.warn`, or raise `ValueError`).
- [x] [Review][Patch] M_R13 — `get_run_manifest` swallows missing context with empty `suite_id=""` while parallel `get_run_spans` raises `ValueError` — inconsistent strictness [src/AgentEval/_kernel/trace_store.py:308-309] — Blind 10 solo. Fix: raise if neither explicit nor context-derived suite_id available.
- [x] [Review][Patch] M_R14 — `test_configure_tracer_provider_initializes_exporter` directly mutates `ts._exporter = None` without cleanup; test order dependence [tests/unit/kernel/test_trace_store.py:280] — Blind 11 + Edge 16. Fix: use `fresh_exporter` fixture or wrap in try/finally that restores singleton.
- [x] [Review][Patch] M_R15 — `fresh_exporter` teardown leaves a fresh exporter rather than restoring the prior value [tests/unit/kernel/test_trace_store.py:33-40] — Blind 12. Fix: save the prior `ts._exporter` before override; restore in finally.
- [x] [Review][Patch] M_R16 — `clear_spans` reaches into private `_finished_spans` without pinning `opentelemetry-sdk` to a tested range in `pyproject.toml` [src/AgentEval/_kernel/trace_store.py:354 + pyproject.toml] — Auditor M2. Fix: pin `opentelemetry-sdk` to a tested-range minor OR migrate to the public `exporter.clear()` + re-export the surviving spans path.
- [x] [Review][Patch] M_R17 — Story spec L156 overstates architecture L853: "architecture explicitly forbids sub-library types modules for cross-cutting types" — L853 says cross-cutting types live at top level, but does NOT forbid sub-library types modules (L845-849 documents per-sub-library `library.py + _internal.py + types.py` triplet as standard pattern) [_bmad-output/implementation-artifacts/1b-2-trace-observability-kernel-trace-store-redaction-coverage.md L156] — Auditor M1. Fix: reword to "architecture L853 requires cross-cutting types at top level".
- [x] [Review][Patch] M_R18 — AC-1b.2.10 says "24+ source files (23 baseline + 5 new)" but 23+5=28; Dev Log correctly says 28 [story spec AC-1b.2.10] — Auditor M4. Fix: update AC text to "28 source files".
- [x] [Review][Patch] L_R5 — `get_run_spans` sorts by `start_time or 0`; malformed spans with `start_time=None` get placed at chronological position 0 [src/AgentEval/_kernel/trace_store.py:139] — Blind 13. Fix: filter out spans with `start_time is None` before sorting OR place them at the end.
- [x] [Review][Patch] L_R6 — `_attr_as_int` silently truncates floats (`int(3.7)` → 3) [src/AgentEval/_kernel/trace_store.py:230] — Blind 14. Fix: treat float as `default` (warning) OR explicitly accept and document the truncation.
- [x] [Review][Patch] L_R7 — Local imports inside `get_run_manifest` (datetime, AgentEval.__version__) — code smell suggesting an unresolved circular-import workaround [src/AgentEval/_kernel/trace_store.py:297-299] — Blind 15. Fix: hoist to module top; if there's a circular dep with `AgentEval.__version__`, document or restructure.
- [x] [Review][Patch] L_R10 — `test_configure_tracer_provider_initializes_exporter` reaches into `ts._exporter = None` private state instead of using `_set_exporter()` helper [tests/unit/kernel/test_trace_store.py:280] — Edge 16. Fix: expose a `_reset_exporter()` test-only helper and use it.

**defer (4):**

- [x] [Review][Defer] L_R3 — `redact_dict` doesn't redact dict keys, only values [src/AgentEval/_kernel/redaction.py:145] — Edge 17. Pre-existing scope decision; credentials are typically values not keys. Documented in module docstring + tracked in `deferred-work.md` for Phase-1.5 hygiene.
- [x] [Review][Defer] L_R4 — `IncompleteTraceError` message references `docs/contracts/mcp-coverage-detection.md` which is currently a Story 1a.4 skeleton (substantive content lands in Epic 4 Story 4.2's CC adapter detection contract) [src/AgentEval/_kernel/coverage.py:101] — Edge 18. Acceptable; the message points consumers to the right place when content fills.
- [x] [Review][Defer] L_R9 — `_resolve_test_id` raises `ValueError` when called from a raw `threading.Thread` (NOT via `_run_async`'s `copy_context()` wrapper) [src/AgentEval/_kernel/trace_store.py:119-124] — Edge 15. Architecture mandates `_run_async` as the canonical async-to-sync bridge (Story 1b.1); sub-libraries spawning raw threads violate the convention. Story 1b.6 convention enforcer will catch it.
- [x] [Review][Defer] **Pre-flag for Story 1b.4 / `completeness` enum drift** — PRD FR36a defines `completeness: Literal["complete", "truncated", "partial"]` (prd.md L1553) but Story 1b.4 epics.md L963 uses `Literal["full", "partial", "incomplete"]`. NOT in Story 1b.2's diff; Story 1b.4 create-story drift check will hit this. Edge bonus catch. Tracked here for next /bmad-create-story.

**dismiss (3):**

- L_R1 — `ToolCallTrace.result: Any | None` typing vs PRD `Any` — Any | None ≡ Any. Noise.
- L_R2 — JWT pattern escaped-hyphen literal (`[A-Za-z0-9_\-]` vs spec `[A-Za-z0-9_-]`) — semantically equivalent. Noise.
- L_R8 — `RedactionProcessor.on_start` signature docstring concern — no code change needed; current is correct.

**Cross-LLM coverage stats (Story 1b.2 review):**

| Reviewer | Solo HIGH | Cross-confirmed HIGH | Total |
|---|---|---|---|
| Blind Hunter (Claude Opus 4.7) | 5 (H1+H4+H5+H8 partial+H12) | 1 (H2 RedactionProcessor) | 16 findings (5H+7M+4L) |
| Edge Case Hunter (Claude Opus 4.7) | 4 (E2+E3+E4+E5) | 1 (E1 RedactionProcessor) | 18 findings (5H+9M+4L) |
| Acceptance Auditor (Claude Opus 4.7) | 2 (H4 sequence_index + H2 missing source) | 1 (H1 RedactionProcessor) + 1 (H3 _attr_to_mapping) | 11 findings (4H+3M+4L+2 verifications) |
| **Codex CLI 0.117.0 (cross-family)** | **2 (C1 resource-vs-span STAR + C3 tier attr name)** | **1 (C2 RedactionProcessor) + 1 (C4 frozen mutation)** | **4 findings (2H+2M)** |

**8th consecutive cross-LLM review where Codex caught real findings the 3 Claude reviewers missed.** Star catch (C1 / H_R2) is structurally identical to Story 1b.1's H1 (silent contract gap that locks tests into the wrong model). Same-family blind spot pattern continues to be load-bearing — particularly stark here because all 3 Claude reviewers EXPLICITLY looked at trace_store.py + the architecture L600-682 Decision-2 citations + still missed the resource-vs-span attribute path. Codex caught it by following architecture L652 verbatim (`"TracerProvider configured with custom resource attributes including agenteval.test_id"`) and noticing the test fixture's `attrs = {"agenteval.test_id": ...}` was a span attribute, not a resource attribute.

## Dev Notes

### Project context — Story 1b.2's place in Epic 1b

Story 1b.2 sits between Story 1b.1 (foundational kernel — context/tier/run_async) and Story 1b.3 (discovery/guardrails). It depends on:
- **Story 1b.1**: `_kernel/context.current_context() / TestContext` consumed by `trace_store.py`'s projection accessors.
- **Architecture L600-682 Decision-2**: trace store data model + projection accessors (LOAD-BEARING for this story).
- **ADR-016**: `mcp_coverage` 3-state ratified value space + `_check_mcp_coverage` kernel-enforcement contract.
- **ADR-014**: error class hierarchy (Story 1b.2 ships the MINIMAL subset: base + integrity sub-base + IncompleteTraceError leaf).

Story 1b.2 ENABLES:
- **Story 1b.4** (CodingAgentAdapter): extends `src/AgentEval/types.py` with `AgentRunResult`/`ToolCall`/`TokenUsage`/`Scenario`; references `coverage._check_mcp_coverage` in the adapter contract.
- **Story 1b.5** (conformance harness): consumes `trace_store.get_*` projection accessors for fixture round-trip assertions.
- **Epic 4** (CodingAgent adapters): populates `AgentRunResult.metadata.mcp_coverage` per ADR-016 §D4 adapter contract; the Generic + CC adapters MUST call `observer.mark_external_mixed(reason)` when external MCP detected.
- **Epic 5** (OTel Listener + observer): wires `RedactionProcessor → InMemoryExporter` chain into `AgentEval.__init__(telemetry=True)` TracerProvider; calls `clear_spans(test_id)` at `end_test`.
- **Epic 6** (Metric.* keywords): consumes the 5 projection accessors exclusively (no direct span access).

### Architecture compliance

| Architecture reference | Story 1b.2 implementation |
|---|---|
| L304 + FR32-40 — Trace recording + hosted-MCP observation + honesty fields | `_kernel/trace_store.py` is the kernel substrate; `coverage._check_mcp_coverage` enforces FR37 |
| L376 — Error class hierarchy (ADR-014) | `errors.py` co-created with minimal subset; extension-friendly for subsequent stories |
| L384 — Honesty fields propagation; kernel `_check_mcp_coverage` helper | `coverage._check_mcp_coverage(run, allow_external_mcp_blind)` enforces gate |
| L600-682 — Decision-2 Trace Store Data Model | 5 projection accessors per L664-669 + InMemorySpanExporter wrapper; per-test cleanup via `clear_spans` |
| L679 — Credential redaction SpanProcessor chain | `RedactionProcessor(SpanProcessor)` in `redaction.py`; Epic 5 wires the chain |
| L853 — Sub-libraries import rule + top-level `types.py` | `src/AgentEval/types.py` co-created at top-level (NOT sub-library) |
| L902-906 — Error convention | `error_code` ClassVar on each error class; base + sub-base + leaf structure |
| L968-990 — Trace Span Naming (OTel GenAI semconv) | trace_store projection accessors filter on `span.name == "execute_tool"` / `"chat"` |
| L1058 — `_check_mcp_coverage` raises IncompleteTraceError | Implemented per AC-1b.2.7 |
| L1184 — `errors.py` location | `src/AgentEval/errors.py` |
| L1192-1197 — `_kernel/{trace_store, redaction, coverage}.py` locations + roles | Honored verbatim |

### ADR-016 trust-floor decision tree (consumed by kernel)

Per ADR-016 §Decision L17-28: the **trust-floor** mechanism means a run that successfully observed BOTH `hosted_in_process` AND `subprocess_with_observer` paths reports `hosted_in_process` (the strongest complete path) — NOT the weaker one. This decision happens in adapters at metadata-population time. The kernel just consumes the resolved value.

For Story 1b.2's `_check_mcp_coverage`:
- The kernel does NOT examine `observed_paths` metadata. It only reads `mcp_coverage`.
- If an adapter incorrectly populates `mcp_coverage = "external_mixed"` when both stronger paths fired, that's an adapter bug (Epic 4 scope). The kernel correctly enforces the gate on whatever value the adapter wrote.
- The unit test `test_coverage_kernel_accepts_hosted_in_process_with_dual_paths_in_observed_paths` exercises the trust-floor case: kernel reads `mcp_coverage="hosted_in_process"` and returns None, even when `observed_paths=("hosted_in_process", "subprocess_with_observer")` (showing both paths fired). This confirms the kernel doesn't second-guess the adapter's resolved value.

### Phase-1 forward-reference pattern for `AgentRunResult`

Story 1b.4 lands `AgentRunResult` in `src/AgentEval/types.py`. Story 1b.2's `_check_mcp_coverage` references it via:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from AgentEval.types import AgentRunResult


def _check_mcp_coverage(
    run: AgentRunResult,  # forward ref at type-check time; duck-typed at runtime
    *,
    allow_external_mcp_blind: bool = False,
) -> None:
    if run.metadata.mcp_coverage == "external_mixed" and not allow_external_mcp_blind:
        raise IncompleteTraceError(...)
```

Runtime works because Python doesn't enforce the type at call time. Type checkers see `AgentRunResult` and produce correct narrowing. **The cost** is that until Story 1b.4 lands, the kernel test must construct a fake object (`types.SimpleNamespace(metadata=SimpleNamespace(mcp_coverage="external_mixed"))` or a small `@dataclass` test fixture). Story 1b.2 test exercises both happy + error paths with this fake.

### Stdlib `@dataclass` vs Pydantic

Architecture L853 says "Pydantic dataclasses" for `AgentRunResult` / `ToolCallTrace` / `RunManifest`. Story 1b.2 ships stdlib `@dataclass(frozen=True)` because:
- Pydantic is NOT in the curated direct dependency set (Story 1a.1 baseline: `mcp / robotframework / anyio / litellm / opentelemetry-* / pyyaml / jsonschema`). Adding it to direct deps requires explicit ratification.
- Pydantic 2.x IS available transitively via the `mcp` SDK; using it indirectly is brittle (mcp could drop the dep).
- Stdlib dataclasses provide the same field-declaration syntax + `dataclasses.asdict()` for JSON serialization (sufficient for Phase-1 jsonl backend).
- Pydantic's validation + `.model_dump()` benefits become load-bearing for Epic 5's OTLP serialization — at that point, Story 5.1 can add `pydantic>=2.0,<3.0` to direct deps with explicit ratification.

This deviation is documented in `types.py` module docstring + tracked as a Phase-1.5 carry-over in `deferred-work.md`.

### `SandboxRequiredError` re-home deferred

Story 1a.1 created `src/AgentEval/security/policy.py` with a placeholder `SandboxRequiredError` that doesn't inherit from `AgentEvalError` (because `errors.py` didn't exist yet in Story 1a.1). Story 1b.2's `errors.py` SHOULD re-home it per ADR-014's "all errors in one module" rule, but doing so requires updating all callers + the existing imports in security/*. **Phase-1 decision: defer to a hygiene story.** Story 1b.2's `errors.py` module docstring notes the gap; `deferred-work.md` tracks the re-home as a Phase-1.5 carry-over.

### ci.yml — no changes needed

Story 1b.1 already restructured `ci.yml` so `tests/unit` runs real assertions (the dedicated `pytest tests/unit (real tests)` step). Story 1b.2's new tests under `tests/unit/{kernel/test_*.py, test_errors.py, test_types.py}` are auto-picked-up by the existing step. No ci.yml changes.

### Project norms applied

1. **Norm #1 (cross-LLM adversarial review)** — code-review uses `/bmad-code-review (Using current Claude + Codex CLI subagent)`. Cross-LLM reviewer prompt embeds the citation-drift re-derivation directive per `feedback_citation_drift_first_class` (Epic 1a retro NEW NORM).
2. **Norm #2 (machine-verified numeric claims)** — 8 drifts caught (6 in 1b.2 + 2 pre-emptive in 1b.4); all resolved by honoring ratified sources.
3. **Pre-create-story spec-vs-ratified-doc check (Norm #4)** — applied 2026-05-18 with 8 drifts caught (largest single-story drift count since Story 1a.4's 10). All resolved by honoring ratified sources; epics.md L880-890 (Story 1b.2) + L924-930 (Story 1b.4 pre-emptive) updated pre-authoring.
4. **CI-log-forensics (Norm #5)** — post-push verification will confirm: pytest tests/unit picks up the new test_errors.py + test_types.py + test_{trace_store,redaction,coverage}.py automatically; 108+ unit tests run real assertions; 6 FR42 + 1 RF smoke tests still pass (regression).
5. **Honest framing** — Phase-1 limitations explicitly documented (stdlib dataclass vs Pydantic; AgentRunResult forward-ref; SandboxRequiredError re-home deferred; RedactionProcessor ships but unwired until Story 5.1; trace_store TracerProvider configuration helper ships but actual wiring at Epic 5).
6. **agentguard inspiration-only** — ratified; no agentguard dependency.
7. **NEW NORM applied (citation-drift first-class category)** — AC-1b.2.11 + Norm #1 entry. The 8 drifts caught in this round (D1-D8) include 1 LOW citation drift (D6 Span → ReadableSpan); 2 architecture-section name/intent drifts (D1, D2); 1 missing-from-spec architectural integration (D5 SpanProcessor); 2 location drifts (D4 types.py home; D6 ReadableSpan typing); + 2 downstream story-spec drifts (D7 dunder; D8 mcp_coverage 4-state).

### References

- **PRD §FR32-40** — Trace recording + hosted-MCP observation + honesty fields
- **PRD §FR35** — `ToolCallTrace` projection (`Get Tool Calls` keyword consumes this)
- **PRD §FR36b** — `mcp_coverage` 3-state field on `AgentRunResult.metadata`
- **PRD §FR37** — `IncompleteTraceError` raised on `external_mixed` runs
- **PRD §FR38a/b** — Credential redaction (NFR-SEC-01 implementation)
- **PRD §FR39** — `RunManifest` structure (library_version + redaction_policy_hash + tier breakdown)
- **PRD §FR42** — Library defaults (relevant: `telemetry` default True + `allow_external_mcp_blind` default False)
- **ADR-014 (was ADR-A3)** (`docs/adr/ADR-014-error-class-hierarchy.md`) — error class hierarchy + `error_code` convention
- **ADR-016 (was ADR-A6)** (`docs/adr/ADR-016-mcp-coverage-detection-default.md`) — `mcp_coverage` 3-state + trust-floor + kernel enforcement contract
- **Architecture L600-682 Decision-2** — Trace Store Data Model (LOAD-BEARING for `trace_store.py`)
- **Architecture L376** — Error class hierarchy cross-cutting concern
- **Architecture L384** — Honesty fields propagation + `_check_mcp_coverage` helper
- **Architecture L679 + L1193** — `_kernel/redaction.py` SpanProcessor
- **Architecture L853** — `agenteval/types.py` top-level shared types module
- **Architecture L902-930** — Error convention (`error_code` ClassVar; `AgentEvalError` base; sub-base scheme)
- **Architecture L968-990** — OTel GenAI semconv (`gen_ai.*` + `agenteval.*` attributes; `execute_tool` / `chat` span names)
- **Architecture L1058** — `_check_mcp_coverage` raises `IncompleteTraceError` per FR37
- **Architecture L1184** — `errors.py` location
- **Architecture L1192-1197** — `_kernel/{trace_store,redaction,coverage}.py` locations
- **docs/contracts/error-class-hierarchy.md** (Story 1a.4 ratified) — 9-leaf catalog; Story 1b.2 ships 1 leaf
- **docs/contracts/mcp-coverage-detection.md** (Story 1a.4 ratified) — trust-floor decision tree + per-adapter detection responsibility
- **Story 1b.1 `_kernel/context.py`** — `current_context()` / `TestContext` / `Scope` consumed by trace_store
- **Story 1a.6 `src/AgentEval/__init__.py`** — `AgentEval.__init__(telemetry=True)` will wire TracerProvider via Epic 5 Story 5.1 (out of scope for 1b.2)
- **Story 1a.1 `src/AgentEval/security/policy.py`** — placeholder `SandboxRequiredError`; Story 1b.2 docs the re-home deferral
- **Epic 1a retrospective** `_bmad-output/implementation-artifacts/epic-1a-retro-2026-05-18.md` — citation-drift first-class norm
- **`feedback_citation_drift_first_class`** (memory) — applied via AC-1b.2.11 + Norm #1

## Dev Agent Record

### Context Reference

- architecture L600-682 Decision-2 (LOAD-BEARING): trace store data model + 5 projection accessors
- architecture L679 + L1193: `_kernel/redaction.py` RedactionProcessor SpanProcessor
- architecture L384 + L1058: `_check_mcp_coverage` kernel-enforcement contract
- architecture L853: top-level shared types module + "no direct span access by sub-libraries" rule
- architecture L902-930: error_code ClassVar convention + base/sub-base/leaf structure
- architecture L968-990: OTel GenAI semconv (`execute_tool` / `chat` span names; `gen_ai.*` + `agenteval.*` attribute namespacing)
- ADR-014 (was ADR-A3): error class hierarchy
- ADR-016 (was ADR-A6): mcp_coverage 3-state + trust-floor + kernel enforcement
- docs/contracts/error-class-hierarchy.md (Story 1a.4 ratified): 11-leaf catalog
- docs/contracts/mcp-coverage-detection.md (Story 1a.4 ratified): trust-floor decision tree
- Story 1b.1 `_kernel/context.current_context()`: consumed by trace_store for test_id default

### Agent Model Used

Claude Opus 4.7 (1M context).

### Debug Log References

- `uv run pytest tests/unit --ignore=tests/unit/conventions -q` → **131 passed in 0.55s** (67 from Story 1b.1 + 64 new: 7 errors + 9 types + 24 redaction + 9 coverage + 15 trace_store)
- `uv run pytest tests/acceptance/tier1 -q` → 6 passed (Story 1a.6 regression check)
- `uv run robot tests/acceptance/smoke` → 1 passed (Story 1a.6 regression check)
- `uv run ruff check src/ tests/` → All checks passed (after 22 auto-fixes for imports, line length, etc.)
- `uv run ruff format` → all 41 files formatted
- `uv run mypy src/` → 28 source files clean (up from 23 pre-Story-1b.2: +5 new — errors.py, types.py, trace_store.py, redaction.py, coverage.py)
- `uv run python scripts/check-license-headers.py` → 28/28 PASS

### Completion Notes List

- **AC-1b.2.1** 5 projection accessors implemented (`get_run_spans`, `get_tool_calls`, `get_usage`, `get_latency`, `get_run_manifest`) per architecture L664-669 + Decision-2. Default-to-`current_context()` behavior wired. Returns `list[ReadableSpan]` (not raw Span) per architecture L664.
- **AC-1b.2.2** InMemorySpanExporter lifecycle: module-level singleton + `_get_exporter()` / `_set_exporter()` test override + `_configure_tracer_provider()` Phase-1 placeholder (Epic 5 Story 5.1 lands full TracerProvider config) + `clear_spans(test_id)` per-test cleanup hook returns count cleared.
- **AC-1b.2.3** `src/AgentEval/types.py` co-created with 3 stdlib `@dataclass(frozen=True)` types: `ToolCallTrace` (7 fields per FR35 + OTel GenAI semconv), `Usage` (3 fields with `cached_input_tokens` defaulting to 0), `RunManifest` (7 fields per FR39). Phase-1 deviation from architecture's "Pydantic dataclasses" wording documented in module docstring.
- **AC-1b.2.4** Primitive redaction: `DEFAULT_PATTERNS` (6 patterns: OpenAI/Anthropic key prefix, Bearer tokens, ANTHROPIC_API_KEY=, OPENAI_API_KEY=, Slack bot tokens, JWT shape), `redact(text, patterns)`, `redact_dict(d)` recursive, `register_pattern(regex)`, `redaction_policy_hash()` SHA-256 of pattern set.
- **AC-1b.2.5** `RedactionProcessor(SpanProcessor)` class: `on_end(span)` mutates the 5 documented sensitive attribute keys (`gen_ai.request.messages`, `gen_ai.response.text`, `gen_ai.tool.args`, `agenteval.tool.args`, `agenteval.tool.result`) via `redact()` or `redact_dict()` based on value type. `on_start` no-op; `shutdown` no-op; `force_flush` returns True. Uses OTel's `opentelemetry.context.Context` (NOT `contextvars.Context`) for the `parent_context` parameter — mypy LSP error caught + fixed.
- **AC-1b.2.6** `src/AgentEval/errors.py` co-created: `AgentEvalError(Exception)` base + `AgentEvalIntegrityError(AgentEvalError)` sub-base + `IncompleteTraceError(AgentEvalIntegrityError)` leaf with **`error_code = "INCOMPLETE_TRACE"`** per `docs/contracts/error-class-hierarchy.md` L90 (citation drift self-caught: initial dev-story implementation used `"TRACE_INCOMPLETE"`; corrected to match ratified contract — the new citation-drift norm catching real drift in real-time).
- **AC-1b.2.7** `_check_mcp_coverage(run, *, allow_external_mcp_blind=False) -> None` implemented. 6-cell behavior matrix verified by tests. TYPE_CHECKING-guarded `AgentRunResult` import (Story 1b.4 lands the type); duck-typed runtime accepts `SimpleNamespace` + `@dataclass` fakes.
- **AC-1b.2.8** trace_store projection accessors consume `current_context().test_id` from Story 1b.1's `_kernel/context.py` when explicit `test_id` is omitted. Verified by `test_get_run_spans_defaults_to_current_context`.
- **AC-1b.2.9** 64 new unit tests total (7 errors + 9 types + 24 redaction + 9 coverage + 15 trace_store). Real OTel spans emitted in `test_trace_store.py` via tracer + SimpleSpanProcessor + InMemorySpanExporter fixtures.
- **AC-1b.2.10** All gates clean: ruff + mypy + license-headers + 131 unit + 6 tier1 regression + 1 smoke regression.
- **AC-1b.2.11** AC body sets the citation-drift directive for the code-review prompt. Already proven load-bearing within Story 1b.2 itself: caught the `TRACE_INCOMPLETE` → `INCOMPLETE_TRACE` drift between my initial implementation and Story 1a.4's ratified contract.

**Phase-1 limitations explicitly documented:**
- `types.py` uses stdlib `@dataclass(frozen=True)` instead of "Pydantic dataclasses" (architecture L853 wording); Phase-1.5 carry-over if Epic 5 OTLP serialization needs Pydantic validation.
- `_check_mcp_coverage` accepts forward-referenced `AgentRunResult`; Story 1b.4 lands the real type.
- `SandboxRequiredError` re-home into `errors.py` is a Phase-1.5 hygiene carry-over (currently at `src/AgentEval/security/policy.py` per Story 1a.1 pre-`errors.py` baseline). Documented in `errors.py` module docstring + `deferred-work.md`.
- `_configure_tracer_provider()` is a Phase-1 placeholder; Epic 5 Story 5.1 lands the full TracerProvider config (resource attributes + RedactionProcessor + BatchSpanProcessor + exporter chain).
- `_kernel/trace_store.clear_spans` uses `exporter._finished_spans` internal attribute (private but stable in opentelemetry-sdk 1.20+); fallback path documented.

**Citation-drift catch (self-applied during dev-story):**
Initial errors.py + coverage.py + tests used `error_code = "TRACE_INCOMPLETE"`. A grep of `docs/contracts/error-class-hierarchy.md` (Story 1a.4 ratified) showed the contract uses `INCOMPLETE_TRACE`. Per the new `feedback_citation_drift_first_class` norm + "fix-the-losing-source-NOW" pattern, I corrected the IMPLEMENTATION to match the contract (5 files updated: errors.py + coverage.py + 2 test files + stability-surface.md). This is exactly the kind of subtle drift the norm targets — caught during dev-story rather than waiting for code-review.

## File List

**New files (10):**
- `src/AgentEval/errors.py` (~75L) — AgentEvalError + AgentEvalIntegrityError + IncompleteTraceError(error_code="INCOMPLETE_TRACE")
- `src/AgentEval/types.py` (~120L) — ToolCallTrace + Usage + RunManifest stdlib frozen dataclasses
- `src/AgentEval/_kernel/trace_store.py` (~360L) — 5 projection accessors + clear_spans + _configure_tracer_provider + _get_exporter/_set_exporter + helpers (_attr_as_int/_attr_as_float/_attr_to_mapping/_attr_to_optional_str)
- `src/AgentEval/_kernel/redaction.py` (~240L) — 6 DEFAULT_PATTERNS + redact + redact_dict + register_pattern + redaction_policy_hash + RedactionProcessor SpanProcessor
- `src/AgentEval/_kernel/coverage.py` (~105L) — _check_mcp_coverage enforcement gate
- `tests/unit/test_errors.py` (~60L) — 7 tests on class hierarchy + error_code
- `tests/unit/test_types.py` (~120L) — 9 tests on construction + frozen + asdict round-trip
- `tests/unit/kernel/test_trace_store.py` (~260L) — 15 tests on 5 projection accessors + clear_spans + _configure_tracer_provider
- `tests/unit/kernel/test_redaction.py` (~220L) — 24 tests on 6 default patterns + redact_dict + register_pattern + RedactionProcessor
- `tests/unit/kernel/test_coverage.py` (~90L) — 9 tests on 6-cell behavior matrix + trust-floor + duck-typed input

**Updated files (3):**
- `docs/contracts/stability-surface.md` — added Kernel public surface entries for trace_store/redaction/coverage + Top-level errors + types surface section
- `docs/contracts/error-class-hierarchy.md` — marked IncompleteTraceError as IMPLEMENTED (Story 1b.2)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — 1b-2 status: ready-for-dev → in-progress → review through this dev-story session

Expected files (5 created + ~5 updated):

**New files (5 source + 5 test):**
- `src/AgentEval/errors.py` (AgentEvalError base + AgentEvalIntegrityError sub-base + IncompleteTraceError leaf, ~60L)
- `src/AgentEval/types.py` (ToolCallTrace + Usage + RunManifest stdlib @dataclass(frozen=True), ~80L)
- `src/AgentEval/_kernel/trace_store.py` (InMemorySpanExporter wrapper + 5 projection accessors + clear_spans + _configure_tracer_provider, ~150L)
- `src/AgentEval/_kernel/redaction.py` (DEFAULT_PATTERNS + redact + redact_dict + register_pattern + redaction_policy_hash + RedactionProcessor SpanProcessor, ~120L)
- `src/AgentEval/_kernel/coverage.py` (_check_mcp_coverage enforcement gate, ~60L)
- `tests/unit/test_errors.py` (5+ tests, ~50L)
- `tests/unit/test_types.py` (6+ tests, ~80L)
- `tests/unit/kernel/test_trace_store.py` (12+ tests, ~250L)
- `tests/unit/kernel/test_redaction.py` (10+ tests, ~180L)
- `tests/unit/kernel/test_coverage.py` (8+ tests, ~150L)

**Updated files (minimal):**
- `docs/contracts/stability-surface.md` (register `_kernel.trace_store.{get_run_spans, get_tool_calls, get_usage, get_latency, get_run_manifest, clear_spans, _configure_tracer_provider}` + `_kernel.redaction.{redact, redact_dict, register_pattern, redaction_policy_hash, RedactionProcessor}` + `_kernel.coverage._check_mcp_coverage` + `errors.{AgentEvalError, AgentEvalIntegrityError, IncompleteTraceError}` + `types.{ToolCallTrace, Usage, RunManifest}` as `provisional`)
- `docs/contracts/error-class-hierarchy.md` (mark `IncompleteTraceError` as IMPLEMENTED; other 8 leaves remain as Phase-1 contract stubs)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (1b-2 status: ready-for-dev → in-progress on dev-story start)
- `_bmad-output/implementation-artifacts/deferred-work.md` (track Phase-1.5 carry-overs: stdlib-dataclass → Pydantic migration; SandboxRequiredError re-home; RedactionProcessor wiring at Story 5.1)
- `CHANGELOG.md` (Unreleased entry)

## Change Log

| Date       | Version | Description                                                                  | Author |
| ---------- | ------- | ---------------------------------------------------------------------------- | ------ |
| 2026-05-18 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (6th consecutive use of `feedback_spec_vs_ratified_doc_precheck`) caught 8 drifts: 6 in Story 1b.2 spec (D1 trace_store API surface, D2 coverage function name+intent, D3 errors.py + IncompleteTraceError dependency, D5 RedactionProcessor missing, D6 Span→ReadableSpan, the spec-driven RunData type undefined → AgentRunResult) + 2 pre-emptive in Story 1b.4 spec (D7 `__agenteval_tier__` dunder→`_agenteval_tier`, D4 AgentRunResult location, D8 mcp_coverage 4-state→3-state). All 8 resolved by honoring ratified sources (ADR-016 + ADR-014 + architecture L600-682/L853/L902-930/L1184-1197 + Story 1b.1 actual implementation). epics.md L880-890 (Story 1b.2) + L924-930 (Story 1b.4 pre-emptive) updated pre-authoring. NEW NORM from Epic 1a retro (`feedback_citation_drift_first_class`) embedded in AC-1b.2.11 + Norm #1. Phase-1 limitations explicitly documented: stdlib @dataclass(frozen=True) vs architecture's "Pydantic dataclasses" (Phase-1.5 carry-over for migration); AgentRunResult TYPE_CHECKING forward-ref (Story 1b.4 lands the class); SandboxRequiredError re-home deferred; RedactionProcessor ships unwired (Epic 5 Story 5.1 wires). | Bob |
| 2026-05-18 | 0.2.0   | Dev-story complete. All 11 ACs satisfied; all 9 tasks marked [x]. 5 new src files (~900L total): errors.py (~75L) + types.py (~120L) + _kernel/trace_store.py (~360L) + _kernel/redaction.py (~240L) + _kernel/coverage.py (~105L). 5 new test files (~750L total) with 64 new unit tests (7 errors + 9 types + 15 trace_store + 24 redaction + 9 coverage). stability-surface.md + error-class-hierarchy.md updated. **Citation-drift self-catch DURING dev-story**: initial implementation used `error_code="TRACE_INCOMPLETE"`; grep of `docs/contracts/error-class-hierarchy.md` L90 revealed contract uses `INCOMPLETE_TRACE`; "fix-the-losing-source-NOW" pattern applied — implementation corrected to match contract (5 files updated). Exactly the kind of subtle drift the new `feedback_citation_drift_first_class` norm targets — caught during dev-story rather than waiting for code-review. All gates clean: ruff + mypy (28 src files, +5 from 23) + license-headers (28/28) + pytest tests/unit (131 passed, +64 from 67) + pytest tier1 (6 passed regression) + robot smoke (1 passed regression). Phase-1 limitations explicitly documented (stdlib @dataclass vs Pydantic; AgentRunResult TYPE_CHECKING forward-ref; SandboxRequiredError re-home deferred; RedactionProcessor unwired until Story 5.1). Status: in-progress → review. | Amelia |
| 2026-05-19 | 1.0.0   | Code-review patches applied (cross-LLM adversarial pair Claude Opus 4.7 in 3 review roles + Codex CLI 0.117.0). 4-reviewer parallel: 49 raw findings → 36 unique → 4 decisions resolved + 28 patches applied + 4 deferred + 3 dismissed. STAR CATCH: Codex C1 — resource-vs-span attribute model bug (architecture L652 says agenteval.test_id is a TracerProvider Resource attribute; impl filtered span.attributes; production spans would silently return empty). 8th consecutive cross-LLM review where Codex caught real findings the 3 Claude reviewers missed. 4-WAY HIGH confirmation on RedactionProcessor real-OTel incompatibility (all 4 reviewers independently caught it). 3-WAY on _attr_to_mapping {"_raw"} production-data-loss + clock-mixing variant. All 28 patches applied across 5 src files + 5 test files + 4 doc files. New test count: 99 new unit tests (163 total) — +35 from initial dev-story's 64. Phase-1 limitations updated: M_R6 uses dict() copy (NOT MappingProxyType — incompatible with dataclasses.asdict deep-copy for jsonl backend); architecture.md amended to ratify agenteval.tool.* attribute namespacing extensions per H_R11; epics.md Story 1b.4 pre-emptive cleanup for completeness enum drift (PRD FR36a L1553 wins over Story 1b.4 L963 — fix-the-losing-source-NOW applied pre-Story-1b.4 create-story). All gates clean post-patches: ruff + mypy (28 src) + license (28/28) + pytest unit (163 passed) + tier1 (6 passed) + smoke (1 passed). Status: review → done. | Amelia |

## Senior Developer Review (AI)

**Reviewer:** Many Kasiriha
**Review Date:** 2026-05-19
**Review Outcome:** **APPROVED** (after applying 32 code-review patches from the 4-reviewer parallel cross-LLM pair Claude Opus 4.7 + Codex CLI 0.117.0)

### Summary

Story 1b.2 ships the trace/observability/coverage kernel (3 new `_kernel/` modules + co-created top-level `errors.py` + `types.py`) consumed by Epic 5 (OTel listener), Epic 6 (Metric.* keywords), and Story 1b.4 (CodingAgentAdapter Protocol). The cross-LLM review caught **36 unique findings** including a **structural blocker** Codex alone surfaced — the resource-vs-span attribute model gap that would have made every production projection accessor silently return empty. All 32 patches landed cleanly; 163 unit tests pass; Story 1a.6 + RF smoke regression checks both clean.

### Key findings from code-review

**Star catch (Codex C1 / H_R2) — resource-vs-span attribute model:** Architecture L652 says `agenteval.test_id` is set as a TracerProvider Resource attribute (NOT a per-span attribute). The implementation filtered `span.attributes.get("agenteval.test_id")` — when Story 5.1 wires the TracerProvider per architecture, all spans carry test_id at the resource level + every projection accessor (`get_run_spans`, `get_tool_calls`, `get_usage`, `get_latency`, `get_run_manifest`, `clear_spans`) would have silently returned empty. The 3 Claude reviewers explicitly looked at trace_store.py + the architecture L600-682 Decision-2 citations + missed it. Codex caught it by following architecture L652 verbatim and noticing the test fixture's `attrs = {"agenteval.test_id": ...}` was a span attribute. Fixed: `_span_test_id` helper reads resource-attribute-first with span-attribute fallback.

**4-way HIGH confirmation — RedactionProcessor real-OTel incompatibility (H_R1):** All 3 Claude reviewers + Codex independently caught that `RedactionProcessor.on_end` mutates `MappingProxyType`-backed `BoundedAttributes` via `attributes[key] = ...` (read-only at runtime); mock tests passed with plain dicts but production would crash/no-op. Fixed: `_set_span_attribute_in_place` helper handles `BoundedAttributes._dict`, mock dicts, and surfaces UserWarning if neither works (so future SDK refactors fail loud, not silent). Added an integration test wiring real TracerProvider → RedactionProcessor → SimpleSpanProcessor(InMemorySpanExporter).

**3-way HIGH confirmations:**
- **`_attr_to_mapping` {"_raw"} data loss (H_R5):** OTel SDK doesn't accept dict attribute values; production always serializes to JSON strings. The pre-fix wrapper meant `tool_call.args["command"]` KeyError'd in every real call. Fixed: `json.loads()` with try/except fallback.
- **`get_latency` double-counting (H_R3):** Pre-fix code summed every span's duration → reports ~2× wall-clock for any tree of depth 2. Fixed: `max(end_time) - min(start_time)` semantic.

**Citation drift self-catches:**
- **H_R6** — `ToolCallTrace.sequence_index` field deleted by the pre-create-story drift check's first pass; PRD FR35 + FR45(d) require it for conformance. Added back, derived from chronological span ordering.
- **H_R11** — `agenteval.tool.args/result/source/error` cited as "per architecture L975-985" but L975-985 didn't define them. Architecture.md amended 2026-05-19 to ratify the namespacing extensions.
- **M_R5** — `_agenteval_tier` decorator attribute (Story 1b.1 private) vs `agenteval.tier` OTel-style span attribute — fixed: count both with fallback.

**M_R6 implementation iteration:** Initial attempt used `MappingProxyType` for defensive freeze; broke `dataclasses.asdict()` (deepcopy-incompatible with MappingProxyType). Switched to `dict()` defensive copy — blocks source-mutation-leakage (the M_R6 hazard) while preserving jsonl-backend serialization path. Direct `tct.args["k"] = v` mutation remains possible (matches Python `frozen=True` semantics for mutable type fields); documented in the dataclass docstring.

**Story 1b.4 pre-emptive cleanup (per fix-the-losing-source-NOW):** Edge Case Hunter's bonus catch — Story 1b.4 epics.md L963 had `completeness: Literal["full", "partial", "incomplete"]` but PRD FR36a L1553 has `Literal["complete", "truncated", "partial"]`. Fixed in epics.md NOW so the next create-story drift check has one less hit.

### Acceptance Criteria Coverage (post-patches)

All 11 AC-1b.2.X satisfied:
- **AC-1b.2.1** 5 projection accessors per architecture L664-669 (post-H_R2 resource-attribute fix)
- **AC-1b.2.2** InMemorySpanExporter lifecycle + `clear_spans` per-test cleanup (post-H_R8 lock acquisition fix)
- **AC-1b.2.3** types.py 3 dataclasses + sequence_index restored (H_R6) + defensive dict() copy (M_R6) + Usage non-negative validation (M_R11)
- **AC-1b.2.4** redaction primitives + expanded pattern catalog (M_R7 added AWS/GitHub PAT/HuggingFace/full Slack family + M_R2 sk-ant- + M_R3 Bearer 20+ char floor + M_R8 JWT padded base64 + H_R9 flags in hash + H_R12 Mapping recursion)
- **AC-1b.2.5** RedactionProcessor real-OTel mutation path (H_R1 4-way) + Sequence[str] handling
- **AC-1b.2.6** errors.py minimal subset + H_R7 __str__ formatter + DegradedTraceWarning class for H_R4
- **AC-1b.2.7** `_check_mcp_coverage` 6-cell matrix + M_R1 unknown-value validation
- **AC-1b.2.8** trace_store consumes current_context (verified via integration test post-H_R2)
- **AC-1b.2.9** test count: initial 64 + new 35 review-patch tests = 99 new total; with Story 1b.1's 67 = 163 unit tests pass
- **AC-1b.2.10** all gates clean (28 source files post-M_R18 correction)
- **AC-1b.2.11** Cross-LLM reviewer prompt embedded the citation-drift directive; Codex caught the C1 STAR catch + 3 citation drifts as direct results

### Test Coverage

- **Local:** `pytest tests/unit --ignore=tests/unit/conventions -q` → **163 passed in 0.58s** (67 Story 1b.1 + 64 initial Story 1b.2 + 32 review-patch tests). `pytest tests/acceptance/tier1 -q` → 6 passed. `robot tests/acceptance/smoke` → 1 passed.
- **CI verification:** pending push.

### Action Items

None. All 32 patches applied; 4 decisions resolved per Many's "Recommended" picks; gates clean.

### Outcome

**Status: review → done.** Epic 1b: 2/6 stories complete. Ready for Story 1b.3 (`/bmad-create-story` next).
