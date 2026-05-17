---
title: "ADR Backlog Seeded from PRD"
source: "_bmad-output/planning-artifacts/prd.md"
created: "2026-05-16"
status: "seeds — to be ratified at Phase 1 close"
intent: |
  Architectural decisions surfaced during PRD authoring (steps 1–8 + party-mode + elicitation rounds).
  Each entry is a SEED — context, decision, rationale, alternatives rejected, consequences — sufficient
  for the architecture step (bmad-create-architecture) to ingest. Final ratified ADRs live in
  `docs/adr/` with formal numbering once Phase 1 implementation begins. Numbering here (ADR-005..014)
  reserves the IDs; ADR-001..004 are informed by patterns reviewed in `robotframework-agentguard`
  among other references (DynamicCore composition, AssertionEngine adoption, polling ban on
  Tier-2/3, `validate` operator disabled by default) — agenteval evaluates each on merit and
  is free to diverge.
informed_by_agentguard_among_others:
  - ADR-001: DynamicCore composition with bounded sub-libraries (lazy-loaded)
  - ADR-002: AssertionEngine adoption for getter+matcher idiom
  - ADR-003: Polling ban on Tier-2/Tier-3 keywords (raises PollingDisallowedError)
  - ADR-004: `validate` operator disabled by default (eval() security gate)
---

# ADR Backlog Seeded from PRD

Ten new ADRs proposed from PRD work. All status: **Proposed (to be ratified at Phase 1 close)**. Date: 2026-05-16.

---

## ADR-005: Tier-1 Adapter Ceiling Rule

**Context.** Solo + AI-agent-assisted maintainership caps long-term CI/test-matrix capacity. Adding adapters has marginal cost (CI cells, version pins, log-format regression risk). Adding *too few* loses real users; adding *too many* makes the eval framework an adapter-maintenance project.

**Decision.** Tier-1 adapter ceiling is **"≤2 adapters per vendor + 1 generic escape hatch"** — not an absolute number.

**Rationale.** Number-based caps are intuition-laundering and don't scale gracefully when a new vendor emerges. The per-vendor rule is principled: it lets Anthropic / OpenAI / GitHub / future vendors each get a CLI adapter + SDK adapter without arbitrary ceiling debates, while the "+1 universal" keeps the LiteLLM-backed Generic as the catch-all.

**Alternatives rejected.**
- *Hard cap at 5 adapters total* — would have arbitrarily excluded a future Mistral/xAI/Anthropic-V2 entrant; cap as principle generalizes.
- *No cap, accept all 1st-party contributions* — death spiral for solo maintainership.
- *One adapter per vendor* — loses CLI/SDK split that's already real (Claude Code CLI vs Claude Agent SDK are genuinely different).

**Consequences.** Tier-1 ceiling extends to 7 if a third vendor enters (currently 3 vendors → 6 actual). New vendor entries require explicit Tier-1 promotion via ADR; community Tier-2 is the default home for new agents.

---

## ADR-006: CodingAgentAdapter Protocol — Internal Class Split

**Context.** SDK-driven adapters (Claude Agent SDK, OpenAI Agents SDK, Generic) and CLI-driven adapters (Claude Code CLI, Codex CLI, Copilot CLI) have fundamentally different machinery: in-process vs subprocess, structured-object traces vs JSONL parsing, full-fidelity vs opportunistic field population.

**Decision.** Single public `CodingAgentAdapter` Protocol (contract at the boundary). Internal base classes: `InProcessAdapter` (full-fidelity defaults) + `SubprocessAdapter(ABC)` with hooks `_spawn`, `_parse_event`, `_finalize` (CLI machinery).

**Rationale.** Preserves callers' invocation symmetry while letting implementers reuse the right base for their adapter style. Two CLI adapter contributors don't reinvent subprocess lifecycle / JSONL parsing / timeout handling.

**Alternatives rejected.**
- *Two public Protocols (`SDKAgentAdapter` + `CLIAgentAdapter`)* — caller has to branch on adapter type; complicates `coding_agent=` library arg.
- *Single Protocol, no internal classes* — every CLI adapter reinvents subprocess lifecycle (~500 LoC each).

**Consequences.** Library publishes `SubprocessAdapter` as part of the contributor-facing API (Phase 1 deliverable). Internal class split is implementation detail; Protocol is the contract.

---

## ADR-007: Hosted-MCP Universal Trace Observation Pattern

> **⚠️ HISTORICAL — superseded by ratified text.** This proposed text was ratified into `docs/adr/ADR-004-hosted-mcp-observation.md` on 2026-05-17 with empirical amendments from Story 0.1 spike. The text below is the original 2026-05-15 draft kept for traceability; see ADR-004 for the authoritative ratified version.

