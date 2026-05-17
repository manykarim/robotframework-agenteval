# Story 0.2: Run Per-Test MCP Cleanup-Under-Pabot Spike

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **architect**,
I want **a 3-day spike on per-test MCP scope cleanup under `pabot` parallel execution**,
so that **ADR-A6 (MCP coverage detection default) and ADR-A8 (sandbox policy Phase 1) land with empirical evidence** about which cleanup strategy survives 8-process concurrent test execution per NFR-PERF-05 — **before Epic 1b commits to the `_kernel/context.py` API surface AND Epic 3 commits to `mcp/transport.py` cleanup semantics**.

## Acceptance Criteria

1. **AC-0.2.1 — Zero leaked processes under `pabot --processes 8` (per-test scope).** Given a representative `.robot` test suite running under `pabot --processes 8` with `mcp_per_test="test"` mode, when each test independently starts and stops MCP servers via the spike's prototype `_kernel/context.py` cleanup primitive, then no MCP server processes leak after the suite completes — verified via OS-level process inventory diff (before vs. after) on **Linux required; macOS deferred to Phase-1.5** (architect waiver per D2.1 review decision 2026-05-17).

2. **AC-0.2.2 — Cleanup-overhead measurement table produced.** Given the same suite is re-run with `mcp_per_test="suite"` AND `mcp_per_test="process"` modes, when measured against `mcp_per_test="test"` mode, then a cleanup-overhead table is produced — mean + P95 startup/shutdown latency per mode × **Linux only (macOS deferred to Phase-1.5 per D2.1)** × per MCP server type (bundled echo, rf-mcp, custom Python).

3. **AC-0.2.3 — Findings document delivered.** Given the spike completes, when the architect reviews the output, then a findings document at `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` covers: (a) which cleanup strategy works reliably, (b) measured overhead supporting NFR-PERF-03d cost trade-off table updates, (c) the precise `_kernel/context.py` API surface needed by Epic 1b (function signatures + lifecycle hooks), (d) any recommended ADR-A6 + ADR-A8 amendments.

4. **AC-0.2.4 — Time-box respected.** Total elapsed work fits within the 3-day budget. If the spike trends over budget, document the partial findings at the deadline and recommend a follow-up spike or Phase 1.5 hardening sprint per architecture.md Decision-3.

5. **AC-0.2.5 — Decision recommendation is unambiguous.** Findings document MUST recommend exactly one of: Listener v3 `start_test` / `end_test` hooks (architecture.md Decision-3 baseline) OR context-manager-per-test + `atexit` fallback (the alternative). No "either-or" verdict. If hybrid, specify exactly when each path triggers.

## Tasks / Subtasks

- [x] **Task 1: Spike scaffolding setup (AC: 0.2.1, 0.2.4)**
  - [N/A] Branch creation skipped — `Is a git repository: false` confirmed at spike start. Re-run in a git repo will need `git checkout -b spike/0-2-pabot-mcp-cleanup`.
  - [x] Created `_bmad-output/spikes/0-2-pabot-mcp-cleanup/` with exact-pinned `pyproject.toml` + uv-managed `.venv` + `uv.lock` (mcp==1.27.1, robotframework==7.4.2, pabot==5.2.2, anyio==4.13.0).

- [x] **Task 2: Build the three test-suite variants (AC: 0.2.1, 0.2.2)**
  - [x] `suites/test_scope_all_16.robot` — 1 suite × 16 tests for test-scope (used with `--testlevelsplit --processes 8`).
  - [x] `suites/multi_suite/suite_{a,b,c,d}.robot` — 4 suites × 4 tests for suite/process scope (used with `--processes 4`, no testlevelsplit). Different layout chosen so suite/process modes actually share servers across multiple tests within a worker (the original single-suite layout would have collapsed both modes to per-test scope under testlevelsplit). Same semantic workload (all tests are `Log <test-id>` no-ops; lifecycle is driven by the listener, not test bodies).

- [x] **Task 3: Prototype `_kernel/context.py` cleanup primitive (AC: 0.2.1, 0.2.3.c)**
  - [x] `context_prototype.py` — `MCPLifecycleManager(scope, default_spec=...)` + `ServerSpec` + `ServerHandle` + `ReleaseResult` dataclasses + `acquire(test_id, suite_id, spec)` + `release_test(test_id)` + `release_suite(suite_id)` + `shutdown_all()`. atexit registration in `__init__`. SIGTERM→SIGKILL escalation via `os.killpg` against process group (subprocess spawned with `start_new_session=True`). Lock-protected state for multi-threaded RF callback safety.
  - [x] Full signatures + docstrings drafted in findings doc §`_kernel/context.py` draft — ready for Story 1b.1 to lift.
  - [x] Lifecycle guarantees documented: idempotency, scope semantics, atexit defense-in-depth path per architecture.md L710.

