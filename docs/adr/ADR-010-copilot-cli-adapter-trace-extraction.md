# ADR-010: Copilot CLI Adapter — Trace Extraction Strategy

**Status:** accepted
**Date:** 2026-05-17
**Renumbering history:** Originally proposed as ADR-013 in `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` §ADR-013. Renumbered to ADR-010 per architecture.md project tree (L429-434, Hybrid scheme).

## Context

GitHub Copilot CLI (verified empirically at v1.0.9 on the maintainer's system, 2026-05-16) supports two trace-extraction surfaces:

- **Live JSONL streaming via `-p` (programmatic mode) + `--output-format=json`** — events stream to stdout as they happen during the agent run.
- **Post-hoc session-state inspection** — every run writes its event stream to `~/.copilot/session-state/{uuid}/events.jsonl` after completion; the file survives subprocess death.

Choosing one or the other is a trade-off:

- Live streaming gives lower latency, `sequence_index` ordering for free, and the ability to observe mid-run progress. But it loses everything if the live stream is interrupted (e.g., subprocess SIGKILL'd before flushing).
- Post-hoc reads add resilience (session-state survives any subprocess fate) but pay 100-500ms read latency per run and can't observe mid-run state.

This ADR governs the adapter implementation for Copilot CLI specifically; the higher-level CLI adapter base class (`SubprocessAdapter`, ADR-003) handles the generic subprocess lifecycle.

## Decision

The Copilot CLI adapter uses **live JSONL streaming as the primary extraction path** and **post-hoc session-state as fallback**:

- **Primary path (live):** `_spawn` launches `copilot -p "<prompt>" --output-format=json`. `_parse_event` parses each stdout line as a JSONL event into the adapter's intermediate event type. `_finalize` folds the event stream into `AgentRunResult`.
- **Fallback path (post-hoc):** when the live stream ends without a terminal event OR `_finalize` detects the subprocess exited non-zero, the adapter reads `~/.copilot/session-state/{run_uuid}/events.jsonl` and merges any events the live stream missed. The `run_uuid` is captured from the subprocess startup banner (Copilot CLI prints it as the first line of session-init output).

The adapter pins the supported Copilot CLI version range explicitly in `pyproject.toml` as `copilot>=1.0.9,<2.0` (added to the project's `[copilot]` extras). The lower bound (1.0.9) is the empirically-verified version; the upper bound is the major-version pin until the schema's stability over a major-version boundary is proven.

The events.jsonl schema is tracked as a pinned external-spec target in `docs/contracts/external-specs.md` Domain Constraints §2 (alongside MCP spec version, Claude Code CLI stream-json schema, etc.).

## Consequences

- Adapter ships with both code paths in Phase 2 (Tier-1 promotion target). Conformance fixture (per ADR-005) covers truncation recovery via the post-hoc path: the mock harness kills the subprocess mid-run; the adapter must produce the same `AgentRunResult` as the un-killed run via session-state fallback.
- Pin `copilot>=1.0.9,<2.0` until schema-stability evidence accumulates across a major-version boundary.
- The `run_uuid` capture is a hard dependency on Copilot CLI's startup-banner format. If the banner format changes (e.g., `run_uuid` moves to a different position), the adapter detects the failure (no `run_uuid` parsed) and degrades to "live-only" mode with a documented log warning.
- Generic LiteLLM-backed adapter (ADR-013) doesn't apply this strategy — it's SDK-driven, not subprocess-driven; trace extraction is the in-process API response.

## Alternatives

- **Post-hoc only (no live streaming)** — rejected. Adds 100-500ms read latency per run; loses the ability to observe mid-run progress for `Trajectory.` keywords that want streaming feedback.
- **Live stream only (no post-hoc fallback)** — rejected. Loses crashed-run recovery. Live stream sometimes ends incomplete on subprocess kill (the in-flight JSONL line gets cut at the kernel level).
- **Plain-text log parsing (`~/.copilot/logs/process-*.log`)** — rejected. Process logs are lifecycle events (subprocess started, subprocess exited), not tool calls. Brittle and structurally wrong for trace extraction.

## References

- PRD §`Adapter-Specific Implementation Notes` (sidecar source, 2026-05-15)
- ADR-003 (CodingAgentAdapter Protocol Internal Class Split) — `SubprocessAdapter` base class this adapter inherits from
- ADR-005 (Conformance Suite Fidelity Oracles) — truncation-recovery scenarios test the fallback path
- ADR-006 (AgentRunResult.metadata.completeness) — adapter populates `"truncated"` when the fallback path detects subprocess died mid-run
- Domain Constraints §2 (`docs/contracts/external-specs.md` — to be authored by Story 1a.4) tracks `copilot` CLI version + events.jsonl schema as pinned external-spec targets
