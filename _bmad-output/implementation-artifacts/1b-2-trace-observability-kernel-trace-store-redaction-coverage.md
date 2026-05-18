# Story 1b.2: Trace + Observability Kernel — Trace Store + Redaction + Coverage

Status: ready-for-dev

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

3. **AC-1b.2.3 — `src/AgentEval/types.py` co-created with 3 Phase-1 dataclasses per architecture L853.** Top-level shared-types module (architecture explicitly forbids sub-library types modules for cross-cutting types). Uses **stdlib `@dataclass(frozen=True)`** for Phase-1 minimalism (architecture L853 wording is "Pydantic dataclasses"; Phase-1 deviation documented in module docstring + Phase-1.5 carry-over to migrate if FR39 OTLP serialization needs Pydantic validation). Types:
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

10. **AC-1b.2.10 — All-gates clean.** `uv run ruff check src/ tests/` clean; `uv run ruff format --check src/ tests/` clean; `uv run mypy src/` clean (24+ source files: previous 23 + new errors.py + types.py + trace_store.py + redaction.py + coverage.py); `uv run python scripts/check-license-headers.py` PASS; `uv run pytest tests/unit -q --ignore=tests/unit/conventions` — all kernel unit tests pass (existing 67 from Story 1b.1 + new ~41+ from Story 1b.2 = 108+); `uv run pytest tests/acceptance/tier1 -q` — Story 1a.6's 6 FR42 tests still pass (regression); `uv run robot tests/acceptance/smoke` — RF smoke test still passes (regression).

11. **AC-1b.2.11 — Code-review prompt embeds the citation-drift re-derivation directive (Epic 1a retro NEW NORM / `feedback_citation_drift_first_class`).** When `/bmad-code-review (Using current Claude + Codex CLI subagent)` runs for Story 1b.2, the cross-LLM reviewer prompt MUST direct: *"For every citation in the changed files — 'per ADR-016 L44', 'per FR37', 'per architecture L664-669', 'per OTel GenAI semconv L975-985', 'per ADR-014 L902-906', 'per spike findings §Y', etc. — open the cited source and verify the claim is EXACTLY what the source says. Flag any mismatches even if subtle (rename, count drift, slug drift, off-by-one line numbers, attribute-name drift)."* Citation drift was the #1 finding category across Epic 1a; Story 1b.1's code review demonstrated this norm caught real drift again (M4 ADR-012 + ADR-015 filename drift).

## Tasks / Subtasks

- [ ] **Task 1: Author `src/AgentEval/errors.py` MINIMAL subset (AC: 1b.2.6)**
  - [ ] Apache 2.0 license header.
  - [ ] Module docstring citing ADR-014 (was ADR-A3) + architecture L376/L902-930 + Story 1a.4's `docs/contracts/error-class-hierarchy.md`.
  - [ ] `AgentEvalError(Exception)` base class with `error_code: str = ""` ClassVar default + `__init__` that captures message + formats `error_code: <msg>` in `__str__`.
  - [ ] `AgentEvalIntegrityError(AgentEvalError)` sub-base — no override; inherits everything from base. Documented as the trace/run-integrity-class sub-base.
  - [ ] `IncompleteTraceError(AgentEvalIntegrityError)` leaf — `error_code: ClassVar[str] = "TRACE_INCOMPLETE"`.
  - [ ] Module docstring includes the placeholder note about `SandboxRequiredError` currently living at `src/AgentEval/security/policy.py` (Story 1a.1 baseline) NOT inheriting from `AgentEvalError`; Phase-1 deferred-work item to re-home it.
  - [ ] Verify with `uv run mypy src/AgentEval/errors.py`.

- [ ] **Task 2: Author `src/AgentEval/types.py` 3 Phase-1 dataclasses (AC: 1b.2.3)**
  - [ ] Apache 2.0 license header.
  - [ ] Module docstring citing architecture L853 (shared types live here); FR35 + FR39; OTel GenAI semconv at architecture L975-985; Phase-1 stdlib `@dataclass(frozen=True)` deviation from architecture's "Pydantic dataclasses" wording (Phase-1 minimalism; migration is a Phase-1.5 carry-over if needed for Epic 5 OTLP).
  - [ ] `ToolCallTrace` dataclass with the 7 fields per AC-1b.2.3. Mapping-typed `args` accepts `dict` at construction; immutable post-construction.
  - [ ] `Usage` dataclass with the 3 fields per AC-1b.2.3.
  - [ ] `RunManifest` dataclass with the 7 fields per AC-1b.2.3.
  - [ ] All 3 are `frozen=True` per Phase-1 immutability convention.

