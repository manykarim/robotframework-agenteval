# Story 0.1: Run Hosted-MCP Universal Observer Spike

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an **architect** (representing all Phase 1 stakeholders),
I want **a 5-day spike on the hosted-MCP universal observer pattern**,
so that **ADR-007 (hosted-MCP universal trace observation) lands with empirical evidence** about which trace-observation backend pattern survives MCP server diversity (stdio + streamable_http + in-memory) and Listener v3 per-test scope concurrency — **before Epic 5 commits to a `mcp/observer.py` API surface**.

## Acceptance Criteria

1. **AC-0.1.1 — Dual-transport coverage.** Given an MCP server hosted in-process (via the in-memory transport) AND a second MCP server launched as a subprocess (via stdio transport), when the spike's observer implementation captures tool-call traces from both during a single `.robot` suite execution, then the observer produces a coherent `mcp_coverage` field per `AgentRunResult` reflecting which observation path provided the data — exactly one of `"hosted_in_process"`, `"subprocess_with_observer"`, or `"external_mixed"`.

2. **AC-0.1.2 — Findings document delivered.** Given the spike completes, when the architect reviews the output, then a written findings document lands at `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` covering: (a) which transports the observer pattern supports, (b) edge cases where coverage degrades to `"external_mixed"`, (c) recommended ADR-007 amendments, (d) any breaking changes to the planned `mcp/observer.py` API surface that affect Epic 5 story planning.

3. **AC-0.1.3 — Concurrency answer with evidence.** The findings document explicitly answers: "does the observer survive a hosted MCP server with concurrent Listener v3 per-test scope under `pabot --processes 4`?" with reproducible evidence (commands + captured output).

4. **AC-0.1.4 — Time-box respected.** Total elapsed work fits within the 5-day budget (one engineer × 5 days). If the spike trends over budget, document the partial findings at the deadline and recommend either a follow-up spike or a Phase 1.5 hardening sprint per architecture.md Decision-3 ("Phase 1 slip beyond +50% buffer").

5. **AC-0.1.5 — Decision recommendation is unambiguous.** Findings document MUST recommend exactly one of: `KEEP-CURRENT-ADR-007` (no amendment needed), `AMEND-ADR-007` (specific text deltas listed), or `REPLACE-ADR-007` (new ADR proposed). No "TBD" / "needs further investigation" verdicts — the point of a spike is to convert uncertainty to a decision.

## Tasks / Subtasks

- [x] **Task 1: Spike scaffolding setup (AC: 0.1.1, 0.1.4)**
  - [x] Created scratch directory `_bmad-output/spikes/0-1-hosted-mcp-observer/` with `pyproject.toml` + uv-managed `.venv` (Python 3.12.3, `mcp==1.27.1`, `robotframework==7.4.2`, `robotframework-pabot==5.2.2`). Branch step skipped — repo is not git-initialized yet (Story 1a.1 owns repo init).
  - [N/A] Branch creation skipped — `Is a git repository: false` confirmed at spike start. Re-run in a git repo will need `git checkout -b spike/0-1-hosted-mcp-observer`.

- [x] **Task 2: Build two-transport probe (AC: 0.1.1)**
  - [x] In-memory MCP server in `transports/in_memory_server.py` using `mcp.server.lowlevel.Server` + `mcp.shared.memory.create_connected_server_and_client_session`.
  - [x] Stdio subprocess MCP server in `transports/stdio_subprocess_server.py` spawned via `mcp.client.stdio.stdio_client`.
  - [x] Observer in `observer_prototype.py` — load-bearing API decision: `Server.request_handlers[CallToolRequest]` runtime dict-mutation pattern (NOT middleware, NOT subclass). See findings §Observation-hook decision.

- [x] **Task 3: Produce `mcp_coverage` field per run (AC: 0.1.1)**
  - [x] `AgentRunResult` dataclass in `observer_prototype.py` with `mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]`.
  - [x] Single dual-transport probe emits one result per run; field populated by weakest-coverage rule (documented in findings §`mcp_coverage` field semantic finding).

