# Story 1b.3: Discovery + Guardrails Kernel — Entry-Points + Fan-Out Decorator

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **adapter author** (Epic 4) **and Tool Discoverability consumer** (Epic 3 MVP, Epic 7 full guardrails),
I want **the two discovery/guardrails `_kernel/` modules — `discovery.py` for adapter discovery via PyPA entry-points across 4 ratified `agenteval.*` groups + the legacy `robotframework_agenteval.adapters` group with programmatic-composition fallback, and `guardrails.py` exposing the `@guarded_fanout(estimator=callable)` decorator with the 3-layer enforcement (pre-flight + mid-run cost meter + mid-run wall-clock meter) per ADR-015 §Decision L25-29 — implemented and unit-tested, plus 2 new `AgentEvalError` sub-bases (`AgentEvalBudgetError`, `AgentEvalCompatError`) + 3 new leaves (`CostExceededError`, `RuntimeBudgetExceededError`, `AdapterDiscoveryError`) added to Story 1b.2's `errors.py`**,
So that **custom adapters register cleanly via PyPA entry-points (FR17a) or programmatic composition (FR17b), any fan-out keyword (`MCP.Get Tool Discoverability`, `Stat.Run N Times`, `Run Scenario`) inherits cost + runtime guardrails by decoration without re-implementing the meter, partial-install failures are surfaced via `AdapterDiscoveryError` per ADR-013 L42, and Epic 4 + Epic 6 ship against a stable kernel layer (discovery API + guardrail decorator + 3 new error leaves)**.

## Acceptance Criteria

> **Pre-create-story drift check (7th consecutive use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-19):** 8 drifts in Story 1b.3 spec caught vs ratified sources. Per Many's 2026-05-19 ratification, ALL 8 resolved by honoring ratified sources (ADR-013 + ADR-014 + ADR-015 + architecture L358-380/L494/L648/L1196-1209/L1426/L1519-1521 + docs/contracts/error-class-hierarchy.md L73/L74/L82 + Story 1b.2's errors.py baseline). epics.md L933-941 (Story 1b.3) updated pre-authoring + architecture.md L1426 ADR-013 filename drift fixed pre-authoring per "fix-the-losing-source-NOW". Drifts: (D1 HIGH) entry-point groups — spec only `robotframework_agenteval.adapters`; ratified 6 tables (4 agenteval.* + 1 legacy + 1 RF-owned `robot.listener`); (D2 HIGH) `@guarded_fanout` signature `cost_kwarg/runtime_kwarg` → `estimator=callable` per ADR-015 §Decision L18; (D3 HIGH) `@guarded_fanout` 2 layers → 3 layers per ADR-015 §Decision L25-29; (D4 MED) `UnknownAdapterError` → `AdapterDiscoveryError` per contract L82; (D5 MED) errors.py extensions — Story 1b.3 adds 2 sub-bases + 3 leaves per ADR-014; (D6 MED) `CodingAgentAdapter` TYPE_CHECKING forward-ref (Story 1b.4 lands the Protocol); (D7 MED) `KeywordTierMissingError` deferred to Story 1b.6 per Many's pick; (D8 LOW) ADR-013 filename drift in architecture L1426 — fixed pre-authoring.