**Context.** Trace fidelity varies wildly across adapters: SDKs give structured traces, CLIs vary, TUI-first agents (OpenCode) give none. The "agent-agnostic" claim collapses without a per-agent guarantee mechanism.

**Decision.** When the library spawns the MCP server the agent connects to, it records every `tools/call` server-side regardless of which agent invoked it. This is the universal trace fallback; adapter-side extraction is supplementary (gives prompt/response context; MCP side gives tool-call truth).

**Rationale.** Tool calls flowing through a library-controlled MCP boundary are observable independently of the agent runtime. Makes "agent-agnostic" structurally true for any MCP-supporting agent.

**Alternatives rejected.**
- *Require adapter-side trace extraction for all agents* — disqualifies TUI-first agents and any future agent without structured output.
- *Wrap agent stdout with universal log parser* — log formats are too varied; brittle.
- *Hook into agent telemetry exporters (OTel)* — requires every agent to emit OTel; very few do.

**Consequences.** Library hosts MCP servers per-RF-test (see ADR-012). Agents that use external MCP servers the library doesn't spawn produce `mcp_coverage="external_mixed"` (see ADR-010). Pi and any non-MCP agent does not benefit from this fallback.

---

## ADR-008: Conformance Suite Includes Fidelity Oracles

**Context.** A conformance suite that asserts only structural shape (e.g., "ToolCallTrace has `latency_ms: float`") can be passed by an adapter emitting nonsense data (all-zero latency, hallucinated sequence_index, fake source attribution). Structural conformance ≠ trace fidelity.

**Decision.** Conformance suite includes **golden-trace fixtures** — JSON files recorded from deterministic mock agent runs against a fixed scenario. Each adapter under test must produce output matching the golden fixture's structure AND values, with documented allowable variations (e.g., `latency_ms > 0` rather than exact).

**Rationale.** Honest community-adapter contributions are the goal; the suite must defend against well-meaning-but-broken AND adversarially-passing adapters. Golden traces are the executable spec.

**Alternatives rejected.**
- *Structural conformance only* — original draft; critical hole.
- *Property-based testing (Hypothesis)* — better at finding edge cases but worse at verifying "did you implement the documented behavior."
- *Manual review per adapter* — doesn't scale beyond Tier 1.

**Consequences.** Mock agent + fixed scenario fixtures must ship Phase 1. Adding a new Tier-1 adapter requires authoring its golden fixture. Community adapters get the fixture format published as part of the conformance suite release.

---

## ADR-009: `AgentRunResult.metadata.completeness` Field Required

**Context.** A CLI subprocess can exit non-zero mid-stream with truncated output. Adapter that doesn't surface this returns a structurally-valid `AgentRunResult` with silently-missing data; users assume the test passed.

**Decision.** `AgentRunResult.metadata.completeness: Literal["complete", "truncated", "partial"]` is **required**. Adapters MUST emit `truncated` when the agent exits non-zero mid-stream OR when their event parser fails to reach a terminal event. Conformance suite injects truncation (e.g., kills mock subprocess mid-run) and asserts the adapter reports it.

**Rationale.** Honest-by-construction is the AC-SIMPLICITY-01 philosophy applied to metadata. Silent partial traces are a worse failure mode than loud truncation.

**Alternatives rejected.**
- *Optional metadata field* — defeats the purpose; adapter authors won't populate it.
- *Library infers completeness from trace shape* — false negatives (well-formed empty traces look complete).

**Consequences.** Every adapter Phase 1+ must implement truncation detection appropriate to its event source. CC CLI: non-zero exit + non-terminal stream-json event = truncated. Generic LiteLLM: API error or HTTP timeout = truncated. Copilot CLI: missing terminal event in events.jsonl = partial.

---

## ADR-010: `AgentRunResult.metadata.mcp_coverage` + `IncompleteTraceError`