- [x] **Task 4: Stress under `pabot --processes 4` (AC: 0.1.3)**
  - [x] `.robot` suite with 8 tests (`concurrency/test_pabot.robot`), each calls `Run Hosted MCP Probe` + assertions. `ROBOT_LIBRARY_SCOPE = "TEST"` simulates per-test scope.
  - [x] Ran under `pabot --testlevelsplit --processes 4` × 5 smoke iterations on Linux. **macOS not tested — gap documented in findings §Toolchain.**
  - [x] Evidence captured: 40/40 runs pass, 32 tool calls captured per iteration (160 total), 0 drops/duplicates/leakage. Wall time mean 11.83s.
  - [x] Raw outputs saved: `concurrency/pabot_evidence/*.jsonl`, `measurements/smoke_loop.txt`, one `output.xml` saved as representative artifact.

- [x] **Task 5: Identify `mcp_coverage="external_mixed"` degradation cases (AC: 0.1.2.b)**
  - [x] 4 edge-case probes in `edge_cases/external_mixed_cases.py`: no-attach baseline, external-blind agent, subprocess-dies-midtest, all-attached-baseline.
  - [x] All 4 probes pass; critical secondary finding: adapter cooperation is mandatory for `external_mixed` detection (observer alone cannot detect external MCP usage). See findings §Edge cases probed.

- [x] **Task 6: Write findings document (AC: 0.1.2, 0.1.5)**
  - [x] Authored `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` covering: (a) transports supported [§Transport coverage]; (b) external_mixed degradation cases [§Edge cases]; (c) ADR-007 amendment text drafted inline [§Verdict]; (d) Epic 5 Story 5.2 API surface + effort estimate within ±20% gate [§Estimated effort delta].
  - [x] Reproducibility commands + raw output paths included [§Reproducibility appendix].
  - [x] mcp 1.27.1 + handler-wrap pattern cited.
  - [x] AC-0.1.3 concurrency answer: yes, observer survives `pabot --processes 4` per-test scope (40/40 runs over 5 smoke iterations).
  - [x] AC-0.1.5 unambiguous verdict: `AMEND-ADR-007` (renumbers to ADR-004).

- [x] **Task 7: Hand-off to Story 0.3 (AC: 0.1.5)**
  - [x] Story 0.3 preconditions documented in findings §Hand-off: file exists, verdict = AMEND, amendment text drafted inline for both ADR-007 (primary) AND ADR-A6 (co-finding surfaced by spike).
  - [N/A] No `REPLACE-ADR-007` verdict, so no ADR-001 divergence note required from this spike.

## Dev Notes

### Spike Discipline

This is a **research spike**, not a feature implementation. Specific constraints:

- **Scratch code lives in `_bmad-output/spikes/0-1-hosted-mcp-observer/`** — NOT in `src/AgentEval/`. Anything that survives the spike must be re-implemented as part of Epic 5 against ratified ADR-007 / ADR-A6.
- **Coverage / lint / typecheck gates do NOT apply to spike code.** Tests are exploratory probes, not pytest-style guarantees. CI workflows from Epic 1a do not block this story.
- **The deliverable is the findings document + decision recommendation**, not production code. Treat code as evidence-generating instrumentation.
- **5-day time-box is hard.** Per architecture.md Decision-3 (L688–720), a spike trending over budget triggers documented partial findings + Phase 1.5 hardening sprint — NOT silent scope creep.

### Why this spike exists

Per `architecture.md` Decision-3 ("Phase 1 Estimation Risks #1 + #2 — Spike Both in Phase 1 Week 1"), three downstream choices depend on the observer pattern's empirical behavior:

1. **`mcp/observer.py` API surface** (Epic 5 Story 5.2) — Cannot commit to a function signature until we know whether the `mcp` SDK gives us a clean middleware/interceptor API OR forces us into a custom subclass.
2. **ADR-007's "decision" section** — Currently `proposed` (per architecture.md L1394); ratification requires empirical evidence.
3. **`mcp_coverage` field semantics** (ADR-A6) — The three-state value space (`"hosted_in_process"` / `"subprocess_with_observer"` / `"external_mixed"`) is only honest if the spike confirms the observer can actually distinguish these states reliably.