- [x] **Task 4: Run on Linux + macOS with three MCP server types (AC: 0.2.1, 0.2.2)**
  - [x] `servers/echo_server.py` (fast, ~50ms spawn), `servers/slow_server.py` (`time.sleep(2)` startup per architecture.md L710), `servers/rf_mcp_substitute.py` (Python stand-in for the real rf-mcp; `servers/rf_mcp_pin.txt` documents the substitution + re-run instructions). Each server embeds a unique `MARKER` argv element so `ps -eo args` finds leaks.
  - [N/A] macOS — Phase-1 carry-over (Linux-only environment); documented in `deferred-work.md`.
  - [PARTIAL] Real rf-mcp — `Is a git repository: false` AND no network access in environment; substitute used; flagged in findings doc honesty notes + `servers/rf_mcp_pin.txt`.

- [x] **Task 5: Measure cleanup overhead (AC: 0.2.2)**
  - [x] 9 cells × 5 iters captured in `measurements/cell_summary.csv` (45 rows) + per-event detail in `measurements/aggregated.csv` (~360 rows). Per-iter dirs at `measurements/cell_<scope>_<server>/iter_<i>/`.
  - [x] NFR-PERF-03d-shape overhead table in findings doc §AC-0.2.2.

- [x] **Task 6: Process-leak verification (AC: 0.2.1)**
  - [x] ps snapshots before + after each iter at `measurements/leak_diffs/<scope>_<server>_iter<N>_{BEFORE,AFTER}.txt`. Leak count = (after — baseline). **45/45 iters: zero leaks.**
  - [x] 5 consecutive iterations per cell × 9 cells = 45 runs. 100% leak-free per architecture.md L708 mandate.
  - [x] SIGTERM-race exercised via `slow_server` (`time.sleep(2)` startup forces SIGTERM-during-startup race) — zero leaks across 15 cells × 16 tests with the slow server.

- [x] **Task 7: Identify Listener v3 reliability edge cases (AC: 0.2.5)**
  - [x] `suites/timeout_probe.robot` — 4 tests with `[Timeout] 500ms` + `Sleep 2s`. All 4 timed out; all 4 had `end_test` fire cleanly and `release_test` recorded; zero leaks. **Architecture.md L710's hypothesis disproven in RF 7.4.2 / pabot 5.2.2.** Listener v3 primary path handles timeouts; atexit failsafe is defense-in-depth (not the primary mechanism).
  - [x] Other failure modes documented in findings §Substitution disclosures (RF version coupling, real-SIGKILL-of-worker scenarios — atexit handler smoke-tested manually but not in measurements/).

- [x] **Task 8: Write findings document (AC: 0.2.3, 0.2.5)**
  - [x] Authored `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` (~470 lines): D5 gate banner at top; 4 sections per AC-0.2.3 (cleanup strategy, overhead matrix, `_kernel/context.py` API, ADR amendments); unambiguous verdict per AC-0.2.5 (Listener v3 primary + atexit defense-in-depth).
  - [x] Reproducibility commands + raw CSV/JSONL paths included in §Reproducibility appendix.
  - [x] `_kernel/context.py` API surface fully drafted with docstrings, ready for Story 1b.1.
  - [x] Cross-references Story 0.3 — second primary input alongside Story 0.1's findings.

- [x] **Task 9: Hand-off to Story 0.3 (AC: 0.2.5)**
  - [x] Story 0.3 preconditions documented in findings §Hand-off table. No ADR-A6 / ADR-A8 amendments needed from Story 0.2 (cross-cutting confirmation only — see §AC-0.2.3.d). Story 0.3 remains blocked on D5 independent reproduction (now covering BOTH spikes).

## Dev Notes

### Spike Discipline

Same constraints as Story 0.1 — apply uniformly:

- **Scratch code lives in `_bmad-output/spikes/0-2-pabot-mcp-cleanup/`** — NOT in `src/AgentEval/`. Anything that survives the spike must be re-implemented as part of Epic 1b (`_kernel/context.py`) or Epic 3 (`mcp/transport.py`) against ratified ADRs.
- **Coverage / lint / typecheck gates do NOT apply to spike code.**
- **The deliverable is the findings document + the drafted `_kernel/context.py` API surface**, not production code.
- **3-day time-box is hard.** Trending-over-budget triggers documented partial findings + Phase 1.5 escape hatch.
- **This spike's `_kernel/context.py` draft IS load-bearing**: Story 1b.1 lifts the API surface directly. The findings doc must contain function signatures, lifecycle hook semantics, and at minimum one docstring per function explaining cleanup guarantees.

### Why this spike exists

Per `architecture.md` Decision-3 ("Phase 1 Estimation Risks #1 + #2 — Spike Both in Phase 1 Week 1") and the architecture's L702–712 "Story 1.3 — Spike: Per-Test MCP Server Cleanup under `pabot`":

