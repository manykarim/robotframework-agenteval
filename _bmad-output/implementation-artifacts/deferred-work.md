# Deferred Work

Carry-overs from code reviews and other workflows. Bullets here did not block merge but should be picked up by the named downstream story or epic.

## Deferred from: code review of 0-1-run-hosted-mcp-universal-observer-spike (2026-05-17)

The 20 items below are real defects in the Story 0.1 spike's scratch Python code. They do **not** block the spike's verdict (`AMEND-ADR-007`) because the spike's deliverable is the findings document, not production code. They DO block the production observer that Epic 5 Story 5.2 will build.

### Carry-overs to Epic 5 Story 5.2 (`src/AgentEval/mcp/observer.py`)

- `attach()` idempotency: double-attach must not double-count tool calls; raise or no-op on re-attach to the same server.
- SDK exception swallowing: production observer must inspect `ServerResult.isError` to distinguish tool failures from successes (the SDK absorbs tool exceptions into `_make_error_result`; the observer's `try/except` around `await handler(req)` is dead for normal tool errors).
- Encapsulation: no external code may mutate `_seq` / `_traces` / private state. All trace ingestion goes through a single `_record()` method. The spike's `_graft_subprocess_log` pattern (free-function reaching into observer internals) must NOT survive into production.
- `mark_external_mixed` must accumulate reasons: `list[str]`, not single overwrite. Declare the field in `__init__`, not as an ad-hoc instance attribute.
- `_summarize_result` must handle multi-block / non-text-first / `ImageContent`+`TextContent` mixed results — not just `blocks[0].text`.
- Arguments serialization: validate JSON-serializability at capture time, not defer to `write_jsonl`; consider Pydantic models for the trace shape.
- Trace immutability: deep-copy args at record time, OR document that callers must not mutate args after a tool call.
- `mcp_coverage` decision logic + `observed_paths` ordering: implementation must mirror the ratified ADR-A6 semantic (whichever D1 resolves to); `observed_paths` should reflect decision order, not alphabetical.
- `finalize()` terminal-state guard: subsequent `finalize()` calls return the same `run_id` + frozen trace snapshot, OR raise.
- Subprocess-side observation: production `subprocess_with_observer` path must inject the observer at subprocess bootstrap (the actual handler-wrap pattern), NOT rely on cooperating servers that log to JSONL. See D2 in story review findings.
- Performance: subprocess-side `_append_log` should batch writes (e.g., write at handler exit, not per-call open/close) for high-frequency tool runs.
- Locking: document single-producer-per-observer assumption OR add anyio.Lock for the `_seq` increment if multi-concurrent-clients can hit the same observer.

### Carry-overs to Epic 3 Story 3.1 (`src/AgentEval/mcp/transport.py`) — load-bearing

- **`stdio_client(params, errlog=<real file>)`** — production code must never pass `sys.stderr` as `errlog` when the host process may be under RF capture. RF replaces `sys.stderr` with a non-fd capture buffer that breaks `subprocess.Popen._get_handles` → `stderr.fileno()`. Surface this as a `mcp/transport.py` constraint AND document in `docs/contracts/listener-integration.md` (Story 1a.4 skeleton).
- `OBSERVER_LOG_PATH` should be namespaced as `AGENTEVAL_OBSERVER_LOG_PATH` (or similar) and validated (must be writable file path; reject directories).
- Subprocess teardown verification — ensure subprocesses are reaped even when `asyncio.run` cancels mid-call. Story 0.2 covers the cleanup-under-pabot scope but transport.py needs to expose the contract.

### Carry-overs to Story 0.2 (per-test MCP cleanup spike)

- `start_new_session=True` (mcp SDK default for stdio_client) — verify this gives clean kill semantics under `pabot --processes 8`. Story 0.1 cited this as a fact in support of its verdict but only validated `--processes 4`.

### Carry-overs to Story 0.3 (BLOCKER — D5 review decision; extends to BOTH Story 0.1 + Story 0.2)

- **Story 0.3 is BLOCKED until independent reproduction of BOTH Epic 0 spikes lands.** Both findings documents were produced autonomously by Claude Opus 4.7 (Story 0.1: ~3h cumulative including review+rework; Story 0.2: ~2h single session). Ratifying the ADR amendments without independent reproduction risks committing the architecture to LLM-only-validated decisions. Unblock criteria documented in the Story 0.3 file itself (now 8 criteria spanning both spikes).
- macOS validation pending for BOTH spikes (Phase-1 carry-over per Story 9.x); does not block Story 0.3 but should be filed as a follow-up.
- Real rf-mcp clone testing for Story 0.2 (substitute used; see `_bmad-output/spikes/0-2-pabot-mcp-cleanup/servers/rf_mcp_pin.txt`).

### Carry-overs to Epic 1b Story 1b.1 (`_kernel/context.py` — from Story 0.2 spike + code review)

- Lift the `MCPLifecycleManager` API surface from `_bmad-output/spikes/0-2-pabot-mcp-cleanup/context_prototype.py` per the docstrings in Story 0.2 findings doc §`_kernel/context.py` draft.
- Production version must add: real liveness check (currently spike only spawns subprocess + tracks `Popen.poll()`; production should do a minimal MCP handshake to confirm the server actually came up before declaring the handle alive); typed error hierarchy (raise `MCPSpawnFailedError` from `ServerSpec.startup_timeout_s` expiry instead of generic timeouts); structured logging hook (the spike writes raw JSONL; production should emit OTel spans for spawn + release events).
- Listener-v3 wiring at `src/AgentEval/telemetry/otel_listener.py` should call the lifecycle manager; the spike's `mcp_listener.py` is the reference but should NOT survive into production (it lives in spike scratch by design).
- atexit failsafe registration should move to `_kernel/context.py.__init__` like the spike — verified load-bearing for defense-in-depth (except SIGKILL — see below).
- **From Story 0.2 code review:** Use `threading.RLock` instead of `Lock` (atexit reentry safety). Spawn outside the lock (Popen-under-lock serializes all acquires + child inherits parent's atexit). Drop `os.getpgid(pid)` — use `pid` directly as pgid since `start_new_session=True`. Distinguish `EPERM` from `ESRCH` in `_kill` (currently both silently swallowed; EPERM falsely reports SIGKILL success). Post-kill liveness verification before recording success (D-state survivors). Always record release events for state transitions (currently dead-and-replaced handles drop silently). Minimize child env (`os.environ.copy()` leaks credentials to third-party servers). Use `MappingProxyType` for `ServerSpec.env` (frozen=True doesn't freeze dict). Implement `startup_timeout_s` or remove from API (currently dead field carried into production). Split `shutdown_latency_ms` into `terminate_to_signal_delivered_ms` + `signal_to_reaped_ms`. Rename `startup_latency_ms` → `process_lifetime_ms` (current field measures lifetime, not startup).
- **From Story 0.2 code review — atexit-on-SIGKILL gap:** Python `atexit` handlers do NOT run on SIGKILL. The verdict's defense-in-depth claim for SIGKILL-of-worker is structurally unrecoverable at the listener layer. Production needs either (a) a parent-side reaper (separate supervisor process tracking pabot worker children + their MCP grandchildren), (b) systemd cgroup / container-level teardown documented as operator responsibility, or (c) explicit acknowledgement that SIGKILL-of-worker leaks are unrecoverable + operators handle externally. **Phase-1 carry-over: design + document the SIGKILL-of-worker mitigation strategy.**

### Carry-overs to Story 0.3 (BLOCKER — D5 review decision; extends to BOTH Story 0.1 + Story 0.2 + Story 0.2 review findings)

- **Story 0.3 is BLOCKED until independent reproduction of BOTH Epic 0 spikes lands.** Both findings documents were produced autonomously by Claude Opus 4.7.
- **Story 0.2 code review surfaced 4 decisions that MUST be resolved before Story 0.3 ratifies** (architect call on each):
  1. macOS gap — literal AC-0.2.1 + AC-0.2.2 violation; needs explicit waiver OR macOS reproduction.
  2. atexit-on-SIGKILL technical correctness — verdict claim factually wrong for SIGKILL; needs verdict text fix + design decision on real mitigation strategy.
  3. `slow_server` SIGTERM-race semantics — spike validates pre-handshake SIGTERM, not in-handshake SIGTERM; either re-run with real handshake probe OR downgrade claim.
  4. atexit failsafe never exercised in `measurements/` — load-bearing but no recorded evidence; add probe OR explicit gap acknowledgement.
- All 4 decisions documented in `0-2-run-per-test-mcp-cleanup-under-pabot-spike.md` Review Findings section.
- macOS validation pending for BOTH spikes (Phase-1 carry-over per Story 9.x); now elevated by D2.1 to potential blocker.
- Real rf-mcp clone testing for Story 0.2 (substitute used; see `_bmad-output/spikes/0-2-pabot-mcp-cleanup/servers/rf_mcp_pin.txt`).

### Carry-overs to Epic 5 Story 5.2 + Epic 6 (`AdapterVersionDriftWarning`)

- The handler-wrap pattern uses `Server.request_handlers` (technically internal in mcp SDK) and `FastMCP._mcp_server` (private). An `AdapterVersionDriftWarning` MUST be wired to detect mcp SDK major-version bumps that could break this coupling.
- Test the pattern against multiple mcp versions in CI (e.g., a version matrix in `.github/workflows/test.yml` covering mcp 1.10, 1.20, 1.27, latest).
- File an upstream issue with `mcp` SDK requesting a stable observer hook on `FastMCP` so we can drop the private-attribute access.

### General hygiene carry-overs (not story-specific)

- Test-ID defaults consistency in any RF library: pick one default, not two.
- `os.getpid()` is not unique enough for long-running pabot suites (Linux PID recycling). Production worker identification should use UUID or pabot's own `PABOTQUEUEINDEX` RF variable read via `BuiltIn`.

---

## Deferred from: code review of 1b-1-foundational-kernel-context-tier-async-bridge (2026-05-18)

- **D1 — `tier(N)` decorator on built-ins / C-extension callables.** Setting `func._agenteval_tier = n` raises `AttributeError` on Python built-in functions, certain partials, and C-extension callables. Pre-existing language constraint, not caused by Story 1b.1. Story 1b.6 convention enforcer (which asserts every `@keyword`-decorated method has a `@tier()` annotation) is the natural place to surface this — fails loudly at library-import time if a sub-library author tries to `@tier` an unsupported callable. Decision deferred to Story 1b.6.
- **D2 — `_FakePopen._next_pid` shared class-level state across tests.** The test-fixture Popen stand-in (`tests/unit/kernel/test_context.py`) uses a class-level counter that monotonically increases across the whole pytest session. No current test asserts a specific PID range, so no bug today. Revisit if any future test grows a PID-specific assertion or if test ordering becomes load-bearing. Phase-2 hygiene.

---

## Deferred from: code review of 1b-2-trace-observability-kernel-trace-store-redaction-coverage (2026-05-18)

- **L_R3 — `redact_dict` doesn't redact dict KEYS, only values** [src/AgentEval/_kernel/redaction.py] — credentials are typically values not keys; Phase-1 scope decision. Module docstring documents the asymmetry. Phase-1.5 hygiene revisit if a real key-credential leak pattern emerges.
- **L_R4 — `IncompleteTraceError` message references `docs/contracts/mcp-coverage-detection.md` which is currently a Story 1a.4 skeleton** — substantive trust-floor decision-tree + per-adapter detection contract lands in Epic 4 Story 4.2 (Claude Code CLI adapter). Acceptable: the message points consumers to the right place when content fills.
- **L_R9 — `_resolve_test_id` raises `ValueError` when called from a raw `threading.Thread` (NOT via `_run_async`'s `copy_context()` wrapper)** [src/AgentEval/_kernel/trace_store.py] — Story 1b.6 convention enforcer will catch sub-libraries spawning raw threads (architecture mandates `_run_async` per Story 1b.1). No code change in Story 1b.2.
- **Pre-flag for Story 1b.4 / `completeness` enum drift** — PRD FR36a defines `completeness: Literal["complete", "truncated", "partial"]` (prd.md L1553) but Story 1b.4 epics.md L963 uses `Literal["full", "partial", "incomplete"]`. NOT in Story 1b.2's diff; Story 1b.4 create-story drift check will hit this. Bonus catch from Edge Case Hunter during 1b.2 review.

---

## Deferred from: code review of story-1b.3-discovery-guardrails-kernel-entry-points-fan-out-decorator (2026-05-19)

- **DF1 AdapterDiscoveryError taxonomy collision (unknown-name vs broken-import use same `error_code`)** — Codex caught: a typo lookup ("`claude-codd`") and a partially-installed adapter raise the same typed error; consumers cannot distinguish without string-matching. Introduce `UnknownAdapterError(AdapterDiscoveryError)` sub-leaf in a follow-up story OR pass `reason: Literal["unknown_name", "broken_import"]` on the existing error.
- **DF2 `CodingAgentAdapter` forward-ref breaks `typing.get_type_hints()`** — Blind Hunter caught: `TYPE_CHECKING`-only import means `get_type_hints(discover_adapters)` raises `NameError` at runtime. Story 1b.4 lands the Protocol and resolves; no action needed before then. If tooling that calls `get_type_hints` (sphinx, pydantic) bites earlier, add a runtime `CodingAgentAdapter = Any` shim.
- **DF3 `test_partial_install_detection_raises_with_diagnostic` ADR-013 substring assertion fragility** — Blind Hunter caught: `assert "ADR-013" in str(exc_info.value)` would break only on ADR renumbering; brittle but tolerable. Future test-hardening story can switch to structural assertion against the exception's diagnostic-hint attribute.
- **DF4 FR17b `register_provider` / `register_sandbox` absence** — Blind Hunter caught: only adapters have a programmatic-registration path; providers + sandboxes are entry-points-only. Documented as by-design (PRD FR17b is adapter-specific). Add module docstring note in Story 1b.5 or earlier follow-up so future contributors don't ask.
- **DF5 Layer 2 + Layer 3 simultaneous breach precedence (cost-wins by code order)** — Edge Case Hunter caught: when both meters detect a breach on the same poll, the cost-check fires first and returns; runtime breach is silently dropped. Acceptable precedence (cost is typically the harder budget); add a docstring note clarifying the deterministic cost-wins-on-tie semantics.

---

*Update this file as new deferred items emerge from future reviews.*
