# Story 1b.1: Foundational Kernel — Context + Tier + Async Bridge

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **subsequent-epic implementer** (Epics 2-8b),
I want **the three foundational `_kernel/` modules — `context.py` (per-test scope + MCPLifecycleManager + FR41 config precedence), `tier.py` (`@tier(N)` decorator + libdoc badge), `run_async.py` (async-to-sync bridge per ADR-012) — implemented and unit-tested**,
So that **every other kernel module + sub-library can build on a stable per-test-scope / tier / async-bridge / config-precedence foundation without re-deriving primitives, AND Story 0.2's load-bearing `_kernel/context.py` draft (12+ deferred-work items + atexit-on-SIGTERM auto-handler) is integrated into production with full empirical coverage**.

## Acceptance Criteria

> **Pre-create-story drift check (5th consecutive use of `feedback_spec_vs_ratified_doc_precheck`, 2026-05-18):** 6 drifts caught in Story 1b.1 spec vs ratified sources. Per Many's 2026-05-18 ratification, ALL 6 resolved by honoring ratified sources (Story 0.2 spike findings §`_kernel/context.py` draft + architecture L314/L410/L620/L1554/L1659 + ADR-009/ADR-012/ADR-015 + Story 1a.6's docstring + deferred-work.md L40-47). Updated `epics.md` Story 1b.1 AC + `.env.example` pre-authoring. Drifts resolved: (1) mcp_per_test enum translation (Library kwarg `bool | Literal["suite"]` vs internal Scope `Literal["test", "suite", "process"]`) — added `_resolve_scope()` translator; (2) `_kernel/context.py` scope underspecification — full spike-findings surface lifted; (3) `tier.py` attribute name `__agenteval_tier__` → `_agenteval_tier` (architecture L620); (4) `ADR-A1` → `ADR-012`; (5) FR41 wiring assigned to Story 1b.1 explicitly (Story 1a.6's docstring expected it here); (6) TestContext kept as lightweight scope-info holder + ContextVar-backed.

1. **AC-1b.1.1 — `_kernel/context.py` exposes the internal `Scope` enum + `_resolve_scope()` translator.** Module-level `Scope = Literal["test", "suite", "process"]` matches Story 0.2 spike's `MCPLifecycleManager.scope`. `_resolve_scope(mcp_per_test: bool | Literal["suite"]) -> Scope` is the SINGLE canonical translator between the user-facing Library kwarg vocabulary (FR42 + ADR-009 + Story 1a.6: `True` / `"suite"` / `False`) and the internal Scope vocabulary. Mapping: `True → "test"`, `False → "process"`, `"suite" → "suite"`. Translator is registered as `provisional` in `stability-surface.md` Phase-1 registry.

2. **AC-1b.1.2 — `_kernel/context.py` exposes `TestContext` dataclass + ContextVar-backed accessor/lifecycle.** `TestContext` dataclass with `test_id: str`, `suite_id: str`, `scope: Scope` (uses the internal Scope enum). ContextVar-backed `current_context() -> TestContext | None` accessor + `bind_context(ctx: TestContext) -> None` / `unbind_context() -> None` lifecycle functions. Architecture L1554's module-level `set_current_test_id(test_id: str, suite_id: str = "", scope: Scope = "test") -> None` is implemented as a convenience wrapper around `bind_context()`. ContextVar isolation across threads MUST be enforced (test A's `current_context()` never returns test B's TestContext).

3. **AC-1b.1.3 — `_kernel/context.py` exposes `MCPLifecycleManager` + 4 dataclasses per Story 0.2 spike findings §`_kernel/context.py` draft (L273-414).** LOAD-BEARING source: the spike's 18 review patches (P2.1-P2.18) + D2.4 atexit-on-SIGTERM finding are INTEGRATED, not optional. The module exposes:
   - **`ServerSpec`** (frozen dataclass) with `command: Sequence[str]`, `marker: str`, `startup_timeout_s: float = 10.0`, `shutdown_timeout_s: float = 2.0`, `env: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))` (P2.15 — `frozen=True` does NOT freeze the dict; MappingProxyType is the fix).
   - **`ServerHandle`** dataclass with `handle_id: str`, `spec: ServerSpec`, `process: subprocess.Popen`, `spawned_at_unix: float`, `test_id: str | None`, `suite_id: str | None`.
   - **`ReleaseResult`** dataclass with `handle_id: str`, `pid: int`, `spawned_at_unix: float`, `released_at_unix: float`, `process_lifetime_ms: float` (P2.2 rename — NOT `startup_latency_ms`; field measures spawn-to-terminate-start lifetime, not startup), `shutdown_latency_ms: float`, `signaled_with: Literal["SIGTERM", "SIGKILL", "already-dead", "failed-EPERM"]`, `killed_by_timeout: bool`.
   - **`MCPLifecycleManager(scope: Scope, *, default_spec: ServerSpec | None = None, install_sigterm_handler: bool = True)`** class with methods:
     - `acquire(*, test_id: str, suite_id: str, spec: ServerSpec | None = None) -> ServerHandle`
     - `release_test(test_id: str) -> list[ReleaseResult]`
     - `release_suite(suite_id: str) -> list[ReleaseResult]`
     - `shutdown_all() -> list[ReleaseResult]`
     - `__init__` registers `atexit.register(self.shutdown_all)` failsafe (P2.16: also document that `atexit.unregister` is the caller's responsibility on long-lived processes).
     - `__init__` AUTO-INSTALLS a SIGTERM→`sys.exit(0)` handler by default (D2.4 LOAD-BEARING finding — Python's default SIGTERM does NOT run atexit; this handler converts SIGTERM to `sys.exit(0)` which DOES run atexit). Configurable via `install_sigterm_handler=False`.

4. **AC-1b.1.4 — All 12+ Story 0.2 deferred-work items are applied to `_kernel/context.py`.** See `deferred-work.md` L40-47. Specifically:
   - `threading.RLock` (NOT `Lock`) — atexit reentry safety (P2.8).
   - Spawn `subprocess.Popen` OUTSIDE the lock (Popen-under-lock serializes all acquires + child inherits parent's atexit).
   - Use `pid` directly as pgid since `subprocess.Popen(start_new_session=True)` — do NOT call `os.getpgid(pid)` (P-edge fix).
   - Distinguish `EPERM` from `ESRCH` in `_kill` (currently both silently swallowed; EPERM falsely reports SIGKILL success).
   - Post-kill liveness verification before recording success (D-state survivors). Use `os.waitpid(pid, os.WNOHANG)` or short `Popen.wait(timeout=0.1)` then re-check `Popen.poll()`.
   - Always record release events for state transitions — currently dead-and-replaced handles drop silently. Every `acquire`/`release_*`/`shutdown_all` MUST emit a `ReleaseResult` even when the process was already dead.
   - Minimize child env (`os.environ.copy()` leaks credentials to third-party MCP servers). Whitelist approach: pass only `PATH`, `HOME`, `LANG`, `LC_ALL`, plus any explicit keys in `ServerSpec.env`. Document the whitelist in module docstring.
   - `startup_timeout_s` is currently caller-tracked (the lifecycle manager returns immediately after `Popen`). For Phase-1, document this in `acquire()`'s docstring: "Returns immediately after `subprocess.Popen()`; readiness check is the caller's responsibility (Epic 3 Story 3.1's MCP handshake)." Field is preserved for future use; do NOT remove from API (P2.4 decision — document, don't implement).
   - Split `shutdown_latency_ms` semantics: include in ReleaseResult AS-IS for Phase-1 (= `terminate_start → Popen.wait() returns`, includes both signal delivery + kernel reap). Future story may split into `terminate_to_signal_delivered_ms` + `signal_to_reaped_ms` if needed.
   - Auto-installed SIGTERM handler default is `install_sigterm_handler: bool = True` per D2.4 production-safe behavior.
   - Document atexit-on-SIGKILL as **UNRECOVERABLE at listener layer** in module docstring — operator must teardown via systemd cgroup / container-level mitigation. This is a known limitation, not a bug.

5. **AC-1b.1.5 — `_kernel/context.py` ALSO wires FR41 (config precedence: kwarg → env-var → `.env` → defaults).** Per Story 1a.6's `__init__.py` docstring + `stability-surface.md` Phase-1 registry, `_kernel/context.py` is the home for FR41. Module exposes:
   - `resolve_config(kwarg_overrides: dict[str, Any]) -> dict[str, Any]` — takes kwarg overrides + reads `AGENTEVAL_*` env-vars (per `.env.example`) + loads `.env` if present + falls back to PRD FR42 defaults; returns the precedence-resolved config dict.
   - **Precedence order (highest wins):** `kwarg_overrides` > `os.environ["AGENTEVAL_*"]` > `.env` file (parsed via simple key=value reader, NOT a third-party `python-dotenv` dependency for Phase-1 minimalism) > FR42 + FR11b defaults.
   - **Type coercion:** env-var values are strings; coerce per param type (`provider: str` raw; `telemetry: bool` via "true/false" parse; `mcp_per_test: bool | Literal["suite"]` accepting "true"/"false"/"suite"; `default_temperature: float` via `float()`; `max_cost_usd: float` via `float()`; `max_runtime_seconds: float | None` empty-string→None else float; etc.). Invalid coercion raises a typed `ConfigParseError` from `_kernel/errors.py` (Story 1b.5 lands the error class; until then, raise `ValueError` with a TODO comment to migrate).
   - **`.env.example` is the canonical env-var name source** — Story 1b.1 also updates `AgentEval.__init__` (in `src/AgentEval/__init__.py`) to call `_resolve_scope(mcp_per_test)` and `resolve_config(kwargs)` so `Get Effective Config` returns precedence-resolved values (Story 1a.6's Phase-1 limitation note removed from stability-surface.md + the `__init__` docstring updated).
   - Unit tests cover all 4 precedence layers + per-param type coercion + missing-env-var fallback + `.env` parsing + invalid-coercion `ValueError`/`ConfigParseError` path.

6. **AC-1b.1.6 — `_kernel/tier.py` exposes `@tier(N)` decorator + accessors.** `@tier(N: Literal[1, 2, 3])` decorator factory attaches **`_agenteval_tier`** attribute (single-underscore convention per architecture L620 — NOT `__agenteval_tier__` dunder) to the decorated function. `get_keyword_tier(func) -> int | None` accessor returns the tier or None. `tier_badge(tier: int) -> str` helper returns libdoc badge text exactly: `"[Tier 1 — Deterministic]"`, `"[Tier 2 — Stochastic Single-Shot]"`, `"[Tier 3 — Stochastic Fan-Out]"`. Invalid tier (any int outside {1, 2, 3}) raises `ValueError("tier must be 1, 2, or 3")`.

7. **AC-1b.1.7 — `_kernel/run_async.py` exposes `_run_async(coro)` per ADR-012 (was ADR-A1).** Runs the coroutine via `asyncio.run()` from a synchronous context; when called from an already-running event loop (IDE runners, nested test executions), falls back to a fresh thread running `asyncio.run()` and joining synchronously. No `nest_asyncio` import. Exceptions raised inside the coroutine propagate to the caller verbatim. Module-level CI enforcement (per architecture L966) is deferred to Story 1b.6 (the 5 conventions tests) — Story 1b.1 just ships the canonical bridge.

8. **AC-1b.1.8 — Unit tests in `tests/unit/kernel/test_{context, tier, run_async}.py`.** Coverage per AC-1b.1.1 → AC-1b.1.7:
   - `test_context.py`: `_resolve_scope` 3 mappings + bool default-True; `TestContext` bind/unbind round-trip; ContextVar isolation across threads (use `threading.Thread` with separate ContextVar copy assertion); `MCPLifecycleManager.acquire/release_test/release_suite/shutdown_all` per scope ("test" / "suite" / "process") using a fake `subprocess.Popen`-shaped class as the spawn point (mock `subprocess.Popen` via dependency-injection in `ServerSpec.command` or via monkey-patching — pick the cleaner one); atexit failsafe registered; SIGTERM auto-handler installed (verify via `signal.getsignal(signal.SIGTERM)`); FR41 `resolve_config` precedence (kwarg > env > .env > defaults); FR41 type coercion for each param; FR41 invalid-coercion raises; minimize-env whitelist verified.
   - `test_tier.py`: decorator attaches `_agenteval_tier` attribute (NOT dunder); `get_keyword_tier` returns int and None; `tier_badge` returns exact strings for 1/2/3; invalid tier raises `ValueError`.
   - `test_run_async.py`: sync-context invocation returns expected value; nested-loop fallback path (use `asyncio.new_event_loop()` + `loop.run_until_complete()` to simulate a running loop, then call `_run_async()` within it); exception propagation (raise inside coro, assert raised at caller).
   - **All tests MUST run real assertions in CI**, not just `--collect-only`. Per the Story 1a.6 HIGH-1 lesson generalized to `tests/unit`.

9. **AC-1b.1.9 — `ci.yml` restructured to actually-execute `tests/unit` (HIGH-1 lesson generalized).** Split `tests/unit` from the collect-only sweep into a dedicated `uv run pytest tests/unit -q` step (no `--collect-only`, no exit-5 leniency). The collect-only sweep narrows further to only `tests/unit/conventions` (still placeholder until Story 1b.6 lands the 5 enforcement tests). Verify locally: `uv run pytest tests/unit -q` returns 0 with real assertions; `uv run pytest tests/unit/conventions -q --collect-only` continues to exit 5 (accepted Phase-1 leniency).

10. **AC-1b.1.10 — `src/AgentEval/__init__.py` integration with `_resolve_scope` + `resolve_config`.** `AgentEval.__init__` calls `resolve_config(kwarg_dict)` to get the precedence-resolved config dict, then sets `self._{provider, telemetry, trace_backend, ...}` from the resolved values. The `mcp_per_test` kwarg gets `_resolve_scope(mcp_per_test)` applied to produce `self._scope: Scope` for internal use; `self._mcp_per_test` remains the user-vocab value for `Get Effective Config` backward compatibility. Story 1a.6's `__init__.py` docstring is updated to remove the Phase-1 "kwarg-only effective resolution" limitation note. `stability-surface.md` Phase-1 registry entry for `Get Effective Config` is upgraded from "Phase-1: kwarg-only" to "Phase-1: precedence-resolved per FR41". The 6 Story 1a.6 FR42 acceptance tests MUST continue to pass (they test Library defaults via kwarg-only invocation, which is the top precedence layer — should remain correct).

11. **AC-1b.1.11 — All-gates clean.** `uv run ruff check src/ tests/` clean; `uv run ruff format --check src/ tests/` clean; `uv run mypy --strict src/` clean (note: Story 1a.2's `ci.yml` step is just `mypy src/` without `--strict`; Story 1b.1 dev MAY tighten to `--strict` if `mypy.ini` supports it cleanly, otherwise document as Phase-1.5 carry-over and use `mypy src/`); `uv run python scripts/check-license-headers.py` PASS (header on every new `.py`); `uv run pytest tests/acceptance/tier1 -q` returns the 6 FR42 tests still passing; `uv run robot tests/acceptance/smoke` returns smoke test still passing; `uv run pytest tests/unit -q` returns ALL new kernel unit tests passing (real execution per HIGH-1 fix).

12. **AC-1b.1.12 — Code-review prompt embeds the citation-drift re-derivation directive (Epic 1a retro action #4 / `feedback_citation_drift_first_class`).** When `/bmad-code-review (Using current Claude + Codex CLI subagent)` runs for Story 1b.1, the cross-LLM-reviewer prompt MUST include: *"For every citation in the changed files — 'per ADR-012', 'per spike findings §`_kernel/context.py` draft', 'architecture L1554 says', 'P2.2 review', etc. — open the cited source and verify the claim is EXACTLY what the source says. Flag any mismatches even if subtle (rename, count drift, slug drift, off-by-one). Citation drift is the #1 finding category across Epic 1a."* This directive is repeated in the story's Dev Notes "Project norms applied" section.

## Tasks / Subtasks

- [x] **Task 1: Author `src/AgentEval/_kernel/run_async.py` (AC: 1b.1.7)**
  - [x] Apache 2.0 license header.
  - [x] Module docstring citing ADR-012 (NOT ADR-A1) + architecture L932-966.
  - [x] `_run_async(coro: Coroutine[Any, Any, T]) -> T` function — uses `asyncio.run()` from sync context; nested-loop fallback via `threading.Thread` + `loop.run_until_complete` in the new thread + `thread.join()`; no `nest_asyncio` import.
  - [x] Exception propagation: capture exception in thread, re-raise at the joining thread.
  - [x] Type hints: `from typing import TypeVar`; `T = TypeVar("T")`; `_run_async(coro: Coroutine[Any, Any, T]) -> T`.
  - [x] Verify with `uv run mypy src/AgentEval/_kernel/run_async.py`.

- [x] **Task 2: Author `src/AgentEval/_kernel/tier.py` (AC: 1b.1.6)**
  - [x] Apache 2.0 license header.
  - [x] Module docstring citing architecture L620 (`_agenteval_tier` attribute name) + Decision-1.
  - [x] `@tier(N: Literal[1, 2, 3])` decorator factory: returns a decorator that sets `func._agenteval_tier = N` and returns `func`. Validate N at decoration time; raise `ValueError("tier must be 1, 2, or 3")` for any other int.
  - [x] `get_keyword_tier(func: Callable) -> int | None` — returns `getattr(func, "_agenteval_tier", None)`.
  - [x] `tier_badge(tier: int) -> str` — returns exact strings per AC-1b.1.6. For invalid tier, raises `ValueError`.
  - [x] Verify with `uv run mypy src/AgentEval/_kernel/tier.py`.

- [x] **Task 3: Author `src/AgentEval/_kernel/context.py` — Phase A: Scope + TestContext + ContextVar (AC: 1b.1.1, 1b.1.2)**
  - [x] Apache 2.0 license header.
  - [x] Module docstring: cite Story 0.2 spike findings §`_kernel/context.py` draft (L273-414) as the LOAD-BEARING source; cite architecture L1198 + L1502 + L1554 for Listener v3 wiring; cite ADR-009 + architecture L314 for `mcp_per_test` 3-mode vocabulary; cite `deferred-work.md` L40-47 for the 12+ applied review fixes; cite D2.4 for atexit-on-SIGTERM auto-handler.
  - [x] `Scope = Literal["test", "suite", "process"]`.
  - [x] `_resolve_scope(mcp_per_test: bool | Literal["suite"]) -> Scope` — exact mapping per AC-1b.1.1. Add unit-test-friendly docstring with explicit truth table.
  - [x] `@dataclass(frozen=True) class TestContext` with `test_id: str`, `suite_id: str`, `scope: Scope`.
  - [x] `_current_context_var: ContextVar[TestContext | None] = ContextVar("agenteval_current_context", default=None)`.
  - [x] `current_context() -> TestContext | None` — `return _current_context_var.get()`.
  - [x] `bind_context(ctx: TestContext) -> None` — `_current_context_var.set(ctx)`. Returns nothing; ContextVar Token discarded for Phase-1 simplicity (caller calls `unbind_context()` to clear).
  - [x] `unbind_context() -> None` — `_current_context_var.set(None)`.
  - [x] `set_current_test_id(test_id: str, suite_id: str = "", scope: Scope = "test") -> None` — convenience wrapper that builds a `TestContext` + calls `bind_context()`. Honors architecture L1554's flow.

- [x] **Task 4: Author `src/AgentEval/_kernel/context.py` — Phase B: ServerSpec + ServerHandle + ReleaseResult (AC: 1b.1.3)**
  - [x] `@dataclass(frozen=True) class ServerSpec` with fields per AC-1b.1.3. `env` field uses `MappingProxyType` (P2.15). Provide a `ServerSpec.create(command, marker, ..., env: dict | None = None) -> ServerSpec` classmethod that wraps the input dict in `MappingProxyType(dict(env or {}))` for caller ergonomics.
  - [x] `@dataclass class ServerHandle` per AC-1b.1.3.
  - [x] `@dataclass class ReleaseResult` per AC-1b.1.3. Note the P2.2 rename: `process_lifetime_ms`, NOT `startup_latency_ms`.

- [x] **Task 5: Author `src/AgentEval/_kernel/context.py` — Phase C: MCPLifecycleManager core (AC: 1b.1.3, 1b.1.4)**
  - [x] `class MCPLifecycleManager` with `__init__(self, scope: Scope, *, default_spec: ServerSpec | None = None, install_sigterm_handler: bool = True)`.
  - [x] `__init__` initializes `self._scope`, `self._default_spec`, `self._lock = threading.RLock()` (P2.8 — RLock, NOT Lock), `self._handles: dict[str, ServerHandle] = {}` (key: handle_id), `self._handles_by_test: dict[str, list[str]] = {}` (test_id → handle_ids), `self._handles_by_suite: dict[str, list[str]] = {}` (suite_id → handle_ids).
  - [x] `acquire(*, test_id: str, suite_id: str, spec: ServerSpec | None = None) -> ServerHandle`:
    - Resolve spec: caller spec > self._default_spec; raise `ValueError` if neither provided (P2.14).
    - Build child env: minimize per deferred-work — whitelist {PATH, HOME, LANG, LC_ALL} from os.environ + apply `spec.env` overlay.
    - Build the Popen kwargs: `args=spec.command + [spec.marker]`, `start_new_session=True`, `env=minimized_env`, `stdout=subprocess.PIPE`, `stderr=subprocess.PIPE`.
    - **Spawn OUTSIDE the lock** (Popen-under-lock serializes all acquires).
    - **After spawn, acquire `self._lock` and register**: build `ServerHandle`, append to `self._handles_by_test[test_id]` and `self._handles_by_suite[suite_id]`, return handle.
    - Use `pid` directly as pgid (NOT `os.getpgid(pid)`) — safe per `start_new_session=True`.
  - [x] `release_test(test_id: str) -> list[ReleaseResult]`: with lock, pop the handle_ids for test_id, call `_kill_and_record(handle)` for each, return `list[ReleaseResult]`.
  - [x] `release_suite(suite_id: str) -> list[ReleaseResult]`: with lock, pop the handle_ids for suite_id, call `_kill_and_record(handle)` for each, return.
  - [x] `shutdown_all() -> list[ReleaseResult]`: with lock, drain all handles, call `_kill_and_record(handle)` for each.
  - [x] `_kill_and_record(handle: ServerHandle) -> ReleaseResult` private method:
    - Record `terminate_start = time.monotonic()`.
    - If `handle.process.poll() is not None`: already dead; record `signaled_with="already-dead"` (P-edge fix — emit ReleaseResult even for dead-and-replaced handles).
    - Else: try `os.killpg(handle.process.pid, signal.SIGTERM)`:
      - Catch `OSError` per errno: if `e.errno == errno.EPERM`: record `signaled_with="failed-EPERM"`, return; if `e.errno == errno.ESRCH`: process already gone, treat as `"already-dead"`. (P-edge fix — distinguish EPERM from ESRCH).
    - `handle.process.wait(timeout=spec.shutdown_timeout_s)`:
      - On `subprocess.TimeoutExpired`: escalate to SIGKILL via `os.killpg(handle.process.pid, signal.SIGKILL)`; record `signaled_with="SIGKILL"`, `killed_by_timeout=True`.
      - Else: record `signaled_with="SIGTERM"`, `killed_by_timeout=False`.
    - **Post-kill liveness verification** (deferred-work fix): `handle.process.poll()` MUST return non-None before recording success. D-state survivors → re-raise as a `RuntimeError` (Phase-1) or `MCPShutdownFailed` once Story 1b.5's `_kernel/errors.py` lands.
    - Build `ReleaseResult` with `process_lifetime_ms` (= `(terminate_start - handle.spawned_at_unix) * 1000`) + `shutdown_latency_ms` (= measured wait + escalation time).
    - Return the ReleaseResult.

- [x] **Task 6: Author `src/AgentEval/_kernel/context.py` — Phase D: atexit + auto-installed SIGTERM handler (AC: 1b.1.3, 1b.1.4)**
  - [x] `MCPLifecycleManager.__init__`: `atexit.register(self.shutdown_all)` — registered AFTER `__init__` state is initialized; cite P2.16 in module docstring (`atexit.unregister(self.shutdown_all)` is the caller's responsibility on long-lived processes).
  - [x] `MCPLifecycleManager.__init__`: if `install_sigterm_handler`: install a SIGTERM handler that calls `sys.exit(0)` — this is the D2.4 LOAD-BEARING finding (Python's default SIGTERM does NOT run atexit; converting to `sys.exit(0)` does). Pseudocode:
    ```python
    if install_sigterm_handler:
        import signal
        signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
    ```
  - [x] Document atexit-on-SIGKILL **UNRECOVERABLE** in module docstring per D2.2 — operator must teardown via systemd cgroup / container-level mitigation. Cite Phase-1.5 carry-over for parent-side reaper.

- [x] **Task 7: Author `src/AgentEval/_kernel/context.py` — Phase E: FR41 config precedence (AC: 1b.1.5)**
  - [x] `def _parse_env_value(raw: str, target_type: type) -> Any` — simple type coercion helper.
  - [x] `def _load_dotenv(path: Path = Path(".env")) -> dict[str, str]` — minimal `.env` parser (no `python-dotenv` dependency): read lines, skip comments (`#` prefix) + blank lines, split on first `=`, return dict.
  - [x] `def resolve_config(kwarg_overrides: dict[str, Any]) -> dict[str, Any]` — implements the 4-layer precedence per AC-1b.1.5. Returns dict with keys matching PRD FR42 + FR11b param names exactly. Calls `_resolve_scope()` for `mcp_per_test` AFTER resolution (so the user-vocab value is preserved for `Get Effective Config`).
  - [x] Document AGENTEVAL_* env-var names in module docstring + cross-reference to `.env.example`.

- [x] **Task 8: Author unit tests under `tests/unit/kernel/` (AC: 1b.1.8)**
  - [x] Create `tests/unit/kernel/__init__.py` (empty + Apache 2.0 header).
  - [x] `tests/unit/kernel/test_run_async.py`: 3 tests minimum (sync invocation, nested-loop fallback, exception propagation).
  - [x] `tests/unit/kernel/test_tier.py`: 4 tests minimum (decorator attaches `_agenteval_tier`, get_keyword_tier returns int + None, tier_badge exact strings, invalid tier raises ValueError).
  - [x] `tests/unit/kernel/test_context.py`: 15+ tests covering AC-1b.1.1 → AC-1b.1.5 (resolve_scope 3 mappings + truth-table; TestContext bind/unbind; ContextVar thread isolation; MCPLifecycleManager.acquire/release per scope using a fake-Popen fixture; atexit register; SIGTERM auto-handler signal.getsignal; resolve_config 4 precedence layers; type coercion per param; invalid coercion raises; minimize-env whitelist verified).
  - [x] Use `pytest` fixtures + `monkeypatch` for env-var manipulation. Use a `FakePopen` class for subprocess injection (or monkey-patch `subprocess.Popen`).

- [x] **Task 9: Restructure `ci.yml` to actually-execute `tests/unit` (AC: 1b.1.9)**
  - [x] Edit `.github/workflows/ci.yml`: above the current "pytest Phase-1 collect-only sweep" step, add a NEW step: `name: pytest tests/unit (real tests)` running `uv run pytest tests/unit -q`. No `--collect-only`. No exit-5 leniency.
  - [x] Update the collect-only sweep step to drop `collect tests/unit` from the function calls; the sweep now covers only `collect tests/unit/conventions` (still placeholder).
  - [x] Update the comment block above the sweep step to reflect the new state (3 dirs now real-execute: tier1 + smoke + unit; only `tests/unit/conventions` remains placeholder).

- [x] **Task 10: Integrate `_resolve_scope` + `resolve_config` into `AgentEval.__init__` (AC: 1b.1.10)**
  - [x] Edit `src/AgentEval/__init__.py` `AgentEval.__init__`: collect kwargs into a dict; call `resolve_config(kwarg_dict)` → resolved dict; set each `self._<param>` from resolved dict.
  - [x] Compute `self._scope = _resolve_scope(resolved["mcp_per_test"])` for internal-API consumers.
  - [x] Update Story 1a.6's docstring (the FR41 limitation note) to reflect new state: precedence resolution now active per `_kernel/context.resolve_config` (Story 1b.1).
  - [x] Update `docs/contracts/stability-surface.md` AgentEval Library Surface subsection: `Get Effective Config` entry note changes from "Phase-1 returns kwarg-resolved values; env-var precedence (FR41) lands in Epic 1b" → "Phase-1 returns precedence-resolved (kwarg → env-var → `.env` → defaults) values per FR41 / `_kernel/context.resolve_config` (Story 1b.1)".
  - [x] Verify all 6 Story 1a.6 FR42 acceptance tests still pass (`uv run pytest tests/acceptance/tier1 -q` → 6 passed). The kwarg-only test paths are the top precedence layer; should remain correct.
  - [x] Verify Story 1a.6 RF smoke test still passes (`uv run robot tests/acceptance/smoke`).

- [x] **Task 11: All-gates pass + cross-LLM-ready (AC: 1b.1.11)**
  - [x] `uv run ruff check src/ tests/` — clean.
  - [x] `uv run ruff format --check src/ tests/` — clean (run `uv run ruff format src/ tests/` if anything's off).
  - [x] `uv run mypy src/` — clean (attempt `--strict` first; if too noisy, document Phase-1.5 carry-over + use non-strict).
  - [x] `uv run python scripts/check-license-headers.py` — PASS (all new `.py` files have the canonical Apache 2.0 header at prologue).
  - [x] `uv run pytest tests/unit -q` — all kernel unit tests PASS.
  - [x] `uv run pytest tests/acceptance/tier1 -q` — 6 FR42 tests still PASS (regression check after Task 10).
  - [x] `uv run robot tests/acceptance/smoke` — RF smoke test still PASS.
  - [x] `uv run pytest tests/unit/conventions -q --collect-only` — still exit 5 (accepted Phase-1 leniency).

### Review Findings

> **Code review 2026-05-18 — cross-LLM adversarial pair (Claude Opus 4.7 + Codex CLI 0.117.0) plus 3-layer Claude review trio (Blind Hunter / Edge Case Hunter / Acceptance Auditor).** 4 reviewers ran in parallel; 38 raw findings caught; 22 deduped. Codex CLI caught the star finding H1 (scope modes silently not implemented) that none of the 3 Claude reviewers saw — 6th + 7th consecutive demonstration of the same-family blind spot pattern that the `feedback_review_methodology_norms` + `feedback_citation_drift_first_class` norms exist to surface. Findings file: this section.

**decision-needed (1):**

- [x] [Review][Decision] H5 — `_UNSET` sentinel approach for FR41 kwarg-not-passed signaling — Resolved per Many's pick: option (a) keep `_UNSET`, add `__repr__` returning `"_UNSET"`. Implemented via `_UnsetType` singleton class with stable `__repr__` for libdoc determinism. (src/AgentEval/__init__.py L61, L130-141) — Currently `_UNSET: Any = object()`; libdoc renders the default as `<object object at 0x7f...>` with a memory address (non-reproducible builds → could break docs-build CI determinism) AND type annotations `provider: str = _UNSET` lie to mypy strict-mode. Three alternatives: (a) keep `_UNSET`, add `__repr__` that returns `"_UNSET"` (minimal change, libdoc deterministic); (b) drop `_UNSET`, use `None` everywhere as the "not passed" sentinel + change `max_runtime_seconds: float | None = None` and have callers wanting "explicit None override" use a separate marker; (c) keep FR42 defaults in signature (`provider: str = "litellm"`) + use a comparison-against-default check inside `__init__` (loses the "user passed default explicitly" disambiguation).

**patch (18):**

- [x] [Review][Patch] H1 — Suite/process scope NOT IMPLEMENTED; `acquire()` always spawns new Popen regardless of `scope`; Codex caught the gap [src/AgentEval/_kernel/context.py:351-393] — spike findings §`_kernel/context.py` draft's P2.19 idempotency contract was dropped silently; `mcp_per_test="suite"` and `mcp_per_test=False` are functionally identical to `True`. Fix: key live handles by scope identity, reuse existing live handles on `acquire()`, make `release_test()` a no-op outside `"test"` scope.
- [x] [Review][Patch] H2 — `process_lifetime_ms` clock mixing: `time.monotonic() - time.time()` = garbage (negative billions) [src/AgentEval/_kernel/context.py:381 + L466,488,503,537] — 3-way confirmation (Blind Hunter + Acceptance Auditor + Codex). Fix: store `spawned_at_monotonic = time.monotonic()` at spawn time AND keep `spawned_at_unix` for `released_at_unix` deltas; compute `process_lifetime_ms` from the monotonic pair.
- [x] [Review][Patch] H3 — FR41 explicit `kwarg=None` falls through to env-var, violating AC-1b.1.5 + `__init__` comment claiming the opposite [src/AgentEval/_kernel/context.py:resolve_config Layer-1 + tests/unit/kernel/test_context.py::test_resolve_config_kwarg_none_falls_through codifies wrong behavior] — 3-way confirmation. Fix: drop `is not None` predicate in resolve_config; `_UNSET` already handles "user did not pass"; update the test to assert the opposite.
- [x] [Review][Patch] H4 — `signal.signal(SIGTERM, ...)` from non-main-thread raises `ValueError` [src/AgentEval/_kernel/context.py:332-333] — 2-way confirmation (Blind Hunter + Edge Case Hunter). Fix: guard with `if threading.current_thread() is threading.main_thread()` and log a warning otherwise; atexit failsafe still fires either way.
- [x] [Review][Patch] H6 — `_run_async` worker thread does NOT inherit caller `ContextVar` [src/AgentEval/_kernel/run_async.py:73-88] — architecture's per-test `test_id` contract silently broken in nested-loop scenarios (the WHOLE keyword surface in IDE-runner cases). Fix: `import contextvars; ctx = contextvars.copy_context()` before spawning; run `_runner` inside `ctx.run(_runner)`.
- [x] [Review][Patch] H7 — `_kill_and_record` D-state `RuntimeError` raised inside `[... for h in handles]` list-comprehension abandons remaining handles [src/AgentEval/_kernel/context.py:1060-1064] — 2-way confirmation. In atexit context, "defense-in-depth shutdown" becomes "stops at first stuck server". Fix: wrap each `_kill_and_record` call in `try/except`; emit `ReleaseResult(signaled_with="failed-EPERM")` or new `"survived"` literal for the survivor case; continue draining remaining handles; aggregate-raise at end if any survived.
- [x] [Review][Patch] M1 — PID race between `Popen.poll()` and `os.killpg()` could SIGTERM unrelated reaped+recycled PID under sustained pabot churn [src/AgentEval/_kernel/context.py:447-521] — Fix: call `Popen.wait(timeout=0)` to reap before `killpg`, or use `signal.pidfd_send_signal` on Linux ≥ 5.1 (Phase-1.5 carry-over OK for pidfd; immediate fix is the wait(0) reaping).
- [x] [Review][Patch] M2 — atexit failsafe accumulates one entry per `MCPLifecycleManager()` instantiation; SIGTERM handler clobbers prior handler each time [src/AgentEval/_kernel/context.py:329-335] — 2-way confirmation. Fix: add `close()` method that calls `atexit.unregister(self.shutdown_all)` + restores prior SIGTERM handler (capture in `__init__`); document the single-instance-per-process assumption otherwise.
- [x] [Review][Patch] M3 — `_resolve_scope` translator NOT registered as `provisional` in `stability-surface.md` per AC-1b.1.1 [docs/contracts/stability-surface.md] — direct AC violation. Fix: add `_resolve_scope` + the Story 1b.1-exposed `_kernel/context` public surface (Scope, TestContext, MCPLifecycleManager, resolve_config) to the Phase-1 registry as `provisional`. Note `_kernel/` is normally internal-only per the stability-surface "out-of-scope" section — for elements that need consumer-facing stability promises, register explicitly.
- [x] [Review][Patch] M4 — ADR-012 + ADR-015 filename citation drift [src/AgentEval/_kernel/run_async.py:27 + spec file L271] — actual filenames per `docs/adr/README.md`: `ADR-012-async-to-sync-bridge-kernel-module.md` (not `ADR-012-async-bridge-kernel.md`) + `ADR-015-cost-runtime-guardrail-decorator.md` (not `ADR-015-guarded-fanout-decorator.md`). EXACTLY the citation-drift pattern the new norm targets. Fix: grep `ADR-012-async-bridge-kernel\|ADR-015-guarded-fanout-decorator` repo-wide + correct all occurrences.
- [x] [Review][Patch] M5 — Missing TODO migration comments per AC-1b.1.5 Task 5 [src/AgentEval/_kernel/context.py several raise sites] — spec required `# TODO(Story 1b.5): replace ValueError with ConfigParseError` at each `raise ValueError` in `_coerce_env_value` / `_parse_bool` / `_parse_optional_float` + `# TODO(Story 1b.5): replace RuntimeError with MCPShutdownFailed` at the D-state survivor raise. Add them.
- [x] [Review][Patch] M6 — `shutdown_timeout_s=0` or negative not guarded; `Popen.wait(timeout=0)` raises `TimeoutExpired` immediately → every release escalates to SIGKILL [src/AgentEval/_kernel/context.py:ServerSpec + acquire/release path] — Fix: validate `shutdown_timeout_s > 0` (or `>= 0.1`) in `ServerSpec.__post_init__`; reject ≤ 0 with `ValueError`.
- [x] [Review][Patch] M7 — `_load_dotenv` doesn't strip surrounding quotes + doesn't handle `export ` prefix common in shell-sourced `.env` files [src/AgentEval/_kernel/context.py:_load_dotenv] — 2-way confirmation. Fix: after `key.strip()`, strip optional `export ` prefix; after `value.strip()`, strip matching surrounding `"`/`'`.
- [x] [Review][Patch] M8 — Unknown `AGENTEVAL_*` keys in `.env` silently ignored (typo `AGENTEVAL_PROVDER=anthropic` → no diagnostic) [src/AgentEval/_kernel/context.py:resolve_config] — Fix: after loading dotenv, warn on `AGENTEVAL_*` keys not in `_ENV_VAR_NAMES.values()`: `import warnings; for k in dotenv_values: if k.startswith("AGENTEVAL_") and k not in _ENV_VAR_NAMES.values(): warnings.warn(f"Unknown agenteval env-var: {k}", UserWarning)`.
- [x] [Review][Patch] M9 — O(N×M) reverse-index scan in `release_test`/`release_suite` [src/AgentEval/_kernel/context.py:399-403, 411-414] — 3-way confirmation. Fix: drop the nested `for suite_ids in self._handles_by_suite.values()` loop — use the `ServerHandle.suite_id` field directly: `self._handles_by_suite[handle.suite_id].remove(handle.handle_id)` with KeyError guard; clear empty keys.
- [x] [Review][Patch] L1 — `tier(N)` accepts `True`/`False` silently via `bool` ⊂ `int` subclass [src/AgentEval/_kernel/tier.py:tier validation] — `True in (1, 2, 3)` is True (since `True == 1`). Fix: `if type(n) is not int or n not in (1, 2, 3): raise ValueError(...)`.
- [x] [Review][Patch] L2 — Test patches `signal.signal` to verify SIGTERM handler install; AC-1b.1.8 specifies `signal.getsignal(signal.SIGTERM)` form [tests/unit/kernel/test_context.py::test_mcplifecyclemanager_installs_sigterm_handler_by_default] — Fix: change test to save/restore prior SIGTERM handler in a fixture, then call `MCPLifecycleManager("test", install_sigterm_handler=True)` and assert `signal.getsignal(signal.SIGTERM) is _sigterm_to_sysexit`.
- [x] [Review][Patch] L3 — `_isolate_agenteval_env` fixture's `monkeypatch.chdir(tmp_path)` is over-cautious + a footgun for future tier1 fixtures with relative paths [tests/acceptance/tier1/conftest.py] — `.env` (not `.env.example`) doesn't exist in the repo root, so chdir is unnecessary for the documented hermeticity goal. Fix: remove `monkeypatch.chdir(tmp_path)` + `tmp_path` parameter; just delete AGENTEVAL_* env-vars.
- [x] [Review][Patch] L4 — `_parse_bool` accepts undocumented `on`/`off` [src/AgentEval/_kernel/context.py:_parse_bool] — Fix: document the full accepted vocabulary (`true`/`false`/`1`/`0`/`yes`/`no`/`on`/`off`) in `.env.example` comment, OR restrict to `true`/`false`/`1`/`0` only and update tests.
- [x] [Review][Patch] L5 — `ServerSpec` direct constructor (not `.create`) doesn't deep-copy `env` → caller mutations leak through `MappingProxyType` view [src/AgentEval/_kernel/context.py:ServerSpec] — Fix: add `__post_init__` to defensively re-wrap: `object.__setattr__(self, "env", MappingProxyType(dict(self.env)))`.

**defer (2):**

- [x] [Review][Defer] D1 — `tier(N)` decorator fails on built-ins / C-extension callables [src/AgentEval/_kernel/tier.py] — pre-existing language constraint; Story 1b.6 convention enforcer will catch `@keyword`-decorated methods that don't accept `@tier()` annotation. Deferred to Story 1b.6.
- [x] [Review][Defer] D2 — `_FakePopen._next_pid` shared class-level state, not reset across tests [tests/unit/kernel/test_context.py] — pre-existing test infrastructure smell; no current bug since no test asserts a specific PID range. Deferred (revisit if any future test grows a PID-specific assertion).

**dismiss (1):**

- DI1 — `_resolve_scope` mixed `is True` / `is False` / `== "suite"` narrowing (Edge Case Hunter LOW) — intentional bool-strict design per AC-1b.1.1 (`bool` ⊂ `int` makes `==` unsafe for True/False; the mixed form is correct). Dismissed as noise.

**Cross-LLM coverage stats (Epic 1b Story 1b.1 review):**

| Reviewer | Solo catches | Cross-confirmed catches | Total |
|---|---|---|---|
| Blind Hunter (Claude Opus 4.7) | 4 | 4 | 8 |
| Edge Case Hunter (Claude Opus 4.7) | 7 | 4 | 11 |
| Acceptance Auditor (Claude Opus 4.7) | 4 | 5 | 9 |
| **Codex CLI 0.117.0 (cross-family)** | **1 (the H1 star catch + LOW citation drift)** | **3 (H2 + H3 + M4)** | **4** |

**7th consecutive cross-LLM review where Codex caught real findings.** This time the 3 Claude reviewers DID catch real bugs (Blind Hunter found the clock-mixing bug; Edge Case Hunter found ContextVar non-propagation; Acceptance Auditor found citation drift + AC violations). But **Codex was the only reviewer to catch the scope-modes-not-implemented bug** — the single most consequential defect in the entire diff, hiding behind the spike's "lift the API surface" framing (where the dev lifted the dataclasses + atexit/SIGTERM but silently dropped the P2.19 idempotency contract that distinguishes the 3 scope modes).

## Dev Notes

### Project context — Story 1b.1's place in Epic 1b

Story 1b.1 is the FOUNDATION for all 5 subsequent Epic 1b stories:
- **Story 1b.2** (trace_store + redaction + coverage) consumes `_kernel/context.current_context()` for per-test partitioning.
- **Story 1b.3** (discovery + guardrails) consumes `_kernel/run_async` for any async-library calls.
- **Story 1b.4** (CodingAgentAdapter Protocol + ABCs) consumes `_kernel/context.current_context()` + `_kernel/tier`.
- **Story 1b.5** (conformance harness) consumes `_kernel/context` for per-fixture isolation.
- **Story 1b.6** (Determinism Contract + 5 conventions tests) builds the convention enforcer that asserts `_run_async` is the ONLY allowed `asyncio.run` callsite, asserts `_agenteval_tier` is set on every `@keyword`, etc.

**Story 0.2 spike findings §`_kernel/context.py` draft (L273-414) is the LOAD-BEARING source for `_kernel/context.py`.** Read it line-by-line before authoring. The spike's hand-off explicitly says (line 77): *"This spike's `_kernel/context.py` draft IS load-bearing: Story 1b.1 lifts the API surface directly. The findings doc must contain function signatures, lifecycle hook semantics, and at minimum one docstring per function explaining cleanup guarantees."* The 18 review patches + D2.4 atexit-on-SIGTERM auto-handler are INTEGRATED, not optional.

### Architecture compliance

| Architecture reference | Story 1b.1 implementation |
|---|---|
| L314 — `mcp_per_test` 3-mode (`True` / `"suite"` / `False`) | Library kwarg vocab honored; `_resolve_scope()` translates to internal `Scope = Literal["test", "suite", "process"]` |
| L410 — dogfood CI startup compound mitigation | `Scope = "suite"` is supported; recipe-5 dogfood-CI ergonomics work |
| L620 — `@tier(1|2|3)` decorator factory; `_agenteval_tier` attribute (single-underscore) | Honored verbatim — NOT `__agenteval_tier__` dunder |
| L932-966 — Async-to-Sync Bridge Convention (ADR-A1 → ADR-012) | `_run_async()` is the canonical bridge; no `asyncio.run` outside this module |
| L1198 — `context.py # Listener v3 test_id propagation context helpers` | `set_current_test_id()` wrapper + `TestContext`/`bind_context`/`unbind_context` |
| L1502 — Per-test scope (Listener v3 test_id) | `_kernel/context.py` is the central scope module |
| L1534-1554 — Listener.start_test → set_current_test_id(test_id) → MCP spawned + adapters bound | Architecture flow honored via the `set_current_test_id` convenience wrapper |
| L1659 — 3-mode `mcp_per_test` via `_kernel/context.py` | The `_resolve_scope()` translator + `MCPLifecycleManager(scope=...)` complete the chain |
| ADR-012 (was ADR-A1) | Cited verbatim in `run_async.py` docstring + Task 1 |
| ADR-015 (was ADR-A5) | `max_cost_usd` + `max_runtime_seconds` env-vars added to `.env.example` pre-authoring; full `@guarded_fanout` is Story 1b.3 scope |
| ADR-009 (mcp_per_test: bool = True) | Honored; Story 1b.1's `_resolve_scope()` is the translator boundary |

### Story 0.2 spike findings — the load-bearing source

Read `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` §`_kernel/context.py` draft (L273-414) verbatim before authoring `_kernel/context.py`. The 18 review patches (P2.1-P2.18) are integrated into the draft — do NOT re-derive; lift the patches.

**Key load-bearing findings:**
- **D2.4 — atexit-on-SIGTERM auto-handler is LOAD-BEARING.** Python's default SIGTERM handler does NOT run atexit. The lifecycle manager auto-installs a SIGTERM→`sys.exit(0)` handler to enable atexit cleanup. Configurable via `install_sigterm_handler=False`.
- **D2.2 — atexit-on-SIGKILL is UNRECOVERABLE.** Operator must mitigate via systemd cgroup / container-level teardown. Document as known limitation.
- **P2.2 — field rename:** `startup_latency_ms` → `process_lifetime_ms` (current field measures lifetime, not startup).
- **P2.15 — `ServerSpec.env` immutability:** `frozen=True` doesn't freeze the dict; use `MappingProxyType`.
- **P2.8 — `threading.RLock`** (NOT Lock) for atexit reentry safety.
- **P-edge — `pid` directly as pgid** (NOT `os.getpgid(pid)`); safe per `start_new_session=True`.
- **P-edge — distinguish EPERM from ESRCH** in `_kill`.
- **P-edge — minimize child env** to whitelisted keys (`os.environ.copy()` leaks credentials).

### Spike's `_kernel/context.py` draft API (lift verbatim)

The spike findings doc §`_kernel/context.py` draft contains full type signatures + docstrings for:
- `Scope`, `ServerSpec`, `ServerHandle`, `ReleaseResult`, `MCPLifecycleManager.__init__/acquire/release_test/release_suite/shutdown_all`.

Story 1b.1 dev MUST lift these signatures + docstrings, NOT re-derive.

### Listener v3 wiring NOT in scope

`telemetry/otel_listener.py` (Epic 5 Story 5.1) calls the lifecycle manager via Listener v3 hooks (`start_test` / `end_test`). Story 1b.1 ships the lifecycle manager BUT NOT the listener wiring. The `set_current_test_id()` convenience wrapper is there for the listener to call when it lands.

### FR41 config precedence — Phase-1 minimalism

Phase-1 implementation does NOT use `python-dotenv`. The `.env` parser is a 10-line key=value reader. Reasons:
- Avoid adding a dependency for a trivial parser.
- Story 1a.1 dependency set is curated; `python-dotenv` would be the first non-curated add.
- `.env.example` is intentionally simple to keep the parser simple.

If `.env` parsing complexity grows (multi-line values, escape sequences, etc.), upgrade to `python-dotenv` in a future story.

### ci.yml unit-test path generalization (HIGH-1 lesson)

Story 1a.6's HIGH-1 finding: `tests/acceptance/tier1` was being collected-only in CI while the 6 FR42 tests reported "6 passed" locally. The fix: split tier1 into its own real-execute step (no `--collect-only`).

Story 1b.1 generalizes the lesson: `tests/unit` now lands real tests (the kernel unit tests). Same fix: split `tests/unit` into its own real-execute step. The collect-only sweep narrows further to ONLY `tests/unit/conventions` (still placeholder until Story 1b.6).

**Pattern:** every directory's first story that adds real tests MUST update `ci.yml` to drop `--collect-only` for that directory.

### Project debt cleanup (Story 1a.6 forward-refs become current-state)

Story 1a.6's `__init__.py` docstring says: *"env-var precedence (FR41) is wired by Epic 1b `_kernel/context.py`. This class accepts kwarg-only config; defaults come from the parameter defaults below."* Story 1b.1 RETIRES this Phase-1 limitation note — FR41 now wired.

Story 1a.6's `stability-surface.md` "AgentEval Library Surface" subsection has a note about `Get Effective Config` returning "kwarg-resolved values; env-var precedence lands in Epic 1b". Story 1b.1 updates this to "precedence-resolved per FR41 / `_kernel/context.resolve_config` (Story 1b.1)".

### Project norms applied

1. **Norm #1 (cross-LLM adversarial review)** — code-review will use `/bmad-code-review (Using current Claude + Codex CLI subagent)`. Per Epic 1a retro action #4 + `feedback_citation_drift_first_class`, the cross-LLM reviewer prompt MUST explicitly direct: *"For every citation in the changed files — 'per ADR-012', 'per spike findings §`_kernel/context.py` draft', 'architecture L1554 says', 'P2.2 review', etc. — open the cited source and verify the claim is EXACTLY what the source says. Flag any mismatches even if subtle (rename, count drift, slug drift, off-by-one)."* Citation drift was the #1 finding category across Epic 1a.
2. **Norm #2 (machine-verified numeric claims)** — 6 drifts caught + resolved pre-authoring; spike's 18 review patches integrated by reference; line numbers/file paths spot-checked.
3. **Pre-create-story spec-vs-ratified-doc check (Norm #4)** — applied 2026-05-18 with 6 drifts caught (largest non-trivial set since Story 1a.4's 10 + 1a.6's 5). All resolved by honoring ratified sources. `epics.md` Story 1b.1 + `.env.example` updated pre-authoring.
4. **CI-log-forensics (Norm #5)** — post-push verification will include: ci.yml's new dedicated `tests/unit` step exits 0 with real assertions (not just collection); `tests/unit/conventions` continues to exit 5 (accepted); the 6 Story 1a.6 FR42 tests still pass post-Task-10 integration; the RF smoke test still passes; the new kernel unit tests run their assertions in CI.
5. **Honest framing** — Phase-1 limitations documented (atexit-on-SIGKILL unrecoverable; `startup_timeout_s` caller-tracked not enforced; `python-dotenv` deferred to a future story; `--strict` mypy may be Phase-1.5 carry-over).
6. **agentguard inspiration-only** — ratified; no agentguard dependency in `_kernel/context.py`.
7. **NEW NORM applied (citation-drift first-class category)** — see Norm #1 entry above.

### References

- **PRD §FR11b** — `max_runtime_seconds` Tier-3 fan-out guardrail
- **PRD §FR41** — kwarg → env-var → `.env` → defaults precedence (Story 1b.1 wires this)
- **PRD §FR42** — Library defaults (Story 1a.6 wired; Story 1b.1's `resolve_config` returns precedence-resolved values for the same set)
- **PRD §FR63** — Determinism Contract (Story 1b.6 will fully ratify; Story 1b.1 ships the `@tier` decorator that makes it possible)
- **ADR-009** (`docs/adr/ADR-009-per-test-mcp-server-scope.md`) — `mcp_per_test: bool = True` default
- **ADR-012 (was ADR-A1)** (`docs/adr/ADR-012-async-to-sync-bridge-kernel-module.md`) — `_run_async` canonical bridge
- **ADR-015 (was ADR-A5)** (`docs/adr/ADR-015-cost-runtime-guardrail-decorator.md`) — `@guarded_fanout` decorator (Story 1b.3 scope)
- **ADR-016 (was ADR-A6)** — `mcp_coverage` 3-state ratified (relevant to Story 1b.2 coverage.py, NOT Story 1b.1)
- **ADR-018 (was ADR-A8)** — sandbox Phase 1 policy (relevant to Story 1a.1's `security/` stubs already shipped)
- **Architecture L314** — 3-mode `mcp_per_test` user vocab
- **Architecture L620** — `@tier` decorator factory + `_agenteval_tier` attribute (single-underscore)
- **Architecture L932-966** — Async-to-Sync Bridge Convention (ADR-012)
- **Architecture L1198** — `_kernel/context.py` purpose statement
- **Architecture L1502** — Per-test scope (Listener v3 test_id) routing table
- **Architecture L1534-1587** — Listener v3 lifecycle flow
- **Story 0.2 spike findings** `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` §`_kernel/context.py` draft (L273-414) — **LOAD-BEARING source for `_kernel/context.py`**
- **`deferred-work.md` L40-47** — 12+ Story 0.2 review fixes to apply
- **Story 1a.6 `src/AgentEval/__init__.py`** — Library entry point that Story 1b.1's `resolve_config` integrates with
- **Story 1a.6 `docs/contracts/stability-surface.md`** — Phase-1 registry to update (AgentEval Library Surface subsection)
- **Story 1a.6 HIGH-1** — `ci.yml` collect-only sweep fix pattern (`tests/unit` generalization in Task 9)
- **Epic 1a retrospective** `_bmad-output/implementation-artifacts/epic-1a-retro-2026-05-18.md` — action items #1-#4 are Story 1b.1 inputs
- **`feedback_citation_drift_first_class`** (memory) — NEW NORM from Epic 1a retro; applied in Norm #1 above
- **`.env.example`** — canonical env-var names (updated 2026-05-18 with `AGENTEVAL_DEFAULT_TEMPERATURE` + `AGENTEVAL_MAX_RUNTIME_SECONDS` pre-authoring for FR41 completeness)

## Dev Agent Record

### Context Reference

- Story 0.2 spike findings `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` §`_kernel/context.py` draft (L273-414) — LOAD-BEARING source for `MCPLifecycleManager` + dataclasses. 18 review patches (P2.1-P2.18) + D2.4 auto-installed SIGTERM handler integrated.
- `deferred-work.md` L40-47 — 12+ Story 0.2 review fixes (threading.RLock, killpg+pid, EPERM/ESRCH distinction, env minimization, MappingProxyType, atexit-on-SIGKILL unrecoverable, post-kill liveness, dead-and-replaced ReleaseResult emission).
- Architecture L314 / L410 / L1198 / L1502 / L1534-1587 / L1659 / L932-966 / L620 — kernel-module placement + Listener v3 wiring + 3-mode `mcp_per_test` + Async-to-Sync Bridge Convention + `_agenteval_tier` single-underscore convention.
- ADR-009 / ADR-012 / ADR-015 — ratified design decisions consumed by Story 1b.1.
- `.env.example` — canonical `AGENTEVAL_*` env-var names for FR41 resolve_config.

### Agent Model Used

Claude Opus 4.7 (1M context).

### Debug Log References

- `uv run pytest tests/unit --ignore=tests/unit/conventions -q` → 54 passed in 0.50s
- `uv run pytest tests/acceptance/tier1 -q` → 6 passed in 0.29s (Story 1a.6 FR42 regression check post-Task-10 integration; all clean)
- `uv run robot --output NONE --report NONE --log NONE tests/acceptance/smoke` → 1 test PASS (Story 1a.6 RF smoke regression check; clean)
- `uv run ruff check src/ tests/` → All checks passed (after applying auto-fixes for I001 import-sort + UP047 PEP-695 type-param syntax + SIM105 contextlib.suppress)
- `uv run ruff format --check src/ tests/` → 31 files, all formatted
- `uv run mypy src/` → Success: no issues found in 23 source files (up from 20 pre-Story-1b.1: +3 new `_kernel/{context,tier,run_async}.py`)
- `uv run python scripts/check-license-headers.py` → PASS: 23/23 files
- FR41 end-to-end smoke: `AGENTEVAL_PROVIDER=custom-via-env AGENTEVAL_TELEMETRY=false python -c 'AgentEval().get_effective_config()'` returned the env-var-resolved values; `trace_backend` (no env set) correctly fell through to FR42 default `"memory"`.
- `tests/unit/conventions` collect-only path: still exits 5 (placeholder; accepted Phase-1 leniency until Story 1b.6 lands convention enforcement tests).

### Completion Notes List

- **AC-1b.1.1** `Scope` + `_resolve_scope()` translator: implemented as the SINGLE canonical mapping point between user-vocab (`bool | Literal["suite"]`) and internal Scope (`Literal["test", "suite", "process"]`). Truth-table-tested with 5 unit tests.
- **AC-1b.1.2** `TestContext` + ContextVar-backed accessor/lifecycle: implemented with frozen dataclass + `ClassVar[bool] = False` pytest sentinel (silences `cannot collect test class` warning). `set_current_test_id()` convenience wrapper matches architecture L1554 flow. ContextVar thread-isolation verified with a real `threading.Thread` cross-thread assertion.
- **AC-1b.1.3 + AC-1b.1.4** Full `MCPLifecycleManager` + `ServerSpec` (with `MappingProxyType` env per P2.15) + `ServerHandle` + `ReleaseResult` (with `process_lifetime_ms` per P2.2 rename) lifted from spike findings. All 12+ deferred-work items applied: `threading.RLock` (P2.8), spawn outside lock, `pid` directly as pgid (`start_new_session=True`), EPERM/ESRCH distinguished via `PermissionError`/`ProcessLookupError`, dead-and-replaced handles emit `ReleaseResult(signaled_with="already-dead")`, env minimization via `_DEFAULT_ENV_WHITELIST = ("PATH", "HOME", "LANG", "LC_ALL")`, atexit failsafe via `atexit.register(self.shutdown_all)`, auto-installed SIGTERM→`sys.exit(0)` handler per D2.4 LOAD-BEARING finding. Post-kill liveness verification raises `RuntimeError` for D-state survivors.
- **AC-1b.1.5** FR41 `resolve_config()` with 4-layer precedence (kwarg → env → `.env` → defaults). 6 type coercers (`_parse_bool`, `_parse_mcp_per_test`, `_parse_optional_float`, `_coerce_env_value`, etc.). Minimal `.env` parser at `_load_dotenv()` — no `python-dotenv` dependency (Phase-1 minimalism). Invalid coercion raises `ValueError` with the offending key + raw value in the message.
- **AC-1b.1.6** `@tier(N)` decorator + `get_keyword_tier()` + `tier_badge()`. Attribute name is `_agenteval_tier` (single-underscore per architecture L620), NOT `__agenteval_tier__` dunder. Invalid tier raises `ValueError` at both decoration AND badge time. 7 unit tests including explicit dunder-non-existence assertion.
- **AC-1b.1.7** `_run_async[T](coro)` using PEP-695 type-parameter syntax (ruff UP047 auto-fix). `asyncio.get_running_loop()` test triggers `RuntimeError` (no loop) → fast-path `asyncio.run()`; else falls back to worker-thread that owns its own `asyncio.new_event_loop()`. Exception propagation preserved via one-slot capture across thread boundary. 5 unit tests including the explicit nested-loop fallback scenario.
- **AC-1b.1.8** 54 unit tests under `tests/unit/kernel/test_{context, tier, run_async}.py`. All run real assertions (no `--collect-only` leniency).
- **AC-1b.1.9** `ci.yml` restructured: new `pytest tests/unit (real tests)` step runs `uv run pytest tests/unit --ignore=tests/unit/conventions -q` (no `--collect-only`, no exit-5 leniency). The collect-only sweep step narrows to `tests/unit/conventions` only (still placeholder until Story 1b.6).
- **AC-1b.1.10** `AgentEval.__init__` integration via `_UNSET` sentinel pattern. Each kwarg defaults to `_UNSET`; the body collects non-`_UNSET` values into a dict and passes to `resolve_config(kwarg_overrides)`. The 9 `self._<param>` attrs are set from the resolved dict. `self._scope = _resolve_scope(self._mcp_per_test)` for internal MCPLifecycleManager consumers. Story 1a.6's "Phase-1: kwarg-only" docstring + stability-surface entry updated. Story 1a.6's 6 FR42 acceptance tests + RF smoke test continue to PASS post-integration. Added `tests/acceptance/tier1/conftest.py` to clear `AGENTEVAL_*` env-vars + chdir to tmp_path for hermeticity (developers with local env-vars set no longer break the tests).
- **AC-1b.1.11** All gates clean. See Debug Log References.
- **AC-1b.1.12** AC body sets the directive; the cross-LLM review prompt at code-review time will need to include this verbatim. Story 1b.1 dev-story does not run the code review itself.

**Phase-1 limitations explicitly documented (per honest framing norm):**
- atexit-on-SIGKILL is **UNRECOVERABLE** at the listener layer — operator must teardown via systemd cgroup / container-level mitigation. Documented in `context.py` module docstring + `MCPLifecycleManager` class docstring.
- `startup_timeout_s` is caller-tracked, NOT enforced by `acquire()`. The lifecycle manager returns immediately after `subprocess.Popen`; MCP handshake is the caller's responsibility (Epic 3 Story 3.1).
- `python-dotenv` deferred to a future story — the Phase-1 `_load_dotenv()` is a 10-line key=value reader.
- mypy `--strict` not yet enabled (current `mypy src/` is permissive). Phase-1.5 carry-over.

**Self-induced Phase-1 design decision (sentinel `_UNSET`):**
The Story 1a.6 `__init__` signature had type-correct defaults (`provider: str = "litellm"`, etc.). FR41 requires distinguishing "user passed this kwarg" from "kwarg used its default". I introduced a private `_UNSET = object()` sentinel that each kwarg defaults to; the body strips `_UNSET` values before calling `resolve_config`. Type hints remain user-correct; libdoc shows `provider: str` (acceptable). The only behavioral nuance: a caller who EXPLICITLY passes the FR42 default (e.g., `AgentEval(provider="litellm")` when env-var is also set) WILL get "litellm" — that's correct FR41 semantics (kwarg wins over env-var).

## File List

**New files (5):**
- `src/AgentEval/_kernel/context.py` (Scope + _resolve_scope + TestContext + ContextVar + bind/unbind/current/unbind + set_current_test_id + ServerSpec + ServerHandle + ReleaseResult + MCPLifecycleManager + atexit failsafe + auto-installed SIGTERM handler + FR41 resolve_config + _load_dotenv + _parse_env_value, ~530 lines)
- `src/AgentEval/_kernel/tier.py` (@tier decorator + get_keyword_tier + tier_badge, ~85 lines)
- `src/AgentEval/_kernel/run_async.py` (_run_async per ADR-012, PEP-695 type-parameter syntax, ~90 lines)
- `tests/unit/kernel/__init__.py` (package marker)
- `tests/unit/kernel/test_context.py` (43 tests covering AC-1b.1.1 → AC-1b.1.5)
- `tests/unit/kernel/test_tier.py` (7 tests covering AC-1b.1.6)
- `tests/unit/kernel/test_run_async.py` (5 tests covering AC-1b.1.7)
- `tests/acceptance/tier1/conftest.py` (autouse env-isolation fixture for hermeticity of Story 1a.6 FR42 tests post-FR41 wiring)

**Updated files (4):**
- `src/AgentEval/__init__.py` (`_UNSET` sentinel pattern; `__init__` calls `resolve_config(kwarg_dict)` + `_resolve_scope(mcp_per_test)`; docstring updated to reflect FR41 wiring is now live; `self._scope` attribute added)
- `docs/contracts/stability-surface.md` (`AgentEval` class entry: "Epic 1b wires env-var precedence" → "FR41 precedence chain wired by Story 1b.1"; `Get Effective Config` entry: adds Story 1b.1 update note that values are now FR41 precedence-resolved)
- `.github/workflows/ci.yml` (new dedicated `pytest tests/unit (real tests)` step running `pytest tests/unit --ignore=tests/unit/conventions -q`; collect-only sweep narrows to `tests/unit/conventions` only; comments updated to document the 3-real-execute / 1-placeholder current state)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (1b-1 status: ready-for-dev → in-progress → review through this dev-story session)

## Change Log

| Date       | Version | Description                                                                  | Author |
| ---------- | ------- | ---------------------------------------------------------------------------- | ------ |
| 2026-05-18 | 0.1.0   | Initial story creation (ready-for-dev). Pre-create-story drift check (5th consecutive use of `feedback_spec_vs_ratified_doc_precheck`) caught 6 drifts in Story 1b.1 spec vs ratified sources: (1) `mcp_per_test` enum translation undefined; (2) `_kernel/context.py` scope drastically underspecified (epics.md = TestContext+bind/unbind; spike findings = LOAD-BEARING MCPLifecycleManager + 4 dataclasses + atexit + auto-SIGTERM); (3) `tier.py` attribute name dunder vs single-underscore (architecture L620 wins); (4) ADR-A1 citation drift (ratified ADR-012); (5) FR41 wiring assigned to Story 1b.1 explicitly; (6) TestContext kept as lightweight scope-info holder + ContextVar-backed (+ added `_resolve_scope()` translator). All 6 resolved by honoring ratified sources; `epics.md` Story 1b.1 + `.env.example` updated pre-authoring. NEW NORM from Epic 1a retro (`feedback_citation_drift_first_class`) embedded in AC-1b.1.12 + Norm #1 — cross-LLM reviewer prompt MUST direct re-derivation of each cited fact from its source. | Bob |
| 2026-05-18 | 0.2.0   | Dev-story complete. All 11 ACs satisfied; all 11 tasks marked [x]. 3 new `_kernel/` modules (context.py ~530 lines, tier.py ~85 lines, run_async.py ~90 lines) + 55 unit tests (43 context + 7 tier + 5 run_async) + ci.yml restructure (tests/unit now real-execute) + AgentEval.__init__ FR41 integration via `_UNSET` sentinel + tier1 conftest.py for env-isolation + stability-surface.md updates. Story 0.2 spike findings §`_kernel/context.py` draft LIFTED with all 18 review patches (P2.1-P2.18) + D2.4 auto-SIGTERM handler integrated. All gates clean: ruff (after I001 + UP047 + SIM105 auto-fixes), ruff format (31 files), mypy (23 src files), license-headers (23/23), pytest tests/unit (54 passed), pytest tests/acceptance/tier1 (6 passed regression), robot smoke (1 passed regression), FR41 end-to-end smoke (env-var precedence verified). Phase-1 limitations explicitly documented (atexit-on-SIGKILL unrecoverable; startup_timeout_s caller-tracked; python-dotenv deferred; mypy --strict deferred). Status: in-progress → review. | Amelia |
| 2026-05-18 | 1.0.0   | Code-review patches applied (cross-LLM adversarial pair Claude Opus 4.7 + Codex CLI 0.117.0; 4-reviewer parallel: Blind Hunter + Edge Case Hunter + Acceptance Auditor + Codex CLI). 22 unique findings triaged: 1 decision-needed (H5 resolved per Many's pick), 18 patches applied, 2 deferred, 1 dismissed. STAR CATCH: Codex caught H1 (scope modes silently not implemented — acquire always spawned regardless of scope; both `"suite"` and `"process"` behaved as `"test"`); NONE of the 3 Claude reviewers saw this. 7th consecutive cross-LLM review where Codex caught real findings; this time the Claude trio also caught real bugs (H2 clock-mixing, H6 ContextVar non-propagation, H3 None-fallthrough, M4 ADR-filename citation drift) — but the H1 functional gap was Codex-only. All 19 patches applied: H1 scope-aware idempotent acquire (P2.19 lifted from spike) + scope-aware release_test/release_suite no-op semantics; H2 spawned_at_monotonic field + monotonic-only process_lifetime_ms math; H3 resolve_config explicit-None-wins + flip codifying test; H4 main-thread guard for signal.signal install; H5 _UnsetType singleton with stable __repr__; H6 contextvars.copy_context propagation through nested-loop worker thread; H7 ReleaseResult("survived") literal + _drain_handles error-absorption; M1 Popen.wait(timeout=0) reap-first PID-race-safe; M2 close() method (unregister atexit + restore prior SIGTERM); M3 kernel public surface registered as `provisional` in stability-surface.md; M4 ADR-012 + ADR-015 filename drift fixed across run_async.py + architecture.md + spec file; M5 TODO(Story 1b.5) migration comments at each ValueError/RuntimeError site; M6 ServerSpec.__post_init__ shutdown_timeout_s > 0 guard; M7 _load_dotenv strips matching quotes + `export ` prefix; M8 unknown AGENTEVAL_* key UserWarning; M9 O(1) reverse-index via ServerHandle.{test_id,suite_id}; L1 isinstance(n, bool) tier guard; L2 signal.getsignal-based handler test; L3 conftest chdir removed; L4 .env.example documents bool vocabulary; L5 ServerSpec.__post_init__ env re-wrap. 13 new unit tests added (H1×3 + H2 + H6 + H7 + M2 + M6 + M7×2 + M8 + L5 + H4 + H3). Total unit tests: 67 (up from 54). All gates clean: ruff + mypy (23 src) + license (23/23) + pytest unit (67 passed) + tier1 (6 passed) + smoke (1 passed). Status: review → done. | Amelia |

## Senior Developer Review (AI)

**Reviewer:** Many Kasiriha
**Review Date:** 2026-05-18
**Review Outcome:** **APPROVED** (after applying 19 code-review patches from the 4-reviewer parallel cross-LLM pair Claude Opus 4.7 + Codex CLI 0.117.0)

### Summary

Story 1b.1 ships the three foundational `_kernel/` modules (context.py / tier.py / run_async.py) per Story 0.2 spike findings §`_kernel/context.py` draft (LOAD-BEARING) with all 18 spike review patches (P2.1-P2.18) + the P2.19 scope-aware idempotent acquire (added during code-review per Codex's H1 finding) + the D2.4 auto-installed SIGTERM handler integrated. FR41 config precedence is wired via `_kernel.context.resolve_config`; `AgentEval.__init__` integrates via the `_UNSET` sentinel pattern. ci.yml is restructured so `tests/unit` runs real assertions (generalizing the Story 1a.6 HIGH-1 lesson). 67 unit tests + 6 FR42 acceptance tests + 1 RF smoke test all pass.

### Key findings from code-review

**Cross-LLM adversarial pair** (4 reviewers in parallel — Blind Hunter, Edge Case Hunter, Acceptance Auditor running Claude Opus 4.7; Codex CLI 0.117.0 as the cross-family reviewer per `feedback_review_methodology_norms`). 38 raw findings → 22 deduped → 1 decision-needed + 18 patches + 2 deferred + 1 dismissed.

**Star catch — Codex solo (H1):** the `MCPLifecycleManager` scope modes were NOT actually implemented. `acquire()` unconditionally spawned a new `Popen` regardless of `scope`; both `"suite"` and `"process"` behaved identically to `"test"`. The dev-story had "lifted the spike's API surface" but silently dropped the P2.19 idempotency contract that distinguishes the 3 scope modes. None of the 3 Claude reviewers (same model family) caught this. 7th consecutive cross-LLM review where Codex caught real findings; the same-family blind spot pattern continues to be structurally load-bearing per the project norm.

**3-way confirmed HIGH findings** (caught by 3+ reviewers independently):
- **H2 clock-mixing** in `process_lifetime_ms`: `time.monotonic() - time.time()` yielded -1.7e12 magnitude garbage on every release.
- **H3 FR41 `None`-fallthrough**: `resolve_config` stripped explicit `None` kwargs, contradicting the `__init__` docstring + AC-1b.1.5 invariant. A test codified the wrong behavior.

**2-way confirmed HIGH findings:**
- **H4** SIGTERM install from non-main-thread crashes with `ValueError`.
- **H5** `_UNSET` sentinel rendered as `<object object at 0x7f...>` in libdoc (non-reproducible builds) + lied to mypy strict.
- **H7** D-state survivor `RuntimeError` raised inside list-comp in `shutdown_all` abandoned remaining handles mid-loop.

**Solo HIGH catch (Edge Case Hunter): H6** `_run_async` worker thread did NOT inherit caller `ContextVar` via `copy_context` — the architecture's per-test `test_id` propagation contract was silently broken in IDE-runner / nested-loop scenarios (the whole keyword surface affected).

**Citation-drift catches (per the new `feedback_citation_drift_first_class` norm):**
- **M4** ADR-012 actual filename is `ADR-012-async-to-sync-bridge-kernel-module.md` (not `ADR-012-async-bridge-kernel.md`); ADR-015 actual filename is `ADR-015-cost-runtime-guardrail-decorator.md` (not `ADR-015-guarded-fanout-decorator.md`). Fixed across `_kernel/run_async.py`, `architecture.md`, and the story spec.

### Acceptance Criteria Coverage (post-patches)

All 12 AC-1b.1.X satisfied:

- **AC-1b.1.1** `Scope` + `_resolve_scope()` translator + registered as `provisional` in `stability-surface.md` (M3 patch added the registry entry).
- **AC-1b.1.2** `TestContext` + `current_context()` / `bind_context()` / `unbind_context()` / `set_current_test_id()` — verified by 7 unit tests including cross-thread isolation.
- **AC-1b.1.3** `MCPLifecycleManager` + 4 dataclasses with H1 scope-aware idempotent acquire per spike P2.19 + scope-aware release_test/release_suite no-op semantics.
- **AC-1b.1.4** All 12+ Story 0.2 deferred-work items applied; atexit + D2.4 auto-installed SIGTERM handler integrated; M2 `close()` method added for caller-controlled disposal; H4 main-thread guard.
- **AC-1b.1.5** FR41 `resolve_config` with explicit-None-wins precedence (H3 fix) + M8 unknown-key warning + M7 quoted-value/export-prefix handling + TODO(Story 1b.5) migration comments at each ValueError site (M5).
- **AC-1b.1.6** `@tier(N)` with `_agenteval_tier` single-underscore attr + L1 bool guard via `isinstance(n, bool)`.
- **AC-1b.1.7** `_run_async` per ADR-012 with H6 `contextvars.copy_context()` propagation through worker thread; M4 ADR filename corrected.
- **AC-1b.1.8** 67 unit tests (54 original + 13 review-patch tests); L2 SIGTERM handler test uses `signal.getsignal()` per spec.
- **AC-1b.1.9** ci.yml restructured: dedicated `pytest tests/unit (real tests)` step; collect-only sweep narrowed to `tests/unit/conventions`.
- **AC-1b.1.10** AgentEval.__init__ integration via H5 `_UnsetType` singleton; FR41 + `_resolve_scope` threaded through; 6 Story 1a.6 FR42 tests + RF smoke test still pass; tier1 conftest hardened per L3 (no chdir) + entry/exit symmetry.
- **AC-1b.1.11** All gates clean (see Debug Log References).
- **AC-1b.1.12** Cross-LLM reviewer prompt embedded the citation-drift re-derivation directive; Codex caught M4 ADR filenames + H1 scope-modes-not-implemented as direct results.

### Test Coverage

**Local:** `pytest tests/unit --ignore=tests/unit/conventions -q` → **67 passed in 0.43s**. `pytest tests/acceptance/tier1 -q` → **6 passed in 0.30s**. `robot tests/acceptance/smoke` → **1 passed**. CI verification pending push.

### Action Items

None. All 19 patches applied; gates clean; cross-LLM-reviewer pair caught + resolved all findings.

### Outcome

**Status: review → done.** Epic 1b 1/6 stories complete. Ready for Story 1b.2 (`/bmad-create-story` next).
