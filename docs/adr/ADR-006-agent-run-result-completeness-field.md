# ADR-006: `AgentRunResult.metadata.completeness` Field Required

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-009 in `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` §ADR-009. Renumbered to ADR-006 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

A CLI-driven coding-agent subprocess can exit non-zero mid-stream with truncated output: timeout-killed, OOM-killed, network drop, panic. An adapter that doesn't surface the truncation returns a structurally-valid `AgentRunResult` with silently-missing data — users see a "successful" run with a few tool calls and assume the test passed, when actually the agent never reached its terminal state.

This is the same failure mode addressed by ADR-007 (`mcp_coverage`) for MCP-side blindness: silent partial truth is a worse failure mode than loud refusal. The library's "honest-by-construction" posture (AC-SIMPLICITY-01) requires that every `AgentRunResult` carry an explicit completeness signal.

## Decision

`AgentRunResult.metadata.completeness: Literal["complete", "truncated", "partial"]` is **required** — every adapter MUST populate it. Semantics:

- **`"complete"`** — the adapter observed the agent's terminal event AND the subprocess (if any) exited 0 OR the SDK call returned successfully.
- **`"truncated"`** — the adapter observed a non-terminal final event before subprocess exit OR the subprocess exited non-zero before reaching a terminal event. The trace contains events up to truncation but is known incomplete.
- **`"partial"`** — the event stream is missing a terminal event but the subprocess exited 0 (i.e., the stream parser couldn't reach a terminal marker even though the subprocess thinks it succeeded). Indicates parser/schema drift; trace is suspect.

Adapter implementations populate the field per their event source:

- **Claude Code CLI adapter:** subprocess exit non-zero + non-terminal `stream-json` event → `"truncated"`. Missing terminal event with exit 0 → `"partial"`.
- **Generic LiteLLM adapter:** API error or HTTP timeout → `"truncated"`. Successful API response → `"complete"`.
- **Copilot CLI adapter:** missing terminal event in `events.jsonl` → `"partial"`. Subprocess exit non-zero with non-terminal events → `"truncated"`.

The conformance suite (ADR-005) injects truncation scenarios (e.g., kills the mock subprocess mid-run after 2 of 3 expected tool calls) and asserts the adapter reports `"truncated"` — adapters that silently report `"complete"` under injected truncation fail the suite.

## Consequences

- Every adapter authored from Phase 1 onward must implement truncation detection appropriate to its event source. Documented in `docs/contributor-api.md` as part of the `SubprocessAdapter` contract (ADR-003).
- `metadata.completeness` is a strict-match field in golden-trace fixtures (per ADR-005) — fidelity oracles assert the exact value.
- Consumers can branch on `completeness` in their RF test logic: e.g., assert `metadata.completeness == "complete"` before running tool-call-count assertions, since a truncated trace's metric values are unreliable.
- The 3-value enum (rather than 2-value boolean) lets users distinguish "subprocess died early" from "stream parser couldn't find a terminal marker" — these have different remediation paths.

## Alternatives

- **Optional metadata field** — rejected. Defeats the purpose. Adapter authors won't populate optional fields; downstream consumers can't rely on a field that might be missing.
- **Library infers completeness from trace shape** — rejected. False negatives: a well-formed empty trace (agent did nothing because the prompt was nonsense) looks "complete" to the library but is meaningfully empty.
- **Boolean (`complete: bool`)** — rejected. Loses the `"truncated"` vs `"partial"` distinction; these have different operational meanings (one indicates infrastructure problems, the other indicates parser drift).

## References

- PRD §`AgentRunResult Schema` + AC-SIMPLICITY-01 (sidecar source, 2026-05-15)
- ADR-003 (CodingAgentAdapter Protocol Internal Class Split) — `SubprocessAdapter._finalize` owns truncation detection per subclass
- ADR-005 (Conformance Suite Fidelity Oracles) — truncation-injection scenarios test this field
- ADR-007 (mcp_coverage Field) — parallel honesty field for MCP-side blindness
