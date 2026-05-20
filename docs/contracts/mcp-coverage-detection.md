# MCP Coverage Detection

**Status:** Phase-1 ratified — Story 5.2 filled the Contract section 2026-05-20.
**Owning epic:** Epic 5 Story 5.2
**Related ADRs:** ADR-016 (MCP Coverage Detection Default — trust-floor + adapter contract), ADR-007 (mcp_coverage + IncompleteTraceError gate), ADR-004 (Hosted-MCP Universal Trace Observation)
**Related FRs:** FR36b (mcp_coverage field), FR37 (IncompleteTraceError), AC-MCP-OBSERVE-01

## Purpose

Governs the **per-adapter responsibility split** for detecting `mcp_coverage` (the 3-valued field `hosted_in_process` / `subprocess_with_observer` / `external_mixed` per ADR-016 D1 trust-floor). agenteval's hosted-MCP observer is structurally blind to MCP servers it didn't spawn; the **adapter** is the only entity that can detect external MCP configurations and signal degradation. This contract documents what each Tier-1 adapter MUST do, what the trust-floor decision tree is, and how detection failure defaults work.

## Scope

### In-scope

- The 3-valued `mcp_coverage` literal set + per-value semantics (per ADR-016 + ADR-007).
- D1 trust-floor: when BOTH `hosted_in_process` AND `subprocess_with_observer` paths fire successfully, report the STRONGER path.
- D4 per-adapter contract: which adapter parses which external-config file (Claude Code: `~/.claude.json` + `.mcp.json`; Copilot: `~/.copilot/mcp-config.json`; Generic LiteLLM: trivially `hosted_in_process`).
- Detection-failure default: `external_mixed` (safer than `hosted_in_process`).
- `IncompleteTraceError` gate behavior: when metric keywords MUST raise vs. when consumer opted out via `allow_external_mcp_blind=True`.

### Out-of-scope

- The hosted-MCP observer's internal implementation — that's `src/AgentEval/mcp/observer.py` (Epic 5 Story 5.2 lands) + ADR-004's content.
- Per-adapter test fixtures for the conformance suite — those live in `tests/conformance/fixtures/<adapter>/` per `conformance-fixture-format.md`.

## Contract

*Phase-1 ratified by Story 5.2 (2026-05-20).*

### 3-valued literal set

`AgentRunResult.metadata.mcp_coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]` per FR36b + ADR-016 D1.

| Value | Semantics |
| --- | --- |
| `hosted_in_process` | Library-hosted in-memory FastMCP/Server with `HostedMcpObserver` attached. All `tools/call` traffic was observed server-side. Strongest trust path. |
| `subprocess_with_observer` | Library-hosted stdio subprocess MCP server with `HostedMcpObserver` injected at subprocess bootstrap via `_observer_subprocess_wrapper.py` (ADR-004 §Consequences). Traces serialized as JSONL by the subprocess + grafted by the parent. |
| `external_mixed` | Either (a) adapter signaled external MCP configs are present (e.g., Claude Code CLI detected `~/.claude.json` or a caller-provided `.mcp.json`), OR (b) the observer is structurally blind to the run (no library-hosted servers attached + no subprocess wrapper). Library refuses to claim trace truth. |

### D1 trust-floor decision tree

`HostedMcpObserver.compute_coverage()` resolves per the following rules (in priority order):

1. **If ANY `mark_external_mixed(reason)` was called** → `"external_mixed"`. Adapter-signaled external presence wins because the observer is structurally blind to external servers; degrading to `"external_mixed"` is the honest answer.
2. **Else, if `"hosted_in_process"` was observed** → `"hosted_in_process"`. Strongest-complete-path wins when multiple instrumented paths fired.
3. **Else, if `"subprocess_with_observer"` was observed** → `"subprocess_with_observer"`.
4. **Else** → `"external_mixed"` (**detection-failure default** per ADR-016 D1).

### D4 per-adapter detection-responsibility table