- [ ] **Task 3: Author `src/AgentEval/_kernel/redaction.py` primitives (AC: 1b.2.4)**
  - [ ] Apache 2.0 license header.
  - [ ] Module docstring citing NFR-SEC-01 / FR38a + architecture L679 + L1193.
  - [ ] `DEFAULT_PATTERNS: list[re.Pattern]` (module-level, mutable) seeded with 6 patterns per AC-1b.2.4.
  - [ ] `redact(text, patterns=None) -> str` — replace each pattern's matches with `[REDACTED]`.
  - [ ] `redact_dict(d) -> dict` — recursive; `str` values get `redact()`; nested dict/list/tuple recursed; other types pass-through.
  - [ ] `register_pattern(regex: str) -> None` — compile + append to `DEFAULT_PATTERNS`. Thread-safety caveat in module docstring.
  - [ ] `redaction_policy_hash() -> str` — SHA-256 hex of `"|".join(p.pattern for p in DEFAULT_PATTERNS)`; stable across runs with the same pattern set.

- [ ] **Task 4: Author `src/AgentEval/_kernel/redaction.py` `RedactionProcessor(SpanProcessor)` class (AC: 1b.2.5)**
  - [ ] Import `opentelemetry.sdk.trace.SpanProcessor`.
  - [ ] `RedactionProcessor(SpanProcessor)` with `on_start(span, parent_context)` no-op; `on_end(span)` scrubs the 5 documented attribute keys (per AC-1b.2.5) via `redact()` or `redact_dict()` based on attribute type.
  - [ ] `shutdown()` + `force_flush(timeout_millis=30000)` no-ops returning True (per SpanProcessor protocol).
  - [ ] Verify with mypy.

- [ ] **Task 5: Author `src/AgentEval/_kernel/trace_store.py` lifecycle + projection accessors (AC: 1b.2.1, 1b.2.2, 1b.2.8)**
  - [ ] Apache 2.0 license header.
  - [ ] Module docstring citing architecture L600-682 Decision-2 + L968-990 OTel GenAI semconv + Story 1b.1's `_kernel/context.current_context()`.
  - [ ] `_exporter: InMemorySpanExporter` module-level singleton (lazy-initialized to allow test override).
  - [ ] `_configure_tracer_provider() -> None` helper that sets up the TracerProvider with the `agenteval.test_id` resource attribute pulled from `current_context()` at span-start time. Phase-1 implementation: rely on OTel SDK's `set_tracer_provider()`; Epic 5 Story 5.1 wires this into `AgentEval.__init__(telemetry=True)`.
  - [ ] `get_run_spans(test_id: str | None = None) -> list[ReadableSpan]` — falls back to `current_context().test_id` when omitted; filters `_exporter.get_finished_spans()` by `span.attributes.get("agenteval.test_id") == test_id`; sorts by `span.start_time` ascending.
  - [ ] `get_tool_calls(test_id, source=None) -> list[ToolCallTrace]` — filter spans by `span.name == "execute_tool"` + optionally `span.attributes.get("agenteval.tool.source") == source`; project into `ToolCallTrace` dataclasses.
  - [ ] `get_usage(test_id) -> Usage` — filter spans by `span.name == "chat"`; sum `gen_ai.usage.{input_tokens, output_tokens, cached_input_tokens}` attributes.
  - [ ] `get_latency(test_id) -> float` — sum `(span.end_time - span.start_time) / 1e9` for nanosecond→second conversion across all spans for the test.
  - [ ] `get_run_manifest(test_id) -> RunManifest` — assemble from `library_version` (read `AgentEval.__version__`), test_id, suite_id (from current TestContext), redaction-policy hash (from `redaction.redaction_policy_hash()`), start/end times (from min/max span timestamps for the test), tier-breakdown (count spans per `agenteval.tier` attribute value).
  - [ ] `clear_spans(test_id: str) -> int` — remove spans tagged with `test_id` from the exporter's internal buffer; return count removed. Phase-1 implementation: `InMemorySpanExporter.get_finished_spans()` returns a list — manipulate the underlying `_finished_spans` list (private but stable in opentelemetry-sdk 1.20+) OR re-create the exporter; pick the cleaner option + document.