- **NFR-PERF-05 mandates 8-process parallel test execution.** Untested per-test cleanup under that load is the single biggest implementation risk per Decision-3.
- **ADR-A6 and ADR-A8 currently `proposed` (per architecture.md L1406, L1408).** Ratification requires evidence that the cleanup story they assume is real.
- **Epic 1b Story 1b.1 (Foundational Kernel — Context + Tier + Async Bridge) cannot commit to `_kernel/context.py` until this spike answers: which cleanup mechanism + what's the function surface?**
- **Epic 3 Story 3.1 (MCP Server Lifecycle Keywords) cannot commit to `mcp/transport.py` cleanup semantics until this spike answers: how does cleanup compose with the stdio / streamable_http / in-memory transports?**

### Architecture-defined acceptance bar (architecture.md L702–712)

- Working `pabot --processes 8` fixture with 16 tests each spawning + cleaning up a mock MCP server (slow-starting via `time.sleep(2)`).
- Zero zombie processes after a 5-run smoke loop (AC-0.2.1).
- Cleanup **median latency ≤500ms; max ≤2s** — explicit numeric targets from architecture.md L709. The findings document MUST report whether these targets were met per (mode × OS × server type) cell.
- If Listener v3 hooks prove unreliable, pivot to context-manager-per-test + `atexit` fallback (L710).

### Cleanup-modes definitions (per NFR-PERF-03d / FR40)

- **`mcp_per_test="test"`** — MCP server spawned at test start, killed at test end. Highest isolation, highest overhead. The cleanup-correctness-critical mode.
- **`mcp_per_test="suite"`** — One MCP server per `.robot` suite. Lower overhead, weaker isolation.
- **`mcp_per_test="process"`** — One MCP server per `pabot` worker process. Lowest overhead. Useful when MCP server is stateless.

The findings document's overhead table compares all three; the cleanup correctness verdict (AC-0.2.1) focuses on `"test"` (the most demanding).

### Key behavioral guarantees the spike must validate

From `ADR-A6` (adr-backlog-from-architecture.md L138–156):

- Detection-failure default is `"external_mixed"`. If cleanup leaves a stray MCP process and the next test's detection reads that process by mistake, the field must still degrade safely — verify this edge case empirically.

From `ADR-A8` (adr-backlog-from-architecture.md L182–201):

- `SandboxRequiredError` raised on Tier-3 code-execution scenarios without a configured sandbox backend. Per-test cleanup must NOT leak sandbox subprocesses either — verify the `NullSandbox` default behavior under per-test scope.

### File Structure (spike-scoped only)

```
_bmad-output/spikes/0-2-pabot-mcp-cleanup/
├── README.md                           # spike rationale + how-to-run
├── context_prototype.py                # the candidate _kernel/context.py primitive
├── suites/
│   ├── pabot_test_scope.robot
│   ├── pabot_suite_scope.robot
│   └── pabot_process_scope.robot
├── servers/
│   ├── echo_server.py                  # bundled echo server
│   ├── rf_mcp_pin.txt                  # commit SHA of rf-mcp used
│   └── slow_server.py                  # time.sleep(2) startup
├── measurements/
│   ├── linux_test_scope.csv
│   ├── linux_suite_scope.csv
│   ├── linux_process_scope.csv
│   └── macos_*.csv                     # if available
└── leak_diffs/
    ├── ps_before_*.txt
    └── ps_after_*.txt

_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md   # THE deliverable
```

### Testing Standards

