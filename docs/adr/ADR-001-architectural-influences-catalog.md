# ADR-001: Architectural Influences Catalog

**Status:** accepted
**Date:** 2026-05-17

> Superseded by the four-surface refocus (2026-07) where the details drifted. The
> decision that matters here is still true and still load-bearing: `robotframework-agentguard`
> and the other projects below are influences, not dependencies — agenteval credits
> them and owes them nothing. The catalog is kept as an honest record of what was
> reviewed. Read it in the past tense: many of the "agenteval will do X" rationales
> describe machinery that the refocus removed (the flat 14-library composition,
> vendor CLI adapters, telemetry/OTLP export, judge calibration, cross-adapter
> A/B stats). agenteval today is four libraries — HooksLibrary, MCPLibrary,
> SkillsLibrary, SubagentsLibrary — testing the agentic stack deterministically,
> with an LLM judge, or by driving a real coding agent.

## Context

agenteval is a Robot Framework library for evaluating AI coding agents. Its architecture was informed by reviewing several reference projects + relevant industry standards. Without explicit documentation of which patterns were reviewed, agenteval risks:

1. **Misperception as a fork.** Some patterns originate in sibling projects (notably `robotframework-agentguard`, also authored by the same maintainer). Without an explicit catalog, consumers may assume agenteval is a fork, inherit obligations to track agentguard's roadmap, or expect API-compatibility guarantees that don't exist.

2. **Drift from acknowledged sources without justification.** Even when adopting a pattern verbatim, future maintainers benefit from knowing *why* the pattern was adopted — so divergence later is a considered decision, not accidental drift.

3. **Re-discovery cost.** Without a written record, every future architectural question ("Should we add a sandbox Protocol surface in Phase 1?") risks re-litigating decisions already made + already justified.

This ADR is the **Architectural Influences Catalog**: a per-pattern record of what was reviewed, the decision taken for agenteval, and a one-line rationale. Per the project's `feedback_agentguard_inspiration_not_dependency` working norm, the catalog **credits influences but creates no obligation** to stay aligned with any source.

## Decision

agenteval maintains a catalog of reviewed architectural patterns with explicit per-pattern decisions:

- `adopt-verbatim` — the pattern is adopted as-is from the source; agenteval's implementation matches the source's behavior at the API/structural level.
- `adapt` — the pattern's shape is adopted, but agenteval implements with project-specific refinements (different module names, different field types, different defaults).
- `borrow-concept` — the underlying *idea* is borrowed, but agenteval's implementation is independent of the source (different architecture, different boundaries).
- `explicitly-diverge` — the source's choice was reviewed and explicitly rejected in favor of a different approach (rationale documented).
- `not-applicable` — the source's pattern targets a problem agenteval doesn't have (e.g., agentguard-internal features like Ruflo / Aidefence).

The catalog lives in this ADR's `§Body` section. New entries (additional reviewed patterns) require an ADR-amendment via the `§Amendments Log` section. Entries' decisions can be updated over time as agenteval's understanding evolves — divergence is acceptable; opacity is not.

## Consequences

- **Catalog is non-binding.** Per the §Scope + obligation framing section, no entry in this catalog creates an obligation for agenteval to track the source's future changes. Catalogued sources can evolve independently.
- **Periodic review cadence.** At each major milestone (Phase 1 close, Phase 2 close), this catalog is reviewed against the source projects to determine whether any new patterns warrant inclusion or whether any existing decisions warrant amendment.
- **Catalog drives ADR-001 evolution.** Each surviving ADR that inherits a pattern cites the corresponding catalog row + decision. Cross-references resolve in both directions.
- **Amendments Log records ratifications.** Each newly-ratified ADR appends an entry to `§Amendments Log` explaining what was ratified and citing the evidence trail.

## Alternatives

- **No catalogue; document influences ad-hoc in each ADR** — rejected. Ad-hoc citations drift; no single source of truth for "which patterns has agenteval reviewed?" makes architectural lineage opaque to new contributors.
- **Catalogue as a separate Markdown file (not an ADR)** — rejected. The catalogue IS an architectural decision (about how to handle architectural inheritance); the ADR namespace is the right home for it.
- **Catalogue but no per-pattern decision label** — rejected. Without explicit `adopt/adapt/diverge/not-applicable` labels, future readers can't tell what agenteval committed to vs what was merely reviewed.
- **Catalogue patterns but suppress source attribution** — rejected. Suppressing attribution would obscure the architectural lineage; transparency about influences is the catalogue's whole point.