### Key behavioral guarantees the spike must validate

From `architecture.md` Decision-3 acceptance criteria (L692–701):

- Working prototype of the chosen observation approach against the bundled echo MCP server fixture.
- API surface documented: middleware hook OR custom subclass + which methods overridden.
- Estimated effort for full Epic 5 implementation within ±20% (i.e., "we can plan around this number").

From `ADR-007` (adr-backlog-from-prd.md L61–74):

- Server-side recording of every `tools/call` is the universal trace fallback; the spike must produce this property empirically, not just by reading SDK docs.
- Agents connecting to MCP servers the library did NOT spawn must degrade to `mcp_coverage="external_mixed"` (interaction with ADR-A6 — adr-backlog-from-architecture.md L138–156).

From `ADR-A6` (adr-backlog-from-architecture.md L138–156):

- Detection-failure default is `"external_mixed"`, NOT `"library_only"` — "loud refusal beats silent half-truth."
- Kernel-level enforcement via `_kernel/coverage.py` `_check_mcp_coverage(run)` helper is planned (Epic 1b Story 1b.2 / 1b.3) — the spike's prototype should be compatible with this gating shape, NOT duplicate it.

### File Structure (spike-scoped only)

```
_bmad-output/spikes/0-1-hosted-mcp-observer/
├── README.md                    # spike rationale + how-to-run
├── observer_prototype.py        # the candidate observer implementation
├── transports/
│   ├── in_memory_server.py      # MCP server via in-memory transport
│   └── stdio_subprocess_server.py
├── concurrency/
│   ├── test_pabot.robot         # 8+ tests exercising hosted MCP under per-test scope
│   └── pabot_evidence/          # captured output.xml + observer logs from runs
└── edge_cases/
    └── external_mixed_cases.py  # deliberate degradation probes

_bmad-output/spikes/spike-hosted-mcp-observer-findings.md   # THE deliverable
```

### Testing Standards

- **No coverage targets.** Spike code is exploratory.
- **Reproducibility is the bar.** Every claim in the findings document must point to a captured command + output, ideally saved under `spike-hosted-mcp-observer/concurrency/pabot_evidence/` or `edge_cases/`.
- **`pabot --processes 4` for concurrency**, NOT 8. Architecture.md Decision-3 mentions `pabot --processes 8` for Story 0.2 (cleanup spike); 0.1 only needs to demonstrate the observer survives parallel Listener v3 scope under reasonable load. Story 0.2 covers the heavier 8-process cleanup question.

### Project Structure Notes

