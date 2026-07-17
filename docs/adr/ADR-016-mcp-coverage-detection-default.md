# ADR-016: MCP Coverage Detection Default — Trust-Floor

**Status:** accepted
**Date:** 2026-05-17

> Superseded by the four-surface refocus (2026-07) where the details drifted. The
> trust-floor rule — report the strongest observation path that fired, degrade
> loudly to `external_mixed` when the observer is blind — is still how MCPLibrary
> reports coverage. What's gone: the fleet of vendor CLI adapters (Claude Code,
> Copilot, Codex, Generic LiteLLM) that used to each own a slice of detection.
> That responsibility now sits with MCPLibrary and the single coding-agent driver,
> not a per-vendor split.

## Context

`mcp_coverage` reflects how completely agenteval observed a run's tool calls. It takes values in the literal set `{"hosted_in_process", "subprocess_with_observer", "external_mixed"}`. Deciding which one to report means knowing whether the run touched agenteval-spawned MCP servers or external ones — and detection can fail (missing file, malformed JSON, permission denied, race mid-read). The safe default on detection failure is `external_mixed`: loud refusal beats a silent half-truth.

Two refinements shape the rule:

- **D1 (trust-floor):** When BOTH `hosted_in_process` AND `subprocess_with_observer` paths fire successfully, the coverage field reports the STRONGER path that completed fully, not the weaker one. A more-instrumented run should get credit for being more-instrumented.
- **D4 (detection is the caller's job, not the observer's):** The observer is structurally blind to MCP servers it did NOT attach to. Only the caller that configured those external servers can detect them and signal degradation via `mark_external_mixed(reason)`.

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

**Detection is the caller's job** — the observer is structurally blind to MCP servers it did NOT attach to. Whoever configured external MCP servers for a run is the only party that can detect them, and MUST call `mark_external_mixed(reason)` when any external MCP is present, regardless of whether it was actually used. Claiming full coverage without actually checking is the one unforgivable sin here: a false "all good" is worse than an honest "I couldn't see everything."

**Enforcement** at the metric-keyword entry point: coverage of `external_mixed` raises `IncompleteTraceError` when `allow_external_mcp_blind=False` (the default). The default-deny posture preserves "loud refusal beats silent half-truth."

## Consequences

- The trust-floor decision tree + the caller's detection responsibility are published in the companion contract `docs/contracts/mcp-coverage-detection.md`.
- The coverage-check helper consults the trust ordering and raises `IncompleteTraceError` on `external_mixed` unless the caller opts in via `allow_external_mcp_blind=True`.
- The `observed_paths` metadata is exposed in trust order (strongest first), not alphabetical, so downstream consumers can reconstruct the decision without rerunning the logic.

## Alternatives

- *Original ADR-A6's "library_only" value for the success state* — superseded during D1 rework: the field's strongest-coverage value was renamed from `library_only` (used in the 2026-05-15 proposed text) to `hosted_in_process` (used in this ratified version) to align with the observer-pattern terminology Story 0.1 spike validated. The semantic is unchanged: it names the case where the library itself hosted the MCP server and observed every tool call directly.
- *Default `"library_only"` (the original proposed default value) on detection failure* — rejected: silent partial truth; violates AC-MCP-OBSERVE-01's "loud refusal beats silent half-truth." The ratified default-on-failure is `external_mixed`.
- *Refuse to run on detection failure (raise `MCPCoverageDetectionError`)* — rejected: too aggressive; breaks legitimate cases where the user knows there's no external MCP (e.g., CI environments without user-level config files).
- *Three-state field (`"complete" | "library_only" | "unknown"`)* — rejected: adds complexity; defers the decision rather than making it.
- *Trust-ceiling semantic* (weakest-coverage-wins; rejected in favor of D1 trust-floor 2026-05-17) — penalizes well-instrumented runs: a run that successfully observed BOTH paths would report the WEAKER path, even though both fired completely. Trust-floor (strongest complete path wins) is more honest about evidence quality.
- *Promote to `set[McpCoverage]`* (multi-value field) — rejected because (a) single-value semantics are clearer in metric reports, (b) trust-floor ordering captures the same information, (c) the value space is small (3 states); a flat enum is sufficient.

## References

- ADR-004 (Hosted-MCP Universal Trace Observation) — the observer whose output this field summarizes.
- ADR-014 (Error-Class Hierarchy) — the `IncompleteTraceError` leaf this gate raises.
- `docs/contracts/mcp-coverage-detection.md` — the companion contract publishing the decision tree.