| Adapter | External-config detection | Default `compute_coverage()` outcome |
| --- | --- | --- |
| **Generic LiteLLM (Story 4.1)** | None — the library spawns + observes every MCP server in-process. Adapter does NOT call `mark_external_mixed()` unless the caller explicitly passes an external server reference. | `hosted_in_process` when `mcp_servers=` is passed; `external_mixed` (detection-failure default) when `mcp_servers=None` and the run claims to use MCP. |
| **Claude Code CLI (Story 4.2)** | Parses `~/.claude.json` + the temp `.mcp.json` written for the subprocess. When external configs (anything NOT pointing at a library-spawned server) are present, adapter calls `observer.mark_external_mixed("Claude Code CLI detected external MCP config at <path>")`. | `subprocess_with_observer` when ONLY library-hosted servers are configured + the subprocess wrapper attached the observer; `external_mixed` when external configs detected. |
| **Copilot CLI (Phase-2)** | Parses `~/.copilot/mcp-config.json`. Same `mark_external_mixed()` pattern as Claude Code CLI. | Phase-2 placeholder; matches Claude Code CLI semantics. |
| **Codex CLI (Phase-2)** | Parses Codex CLI's MCP config (location TBD by Story 11.x). | Phase-2 placeholder. |

Custom community adapters MUST document their external-detection responsibility in their adapter's docstring + register a conformance-suite fixture covering each `mcp_coverage` outcome per ADR-005.

### `IncompleteTraceError` raise gate

Per FR37 + `_kernel/coverage._check_mcp_coverage` (shipped Story 1b.2): when a metric keyword is called against an `AgentRunResult` with `metadata.mcp_coverage == "external_mixed"`:

- **`allow_external_mcp_blind=False`** (default per PRD FR42) → raises `IncompleteTraceError` with the canonical message:
  > "metric keyword <name> called on AgentRunResult with mcp_coverage=external_mixed; opt in via allow_external_mcp_blind=True or ensure all MCP traffic flows through library-hosted servers"
- **`allow_external_mcp_blind=True`** (opt-out) → metric keyword proceeds, returning whatever the partial trace records. Consumer accepts the honesty trade-off.

The flag flows from PRD FR41/FR42 config precedence (`init_arg → env → dotenv → default`).

### Test-injection scenarios (conformance suite per ADR-005)

Every Tier-1 adapter MUST ship `tests/conformance/fixtures/<adapter>/`:

- `echo_simple.json` — hosted-only run; expects `mcp_coverage="hosted_in_process"` (Generic) or `"subprocess_with_observer"` (Claude Code CLI).
- `echo_external_mcp.json` — adapter detects an external config; expects `mcp_coverage="external_mixed"`.
- `echo_truncated.json` — non-terminal exit; expects `completeness="truncated"` per ADR-006 + FR36a.

Story 1b.5 ships the 6-fixture set (Generic + Claude Code CLI × 3 scenarios); Story 5.2 wires the per-adapter detection so the existing fixtures produce the expected `mcp_coverage` outcomes via real adapter execution.

### Observer API surface

The `HostedMcpObserver` class at `src/AgentEval/mcp/observer.py` exposes:

- `attach(server, observation_path)` — wraps `Server.request_handlers[CallToolRequest]` per ADR-004. Idempotent on repeated attach to the same server. Emits `AdapterVersionDriftWarning` on first attach when the mcp SDK version is outside the tested range `[1.27, 2.0)`.
- `mark_external_mixed(reason)` — adapter cooperation hook per D4.
- `compute_coverage()` — D1 trust-floor resolution.
- `tool_calls()` — chronological list of observed `ToolCallTrace` records (each with `source="hosted_mcp"`).
- `external_mixed_reasons()` — chronological list of `mark_external_mixed` reasons (defensive shallow copy).
- `clear()` — per-test cleanup; called by Story 5.1's Listener at `end_test` via the `Listener.register_observer(observer)` registry.

Refer to ADR-016 for the ratified attribute-set rationale; this contract surfaces the per-adapter API for community adapter authors.

## Change Policy

This contract evolves per [`stability-surface.md`](stability-surface.md) labels. The 3-valued literal set is `stable` from Phase-1 onward; additions require major-version bump (changes the consumer-facing field type). The per-adapter detection-responsibility table is `provisional` — new adapter entries don't break consumers (an adapter can opt into the default `external_mixed` if its detection logic doesn't ship in time).

## References

- ADR-016: MCP Coverage Detection Default
- ADR-007: mcp_coverage + IncompleteTraceError
- ADR-004: Hosted-MCP Universal Trace Observation
- FR36b / FR37 / AC-MCP-OBSERVE-01 (PRD)
- Story 0.1 spike findings: `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md`