- Spike output deliberately lives OUTSIDE `src/AgentEval/` (which doesn't exist yet — Story 1a.1 creates it). The intentional separation prevents future Epic 5 work from picking up spike code accidentally.
- Findings document at `_bmad-output/spikes/` (a sibling of `planning-artifacts/`) — establishes the `_bmad-output/spikes/` convention for any future spikes Phase 1 may need.
- No conflicts with architecture.md project tree (L1141–1445).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-0.1] — full story text + acceptance criteria
- [Source: _bmad-output/planning-artifacts/architecture.md#Decision-3] (L688–720) — original spike framing, ±20% estimation gate, Phase 1.5 escape hatch
- [Source: _bmad-output/planning-artifacts/architecture.md#Project-Tree] (L1141–1445) — planned `mcp/observer.py` location (Epic 5 will land it; spike must NOT)
- [Source: _bmad-output/planning-artifacts/adr-backlog-from-prd.md#ADR-007] (L61–74) — proposed-status ADR this spike ratifies
- [Source: _bmad-output/planning-artifacts/adr-backlog-from-architecture.md#ADR-A6] (L138–156) — `mcp_coverage` field semantics + `"external_mixed"` safe default
- [Source: _bmad-output/planning-artifacts/prd.md] — FR35 (universal observer), FR36b (`mcp_coverage` field), FR40 (per-test scope) — search by FR ID
- [Source: _bmad-output/planning-artifacts/epics.md#Story-0.3] — downstream story that consumes this spike's findings

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context) — Claude Code, single autonomous session (2026-05-17, ~2h wall time).

### Debug Log References

- `mcp.client.stdio.stdio_client` UnsupportedOperation: fileno under RF — see findings §RF-Compat finding. Root cause: `errlog=sys.stderr` default + RF stdout/stderr capture buffer lacking `.fileno()`. Workaround: pass real file object.
- Pabot test-level parallelism requires `--testlevelsplit` flag; without it, an 8-test single-suite invocation runs serially on one worker. Surface in `docs/contracts/listener-integration.md`.
- `PABOTQUEUEINDEX` is an RF variable (not env var) in pabot 5.2.2 — used `os.getpid()` for per-worker file split since accessing RF BuiltIn from a regular library couples scope.

### Completion Notes List

- **Verdict:** `AMEND-ADR-007` (renumbers to ADR-004). Amendment text drafted inline in findings doc §Verdict — ready for Story 0.3 copy-edit.
- **Co-verdict:** `AMEND-ADR-A6` (renumbers to ADR-016). Adapter-vs-observer responsibility split + weakest-coverage semantics drafted inline in findings doc §Related.
- **No verdict for ADR-A8** — sandbox policy unaffected by this spike (Story 0.2 may surface ADR-A8 deltas independently).
- **Estimation gate met:** Epic 5 Story 5.2 effort estimate 10.5-11.5 days (2.1-2.3 weeks), within architecture.md ±20% gate. **No Phase 1.5 hardening sprint triggered.**
- **Honesty caveat:** This is an LLM-driven autonomous spike, NOT a 5-day human exploration. Architect review mandatory before Story 0.3 ratifies amendments. macOS untested (Linux-only env). `streamable_http` transport coverage untested (Story 5.2 first task should be a 1-day mini-spike before committing to full plan).
- **Critical RF-compat finding** must propagate to Epic 3 Story 3.1 (mcp/transport.py) AND Epic 5 Story 5.2 (mcp/observer.py): stdio_client requires file-backed `errlog` under RF capture.
- **Adapter contract**: ADR-A6's safe default only works if adapters call `mark_external_mixed(reason)` when detecting external MCP — observer alone is structurally blind to uninstrumented servers.

### File List

**Created (spike scratch, lives in `_bmad-output/spikes/0-1-hosted-mcp-observer/`):**

- `pyproject.toml` — scratch deps EXACT-PINNED (mcp==1.27.1, robotframework==7.4.2, pabot==5.2.2, anyio==4.13.0, uvicorn==0.47.0)
- `uv.lock` — full transitive dependency lock (post-P8 review fix)
- `README.md` — spike rationale + re-run commands (post-P10 review fix)
- `observer_prototype.py` — `HostedMcpObserver` with D1 trust-floor semantic + declared `_external_mixed_reasons` field; `AgentRunResult`, `ToolCallTrace` dataclasses + `write_jsonl`
- `run_dual_transport_probe.py` — in-memory + stdio orchestrator (now spawns the D2 wrapper, not raw server)
- `run_streamable_http_probe.py` — D3 streamable HTTP probe (FastMCP + uvicorn + observer attach)
- `run_smoke_loop.sh` — 5-iteration pabot smoke loop with per-iter evidence preservation + timing capture (P3 + P4 fix)
- `transports/__init__.py`, `concurrency/__init__.py`, `edge_cases/__init__.py` — package markers
- `transports/in_memory_server.py` — in-memory MCP server fixture
- `transports/stdio_subprocess_server.py` — plain MCP server (instrumentation removed per D2)
- `transports/subprocess_observer_wrapper.py` — D2 wrapper that injects observer at subprocess bootstrap
- `transports/streamable_http_server.py` — D3 FastMCP server fixture for streamable_http probe
- `concurrency/SpikeLibrary.py` — RF library with 4 probe keywords (dual / hosted-only / subprocess-only / external-mixed) per P11
- `concurrency/test_pabot.robot` — 15-test suite covering all 3 coverage states (P11 fix)
- `edge_cases/external_mixed_cases.py` — 5 edge-case probes including real partial-log scenario (P12 fix)
- `measurements/dual_transport.jsonl` — dual-transport probe evidence
- `measurements/streamable_http.jsonl` — D3 probe evidence
- `measurements/edge_cases.jsonl` — 5 edge-case results
- `measurements/smoke_loop.txt` — 5-iteration timing + pass/fail summary
- `concurrency/pabot_evidence/iter_{1..5}/` — per-iteration JSONL + output.xml + pabot_stdout.log (P3 fix)

**Created (deliverable artifact, survives spike):**

- `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` — **the load-bearing deliverable** with verdict, amendment text, reproducibility commands, and Story 0.3 hand-off.

**Modified:**

- `_bmad-output/implementation-artifacts/0-1-run-hosted-mcp-universal-observer-spike.md` (this file) — Status `ready-for-dev` → `review` → `done`; Tasks/Subtasks checked off; Dev Agent Record populated; Review Findings section appended after code review.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — `0-1`: `in-progress` → `review` → `done`. `0-3`: `ready-for-dev` → `blocked` (D5 review decision).
- `_bmad-output/implementation-artifacts/0-3-amend-and-ratify-spike-dependent-adrs.md` — Status `ready-for-dev` → `blocked` with D5 unblock criteria documented.
- `_bmad-output/implementation-artifacts/deferred-work.md` — created during code review; carry-overs for Epic 3 Story 3.1 + Epic 5 Story 5.2 + Story 0.2 + Story 0.3.

**Not modified (per spike discipline — these belong to downstream stories):**

- `src/AgentEval/**` — does not exist yet (Story 1a.1 creates it). Spike code lives OUTSIDE `src/AgentEval/` by design.
- `docs/adr/**` — Story 0.3 owns ADR ratification, not 0.1.
- `_bmad-output/planning-artifacts/architecture.md` — Story 0.3 owns the Step-4 delta note.

### Change Log

- 2026-05-17 — Spike executed end-to-end by Claude Opus 4.7. Verdict AMEND-ADR-007 (→ ADR-004) with co-verdict AMEND-ADR-A6 (→ ADR-016). Findings document delivered. Status moved to `review` pending architect validation before Story 0.3 ratification.
- 2026-05-17 — Code review (3-layer adversarial: Blind Hunter, Edge Case Hunter, Acceptance Auditor) completed. 5 decisions needed, 12 patches identified, 20 items deferred to Story 5.2 / Story 0.2 production work. Status remains `review` pending decision resolution + patch application.
- 2026-05-17 — All 5 review decisions resolved (D1 trust-floor, D2 real handler-wrap injection, D3 streamable_http added, D4 adapter contract ratified, D5 independent reproduction commissioned). All 12 patches applied: observer rewritten with trust-floor semantic + declared `_external_mixed_reasons` field; subprocess wrapper script (`subprocess_observer_wrapper.py`) injects observer at subprocess bootstrap; streamable_http transport + probe added; 15-test RF suite covering all 3 coverage states; partial-log corrupt-JSON handling; `pyproject.toml` exact-pinned + `uv.lock` committed; README.md added; smoke loop wrapper preserves per-iter evidence + timing capture; findings doc rewritten with gate banner + calibrated claims + amendment text matching implementations. Re-run: 75/75 pabot runs pass over 5 iterations (195 tool calls, all 3 coverage states); 5/5 edge cases pass. Status: `done` (Story 0.1 complete); Story 0.3 blocked on D5 independent reproduction.

### Review Findings

**Review date:** 2026-05-17. **Reviewers:** Blind Hunter, Edge Case Hunter, Acceptance Auditor (LLM subagents). **72 raw findings → triaged.**

#### Decisions Needed (Architect call required before Story 0.3 ratifies amendments) — ALL RESOLVED 2026-05-17

- [x] **[Review][Decision] D1 — `mcp_coverage` weakest-coverage trust semantic is internally inconsistent.** **Resolved: trust-floor** (strongest complete path wins; degrade to `external_mixed` only on path failure). Implemented in `observer_prototype.py::finalize()`; ADR-A6 amendment text in findings doc §Related ratified. **Resolved: trust-floor** (strongest complete path wins; degrade to `external_mixed` only on path failure). Implemented in `observer_prototype.py::finalize()`; ADR-A6 amendment text in findings doc §Related ratified.

- [x] **[Review][Decision] D2 — Stdio path is NOT actually a `request_handlers` observer.** **Resolved: rebuild with real handler-wrap injection.** Created `transports/subprocess_observer_wrapper.py` that injects `HostedMcpObserver` at subprocess bootstrap via the SAME `request_handlers[CallToolRequest]` wrap pattern as the in-memory leg. Original `stdio_subprocess_server.py` stripped of baked-in instrumentation. Re-validated end-to-end.

- [x] **[Review][Decision] D3 — `streamable_http` transport scoping.** **Resolved: expand spike now.** Added `transports/streamable_http_server.py` + `run_streamable_http_probe.py`. FastMCP + uvicorn server, observer attached via `_mcp_server`, validated 2/2 tool calls captured. Handler-wrap pattern is now confirmed transport-agnostic across all three transports.

- [x] **[Review][Decision] D4 — ADR-A6 amendment reaches into Story 4.2 scope.** **Resolved: ratify adapter contract now.** ADR-A6 amendment in findings doc §Related now formally ratifies the adapter contract (Claude Code CLI MUST parse `~/.claude.json` + project `.mcp.json` and call `mark_external_mixed(reason)`). This constrains Story 4.2 to that contract. Trade-off accepted: front-loads the decision.

- [x] **[Review][Decision] D5 — Re-run rigor before ratification.** **Resolved: commission independent reproduction.** Story 0.3 is now **blocked** until a different LLM/human reproduces the smoke loop + edge cases. Blocker documented in Story 0.3 file. Findings doc has a gate banner at the top. macOS validation is a Phase-1 carry-over per `deferred-work.md`.

#### Patches (Unambiguous fixes — ALL APPLIED 2026-05-17)

- [x] **[Review][Patch] P1 — PIPE_BUF atomicity claim is wrong.** Comment in `observer_prototype.py:247-251` says "O_APPEND on POSIX is atomic for writes ≤ PIPE_BUF (4096 on Linux)". PIPE_BUF applies to pipes, not regular files. Python's `f.write()` is buffered; large `json.dumps()` outputs may split across multiple `write(2)` syscalls. Findings doc inherits the claim. Replace with accurate guarantee or document the actual constraint. [observer_prototype.py:247-251, stdio_subprocess_server.py:92-94, findings doc]

- [x] **[Review][Patch] P2 — Findings overclaims "100% capture, zero drops".** The 40/40 smoke-loop runs used 4-byte arguments + no crashes + no contention beyond 4-process pabot. Failure modes (large payloads non-atomic writes, subprocess crashes mid-log, JSON parse errors, observer re-attach) were not exercised. Rewrite findings §Concurrency probe to concretely scope what was tested vs what was not. [findings §Concurrency probe L111-127]

- [x] **[Review][Patch] P3 — Per-iteration pabot evidence not preserved.** Reproducibility appendix runs `rm -rf concurrency/pabot_evidence/*.jsonl` before each iteration. Only the last iteration's JSONL survives; the "40/40 runs verifiable" claim is unverifiable from artifacts. Either preserve per-iteration directories (`iter1/`, `iter2/`, ...) OR rewrite the §Concurrency probe table to note summary-only evidence with the smoke_loop.txt as the surviving artifact. [findings §Concurrency probe + §Reproducibility appendix]

- [x] **[Review][Patch] P4 — Timing capture command missing from Reproducibility appendix.** Mean wall time 11.83s is a load-bearing claim. Add the bash wrapper that produced `measurements/smoke_loop.txt` (the `date +%s.%N` + `bc` pattern) so readers can reproduce. [findings §Reproducibility appendix L348-369]

- [x] **[Review][Patch] P5 — macOS caveat missing from inline ADR amendment text.** §Verdict amendment text for ADR-007 has no "Linux-only validation; macOS pending" line; only the surrounding prose mentions it. Story 0.3 will lose this caveat when copy-editing. Add a one-line "Empirical evidence captured on Linux 6.8; macOS validation pending Story 9.x" to the inline amendment block. [findings §Verdict L267-281]

- [x] **[Review][Patch] P6 — ±20% baseline is unpinned.** §Estimated effort delta cites "Original estimate: Implied moderate complexity (1-2 weeks)" — vague. The "1.6-2.4 weeks" gate is calculated from an imprecise base. Either cite a specific source (epics.md Story 5.2 effort field, if it exists) or compute concretely from architecture.md Decision-3 anchors. [findings §Estimated effort delta]

- [x] **[Review][Patch] P7 — `AdapterVersionDriftWarning` referenced as if it exists.** Findings §Verdict Consequences references the warning class as a current artifact. It's a planned Epic 5/6 deliverable. Reword: "An `AdapterVersionDriftWarning` MUST be added (Epic 5 Story 5.2 deliverable per FR — listed in architecture.md project tree L —)". [findings §Verdict Consequences amendment L277]

- [x] **[Review][Patch] P8 — `pyproject.toml` uses `>=` pins; spec Task 1 claims `==` pins; no `uv.lock` committed.** A fresh `uv sync` could pick `mcp` 1.30+ and break the `request_handlers` dict pattern silently. Either commit `uv.lock` to the spike dir OR change `pyproject.toml` to exact pins (`mcp==1.27.1`, etc.). Align spec Task 1 wording. [pyproject.toml, story Task 1]

- [x] **[Review][Patch] P9 — Add a "Phase 1 Carry-overs" tracking item for the RF-compat finding.** The `stdio_client` errlog=sys.stderr → `fileno()` failure is the spike's highest-value finding for downstream stories. Currently captured only in findings doc prose. Add an explicit hand-off item to sprint-status.yaml OR a new `docs/contracts/listener-integration.md` skeleton stub so Epic 3 Story 3.1 + Epic 5 Story 5.2 + Story 1a.4 cannot miss it. [findings §RF-Compat finding L172-192]

- [x] **[Review][Patch] P10 — Spec File Structure claims `README.md` in spike dir; file doesn't exist.** Either add a one-pager README.md pointing to the findings doc + re-run commands, or remove from spec Dev Notes §File Structure. [spec L100-114]

- [x] **[Review][Patch] P11 — `test_pabot.robot` only asserts `subprocess_with_observer`; never validates `hosted_in_process` or `external_mixed` under RF execution.** AC-0.1.1 requires the field to be "exactly one of" three values; only one is actually tested under pabot. Add at minimum one RF test asserting `hosted_in_process` (e.g., in-memory-only probe) and one asserting `external_mixed` (e.g., explicitly call `mark_external_mixed` + no attach) so the AC-0.1.1 3-state claim is exercised under the concurrency conditions Story 0.1 is supposed to validate. [concurrency/test_pabot.robot:10-46]

- [x] **[Review][Patch] P12 — `probe_subprocess_dies_midtest` doesn't test what its name claims.** The probe reads a nonexistent file (missing-log path), which is structurally identical to "no observation collected". A real subprocess crash leaves a *partial* JSONL with a truncated last line — which exposes the unhandled `json.JSONDecodeError` in `_graft_subprocess_log:103`. Either fix the graft to handle malformed lines + retest with a real partial log, OR rename the probe to `probe_missing_subprocess_log` to match what it actually tests. [edge_cases/external_mixed_cases.py:60-68, run_dual_transport_probe.py:93-118]

#### Deferred (Real defects in throwaway spike code — for Epic 5 Story 5.2 or Story 0.2)

- [x] [Review][Defer] `attach()` double-attach double-counts every tool call [observer_prototype.py:89-143] — deferred; production observer (Story 5.2) needs idempotency guard
- [x] [Review][Defer] SDK swallows tool exceptions → observer's `except` branch is dead code; tool failures masquerade as successes [observer_prototype.py:111-136] — deferred to Story 5.2
- [x] [Review][Defer] `_graft_subprocess_log` mutates private `_seq`/`_traces`/`_has_subprocess_observation` (which is dead code) [run_dual_transport_probe.py:99-118] — deferred; production observer must encapsulate via `_record()`
- [x] [Review][Defer] `mark_external_mixed` stores only last reason; multiple uninstrumented servers lose forensic detail [observer_prototype.py:170-177] — deferred; use `list[str]` in production
- [x] [Review][Defer] `metadata_reason` is an undeclared instance attribute with `# type: ignore` — typo-fragile [observer_prototype.py:170, 187, 204] — deferred; declare field in `__init__` for production
- [x] [Review][Defer] `_summarize_result` only inspects `blocks[0]`; multi-block / image-first results silently truncated [observer_prototype.py:210-220] — deferred
- [x] [Review][Defer] `dict(req.params.arguments)` accepts non-JSON-serializable values that explode later in `write_jsonl` [observer_prototype.py:113] — deferred to Story 5.2 with proper schema enforcement
- [x] [Review][Defer] Trace dict shallow-copy: nested mutable args mutated by caller after `finalize` corrupts the snapshot [observer_prototype.py:113, 199] — deferred
- [x] [Review][Defer] `observed_paths` sorted alphabetically, not by decision order — confuses evidence trail [observer_prototype.py:205] — deferred
- [x] [Review][Defer] `finalize()` can be called repeatedly producing different `run_id`s on same traces — no terminal-state guard [observer_prototype.py:179-207] — deferred
- [x] [Review][Defer] `os.getpid()` per-worker filename: pid recycling possible on long pabot runs [concurrency/SpikeLibrary.py:29] — deferred; production needs UUID or run-id prefix
- [x] [Review][Defer] `OBSERVER_LOG_PATH` env var: collides with parent's existing var; not validated against directory paths [run_dual_transport_probe.py:65-66, stdio_subprocess_server.py:74-75] — deferred; namespace as `AGENTEVAL_OBSERVER_LOG_PATH` + validate
- [x] [Review][Defer] Stdio subprocess `latency_ms` is tool-body wall-clock; in-memory is wrapped-handler wall-clock — same field name, different semantics [stdio_subprocess_server.py:62, observer_prototype.py:111-138] — deferred; document or unify
- [x] [Review][Defer] Subprocess `_append_log` opens/closes file per tool call — high syscall overhead for hot loops [stdio_subprocess_server.py:92-94] — deferred; performance polish for Story 5.2
- [x] [Review][Defer] `start_new_session=True` claim (mcp SDK default) unverified by Story 0.1 — Story 0.2's scope per findings — deferred to Story 0.2
- [x] [Review][Defer] `mcp>=1.10` compat claim unbacked — only mcp 1.27.1 tested; line numbers cited are 1.27.1-specific [pyproject.toml:7, findings doc] — deferred; AdapterVersionDriftWarning + version matrix testing in Story 5.2
- [x] [Review][Defer] `_graft_subprocess_log` cleanup unlinks temp + stderr files on stdio_client startup failure — destroys forensics [run_dual_transport_probe.py:85-90] — deferred; production needs error-path-preserves-state pattern
- [x] [Review][Defer] `stderr_path = log_path + ".stderr"` derived name can clobber pre-existing file [run_dual_transport_probe.py:63] — deferred; use tempfile for both
- [x] [Review][Defer] `_seq` increment + `_traces.append` not locked; multi-concurrent-client to a single observer instance has race [observer_prototype.py:155-168] — deferred; document single-producer assumption or add lock for Story 5.2
- [x] [Review][Defer] Test ID defaults inconsistent (`probe-cli` vs `probe-default` between code paths) [run_dual_transport_probe.py:124, 132] — deferred
