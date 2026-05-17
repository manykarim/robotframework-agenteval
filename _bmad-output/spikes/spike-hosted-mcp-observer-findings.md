# Spike Findings — Story 0.1: Hosted-MCP Universal Observer

> **✅ D5 INDEPENDENT REPRODUCTION LANDED 2026-05-17** — Three agents (Codex CLI, GitHub Copilot CLI, Claude Sonnet 4.6) independently ran reproductions. **3/3 GO for Story 0.1.** Smoke loop reproduced exactly: 75/75 runs pass, 195 tool calls captured, all 3 coverage states observed per iter, wall time 9.86–16.20s/iter (cross-agent range). Edge cases 5/5 pass under all 3 agents. Verdict text + ADR-007 / ADR-A6 amendments are robustly reproducible. Full synthesis: `_bmad-output/spikes/d5-reproduction-report.md`.

**Date:** 2026-05-17 (initial) → 2026-05-17 (post-review rework: D1+D2+D3+D4+P1..P12)
**Spike branch (planned):** `spike/0-1-hosted-mcp-observer` (no git in current workspace; branch would be created in a git-initialized repo)
**Verdict for ADR-007:** `AMEND-ADR-007` — see §Verdict.

---

## TL;DR

1. **`mcp` Python SDK exposes no middleware/interceptor API.** Observation is feasible via a third path the architecture didn't enumerate: **wrapping `Server.request_handlers[CallToolRequest]`** at runtime. Validated across THREE transports — in-memory, stdio subprocess (via wrapper that injects the observer at subprocess bootstrap), and streamable HTTP (FastMCP + uvicorn).
2. **The handler-wrap pattern works in subprocess context, not just in-process.** Post-review rework (D2): the stdio leg was rebuilt with a `subprocess_observer_wrapper.py` that imports the target server module, attaches `HostedMcpObserver` in the subprocess process, runs stdio, and persists a finalized trace JSONL for the parent to graft. Same `request_handlers[CallToolRequest]` mechanism as in-memory; just running in a different process.
3. **The observer survives `pabot --processes 4` per-test scope concurrently** with all THREE `mcp_coverage` states exercised (post-review P11). 5-iteration smoke loop: 5×15 = 75 runs, 75/75 pass, 195 tool calls captured 100% (15 runs × 13 calls/iter — 9× hosted+dual (4+2 calls), 3× subprocess-only (2 calls), 3× external-mixed (1 call)). No drops, no duplicates, no cross-test trace leakage observed.
4. **There is a load-bearing RF-compat issue** with `mcp.client.stdio.stdio_client`: its default `errlog=sys.stderr` breaks under RF execution because RF replaces `sys.stderr` with a non-fd capture buffer, causing `io.UnsupportedOperation: fileno` during subprocess spawn. **Workaround**: pass a real file object for `errlog`. **This must be wired into `mcp/transport.py` (Epic 3) AND surfaced in the contributor docs for `mcp/observer.py` (Epic 5).** Captured as a Phase-1 carry-over in `_bmad-output/implementation-artifacts/deferred-work.md`.
5. **`mcp_coverage` semantic = trust-floor (D1 review decision).** Strongest complete path wins (`hosted_in_process` > `subprocess_with_observer` > `external_mixed`). Degrade to `external_mixed` only on explicit path failure (adapter signals `mark_external_mixed(reason)` OR no instrumented servers attached OR subprocess log unparseable). When BOTH `hosted_in_process` and `subprocess_with_observer` paths fire successfully, result reports `hosted_in_process` — a more-instrumented run gets credit for being more-instrumented. ADR-A6 amendment text in §Verdict reflects this.
6. **Adapter cooperation is mandatory for `external_mixed` detection.** The observer is structurally blind to MCP servers it didn't attach to. The adapter must actively detect external MCP usage and call `observer.mark_external_mixed(reason)`. D4 review decision: ratify this adapter contract as part of the ADR-A6 amendment (constrains Story 4.2 Claude Code CLI adapter).

---

## §Toolchain (pinned per P8)