- [ ] **Task 6: Author `src/AgentEval/_kernel/coverage.py` enforcement gate (AC: 1b.2.7)**
  - [ ] Apache 2.0 license header.
  - [ ] Module docstring citing ADR-016 L44 + L17-28 + architecture L384 + L1058 + FR37; explicitly note kernel does NOT detect (adapters do) — kernel only enforces.
  - [ ] `from __future__ import annotations` + `from typing import TYPE_CHECKING`; under `if TYPE_CHECKING:` import `AgentRunResult` from `AgentEval.types` (forward ref; Story 1b.4 lands the class).
  - [ ] `_check_mcp_coverage(run: AgentRunResult, *, allow_external_mcp_blind: bool = False) -> None` — implements the 4 cases per AC-1b.2.7. Raises `IncompleteTraceError` from `AgentEval.errors` with the documented message.
  - [ ] Document Phase-1 duck-typed runtime: function accesses `run.metadata.mcp_coverage` only; any object with that attribute shape works at runtime.

- [ ] **Task 7: Author unit tests under `tests/unit/kernel/` + `tests/unit/` (AC: 1b.2.9)**
  - [ ] `tests/unit/kernel/test_trace_store.py` — 12+ tests covering the 5 accessors + per-test isolation + chronological ordering + `clear_spans` + `_configure_tracer_provider` + default-to-current_context behavior. Use OTel SDK's `InMemorySpanExporter` directly + synthesize `ReadableSpan` fixtures via `tracer.start_span(...).end()` pattern.
  - [ ] `tests/unit/kernel/test_redaction.py` — 10+ tests covering the 6 default patterns + idempotency + recursion + `register_pattern` extension + `redaction_policy_hash` stability + `RedactionProcessor.on_end` mutation in-place.
  - [ ] `tests/unit/kernel/test_coverage.py` — 8+ tests covering the 6 input combinations + trust-floor fixture + duck-typed input. Use a `types.SimpleNamespace`-shaped fake to stand in for `AgentRunResult` until Story 1b.4 lands the real type.
  - [ ] `tests/unit/test_errors.py` — 5+ tests verifying the class hierarchy + `error_code` semantics.
  - [ ] `tests/unit/test_types.py` — 6+ tests verifying construction + frozen immutability + `asdict()` round-trip for each of the 3 dataclasses.

- [ ] **Task 8: All-gates pass (AC: 1b.2.10)**
  - [ ] `uv run ruff check src/ tests/` — clean.
  - [ ] `uv run ruff format --check src/ tests/` — clean.
  - [ ] `uv run mypy src/` — clean (28+ source files: previous 23 + errors.py + types.py + trace_store.py + redaction.py + coverage.py).
  - [ ] `uv run python scripts/check-license-headers.py` — PASS (28+ files).
  - [ ] `uv run pytest tests/unit -q --ignore=tests/unit/conventions` — 108+ pass (67 from Story 1b.1 + 41+ new).
  - [ ] `uv run pytest tests/acceptance/tier1 -q` — 6 FR42 tests still PASS (Story 1a.6 regression).
  - [ ] `uv run robot tests/acceptance/smoke` — RF smoke test still PASS (Story 1a.6 regression).

- [ ] **Task 9: Apply project norms (AC: 1b.2.11)**
  - [ ] Code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)` per `feedback_review_methodology_norms`.
  - [ ] The cross-LLM-reviewer prompt MUST direct: *"For every citation, re-derive from the source"* (per `feedback_citation_drift_first_class`).
  - [ ] Honest framing: Phase-1 limitations documented (stdlib dataclass vs Pydantic; forward-ref `AgentRunResult`; `SandboxRequiredError` not re-homed; `RedactionProcessor` ships but isn't wired until Story 5.1).

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

<!-- To be filled by dev-story workflow -->

### Agent Model Used

<!-- To be filled by dev-story workflow -->

### Debug Log References

<!-- To be filled by dev-story workflow -->

### Completion Notes List

<!-- To be filled by dev-story workflow -->

## File List

<!-- To be filled by dev-story workflow -->

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