## §Scope + obligation framing

> This catalog credits influences but creates **no obligation** to stay aligned with any source project. agenteval is free to evolve its decisions independently of any catalogued source.

Per the `feedback_agentguard_inspiration_not_dependency` project norm (ratified 2026-05-17 with the retirement of NFR-MAINT-06 / ADR-A4):

- **`robotframework-agentguard` is one reviewed reference among several.** It is NOT a dependency, NOT a parent project, and NOT a roadmap obligation. agenteval can diverge from any agentguard pattern at any time.
- **Competitor MCP-eval projects (`wolfeidau/mcp-evals`, `lastmile-ai/mcp-eval`) were reviewed as additional reference points.** Neither is a dependency.
- **The Model Context Protocol specification is treated as binding for the surface it governs.** When agenteval observes MCP traffic, it follows the protocol spec.

Inclusion in this catalog does NOT imply agenteval has any obligation to the source's maintainers, license, governance, or evolution. agenteval's architectural choices are agenteval's own.

## §Body

The catalog table lists each reviewed pattern with: source project + reference (URL / ADR ID), what the pattern does, the decision for agenteval, and a one-line rationale.

### `robotframework-agentguard` reviewed ADRs

Source: `/home/many/workspace/robotframework-agentguard/docs/adr/` (22 ADRs reviewed 2026-05-17).