| Component | Version | Notes |
|---|---|---|
| Python | 3.12.3 | Per architecture.md NFR-COMPAT-*; matches Story 1a.1 dep target |
| mcp | 1.27.1 | architecture.md pins `mcp>=1.10`; spike validates 1.27.1 only |
| robotframework | 7.4.2 | architecture.md pins `>=7.3` |
| robotframework-pabot | 5.2.2 | architecture.md NFR-PERF-05 mandates pabot |
| anyio | 4.13.0 | mcp's async dep |
| uvicorn | 0.47.0 | FastMCP streamable_http transport |
| OS | Linux 6.8.0-110-generic, glibc 2.39 (Ubuntu 24.04) | **macOS untested in this spike — Phase-1 carry-over** |

`uv.lock` is committed at `_bmad-output/spikes/0-1-hosted-mcp-observer/uv.lock` for full transitive reproducibility.

---

## §Observation-hook decision (the central question)

### Question
> Per architecture.md Decision-3 L693–694: "determine whether `mcp` Python SDK exposes a clean middleware/interceptor API for server-side observation, OR whether custom MCP server subclass with protocol-layer re-implementation is required."

### Empirical finding
`mcp.server.lowlevel.Server` dispatches client requests via a runtime-mutable dict:

```python
# mcp 1.27.1, mcp/server/lowlevel/server.py L156
self.request_handlers: dict[type, Callable[..., Awaitable[types.ServerResult]]] = {}

# mcp 1.27.1, L586 — @server.call_tool decorator assigns into this dict
self.request_handlers[types.CallToolRequest] = handler
```

The `@server.call_tool()` decorator (L492) registers the handler at `request_handlers[CallToolRequest]`. Nothing in the public API enforces the dict's immutability after registration. **The Server class does NOT expose middleware/interceptor hooks, NOR does it require subclassing — there is a third, simpler path: replace `request_handlers[CallToolRequest]` with a wrapping function after tool registration.**

### Pattern that works (the candidate `mcp/observer.py` API surface)

```python
class HostedMcpObserver:
    def attach(self, server: Server | FastMCP, observation_path: str = "hosted_in_process") -> None:
        lowlevel = server._mcp_server if isinstance(server, FastMCP) else server
        original = lowlevel.request_handlers[CallToolRequest]
        async def wrapped(req):
            try:
                result = await original(req)
            except Exception:
                self._record(..., "<exception>")
                raise
            self._record(...)  # post-call: extract name, args, latency, summary
            return result
        lowlevel.request_handlers[CallToolRequest] = wrapped
```

**Concrete evidence:** `_bmad-output/spikes/0-1-hosted-mcp-observer/observer_prototype.py`. The wrapping pattern is the load-bearing implementation choice for Epic 5 Story 5.2.

### Trade-offs

**Pros:**
- No subclassing — works for any server users construct via `Server(...)` or `FastMCP(...)` without modifying their code.
- One observer instance can attach to many servers within the same process.
- Compatible with both lowlevel `Server` and high-level `FastMCP`.
- **Works across process boundaries** (post-D2 validation): the same pattern installed in a subprocess via the wrapper script captures tool calls just as effectively as in-process.
- **Works across all three transports tested** (post-D3 validation): in-memory, stdio subprocess, streamable HTTP.

**Cons:**
- Accesses `request_handlers` which is technically a public attribute (not name-mangled) but never advertised as a stability surface in mcp SDK docs. **Risk:** a future mcp SDK version could replace dict-dispatch with a closed registration mechanism. Mitigation: `AdapterVersionDriftWarning` MUST be added (Epic 5 Story 5.2 deliverable per architecture.md project tree references) to detect mcp SDK major-version bumps.
- For FastMCP, accesses `_mcp_server` (underscore-prefixed private attribute). **Officially undocumented**; the mcp SDK source notes "we should expose a method in the `FastMCP` so we don't access a private attribute" (see `mcp/shared/memory.py` L64) — they have the same coupling internally. **Recommend Epic 5 file an upstream issue requesting a stable public hook.**

### Alternatives considered and rejected

