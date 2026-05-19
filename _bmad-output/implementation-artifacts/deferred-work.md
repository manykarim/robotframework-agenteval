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

## Deferred from: code review of story-1b.4-codingagentadapter-protocol-inprocessadapter-subprocessadapter-abcs (2026-05-19)

- **DF1 Async-safety of `_assert_binary_version`** — Edge Case Hunter caught: calls blocking `subprocess.run` synchronously; OK in Phase-1 because Story 1b.4 invokes this only at adapter init-time, but async-runtime callers from Story 4.1+ (LiteLLM streaming) blocking on it could stall the event loop. Wrap in `asyncio.to_thread` or provide an `_assert_binary_version_async` variant when concrete async adapters land.
- **DF2 `_default_version` namespace-package edge case** — Blind Hunter caught: `type(self).__module__.split('.')[0]` heuristic doesn't handle namespace packages or in-tree-adapter modules whose top-level differs from the installed distribution. Story 1b.4 ships `packages_distributions()` resolution as the D5 fix, but namespace-package edge cases still need explicit subclass overrides. Concrete adapters in Epic 4/11 SHOULD override `version` explicitly rather than rely on the default heuristic.
- **DF3 Real-Popen integration test for SubprocessAdapter** — Blind Hunter caught: tests use `MagicMock(spec=subprocess.Popen)` which exercises the contract shape but not the real-`Popen` blocking-IO, `BlockingIOError`, partial-line buffering, or stdout-close semantics. Story 1b.5 conformance harness will own integration-style fixtures with real `python -c "..."` subprocesses.
- **DF4 Long-stdout / unbounded-events memory test** — Edge Case Hunter caught: `events: list[ParsedEvent]` accumulator is unbounded; very long event streams could OOM. Phase-1.5 robustness pass; Story 4.2 (Claude Code CLI adapter, first real consumer) will be the first place this gets exercised in anger.
- **DF5 Cancellation-mid-stream test** — Blind Hunter caught: no test verifies that a kernel-driven cooperative cancellation (`current_cancel_event().set()`) interrupts `for line in proc.stdout` iteration. Story 4.1 wires real provider-client cancellation; Story 1b.4 ships only the cleanup-on-exception path. Add the integration test alongside Story 4.1's cancellation wiring.
- **DF6 Test factory-fixture refactor** — Blind Hunter caught: `ToolCallTrace(...)` constructor is repeated across 25+ tests in `test_base.py`; if Story 1b.2's dataclass adds a required field, all tests break. Add `tests/unit/coding_agent/conftest.py` with `tool_call_trace_factory` + `usage_factory` + `agent_run_metadata_factory` fixtures during the Story 1b.5 conformance fixture work — that story builds the shared fixture infrastructure anyway.
- **DF7 architecture.md L1226-1228 split-file scheme annotation** — Acceptance Auditor caught: architecture L1228 wording reads "`subprocess.py # SubprocessAdapter ABC ...`" but Story 1b.4 consolidates everything in `coding_agent/base.py` per the D8 ratification. Architecture file needs an annotation that the split-file scheme is Phase-2-or-later. Add to Epic 1b retrospective doc-cleanup batch.
- **DF8 architecture L1230 + ADR-003 L30 base-class lifecycle ownership Phase-2 carry-over** — Codex STAR catch: ADR-003 L30 ratifies "signal handling, timeout enforcement, stderr capture, exit-code mapping, truncation detection" as base-class responsibilities. Story 1b.4 D1+D2 patches deliver process-group SIGTERM + escalation but explicitly defer stderr capture + timeout enforcement + truncation detection to Phase-2. ADR-003 L30 amended pre-Story-1b.4-code-review-patches to reflect this Phase-1-minimum + Phase-2-deliverable split.

---

## Deferred from: code review of story-1b.5-conformance-harness-loader-fixture-schema-6-reference-fixtures (2026-05-19)