**Context.** When an agent connects to BOTH library-hosted MCP servers AND external ones (e.g., `~/.claude.json`-registered servers Claude Code reads, or the user's `~/.copilot/mcp-config.json`), the library only observes the hosted half. Tool-call truth via hosted-MCP becomes partial; metric keywords that report on tool-call counts can silently understate.

**Decision.** Every `AgentRunResult` from a keyword using `mcp_servers=` populates `metadata.mcp_coverage: Literal["complete", "library_only", "external_mixed", "no_mcp"]`. Metric keywords (`Get Tool Call Count`, `Get Tool Hit Rate`, etc.) raise `IncompleteTraceError` on `external_mixed` unless user opts in via `allow_external_mcp_blind=True`.

**Rationale.** "Loud refusal" beats "silent half-truth." User who explicitly accepts the blindness keeps shipping; user who doesn't know it's happening gets stopped before the test passes wrongly.

**Alternatives rejected.**
- *Always merge external MCP traces opportunistically* — most agents don't expose external MCP traffic.
- *Warning instead of error* — warnings get filtered out in CI; loud failure is the only honest gate.
- *Library blocks `mcp_servers=` calls when external MCP is detected* — too aggressive; users running CC with their own `.mcp.json` are common.

**Consequences.** Adapter implementations must detect "external MCP in play" — for CC CLI: parse `~/.claude.json` + project `.mcp.json` before run. For Copilot CLI: parse `~/.copilot/mcp-config.json`. Detection-failure default is `external_mixed` (safer than `library_only`).

---

## ADR-011: MCP Spec Version Validation

**Context.** MCP spec evolves (Tasks primitive incoming, SSE deprecated). Library's MCP observer parses `tools/call` JSON-RPC requests. If the spec changes the field/method name, the observer returns empty `tool_calls` lists — conformance suite passes the empty shape; users get nonsense traces.

**Decision.** MCP observer validates the negotiated MCP spec version at session start. If outside `mcp>=1.0,<2.0`, observer raises `UnsupportedMCPVersionError`. Conformance suite injects a future-spec mock server to verify the gate fires.

**Rationale.** Same "loud refusal beats silent half-truth" principle as ADR-010. MCP spec drift is a high-likelihood risk per the existing risk register.

**Alternatives rejected.**
- *Best-effort parse with warnings* — warnings ignored in CI.
- *Library tracks MCP spec via online registry* — adds network dep + spec-fetch failure mode.
- *Pin MCP SDK and let SDK enforce* — SDK may accept future versions while the observer logic doesn't.

**Consequences.** Each library release pins the supported MCP spec version range. Users on cutting-edge MCP servers get a clear error pointing to a library upgrade path. ADR is a forcing function for keeping the library current with MCP spec.

---

## ADR-012: Per-Test MCP Server Scope (Listener v3 `test_id`)

**Context.** Under `pabot` (parallel RF execution), two tests using the same library-hosted MCP server interleave `tools/call` traces server-side. Both tests' `mcp_coverage="library_only"` claims become wrong — the server-side trace is polluted.

**Decision.** MCP observer scopes traces per-RF-test by reading the Listener v3 `test_id` from RF context. Each test gets a unique library-hosted MCP server instance by default. Library `__init__(mcp_per_test=False)` opts out for users who explicitly want shared instances; documented trade-off.

**Rationale.** Per-test isolation is the only correctness guarantee under parallel execution. Shared servers are an optimization that loses correctness — only acceptable when the user explicitly chooses it.

**Alternatives rejected.**
- *Shared MCP server per suite* — pabot runs at suite level too; same pollution.
- *Trace tagging with test_id, single shared server* — works in theory; brittle under server crashes (one bad test poisons others).
- *Block pabot entirely* — breaks legitimate parallel-test workflows.

**Consequences.** MCP server startup is per-test → adds startup latency (~100-500ms per test depending on server). Acceptable for Tier 1/2 (rarely parallelized); Tier 3 (heavily parallelized via Pass@k) should consider `mcp_per_test=False` with documented pollution caveat.

---

## ADR-013: Copilot CLI Adapter — Trace Extraction Strategy

**Context.** Copilot CLI (v1.0.9 verified empirically on the maintainer's system, 2026-05-16) supports both live JSONL streaming (`-p` programmatic mode + `--output-format=json`) and post-hoc session inspection (`~/.copilot/session-state/{uuid}/events.jsonl`). Choosing one impacts trace fidelity and adapter complexity.

**Decision.** Adapter uses **live JSONL streaming as primary** (lower latency, no post-hoc file-read race conditions) and **post-hoc session-state as fallback** (when live stream is truncated or the adapter cannot reach the live stream).

**Rationale.** Live streaming gives sequence_index ordering for free. Post-hoc reads add resilience for crashed runs (session-state survives subprocess death). Best-of-both costs little extra adapter complexity since both speak JSONL.

**Alternatives rejected.**
- *Post-hoc only* — adds 100-500ms read latency per run; can't observe mid-run progress.
- *Live stream only* — loses crashed-run recovery; live stream sometimes incomplete on subprocess kill.
- *Plain-text log parsing (`~/.copilot/logs/process-*.log`)* — logs are lifecycle events, not tool calls; brittle.

**Consequences.** Adapter ships with both code paths Phase 2; conformance fixture covers truncation recovery via post-hoc. Pin `copilot` CLI version range (`>=1.0.9,<2.0` until schema stability is proven). Track Copilot's events.jsonl schema as a pinned external-spec target in Domain Constraints §2.

---

## ADR-014: Three-Persona Model + Persona-Split Test

**Context.** Brief named QA engineers as primary. Elicitation pre-mortem collapsed personas to 2 (QA Engineer + Agent Developer with 3 modes). Mary's party-mode directive re-split to 3 (added Agent Surface Author). Without a rule, future persona decisions are vote-driven.

**Decision.** Three primary personas: **QA Engineer** (evaluates pre-existing agents), **Agent Surface Author** (ships skills + MCP servers + prompts INTO pre-built coding agents), **Agent Developer** (builds multi-step agent orchestrations from scratch). **Persona-split test:** a persona splits when downstream artifacts (epics, stories, capability surfaces) require *different capabilities* — not when *different people* happen to use *different tools*.

**Rationale.** Capability-surface-driven splits scale; tool-driven splits inflate persona count without product value. The 3-way split survives the test: `Skill.` + `MCP.` keywords (Surface Author) vs. `Run Scenario` + `Trajectory.` (Agent Developer) are genuinely different downstream artifacts.

**Alternatives rejected.**
- *Two personas (post-elicitation-collapse state)* — loses the "consumes pre-built agent vs builds new agent" distinction; epics for Surface Author keyword surface get conflated with multi-step orchestration epics.
- *Four personas (brief's original)* — fails the persona-split test for Skill/MCP/Multi-step (the modes share enough downstream artifacts that 3 collapses cleanly).

**Consequences.** Future persona proposals must justify against the split test in ADR form. Reverses part of the elicitation pre-mortem's "persona inflation correction" — annotated in frontmatter as a refinement (Mary's directive added new information about CLI agents that the pre-mortem didn't consider).

---

# Cross-cutting notes for the architecture step

- **All 10 ADRs touch the `CodingAgentAdapter` + `_assertions/` + `telemetry/mcp_observer/` surfaces.** No ADR isolates cleanly to one sub-library; expect cross-cutting code in `_assertions/`, `telemetry/`, `coding_agent/`, and `mcp/` for ADR-007 through ADR-012.
- **`SubprocessAdapter` ABC (ADR-006) is part of the contributor-facing public API** — must be in `docs/keywords/` libdoc OR in a separate `docs/contributor-api.md`. Phase 1 deliverable.
- **Conformance suite (ADR-008) ships in Phase 1 as contract publication**, even though only 2 adapters exist. Phase 2 adds 4 more adapters; the suite's value compounds.
- **Five new acceptance criteria** map 1:1 to ADRs 008–012: AC-CONFORMANCE-01 (ADR-008), AC-CONFORMANCE-02 (ADR-009), AC-MCP-OBSERVE-01 (ADR-010), AC-MCP-OBSERVE-02 (ADR-011), AC-MCP-OBSERVE-03 (ADR-012). Architecture step should keep AC ↔ ADR symmetric.
- **ADR-001 through ADR-004 are informed by patterns reviewed in robotframework-agentguard among other references**; the architecture step should author them in this library's `docs/adr/` evaluated on merit for agenteval, with cross-reference to agentguard where the pattern was borrowed but free to diverge.

# What this backlog REVEALED that the prior PRD critique missed

1. **Adapter cap rule is principle-based, not number-based** (ADR-005 rationale) — the "5" was an instantiation; the rule is "≤2 per vendor + 1."
2. **`SubprocessAdapter` is contributor-facing API** (ADR-006 consequences) — not just internal scaffolding. Community CLI adapter authors should reuse it.
3. **External MCP detection-failure default must be `external_mixed`** (ADR-010 alternatives) — safer than `library_only`. Adapter that can't tell what's in play should refuse to claim full coverage.
4. **Per-test MCP server startup latency is real** (ADR-012 consequences) — 100-500ms per test. Tier-3 statistical re-runs (`Run N Times 10`) compound this. Documented trade-off for users who choose `mcp_per_test=False`.
5. **Pin Copilot CLI version range explicitly** (ADR-013 consequences) — `>=1.0.9,<2.0`. Add to Domain Constraints §2 as another pinned external-spec target.
6. **Future persona proposals require ADR justification** (ADR-014 consequences) — the split-test rule needs to be enforceable, not advisory.