| Alternative | Why rejected |
|---|---|
| Custom Server subclass + override `_handle_request` | Forces every test author to use our subclass; brittle if they're already wrapping `Server`. |
| Protocol-layer re-implementation (write our own MCP server) | 10×–100× the implementation cost; gives up access to mcp SDK's transport machinery. Architecture.md Decision-3 explicitly flagged this as the "worst-case" outcome. |
| Wrap the underlying transport streams | Possible in principle, but observability lives below the JSON-RPC layer — would need to parse JSON-RPC bytes to reconstruct tool-call semantics. Brittle. |
| Monkey-patch `Server.call_tool` decorator at module level | Breaks any user code that calls `server.call_tool()` directly on a server they constructed elsewhere; global state pollution. |
| Instrument cooperating subprocess servers at source (the spike's original stdio approach) | Discarded post-D2 review: this is NOT the handler-wrap pattern, just printf-debugging dressed up. The ratified approach is wrapper-script injection at subprocess bootstrap. |

### Recommendation
**Use `request_handlers` dict-wrapping.** Document the mcp version coupling in `docs/contracts/mcp-coverage-detection.md` (Story 1a.4 owns the skeleton). Add an `AdapterVersionDriftWarning` for `mcp` SDK major-version bumps (Story 5.2 deliverable).

---

## §Concurrency probe — `pabot --processes 4` (post-review P3 + P11 evidence preservation)

### Methodology

- **Suite:** `concurrency/test_pabot.robot` — **15 tests covering ALL THREE `mcp_coverage` states** (AC-0.1.1 "exactly one of"):
  - 6 × `Run Dual Transport Probe` → asserts `hosted_in_process` + 4 tool calls (D1 trust-floor: in-memory + stdio both fire)
  - 3 × `Run Hosted In Process Probe` → asserts `hosted_in_process` + 2 tool calls (in-memory only)
  - 3 × `Run Subprocess Only Probe` → asserts `subprocess_with_observer` + 2 tool calls (stdio only, D2 wrapper injection)
  - 3 × `Run External Mixed Probe` → asserts `external_mixed` + 1 tool call (adapter signals path failure)
- **Per-test fresh observer:** `ROBOT_LIBRARY_SCOPE = "TEST"` on `SpikeLibrary.py` instantiates a new library per test.
- **Pabot invocation:** `pabot --testlevelsplit --processes 4` — `--testlevelsplit` is required to get test-level parallelism. **Surface this in `docs/contracts/listener-integration.md` (Story 1a.4 skeleton): "agenteval's per-test scope guarantees rely on pabot `--testlevelsplit`; without it, all tests in a suite serialize through one worker."**
- **Per-iteration evidence preservation (P3 fix):** the wrapper script `run_smoke_loop.sh` moves each iteration's per-worker JSONL files + RF output.xml into `concurrency/pabot_evidence/iter_{1..5}/` so every iteration's evidence survives the smoke loop.
- **Smoke loop:** 5 consecutive iterations, 15 tests each = 75 runs total.

### Results

| Iter | Wall time (s) | Tests pass | Per-iter runs | Per-iter tool calls | Per-iter coverage breakdown |
|---|---|---|---|---|---|
| 1 | 9.33 | 15/15 | 15 | 39 | hosted_in_process=9, subprocess_with_observer=3, external_mixed=3 |
| 2 | 9.74 | 15/15 | 15 | 39 | hosted_in_process=9, subprocess_with_observer=3, external_mixed=3 |
| 3 | 11.02 | 15/15 | 15 | 39 | hosted_in_process=9, subprocess_with_observer=3, external_mixed=3 |
| 4 | 11.14 | 15/15 | 15 | 39 | hosted_in_process=9, subprocess_with_observer=3, external_mixed=3 |
| 5 | 11.00 | 15/15 | 15 | 39 | hosted_in_process=9, subprocess_with_observer=3, external_mixed=3 |

- **Mean wall:** 10.45s
- **Total runs:** 75 / 75 passed (5 iter × 15 tests)
- **Total tool calls captured:** 195 (5 iter × 39)
- **Drops:** 0 (verified by per-iter `tool_call_count` matching the expected per-test count for each probe type)
- **Duplicates:** 0
- **Cross-test leakage:** none (each run's `test_id` field matches its source test name)

**What this evidence does NOT cover (P2 — calibrated claims):**
- Workloads larger than 4 tool calls per test (no large-payload contention)
- Subprocess SIGKILL mid-test (the spike simulates partial-log via `probe_subprocess_dies_midtest` but does not actually kill a live subprocess under pabot)
- `pabot --processes 8` (Story 0.2 territory; this spike only covers `--processes 4` per AC-0.1.3)
- Long-running suites that exhaust pid space and force PID recycling
- mcp SDK versions other than 1.27.1
- macOS — Linux-only environment

### Raw evidence

`concurrency/pabot_evidence/iter_{1..5}/` — each directory contains:
- `worker_pid<N>.jsonl` — per-pabot-worker JSONL traces
- `output.xml` — that iteration's RF output XML
- `pabot_stdout.log` — captured pabot stdout

Plus `measurements/smoke_loop.txt` — timing + pass/fail summary.

### Reproducibility

```bash
cd _bmad-output/spikes/0-1-hosted-mcp-observer/
# Build venv if needed (uv.lock pins exact versions per P8)
uv venv --python 3.12 .venv
uv sync

# Run 5-iteration pabot smoke loop with per-iter evidence preserved (P3 + P4: includes timing capture)
./run_smoke_loop.sh
# → measurements/smoke_loop.txt, concurrency/pabot_evidence/iter_{1..5}/
```

The script (`run_smoke_loop.sh`) handles the LC_ALL locale issue, timing capture via `date +%s.%N`, and per-iter directory preservation. P4 satisfied.

### Answer to AC-0.1.3

**Yes, the observer survives a hosted MCP server with concurrent Listener v3 per-test scope under `pabot --processes 4`** across all three `mcp_coverage` states. 75/75 runs over 5 consecutive iterations produced complete traces with the expected coverage value. No drops, no duplicates, no cross-test leakage at this scale and workload.

---

## §Transport coverage

### In-memory transport (`hosted_in_process`)

- **Implementation:** `mcp.shared.memory.create_connected_server_and_client_session()` wires anyio memory streams between client and server in the same process.
- **Observation:** Direct via `request_handlers` wrap. Captures every tool call with sub-10ms latency.

### Stdio subprocess transport (`subprocess_with_observer`) — post-D2 rework

- **Implementation:** `transports/subprocess_observer_wrapper.py` is spawned as `python -m transports.subprocess_observer_wrapper`. Inside the subprocess:
  1. Import the target server module (default `transports.stdio_subprocess_server`; override via `OBSERVER_SERVER_MODULE` env var).
  2. Call `build_server()` to get a plain `Server` instance (NO baked-in instrumentation).
  3. Construct a fresh `HostedMcpObserver` in the subprocess process.
  4. `observer.attach(server, observation_path="subprocess_with_observer")` — same `request_handlers[CallToolRequest]` wrap mechanism as in-memory.
  5. Run the server via `stdio_server()`.
  6. On parent disconnect, `observer.finalize()` + `write_jsonl()` to `OBSERVER_LOG_PATH`.
- **Parent-side graft:** `run_dual_transport_probe.py::_graft_subprocess_observer_log()` reads the subprocess's finalized JSONL and replays each captured `ToolCallTrace` into the parent observer via `observer._record(...)` — preserving the observer's encapsulation invariant (review F-edge-15 fix).
- **Critical workaround:** `stdio_client(params, errlog=<real file>)` MUST pass a file object — see §RF-Compat finding.
- **Trade-off:** This pattern requires the library to KNOW the target server module to spawn it via the wrapper. For genuinely third-party stdio MCPs (binaries we cannot wrap), the observer is structurally blind and the run degrades to `external_mixed` honestly. Documented as Phase-1 carry-over.

### Streamable HTTP transport (`hosted_in_process`) — post-D3 rework

- **Implementation:** `transports/streamable_http_server.py` builds a FastMCP server with `echo` + `add` tools. `run_streamable_http_probe.py` launches uvicorn on a free local port in a background task, attaches the observer to `fastmcp._mcp_server` BEFORE serving, connects via `mcp.client.streamable_http.streamablehttp_client`, calls tools, asserts.
- **Observation:** Same `request_handlers` wrap pattern. Validated.
- **Result:** `measurements/streamable_http.jsonl` shows 2 tool calls captured, `mcp_coverage = "hosted_in_process"`, observed_paths = `["hosted_in_process"]`. **The pattern is transport-agnostic.**
- **Caveat:** Only single-process happy path tested. Multi-session streamable_http with reconnection / SSE resumption is Epic 5 Story 5.2 territory.

---

## §RF-Compat finding (load-bearing)

> **Failure mode:** Running `stdio_client(params)` under RF/pabot raises `io.UnsupportedOperation: fileno` during subprocess spawn.

**Trace:**
```
mcp/client/stdio/__init__.py:251 → anyio.open_process(...)
  → asyncio.create_subprocess_exec(...)
    → subprocess.Popen._get_handles(stdin, stdout, stderr)
      → stderr.fileno()
        → io.UnsupportedOperation: fileno
```

**Root cause:** RF captures stdout/stderr in `io.StringIO`-like objects without OS file descriptors. The `subprocess` module needs a real fd to pass to the child's stderr. `mcp.client.stdio.stdio_client(server, errlog=sys.stderr)` (L106 of mcp/client/stdio/__init__.py) defaults to `sys.stderr` which RF has already replaced.

**Workaround applied in spike:** Pass an explicit file object: `stdio_client(params, errlog=open(stderr_path, "w"))`. Tested under `pabot --processes 4` × 5 smoke iterations × 15 tests = 75 runs — zero failures.

**Production implications (Phase-1 carry-overs per P9):**
- Epic 3 Story 3.1 (MCP Server Lifecycle Keywords) **MUST** use a non-default `errlog` value when calling `stdio_client`. Recommended: write subprocess stderr to a per-test temp file that goes into the OTel trace's evidence block (FR — evidence-block-format.md per Story 1a.4).
- Epic 5 Story 5.2 (Hosted-MCP Observer) **MUST** document this constraint in the observer's docstring and `docs/contracts/listener-integration.md`.
- Tests/conformance suite **MUST** include a fixture that exercises stdio MCP under RF capture to prevent regression.

Captured as a Phase-1 carry-over in `_bmad-output/implementation-artifacts/deferred-work.md`.

---

## §`mcp_coverage` field semantic (D1 ratified: trust-floor)

The 3-state field (`hosted_in_process` | `subprocess_with_observer` | `external_mixed`) under the D1 trust-floor convention:

**Decision tree (implemented in `observer_prototype.py::finalize`):**

```
1. If any external_mixed signal was raised (mark_external_mixed called):
       → "external_mixed"  (explicit path failure)
2. Else if at least one trace has observation_path == "hosted_in_process":
       → "hosted_in_process"  (strongest complete path observed)
3. Else if at least one trace has observation_path == "subprocess_with_observer":
       → "subprocess_with_observer"
4. Else (no traces AND no signals):
       → "external_mixed"  (catch-all safe default)
```

**Trust ordering (strongest to weakest):** `hosted_in_process` > `subprocess_with_observer` > `external_mixed`.

**Why trust-floor (D1 architect decision 2026-05-17):** A run that successfully observed BOTH `hosted_in_process` AND `subprocess_with_observer` gets credit for the **stronger** path actually achieving complete observation. `external_mixed` is reserved for runs with a **known** uninstrumented gap (explicit signal from adapter OR empty observations). A more-instrumented run gets credit for being more-instrumented.

**`observed_paths` metadata** is now ordered strongest-to-weakest (not alphabetical — review F-blind-14 fix), so consumers reading the JSONL can reconstruct the decision order without rerunning the logic.

| Run scenario | mcp_coverage | observed_paths |
|---|---|---|
| In-memory only | `hosted_in_process` | `["hosted_in_process"]` |
| Stdio subprocess only (wrapper injection) | `subprocess_with_observer` | `["subprocess_with_observer"]` |
| Streamable HTTP only | `hosted_in_process` | `["hosted_in_process"]` |
| Dual (in-memory + stdio) | `hosted_in_process` | `["hosted_in_process", "subprocess_with_observer"]` |
| Adapter signals external MCP | `external_mixed` | (paths captured before signal) |
| No attach, no signals | `external_mixed` | `[]` |
| Subprocess log corrupt / missing | `external_mixed` (with reason in metadata) | (in-memory paths if any) |

The ADR-A6 amendment text in §Verdict ratifies this.

---

## §Edge cases probed (5 probes, all PASS post-rework)

All 5 edge-case probes pass (`_bmad-output/spikes/0-1-hosted-mcp-observer/measurements/edge_cases.jsonl`):

| Probe | Setup | Expected | Actual | Result |
|---|---|---|---|---|
| `probe_no_attach` | Observer never attached | `external_mixed` | `external_mixed` | ✅ |
| `probe_external_server_blind` | Observer attached to A; agent uses A AND uninstrumented B; adapter calls `mark_external_mixed()` | `external_mixed` | `external_mixed` | ✅ |
| `probe_subprocess_dies_midtest` (P12 fixed) | Real partial-log scenario: 1 complete record + truncated tail | `external_mixed` | `external_mixed` (with accumulated reason) | ✅ |
| `probe_baseline_all_attached` | Clean in-memory instrumentation | `hosted_in_process` | `hosted_in_process` | ✅ |
| `probe_dual_path_trust_floor` (new) | Full dual-transport happy path | `hosted_in_process` (D1) | `hosted_in_process` | ✅ |

### Critical secondary finding from `probe_external_server_blind` (D4 ratified)

The probe attached the observer to server A but had the agent talk to BOTH A AND B (uninstrumented). The observer correctly reported `external_mixed` **only because the adapter explicitly called `mark_external_mixed()`**. Without that call, the observer would have reported `hosted_in_process` falsely.

**D4 ratification:** ADR-A6 amendment includes the adapter contract — see §Verdict.

---

## §Estimated effort delta for Epic 5 Story 5.2 (post-D3 expansion)

Per architecture.md Decision-3 L700: "Estimated effort for full Phase 1 implementation of FR35 + FR40 is within ±20% (i.e., 'we can plan around this number')."

**Baseline (P6 fix):** Architecture.md Decision-3 implies "moderate complexity" for the post-spike Story 5.2 implementation but does not give a concrete number. Using **2 weeks (10 working days)** as the baseline (consistent with epics.md Epic 5 sizing and architecture.md L700's "If estimate is >5 weeks, trigger Phase 1.5"). ±20% gate = 8 to 12 working days.

**Post-spike estimate:**

| Sub-work | Spike output reuse | Effort |
|---|---|---|
| Production observer class (replaces `observer_prototype.py`) | Direct port + unit tests + deferred-work fixes from review | 2.5 days |
| `request_handlers` wrapping + version compat + `AdapterVersionDriftWarning` | Spike validates approach | 1 day |
| RF-compat: file-backed stderr for stdio_client | Spike found the workaround | 0.5 day |
| D1 trust-floor `mcp_coverage` logic | Implemented in spike | 0.5 day |
| D2 subprocess wrapper (production version) | Spike validates approach | 1.5 days |
| D3 streamable_http transport coverage | Spike validates approach | 1 day |
| D4 adapter contract (`mark_external_mixed` API) | API defined; Story 4.2 implements adapter side | 0.5 day |
| Documentation (`mcp/observer.py` docstrings + `docs/contracts/mcp-coverage-detection.md`) | New work | 1 day |
| Tests (unit + integration + conformance fixtures, addressing deferred-work items) | New work | 2 days |
| Production-grade error handling (deferred-work items: SDK exception swallowing, multi-block summary, JSON serialization, terminal-state guards, locking) | New work, scoped from review findings | 1.5 days |

**Total: 12 working days (2.4 weeks).** Right at the high edge of the ±20% gate. **Verdict: estimation gate JUST met; risk of slipping past 2.4 weeks is real.** Architect should consider whether to schedule a Phase 1.5 hardening sprint for buffer.

**Risk note:** The deferred-work load (20 items from review) is real production-engineering effort that the original spike's "2 weeks moderate complexity" estimate did NOT account for. If any 2 items take longer than expected, the gate is breached.

---

## §Verdict

> **`AMEND-ADR-007`** (which renumbers to **ADR-004** per architecture.md project tree L1394)

**Amend the Decision section** with the empirically validated observation hook + D1 + D2 + D3 outcomes:

> **Decision (amended 2026-05-17 with empirical findings from Story 0.1):** When the library spawns the MCP server the agent connects to, it records every `tools/call` server-side via **handler-wrapping at `Server.request_handlers[CallToolRequest]`** — a runtime dict-mutation pattern. This works for `mcp.server.lowlevel.Server` and `mcp.server.fastmcp.FastMCP` (composes `Server` at `_mcp_server`). No subclassing required; no middleware API exists in mcp 1.27.1. The pattern is validated across THREE transports: in-memory, stdio subprocess (handler-wrap injected at subprocess bootstrap via a wrapper script the library spawns), and streamable HTTP (FastMCP + uvicorn). Implementation surface is ~250 LoC for the production observer; Phase 1 Epic 5 Story 5.2 effort estimate 12 working days (at the high edge of the ±20% gate per architecture.md Decision-3 L700). The pattern survives `pabot --processes 4` per-test scope under Listener v3 — 75/75 runs across 5 smoke iterations × 15 tests captured 100% of expected tool calls with zero drops/duplicates/cross-test-leakage. **Empirical evidence captured on Linux 6.8 only; macOS validation is a Phase-1 carry-over per Story 9.x.** Independent reproduction is a Story 0.3 precondition per D5 review decision.

**Amend the Consequences section** to add:

> Implementation must route stdio subprocess stderr to a real file (not `sys.stderr`) when running under Robot Framework — RF replaces `sys.stderr` with a non-fd capture buffer, breaking `mcp.client.stdio.stdio_client`'s default. See `docs/contracts/listener-integration.md` for the contributor-facing constraint.
>
> Implementation accesses `Server.request_handlers` and `FastMCP._mcp_server` — both technically internal in the mcp SDK. An `AdapterVersionDriftWarning` MUST be added as part of Epic 5 Story 5.2 (per architecture.md project tree FR reference) to detect mcp SDK major-version bumps that could break this coupling. Recommend filing an upstream issue with mcp asking for a stable observer hook on `FastMCP`.
>
> For stdio MCP servers the library spawns, observation requires a wrapper script that injects the observer at subprocess bootstrap (the `subprocess_observer_wrapper.py` pattern from this spike). For genuinely third-party stdio MCP binaries (which the library cannot wrap), the observer is structurally blind and the run degrades to `external_mixed`. Adapters MUST detect external/uninstrumented MCP configurations and signal via `observer.mark_external_mixed(reason)`.

**Amend the Alternatives section** to elaborate:

> *Custom Server subclass with protocol-layer re-implementation* — rejected as 10×–100× the implementation cost. *Wrapping the underlying transport streams* — rejected because tool-call semantics live above JSON-RPC and would require byte-level parsing. *Module-level monkey-patch of `Server.call_tool`* — rejected because it pollutes global state and breaks users who construct servers elsewhere. *Cooperating-subprocess-server-at-source instrumentation* (the original spike approach) — rejected post-review because it's not actually the handler-wrap pattern, just printf-debugging. The chosen path (handler-wrapping via `request_handlers` dict mutation, applied via wrapper-script injection for subprocesses) is a "third option" not enumerated in the original ADR.

---

## §Related ADR-A6 amendment (D1 trust-floor + D4 adapter contract — handed off to Story 0.3)

**Amend ADR-A6 (→ ADR-016) Decision section:**

> **Decision (amended 2026-05-17 with empirical findings from Story 0.1, D1 trust-floor ratified):** `mcp_coverage` reports the **strongest** observation path that fired completely during the run, ordered (strongest to weakest): `hosted_in_process` > `subprocess_with_observer` > `external_mixed`. Coverage degrades to `external_mixed` ONLY on explicit path failure: (a) the adapter calls `observer.mark_external_mixed(reason)` to signal uninstrumented MCP usage, (b) no instrumented servers were attached during the run, or (c) a subprocess observer's persisted trace log is missing or corrupt (e.g., the subprocess crashed mid-write). A run that successfully observed BOTH `hosted_in_process` AND `subprocess_with_observer` reports `hosted_in_process` — a more-instrumented run gets credit for being more-instrumented. Multiple `mark_external_mixed(reason)` calls accumulate reasons in the run's metadata (no overwrite — forensic trail is preserved).
>
> **Adapter contract (D4 ratified 2026-05-17):** The observer is structurally blind to MCP servers it did NOT attach to. External-MCP detection is the **adapter's** responsibility, not the observer's. Adapters MUST implement detection per their CLI's config conventions:
> - **Claude Code CLI adapter** (Story 4.2): parse `~/.claude.json` + project-local `.mcp.json` before run; call `observer.mark_external_mixed(reason)` when ANY external MCP is detected, regardless of whether the agent actually used it (per ADR-A6's "safer than `library_only` default — false positives violate AC-MCP-OBSERVE-01").
> - **Copilot CLI adapter** (Story 11.2 Phase 2): parse `~/.copilot/mcp-config.json` similarly.
> - **Generic LiteLLM adapter** (Story 4.1): emit no signal — LiteLLM doesn't speak MCP, so the field is trivially `hosted_in_process` if the library spawned an MCP for the test, else `external_mixed` if no library-spawned MCP exists.

**Amend ADR-A6 Consequences:**

> The kernel-level enforcement at metric keyword entry point (`_kernel/coverage.py::_check_mcp_coverage(run)`) MUST raise `IncompleteTraceError` per FR37 when `mcp_coverage == "external_mixed"` AND `allow_external_mcp_blind=False`. The default-deny posture preserves "loud refusal beats silent half-truth."
>
> The `observed_paths` field in `AgentRunResult.metadata` MUST be ordered strongest-to-weakest (matching the trust ordering) so downstream consumers can reconstruct the decision without rerunning the logic.

---

## §Time-box check (AC-0.1.4)

- **Story budget:** 5 days (architect calendar time)
- **Actual spike execution time:** ~3h cumulative (initial 2h LLM session + 1h post-review rework for D1+D2+D3+P-fixes)
- **Honest framing:** Compressed technical execution; lacks the breadth a human architect would explore (independent reproduction, weeks of edge-case curiosity, deeper SDK-internals dive, macOS testing, upstream-issue conversation, real mcp version matrix testing). **D5 review decision: Story 0.3 BLOCKED until independent reproduction lands.** That reproduction IS the "5 days of architect time" — outsourced to the architect or a different reviewer who reproduces the smoke loop + edge cases + ratifies the verdict on the basis of their own evidence.

---

## §Hand-off to Story 0.3 (AC-0.1.5)

**Verdict:** `AMEND-ADR-007` — amendment text drafted inline above (§Verdict).
**Co-verdict:** `AMEND-ADR-A6` — amendment text drafted inline above (§Related ADR-A6 amendment), including D1 trust-floor semantic + D4 adapter contract.
**No findings for ADR-A8** — sandbox policy unaffected by hosted-MCP observation. Story 0.3 can ratify ADR-A8 (→ ADR-018) without spike-driven amendments. (Story 0.2's findings may add ADR-A8 deltas independently.)

**Preconditions for Story 0.3:**

| Precondition | Status |
|---|---|
| Findings document exists at `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` | ✅ this file |
| Recommendation is one of {KEEP, AMEND, REPLACE} | ✅ AMEND |
| Amendment text drafted inline | ✅ §Verdict + §Related |
| Code review of spike completed | ✅ 2026-05-17, 5 decisions + 12 patches resolved |
| **D5 independent reproduction completed** | ❌ **BLOCKER** — Story 0.3 cannot proceed until landed |
| macOS validation | ⏸️ Phase-1 carry-over (Story 9.x) |
| Reproduction commands documented | ✅ §Concurrency probe + README.md |
| Spike deferred-work captured | ✅ `_bmad-output/implementation-artifacts/deferred-work.md` |

---

## §Reproducibility appendix

See `_bmad-output/spikes/0-1-hosted-mcp-observer/README.md` for the canonical commands. Key entry points:

- `run_dual_transport_probe.py` — single in-memory + stdio probe
- `run_streamable_http_probe.py` — single streamable HTTP probe
- `edge_cases/external_mixed_cases.py` — 5 edge-case probes
- `run_smoke_loop.sh` — 5-iteration pabot smoke loop with per-iter evidence preserved

Outputs:
- `measurements/dual_transport.jsonl`, `measurements/streamable_http.jsonl`, `measurements/edge_cases.jsonl`, `measurements/smoke_loop.txt`
- `concurrency/pabot_evidence/iter_{1..5}/` — per-iter pabot JSONL + output.xml + stdout.log

### Discard policy

This entire spike directory is **scratch**. Story 0.3 ratifies the ADRs; Epic 5 Story 5.2 implements the production observer at `src/AgentEval/mcp/observer.py`. The spike directory can be removed once Story 5.2 is done and its tests pass against the ratified ADRs. The findings document at `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` is retained as historical evidence (per architecture.md decision-record discipline).
