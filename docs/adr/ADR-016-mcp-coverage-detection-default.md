# ADR-016: MCP Coverage Detection Default — Trust-Floor with Adapter Contract

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-A6 in `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` §ADR-A6. Renumbered to ADR-016 per architecture.md project tree (`docs/adr/` subsection of the Complete Project Directory Structure).

## Context

`mcp_coverage` is a per-`AgentRunResult` field reflecting how completely the library observed a run's tool calls (FR36b / AC-MCP-OBSERVE-01). It takes values in the literal set `{"hosted_in_process", "subprocess_with_observer", "external_mixed"}`. Per-adapter detection of whether the run touched library-spawned vs external MCP servers requires reading external MCP configurations:

- Claude Code CLI adapter: parse `~/.claude.json` + project `.mcp.json` before run.
- Copilot CLI adapter: parse `~/.copilot/mcp-config.json`.
- Generic LiteLLM adapter: trivially `"hosted_in_process"` (or `"external_mixed"`) since LiteLLM doesn't speak MCP.

Detection can fail (missing file, malformed JSON, permission denied, race mid-read). The original ADR-A6 (2026-05-15 draft) committed to `external_mixed` as the safe default on detection failure ("loud refusal beats silent half-truth"). Story 0.1 (Hosted-MCP Universal Observer Spike, 2026-05-17) empirically validated the field's semantics under dual-transport runs and surfaced two refinements that this ratification incorporates:

- **D1 (trust-floor):** When BOTH `hosted_in_process` AND `subprocess_with_observer` paths fire successfully, the coverage field should report the STRONGER path that completed fully, not the weaker one. A more-instrumented run should get credit for being more-instrumented.
- **D4 (adapter contract):** Detection responsibility is split — the observer is structurally blind to MCP servers it did NOT attach to; only the ADAPTER can detect external MCP configurations and signal degradation.

## Decision

`mcp_coverage` reports the **strongest** observation path that fired completely during the run, ordered (strongest to weakest):

1. `hosted_in_process` — at least one tool call observed via in-process handler-wrap on a library-spawned server.
2. `subprocess_with_observer` — at least one tool call observed via wrapper-script-injected observer in a library-spawned subprocess MCP server.
3. `external_mixed` — degraded state, see degradation rules below.

A run that successfully observed BOTH `hosted_in_process` AND `subprocess_with_observer` reports `hosted_in_process` (the strongest complete path).

**Degradation to `external_mixed`** happens ONLY on explicit path failure:

1. The adapter calls `observer.mark_external_mixed(reason)` to signal uninstrumented MCP usage.
2. No instrumented servers were attached during the run (catch-all safe default).
3. A subprocess observer's persisted trace log is missing or corrupt (e.g., the subprocess crashed mid-write).

Multiple `mark_external_mixed(reason)` calls accumulate reasons in the run's metadata (no overwrite — forensic trail is preserved). The `observed_paths` field in `AgentRunResult.metadata` MUST be ordered strongest-to-weakest (matching the trust ordering above) so downstream consumers can reconstruct the decision without rerunning the logic.

**Adapter contract** — the observer is structurally blind to MCP servers it did NOT attach to. External-MCP detection is the **adapter's** responsibility, not the observer's. Adapters MUST implement detection per their CLI's config conventions:

- **Claude Code CLI adapter** (Epic 4 Story 4.2): parse `~/.claude.json` + project-local `.mcp.json` before run; call `observer.mark_external_mixed(reason)` when ANY external MCP is detected, regardless of whether the agent actually used it. False positives (claiming full coverage when adapter couldn't actually check) violate AC-MCP-OBSERVE-01's load-bearing principle.
- **Copilot CLI adapter** (Phase 2 Story 11.2): parse `~/.copilot/mcp-config.json` similarly.
- **Generic LiteLLM adapter** (Epic 4 Story 4.1): emit no signal — LiteLLM doesn't speak MCP, so the field is trivially `hosted_in_process` if the library spawned an MCP for the test, else `external_mixed` if no library-spawned MCP exists.

**Kernel enforcement** at metric keyword entry point: `_kernel/coverage.py::_check_mcp_coverage(run)` MUST raise `IncompleteTraceError` per FR37 when `mcp_coverage == "external_mixed"` AND `allow_external_mcp_blind=False` (the default). The default-deny posture preserves "loud refusal beats silent half-truth."

**Citation:** see `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` §`mcp_coverage` field semantic + §Related ADR-A6 amendment for the trust-floor empirical validation; the D2.3 handshake-race and D2.4 atexit findings from `_bmad-output/spikes/spike-per-test-mcp-cleanup-findings.md` are consistent with this semantic.

## Consequences

- Adapter authors implement external-MCP detection per their CLI's config conventions; documentation contract `docs/contracts/mcp-coverage-detection.md` (Story 1a.4 owns the skeleton) MUST publish the trust-floor decision tree + the per-adapter detection responsibility.
- Conformance suite (Epic 1b Story 1b.5 / Epic 8a) injects detection-failure scenarios — missing `~/.claude.json` permission, corrupt subprocess log, dual-transport happy-path — and asserts the expected `mcp_coverage` outcome per the decision tree above.
- The kernel `_check_mcp_coverage` helper in `_kernel/coverage.py` (Epic 1b Story 1b.2 deliverable) MUST consult the trust ordering and raise `IncompleteTraceError` on `external_mixed` unless the caller opts in via `allow_external_mcp_blind=True`.
- The `observed_paths` ordering convention requires the production observer (Epic 5 Story 5.2) to expose this field in trust order, not alphabetical (review F-blind-14 fix already applied in spike prototype).
- Cross-cutting concern #9 from architecture's Project Context Analysis (adapter-emitted data contract). **Adds 1 new doc contract to NFR-MAINT-04's enumerated list** (`docs/contracts/mcp-coverage-detection.md`).

## Alternatives

- *Original ADR-A6's "library_only" value for the success state* — superseded during D1 rework: the field's strongest-coverage value was renamed from `library_only` (used in the 2026-05-15 proposed text) to `hosted_in_process` (used in this ratified version) to align with the observer-pattern terminology Story 0.1 spike validated. The semantic is unchanged: it names the case where the library itself hosted the MCP server and observed every tool call directly.
- *Default `"library_only"` (the original proposed default value) on detection failure* — rejected: silent partial truth; violates AC-MCP-OBSERVE-01's "loud refusal beats silent half-truth." The ratified default-on-failure is `external_mixed`.
- *Refuse to run on detection failure (raise `MCPCoverageDetectionError`)* — rejected: too aggressive; breaks legitimate cases where the user knows there's no external MCP (e.g., CI environments without user-level config files).
- *Three-state field (`"complete" | "library_only" | "unknown"`)* — rejected: adds complexity; defers the decision rather than making it.
- *Trust-ceiling semantic* (weakest-coverage-wins; rejected in favor of D1 trust-floor 2026-05-17) — penalizes well-instrumented runs: a run that successfully observed BOTH paths would report the WEAKER path, even though both fired completely. Trust-floor (strongest complete path wins) is more honest about evidence quality.
- *Promote to `set[McpCoverage]`* (multi-value field) — rejected because (a) single-value semantics are clearer in metric reports, (b) trust-floor ordering captures the same information, (c) the value space is small (3 states); a flat enum is sufficient.

## References

- Original proposed text: `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` §ADR-A6 (note: that text uses `library_only` as the success state; renamed to `hosted_in_process` per D1 rework).
- D1 trust-floor + D4 adapter contract ratification: `_bmad-output/spikes/spike-hosted-mcp-observer-findings.md` §`mcp_coverage` field semantic + §Related ADR-A6 amendment.
- Empirical validation: spike's `edge_cases/external_mixed_cases.py` 5/5 probes pass; `probe_dual_path_trust_floor` reports `hosted_in_process` when both paths fire (proves the trust-floor decision tree).
- Independent reproduction: `_bmad-output/spikes/d5-reproduction-report.md` 3/3 agents confirm 5/5 edge-case pass.
- Cross-spike confirmation: Story 0.2's per-test cleanup did NOT surface any additional ADR-A6 deltas — cross-cutting confirmation only (`spike-per-test-mcp-cleanup-findings.md` §Hand-off to Story 0.3 table row "ADR-A6 / ADR-A8 amendments needed? ✅ NO new amendments from Story 0.2").
- Architecture context: `_bmad-output/planning-artifacts/architecture.md` project-tree `docs/adr/` subsection; FR36b + AC-MCP-OBSERVE-01 in PRD.