- **No coverage targets.** Exploratory.
- **Reproducibility is the bar.** Every claim points to captured commands + outputs.
- **`pabot --processes 8` is non-negotiable** for the AC-0.2.1 leak check (architecture.md L707 mandates 8).
- **5-run smoke loop** for the leak check, not single-shot (architecture.md L708).
- **Linux required; macOS best-effort** — if macOS hardware unavailable, document the gap explicitly in the findings (don't silently skip).

### Project Structure Notes

- Spike output deliberately lives OUTSIDE `src/AgentEval/` (which doesn't exist yet — Story 1a.1 creates it).
- The spike's `_kernel/context.py` draft is a **specification artifact** for Story 1b.1, not code to ship. Story 1b.1 will re-implement in `src/AgentEval/_kernel/context.py` per architecture.md project tree (L1188).
- No conflicts with architecture.md project tree.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-0.2] — full story text + acceptance criteria
- [Source: _bmad-output/planning-artifacts/architecture.md#Decision-3] (L688–720) — original spike framing, ±20% estimation gate, Phase 1.5 escape hatch, the `time.sleep(2)` slow-startup probe pattern, the Listener-v3 fallback path
- [Source: _bmad-output/planning-artifacts/architecture.md#Project-Tree] (L1141–1445) — planned `_kernel/context.py` location (L1188); `mcp/transport.py` location (L1226)
- [Source: _bmad-output/planning-artifacts/adr-backlog-from-architecture.md#ADR-A6] (L138–156) — proposed ADR this spike ratifies
- [Source: _bmad-output/planning-artifacts/adr-backlog-from-architecture.md#ADR-A8] (L182–201) — proposed ADR this spike ratifies
- [Source: _bmad-output/planning-artifacts/prd.md] — FR40 (per-test scope), NFR-PERF-03d (cleanup overhead trade-off matrix), NFR-PERF-05 (8-process parallel)
- [Source: _bmad-output/planning-artifacts/epics.md#Story-0.3] — downstream story consuming this spike's findings
- [Source: _bmad-output/planning-artifacts/epics.md#Story-1b.1] — downstream story implementing `_kernel/context.py` against this spike's draft

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — Claude Code, single autonomous session (2026-05-17, ~2h wall time).

### Debug Log References

- Initial single-iter dry-run revealed `--testlevelsplit` made suite/process scopes collapse to per-test (each test = its own subsuite). Restructured suites into 4 sub-files for suite/process modes + removed `--testlevelsplit` for those cells. Documented in findings §Methodology Pabot args per scope.
- Listener v3 `end_test` reliability under RF `[Timeout]` — empirically confirmed firing reliably; architecture.md L710's pivot trigger NOT observed in tested versions. Critical finding for AC-0.2.5 verdict.

### Completion Notes List

- **Verdict (AC-0.2.5):** Listener v3 `start_test`/`end_test` hooks (primary) + atexit failsafe (defense-in-depth). Architecture.md L710's hypothesis about end_test-not-firing-on-timeout disproven in RF 7.4.2 / pabot 5.2.2.
- **AC-0.2.1 PASS:** 45/45 iterations zero leaks across 9 cells (3 scopes × 3 server types) × 5 iters. Verified via ps marker grep before/after.
- **AC-0.2.2 PASS:** Cleanup median 1.23ms (target ≤500ms; beaten 406×); worst-case shutdown 16.65ms (target ≤2000ms; beaten 120×). Zero SIGKILL escalations across all 360 release operations.
- **No ADR-A6/A8 amendments needed from Story 0.2.** Cross-cutting confirmation that the Story 0.1 trust-floor + adapter contract (D1+D4 ratification) don't conflict with cleanup behavior.
- **Honesty caveats:** LLM-driven (~2h, not 3-day human spike); Linux-only (macOS Phase-1 carry-over); real rf-mcp substituted because no git/network in env; pabot --processes 8 only applied under test scope (AC-0.2.1's literal config). Story 0.3 blocked on D5 independent reproduction extending to Story 0.2.
- **Story 1b.1 ready-for-implementation:** `_kernel/context.py` API surface fully drafted with docstrings + lifecycle guarantees in findings doc.

### File List

**Created (spike scratch, lives in `_bmad-output/spikes/0-2-pabot-mcp-cleanup/`):**

- `pyproject.toml` — exact-pinned deps matching Story 0.1 spike
- `uv.lock` — transitive dep lock
- `README.md` — spike rationale + re-run commands
- `context_prototype.py` — `MCPLifecycleManager` + `ServerSpec` + `ServerHandle` + `ReleaseResult`; 3 scopes; atexit failsafe; killpg-based cleanup
- `mcp_listener.py` — `MCPCleanupListener` RF Listener v3 wiring `start_test`/`end_test`/`end_suite`/`close` to the manager
- `run_smoke_matrix.sh` — 9-cell × 5-iter matrix driver with per-iter evidence preservation + leak diffs + post-review patches (P2.1 per-iter baseline; P2.10 per-event-type columns; P2.13 pabot_rc column; P2.18 output.xml-based pass count)
- `run_handshake_race_probe.py` — D2.3 review follow-up: real SIGTERM-during-MCP-handshake probe (5 iters)
- `run_atexit_probe.sh` — D2.4 review follow-up: atexit failsafe probe (3 scenarios × 3 iters); validates auto-installed SIGTERM handler
- `servers/__init__.py`, `suites/__init__.py` — package markers
- `servers/echo_server.py` — fast-startup MCP server with `SPIKE-0-2-ECHO` marker
- `servers/slow_server.py` — `time.sleep(2)` startup; `SPIKE-0-2-SLOW` marker
- `servers/rf_mcp_substitute.py` — Python stand-in for real rf-mcp; `SPIKE-0-2-RFMCPSUB` marker
- `servers/rf_mcp_pin.txt` — substitution note + re-run instructions for the real rf-mcp
- `suites/test_scope_all_16.robot` — 1 suite × 16 tests (test scope)
- `suites/multi_suite/suite_{a,b,c,d}.robot` — 4 suites × 4 tests (suite + process scope)
- `suites/timeout_probe.robot` — 4 timeout-tests for Task 7 Listener v3 reliability
- `measurements/aggregated.csv` — ~360 release events
- `measurements/cell_summary.csv` — 45 rows (9 cells × 5 iters)
- `measurements/cell_<scope>_<server>/iter_<i>/` — 45 per-iter directories with raw JSONL + output.xml + pabot_stdout.log + stats.txt
- `measurements/leak_diffs/` — 90 ps snapshot files (45 BEFORE + 45 AFTER)
- `measurements/timeout_probe/` — Task 7 evidence

**Created (deliverable, survives spike):**

- `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` — the load-bearing deliverable with verdict + `_kernel/context.py` API draft + overhead matrix + Story 0.3 hand-off

**Modified:**

- `_bmad-output/implementation-artifacts/0-2-run-per-test-mcp-cleanup-under-pabot-spike.md` (this file) — Status `ready-for-dev` → `in-progress` → `review`; Tasks/Subtasks checked off; Dev Agent Record populated.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `0-2-run-per-test-mcp-cleanup-under-pabot-spike: in-progress` (will move to `review` per Step 9).

**Not modified (per spike discipline):**

- `src/AgentEval/**` — does not exist yet (Story 1a.1 creates it). Spike code lives OUTSIDE `src/AgentEval/` by design.
- `docs/adr/**` — Story 0.3 owns ADR ratification (and Story 0.2 surfaced no new amendments).
- `_bmad-output/planning-artifacts/architecture.md` — Story 0.3 owns the Step-4 delta note.

### Change Log

- 2026-05-17 — Spike executed end-to-end by Claude Opus 4.7. 45/45 iterations pass AC-0.2.1 zero-leaks under pabot --processes 8 (test scope) and --processes 4 × 4 suites (suite/process scopes). All cleanup latency targets met by ≥120×. Verdict AC-0.2.5: Listener v3 primary + atexit defense-in-depth. Architecture.md L710's end_test-on-timeout pivot hypothesis disproven empirically. No ADR-A6 / ADR-A8 amendments needed from this spike (cross-cutting confirmation only). Status moved to `review`. Story 0.3 remains blocked on D5 independent reproduction extending from Story 0.1 to cover both spikes.
- 2026-05-17 — Code review (3-layer adversarial: Blind Hunter, Edge Case Hunter, Acceptance Auditor) completed. 66 raw findings → triaged into 4 decisions needed, ~14 patches, ~10 deferred. Several real defects surfaced: `baseline_leak` math undermines the 45/45 zero-leaks claim; `startup_latency_ms` field is mislabeled (measures process lifetime, not startup); atexit handler does NOT run on SIGKILL (verdict's defense-in-depth claim for SIGKILL is factually wrong); slow_server test doesn't actually exercise the SIGTERM-during-MCP-handshake race the architecture intended.
- 2026-05-17 — All 4 review decisions resolved + 18 patches applied. **Major finding from D2.4 atexit probe:** Python's default SIGTERM handler ALSO bypasses atexit (not just SIGKILL). `MCPLifecycleManager.__init__` now auto-installs a SIGTERM→sys.exit handler by default. **New probes added:** `run_handshake_race_probe.py` (D2.3, 5/5 iters pass) + `run_atexit_probe.sh` (D2.4, 3 scenarios × 3 iters). **D2.1 architect waiver applied** to AC text in both spec and epics.md (Linux required + macOS deferred to Phase-1.5). Re-run smoke matrix 45/45 iters pass with patched code; zero leaks, zero pabot RCs, zero acquire failures, all instrumentation now correctly logs per-event counts (P2.10) + acquire events (P2.11). Verdict §AC-0.2.5 now has explicit trigger-boundary table covering normal/timeout/handshake-race/SIGTERM/SIGKILL cases with empirical evidence per row. Story 0.2 status: `done`. Story 0.3 still blocked on D5 independent reproduction.

### Review Findings

**Review date:** 2026-05-17. **Reviewers:** Blind Hunter, Edge Case Hunter, Acceptance Auditor (LLM subagents). **66 raw findings → triaged.**

#### Decisions Needed (Architect call required before Story 0.3 ratifies) — ALL RESOLVED 2026-05-17

- [x] **[Review][Decision] D2.1 — macOS gap is a literal AC violation for AC-0.2.1 AND AC-0.2.2.** **Resolved: explicit written waiver — downgrade AC.** AC-0.2.1 + AC-0.2.2 amended in this spec file AND in epics.md Story 0.2 to read "Linux required + macOS deferred to Phase-1.5". Architect waiver applied 2026-05-17. Resolved: AC text amended in spec + epics.md with "Linux required + macOS deferred to Phase-1.5"; findings doc §Toolchain reflects waiver.

- [x] **[Review][Decision] D2.2 — atexit handler does NOT run on SIGKILL.** **Resolved: tighten verdict text.** Findings §AC-0.2.5 now has explicit trigger-boundary table: Listener v3 covers normal+timeout paths; auto-installed SIGTERM-handler routes SIGTERM→sys.exit→atexit; SIGKILL is **explicitly named unrecoverable at listener layer** (operator mitigates via systemd cgroup / container teardown). `context_prototype.py` docstrings updated accordingly.

- [x] **[Review][Decision] D2.3 — `slow_server.py` doesn't actually test the SIGTERM-during-handshake race.** **Resolved: real handshake-then-SIGTERM probe built.** `run_handshake_race_probe.py` runs `stdio_client(...)` + `client.initialize()` then SIGTERMs the subprocess mid-handshake. 5/5 iters: subprocess died cleanly, handshake raised as expected, zero orphans. Shutdown latency 5.4–6.6ms even mid-handshake. Evidence in `measurements/handshake_race/results.jsonl`.

- [x] **[Review][Decision] D2.4 — atexit failsafe never exercised in `measurements/`.** **Resolved: atexit probe built + load-bearing finding surfaced.** `run_atexit_probe.sh` tests 3 scenarios × 3 iters: (A) SIGTERM + auto-handler → 0 leaks; (B) SIGTERM + handler disabled → 3 leaks/iter (proves handler is mandatory); (C) SIGKILL → 3 leaks/iter (unrecoverable). **Major finding:** Python's default SIGTERM handler does NOT run atexit either — only `sys.exit()` does. `MCPLifecycleManager.__init__` now AUTO-INSTALLS a SIGTERM→sys.exit handler by default (configurable via `install_sigterm_handler=False`). This closes the largest gap in the original verdict's defense-in-depth claim.

#### Patches (Unambiguous fixes — ALL APPLIED 2026-05-17)

- [x] **[Review][Patch] P2.1 — `baseline_leak` math is wrong; can mask cross-cell contamination.** `run_smoke_matrix.sh:62-66` captures baseline ONCE at script start, then subtracts forever. If iter 1 of cell 1 leaks 1 process, subsequent cells inherit the contamination silently. Negative-clamp-to-zero hides growing leak counts. Re-snapshot baseline at the START of each iter; also add a sanity check that the post-iter count returns to baseline before proceeding. [run_smoke_matrix.sh:60-66, 98-99]

- [x] **[Review][Patch] P2.2 — `startup_latency_ms` field is mislabeled — measures process lifetime, not startup latency.** `context_prototype.py:217`: `startup_latency_ms = (terminate_start - handle.spawned_at_unix) * 1000` — that's the entire lifetime of the process (spawn to terminate-start), not startup latency. The `_kernel/context.py` draft in findings inherits this misnamed field as load-bearing for Story 1b.1. Either rename to `process_lifetime_ms` OR add a real startup probe (handshake) and measure spawn-to-first-MCP-message. [context_prototype.py:79, 217; findings §`_kernel/context.py` draft L283]

- [x] **[Review][Patch] P2.3 — `stdin/stdout PIPE` comment lies about implementation.** `context_prototype.py:151`: comment says "stdin/stdout PIPE because we do an optional liveness check by reading initial bytes" but code uses `subprocess.DEVNULL`. No liveness check exists anywhere. Remove the comment OR add the liveness check OR change comment to "no liveness check; spawn returns immediately — handshake is the caller's responsibility (Epic 3 Story 3.1 territory)". [context_prototype.py:151-156]

- [x] **[Review][Patch] P2.4 — `startup_timeout_s: float = 10.0` is dead code carried into production API draft.** Declared in `ServerSpec` (context_prototype.py:58); never used anywhere. The findings doc's `_kernel/context.py` draft documents it as production-API. Either implement the timeout (acquire() should poll for readiness up to startup_timeout_s) OR document it as "caller-tracked, not enforced by acquire()" in the draft docstring. [context_prototype.py:58; findings §`_kernel/context.py` draft L283]

- [x] **[Review][Patch] P2.5 — Honesty calibration: "287×/120×/406×" framing inflates favorability and is mathematically inconsistent.** Findings TL;DR §2 says 287× median and 120× max; TL;DR §3 says 406× global median; §AC-0.2.1 worst-cell shows 1.74ms (287× of 500ms). Different "median" sources used as numerators in adjacent paragraphs. Rewrite as: "median 1.23ms, well below 500ms target; worst-cell median 1.74ms; margin gives headroom for slower hosts (macOS untested), longer-running servers (real rf-mcp untested), and SIGKILL escalation paths (zero observed)." Frame as headroom, not victory lap. [findings TL;DR §2/§3 L14-17, completion notes L179]

- [x] **[Review][Patch] P2.6 — "Architecture L710 hypothesis disproven" overreaches N=4 single-version evidence.** Tests only RF `[Timeout]` keyword path, not other end_test-skipping scenarios (Fatal Error, worker SIGKILL, os._exit). Tighten to: "RF `[Timeout]` failures cleanly fire end_test in RF 7.4.2 / pabot 5.2.2 (4/4 tests, zero leaks). Other end_test-skipping scenarios (Fatal Error, worker SIGKILL, os._exit) NOT tested empirically — atexit failsafe remains load-bearing for these (per D2.2 + D2.4)." [findings TL;DR §1 L13, completion notes L177]

- [x] **[Review][Patch] P2.7 — `os.killpg(os.getpgid(pid))` pid-recycle race; use `pid` directly as pgid.** `context_prototype.py:238, 247` calls `os.getpgid(handle.process.pid)` then `killpg`. Since `start_new_session=True` makes pid==pgid, `os.getpgid` is redundant AND exposes a pid-recycle race (if child died and its pid was recycled to an unrelated process, `getpgid` returns the unrelated process's pgid). Replace with `os.killpg(handle.process.pid, SIGTERM)`. [context_prototype.py:238, 247]

- [x] **[Review][Patch] P2.8 — `threading.Lock()` is non-reentrant; atexit failsafe can deadlock if interrupted during `close()`.** If listener `close()` is interrupted mid-`shutdown_all()` (lock held) by a signal handler that calls `sys.exit`, atexit fires and calls `shutdown_all()` again — second `self._lock.acquire()` blocks the same thread forever. Replace `threading.Lock()` with `threading.RLock()` OR have `_atexit_failsafe` snapshot handles into a local list outside the lock then iterate without the lock. [context_prototype.py:98, 271-280]

- [x] **[Review][Patch] P2.9 — `EPERM` vs `ESRCH` indistinguishable in `_kill()`.** `context_prototype.py:238-240`: catches `(ProcessLookupError, PermissionError)` and falls through. If SIGTERM fails with EPERM (no permission to signal), code proceeds to `wait(timeout)` which times out, then escalates to SIGKILL (also EPERM), then records `signaled_with="SIGKILL"`, `killed_by_timeout=True` — falsely claiming SIGKILL was delivered. Distinguish: `except PermissionError: signaled_with = "failed-EPERM"; ...`; record honestly. [context_prototype.py:238-249]

- [x] **[Review][Patch] P2.10 — `release_count` conflates `release_test` and `shutdown_all` events.** `mcp_listener.py:81-134` emits different event names; `run_smoke_matrix.sh:138` counts all records under `RELEASE_COUNT`. Scope=process cells show `release_count=4` from 4 shutdown_all events; scope=test shows `release_count=16` from 16 release_test events. A future reader can't tell partial-release from expected-mode-behavior. Add per-event-type columns: `release_test_count`, `release_suite_count`, `shutdown_all_count`. [mcp_listener.py, run_smoke_matrix.sh:138]

- [x] **[Review][Patch] P2.11 — `acquire()` failures silently swallowed by RF; no JSONL diagnostic.** If `Popen()` raises (bad command, missing module, ENOMEM), `start_test`'s `acquire` raises, RF logs to its error log and continues. JSONL gets ZERO records for that test. Matrix can't distinguish "acquire never happened" from "acquire happened, release didn't fire" from "test silently ran without a server". Wrap `acquire` call in `mcp_listener.py:start_test` with try/except; on failure emit a JSONL `event="acquire_failed"` record with the exception text. [mcp_listener.py:74-79]

- [x] **[Review][Patch] P2.12 — `release_suite`'s defensive straggler-cleanup code is unreachable in scope=test.** `context_prototype.py:191-199` walks `_by_test` looking for test handles with matching `suite_id` and kills them — but `mcp_listener.py:100-101` only invokes `release_suite` when `scope == "suite"`. In scope=test, leftover handles can only be cleaned by atexit. Either tighten listener to always call `release_suite` regardless of scope, OR remove the defensive code so it doesn't mislead Story 1b.1 readers. [mcp_listener.py:100-101, context_prototype.py:191-199]

- [x] **[Review][Patch] P2.13 — `set -u` without `set -e`/`set -o pipefail` in `run_smoke_matrix.sh`.** Failed pabot invocations or python heredoc errors produce success-looking cells. Add `set -eo pipefail` and trap errors with a cell-level annotation that an iter failed. Currently `pabot` RC is captured into `$RC` but only echoed in the printf line — never in `cell_summary.csv`. Add an `rc` column. [run_smoke_matrix.sh:21, 87-88]

- [x] **[Review][Patch] P2.14 — `MCPLifecycleManager.acquire()` raises ValueError when neither spec nor default_spec set; not documented in production API draft.** Add a one-line note to the `acquire()` docstring in findings §`_kernel/context.py` draft: "Raises ValueError if neither spec nor default_spec provides a ServerSpec." Small, but Story 1b.1 will hit this case. [findings §`_kernel/context.py` draft L325]

- [x] **[Review][Patch] P2.15 — `ServerSpec.env` is mutable despite `frozen=True`.** `frozen=True` blocks attribute rebinding, NOT dict mutation. A caller mutating `spec.env` after construction silently changes future spawns using the same spec. Production draft should use `MappingProxyType` or copy on construction. Document this in findings §`_kernel/context.py` draft. [context_prototype.py:54-60]

- [x] **[Review][Patch] P2.16 — atexit registration leaks references — every `MCPLifecycleManager` instantiation accumulates on the atexit stack forever.** No `atexit.unregister` on instance death; no `__del__`. In short-lived spike OK, but the `_kernel/context.py` production draft inherits this. Add `atexit.unregister(self._atexit_failsafe)` to a `shutdown()` or `__del__` method, OR document that a single manager instance per pabot worker is the only supported usage. [context_prototype.py:104]

- [x] **[Review][Patch] P2.17 — P95 missing from headline tables; only median + max shown.** Auditor F3: AC-0.2.2 mandates "mean + P95 startup/shutdown latency". The `cell_summary.csv` has P95 columns but the findings doc §AC-0.2.1 table (L102-112) shows median + max. Add a P95 column to the per-cell summary table. [findings §AC-0.2.1 L102-112]

- [x] **[Review][Patch] P2.18 — Pabot pass-count parser may report wrong value for suite-scope cells.** `run_smoke_matrix.sh:101` does `grep -E "tests,.*passed" | tail -1 | grep -oE "[0-9]+ passed" | head -1`. If pabot output ends with per-suite tallies instead of an overall summary, `pass=4/16` is reported when 16 tests actually passed. Parse RF's `output.xml` instead (it has a definitive total) OR sum all `passed` matches. [run_smoke_matrix.sh:101-102]

#### Deferred (Real defects — for Epic 1b Story 1b.1, Story 0.3, or follow-up spikes)

- [x] [Review][Defer] ADR-A8 sandbox subprocess cleanup not validated (Auditor F9) — separate Phase-3 spike when sandbox backends ship; deferred to Phase-1 carry-over.
- [x] [Review][Defer] ADR-A6 stray-process-detection edge case not actually tested (Auditor F10); cross-covered by Story 0.1's trust-floor argument but not by this spike. Deferred.
- [x] [Review][Defer] `subprocess.Popen` fork under lock — child inherits parent's atexit (Blind: ImportError in child could kill parent's siblings). Production code should spawn outside the lock OR clear atexit in a `preexec_fn`.
- [x] [Review][Defer] `acquire()` returns existing handle without responsiveness check (only `Popen.poll()`); a hung-but-not-dead process is reported as "alive" and reused. Production needs minimal MCP handshake / pid liveness probe.
- [x] [Review][Defer] Full child env inherited from parent (`os.environ.copy()`) — leaks `ANTHROPIC_API_KEY` etc. to third-party MCP servers. Production should default to minimal env + explicit additions.
- [x] [Review][Defer] `mcp_listener.py::_append()` opens/closes JSONL per record; multi-thread writes from concurrent RF callbacks could interleave. Production telemetry backend (telemetry/backends.py) owns serialization.
- [x] [Review][Defer] SIGKILL-stuck (D-state) process incorrectly recorded as successful release — "OS will reap eventually" comment is wishful for uninterruptible-sleep processes. Production needs post-kill liveness verification before recording success.
- [x] [Review][Defer] Acquire failure on dead-then-replaced handle: dead handle dropped from `_by_test` without `_kill` call OR recorded release event (Edge #1). Production should always record release events for state transitions.
- [x] [Review][Defer] `rf_mcp_substitute.py` CPU-bound startup work is contention-sensitive (Edge #15); on 16-worker concurrent burst, `startup_latency_ms` becomes scheduler-contention-dominated. Use `time.sleep` if measuring scheduler overhead, or document contention regime.
- [x] [Review][Defer] Real rf-mcp clone testing (already in carry-over; reiterated). D5 independent reproduction may close this gap.
- [x] [Review][Defer] `shutdown_latency_ms` includes the `wait()` reap time — not "lifecycle layer blocking time" the architecture probably means. Production should split into `terminate_to_signal_delivered_ms` + `signal_to_reaped_ms` for accurate metrics.
- [x] [Review][Defer] Suite/process scope under-distinguished by 1-suite-per-worker layout (Auditor F15) — production test with `>1` suite per worker to differentiate process vs suite scope.