| Source ADR | What it does | Decision | Rationale |
| --- | --- | --- | --- |
| [agentguard ADR-001 Provider Abstraction](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-001-provider-abstraction.md) | LiteLLM as the universal LLM provider abstraction layer. | `adapt` | agenteval also uses LiteLLM, but wraps it in its own `agenteval.providers` entry-point plugin architecture (ADR-013) to allow non-LiteLLM providers via plugin. |
| [agentguard ADR-002 MCP Transport Strategy](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-002-mcp-transport-strategy.md) | MCP transport selection logic (stdio vs streamable HTTP). | `borrow-concept` | agenteval's hosted-MCP universal observation pattern (ADR-004) goes BEYOND transport selection — it imposes a per-test scoping model (ADR-009) and a coverage-detection contract (ADR-016) that have no analog in agentguard. |
| [agentguard ADR-003 Library Composition](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-003-library-composition.md) | DynamicCore composition with bounded sub-libraries, lazy-loaded. | `adapt` | agenteval also uses DynamicCore composition (16 sub-libraries per architecture.md project tree); the sub-library decomposition differs because agenteval's domain differs (evaluating coding agents vs guardrails). |
| [agentguard ADR-004 Tool-Call Matching](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-004-tool-call-matching.md) | Heuristics for matching observed tool calls against expected ones. | `adapt` | agenteval's tool-call matching surfaces via `metrics/` keywords (e.g., `Get Tool Hit Rate`); the matching heuristics are reviewed but agenteval applies them to its own per-test scoping. |
| [agentguard ADR-005 Statistical Assertion API](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-005-statistical-assertion-api.md) | Statistical primitives (`pass_at_k`, Mann-Whitney U, Cliff's δ, bootstrap). | `adapt` | agenteval's `Stat.` sub-library starts from agentguard's primitives; advanced primitives gated behind `[agenteval-advanced]` extra (Phase 2 — Epic 13; ratified Story 13.1 fix-the-losing-source-NOW amendment 2026-06-01 — drift from PRD/architecture/epic consistent `[agenteval-advanced]` wording). |
| [agentguard ADR-006 Skill Discovery Default-Deny](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-006-skill-discovery-default-deny.md) | Skills default to disabled; explicit allow-list required. | `explicitly-diverge` | agenteval's `Skill.` keywords *inspect* (static analysis) rather than *enforce* skill activation. Default-deny is the wrong posture for an evaluation framework — evaluators need to observe what skills WOULD activate, not block them. |
| [agentguard ADR-007 Hook Test Harness](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-007-hook-test-harness.md) | Test harness for agent hooks (pre-tool, post-tool). | `borrow-concept` | agenteval's `hooks/` sub-library has its own static-inspection keywords; the test-harness *concept* (hook-aware testing) is shared but the implementation is independent. |
| [agentguard ADR-008 Subagent A2A Harness](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-008-subagent-a2a-harness.md) | Agent-to-agent (A2A) communication test harness for subagents. | `borrow-concept` | agenteval's `subagents/` sub-library inspects subagent definitions statically; A2A runtime harness is out of scope for Phase 1 (re-evaluate Phase 2). |
| [agentguard ADR-009 Coding Agent Driver](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-009-coding-agent-driver.md) | Driver pattern for invoking coding agents (CC CLI, OpenAI Agents SDK, ...). | `adapt` | The foundational pattern for agenteval's `CodingAgentAdapter` Protocol (ADR-003). agenteval adapts with explicit CLI/SDK base-class split (`SubprocessAdapter` / `InProcessAdapter`) and structured trace-extraction (ADR-006 completeness, ADR-007 coverage). |
| [agentguard ADR-010 Session Schema + 42796 Metrics](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-010-session-schema-and-42796-metrics.md) | Persistent session schema + the "42796" reference metrics set. | `adapt` | agenteval's `metrics/` sub-library borrows the per-session metric-recording pattern; the specific metric set differs (agenteval focuses on tool-call metrics, agentguard on guardrail-breach metrics). |
| [agentguard ADR-011 LLM-Judge Calibration](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-011-llm-judge-calibration.md) | LLM-as-judge calibration suite + agreement scoring. | `adapt` | agenteval's `judge/` sub-library (Phase 2 — Epic 12) borrows the calibration suite pattern; calibration corpus differs (agenteval calibrates against coding-agent traces, not guardrail decisions). |
| [agentguard ADR-012 OTel RF Listener](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-012-otel-rf-listener.md) | OpenTelemetry RF Listener v3 for emitting evaluation spans. | `adapt` | The foundational pattern for agenteval's `telemetry/` OTel listener (Story 5.1). agenteval emits its own span schema following OTel GenAI semconv (separately catalogued below). |
| [agentguard ADR-013 Sandbox Policy](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-013-sandbox-policy.md) | Sandbox-required gate for code-execution scenarios + Inspect AI sandbox toolkit integration (Docker/K8s/Proxmox) + `--allow-code-execution` opt-in flag. | `adapt` | agenteval ADR-018 preserves the sandbox-required posture + the error-on-refusal gate semantics, but diverges on the backend strategy (no Inspect AI dep; `agenteval.sandboxes` entry-points-plugin model with Phase-3 deferral) and on the opt-in mechanism (`SandboxBackend` Protocol + `NullSandbox` default vs `--allow-code-execution` flag). Different error-class hierarchy (`SandboxRequiredError(AgentEvalSafetyError)` vs `CodeExecutionDeniedError`). |
| [agentguard ADR-014 Spec Version Pinning](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-014-spec-version-pinning.md) | Pin external spec versions (MCP, agent-SDK schemas). | `adapt` | agenteval ADR-008 (MCP Spec Version Validation) implements the pin-and-validate pattern for the MCP spec; per-adapter spec pinning lives in each adapter's pyproject.toml extra. |
| [agentguard ADR-015 Ruflo Sona Self-Learning](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-015-ruflo-sona-self-learning.md) | Ruflo Sona self-learning system. | `not-applicable` | Ruflo is agentguard-internal infrastructure for guardrail self-improvement; agenteval is an evaluation library, not a self-improving guardrail. |
| [agentguard ADR-016 Ruflo Memory HNSW Knowledge Graph](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-016-ruflo-memory-hnsw-knowledge-graph.md) | HNSW-based knowledge graph for Ruflo memory. | `not-applicable` | Ruflo-internal; outside agenteval's scope. |
| [agentguard ADR-017 Ruflo Hooks Integration](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-017-ruflo-hooks-integration.md) | Ruflo-Hooks integration for self-improvement loops. | `not-applicable` | Ruflo-internal. |
| [agentguard ADR-018 Multi-Agent Swarm Test Generation](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-018-multi-agent-swarm-test-generation.md) | Multi-agent swarm for generating test scenarios. | `not-applicable` | agentguard-internal feature for guardrail test generation; agenteval generates scenarios via deterministic fixtures (ADR-005), not swarm-generation. |
| [agentguard ADR-019 3-Tier Model Routing](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-019-3-tier-model-routing.md) | 3-tier model routing (T1 fast/cheap, T2 balanced, T3 slow/accurate). | `adapt` | agenteval inherits the 3-tier model concept and applies it to evaluation keywords: Tier-1 = static inspection, Tier-2 = single LLM call, Tier-3 = fan-out + statistical. ACL gates per-tier (FR26-31). |
| [agentguard ADR-020 Aidefence Skill Scanner](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-020-aidefence-skill-scanner.md) | Aidefence skill-scanner for malicious-skill detection. | `not-applicable` | agentguard-internal security feature; agenteval doesn't ship a scanner — it inspects skill definitions statically without judging maliciousness. |
| [agentguard ADR-021 Unified Scenario Test Harness](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-021-unified-scenario-test-harness.md) | Unified scenario-test harness across guardrail types. | `borrow-concept` | agenteval's `scenarios/` sub-library has its own scenario fixture model (golden traces per ADR-005); the *unification* concept is shared but the implementation is independent. |
| [agentguard ADR-022 AssertionEngine Adoption](https://github.com/manykarim/robotframework-agentguard/blob/main/docs/adr/ADR-022-assertion-engine-adoption.md) | Adopts robotframework-assertion-engine; documents the getter+matcher idiom, polling-ban on Tier-2/3, validate-operator-disabled-by-default. | `adapt` | agenteval's `_assertions/` sub-library inherits the getter+matcher idiom + the two negative-consequence clauses (polling-ban + validate-disabled). Likely Phase 2 deliverable for the full AssertionEngine wiring; the two PRD-locked clauses ship in Phase 1 enforced by `PollingDisallowedError` + `ValidateOperatorDisallowed` (ADR-014). |

### Competitor MCP-eval projects

Reviewed 2026-05-17. No code clones; reviewed via published READMEs + ADRs (where available).

| Source | Reference | What it does | Decision | Rationale |
| --- | --- | --- | --- | --- |
| `wolfeidau/mcp-evals` | https://github.com/wolfeidau/mcp-evals | MCP-server evaluation toolkit. | `borrow-concept` | The general shape (eval framework for MCP servers) overlaps with agenteval's MCP-side surface (FR23-29); agenteval's RF-native + per-test-scoped approach differs in primary surface (RF keywords vs CLI tool). |
| `lastmile-ai/mcp-eval` | https://github.com/lastmile-ai/mcp-eval | MCP server-side evaluation harness. | `borrow-concept` | Similar overlap; agenteval differentiates via RF integration + agent-side metric integration. |

### Relevant standards

| Source | Reference | What it does | Decision | Rationale |
| --- | --- | --- | --- | --- |
| Model Context Protocol specification | https://spec.modelcontextprotocol.io/ | Defines the MCP wire protocol + lifecycle. | `adopt-verbatim` | agenteval consumes MCP servers per the spec; spec-version validation (ADR-008) enforces conformance to the supported range (`mcp>=1.0,<2.0`). |

## §Amendments Log

Date-ordered log of ratifications that amended catalog entries OR ratified ADRs
that depend on catalog patterns. Only the ADRs that survive the four-surface
refocus are listed; the entries for retired ADRs were removed alongside their
files (2026-07).

- **2026-05-17 — ADR-004 ratified.** Hosted-MCP universal trace observation pattern accepted with empirical findings from the Story 0.1 spike: handler-wrap at `Server.request_handlers[CallToolRequest]` validated across three transports (in-memory, stdio subprocess, streamable HTTP) under `pabot --processes 4`. See `docs/adr/ADR-004-hosted-mcp-observation.md`.
- **2026-05-17 — ADR-008 ratified.** MCP spec version validation at session start; the observer refuses loudly when the negotiated version falls outside the supported range. See `docs/adr/ADR-008-mcp-spec-version-validation.md`.
- **2026-05-17 — ADR-009 ratified.** Per-test MCP server scope via Listener v3 `test_id`; per-test SIGTERM-aware teardown. See `docs/adr/ADR-009-per-test-mcp-server-scope.md`.
- **2026-05-17 — ADR-014 ratified.** Error-class hierarchy: `AgentEvalError` base with per-leaf `error_code` attributes mapped to exit codes. See `docs/adr/ADR-014-error-class-hierarchy.md`.
- **2026-05-17 — ADR-016 ratified.** `mcp_coverage` field semantics with the D1 trust-floor (strongest complete path wins). See `docs/adr/ADR-016-mcp-coverage-detection-default.md`.