1. **AC-1b.3.1 — `_kernel/discovery.py` 3 typed group-specific accessors + generic underlying helper per ADR-013 L47.** Module exposes:
   - `discover_adapters() -> dict[str, type["CodingAgentAdapter"]]` — loads `agenteval.coding_agents` (primary FR17a) AND `robotframework_agenteval.adapters` (legacy backward-compat group per ADR-013 L18). Returns a single merged dict keyed by entry-point name; on name collision, the primary `agenteval.coding_agents` group wins (logs a warning).
   - `discover_providers() -> dict[str, type]` — loads `agenteval.providers` (FR17c).
   - `discover_sandboxes() -> dict[str, type]` — loads `agenteval.sandboxes` (per ADR-018).
   - `_discover_entry_point_group(group_name: str) -> dict[str, type]` — generic underlying helper. Module-private (single underscore); the 3 typed accessors are the public surface for sub-libraries.
   - `agenteval.judges` is Phase-2; no Phase-1 discover function (the group is declared in pyproject.toml for forward-compat but unused).
   - `robot.listener` group is NOT discovered by this module — Robot Framework's own listener-discovery code owns it.
   - All discovery calls use `importlib.metadata.entry_points(group=...)` (Python 3.10+ API; the project's pinned 3.12+ baseline is fine).

2. **AC-1b.3.2 — `_kernel/discovery.py` `register_adapter` + `get_adapter` + `AdapterDiscoveryError` per ADR-013 L40-42.** Module exposes:
   - `register_adapter(name: str, cls: type["CodingAgentAdapter"]) -> None` — programmatic registration per FR17b (composition path that doesn't require an installed entry-point package). Stores in a module-level `_registered_adapters: dict[str, type]`. Same-name re-registration overwrites with a `UserWarning`.
   - `get_adapter(name: str) -> type["CodingAgentAdapter"]` — lookup precedence: programmatic registrations (`_registered_adapters`) > `agenteval.coding_agents` entry-points > `robotframework_agenteval.adapters` legacy entry-points. On miss raises `AdapterDiscoveryError("No adapter registered as {name!r}; known adapters: {sorted(known)!r}")`.
   - Entry-point loading errors are caught at per-entry-point granularity + emitted via the Python `logging` module at WARNING level (one broken third-party adapter cannot block library import). Partial-install detection (entry-point points at a missing module / wrong import path) raises `AdapterDiscoveryError` with the diagnostic hint per ADR-013 L42: *"Found `agenteval.coding_agents:{name}` registration but `{import_path}` is not installed; install `pip install agenteval[{extras}]` or remove the registration."*

3. **AC-1b.3.3 — `_kernel/guardrails.py` `@guarded_fanout(estimator=callable)` decorator per ADR-015 §Decision L18 — Layer 1 pre-flight estimation.** Module exposes `@guarded_fanout(estimator: Callable[[dict], tuple[float, float]] | None = None, *, meter_interval_seconds: float = 5.0)` decorator:
   - When `estimator` is provided, the decorator wraps the keyword function so calling it triggers `estimator(kwargs) -> (cost_estimate_usd, runtime_estimate_seconds)` BEFORE entering the keyword body.
   - The decorator reads `max_cost_usd` + `max_runtime_seconds` from the AgentEval instance's resolved config (Story 1a.6 wiring + Story 1b.1's `resolve_config` precedence chain). For Phase-1 Story 1b.3 testing, the decorator accepts an optional `_budget: tuple[float, float | None] | None = None` kwarg-only parameter that overrides the instance config (test-only path documented in the module docstring; production code path reads from the bound instance).
   - If `cost_estimate_usd > max_cost_usd`: raises `CostExceededError(f"Pre-flight cost estimate {cost_estimate_usd:.2f} USD > budget {max_cost_usd:.2f} USD; refusing to enter keyword body.")`.
   - If `runtime_estimate_seconds > max_runtime_seconds` (when not None): raises `RuntimeBudgetExceededError(f"Pre-flight runtime estimate {runtime_estimate_seconds:.1f}s > budget {max_runtime_seconds:.1f}s; refusing to enter keyword body.")`.
   - When `estimator=None`, Layer 1 is skipped (caller defers to mid-run meters only — useful for keywords whose cost is fundamentally unpredictable until first call).

4. **AC-1b.3.4 — `_kernel/guardrails.py` Layer 2 mid-run cost meter (Phase-1 stub per ADR-015 §Decision L27).** Inside the decorator's wrapped function:
   - Starts a background poller (Python `threading.Thread` daemon=False per Story 1b.1 patterns) that polls every `meter_interval_seconds` (default 5.0s; configurable).
   - The poller calls a `_current_cost_usd_for_run() -> float` Phase-1 stub returning 0.0; **the real implementation lands in Story 4.1** (Generic LiteLLM adapter) when the LiteLLM cost-tracking API is wired. Story 1b.3 ships the polling loop + breach detection + cooperative-cancellation hook; the cost source is the stub.
   - On breach (`current_cost > max_cost_usd`): the poller sets a `_cancel_event: threading.Event` (cooperative-cancellation hook) AND records the breach via a module-level `_BreachState` that the outer wrapper re-checks on each yield. After the keyword returns or yields, the wrapper raises `CostExceededError(f"Mid-run cost {current_cost:.2f} USD breached budget {max_cost_usd:.2f} USD after {elapsed:.1f}s; cumulative cost surfaces in this message.")`.
   - Phase-1 documentation: the stub-returns-0 means the polling loop never fires `CostExceededError` from Layer 2 in Story 1b.3's own tests; Story 1b.3 tests Layer 2 by monkey-patching `_current_cost_usd_for_run` to return a custom value.

5. **AC-1b.3.5 — `_kernel/guardrails.py` Layer 3 mid-run wall-clock meter per ADR-015 §Decision L29.** Same background poller as Layer 2 also tracks wall-clock elapsed time:
   - On `elapsed > max_runtime_seconds` (when not None): raises `RuntimeBudgetExceededError(f"Mid-run wall-clock {elapsed:.1f}s breached budget {max_runtime_seconds:.1f}s; cumulative elapsed surfaces here.")` — **at exactly the configured budget**, NOT at 1.1× (the 1.1× wording in the pre-edit epics.md draft was unratified).
   - When `max_runtime_seconds is None` (the FR11b default), Layer 3 is silent + the poller skips the wall-clock check.
   - Cooperative cancellation: same `_cancel_event` shared with Layer 2; estimator-aware keyword bodies that poll the event can exit early.

6. **AC-1b.3.6 — Cooperative cancellation hook + `_run_async` integration.** The decorator exposes the `_cancel_event` as a contextually-available reference (via a `ContextVar[Event | None]`-backed accessor or a function arg the keyword body opts into). The integration with Story 1b.1's `_run_async`:
   - Story 1b.1's `_run_async` already propagates ContextVar context via `copy_context()`. The decorator binds the `_cancel_event` to a ContextVar at the decorator's wrapped-function entry; the bound event survives through `_run_async`'s worker-thread fallback path.
   - Async-aware fan-out keyword bodies access via `guardrails.current_cancel_event()` helper (returns None outside a decorated frame). Phase-1: the helper is shipped + tested; actual usage by fan-out keywords lands in Epic 6 Story 6.3 (`Stat.Run N Times`).

7. **AC-1b.3.7 — `src/AgentEval/errors.py` extended with 2 sub-bases + 3 leaves per ADR-014 + docs/contracts/error-class-hierarchy.md L73/L74/L82.** Pure extension to Story 1b.2's errors.py (no refactor of `AgentEvalError`/`AgentEvalIntegrityError`/`IncompleteTraceError`):
   - `AgentEvalBudgetError(AgentEvalError)` — sub-base for cost/runtime budget breaches per ADR-014's 4-sub-base scheme.
   - `AgentEvalCompatError(AgentEvalError)` — sub-base for environment/version/compat issues per ADR-014.
   - `CostExceededError(AgentEvalBudgetError)` — `error_code: ClassVar[str] = "COST_EXCEEDED"`. Per contract L73, exit code 66 (sysexits-extended; pinned by epics.md Story 8a.1 L1660).
   - `RuntimeBudgetExceededError(AgentEvalBudgetError)` — `error_code: ClassVar[str] = "RUNTIME_BUDGET_EXCEEDED"`. Per contract L74, exit code 75 (EX_TEMPFAIL).
   - `AdapterDiscoveryError(AgentEvalCompatError)` — `error_code: ClassVar[str] = "ADAPTER_DISCOVERY_ERROR"`. Per contract L82, exit code 78 (EX_CONFIG). Raised by both partial-install detection AND `get_adapter()` lookup miss (per Many's decision — single leaf covers both cases; `UnknownAdapterError` is NOT added to the catalog).
   - Story 1b.2's H_R7 `__str__` formatter (renders `f"{error_code}: {message}"` when `error_code` non-empty) inherits cleanly to all 3 new leaves — no override needed.
   - The other 6 leaves from the 11-leaf catalog (`PollingDisallowedError`, `UnsupportedMCPVersionError`, `UnsupportedBinaryVersionError`, `TierViolationError`, `SandboxRequiredError`, `ValidateOperatorDisallowed`, `AdapterVersionDriftWarning`) are added by their owning stories (Story 1b.6, Epic 3 Story 3.1, Story 1b.4 / Epic 4 Story 4.2, Story 1b.6, future hygiene re-home story, Epic 6 Story 6.2, Epic 11 Story 11.3).

8. **AC-1b.3.8 — `CodingAgentAdapter` TYPE_CHECKING forward-ref pattern.** Story 1b.4 lands the `CodingAgentAdapter` Protocol in `src/AgentEval/types.py`. Story 1b.3's `discovery.py` references it via:
   ```python
   from __future__ import annotations
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from AgentEval.types import CodingAgentAdapter
   ```
   Runtime accepts any duck-typed object (Phase-1 forward-reference pattern proven in Story 1b.2 for `AgentRunResult`). Tests use a small stand-in (`types.SimpleNamespace` or a tiny `@dataclass`) until Story 1b.4 ratifies the type.

9. **AC-1b.3.9 — Unit tests in `tests/unit/kernel/test_{discovery, guardrails}.py` + extended `tests/unit/test_errors.py`.** Coverage:
   - `test_discovery.py` (~12+ tests): entry-point loading for each of 3 typed groups (mock `importlib.metadata.entry_points` via `monkeypatch`); legacy `robotframework_agenteval.adapters` merge with `agenteval.coding_agents` + collision-prefers-primary + warning; `register_adapter` + override-by-name + UserWarning; `get_adapter` lookup precedence (programmatic > primary > legacy); `get_adapter` miss raises `AdapterDiscoveryError`; broken-entry-point graceful degradation (load_entry_point raises → caught + WARNING-logged + other entry-points still load); partial-install detection (entry-point points at non-existent module) raises `AdapterDiscoveryError` with the installed-vs-required-extras diagnostic.
   - `test_guardrails.py` (~14+ tests): Layer 1 pre-flight cost estimate raises `CostExceededError` (with estimator provided); Layer 1 pre-flight runtime estimate raises `RuntimeBudgetExceededError`; `estimator=None` skips Layer 1; Layer 2 mid-run cost meter polls + raises on cumulative breach (monkey-patch `_current_cost_usd_for_run` to return increasing values); Layer 3 mid-run wall-clock meter raises at exactly the budget (NOT 1.1×); cooperative-cancellation `_cancel_event` is observable from inside the keyword body; `current_cancel_event()` accessor returns None outside a decorated frame; `_run_async`-wrapped keyword body sees the propagated cancellation event via ContextVar (verifies Story 1b.1 integration); error message format surfaces cumulative cost at breach time; `meter_interval_seconds` parameter respected.
   - `test_errors.py` extensions (~6+ tests): `AgentEvalBudgetError` inherits `AgentEvalError`; `AgentEvalCompatError` inherits `AgentEvalError`; `CostExceededError` inherits `AgentEvalBudgetError`; `RuntimeBudgetExceededError` inherits `AgentEvalBudgetError`; `AdapterDiscoveryError` inherits `AgentEvalCompatError`; each leaf has correct `error_code` ClassVar; Story 1b.2's `__str__` formatter renders correctly for all 3 new leaves.

10. **AC-1b.3.10 — All-gates clean.** `uv run ruff check src/ tests/` clean; `uv run ruff format --check src/ tests/` clean; `uv run mypy src/` clean (30 source files: previous 28 + new discovery.py + guardrails.py); `uv run python scripts/check-license-headers.py` PASS; `uv run pytest tests/unit -q --ignore=tests/unit/conventions` — all kernel unit tests pass (existing 163 from Stories 1b.1 + 1b.2 + new ~32 from Story 1b.3 = ~195+); `uv run pytest tests/acceptance/tier1 -q` — Story 1a.6's 6 FR42 tests still pass (regression); `uv run robot tests/acceptance/smoke` — RF smoke test still passes (regression).

11. **AC-1b.3.11 — Code-review prompt embeds the citation-drift re-derivation directive (`feedback_citation_drift_first_class`).** Same NEW NORM applied across Stories 1b.1, 1b.2 reviews. Cross-LLM reviewer MUST direct: *"For every citation in the changed files — 'per ADR-013 L42', 'per ADR-015 §Decision L25-29', 'per docs/contracts/error-class-hierarchy.md L73', 'per architecture L648', etc. — open the cited source and verify the claim is EXACTLY what the source says."* Citation drift was the #1 finding category across Epic 1a + Stories 1b.1, 1b.2; Codex's solo catches in those reviews (H1 scope-modes, C1 resource-vs-span) showed structural blockers hide behind correct-looking citations.

## Tasks / Subtasks

- [ ] **Task 1: Extend `src/AgentEval/errors.py` with 2 new sub-bases + 3 new leaves (AC: 1b.3.7)**
  - [ ] `AgentEvalBudgetError(AgentEvalError)` sub-base — no override; inherits `__str__` formatter from Story 1b.2's base.
  - [ ] `AgentEvalCompatError(AgentEvalError)` sub-base — same pattern.
  - [ ] `CostExceededError(AgentEvalBudgetError)` leaf — `error_code: ClassVar[str] = "COST_EXCEEDED"`.
  - [ ] `RuntimeBudgetExceededError(AgentEvalBudgetError)` leaf — `error_code: ClassVar[str] = "RUNTIME_BUDGET_EXCEEDED"`.
  - [ ] `AdapterDiscoveryError(AgentEvalCompatError)` leaf — `error_code: ClassVar[str] = "ADAPTER_DISCOVERY_ERROR"`.
  - [ ] Update `__all__` export list.
  - [ ] Update module docstring "Story 1b.3 ships these leaves" note + retire the 6 remaining future-story placeholders mention to be just the 6 still-unimplemented ones (PollingDisallowedError, UnsupportedMCPVersion, UnsupportedBinaryVersion, TierViolationError, ValidateOperatorDisallowed, AdapterVersionDriftWarning).

- [ ] **Task 2: Author `src/AgentEval/_kernel/discovery.py` (AC: 1b.3.1, 1b.3.2, 1b.3.8)**
  - [ ] Apache 2.0 license header.
  - [ ] Module docstring citing ADR-013 (was ADR-A2) at `docs/adr/ADR-013-entry-points-discovery-infrastructure.md` (NOT `-discovery.md`; architecture L1426 was corrected pre-authoring) + FR17a/b/c + Phase-1 forward-ref pattern for `CodingAgentAdapter`.
  - [ ] `TYPE_CHECKING` forward-ref import for `CodingAgentAdapter` from `AgentEval.types`.
  - [ ] Module-level `_registered_adapters: dict[str, type] = {}` for programmatic-composition path.
  - [ ] `_discover_entry_point_group(group_name: str) -> dict[str, type]` private helper:
    - Uses `importlib.metadata.entry_points(group=group_name)`.
    - Iterates entries; for each, tries `entry.load()` in a try/except.
    - On `ModuleNotFoundError` / `ImportError` / `AttributeError`: emits a `logging.WARNING` log via the module's logger + raises `AdapterDiscoveryError` with the installed-vs-required-extras diagnostic (ADR-013 L42 format).
    - Returns dict mapping entry name → loaded class.
  - [ ] `discover_adapters() -> dict[str, type["CodingAgentAdapter"]]`:
    - Calls `_discover_entry_point_group("agenteval.coding_agents")` (primary).
    - Calls `_discover_entry_point_group("robotframework_agenteval.adapters")` (legacy backward-compat).
    - Merges: primary wins on name collision, emits `UserWarning` via `warnings.warn` when collision detected.
    - Returns merged dict.
  - [ ] `discover_providers() -> dict[str, type]` — single-group dispatch.
  - [ ] `discover_sandboxes() -> dict[str, type]` — single-group dispatch.
  - [ ] `register_adapter(name: str, cls: type["CodingAgentAdapter"]) -> None` — overwrites + emits `UserWarning` on same-name re-registration.
  - [ ] `get_adapter(name: str) -> type["CodingAgentAdapter"]` — precedence: `_registered_adapters` > `discover_adapters()` cached result. Cache discovery via `functools.lru_cache(maxsize=1)` to avoid repeated entry-point traversal; document the cache + provide `_clear_discovery_cache()` test-only helper.
  - [ ] Verify with `uv run mypy src/AgentEval/_kernel/discovery.py`.

- [ ] **Task 3: Author `src/AgentEval/_kernel/guardrails.py` (AC: 1b.3.3, 1b.3.4, 1b.3.5, 1b.3.6)**
  - [ ] Apache 2.0 license header.
  - [ ] Module docstring citing ADR-015 (was ADR-A5) at `docs/adr/ADR-015-cost-runtime-guardrail-decorator.md` (ratified filename per Story 1b.1 M4 fix) + FR11 + FR11b + Story 1b.2's errors.py CostExceededError / RuntimeBudgetExceededError + 3-layer enforcement description.
  - [ ] Imports: `contextvars`, `threading`, `time`, `functools`, `warnings`, `logging`; `CostExceededError`, `RuntimeBudgetExceededError` from `AgentEval.errors`; `_run_async` integration (not direct import — the decorator works via ContextVar that `_run_async` already propagates per Story 1b.1).
  - [ ] Module-level `_cancel_event_var: ContextVar[threading.Event | None] = ContextVar("agenteval_cancel_event", default=None)`.
  - [ ] Module-level `_current_cost_usd_for_run() -> float` STUB returning 0.0 (Phase-1; Story 4.1 wires real LiteLLM cost tracker). Documented in module docstring.
  - [ ] `current_cancel_event() -> threading.Event | None` accessor — returns the ContextVar value (None outside a decorated frame).
  - [ ] `@guarded_fanout(estimator: Callable[[dict], tuple[float, float]] | None = None, *, meter_interval_seconds: float = 5.0)` decorator factory:
    - Returns a decorator that wraps the keyword function.
    - Inside the wrapper:
      - Read budget from the AgentEval instance (`self._max_cost_usd`, `self._max_runtime_seconds` per Story 1a.6 / Story 1b.1 wiring). Also accept the `_budget` kwarg-only test-override.
      - **Layer 1 (pre-flight)**: if `estimator` is not None, call it with `kwargs`; check the returned tuple against budgets; raise `CostExceededError` / `RuntimeBudgetExceededError` per AC-1b.3.3.
      - Create a fresh `threading.Event` as the cancellation hook; bind via the ContextVar.
      - Spawn a daemon=False background poller thread (uses `threading.Thread` consistent with Story 1b.1's RLock/threading conventions); the thread runs the meter loop, polls every `meter_interval_seconds`, checks Layer 2 + Layer 3 conditions, sets `_cancel_event` + records `_BreachState` on breach.
      - Wrap the keyword body in a try/finally so the poller thread is joined cleanly on exit.
      - After the keyword returns (or yields), re-check `_BreachState` and raise `CostExceededError` / `RuntimeBudgetExceededError` if a breach was recorded (so the caller sees the typed error even though the keyword body itself didn't raise).
    - Document the `meter_interval_seconds` kwarg with sensible-default rationale (5s = ADR-015 reference; configurable for unit tests + low-budget runs).

- [ ] **Task 4: Author unit tests under `tests/unit/kernel/` + extend `tests/unit/test_errors.py` (AC: 1b.3.9)**
  - [ ] `tests/unit/kernel/test_discovery.py` (~12+ tests covering the 3 group accessors + register/get + AdapterDiscoveryError + broken-entry-point + partial-install detection):
    - Use `monkeypatch.setattr(importlib.metadata, "entry_points", fake_func)` to stub the entry-point discovery surface.
    - Fake entry-points return small `SimpleNamespace`-shaped stand-ins for the `CodingAgentAdapter` Protocol (Story 1b.4 forward-ref).
    - At least one test for the collision-warning between `agenteval.coding_agents` and `robotframework_agenteval.adapters`.
    - At least one test for `_clear_discovery_cache()` test-helper.
  - [ ] `tests/unit/kernel/test_guardrails.py` (~14+ tests covering 3 layers + cancellation + estimator=None + ContextVar propagation + error message format):
    - Use a tiny `_FakeAgent` class with `_max_cost_usd` + `_max_runtime_seconds` attributes (mimics the AgentEval instance contract; full `AgentEval` not needed).
    - For Layer 2 / Layer 3 tests: use very small `meter_interval_seconds` (e.g., 0.01s) so the poller fires multiple times in a sub-second test.
    - Monkey-patch `_current_cost_usd_for_run` to return increasing values for Layer 2 breach tests.
    - At least one test verifies `_run_async` integration: spawn a coroutine via `_run_async`, observe `current_cancel_event()` returns the propagated event.
    - At least one test verifies `estimator=None` skips Layer 1 (only Layers 2/3 fire).
    - At least one test verifies error message contains cumulative-cost-at-breach number.
  - [ ] `tests/unit/test_errors.py` extensions:
    - 2 tests for new sub-bases (each inherits AgentEvalError, has empty `error_code`).
    - 3 tests for new leaves (each inherits the correct sub-base, has correct `error_code` string, inherits the H_R7 `__str__` formatter from base).
    - 1 test for full hierarchy: `isinstance(CostExceededError("x"), AgentEvalError) is True`.

- [ ] **Task 5: All-gates pass (AC: 1b.3.10)**
  - [ ] `uv run ruff check src/ tests/` — clean.
  - [ ] `uv run ruff format --check src/ tests/` — clean.
  - [ ] `uv run mypy src/` — clean (30 source files: previous 28 + new discovery.py + guardrails.py).
  - [ ] `uv run python scripts/check-license-headers.py` — PASS (30/30).
  - [ ] `uv run pytest tests/unit -q --ignore=tests/unit/conventions` — all kernel + errors + types tests pass (~195+).
  - [ ] `uv run pytest tests/acceptance/tier1 -q` — Story 1a.6's 6 FR42 tests still PASS (regression).
  - [ ] `uv run robot tests/acceptance/smoke` — RF smoke test still PASS (regression).

- [ ] **Task 6: Update `docs/contracts/stability-surface.md` Phase-1 registry (AC: 1b.3.7 — extends Story 1b.2's kernel surface entry)**
  - [ ] Add `_kernel.discovery.{discover_adapters, discover_providers, discover_sandboxes, register_adapter, get_adapter}` as `provisional` to the Kernel public surface section.
  - [ ] Add `_kernel.guardrails.{guarded_fanout, current_cancel_event}` as `provisional`.
  - [ ] Update the Top-level errors + types surface section: add `AgentEvalBudgetError`, `AgentEvalCompatError` sub-bases + `CostExceededError`, `RuntimeBudgetExceededError`, `AdapterDiscoveryError` leaves with `stable` label per the established pattern.

- [ ] **Task 7: Update `docs/contracts/error-class-hierarchy.md` IMPLEMENTED markers (AC: 1b.3.7)**
  - [ ] Mark `CostExceededError` (L73) as IMPLEMENTED — Story 1b.3 (`src/AgentEval/errors.py`); raise site at `src/AgentEval/_kernel/guardrails.@guarded_fanout` Layer 1 + Layer 2.
  - [ ] Mark `RuntimeBudgetExceededError` (L74) as IMPLEMENTED — Story 1b.3; raise site at `_kernel/guardrails.@guarded_fanout` Layer 1 + Layer 3.
  - [ ] Mark `AdapterDiscoveryError` (L82) as IMPLEMENTED — Story 1b.3 (`src/AgentEval/errors.py`); raise site at `src/AgentEval/_kernel/discovery.{_discover_entry_point_group, get_adapter}`.

- [ ] **Task 8: Apply project norms (AC: 1b.3.11)**
  - [ ] Code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)` per `feedback_review_methodology_norms`.
  - [ ] Cross-LLM reviewer prompt MUST direct re-derivation of cited facts per `feedback_citation_drift_first_class`.
  - [ ] Honest framing: Phase-1 limitations documented (Layer 2 cost-meter stub returns 0.0 until Story 4.1; cooperative-cancellation hook ships but full provider-client cancellation integration is Story 4.1; `CodingAgentAdapter` TYPE_CHECKING forward-ref until Story 1b.4).

## Dev Notes

### Project context — Story 1b.3's place in Epic 1b

Story 1b.3 is the 3rd Epic 1b foundational kernel story. Dependencies:
- **Story 1b.1** `_kernel/{context, tier, run_async}.py` — `_run_async` ContextVar propagation is load-bearing for the cancellation-event hook; `tier.py` is consumed by Epic 6 (Story 1b.6 enforces tier annotations on `@keyword`-decorated methods, but Story 1b.3's discovery.py loader does NOT enforce — per Many's D7 decision).
- **Story 1b.2** `src/AgentEval/errors.py` — Story 1b.3 EXTENDS the existing class hierarchy (`AgentEvalError` base + `AgentEvalIntegrityError` sub-base + `IncompleteTraceError` leaf) with 2 new sub-bases + 3 new leaves. No refactor of the existing classes.

Story 1b.3 ENABLES:
- **Story 1b.4** (CodingAgentAdapter Protocol): lands the type Story 1b.3's TYPE_CHECKING forward-ref imports.
- **Story 1b.5** (Conformance harness): consumes `discovery._discover_entry_point_group` for fixture-discovery.
- **Story 1b.6** (Determinism Contract + conventions): owns the `KeywordTierMissingError` enforcer per Many's D7 decision (architecture L648's `discovery.py` tier-validation is moved to 1b.6's scope).
- **Story 4.1** (Generic LiteLLM adapter): wires the real LiteLLM cost-tracking API into Story 1b.3's `_current_cost_usd_for_run` stub.
- **Story 6.3** (`Stat.Run N Times` Tier-3 fan-out keyword): the first real consumer of `@guarded_fanout(estimator=...)`.

### Architecture compliance

| Architecture reference | Story 1b.3 implementation |
|---|---|
| L374 — Entry-points discovery infrastructure / 6 tables | 3 typed accessors + 1 generic helper; legacy + primary merge with collision warning |
| L376 — Error class hierarchy / `AgentEvalError` base + 4 sub-bases | Story 1b.3 adds 2 of the 4 sub-bases (Budget, Compat); Integrity was Story 1b.2; Safety is future story |
| L380 — Cost + runtime guardrails / `@guarded_fanout(estimator=callable)` | Honored verbatim with 3-layer enforcement per ADR-015 §Decision L25-29 |
| L494 — `[project.entry-points."robot.listener"]` | NOT discovered by `_kernel/discovery.py` — RF owns it |
| L648 — `_kernel/discovery.py` validates `@tier` annotation; raises `KeywordTierMissingError` | **DEFERRED to Story 1b.6** per Many's D7 decision |
| L1196-1209 — `_kernel/{discovery, guardrails}.py` locations + roles | Honored verbatim |
| L1426 — ADR-013 filename | FIXED pre-authoring: `ADR-013-entry-points-discovery-infrastructure.md` (was `ADR-013-entry-points-discovery.md` — D8 drift) |
| L1519-1521 — Cross-cutting routing | Entry-points discovery at library import time; `@guarded_fanout` selectively on Tier-3 fan-out keywords |
| ADR-013 L42 partial-install detection | `AdapterDiscoveryError` with installed-vs-required-extras diagnostic hint |
| ADR-013 L47 6-table count | Honored: 4 agenteval.* + 1 legacy + 1 RF-owned `robot.listener` |
| ADR-015 L18 `@guarded_fanout(estimator=callable)` | Honored verbatim |
| ADR-015 L25-29 3-layer enforcement | All 3 layers shipped; Layer 2's provider cost source is stubbed (Story 4.1 wires real source) |
| ADR-015 L55 CostExceededError + RuntimeBudgetExceededError | Both leaves added to errors.py |
| docs/contracts/error-class-hierarchy.md L73 + L74 + L82 | All 3 leaves marked IMPLEMENTED |
| docs/contracts/error-class-hierarchy.md L82 owning epic "Epic 1b Story 1b.3" | Honored: AdapterDiscoveryError implemented here |

### Phase-1 limitations explicitly documented

- **Layer 2 mid-run cost meter**: `_current_cost_usd_for_run()` returns 0.0 in Phase-1; the real LiteLLM cost-tracking integration lands in **Story 4.1**. Story 1b.3 ships the polling loop + breach detection + cooperative-cancellation hook; the cost source is the stub. Documented in module docstring + AC-1b.3.4. Tests monkey-patch the stub to verify the breach path.
- **Cooperative cancellation**: the `_cancel_event` hook is surfaced via `current_cancel_event()`; full integration with provider-client cancellation (so LiteLLM streaming calls actually stop mid-response) lands in **Story 4.1**. Story 1b.3 ships the event-propagation contract; consumers opt in.
- **`CodingAgentAdapter` forward-ref**: TYPE_CHECKING-guarded import until Story 1b.4 ratifies the Protocol. Tests use `SimpleNamespace` stand-ins.
- **`agenteval.judges` group**: declared in pyproject.toml but no Phase-1 discover function. Phase-2 deliverable.
- **`KeywordTierMissingError` convention enforcer**: deferred to Story 1b.6 per Many's D7 decision (architecture L648's `discovery.py` tier-validation is 1b.6's scope, not 1b.3's).

### Story 1b.2 integration — errors.py extension pattern

Story 1b.2's `errors.py` ships:
- `AgentEvalError(Exception)` base with `error_code: ClassVar[str] = ""` + `__str__` formatter (H_R7 fix).
- `AgentEvalIntegrityError(AgentEvalError)` sub-base.
- `IncompleteTraceError(AgentEvalIntegrityError)` leaf with `error_code = "INCOMPLETE_TRACE"`.

Story 1b.3 ADDS (pure extension, no refactor):
- `AgentEvalBudgetError(AgentEvalError)` + `AgentEvalCompatError(AgentEvalError)` sub-bases.
- 3 leaves with their `error_code` ClassVar strings.

Subsequent stories add the remaining leaves to the same file. The base + sub-base structure is now 3 of 4 ratified sub-bases (Integrity, Budget, Compat); the 4th (`AgentEvalSafetyError` per ADR-014's 4-sub-base scheme) lands in a future story (likely Story 1b.6 for `TierViolationError` or Epic 6 Story 6.2 for `ValidateOperatorDisallowed`).

### Story 1b.1 integration — `_run_async` ContextVar propagation

Story 1b.1's `_run_async` uses `contextvars.copy_context()` to propagate ContextVar state across the worker-thread fallback path (the H6 fix from Story 1b.1's code review). Story 1b.3's `@guarded_fanout` decorator binds `_cancel_event_var` via ContextVar BEFORE the keyword body executes. Async-aware fan-out keyword bodies invoked through `_run_async` therefore inherit the cancellation event.

Verification: `test_guardrails.py` includes an integration test that spawns a coroutine via `_run_async`, observes that `current_cancel_event()` (called from inside the coroutine) returns the same Event instance as the outer wrapper.

### Project norms applied

1. **Norm #1 (cross-LLM adversarial review)** — `/bmad-code-review (Using current Claude + Codex CLI subagent)` per Epic 0 retro Norm #1.
2. **Norm #4 (pre-create-story drift check)** — 7th consecutive use. 8 drifts caught + 1 pre-authoring fix in architecture.md L1426.
3. **NEW NORM (citation-drift first-class category)** — AC-1b.3.11 directive applies to the cross-LLM-reviewer prompt at code-review time. Story 1b.1's M4 (ADR-012 + ADR-015 filename drift) + Story 1b.2's pre-create-story sweep both demonstrated this catches real bugs.
4. **Honest framing** — Phase-1 limitations explicitly documented (Layer 2 stub; cancellation hook; forward-ref; deferred enforcer).
5. **agentguard inspiration-only** — ratified; no agentguard dependency in discovery or guardrails.

### References

- **PRD §FR11** — `max_cost_usd` budget on Tier-3 fan-out keywords
- **PRD §FR11b** — `max_runtime_seconds` budget (sibling to FR11)
- **PRD §FR17a** — Adapter registration via PyPA entry-points
- **PRD §FR17b** — Programmatic adapter composition (FR17a's complement)
- **PRD §FR17c** — Provider entry-points (separate group)
- **PRD §FR42** — `max_cost_usd=5.0` + `max_runtime_seconds=None` Library defaults wired in Story 1a.6
- **ADR-013 (was ADR-A2)** (`docs/adr/ADR-013-entry-points-discovery-infrastructure.md`) — 6 entry-point tables + AdapterDiscoveryError partial-install contract (Story 1b.1 M4 filename drift fix applied to this filename)
- **ADR-014 (was ADR-A3)** (`docs/adr/ADR-014-error-class-hierarchy.md`) — error class hierarchy
- **ADR-015 (was ADR-A5)** (`docs/adr/ADR-015-cost-runtime-guardrail-decorator.md`) — `@guarded_fanout(estimator=callable)` 3-layer enforcement
- **ADR-018 (was ADR-A8)** (`docs/adr/ADR-018-sandbox-phase1-policy-protocol.md`) — adds the `agenteval.sandboxes` 5th group consumed by `discover_sandboxes()`
- **Architecture L374** — 6 entry-point tables
- **Architecture L376** — Error class hierarchy
- **Architecture L380** — `@guarded_fanout(estimator=callable)`
- **Architecture L494** — `robot.listener` entry-points group (NOT our discovery scope)
- **Architecture L648** — `_kernel/discovery.py` tier validation (DEFERRED to Story 1b.6)
- **Architecture L1196-1209** — `_kernel/{discovery, guardrails}.py` project tree positions
- **Architecture L1426** — ADR-013 filename (fixed pre-authoring)
- **docs/contracts/error-class-hierarchy.md** (Story 1a.4 ratified) — per-leaf inventory; Story 1b.3 implements 3 of the 11 leaves
- **Story 1b.1 `_kernel/run_async.py`** — `_run_async` ContextVar propagation via `copy_context()` (H6 fix); load-bearing for cancellation-event integration
- **Story 1b.1 `_kernel/tier.py`** — `@tier` decorator; KeywordTierMissingError enforcement is Story 1b.6 scope, NOT 1b.3
- **Story 1b.2 `src/AgentEval/errors.py`** — base class hierarchy that Story 1b.3 EXTENDS (pure addition, no refactor)
- **Story 1b.2 `src/AgentEval/_kernel/redaction.py`** — Story 1b.3 patterns mirror it (module-level state + register_pattern-style extension hooks)
- **Story 1a.6 `src/AgentEval/__init__.py`** — `max_cost_usd` + `max_runtime_seconds` defaults wired; Story 1b.3's `@guarded_fanout` reads from the bound instance
- **Epic 1a retrospective** `_bmad-output/implementation-artifacts/epic-1a-retro-2026-05-18.md` — `feedback_citation_drift_first_class` NEW NORM
- **`feedback_citation_drift_first_class`** (memory) — applied via AC-1b.3.11 + Norm #1

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

Expected files (2 created + 3 updated + 2 new test files):

**New source files (2):**
- `src/AgentEval/_kernel/discovery.py` (~200L) — 3 typed group accessors + register_adapter + get_adapter + AdapterDiscoveryError raise sites + lru_cache discovery cache
- `src/AgentEval/_kernel/guardrails.py` (~250L) — `@guarded_fanout(estimator=callable)` decorator + 3-layer enforcement + ContextVar-bound cancellation event + current_cancel_event accessor + `_current_cost_usd_for_run` Phase-1 stub

**New test files (2):**
- `tests/unit/kernel/test_discovery.py` (~250L) — 12+ tests covering 3 group accessors + register/get + AdapterDiscoveryError + broken-entry-point + partial-install + collision warning + lru_cache
- `tests/unit/kernel/test_guardrails.py` (~280L) — 14+ tests covering 3 layers + cancellation + estimator=None + ContextVar propagation + error message format + meter_interval_seconds

**Updated files (3):**
- `src/AgentEval/errors.py` — pure extension: 2 new sub-bases + 3 new leaves
- `tests/unit/test_errors.py` — extended: 6+ new tests covering new sub-bases + leaves + hierarchy
- `docs/contracts/stability-surface.md` — register new public surface entries for discovery + guardrails + extended errors
- `docs/contracts/error-class-hierarchy.md` — mark 3 leaves as IMPLEMENTED (Story 1b.3)

## Change Log

| Date       | Version | Description                                                                  | Author |
| ---------- | ------- | ---------------------------------------------------------------------------- | ------ |
| 2026-05-19 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (7th consecutive use of `feedback_spec_vs_ratified_doc_precheck`) caught 8 drifts in Story 1b.3 spec: (D1 HIGH) entry-point groups → 6 tables per ADR-013 L47; (D2 HIGH) `@guarded_fanout` signature `cost_kwarg/runtime_kwarg` → `estimator=callable` per ADR-015 §Decision L18; (D3 HIGH) 2-layer → 3-layer enforcement per ADR-015 §Decision L25-29; (D4 MED) `UnknownAdapterError` → `AdapterDiscoveryError` per contract L82; (D5 MED) errors.py adds 2 sub-bases + 3 leaves; (D6 MED) `CodingAgentAdapter` TYPE_CHECKING forward-ref; (D7 MED) `KeywordTierMissingError` deferred to Story 1b.6 per Many's pick; (D8 LOW) ADR-013 filename drift in architecture L1426 → fixed pre-authoring. All 8 resolved by honoring ratified sources; epics.md L933-941 (Story 1b.3) + architecture.md L1426 updated pre-authoring per "fix-the-losing-source-NOW" pattern. NEW NORM from Epic 1a retro (`feedback_citation_drift_first_class`) embedded in AC-1b.3.11. Phase-1 limitations explicitly documented (Layer 2 cost-meter stub until Story 4.1; cooperative-cancellation hook ships but provider-client integration is Story 4.1; CodingAgentAdapter TYPE_CHECKING forward-ref). | Bob |