- **DF-1b.5-S1 `_schema_version` regex rejects pre-release semver** — Codex F11 + Blind#11: fixture-schema's `_schema_version` regex `^[0-9]+\.[0-9]+\.[0-9]+$` rejects valid pre-release semver like `2.0.0-rc1`. Phase-2 schema migrations may want to ship preview tags. Widen the regex to full semver per semver.org BNF when Phase-2 OTLP serialization story lands.
- **DF-1b.5-S2 Pydantic-migration consolidated tracker** — Story 1b.5 Acceptance Auditor F2 catch: types.py docstrings claim a Phase-1.5 Pydantic migration is tracked here. The trigger condition is "When Epic 5's OTLP serialization needs validation". Affected dataclasses across stories: `ToolCallTrace` + `Usage` + `RunManifest` (Story 1b.2 types.py L46-56); `AgentRunResult` + `AgentRunMetadata` (Story 1b.4 types.py); `ConformanceFixture` + `ConformanceResult` (Story 1b.5 tests/conformance/types.py). When the migration ships, all 7 dataclasses migrate together to preserve consistent validation semantics.
- **DF-1b.5-S3 `run_fixture` tristate clarity (passed/skipped/failed)** — Blind#8: pre-edit `ConformanceResult.passed=False+skip_reason="..."` overloads pass-vs-skip in a single boolean. Refactor to explicit `status: Literal["passed", "failed", "skipped"]` field OR raise `pytest.skip.Exception` directly from `run_fixture` when Story 4.1/4.2 wire concrete-adapter assertions. Phase-1 stub's all-skip behavior is consistent enough that the refactor isn't blocking.
- **DF-1b.5-S4 Defensive deep-copy in `ConformanceFixture` / `ConformanceResult` `__post_init__`** — Blind#9: `frozen=True` only prevents rebinding; inner dict/list contents are still mutable. Apply Story 1b.2 M_R6 pattern (`__post_init__` with `dict(...)` shallow copy or `copy.deepcopy` per the M_R11 decision matrix) when concrete adapters land + start using these dataclasses in production assertion paths.
- **DF-1b.5-S5 Per-AC skeleton tests parametrized over `adapter_registry`** — Codex F7: spec says each skeleton is "parametrized over `adapter_registry`" but shipped skeletons skip unconditionally without the parameter. Add `adapter_registry: list[type]` parameter to each of the 10 per-AC test files (preserving current SKIP semantics) when concrete adapters land in Epic 4. Acceptable Phase-1 simplification: the SKIP fires before parametrize matters.
- **DF-1b.5-S6 `test_structural_shape.py` wider scope per ADR-017 L36-43** — Codex F6 + Auditor F10: pre-edit only calls `assert_adapter_signature`. ADR-017 L36-43 also mandates `AgentRunResult` / `ToolCallTrace` / `AgentRunMetadata` schema assertions. Add nested-field schema assertions in Story 4.1/4.2 when the first concrete adapter lands; expand the per-adapter parametrize at that time.
- **DF-1b.5-S7 `truncation_injection_harness` + `mock_provider` deferred build wiring** — Blind#7: pre-edit Phase-1 stubs raise `NotImplementedError` on `.build()`. The fixtures consume the dict-shaped builders; current tests don't exercise the `build()` callable. Wire real subprocess control (`kill_at` mid-stream) when Epic 4 Story 4.2 (Claude Code CLI) lands + Epic 6 Story 6.x (Tier-3 cost-guardrail keywords). Until then the harness keys are documentation-only.
- **DF-1b.5-S8 `library_version` synthetic-placeholder regeneration** — Codex F9 + Blind#19: Phase-1 fixtures use `library_version: "0.0.1"` matching `pyproject.toml`. When `pyproject.toml` bumps to a new version, fixtures need regeneration. Add a CI check (or fixture-template generation) when Story 4.1 + 4.2 ship real recorded runs.

---

*Update this file as new deferred items emerge from future reviews.*
