---
stepsCompleted:
  - step-01-init
  - step-02-context
  - step-03-starter
  - step-04-decisions
  - step-05-patterns
  - step-06-structure
  - step-07-validation
  - step-08-complete
lastStep: 8
status: complete
completedAt: 2026-05-17
inputDocuments:
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/adr-backlog-from-prd.md"
  - "_bmad-output/planning-artifacts/implementation-readiness-report-2026-05-16.md"
  - "_bmad-output/planning-artifacts/product-brief-robotframework-agenteval.md"
  - "_bmad-output/planning-artifacts/product-brief-robotframework-agenteval-distillate.md"
  - "_bmad-output/planning-artifacts/research/technical-robot-framework-agent-evaluation-library-design-research-2026-05-15.md"
referenceCodebases:
  - path: "/home/many/workspace/robotframework-agentguard"
    role: "Inspiration / pattern reference project (one of several reviewed); NOT a dependency. agenteval is free to diverge from agentguard's choices whenever a different approach serves agenteval better. Reframed 2026-05-17 from earlier 'sibling code-copy' framing — see memory/feedback_agentguard_inspiration_not_dependency.md"
    actualAdrCount: 20  # ADR-001..014 + ADR-019..022 in agentguard/docs/adr/
workflowType: architecture
projectType: developer_tool
projectContext: greenfield
project_name: robotframework-agenteval
user_name: Many
date: 2026-05-16

# Step 1 outputs — load-bearing architectural decisions captured before content drafting
step01Decisions:
  structuralRelationshipToAgentguard:
    decision: "Structure A — independent implementation (agentguard is one reviewed pattern source among others)"
    rationale: |
      agenteval is its own product with its own destiny. Sub-library names may
      overlap with agentguard's (_assertions, providers, stats, telemetry, mcp,
      skills, hooks, subagents, coding_agent, judge) because the names describe
      the concerns naturally — agenteval evaluates each pattern on merit and is
      free to diverge whenever a different abstraction serves agenteval better.
      Patterns may be borrowed from agentguard (and other references: wolfeidau/
      mcp-evals, lastmile-ai/mcp-eval, OpenTelemetry GenAI semconv, etc.), but
      there is NO dependency, NO code-copy lock-in, NO required alignment.
      agenteval does NOT import from `agentguard.*`. Structure A is the right
      structure NOT because we code-copy from agentguard but because agenteval
      is its own product.
    alternatives_rejected:
      - "Structure B (agenteval depends on agentguard PyPI dep): rejected — couples release cadence; requires agentguard to be published as 1.0+ (pre-1.0 today); user-elected independence."
      - "Structure C (extract shared `robotframework-agentcore` kernel): rejected for Phase 1 — biggest refactor cost; coordinated 3-package release; revisit if maintenance burden becomes painful."
    reframed_2026_05_17: |
      Earlier framing called Structure A "sibling code-copy + drift-check CI
      (NFR-MAINT-06)" with ADR-A4 implementing automated agentguard-drift CI.
      Both retired 2026-05-17 — agentguard reframed from dependency to
      inspiration; agenteval is free to diverge. No drift-check needed because
      there is no dependency to drift-check. See
      memory/feedback_agentguard_inspiration_not_dependency.md.

  adrNumberingScheme:
    decision: "Hybrid — Architectural Influences Catalog (ADR-001) + original/extended ADRs (ADR-002..0NN)"
    rationale: |
      agenteval ADR-001 is a single "Architectural Influences Catalog" listing
      patterns reviewed across multiple references (robotframework-agentguard
      among others) with status: adopt | adapt | diverge | acknowledge-only.
      Subsequent agenteval ADRs (ADR-002..0NN) cover original-to-agenteval
      decisions. Keeps docs/adr/ listing lean; reviewed patterns remain visible
      via the catalog. (Originally framed as "Inheritance Manifest" with verbatim
      inheritance from agentguard; reframed 2026-05-17.)
    alternatives_rejected:
      - "Verbatim renumbering (16+ ADRs all numbered in agenteval): rejected — bureaucratic; many ADRs would be 'copy of agentguard ADR-NNN'."
      - "Cross-reference only (no catalog): rejected — reviewed patterns invisible in agenteval's docs/adr/ listing; new contributors miss the architectural context."

  sandboxPolicyScope:
    decision: "Adopt sandbox policy now (Phase 1); defer backend implementation to Phase 3"
    rationale: |
      Honest middle ground (third option from the elicitation). Phase 1 ships:
      (1) Sandbox Policy adopted into agenteval's Architectural Influences
      Catalog (borrowed from agentguard ADR-013, evaluated on merit); (2)
      `SandboxRequiredError` raised when Tier-3 code-execution scenarios are
      requested without a configured sandbox backend; (3) `SandboxBackend`
      Protocol published as part of the contributor-facing API. Phase 3 ships:
      (4) bundled sandbox backend implementations (Docker, ephemeral worktree).
      This keeps the PRD's Phase 1 implementation scope honest (no actual
      sandbox code shipped in MVP) while tightening the security posture from
      Day 1 — the policy + error gate exist; backends are extras.
    impact_on_prd: |
      Modifies PRD `## Product Scope > Vision — Phase 3` slightly: Phase 3 still
      ships sandbox BACKENDS, but the Sandbox Policy ADR + SandboxRequiredError
      gate + SandboxBackend Protocol all ship Phase 1. This is a tighter Phase 1
      than the PRD originally framed. Architecture step captures this as a
      sanctioned scope refinement; epic-author should add a Phase 1 "Sandbox
      Policy + Gate + Protocol (no backend)" story.

reconciliationFindings:
  prd_adr_claims_audited: 4
  prd_adr_claims_grounded: 4   # all 4 claims ARE grounded in agentguard's prior art, but...
  prd_adr_claims_misnumbered: 4  # ...the numbering is misaligned with agentguard's actual ADR ordering
  agentguard_adrs_relevant_unreviewed_in_prd: 10  # ADR-001/002/004/005/010/011/012/013/014/019
  finding_summary: |
    All 4 PRD-claimed influenced concepts have prior art in agentguard's reviewed
    patterns, but two of them (polling ban, validate-operator-disabled) are NOT
    standalone ADRs in agentguard — they are negative-consequence clauses inside
    agentguard ADR-022 (AssertionEngine Adoption, dated 2026-05-04 = newest
    agentguard ADR). Polling ban observed at src/AgentGuard/_assertions/adapter.py:101-105.
    Validate-disabled observed at src/AgentGuard/_assertions/adapter.py:107-112.
    PRD's "ADR-001..004 informed by agentguard" framing is a renumbering convention
    for agenteval's own ADR namespace, NOT a literal claim about agentguard's
    ADR-001..004 (which are: 001 provider-abstraction, 002 mcp-transport-strategy,
    003 library-composition, 004 tool-call-matching). agenteval evaluates each
    reviewed pattern on merit and may diverge.
    See reconciliationMatrix entries below for the full mapping.

  agentguard_actual_adr_count: 20  # 001-014 + 019-022 (some numbers skipped: 015-018 reserved/ruflo-specific)
  agentguard_sub_libraries: 11
  # Sub-libraries in agentguard/src/AgentGuard/:
  # _assertions, providers, stats, telemetry, mcp, skills, hooks, subagents (with bridges/),
  # coding_agent (with benchmarks/, drivers/, metrics/, session/), judge, security, tool_calls, mcp_scenario
  # = 13 sub-library directories; some grouped under coding_agent/
  agenteval_sub_libraries_target: 12
  # Per PRD: _assertions, providers, coding_agent, telemetry, mcp, skills, hooks,
  # subagents, scenarios, metrics, stats, judge
  divergence_from_agentguard:
    # Examples of where agenteval picks a different shape than agentguard.
    # agenteval is free to diverge anywhere on the catalog; these are just notable cases.
    - "agenteval has `metrics` (folds patterns observed in agentguard's tool_calls/ + parts of coding_agent/metrics/ into a different shape)"
    - "agenteval has `scenarios` (generalizes the concept observed in agentguard's mcp_scenario/)"
    - "agenteval ships `security` policy in Phase 1 (per sandboxPolicyScope decision above); agentguard has a `security/` sub-library that agenteval may reference for pattern review but independently implements"

reconciliationMatrix:
  - agenteval_concept: "DynamicCore composition with bounded sub-libraries"
    agentguard_source: "ADR-003 Library Composition"
    agentguard_code: "src/AgentGuard/library.py:48 `class AgentGuard(DynamicCore)`; lazy-import loop lines 79-102 silently swallows ImportError"
    agenteval_action: "inherit-verbatim"
    grounded: true

  - agenteval_concept: "AssertionEngine adoption for getter+matcher idiom"
    agentguard_source: "ADR-022 AssertionEngine Adoption as Shared Kernel for Get-Style Keywords (dated 2026-05-04, agentguard's NEWEST ADR)"
    agentguard_code: "src/AgentGuard/_assertions/adapter.py:71-120 `assert_value()` free function with tier+polling+validate gates; pyproject.toml:45 pins `robotframework-assertion-engine>=4.0,<5.0`"
    agenteval_action: "inherit-verbatim"
    grounded: true
    note: "Misnumbered in agenteval PRD — chronologically agentguard's newest ADR, not foundational ADR-002 material."

  - agenteval_concept: "Polling ban on Tier-2/Tier-3 keywords (PollingDisallowedError)"
    agentguard_source: "ADR-022 §Negative Consequences (composite with ADR-019 3-Tier Model Routing as tier source)"
    agentguard_code: "src/AgentGuard/_assertions/adapter.py:101-105 `if polling is not None and tier >= 2: raise PollingDisallowedError`"
    agenteval_action: "inherit-verbatim"
    grounded: true
    note: "NOT a standalone ADR; rule embedded in ADR-022 with code enforcement. agenteval should likewise NOT mint a standalone ADR for this — capture as a clause in agenteval's AssertionEngine ADR (after architectural influences catalog)."

  - agenteval_concept: "validate operator disabled by default (eval() security gate)"
    agentguard_source: "ADR-022 §Negative Consequences (composite with ADR-013 Sandbox Policy)"
    agentguard_code: "src/AgentGuard/_assertions/adapter.py:107-112 `if op is AssertionOperator.validate and not allow_validate: raise ValidateOperatorDisallowed`"
    agenteval_action: "inherit-verbatim"
    grounded: true
    note: "Same status as polling ban — rule embedded in ADR-022 + composite with sandbox-policy ADR-013. agenteval borrows both gates as part of AssertionEngine adoption (evaluated on merit; free to diverge)."

  - agenteval_concept: "Tool-Call Matching (BFCL AST Equality)"
    agentguard_source: "ADR-004 Tool-Call Matching"
    agentguard_code: "src/AgentGuard/tool_calls/library.py"
    agenteval_action: "inherit"
    grounded: true
    note: "agenteval `Trajectory Should Match mode=exact|subsequence|set|regex` (FR23a/b) consumes this. Originally uncaptured in PRD's 'inherited 4' framing."

  - agenteval_concept: "Statistical Assertion API (N≥10, pass@k, Mann-Whitney, Cliff's δ)"
    agentguard_source: "ADR-005 Statistical Assertion API"
    agentguard_code: "src/AgentGuard/stats/{pass_at_k,mannwhitney,cliffs_delta,bootstrap,vargha_delaney,tar}.py"
    agenteval_action: "inherit"
    grounded: true
    note: "agenteval `Stat.` namespace (FR26-FR29) is this. Phase 1 ships subset (Run N Times + Pass At K); Phase 2 adds Mann-Whitney/Cliff/bootstrap behind `[agenteval-advanced]` extras. PRD uncaptured."

  - agenteval_concept: "Provider Abstraction via LiteLLM"
    agentguard_source: "ADR-001 Provider Abstraction via LiteLLM"
    agentguard_code: "src/AgentGuard/providers/{base.py,litellm_adapter.py,mock.py,factory.py}"
    agenteval_action: "inherit"
    grounded: true
    note: "agenteval `LLMProviderAdapter` Protocol (FR17c) is this exact shape. PRD uncaptured."

  - agenteval_concept: "MCP Transport Strategy (in-memory/stdio/streamable_http auto)"
    agentguard_source: "ADR-002 MCP Transport Strategy"
    agentguard_code: "src/AgentGuard/mcp/library.py"
    agenteval_action: "inherit"
    grounded: true
    note: "FR7 supports all three transports. PRD uncaptured."

  - agenteval_concept: "Coding Agent Driver Pattern"
    agentguard_source: "ADR-009 Coding Agent Driver"
    agentguard_code: "src/AgentGuard/coding_agent/library.py + coding_agent/drivers/"
    agenteval_action: "extend"
    grounded: true
    note: "agenteval `CodingAgentAdapter` Protocol + `InProcessAdapter` / `SubprocessAdapter` base classes (FR12-13) extends this with the SubprocessAdapter ABC for CLI agents (CC CLI, Codex CLI, Copilot CLI) — agentguard's Driver pattern is mostly in-process SDK-style. PRD uncaptured."

  - agenteval_concept: "Session JSONL Schema + #42796 Metric Pack"
    agentguard_source: "ADR-010 Session Schema and 42796 Metrics"
    agentguard_code: "src/AgentGuard/coding_agent/session/types.py + coding_agent/metrics/"
    agenteval_action: "inherit"
    grounded: true
    note: "agenteval `Metric.*` keywords (FR19-FR22) consume this schema. The RunManifest (FR39) extends it with reproducibility footer. PRD uncaptured."

  - agenteval_concept: "LLM-as-Judge Calibration (Cohen's κ ≥ 0.7 hard-fail)"
    agentguard_source: "ADR-011 LLM-Judge Calibration"
    agentguard_code: "src/AgentGuard/judge/library.py"
    agenteval_action: "inherit"
    grounded: true
    note: "agenteval `Judge.Get Score` (Phase 2 per FR48) borrows the calibration discipline (evaluated on merit; free to diverge). PRD uncaptured."

  - agenteval_concept: "OTel + Robot Listener (span hierarchy, JSON+OTLP export)"
    agentguard_source: "ADR-012 OTel RF Listener"
    agentguard_code: "src/AgentGuard/telemetry/{otel_listener.py,spans.py}"
    agenteval_action: "inherit"
    grounded: true
    note: "agenteval `telemetry/listener.py` (FR32-33) is this. PRD uncaptured. (Story 5.1 pre-create-story drift fix 2026-05-20: pre-edit said `otel_listener.py` borrowing agentguard's filename; ratified `docs/contracts/listener-integration.md` L17 + epics.md L1437 say `listener.py` — fix-the-losing-source-NOW pattern per `feedback_spec_vs_ratified_doc_precheck`. agentguard's file remains `otel_listener.py` per the reference row L208; agenteval diverges to `listener.py`.)"

  - agenteval_concept: "Sandbox Policy (default-deny + Inspect AI)"
    agentguard_source: "ADR-013 Sandbox Policy"
    agentguard_code: "src/AgentGuard/security/{library.py,sandbox_backends/}"
    agenteval_action: "inherit-policy-defer-backends"
    grounded: true
    note: "Per user decision: inherit policy + SandboxRequiredError + SandboxBackend Protocol in Phase 1; defer bundled backends (Docker, ephemeral worktree) to Phase 3. Tightens PRD scope (PRD deferred everything sandbox-related to Phase 3). agenteval epic-author should add a Phase 1 'Sandbox Policy + Gate + Protocol (no backend)' story. PRD uncaptured."

  - agenteval_concept: "Spec Version Pinning (MCP, A2A, Skills)"
    agentguard_source: "ADR-014 Spec Version Pinning"
    agentguard_code: "pyproject.toml + version checks at session init"
    agenteval_action: "extend"
    grounded: true
    note: "agenteval extends with MCP spec version gate (PRD ADR-011 / AC-MCP-OBSERVE-02 / FR8 / FR46). PRD captured this as agenteval's own ADR — should be reframed as 'extending agentguard ADR-014' in agenteval's manifest."

  - agenteval_concept: "3-Tier Model Routing"
    agentguard_source: "ADR-019 3-Tier Model Routing"
    agentguard_code: "Tier param threaded through adapter; tier source for polling gate"
    agenteval_action: "inherit"
    grounded: true
    note: "agenteval Tier 1/2/3 ACL model (FR30a/b, FR31a/b) is this. PRD uncaptured."

  - agenteval_concept: "SubAgent / A2A Harness"
    agentguard_source: "ADR-008 SubAgent A2A Harness"
    agentguard_code: "src/AgentGuard/subagents/{library.py,bridges/}"
    agenteval_action: "extend-if-needed"
    grounded: true
    note: "Phase 1 agenteval doesn't ship multi-agent trajectory scoring (sub-agent eval is single-skill-flow in journeys); revisit if Phase 2+ adds multi-agent scenarios. PRD uncaptured but not Phase 1 critical."

  - agenteval_concept: "Skill Discovery + Default-Deny"
    agentguard_source: "ADR-006 Skill Discovery + Default-Deny"
    agentguard_code: "src/AgentGuard/skills/library.py"
    agenteval_action: "acknowledge-only"
    grounded: true
    note: "agentguard's security-focused skill discovery (default-deny allowlist) is a different concern from agenteval's skill EVALUATION (FR1-3). agenteval acknowledges the pattern but doesn't enforce default-deny on skills it evaluates."

  - agenteval_concept: "Hook Test Harness"
    agentguard_source: "ADR-007 Hook Test Harness"
    agentguard_code: "src/AgentGuard/hooks/library.py"
    agenteval_action: "acknowledge-only"
    grounded: true
    note: "agenteval hook validation (FR4) is static-inspection only; agentguard's harness for actually running hooks is out of agenteval scope."

netNewArchitecturalFindings:
  - finding: "agentguard ships 11 sub-libraries but no top-level eval orchestrator surface — agenteval is the missing eval layer in this problem space."
    impact: "agenteval is its own product, not a wrapper around agentguard. agenteval's top-level library.py composes its own sub-libraries; sub-library names may overlap with agentguard's because they describe the concerns naturally."

  - finding: "agentguard's lazy-import pattern (library.py:82-93) silently swallows ImportError to enable staged sub-library landing without breaking the import."
    impact: "agenteval borrows this pattern (evaluated on merit) — useful for Phase 1 / Phase 2 split (Judge sub-library can ship Phase 2 without breaking Phase 1 imports if `[judge]` extra is absent)."

  - finding: "agentguard BehavioralReport (coding_agent/library.py:216-252) wires Mann-Whitney U + alpha=0.05 into the Session metric pack."
    impact: "Stats × Session integration has prior art in agentguard. agenteval can borrow the wiring shape (evaluated on merit) as part of ADR-005 + ADR-010 work; doesn't need to re-derive."

  - finding: "AssertionEngine ADR (agentguard ADR-022, dated 2026-05-04) is the NEWEST agentguard ADR — chronologically the OPPOSITE of foundational; it's a recent shared-kernel formalization."
    impact: "agenteval architecture treats AssertionEngine as a Shared Kernel dependency (imported from `robotframework-assertion-engine` PyPI pkg, pinned `>=4.0,<5.0`), with agenteval's own `_assertions/adapter.py` borrowing agentguard's gating shape as a reviewed pattern. Free to diverge if a different gating shape proves better for agenteval."

  - finding: "Polling ban + validate-disabled are TWO RULES in ONE agentguard ADR (ADR-022), each enforced at specific line ranges in `_assertions/adapter.py`. PRD's framing as TWO separate influenced ADRs (003 + 004) overcounts."
    impact: "agenteval's Architectural Influences Catalog (ADR-001) lists ADR-022 ONCE with both gates noted; agenteval's own AssertionEngine ADR (likely ADR-002 in agenteval numbering) likewise carries both rules as negative-consequence clauses, NOT two separate ADRs."
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Document orientation

- **Project:** `robotframework-agenteval` — open-source Robot Framework library for evaluating AI agents (MCP servers, Claude Code skills, sub-agents, hooks, multi-step LLM agents).
- **Phase:** Architecture (Phase 3 of BMad planning pipeline, between PRD and Epics).
- **Inputs:** PRD (`prd.md`, status: complete) + ADR backlog sidecar (`adr-backlog-from-prd.md`) + implementation readiness report (`implementation-readiness-report-2026-05-16.md`) + brief/distillate/research + reference codebase `robotframework-agentguard` (inspiration / pattern reference only — NO dependency; reframed 2026-05-17 from earlier sibling-code-copy framing).
- **Architectural relationship to reference project (locked at Step 1; reframed 2026-05-17):** Structure A — independent implementation. agenteval is free to diverge from agentguard's choices whenever a different approach serves agenteval better. `robotframework-agentguard` is one inspiration / pattern source among others (alongside wolfeidau/mcp-evals, lastmile-ai/mcp-eval, OpenTelemetry GenAI semconv); no PyPI dependency; no code-copy lock-in.
- **ADR numbering scheme (locked at Step 1):** Hybrid — ADR-001 will be the Architectural Influences Catalog listing reviewed patterns by adopt/adapt/diverge status; ADR-002 onwards = original/extended decisions for agenteval.
- **Sandbox policy scope (locked at Step 1):** Adopt sandbox policy + `SandboxRequiredError` gate + `SandboxBackend` Protocol in Phase 1; defer bundled backends to Phase 3. Tighter than the PRD's original Phase 3 deferral; epic-author should add a Phase 1 "Sandbox Policy + Gate + Protocol (no backend)" story.

## Reviewed-pattern summary

See frontmatter `reconciliationMatrix` for the full 17-entry mapping of agenteval concepts to reviewed agentguard ADRs + code locations. Key takeaways:

- **All 4 PRD-claimed influenced concepts have prior art in agentguard's reviewed patterns**, but two of them (polling ban, validate-disabled) are NOT standalone ADRs — they're negative-consequence clauses inside agentguard ADR-022 (AssertionEngine Adoption, the NEWEST agentguard ADR).
- **10 additional agentguard ADRs are directly relevant** to agenteval and were unreviewed in the PRD's "4 influenced" framing: ADR-001 (Provider Abstraction), ADR-002 (MCP Transport), ADR-004 (Tool-Call Matching), ADR-005 (Statistical Assertion API), ADR-009 (Coding Agent Driver), ADR-010 (Session Schema + #42796 metrics), ADR-011 (LLM-Judge Calibration), ADR-012 (OTel RF Listener), ADR-013 (Sandbox Policy), ADR-014 (Spec Version Pinning), ADR-019 (3-Tier Model Routing).
- **The Architectural Influences Catalog (agenteval ADR-001)** will be the first authored content in subsequent steps — it lists ~14 reviewed agentguard patterns (the 4 from PRD's framing + 10 newly-recognized) plus references reviewed elsewhere, each annotated with action status: `adopt` / `adapt` / `diverge` / `acknowledge-only`. agenteval is free to diverge anywhere on the catalog.

## Project Context Analysis

### Requirements Overview

**Functional Requirements (65 FRs across 11 capability areas):**

The PRD's 65 FRs split into ~56 Phase 1 + ~9 Phase 2, organized into 11 capability areas: Static Inspection (6 FRs), MCP Server Dynamic Eval (6), Agent Run Orchestration (13), Tool-Call Metrics (7), Statistical Evaluation + Tier Model (9), Trace Recording (9), Configuration & Extensibility (4), Conformance & Compatibility (4), Reporting/CI/First-Run (11), Honest Failure Reporting (3), Determinism Contract docs (3). Architecturally these map to **12 sub-libraries** under a `DynamicCore`-composed top-level `AgentEval` library (pattern borrowed from agentguard ADR-003, evaluated on merit).

**Most architecturally consequential FR clusters:**

- **FR12 + FR13a-f (CodingAgentAdapter Protocol + 6 Tier-1 adapter implementations)** — drives the `InProcessAdapter` / `SubprocessAdapter` internal base-class split (extending the Coding Agent Driver pattern borrowed from agentguard ADR-009). Phase 1: Generic + Claude Code CLI. Phase 2: Claude Agent SDK + OpenAI Agents SDK + Codex CLI + Copilot CLI.
- **FR32-40 (trace recording + hosted-MCP observation + honesty fields)** — drives the OTel listener + trace store backplane (borrowed from agentguard ADR-012, evaluated on merit) plus the novel hosted-MCP server-side observer (agenteval-original ADR-007 per PRD sidecar). Per-test scope via Listener v3 `test_id` (FR40 / AC-MCP-OBSERVE-03) threads across MCP server lifecycle + adapter instances + trace collection.
- **FR26-31 (statistical primitives + Tier-1/2/3 model + ACL gates + determinism contract)** — drives the `Stat.` sub-library (borrows from agentguard ADR-005 Statistical Assertion API — `pass_at_k`, Mann-Whitney U, Cliff's δ, bootstrap already implemented in agentguard `stats/`; agenteval is free to diverge). Tier model borrowed from agentguard ADR-019; polling ban + `validate` operator gate borrowed from agentguard ADR-022 (the AssertionEngine adoption ADR).
- **FR45 + AC-CONFORMANCE-01/02 (conformance suite with fidelity oracles)** — drives `tests/conformance/` as a Phase 1 first-class deliverable, golden-trace fixtures from deterministic mock agent runs. No direct agentguard parallel (agentguard has its own tests but no published conformance suite for adapter authors); agenteval-original architecture work.
- **FR10a/b + FR11/FR11b (Tool Discoverability + cost guardrail + time guardrail)** — drives the multi-model fan-out pre-flight infrastructure with cost meter (FR11, default `max_cost_usd=5.00`) and time meter (FR11b, `max_runtime_seconds` default None). Agenteval-original; no agentguard parallel for "tool discoverability across models."
- **FR52 + FR18 (`agenteval init` + `agenteval new-adapter` CLI scaffolding)** — drives a separate CLI module (`agenteval.cli`) registered via `[project.scripts]`. Not a Robot Framework keyword surface — agenteval's only non-RF entry point.

**Non-Functional Requirements (25 NFRs) — architectural drivers:** (NFR-MAINT-06, an earlier architecture-introduced drift-check NFR, was retired 2026-05-17 when agentguard was reframed from dependency to inspiration.)

- **NFR-PERF-01 (≤5 min time-to-first-test)** drives minimal default install + bundled echo MCP server fixture + zero-API-key first-run path. Architecture must ensure the default install includes the bundled echo server; extras gate everything heavier.
- **NFR-PERF-02 (Tier-1 ≤50 ms median)** drives pure-Python file I/O for static-inspection keywords; no network, no LLM calls in Tier 1.
- **NFR-PERF-03a/b/c/d + NFR-PERF-05 (MCP startup latency + per-test scope trade-off)** drives a 3-mode `mcp_per_test` configuration (`True` / `"suite"` / `False`) — Phase 1 architecture must accommodate all three modes from Day 1 to honor the realistic constraint that `rf-mcp` / `robotmcp` take several seconds to start.
- **NFR-PERF-04 + NFR-PERF-06 (cost + runtime guardrails)** drives a cost-meter + wall-clock-meter abstraction that wraps any Tier-3 fan-out keyword. Pre-flight estimation infrastructure must be in the kernel, not per-keyword.
- **NFR-REL-01-03 (test-tier reliability bars: unit ≥99%, smoke 100%, live-nightly ≥95%)** drives the 3-tier test layout (`tests/unit/`, `tests/integration/` with `@pytest.mark.live`, `tests/acceptance/` with RF tags `smoke`/`tier1`/`tier3`) — borrowed from agentguard's structure (one reviewed pattern; agenteval is free to diverge).
- **NFR-REL-05 (dogfood loop integrity)** drives cross-repo CI integration as a first-class architectural concern. Library release CI must invoke `rf-mcp` + `robotframework-agentskills` test suites against the about-to-be-released wheel; regression in either blocks the release. Webhook / GitHub Actions workflow design needed.
- **NFR-SEC-01 (credential redaction mandatory pre-trace-write)** drives a single `config.redact_env()` choke point that every adapter + every trace backend MUST route through. Cannot be optional / opt-in; architecture must make redaction unavoidable.
- **NFR-COMPAT-01-06 (pinning + compatibility ranges)** drives a thin internal-facade pattern for every external-spec dependency: `telemetry/semconv.py` for OTel GenAI attribute names; `mcp/version_gate.py` for spec negotiation; `providers/base.py` Protocol for LiteLLM dependency isolation; binary-version-check helpers per CLI adapter.
- **NFR-MAINT-01-05 (solo + AI-agent-assisted; bus-factor mitigation; semver discipline; docs as first-class)** drives the contributor-facing API surface (`InProcessAdapter`, `SubprocessAdapter`, `LLMProviderAdapter`, `CodingAgentAdapter` Protocols + Mock adapter as template) and the doc-build CI commitment.
- **NFR-MAINT-06 (RETIRED 2026-05-17)** — Was "Automated agentguard-drift detection CI" implemented via ADR-A4. Retired when agentguard was reframed from dependency to inspiration — there is no dependency to drift-check, so Structure-A mitigations are no longer needed. agenteval is free to diverge from agentguard's choices whenever a different approach serves agenteval better. See `_bmad-output/planning-artifacts/memory/feedback_agentguard_inspiration_not_dependency.md` for the full reframing.

### Scale & Complexity

- Project complexity: **HIGH at the integration boundary, MEDIUM at the core** (per PRD `## Project Classification` and Domain Constraints §1-5).
- Primary technical domain: **Python developer-tool library** (Robot Framework PyPI package; pyproject.toml + `uv` + `hatchling`; semver pre-1.0).
- Estimated architectural components: **12 sub-libraries** + 6 Tier-1 coding-agent adapters (Phase 1: 2; Phase 2: 4) + **9 distinct error classes sharing a common `AgentEvalError` base** (per architectural concern #11 below + ADR-A3) + multiple Protocol surfaces (`LLMProviderAdapter`, `CodingAgentAdapter`, `SandboxBackend`) + conformance test suite + 7 documentation-contract deliverables (5 PRD-named + 2 architecture-introduced; agentguard-inheritance.md retired 2026-05-17).
- **11 architectural concerns** (revised — see next section): 7 truly cross-cutting + 1 selectively-applied shared pattern + 1 adapter-emitted data contract + 1 localized concern with kernel gate + 1 test-infrastructure deliverable.

### Technical Constraints & Dependencies

**Pinned external dependencies (per PRD Compatibility Matrix):**

- `robotframework>=7.4,<9.0` + `robotframework-pythonlibcore>=4.5` + `robotframework-assertion-engine>=4.0` (standard for modern Python+RF libraries).
- `mcp>=1.0,<2.0` — pinned major; spec-version gate (FR8, FR46) raises `UnsupportedMCPVersionError` on out-of-range negotiated versions.
- `litellm>=1.83` — pinned minor floor; `LLMProviderAdapter` Protocol isolates the dep.
- `opentelemetry-api/sdk>=1.27` — pinned minor floors; GenAI semconv routed through internal facade.
- `pydantic>=2.0`, `pyyaml>=6.0`, `jsonschema>=4.0`, `python-dotenv>=1.0`, `scipy>=1.13`, `numpy>=1.26` — core deps.

**External CLI binaries (never bundled per PRD NFR-SEC-04):**

- `claude` (Phase 1 — Claude Code CLI, output-format=stream-json schema is implicit external contract).
- `copilot` (Phase 2 — pinned `>=1.0.9,<2.0` per ADR-013, `events.jsonl` schema is implicit external contract).
- `codex` (Phase 2 — JSON event stream schema is implicit external contract).
- Each adapter validates binary version at instantiation; raises `UnsupportedBinaryVersionError` if outside pinned range.

**Pattern dependencies (Structure A — independent implementation; agentguard is one reviewed pattern source among others):**

- Per Step-1 decision (reframed 2026-05-17): agenteval does NOT import from or depend on agentguard. The reconciliation matrix in frontmatter identifies ~14 reviewed agentguard patterns that agenteval evaluates on merit. Concrete patterns reviewed (agenteval implements its own, may borrow shape, may diverge):
  - `_assertions/adapter.py` — pattern borrowed from agentguard's `assert_value()` free function with tier+polling+validate gates; agenteval may refine the gating shape.
  - `providers/base.py` + `providers/litellm_adapter.py` + `providers/mock.py` — pattern borrowed from agentguard's `LLMProviderAdapter` Protocol + LiteLLM impl + Mock impl + factory.
  - `telemetry/listener.py` + `telemetry/spans.py` — pattern borrowed from agentguard's RF Listener v3 entry-point (`telemetry/otel_listener.py`) + span emission helpers. (Story 5.1 pre-create-story drift fix 2026-05-20: agenteval filename diverges from agentguard's `otel_listener.py` to `listener.py` per ratified `docs/contracts/listener-integration.md` L17 + epics.md L1437.)
  - `stats/{pass_at_k.py, mannwhitney.py, cliffs_delta.py, bootstrap.py, _helpers.py, library.py}` — pattern borrowed from agentguard's statistical primitives.
  - `library.py` top-level — pattern borrowed from agentguard's `DynamicCore` composition with lazy-import loop (silent `ImportError` swallowing per agentguard `library.py:82-93`).

### Architectural Concerns Identified (11 total — restructured)

The original "8 cross-cutting concerns" list was audited via first principles (`changes ripple to multiple sub-libraries`) and 3 of 8 were reclassified. Net result: 7 truly cross-cutting + 4 differently-categorized concerns + 3 new concerns the original list missed (async bridge, entry-points discovery, error-class hierarchy). Total: **11 architectural concerns**. Each formalized as an ADR in `adr-backlog-from-architecture.md` where indicated.

#### A. Truly cross-cutting (7) — kernel-level architecture decisions required

These touch every (or nearly every) sub-library; design must be settled before sub-library work proceeds.

1. **Determinism handling + three-tier ACL** — every keyword carries a tier annotation; `_assertions/adapter.py` enforces gates (polling ban on Tier-2/3, `validate` operator opt-in, `TierViolationError` on Tier-1 LLM-invocation attempts). Architecture must define the tier-annotation mechanism (decorator? metadata dict? per-method attribute?) so libdoc renders tier badges (FR30a) and the dispatcher enforces gates (FR30b).

2. **Per-test scope via Listener v3 `test_id`** — threads across MCP server lifecycle (FR16, FR40), adapter instances (FR15), trace collection (FR32-33), conformance suite parallel-execution fixture (FR45 + NFR-PERF-05). Architecture must define how `test_id` flows from Listener context into every component needing scope isolation.

3. **Trace recording backplane** — single in-memory OTel-shaped store populated by Listener v3 + adapters + MCP observer; consumed by every `Metric.*` keyword (FR19-22), every honesty field (FR36a/b), `Get Last Warnings` (FR62), `Get Run Manifest` (FR39). Architecture must define the trace store data model + access API + backend dispatch (memory / JSONL / OTLP).

4. **Credential redaction (mandatory choke point)** — `config.redact_env()` + `config.add_redaction_pattern()`; applies to every trace serialization (memory / JSONL / OTLP) AND `Get Effective Config` output (FR38a/b). Architecture must make redaction unavoidable — no path that writes credentials in original form to any sink.

5. **(NEW) Async-to-sync bridge (`_run_async`) → ADR-A1** — kernel module used by every sub-library that calls async libraries: MCP client (`mcp` Python SDK), LiteLLM async paths, OTel async exporter (Phase 2), coding-agent SDK async APIs. PRD framed it as "internal helper" but it touches MCP, providers, coding_agent, telemetry — truly cross-cutting. Lives at `agenteval/_kernel/run_async.py`.

6. **(NEW) Entry-points discovery infrastructure → ADR-A2** — 4 distinct entry-point groups loaded at library import time: `[project.entry-points."agenteval.coding_agents"]` (FR17a), `[project.entry-points."agenteval.providers"]` (FR17c), `[project.entry-points."agenteval.judges"]` (Phase 2 implicit), `[project.entry-points."robot.listener"]` (FR33a) + a 4th implicit `plugins=[]` composition path (FR48). **+1 after ADR-A8** (`agenteval.sandboxes`). Cross-cutting at the package-loading layer. Architecture must define the discovery sequence, error handling for partially-installed adapter packages, and the precedence between entry-point-discovered adapters vs direct `__init__` passing (per FR17b). Lives at `agenteval/_kernel/discovery.py`.

7. **(NEW) Error-class hierarchy → ADR-A3** — 9 distinct error classes raised by the library: `PollingDisallowedError`, `CostExceededError`, `RuntimeBudgetExceededError`, `IncompleteTraceError`, `UnsupportedMCPVersionError`, `UnsupportedBinaryVersionError`, `TierViolationError`, `SandboxRequiredError`, `ValidateOperatorDisallowed`. **Architecture decision:** common `AgentEvalError(Exception)` base class + 4 sub-bases (`AgentEvalSafetyError`, `AgentEvalBudgetError`, `AgentEvalCompatError`, `AgentEvalIntegrityError`) for `try/except AgentEvalError` programmatic catch + structured `error_code` field for downstream JUnit XML emission (FR49) and exit-code mapping (FR50). Touches every sub-library that raises. Lives at `agenteval/errors.py`.

#### B. Shared pattern, applied selectively (1)

8. **Cost + runtime guardrails (Tier-3 fan-out keywords only) → ADR-A5** — `max_cost_usd` (FR11) and `max_runtime_seconds` (FR11b) apply ONLY to Tier-3 fan-out keywords (`MCP.Get Tool Discoverability`, `Stat.Run N Times`, `Run Scenario`). Static-inspection keywords, single-shot Tier-2 LLM keywords, and most metric getters DON'T touch this. **`@guarded_fanout(estimator=callable)` decorator** in `agenteval/_kernel/guardrails.py` opt-in keywords adopt, exposing standard estimation interface `(kwargs) -> (cost_estimate_usd, runtime_estimate_seconds)`. Pattern reuse via decoration; not kernel-level.

#### C. Adapter-emitted data contract (1)

9. **Honesty fields propagation (`completeness`, `mcp_coverage`) → ADR-A6** — only adapter-emitting paths (every `CodingAgentAdapter` impl + the hosted-MCP observer) populate these on `AgentRunResult.metadata`. Consumer sub-libraries (`Metric.*`, the kernel) check them and raise `IncompleteTraceError` on `external_mixed` (FR37) per ADR-016; orthogonally, recoverable trace-quality degradation events (observer connection drop, JSONL write failure, novel redaction pattern, missing `agenteval.*` span attributes) emit `DegradedTraceWarning` per FR61 (without raising) and — if the degradation invalidates server-side observation coverage — the run's `mcp_coverage` falls to `"external_mixed"` per ADR-016's degradation rules (the 3-state Literal `{"hosted_in_process", "subprocess_with_observer", "external_mixed"}` admits NO `"partial"` value — superseded 2026-05-17 ADR-016 ratification). **Detection-failure defaults to `external_mixed`** (NOT `hosted_in_process`) — safer than silent partial truth. Kernel-level enforcement at metric keyword entry via `_check_mcp_coverage(run)` helper in `agenteval/_kernel/coverage.py`. Adapter authors implement detection per their CLI's config conventions (CC: parse `~/.claude.json` + project `.mcp.json`; Copilot: parse `~/.copilot/mcp-config.json`; Generic: trivially `hosted_in_process` when a library-spawned MCP is registered, else `external_mixed`).

#### D. Localized concern with kernel-level gate (1)

10. **Sandbox policy + gate + Protocol Phase 1 → ADR-A8** — per Step-1 decision: Phase 1 ships policy + `SandboxRequiredError(AgentEvalSafetyError)` gate + `SandboxBackend` Protocol at `agenteval/security/protocols.py`. Default `NullSandbox` backend raises on every call — forces explicit user choice. Phase 3 ships bundled backends (Docker, ephemeral worktree). Localized to `security/` (Protocol + policy) + `scenarios/` (raises gate when Tier-3 code-execution scenarios requested without configured backend). Other sub-libraries don't touch sandbox.

#### E. Test infrastructure deliverable — NOT cross-cutting (1)

11. **Conformance suite as executable contract → ADR-A7** — `tests/conformance/` ships in Phase 1 as contract publication (FR45). It TESTS every Tier-1 adapter; community Tier-2 adapters self-service against it. But the suite itself lives in `tests/conformance/`; **no production sub-library imports from or depends on it**. The conformance contract is a deliverable; the suite is one component. **Organization:** per-AC test files (`test_ac_simplicity_01_evidence_block.py`, ...) + per-adapter parametrize + golden-trace fixtures under `fixtures/<adapter>/<scenario>.json` + truncation-injection harness at `harness.py`.

### Phase 1 Estimation Risk Register (3 items lacking agentguard precedent)

These three components are agenteval-original architecture work with **no agentguard precedent**. Estimation has wide error bars; architecture must surface them as Phase 1 timeline risks before committing to scope.

| Component | Best case | Worst case | Estimation hinge |
|---|---|---|---|
| **Hosted-MCP universal trace observer** (FR35 + FR40 + ADR-007 from PRD sidecar) | 1 week | 4 weeks | Hinges on whether `mcp` Python SDK exposes a clean middleware/interceptor API for server-side observation OR requires custom MCP server subclass that re-implements the protocol layer. **Action: spike-prototype in week 1 of Phase 1 to resolve the unknown.** |
| **Per-test MCP server scope mechanism + cleanup** (FR40 + AC-MCP-OBSERVE-03) | 1 week | 3 weeks | Hinges on graceful subprocess teardown under `pabot --processes 8` parallel execution + Listener v3 `test_id` propagation reliability across forked processes. agentguard has per-suite scope but not per-test; pattern must be derived. **Action: spike-prototype the parallel-cleanup harness early.** |
| **Conformance suite with fidelity oracles** (FR45 + AC-CONFORMANCE-01/02) | 1.5 weeks | 4 weeks | Hinges on golden-trace fixture format design (JSON Schema? Python data classes? `pytest-snapshot`-style?) AND truncation-injection harness mechanism. agentguard has tests but no published conformance suite for adapter authors. **Action: design the fixture format + harness before writing the first oracle.** |

**Aggregate impact:** worst-case combined slippage = ~11 weeks for these 3 components alone vs. best-case ~3.5 weeks — 7.5-week swing on a 6-8-week Phase 1 budget. **Recommendation:** schedule all 3 spikes in week 1-2 of Phase 1; acceptance criteria for the spikes is "can we estimate the rest of the work to ±20%". If spike outcome lands at worst case, trigger Phase 1.5 hardening sprint (per Risk Mitigation > Resource Risks > "Phase 1 slip beyond +50% buffer").

### NFR Conflict Compounds (surfaced via FMA)

NFR conflicts that the original PRD/Domain Constraints flagged but didn't COMPOUND to identify the worst-case interaction:

- **NFR-PERF-03d × NFR-PERF-05 × NFR-REL-05 — dogfood CI startup compound.** `rf-mcp` startup is several seconds (per NFR-PERF-03b empirical input). Default `mcp_per_test=True` (NFR-PERF-03d) under `pabot --processes 8` (NFR-PERF-05) running 30 tests against `rf-mcp` (NFR-REL-05 dogfood loop) = **~1,200 person-seconds of pure MCP server startup per CI run** (8 procs × 30 tests × ~5s startup). Trade-off matrix is documented; the COMPOUND in dogfood CI specifically isn't flagged. **Architecture mitigation:** Recipe Gallery #5 (dogfood replacement) MUST default to `mcp_per_test="suite"` to make the loop ergonomic; Phase 1 conformance suite includes a "heavy server simulation" fixture (intentionally `time.sleep(3)` on startup) that asserts the opt-out paths function correctly per NFR-PERF-05. Cross-repo CI integration (NFR-REL-05) must assume `mcp_per_test="suite"` is the default for dogfood scenarios.

- **NFR-PERF-04 × NFR-PERF-06 × FR11/FR11b — guardrail overlap.** Cost guardrail (`max_cost_usd`) and runtime guardrail (`max_runtime_seconds`) are orthogonal axes but architecturally share the pre-flight estimation infrastructure. ADR-A5's `@guarded_fanout(estimator=...)` decorator defines ONE shared estimator interface consumed by both guardrails — NOT two separate per-keyword estimation paths.

- **NFR-MAINT-06 × NFR-MAINT-01 (RETIRED 2026-05-17).** The earlier drift-check CI compound concern is moot — NFR-MAINT-06 was retired when agentguard was reframed from dependency to inspiration. No drift-check CI, no drift-triage burden, no `DriftReport` issues. agenteval is free to diverge.

### Project-Specific Architectural Risks Surfaced by Reviewed Patterns

- **AssertionEngine ADR (agentguard ADR-022) is the newest agentguard ADR, dated 2026-05-04 — chronologically opposite of "foundational."** Architecture treats AssertionEngine + its gates as a Shared Kernel dependency from a stable PyPI package (`robotframework-assertion-engine>=4.0,<5.0`); agenteval's `_assertions/adapter.py` borrows agentguard's gating shape as a reviewed pattern. agenteval is free to diverge.
- **The 10 agentguard ADRs the PRD did not capture as "influenced"** are now in the reconciliation matrix and will populate the Architectural Influences Catalog (agenteval ADR-001) in a later step. Architecture work cannot proceed without explicit decisions on each (`adopt` / `adapt` / `diverge` / `acknowledge-only`).
- **The hosted-MCP universal observation pattern (PRD ADR-007 / agenteval-original)** has no agentguard precedent — agentguard inspects MCP servers but does not perform server-side observation as a universal trace fallback. This is genuinely novel agenteval architecture; the implementation surface (FR35 + per-test scope via FR40 + spec version gate via FR8/FR46) is uncharted, with no agentguard code to consult. See Phase 1 Estimation Risk Register above.

### ADR backlog status (companion sidecars)

Two ADR backlog sidecars feed the Architectural Influences Catalog step:

- `_bmad-output/planning-artifacts/adr-backlog-from-prd.md` — 10 PRD-originated ADRs (working IDs ADR-005..014 in the PRD sidecar's namespace).
- `_bmad-output/planning-artifacts/adr-backlog-from-architecture.md` — 7 active architecture-originated ADRs (working IDs ADR-A1/A2/A3/A5/A6/A7/A8; ADR-A4 retired 2026-05-17).

Final agenteval ADR numbering after Architectural Influences Catalog authoring:
- agenteval ADR-001: Architectural Influences Catalog (catalogs ~14 reviewed agentguard patterns among other references; each evaluated on merit)
- agenteval ADR-002..011: 10 PRD-originated ADRs (renumbered from PRD sidecar)
- agenteval ADR-012..018: 7 architecture-originated ADRs (renumbered from architecture sidecar; ADR-A4 retired)

Total: 18 distinct agenteval-numbered ADRs in `docs/adr/`, of which 1 (the catalog) annotates ~14 reviewed agentguard patterns.

## Starter Template Evaluation

### Primary Technology Domain

**Python Robot Framework PyPI library** (per PRD `## Project Classification`: `developer_tool`; `pyproject.toml` + `uv` + `hatchling` per `## Developer Tool — Specific Requirements > Language & Platform Compatibility Matrix`).

The conventional starter-template landscape (web frameworks, mobile, full-stack, API generators) does not apply. The relevant starter options for a Python RF library are:

| Option | What it provides | Fit for agenteval |
|---|---|---|
| `uv init --lib robotframework-agenteval` | Bare-minimum Python package skeleton (`pyproject.toml`, `src/`, `tests/`, basic CI nothing) | Trivial; provides nothing agenteval-specific. Could be a fallback if Structure A is rejected later. |
| `cookiecutter-robotframework-library` (if it exists) | Generic RF library skeleton (`@keyword`-decorated class, `libdoc` setup, basic tests) | Not specific to agent-eval; would not include `_assertions/` kernel, OTel listener entry-point, `providers/` Protocol, `stats/`, `_kernel/`, conformance suite, ADR pattern. Misses ~80% of the agenteval-specific structure. |
| **`robotframework-agentguard` as a reviewed project layout reference** | Project layout reference from a related project by the same maintainer: sub-library layout shape, pyproject.toml conventions, RF Listener v3 entry-point pattern, 3-tier test layout, ADR directory convention, `MAINTAINERS.md`/`CONTRIBUTING.md`/`SUPPORT.md`/`SECURITY.md` skeletons. agenteval may borrow, adapt, or diverge from any of these. | **Selected as a starting reference** (one of several reviewed). agenteval implements its own layout informed by this and other prior art. |
| Greenfield from scratch (no template) | Total freedom; total work | Rejected — wastes solo + AI-agent-assisted maintainer capacity when reviewed prior art is available. |

### Selected Starter: agentguard reviewed as a project-layout reference (agenteval is independent)

**Rationale for selection:**

- **Reviewed prior art available.** Step-1 architectural-relationship decision locked Structure A: agenteval is its own product; agentguard is one inspiration / pattern source among others. Reviewing agentguard's repo layout costs less than greenfield + gives a fast starting reference; agenteval is free to diverge on any choice.
- **Reference project authored by the same maintainer (Many).** No external dependency risk; pattern review is intentional and pre-vetted.
- **Covers a useful chunk of agenteval's structural starting points**: `src/AgentEval/` (different package name); `_assertions/`, `providers/`, `telemetry/`, `stats/`, `mcp/`, `skills/`, `hooks/`, `subagents/`, `coding_agent/`, `judge/` sub-library names (agenteval reorganizes per PRD `## Product Scope > MVP > Module layout`); `tests/{unit,integration,acceptance}/`; `pyproject.toml` shape; `.github/workflows/` cadence; `docs/adr/` pattern; `examples/` numbered RF files. agenteval evaluates each on merit.
- **Phase 1 first story per implementation readiness report.** `implementation-readiness-report-2026-05-16.md` Section 5 (Issue 3 — greenfield setup gap) flagged that no PRD FR captures the project-bootstrap work. This Starter step's selection closes that gap by formalizing the bootstrap process: review agentguard layout, set up independent repo, write the agenteval-specific kernel modules.
- **No web search needed.** agentguard's repo structure was empirically inspected during Step-1 reconciliation (the subagent read pyproject.toml, library.py, providers/base.py, telemetry/otel_listener.py, _assertions/adapter.py, stats/*.py). The structure is known.

**Initialization Command (per Phase 1 Story 1.1 — to be authored at `/bmad-create-epics-and-stories`):**

```bash
# Conceptual sequence; exact mechanics are an implementation detail of Epic 1 Story 1.
# agentguard is a REFERENCE for layout, not a code source. agenteval implements its own modules,
# free to diverge wherever a different shape serves agenteval better.

uv init --lib robotframework-agenteval

# Then, informed by patterns reviewed in agentguard (and other references — wolfeidau/mcp-evals,
# lastmile-ai/mcp-eval, OpenTelemetry GenAI semconv), write agenteval's own:
#   - pyproject.toml — agenteval's deps + extras matrix per FR Extras Matrix, pinned per NFR-COMPAT-*
#   - src/AgentEval/library.py — agenteval's own DynamicCore composition (shape borrowed from agentguard ADR-003)
#   - src/AgentEval/_assertions/, providers/, telemetry/, stats/ — agenteval's own modules; may borrow shape from agentguard, may diverge
#   - src/AgentEval/_kernel/ (new directory per ADR-A1/A2/A5/A6)
#   - src/AgentEval/errors.py (per ADR-A3)
#   - src/AgentEval/security/protocols.py (per ADR-A8)

# Optional: clone agentguard for read-only reference review during implementation.
# git clone --depth 1 https://github.com/manykarim/robotframework-agentguard /tmp/agentguard-ref
# DO NOT cp from /tmp/agentguard-ref into agenteval; write agenteval's modules ourselves.
```

**Architectural Decisions Informed by Reviewing the agentguard Layout (agenteval evaluates each on merit):**

**Language & Runtime:**

- Python ≥3.12 (per NFR-COMPAT-01).
- `uv` package manager + `hatchling` build backend.
- `pyproject.toml` only — no `setup.py`, no `requirements.txt`.

**Robot Framework integration:**

- `[project.entry-points."robot.listener"]` declares the OTel listener.
- `robotframework-pythonlibcore>=4.5` for `DynamicCore` composition.
- `robotframework-assertion-engine>=4.0,<5.0` for getter+matcher idiom.
- `libdoc`-generated keyword reference.

**Testing framework:**

- 3-tier test layout per NFR-REL-01/02/03:
  - `tests/unit/` — pure functions, Mock provider only, always-CI (`pytest`).
  - `tests/integration/` — `@pytest.mark.live` with real LiteLLM/MCP, nightly cron.
  - `tests/acceptance/` — `.robot` suites tagged `smoke`/`tier1`/`tier3`.
- `tests/conformance/` (NEW per ADR-A7) — per-AC test files + per-adapter parametrize + fixtures + harness.

**Linting / Formatting:**

- `ruff` (linter + formatter).
- `mypy` (type checker).
- `robotframework-tidy` (.robot file formatter).

**Build tooling:**

- `uv build` produces wheel + sdist via `hatchling`.
- `uv publish` with GitHub Actions OIDC trusted publishing (no PyPI tokens in CI).

**Project structure & organization:**

- `src/AgentEval/` package root (agenteval's own package; the directory-layout shape is informed by agentguard's layout review).
- 12 sub-libraries per PRD `## Product Scope > MVP`: `_assertions/`, `providers/`, `coding_agent/`, `telemetry/`, `mcp/`, `skills/`, `hooks/`, `subagents/`, `scenarios/`, `metrics/`, `stats/`, `judge/`.
- **NEW** `src/AgentEval/_kernel/` directory (per ADR-A1/A2/A5/A6 — `run_async.py`, `discovery.py`, `guardrails.py`, `coverage.py`).
- **NEW** `src/AgentEval/errors.py` (per ADR-A3 — error class hierarchy).
- **NEW** `src/AgentEval/security/protocols.py` (per ADR-A8 — `SandboxBackend` Protocol + `NullSandbox` default).

**Development experience:**

- VS Code + Robot Framework Language Server extension (per PRD `## Developer Tool — Specific Requirements > IDE Integration & Tooling`).
- `libdoc` HTML auto-generated per release.
- `examples/` numbered `.robot` files (01–N) ordered by progressive complexity.

**Documentation pattern:**

- `README.md` — single-page pitch + 30-line quickstart.
- `docs/keywords/` — auto-generated libdoc.
- `docs/adr/` — Architectural Decision Records (18 entries: Architectural Influences Catalog + 10 PRD-original + 7 architecture-original; ADR-A4 retired 2026-05-17).
- `docs/contracts/` — 7 contract docs (5 PRD-named + 2 architecture-introduced per ADR-A3/A6; agentguard-inheritance.md retired 2026-05-17).
- `docs/scenarios/` — annotated YAML scenario examples.
- `CHANGELOG.md` — Keep-a-Changelog, semver.

**Release & versioning:**

- Semver: pre-1.0 (`0.x.y`) during Phase 1 (breaking changes minor-bump per NFR-MAINT-03).
- `uv build` → PyPI via OIDC trusted publishing.
- CI matrix: Python 3.12 + 3.13 on Linux + macOS for unit + acceptance-smoke + acceptance-tier1; nightly cron for `@live` + tier3.
- (Drift-check CI per ADR-A4 / NFR-MAINT-06 was RETIRED 2026-05-17 when agentguard was reframed from dependency to inspiration; no drift-check is needed because there is no dependency to drift-check.)

### Considered Alternatives (documented for completeness)

**Alternative 1: `cookiecutter-robotframework-library` (or similar generic RF library cookiecutter):**

- **Rejected.** Provides bare RF library scaffolding only — no `_assertions/` kernel pattern, no `LLMProviderAdapter` Protocol, no OTel listener, no `stats/` primitives, no conformance suite, no `docs/adr/` ADR convention. Would replicate ~80% of agenteval's specific structure from scratch. Time cost: weeks of scaffolding work that agentguard already did.

**Alternative 2: `uv init --lib` bare-minimum:**

- **Rejected.** Provides only `pyproject.toml` + `src/` + empty `tests/`. Strictly inferior to Alternative 1 for agenteval-specific needs.

**Alternative 3: Greenfield from scratch (no reference review):**

- **Rejected.** Highest cost; lowest reuse of available prior art. Solo + AI-agent-assisted maintainership (NFR-MAINT-01) cannot afford this level of bootstrap work when reviewed references are available.

**Alternative 4: Structure B (agenteval depends on agentguard as PyPI dep):**

- Considered at Step-1, rejected (per Step-1 decision frontmatter). Would have made `pip install robotframework-agenteval` pull `robotframework-agentguard` transitively; couples release cadence; requires agentguard to be published as ≥1.0 (currently pre-1.0). Structure A (independent implementation) explicitly chosen.

### Note: Project initialization using this starter should be Phase 1 Story 1.1

Per `implementation-readiness-report-2026-05-16.md` Section 5 Issue 3 (greenfield setup gap), the epic author (`/bmad-create-epics-and-stories` downstream) MUST add a Foundation Epic with this initialization as Story 1.1:

> **Story 1.1 — Set up independent project (informed by agentguard layout review).**
>
> Acceptance Criteria:
> - `src/AgentEval/library.py` exists with `class AgentEval(DynamicCore)` (lazy-import loop shape borrowed from agentguard).
> - `src/AgentEval/_kernel/` directory contains `run_async.py`, `discovery.py`, `guardrails.py`, `coverage.py` skeletons (Protocol shells; implementations Phase 1 Story 1.2+).
> - `src/AgentEval/errors.py` contains `AgentEvalError` base + 4 sub-bases + 9 leaf classes (per ADR-A3).
> - `src/AgentEval/security/protocols.py` contains `SandboxBackend` Protocol + `NullSandbox` default (per ADR-A8).
> - `pyproject.toml` declares deps (per NFR-COMPAT-*) + extras (per FR Extras Matrix) + `[project.entry-points."robot.listener"]` + `[project.scripts]` for `agenteval init` / `agenteval new-adapter`.
> - `.github/workflows/` contains `ci.yml` (Python 3.12+3.13 × Linux+macOS matrix). (Previously listed `agentguard-drift-check.yml`; retired 2026-05-17 — replaced by `security-scan.yml` (CodeQL) to keep workflow count at 7.)
> - `docs/adr/` contains 10 ratified ADRs from `adr-backlog-from-prd.md` + 7 from `adr-backlog-from-architecture.md` + 1 Architectural Influences Catalog (agenteval ADR-001) — total 18 ADRs in renumbered agenteval namespace.
> - `docs/contracts/` contains 7 contract docs (5 PRD-named + 2 architecture-introduced; agentguard-inheritance.md retired 2026-05-17).
> - `MAINTAINERS.md`, `CONTRIBUTING.md`, `SUPPORT.md`, `SECURITY.md`, `CHANGELOG.md` exist with content.
> - `tests/conformance/__init__.py` + `harness.py` exist (per ADR-A7); first per-AC test file as scaffolding for Phase 1 Story 1.2+ to fill in.
> - `examples/00_setup.robot` runs green against bundled echo MCP server with `uv run robot examples/00_setup.robot` after `uv sync`.

## Core Architectural Decisions

### Decision Priority Analysis

**Already decided (no re-litigation here):**

- All Step-1 architectural-relationship decisions (Structure A / Hybrid ADR scheme / Sandbox Phase 1).
- All Step-2 cross-cutting concern resolutions (11 concerns reclassified + 3 new + ADR-A1..A8 formalized).
- All Step-3 starter-template decisions (agentguard skeleton via Structure A code-copy).
- All PRD-originated ADRs (10 in `adr-backlog-from-prd.md`).
- All NFR-driven design constraints (database, auth, frontend = N/A per library product; infrastructure = PyPI + uv + GitHub Actions OIDC).

**Critical decisions (block sub-library implementation; settled in this step):**

1. **Tier annotation mechanism** — `@tier(N)` decorator (Decision-1 below).
2. **Trace store data model** — OTel SDK `InMemorySpanExporter` + custom accessor wrapper (Decision-2 below).
3. **Phase 1 estimation risks #1 + #2** — both spike-resolved in Phase 1 Week 1 (Decision-3 below).
4. **Conformance suite fixture format** — JSON files + `jsonschema` validation (Decision-4 below).

**Important decisions (shape architecture; deferred to later steps or to spike outputs):**

- Specific MCP observer implementation (middleware vs subclass) — emerges from Decision-3's spike.
- Specific per-test MCP cleanup mechanism — emerges from Decision-3's spike.
- Sub-library internal module decomposition — handled at `/bmad-create-epics-and-stories` per-sub-library story breakdown.

**Deferred decisions (post-MVP, Phase 2+):**

- OTLP exporter endpoint configuration ergonomics (Phase 2 per FR33b).
- Multi-judge ensemble + calibration methodology (Phase 2 per FR48 + agentguard ADR-011).
- LangGraph / CrewAI / AutoGen bridge adapter shapes (Phase 3 per PRD `## Product Scope > Vision`).

---

### Decision 1: Tier Annotation Mechanism

**Decision:** `@tier(1|2|3)` decorator factory in `agenteval/_kernel/tier.py`. Decorator sets a `_agenteval_tier: int` attribute on the wrapped method.

**Implementation surface (~30 LoC kernel module):**

```python
# agenteval/_kernel/tier.py
from typing import Callable, Literal, TypeVar

F = TypeVar("F", bound=Callable)
Tier = Literal[1, 2, 3]

def tier(level: Tier) -> Callable[[F], F]:
    """Annotate a keyword method with its tier (1=static, 2=LLM-deterministic, 3=agent-non-deterministic)."""
    if level not in (1, 2, 3):
        raise ValueError(f"tier must be 1, 2, or 3; got {level}")
    def _decorator(fn: F) -> F:
        fn._agenteval_tier = level
        return fn
    return _decorator

def get_keyword_tier(fn: Callable) -> Tier | None:
    """Read the tier annotation from a keyword method; returns None if unannotated."""
    return getattr(fn, "_agenteval_tier", None)
```

**Cascading implications:**

- `agenteval/_assertions/adapter.py` `assert_value()` reads tier via `get_keyword_tier()`; raises `PollingDisallowedError` if `tier >= 2` and `polling=` is passed (per ADR-A3 → AgentEvalIntegrityError sub-base). Mirrors agentguard `_assertions/adapter.py:101-105` exactly.
- **Tier-annotation enforcer location ratification (Story 1b.3 code-review amendment).** The pre-Story-1b.3 wording placed the `@tier()`-annotation validator at `agenteval/_kernel/discovery.py` raising `KeywordTierMissingError(AgentEvalIntegrityError)` at library import. Story 1b.3's create-story drift-check decision D7 + the code-review citation-drift re-derivation (Codex catch) both surfaced that this responsibility is better-scoped to Story 1b.6 (Determinism Contract + conventions module), where the rest of the convention-enforcer machinery lives. The amended location is `agenteval/_kernel/conventions.py` (Story 1b.6 scope); `discovery.py` (Story 1b.3) handles only entry-points discovery + adapter resolution. Conformance suite still asserts this gate exists — just at the Story-1b.6-amended location.
- `agenteval.cli.libdoc_extras` (or similar) reads tier from `get_keyword_tier()` to render libdoc HTML tier badge per FR30a.
- `Get Keyword Tier <keyword_name>` introspection keyword (FR30a) returns the tier via `get_keyword_tier()`.
- `Get Keyword Tier` itself is Tier 1 (pure metadata read; deterministic).

**Alternatives rejected** (per Step-4 question rationale): per-method `@keyword(tier=)` extension (couples to pythonlibcore upstream); class-level tier (forces sub-library splits); metadata dict (disconnected from definition, drift risk).

---

### Decision 2: Trace Store Data Model

**Decision:** OpenTelemetry SDK `InMemorySpanExporter` as the underlying store, wrapped by `agenteval/_kernel/trace_store.py` with per-test-id indexing + projection accessors.

**Implementation surface (~120 LoC kernel module):**

- `TracerProvider` configured at library `__init__(telemetry=True)` (default on per FR33a). Per-test scope: a `TestIdContextSpanProcessor` (added by Story 5.1's Listener at `src/AgentEval/telemetry/listener.py`) stamps `agenteval.test_id` on every span at `on_start` by reading `_kernel/context.current_context().test_id`. (Story 5.1 code-review Auditor M1 fix 2026-05-20: pre-edit said "TracerProvider configured with custom resource attributes" but OTel SDK Resource attributes are IMMUTABLE per-provider; the SpanProcessor-stamping path is the canonical Phase-1 design + `_kernel/trace_store._span_test_id` falls back to span attributes per Story 1b.2 H_R2.)
- `_kernel/trace_store.py` exposes:
  - `get_run_spans(test_id: str) -> list[ReadableSpan]` — all spans tagged with the given test_id.
  - `get_tool_calls(test_id: str, source: Literal["adapter", "hosted_mcp", None] = None) -> list[ToolCallTrace]` — projection of `execute_tool` spans into `ToolCallTrace` Pydantic dataclasses (per FR35); `source` filter optional.
  - `get_usage(test_id: str) -> Usage` — sum of `gen_ai.usage.*` attributes across `chat` spans.
  - `get_latency(test_id: str) -> float` — sum of span durations.
  - `get_run_manifest(test_id: str) -> RunManifest` — assembled per FR39 from resource attributes + library version + redaction-policy hash.
- Backend dispatch in `agenteval/telemetry/`:
  - `memory` backend (default) — keeps InMemorySpanExporter state for the RF run; cleared per-test on `start_test`.
  - `jsonl` backend (Phase 1) — serializes InMemorySpanExporter spans to `${OUTPUT_DIR}/agenteval/trace__<suite>__<test>.jsonl` on `end_test` via custom JSON formatter producing OTLP-compatible JSON shape.
  - `otlp` backend (Phase 2 via `[otlp]` extra) — swaps `InMemorySpanExporter` for `OTLPSpanExporter`; configured via `__init__(trace_backend="otlp", otlp_endpoint=...)`.

**Cascading implications:**

- All `Metric.*` keywords (FR19-22) read from `_kernel/trace_store` via the projection accessors — no direct span access by sub-libraries.
- `RunManifest` Pydantic dataclass (per FR39) is constructed from trace store metadata, not separately collected.
- Credential redaction (NFR-SEC-01 / FR38a) intercepts at the span-attribute level via a custom OTel `SpanProcessor` chain: `RedactionProcessor` → `InMemoryExporter`. Single choke point per `agenteval/_kernel/redaction.py`.
- `Mock` provider for unit tests configures a `Mock` `TracerProvider` that records spans without OTel SDK overhead; conformance suite uses this for deterministic span-shape assertions.
- OTLP migration in Phase 2: change `__init__` argument; no API change to consumer sub-libraries (projection accessors stay identical).
- Per-test scope cleanup: `start_test` clears InMemorySpanExporter state (or scopes new TracerProvider per test if Decision-3 spike picks per-test TracerProvider).

**Alternatives rejected:** custom dict-based store (re-implementation cost; OTLP double-emission); Pydantic-first with OTel adapter (extra layer; deeper agentguard divergence).

---

### Decision 3: Phase 1 Estimation Risks #1 + #2 — Spike Both in Phase 1 Week 1

**Decision:** Foundation Epic in Phase 1 includes 2 spike stories scheduled for Week 1, BEFORE sub-library implementation begins.

**Story 1.2 — Spike: Hosted-MCP Universal Trace Observer (5-day budget).**

Spike goal: determine whether `mcp` Python SDK exposes a clean middleware/interceptor API for server-side observation, OR whether custom MCP server subclass with protocol-layer re-implementation is required.

Acceptance criteria:
- Spike branch contains a working prototype of the chosen approach observing `tools/call` invocations server-side against the bundled echo MCP server fixture.
- Prototype documents the API surface used (middleware hook OR custom subclass + which methods overridden).
- Spike output is an ADR amendment (new ADR-A9 or update to ADR-A7) locking the approach.
- Estimated effort for full Phase 1 implementation of FR35 + FR40 is within ±20% (i.e., "we can plan around this number"). If estimate is >5 weeks, trigger Phase 1.5 hardening sprint (per Risk Mitigation: "Phase 1 slip beyond +50% buffer").

**Story 1.3 — Spike: Per-Test MCP Server Cleanup under `pabot` (3-day budget).**

Spike goal: validate that Listener v3 `start_test` / `end_test` hooks reliably spawn + clean up MCP server subprocesses under `pabot --processes 8` parallel execution; identify zombie-process / SIGTERM-race conditions; benchmark cleanup latency.

Acceptance criteria:
- Spike branch contains a working `pabot --processes 8` fixture with 16 tests each spawning + cleaning up a mock MCP server (intentionally slow-starting via `time.sleep(2)`).
- Zero zombie processes after a 5-run smoke loop.
- Cleanup median latency ≤500ms; max ≤2s.
- If Listener v3 hooks prove unreliable (e.g., `end_test` not firing on test timeout), spike pivots to context-manager-per-test pattern + `atexit` fallback (alternative from the Step-4 question).
- Spike output is an ADR amendment locking the cleanup mechanism.

**Cascading implications:**

- Sub-library work (Tier 1 + 2 keywords, metric keywords, adapter implementations) can proceed in parallel during Week 1 while spikes run — they don't depend on MCP observer/cleanup mechanics for their internal logic.
- Spike outcomes become inputs to Stories 1.4+ (Phase 1 MCP-touching work).
- Architecture document gets two new ADRs (or amendments) appended at end of Week 1.
- If spikes land at "worst case" — Foundation Epic re-baselines + Phase 1.5 hardening sprint scheduled.

**Alternatives rejected:** commit-to-defaults-now (optimistic; risks late-Phase-1 rework); commit-to-pessimistic-now (over-engineered if best case works).

---

### Decision 4: Conformance Suite Fixture Format

**Decision:** JSON files validated by `jsonschema` against `tests/conformance/fixture-schema.json`; loaders return Pydantic `ConformanceFixture` instances.

**Implementation surface (~80 LoC test infrastructure):**

- `tests/conformance/fixture-schema.json` — JSON Schema (draft-07) defining the strict shape:
  - `adapter_name: str` (required)
  - `scenario_name: str` (required)
  - `agent_run_result: object` — schema for `AgentRunResult` with all required metadata fields per FR36a/b.
  - `expected_tool_calls: array` — per ADR-A7 / AC-CONFORMANCE-01.
  - `expected_errors: array` — for truncation-injection scenarios per AC-CONFORMANCE-02.
  - `reproducibility_footer: object` — per FR39.
- `tests/conformance/loader.py` — `load_fixture(path: Path) -> ConformanceFixture` validates against schema + returns Pydantic instance.
- `tests/conformance/fixtures/<adapter>/<scenario>.json` — fixture files. Phase 1 initial set:
  - `generic/echo_simple.json`, `generic/echo_truncated.json`, `generic/echo_external_mcp.json`
  - `claude_code_cli/echo_simple.json`, `claude_code_cli/echo_truncated.json`, `claude_code_cli/echo_external_mcp.json`
- `docs/contracts/conformance-fixture-format.md` (NEW — adds to NFR-MAINT-04 doc list; total now **9 contracts**) — documents schema + fixture-authoring guide for community adapter authors.

**Cascading implications:**

- All `tests/conformance/test_ac_*.py` files (per ADR-A7) parametrize over fixtures loaded via `loader.load_fixture()`.
- Community adapter authors can produce fixtures in any language that outputs JSON; conformance suite is cross-language by design.
- Schema drift = breaking change (semver minor-bump per NFR-MAINT-03); schema version in fixture (e.g., `"_schema_version": "1.0"`) enables backward-compat loading.
- Truncation-injection harness (per AC-CONFORMANCE-02) consumes `expected_errors` array from fixtures to assert correct error class + `error_code` field per ADR-A3.
- Fixture authoring tooling: `agenteval new-fixture <adapter> <scenario>` CLI subcommand (added to `agenteval new-adapter` per FR18) — Phase 2 scaffolding extension.

**Alternatives rejected:** Python data classes (not cross-language; harder to diff); pytest-snapshot/syrupy (opaque to humans; no structural enforcement).

---

### Decision Impact Analysis

**Implementation sequence (Phase 1 Foundation Epic):**

1. **Story 1.1** — Set up project from agentguard skeleton (per Step-3; closes greenfield gap).
2. **Story 1.2** — Spike: Hosted-MCP universal trace observer (Decision-3; Week 1).
3. **Story 1.3** — Spike: Per-test MCP server cleanup under pabot (Decision-3; Week 1, parallel with 1.2).
4. **Story 1.4** — `agenteval/_kernel/tier.py` decorator factory + `Get Keyword Tier` introspection (Decision-1).
5. **Story 1.5** — `agenteval/_kernel/trace_store.py` OTel wrapper + projection accessors (Decision-2).
6. **Story 1.6** — `tests/conformance/fixture-schema.json` + `loader.py` + first 6 fixtures (Decision-4).

Stories 1.4-1.6 can run in parallel with Stories 1.2-1.3 (different surfaces). All Foundation work targets Week 2 end for completion; sub-library implementation begins Week 3.

**Cross-component dependencies:**

| Decision | Depends on | Enables |
|---|---|---|
| #1 Tier annotation | (none — kernel) | `_assertions/adapter.py` ACL gates; libdoc tier badges; conformance assertions |
| #2 Trace store | OTel SDK; `_kernel/redaction.py` SpanProcessor | All `Metric.*` keywords; FR39 RunManifest; JSONL backend; Phase 2 OTLP |
| #3a MCP observer (post-spike) | `mcp` Python SDK middleware OR subclass mechanism | FR35 hosted-MCP observation; FR10a/b Tool Discoverability |
| #3b MCP cleanup (post-spike) | Listener v3 hooks OR context-manager pattern | FR40 per-test scope; AC-MCP-OBSERVE-03; NFR-PERF-05 parallel testing |
| #4 Fixture format | `jsonschema` lib + Pydantic | All conformance suite tests; community adapter authoring |

**New documentation contracts triggered by these decisions (1 added):**

- `docs/contracts/conformance-fixture-format.md` (per Decision-4). NFR-MAINT-04 contract list grows from 8 to **9**.

**New error classes (none beyond ADR-A3):**

- All errors required by these decisions already exist in the ADR-A3 hierarchy. `KeywordTierMissingError` (raised by Decision-1's discovery validation) extends `AgentEvalIntegrityError` per ADR-A3 sub-base; one new leaf added to the hierarchy.

**Architecture-level NFR introductions: none.** (NFR-MAINT-06 drift-check CI was introduced in Step-2 but RETIRED 2026-05-17 — no longer applicable; no new NFRs from Step-4 decisions either.)

### Step-4 Ratification Delta (2026-05-17)

Append-only delta. Story 0.3 ratified 3 spike-dependent ADRs after D5 reproduction by 3 agents (Codex / Copilot / Sonnet):

- **ADR-004 (was ADR-007) — Hosted-MCP Universal Trace Observation** — `docs/adr/ADR-004-hosted-mcp-observation.md`. Decision AMENDED with handler-wrap at `Server.request_handlers[CallToolRequest]` (a third option not in original ADR text — neither middleware nor subclassing). No deviation from Decision-3 defaults; Epic 5 Story 5.2 estimate 2.4 weeks, within ±20% gate.
- **ADR-016 (was ADR-A6) — MCP Coverage Detection Default** — `docs/adr/ADR-016-mcp-coverage-detection-default.md`. Decision AMENDED with D1 trust-floor (strongest complete path wins) + D4 adapter contract (Claude Code CLI / Copilot CLI / Generic LiteLLM detection split). Safe-default principle preserved.
- **ADR-018 (was ADR-A8) — Sandbox Phase 1 Policy** — `docs/adr/ADR-018-sandbox-phase-1-policy.md`. Original proposed text ratified verbatim. Cross-cutting notes about MCP lifecycle integration are forward-references for Phase 3, not amendments to ADR-A8's substance. Real-sandbox-backend lifecycle (Docker / gVisor / real-rf-mcp) deferred to Phase-3 spike when backends ship.

FR65 exit criterion satisfied for the spike-dependent slate. Story 1a.3 ratifies the remaining 15 non-spike ADRs. No `proposed` ADRs remain on Story 1b.1 / 3.1 / 5.1 critical path.

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**12 critical conflict points identified** where AI agents writing different parts of agenteval could make divergent choices that cause integration problems. Each pattern below has: (1) the **Rule**, (2) a concrete **Example**, (3) a typical **Anti-Pattern** to avoid.

### Keyword Naming Conventions

**Rule (per AC-SIMPLICITY-02):** Sub-library keywords use `<Prefix>.Get <NounPhrase>` for getters, paired with optional AssertionEngine matchers. Core keywords (no prefix) may use `<NounPhrase> Should <VerbPhrase>` ergonomic form AND MUST have a paired `Get <NounPhrase>` getter. Sub-library prefix is ≤8 chars, pronounceable, capitalized: `MCP.`, `Skill.`, `Hook.`, `Subagent.`, `Stat.`, `Metric.`, `Judge.`, `Scenario.`.

**Example (sub-library, AC-SIMPLICITY-02a):**
```robot
${tools}=    MCP.Get Tools    ${HANDLE}
MCP.Get Tool Names    ${tools}    contains    search_database
```

**Example (core, AC-SIMPLICITY-02b paired):**
```robot
# Ergonomic form:
Tool Call Should Have Occurred    ${run}    search_database
# Programmatic form (paired getter):
${calls}=    Get Tool Calls    ${run}
Should Contain    ${calls}    search_database
```

**Anti-pattern:**
```robot
# ❌ Sub-library Should Be (violates AC-SIMPLICITY-02a — sub-libraries are getter+matcher only):
MCP.Tool Should Be Discoverable    search_database    ...
# Correct: MCP.Get Tool Discoverability ... + AssertionEngine operator
```

CI enforcement: conformance suite `test_ac_simplicity_02_keyword_idiom.py` introspects `DynamicCore` keyword registry; asserts no sub-library `Should *` keywords exist; asserts every core ergonomic `Should *` has a paired `Get *`.

**Phase-1 documented carve-out (ratified Story 2.1 code-review 2026-05-19, Codex C5 catch):**

PRD FR2 (L1487) explicitly names `Should Be Valid Frontmatter` as the AssertionEngine matcher paired with `Skill.Get Frontmatter`. ADR-022 catalog row (`docs/adr/ADR-001-architectural-influences-catalog.md` L87) defers AssertionEngine adoption to Phase-2. Phase-1 therefore ships `Should Be Valid Frontmatter` on the `Skill` sub-library as a plain `@keyword`-decorated function (no AssertionEngine wiring). This is a TIME-BOXED deviation from the anti-pattern above, scoped to Phase-1 only; Phase-2 re-wires it as the proper AssertionEngine matcher per the canonical contract.

The CI enforcement conformance test `test_ac_simplicity_02_keyword_idiom.py` is currently SKIPPED (one of the 11 conformance skips at end-of-Epic-1b); it is the right test to assert the carve-out's expiry once Phase-2 lands. Sibling future Phase-1 carve-outs (other `Should *` sub-library keywords) MUST be enumerated here AND tied to a Phase-2 ratification story before being shipped.

Carve-out registry (extend per story):
- `Skill.Should Be Valid Frontmatter` (Story 2.1; Phase-2 conversion target: Epic 6 Story 6.x AssertionEngine adoption, OR retire if PRD FR2 is amended).

### Module Organization Within Sub-libraries

**Rule:** Each sub-library directory under `src/AgentEval/<name>/` contains:
- `library.py` — the user-facing keyword class (decorated methods only; minimal logic).
- `_internal.py` — implementation helpers; not exposed via `@keyword`.
- `types.py` — Pydantic models / dataclasses scoped to this sub-library.
- `__init__.py` — re-exports the keyword class for the top-level `DynamicCore` to find.

**Example (`src/AgentEval/mcp/`):**
```
src/AgentEval/mcp/
├── __init__.py          # from .library import MCPKeywords
├── library.py           # class MCPKeywords: @keyword decorated methods
├── _internal.py         # _negotiate_version(), _parse_server_config(), etc.
└── types.py             # MCPToolSchema, MCPServerConfig, MCPToolResult
```

**Anti-pattern:** Logic-heavy `library.py` with private helpers as `_method()` on the class; spreading types across multiple files; circular imports between sub-libraries.

### Cross-Sub-library Import Discipline

**Rule:** Sub-libraries import FROM `agenteval/_kernel/*` and `agenteval/_assertions/*` and `agenteval/errors.py` ONLY. Sub-libraries NEVER import from each other. Cross-sub-library data flow goes through the trace store (`_kernel/trace_store.py`) or via shared types in `agenteval/types.py` (top-level shared types: `AgentRunResult`, `ToolCallTrace`, `RunManifest`).

**Example:**
```python
# src/AgentEval/metrics/library.py — OK
from agenteval._kernel.trace_store import get_tool_calls
from agenteval._assertions.adapter import assert_value
from agenteval.errors import AgentEvalIntegrityError
from agenteval.types import ToolCallTrace
```

**Anti-pattern:**
```python
# ❌ src/AgentEval/metrics/library.py
from agenteval.mcp.library import MCPKeywords  # cross-sub-library import
```

CI enforcement: custom `ruff` rule (or `import-linter`) in `pyproject.toml` defines allowed-import graph; violations fail build.

### Type Hints + Pydantic Conventions

**Rule:** Public Protocol surfaces (`LLMProviderAdapter`, `CodingAgentAdapter`, `SandboxBackend`) use `typing.Protocol` with runtime-checkable decorator. Data structures returned to users are Pydantic `BaseModel` subclasses (frozen for immutability where applicable). Internal data structures within sub-libraries may use `@dataclass(frozen=True)` if Pydantic overhead isn't justified. Type hints are mandatory on every public function/method signature; `mypy --strict` clean.

**Example:**
```python
# Public Protocol
from typing import Protocol, runtime_checkable
@runtime_checkable
class LLMProviderAdapter(Protocol):
    def chat(self, messages: list[Message], tools: list[Tool] | None = None) -> ChatResponse: ...

# Public return type
class AgentRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    messages: list[Message]
    tool_calls: list[ToolCallTrace]
    # ... per FR13/FR36

# Internal helper data
@dataclass(frozen=True)
class _SpanIndex:
    test_id: str
    span_ids: tuple[str, ...]
```

**Anti-pattern:** Plain `dict[str, Any]` returned to users; missing type hints on public signatures; mutating frozen Pydantic models via private attribute access.

### Error-Raising Conventions

**Rule (per ADR-A3):** All errors raised by the library inherit from `AgentEvalError`. Choose the appropriate sub-base (`AgentEvalSafetyError`, `AgentEvalBudgetError`, `AgentEvalCompatError`, `AgentEvalIntegrityError`). Every error class sets a static `error_code: str` class attribute matching the pattern `<DOMAIN>_<ACTION>` (uppercase). Error messages MUST include: (1) what failed, (2) why it failed if discoverable, (3) one-line remediation hint or doc link.

**Example:**
```python
class PollingDisallowedError(AgentEvalIntegrityError):
    error_code = "POLLING_DISALLOWED"

# In _assertions/adapter.py:
if polling is not None and tier >= 2:
    raise PollingDisallowedError(
        f"Polling defeats deterministic evaluation. "
        f"Use Stat.Get Pass At K to express tolerance for flakiness instead.\n"
        f"Example: ${{runs}}=  Stat.Run N Times  10  <your assertion>\n"
        f"         Stat.Get Pass At K  ${{runs}}  k=8  >=  0.8\n"
        f"See ADR-003: docs/adr/003-polling-ban.md"
    )
```

**Anti-pattern:**
```python
# ❌ Raising bare Exception
raise Exception("polling not allowed")
# ❌ No remediation hint
raise PollingDisallowedError("polling not allowed")
# ❌ Inheriting from RobotError (couples to RF internals)
class MyError(RobotError): ...
```

CI enforcement: conformance suite asserts every raised exception class has an `error_code` attribute and inherits from `AgentEvalError`.

### Async-to-Sync Bridge Convention (ADR-A1)

**Rule:** Every keyword method that calls async libraries goes through `agenteval._kernel.run_async._run_async()`. No direct `asyncio.run()` calls in sub-library code. No `async def` keyword methods. `_run_async` handles nested-event-loop fallback via worker thread.

**Example:**
```python
# src/AgentEval/mcp/library.py
from agenteval._kernel.run_async import _run_async

class MCPKeywords:
    @keyword
    @tier(1)
    def get_tools(self, handle: MCPHandle) -> list[MCPTool]:
        return _run_async(self._async_get_tools(handle))

    async def _async_get_tools(self, handle: MCPHandle) -> list[MCPTool]:
        async with handle.session() as session:
            result = await session.list_tools()
        return [_tool_from_mcp(t) for t in result.tools]
```

**Anti-pattern:**
```python
# ❌ Direct asyncio.run — breaks under nested event loops
@keyword
def get_tools(self, handle):
    return asyncio.run(self._async_get_tools(handle))

# ❌ async def keyword — RF 6.1+ async support is rough; complicates listener
@keyword
async def get_tools(self, handle):
    ...
```

CI enforcement: custom `ruff` rule scans for `asyncio.run` calls in `src/AgentEval/*/library.py`; allowed only in `_kernel/run_async.py`.

### Trace Span Naming (OTel GenAI semconv)

**Rule (per FR32 + agentguard ADR-012):** Span hierarchy follows OTel GenAI semantic conventions:
- Top-level: `invoke_agent` per agent run.
- Per-LLM-round-trip: `chat`.
- Per-tool-call: `execute_tool`.

Attributes use `gen_ai.*` namespace per OTel semconv (`gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.response.finish_reasons`, `gen_ai.tool.name`, etc.). agenteval-specific attributes prefix `agenteval.*` (e.g., `agenteval.test_id`, `agenteval.tool.success`, `agenteval.tool.duration_ms`).

**Example:**
```python
# src/AgentEval/telemetry/spans.py
def emit_tool_call_span(name: str, args: dict, result: Any, error: str | None, latency_ms: float):
    with tracer.start_as_current_span("execute_tool") as span:
        span.set_attribute("gen_ai.tool.name", name)
        span.set_attribute("gen_ai.tool.call.id", str(uuid4()))
        span.set_attribute("agenteval.tool.success", error is None)
        span.set_attribute("agenteval.tool.duration_ms", latency_ms)
```

**Anti-pattern:** Custom span names that conflict with OTel semconv (`run`, `query`, `call`); attribute names without namespace prefix; mixing `gen_ai.*` and custom names for the same concept.

**`agenteval.*` namespacing extensions** (ratified 2026-05-19 per Story 1b.2 code-review H_R11 — was implicitly cited but unratified before):

| Attribute | Type | Description | Source |
| --- | --- | --- | --- |
| `agenteval.test_id` | str | Listener v3 test identifier (set on TracerProvider Resource per Story 5.1) | architecture L652-663 |
| `agenteval.tool.success` | bool | True when the tool call returned without error | original (L984) |
| `agenteval.tool.duration_ms` | float | Tool-call wall-clock duration (milliseconds) | original (L985) |
| `agenteval.tool.source` | Literal["adapter", "hosted_mcp"] | Which observation path emitted the trace (FR35) | Story 1b.2 H_R11 ratification |
| `agenteval.tool.args` | str (JSON-encoded) | Post-redaction tool-call arguments. OTel SDK doesn't accept dict attributes, so producers JSON-serialize at emission time; `_kernel/trace_store.get_tool_calls` JSON-parses at projection time. | Story 1b.2 H_R11 ratification |
| `agenteval.tool.result` | str / int / float / bool | Post-redaction tool-call return value (primitive OTel-compatible type; complex results JSON-serialized like args). | Story 1b.2 H_R11 ratification |
| `agenteval.tool.error` | str \| None | Tool-call error message (None on success). | Story 1b.2 H_R11 ratification |
| `agenteval.tier` | Literal[1, 2, 3] | OTel-style span-attribute carrying the tier annotation; counted by `RunManifest.agenteval_tier_breakdown`. Producers emit this on every `@tier`-annotated keyword's spans (Epic 5 Story 5.1 wires the Listener-side propagation from `_agenteval_tier` decorator attribute → span attribute). | Story 1b.2 M_R5 ratification |

CI enforcement: `tests/conformance/test_otel_semconv.py` asserts emitted spans match the documented semconv contract; deviation = test failure.

### Logging Conventions

**Rule:** Use Python `logging` module. Logger name = module path (`logging.getLogger(__name__)`). Log levels:
- `DEBUG` — internal state useful for triage; not surfaced to users by default.
- `INFO` — significant lifecycle events (server start/stop, adapter loaded, test_id scope change).
- `WARNING` — `DegradedTraceWarning`, `AdapterVersionDriftWarning`, recoverable degradations.
- `ERROR` — preceding a raise of `AgentEvalError`; one log line per error path with the same `error_code` field.

Logs MUST go through `config.redact_env()` before any structured log emission to prevent credential leakage in log output (parallels NFR-SEC-01 trace redaction).

**Example:**
```python
import logging
_logger = logging.getLogger(__name__)

def _start_mcp_server(cmd, args):
    _logger.info("starting MCP server: %s %s", cmd, args)
    try:
        proc = subprocess.Popen(...)
    except FileNotFoundError as e:
        _logger.error("MCP server binary not found: %s (error_code=BINARY_NOT_FOUND)", cmd)
        raise UnsupportedBinaryVersionError(...) from e
```

**Anti-pattern:** `print()` calls; logger configured at import time (should be lazy); logging credentials/secrets directly.

CI enforcement: `ruff` rule bans `print()` in `src/AgentEval/`; custom test asserts no logger emits API-key string patterns.

### Docstring + Libdoc Convention

**Rule:** Every `@keyword`-decorated method has a docstring readable as Robot Framework documentation. Sections in order: short description (1 line) + extended description + `Arguments:` + `Returns:` + `Raises:` + `Examples:` (with `.robot` syntax). AssertionEngine matcher signature documented when applicable.

**Example:**
```python
@keyword(name="MCP.Get Tool Discoverability")
@tier(3)
def get_tool_discoverability(
    self, tool: str, by_models: list[str], with_tasks: list[str],
    k: int = 8, max_cost_usd: float = 5.0,
    assertion_operator: AssertionOperator | None = None,
    assertion_expected: float | None = None,
    message: str | None = None,
) -> float:
    """Evaluate whether an MCP tool is discovered by coding agents given natural-language tasks.

    Runs each task against each model `repeat=n_tasks*len(by_models)` times; computes Pass@k
    over the trial set; returns the discoverability score in [0, 1].

    Tier 3 (agent-non-deterministic). Cost-guarded via max_cost_usd (default $5.00 per call).
    Hosted-MCP observation collects tool-call truth server-side regardless of agent runtime.

    Arguments:
        tool: MCP tool name under test (e.g., "search_database").
        by_models: List of LiteLLM model strings (e.g., ["anthropic/claude-sonnet", "openai/gpt-4o-mini"]).
        with_tasks: List of natural-language task strings.
        k: Pass@k parameter (default 8).
        max_cost_usd: Cost guardrail per invocation (default $5.00; pre-flight + mid-run enforced).
        assertion_operator: Optional AssertionEngine operator for inline assertion.
        assertion_expected: Optional expected threshold for inline assertion.
        message: Optional custom error message for failed assertions.

    Returns:
        Discoverability score in [0, 1].

    Raises:
        CostExceededError: If projected or actual cost exceeds max_cost_usd.
        IncompleteTraceError: If mcp_coverage is "external_mixed" without allow_external_mcp_blind=True.

    Examples:
        | ${score}=    MCP.Get Tool Discoverability    tool=search_database    by_models=anthropic/claude-sonnet,openai/gpt-4o-mini    with_tasks=${TASKS}    k=8
        | MCP.Get Tool Discoverability    tool=search_database    by_models=anthropic/claude-sonnet    with_tasks=${TASKS}    k=8    >=    0.8
    """
```

**Anti-pattern:** Missing docstring; no `Arguments`/`Returns`/`Raises` sections; no `Examples` with runnable `.robot` syntax; pythonic docstring patterns (Google/Sphinx style) — RF reads plain text.

CI enforcement: `docs/keywords/` libdoc generation in CI; sample-keyword check asserts the structure exists.

### Configuration Parameter Naming

**Rule:** Library `__init__` args use `snake_case` (Python convention). Environment variables use `SCREAMING_SNAKE_CASE` prefixed `AGENTEVAL_` (e.g., `AGENTEVAL_DEFAULT_MODEL`, `AGENTEVAL_TRACE_BACKEND`, `AGENTEVAL_TELEMETRY`). `.env` file uses the same env-var names. Boolean env vars use `true`/`false` (lowercase, NOT `1`/`0` or `True`/`False`).

**Example:**
```python
library = AgentEval(
    provider="litellm",
    telemetry=True,
    trace_backend="memory",
    mcp_per_test=True,
    allow_validate_operator=False,
    max_cost_usd=5.0,
)

# Equivalent via env vars:
# AGENTEVAL_PROVIDER=litellm
# AGENTEVAL_TELEMETRY=true
# AGENTEVAL_TRACE_BACKEND=memory
# AGENTEVAL_MCP_PER_TEST=true
# AGENTEVAL_ALLOW_VALIDATE_OPERATOR=false
# AGENTEVAL_MAX_COST_USD=5.0
```

**Anti-pattern:** CamelCase env vars (`AGENTEVAL_DefaultModel`); inconsistent prefix (`MY_AGENTEVAL_*`); boolean env vars as `1`/`0` or `yes`/`no`.

CI enforcement: `tests/unit/test_config_precedence.py` asserts every `__init__` arg has a matching env var with correct naming pattern.

### Pydantic Model Field Naming

**Rule:** Pydantic model fields use `snake_case` (Python convention). When serializing to JSON (JSONL trace backend, scenario YAML, OTLP export), preserve `snake_case` — do NOT auto-camelCase. Robot Framework `.robot` scenario YAML readers expect `snake_case` keys.

**Example:**
```python
class AgentRunResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    messages: list[Message]
    tool_calls: list[ToolCallTrace]
    final_response: str  # NOT finalResponse
    metadata: AgentRunMetadata
```

**Anti-pattern:** `Field(alias="finalResponse")` for API surface (no API surface here); mixed naming across models.

### CI-Enforcement Pattern (cross-cutting)

**Rule:** Every consistency rule in this section that CAN be CI-enforced IS CI-enforced. Where the rule can be a `ruff` lint, write the lint. Where it requires a custom check, write a test in `tests/unit/conventions/test_*.py`. Where it requires conformance assertion, add to `tests/conformance/`. Documented but unenforced rules drift; enforced rules don't.

**Example checks (Phase 1 deliverable):**
- `tests/unit/conventions/test_import_graph.py` — verifies no cross-sub-library imports.
- `tests/unit/conventions/test_error_classes.py` — verifies all errors inherit `AgentEvalError` + have `error_code`.
- `tests/unit/conventions/test_no_asyncio_run.py` — scans `src/AgentEval/*/library.py` for `asyncio.run`.
- `tests/unit/conventions/test_print_banned.py` — scans `src/AgentEval/` for `print(` (allowed only in `agenteval/cli.py`).
- `tests/unit/conventions/test_config_naming.py` — verifies `__init__` arg ↔ env var naming consistency.

CI enforcement: `pytest tests/unit/conventions/ -v` runs on every PR; conventions failures block merge.

### Enforcement Guidelines

**All AI Agents writing agenteval code MUST:**

1. Follow PEP 8 + `ruff` linter rules (enforced in CI).
2. Pass `mypy --strict` on all `src/AgentEval/` code.
3. Use the `AgentEvalError` hierarchy for every raised exception.
4. Route every async-touching call through `_kernel/run_async._run_async`.
5. Annotate every keyword with `@tier(N)`.
6. Write docstrings in the documented Args/Returns/Raises/Examples format.
7. Add a `tests/unit/conventions/test_*.py` check when introducing a new pattern.

**Pattern enforcement process:**
- `ruff`, `mypy`, `tests/unit/conventions/` run on every PR (mandatory checks).
- Conformance suite runs on every release.
- New patterns added via ADR (extends `adr-backlog-from-architecture.md` or amends).
- Pattern violations not auto-fixable: PR comment + reviewer hold.

### Pattern Examples — Good vs Anti-Pattern Reference Card

A consolidated reference in `docs/contracts/coding-conventions.md` (NEW — adds 10th doc contract to NFR-MAINT-04 list) documents every pattern in this section with side-by-side good/anti-pattern examples + the CI check that enforces it.

## Project Structure & Boundaries

### Complete Project Directory Structure

```
robotframework-agenteval/
├── README.md
├── pyproject.toml                          # uv + hatchling; deps + extras matrix per FR Extras Matrix + NFR-COMPAT-*; [project.entry-points] declarations for robot.listener + 5 agenteval groups + [project.scripts] for agenteval CLI
├── uv.lock
├── ruff.toml                               # Lint + format config; custom rules per Step-5 conventions
├── mypy.ini                                # mypy --strict config per Step-5
├── .python-version                         # 3.12 (CI matrix tests 3.12 + 3.13)
├── .env.example                            # Documented env vars per FR41 + Step-5 naming convention
├── .gitignore
├── LICENSE                                 # Apache-2.0
├── CHANGELOG.md                            # Keep-a-Changelog; semver per NFR-MAINT-03
├── MAINTAINERS.md                          # Solo + AI-agent-assisted posture per NFR-MAINT-01
├── CONTRIBUTING.md                         # Per NFR-MAINT-01; "good first issue" labels + agent* portfolio docs + SubprocessAdapter ABC contributor surface
├── SUPPORT.md                              # 5-business-day triage SLA per NFR-MAINT-02
├── SECURITY.md                             # Supply-chain trust boundary per NFR-SEC-04; security disclosure process
│
├── .github/
│   └── workflows/
│       ├── ci.yml                          # PR-gating: Python 3.12+3.13 × Linux+macOS; unit + acceptance-smoke + acceptance-tier1; ruff + mypy; tests/unit/conventions/
│       ├── nightly-live.yml                # Nightly cron: tests/integration/ (@pytest.mark.live) + tests/acceptance/ tier3 tag
│       ├── conformance.yml                 # Per-release: tests/conformance/ runs against all Tier-1 adapters
│       ├── security-scan.yml               # CodeQL on every PR (standard hygiene; replaces retired agentguard-drift-check.yml)
│       ├── dogfood-integration.yml         # Per-release per NFR-REL-05: invokes rf-mcp + robotframework-agentskills CI against released wheel
│       ├── docs-build.yml                  # Per-release: libdoc + contracts docs build + asserts required sections exist (NFR-MAINT-04)
│       └── release.yml                     # Tagged release: uv build + uv publish via PyPI OIDC trusted publishing (NFR-MAINT-03)
│
├── src/
│   └── AgentEval/
│       ├── __init__.py                     # Re-exports AgentEval class + errors + public Protocols
│       ├── library.py                      # class AgentEval(DynamicCore); lazy-loaded sub-libraries (pattern borrowed from agentguard ADR-003) + ADR-A2 entry-points discovery
│       ├── errors.py                       # AgentEvalError + 4 sub-bases + 9 leaves per ADR-A3
│       ├── types.py                        # Shared top-level types: AgentRunResult, ToolCallTrace, RunManifest, AgentRunMetadata, Message, Tool, Usage
│       ├── config.py                       # Config precedence (init → env → .env → defaults) per FR41; redact_env() + add_redaction_pattern() per FR38a
│       ├── cli.py                          # agenteval CLI entry point: init / new-adapter subcommands per FR18 + FR52
│       │
│       ├── _kernel/                        # Cross-cutting kernel modules (NEW directory per Step-2 elicitation + Step-4 decisions)
│       │   ├── __init__.py
│       │   ├── tier.py                     # @tier(N) decorator + get_keyword_tier() per Decision-1
│       │   ├── trace_store.py              # OTel InMemorySpanExporter wrapper + per-test-id indexing + projection accessors per Decision-2
│       │   ├── redaction.py                # OTel SpanProcessor for credential redaction per NFR-SEC-01 / Decision-2 cascading
│       │   ├── discovery.py                # Entry-points discovery for 5 groups + plugins=[] composition per ADR-A2
│       │   ├── run_async.py                # _run_async() async-to-sync bridge per ADR-A1
│       │   ├── guardrails.py               # @guarded_fanout(estimator=) decorator for cost + runtime guardrails per ADR-A5
│       │   ├── coverage.py                 # _check_mcp_coverage() helper + IncompleteTraceError gate per ADR-A6
│       │   └── context.py                  # Listener v3 test_id propagation context helpers
│       │
│       ├── _assertions/                    # agenteval's own implementation; gating shape borrowed from agentguard, evaluated on merit
│       │   ├── __init__.py
│       │   └── adapter.py                  # assert_value() with tier+polling+validate gates (shape borrowed from agentguard ADR-022) + ADR-A6 mcp_coverage check
│       │
│       ├── providers/                      # LLMProviderAdapter Protocol (shape borrowed from agentguard ADR-001, evaluated on merit)
│       │   ├── __init__.py
│       │   ├── base.py                     # LLMProviderAdapter Protocol (runtime_checkable)
│       │   ├── litellm_adapter.py          # Default Phase 1 provider (NFR-COMPAT-05)
│       │   ├── mock.py                     # Mock provider for unit tests + contributor template
│       │   └── factory.py                  # Provider discovery via entry-points (_kernel/discovery.py)
│       │
│       ├── coding_agent/                   # CodingAgentAdapter Protocol + InProcessAdapter/SubprocessAdapter per ADR-A6
│       │   ├── __init__.py
│       │   ├── base.py                     # CodingAgentAdapter Protocol + AgentRunResult shape (uses types.py)
│       │   ├── in_process.py               # InProcessAdapter ABC (full-fidelity SDK adapters)
│       │   ├── subprocess.py               # SubprocessAdapter ABC (CLI adapters with _spawn / _parse_event / _finalize hooks; contributor-facing API per ADR-A6)
│       │   ├── generic.py                  # Generic adapter via LiteLLM (Phase 1, FR13a)
│       │   ├── claude_code_cli.py          # Claude Code CLI adapter (Phase 1, FR13b; pinned binary)
│       │   ├── claude_agent_sdk.py         # Phase 2 (FR13c, under [claude] extra)
│       │   ├── openai_agents.py            # Phase 2 (FR13d, under [openai-agents] extra)
│       │   ├── codex_cli.py                # Phase 2 (FR13e, under [codex] extra)
│       │   ├── copilot_cli.py              # Phase 2 (FR13f, under [copilot] extra)
│       │   └── factory.py                  # Adapter discovery via entry-points
│       │
│       ├── telemetry/                      # Per agentguard ADR-012 pattern (borrowed, evaluated on merit) + Decision-2
│       │   ├── __init__.py
│       │   ├── listener.py                 # RF Listener v3 entry point (registered via [project.entry-points."robot.listener"]) per FR33a. (Story 5.1 pre-create-story drift fix 2026-05-20: was `otel_listener.py` borrowing agentguard's name; ratified `docs/contracts/listener-integration.md` L17 + epics.md L1437 say `listener.py`.)
│       │   ├── spans.py                    # OTel span emission helpers (invoke_agent → chat → execute_tool) per FR32 + Step-5 semconv convention
│       │   ├── backends.py                 # memory / jsonl backends Phase 1; otlp dispatch Phase 2 per FR33b
│       │   └── semconv.py                  # Internal facade for gen_ai.* attribute names per NFR-COMPAT-06
│       │
│       ├── mcp/                            # MCP sub-library
│       │   ├── __init__.py
│       │   ├── library.py                  # MCP keywords: Get Server Config, Start/Connect/Stop Server, Get Tools, Call Tool, Get Tool Discoverability per FR5-11 + FR11b
│       │   ├── _internal.py                # _negotiate_version, _parse_server_config, _spawn_server, etc.
│       │   ├── observer.py                 # Hosted-MCP universal trace observer per FR35 + ADR-004 (Story 5.2; ratified spike Decision-3 = request_handlers dict-wrap pattern)
      │   ├── _observer_subprocess_wrapper.py  # Subprocess-bootstrap wrapper injecting observer at stdio subprocess startup per ADR-004 Consequences (Story 5.2 pre-create-story drift D-3 fix 2026-05-20: spike findings + ADR-004 mandated this file; pre-edit project tree didn't list it)
│       │   ├── transport.py                # stdio / streamable_http / in-memory transport adapters per NFR-COMPAT-04
│       │   ├── version_gate.py             # UnsupportedMCPVersionError per FR8/FR46 + ADR-011 from PRD sidecar
│       │   └── types.py                    # MCPToolSchema, MCPServerConfig, MCPToolResult
│       │
│       ├── skills/                         # Skill sub-library (Tier 1 + Phase 1 Tier 3 activation; Phase 2 Tier 2 judge)
│       │   ├── __init__.py
│       │   ├── library.py                  # Skill keywords: Get Frontmatter, Get Allowed Tools, Get Description, Get Activation Decision per FR1-2 + FR4 + Devon's Journey 4
│       │   ├── _internal.py
│       │   └── types.py                    # SkillFrontmatter, SkillActivationResult
│       │
│       ├── hooks/                          # Hook sub-library (Tier 1)
│       │   ├── __init__.py
│       │   ├── library.py                  # Hook keywords: Get Config per FR4
│       │   ├── _internal.py
│       │   └── types.py
│       │
│       ├── subagents/                      # Subagent sub-library (Tier 1)
│       │   ├── __init__.py
│       │   ├── library.py                  # Subagent keywords: Get Frontmatter per FR3
│       │   ├── _internal.py
│       │   └── types.py
│       │
│       ├── scenarios/                      # Scenario YAML loader + Run Scenario per FR15
│       │   ├── __init__.py
│       │   ├── library.py                  # Run Scenario keyword
│       │   ├── _internal.py                # YAML loader + schema validation
│       │   ├── schema.json                 # JSON Schema for scenario YAML files
│       │   └── types.py                    # ScenarioConfig, ScenarioRun, EvalSpec
│       │
│       ├── metrics/                        # Tool-call metrics per FR19-22
│       │   ├── __init__.py
│       │   ├── library.py                  # Metric keywords: Get Tool Call Count, Get Tool Hit Rate, Get Latency P95, Get Cost Total per FR19-22
│       │   ├── _internal.py                # Projection accessors that read from _kernel/trace_store
│       │   └── types.py                    # Usage, LatencyStats, CohortHeatmap (per FR55)
│       │
│       ├── stats/                          # Borrowed shape from agentguard ADR-005 statistical primitives; agenteval is free to diverge
│       │   ├── __init__.py
│       │   ├── library.py                  # Stat keywords: Run N Times, Get Pass At K per FR26-27
│       │   ├── pass_at_k.py                # HumanEval unbiased estimator
│       │   ├── mannwhitney.py              # Phase 2 (in [agenteval-advanced] extra)
│       │   ├── cliffs_delta.py             # Phase 2
│       │   ├── bootstrap.py                # Phase 2 (CI for binomial proportions; Wilson CI in Phase 1)
│       │   ├── wilson.py                   # Wilson CI for Phase 1 (no SciPy dep yet)
│       │   └── _helpers.py
│       │
│       ├── judge/                          # Phase 2 only (under [judge] extra); FR48 + pattern reviewed in agentguard ADR-011
│       │   ├── __init__.py
│       │   ├── library.py                  # Judge keywords: Get Score with rubric
│       │   ├── _internal.py                # Rubric loader, calibration helpers
│       │   └── types.py                    # JudgeRubric, JudgeScore
│       │
│       ├── security/                       # Phase 1 = policy + gate + Protocol per ADR-A8
│       │   ├── __init__.py
│       │   ├── protocols.py                # SandboxBackend Protocol (contributor-facing API per ADR-A8)
│       │   ├── null_sandbox.py             # NullSandbox default (raises SandboxRequiredError on every call)
│       │   └── policy.py                   # Sandbox policy + gate logic
│       │
│       └── reporting/                      # JUnit XML + run summary per FR49-51, FR54
│           ├── __init__.py
│           ├── junit_listener.py           # RF Listener for JUnit XML emission per FR49
│           ├── run_summary.py              # Terminal run summary per FR54
│           └── exit_codes.py               # Exit-code mapping per FR50 (uses errors.py error_code field)
│
├── tests/
│   ├── unit/                               # Always-CI per NFR-REL-01
│   │   ├── _assertions/
│   │   │   ├── test_adapter.py             # Tests assert_value() gates per ADR-A1
│   │   │   └── test_polling_ban.py         # PollingDisallowedError on Tier-2/3
│   │   ├── _kernel/
│   │   │   ├── test_tier.py
│   │   │   ├── test_trace_store.py
│   │   │   ├── test_redaction.py
│   │   │   ├── test_discovery.py
│   │   │   ├── test_run_async.py
│   │   │   ├── test_guardrails.py
│   │   │   └── test_coverage.py
│   │   ├── mcp/
│   │   ├── skills/
│   │   ├── hooks/
│   │   ├── subagents/
│   │   ├── scenarios/
│   │   ├── metrics/
│   │   ├── stats/
│   │   ├── security/
│   │   ├── reporting/
│   │   ├── providers/
│   │   ├── coding_agent/
│   │   ├── conventions/                    # Step-5 CI-enforcement pattern
│   │   │   ├── test_import_graph.py
│   │   │   ├── test_error_classes.py
│   │   │   ├── test_no_asyncio_run.py
│   │   │   ├── test_print_banned.py
│   │   │   └── test_config_naming.py
│   │   ├── test_config_precedence.py
│   │   ├── test_errors.py
│   │   └── test_library.py
│   │
│   ├── integration/                        # @pytest.mark.live, nightly CI per NFR-REL-03
│   │   ├── test_litellm_providers.py
│   │   ├── test_claude_code_cli_live.py
│   │   ├── test_mcp_stdio.py
│   │   ├── test_mcp_streamable_http.py
│   │   └── test_pabot_parallel.py
│   │
│   ├── acceptance/                         # .robot suites per NFR-REL-02
│   │   ├── smoke/
│   │   │   ├── 01_first_test.robot
│   │   │   ├── 02_static_inspection.robot
│   │   │   └── 03_polling_ban.robot
│   │   ├── tier1/
│   │   │   ├── mcp_tools.robot
│   │   │   ├── skill_frontmatter.robot
│   │   │   └── statistical_primitives.robot
│   │   └── tier3/
│   │       ├── tool_discoverability.robot
│   │       ├── skill_activation_pass_at_k.robot
│   │       └── scenario_yaml.robot
│   │
│   ├── conformance/                        # Phase 1 deliverable per FR45 + ADR-A7 + Decision-4
│   │   ├── __init__.py                     # Entry point: python -m agenteval.conformance [--adapter NAME] per FR57
│   │   ├── harness.py
│   │   ├── loader.py
│   │   ├── fixture-schema.json
│   │   ├── fixtures/
│   │   │   ├── generic/
│   │   │   │   ├── echo_simple.json
│   │   │   │   ├── echo_truncated.json
│   │   │   │   └── echo_external_mcp.json
│   │   │   └── claude_code_cli/
│   │   │       ├── echo_simple.json
│   │   │       ├── echo_truncated.json
│   │   │       └── echo_external_mcp.json
│   │   ├── test_ac_simplicity_01_evidence_block.py
│   │   ├── test_ac_simplicity_02_keyword_idiom.py
│   │   ├── test_ac_discover_01_cohort.py
│   │   ├── test_ac_discover_02_cost_guardrail.py
│   │   ├── test_ac_dogfood_01_replacement.py
│   │   ├── test_ac_conformance_01_fidelity_oracles.py
│   │   ├── test_ac_conformance_02_completeness.py
│   │   ├── test_ac_mcp_observe_01_coverage.py
│   │   ├── test_ac_mcp_observe_02_version_gate.py
│   │   ├── test_ac_mcp_observe_03_per_test_scope.py
│   │   └── test_structural_shape.py
│   │
│   ├── benchmarks/                         # Per NFR-PERF-02
│   │   ├── bench_static_inspection.py
│   │   ├── bench_mcp_handshake.py
│   │   └── bench_echo_server_startup.py
│   │
│   └── fixtures/
│       ├── mcp/
│       │   ├── echo_server.py              # Bundled echo MCP server per NFR-PERF-01 happy path
│       │   ├── heavy_simulator.py          # time.sleep(3) startup simulation for NFR-PERF-05 testing
│       │   └── future_spec_mock.py         # Mock server negotiating MCP spec 2.5.0 to verify version_gate
│       ├── skills/
│       │   ├── valid_skill.md
│       │   └── invalid_skill.md
│       └── scenarios/
│           ├── basic_eval.yaml
│           └── multi_model_discover.yaml
│
├── docs/
│   ├── README.md
│   ├── adr/                                # 18 ADRs per Hybrid scheme (Step-1); ADR-A4 retired 2026-05-17
│   │   ├── README.md
│   │   ├── ADR-001-architectural-influences-catalog.md  # Catalogs ~14 reviewed agentguard patterns among other references; each evaluated on merit
│   │   ├── ADR-002-adapter-cap-rule.md         # Was ADR-005 in PRD sidecar
│   │   ├── ADR-003-protocol-class-split.md     # Was ADR-006 in PRD sidecar
│   │   ├── ADR-004-hosted-mcp-observation.md
│   │   ├── ADR-005-conformance-suite-fidelity-oracles.md
│   │   ├── ADR-006-completeness-field.md
│   │   ├── ADR-007-mcp-coverage-incomplete-trace-error.md
│   │   ├── ADR-008-mcp-spec-version-gate.md
│   │   ├── ADR-009-per-test-mcp-scope.md
│   │   ├── ADR-010-copilot-cli-trace-strategy.md
│   │   ├── ADR-011-three-persona-model.md
│   │   ├── ADR-012-async-to-sync-bridge-kernel-module.md   # Was ADR-A1
│   │   ├── ADR-013-entry-points-discovery-infrastructure.md  # Was ADR-A2
│   │   ├── ADR-014-error-class-hierarchy.md        # Was ADR-A3
│   │   ├── ADR-015-cost-runtime-guardrail-decorator.md     # Was ADR-A5 (ADR-A4 retired 2026-05-17 — renumbered down by one)
│   │   ├── ADR-016-mcp-coverage-detection-default.md # Was ADR-A6
│   │   ├── ADR-017-conformance-suite-organization.md # Was ADR-A7
│   │   └── ADR-018-sandbox-phase-1-policy.md       # Was ADR-A8
│   ├── contracts/                          # 11 doc contracts: 9 NFR-MAINT-04/Step-4/Step-5 + 2 empirical adds (Story 1a.4 ratification 2026-05-18); agentguard-inheritance.md retired 2026-05-17
│   │   ├── evidence-block-format.md
│   │   ├── determinism-contract.md
│   │   ├── stability-surface.md
│   │   ├── exit-criteria-0x-to-1x.md
│   │   ├── otel-trace-visual.md
│   │   ├── error-class-hierarchy.md
│   │   ├── mcp-coverage-detection.md
│   │   ├── conformance-fixture-format.md
│   │   ├── coding-conventions.md           # Per Step-5 reference card
│   │   ├── listener-integration.md         # Story 0.1/0.2 empirical add — RF Library vs Regular Listener scoping
│   │   └── junit-xml-enrichment.md         # FR49 contract — empirical add 2026-05-18 by Story 1a.4 ratification
│   ├── keywords/                           # Auto-generated libdoc HTML per release
│   ├── scenarios/                          # Annotated YAML scenario examples
│   │   ├── basic.yaml
│   │   ├── tool_discoverability.yaml
│   │   └── multi_step_orchestration.yaml
│   ├── recipes/                            # Phase 1 Recipe Gallery (8 recipes per PRD Appendix)
│   │   ├── 01-first-eval-in-5-min.md
│   │   ├── 02-flaky-tests-pass-at-k.md
│   │   ├── 03-tool-discoverability-vocabulary.md
│   │   ├── 04-static-skill-validation.md
│   │   ├── 05-replace-custom-python-e2e.md  # Includes mcp_per_test="suite" trade-off matrix
│   │   ├── 06-custom-provider-adapter.md
│   │   ├── 07-first-mcp-server-test.md
│   │   └── 08-ci-integration-github-actions.md
│   ├── coming-from/                        # Migration mappings
│   │   ├── deepeval.md
│   │   └── promptfoo.md
│   └── troubleshooting/
│       └── first-day.md
│
└── examples/                               # Numbered .robot files for users
    ├── 00_setup.robot
    ├── 01_skill_validation.robot
    ├── 02_mcp_introspection.robot
    ├── 03_tool_discoverability.robot
    └── 04_run_scenario.robot
```

### Architectural Boundaries

**API Boundaries (Python-level, not network):**

| Surface | Purpose | Audience |
|---|---|---|
| Robot Framework keyword catalog | Primary user surface; consumed via `Library AgentEval` import in `.robot` files | QA Engineers + Agent Surface Authors + Agent Developers |
| `agenteval.errors`, `agenteval.types` Python imports | Programmatic catch-by-class + type hints in Python code | Contributors + advanced users wrapping the library in Python |
| `agenteval` CLI (`agenteval init`, `agenteval new-adapter`) | Bootstrap + scaffolding | All personas Day-1 |

Protocol surfaces (contributor-facing API per NFR-MAINT-01):

| Protocol | Purpose | Stability |
|---|---|---|
| `LLMProviderAdapter` (in `providers/base.py`) | Custom LLM provider integration | stable (Phase 1) |
| `CodingAgentAdapter` + `InProcessAdapter` + `SubprocessAdapter` (in `coding_agent/`) | Custom coding-agent integration | stable (Phase 1) |
| `SandboxBackend` (in `security/protocols.py`) | Custom sandbox backend (Phase 3 backends will implement this; Phase 1 ships Protocol + `NullSandbox` only per ADR-A8) | provisional (Phase 1) |

**Component Boundaries (sub-library responsibilities):**

| Sub-library | Owns | Does NOT own |
|---|---|---|
| `mcp/` | MCP transport, server lifecycle, tool calls, observation, version gate | LLM provider calls, agent orchestration, statistical analysis |
| `skills/` | Skill `.md` frontmatter parsing, activation decisions, allowed-tools validation | Generic LLM prompting, scenario orchestration |
| `hooks/` | `settings.json` hook config parsing | Hook execution (out of scope per PRD) |
| `subagents/` | Sub-agent `.md` frontmatter parsing | Sub-agent orchestration |
| `scenarios/` | YAML scenario loading + `Run Scenario` orchestration | Per-scenario adapter selection (delegates to `coding_agent/`) |
| `metrics/` | Reading from `_kernel/trace_store` and projecting to metric values | Trace span emission (lives in `telemetry/`) |
| `stats/` | Pure statistical primitives (no I/O) | Driving the runs (delegates to other sub-libraries) |
| `judge/` (Phase 2) | LLM-as-judge scoring + calibration | Provider integration (delegates to `providers/`) |
| `coding_agent/` | Agent runtime adapters + AgentRunResult emission | Trace storage (delegates to `_kernel/trace_store`) |
| `providers/` | LLM provider integration | Agent loop orchestration (delegates to `coding_agent/`) |
| `telemetry/` | Span emission + OTel listener + trace backends | Span consumption (delegates to `_kernel/trace_store`) |
| `security/` | Sandbox Protocol + NullSandbox | Sandbox backend implementations (Phase 3) |
| `reporting/` | JUnit XML + exit codes + terminal run summary | Trace storage |
| `_kernel/` | Cross-cutting helpers (no sub-library) | Sub-library-specific logic |
| `_assertions/` | AssertionEngine adapter + tier ACL gates | Sub-library-specific assertion logic |

**Cross-cutting Concern Locations** (per Step-2 architectural concerns):

| Concern | Lives in | Touched by |
|---|---|---|
| Determinism handling + tier ACL | `_assertions/adapter.py` + `_kernel/tier.py` | Every sub-library's `@tier(N)` annotations |
| Per-test scope (Listener v3 test_id) | `_kernel/context.py` + `telemetry/otel_listener.py` | `mcp/observer.py`, `coding_agent/*`, `_kernel/trace_store.py` |
| Trace recording backplane | `_kernel/trace_store.py` + `telemetry/` | Every `Metric.*` keyword; every adapter |
| Credential redaction | `_kernel/redaction.py` + `config.py` | Every trace serialization path; every log emission |
| Async-to-sync bridge | `_kernel/run_async.py` | Every sub-library calling async libs |
| Entry-points discovery | `_kernel/discovery.py` | Library import time |
| Error-class hierarchy | `errors.py` | Every sub-library that raises |
| Cost + runtime guardrails | `_kernel/guardrails.py` (`@guarded_fanout` decorator) | Tier-3 fan-out keywords only (selectively) |
| Honesty fields propagation | `_kernel/coverage.py` + adapters | Every adapter + every `Metric.*` keyword |
| Sandbox policy + gate | `security/policy.py` + `security/null_sandbox.py` | `scenarios/` (raises on Tier-3 code-exec without backend) |

### Requirements to Structure Mapping

**11 capability areas → directory mapping (1:1 except shared services):**

| Capability Area | Lives in |
|---|---|
| 1. Static Agent-Surface Inspection | `src/AgentEval/{skills, subagents, hooks, mcp}/` |
| 2. MCP Server Dynamic Evaluation | `src/AgentEval/mcp/` |
| 3. Agent Run Orchestration & Adapter Ecosystem | `src/AgentEval/{coding_agent, providers}/` |
| 4. Tool-Call Metrics & Trajectory Analysis | `src/AgentEval/metrics/` |
| 5. Statistical Evaluation & Three-Tier Determinism | `src/AgentEval/{stats, _assertions, _kernel/tier}/` |
| 6. Trace Recording & Observability | `src/AgentEval/{telemetry, _kernel/trace_store, _kernel/redaction, _kernel/coverage}/` |
| 7. Configuration & Provider/Agent Extensibility | `src/AgentEval/{config, _kernel/discovery}/` + `providers/` + `coding_agent/` |
| 8. Conformance & Compatibility Contracts | `tests/conformance/` + `mcp/version_gate.py` + `coding_agent/*` binary version checks |
| 9. Reporting, CI Integration & First-Run Experience | `src/AgentEval/{reporting, cli}/` + `.github/workflows/` + `docs/recipes/` |
| 10. Honest Failure Reporting | `src/AgentEval/errors.py` + warnings in `telemetry/` + `_kernel/coverage.py` |
| 11. Determinism Contract & Stability Surface (docs) | `docs/contracts/` + doc-build CI |

### Integration Points

**Internal communication (no IPC; all in-process Python):**

- **Trace store as message bus:** adapters emit spans → `_kernel/trace_store` indexes by `test_id` → metric keywords + `Get Last Warnings` + `Get Run Manifest` read via projection accessors. No direct sub-library ↔ sub-library calls.
- **Listener v3 lifecycle:** `start_test` → `_kernel/context.set_current_test_id()` → MCP servers spawned + adapters bound → keywords execute → `end_test` → trace backend writes JSONL + RunManifest + MCP servers torn down.
- **Entry-points discovery at import:** `library.py` import → `_kernel/discovery` loads all entry-point groups → AdapterRegistry populated → sub-libraries access registry on first keyword call (lazy).

**External integrations:**

- **LiteLLM** (140+ providers) via `providers/litellm_adapter.py` → external HTTPS to provider endpoints.
- **MCP servers** (user-provided or library-hosted): stdio subprocess, Streamable HTTP HTTPS, in-memory test transport.
- **Coding-agent CLIs** (`claude`, `codex`, `copilot`) via subprocess in `coding_agent/{claude_code,codex,copilot}_cli.py`.
- **Coding-agent SDKs** (Claude Agent SDK, OpenAI Agents SDK) via Python in-process imports.
- **OTLP backend** (Phase 2): `opentelemetry-exporter-otlp` → external endpoint.
- **GitHub Actions** (cross-repo dogfood integration per NFR-REL-05): `dogfood-integration.yml` triggers downstream CI in `rf-mcp` + `robotframework-agentskills`.
- (Previously listed: external `agentguard repo` integration for the agentguard-drift-check workflow per NFR-MAINT-06 / ADR-A4. RETIRED 2026-05-17 — agenteval has no dependency on agentguard; no integration needed.)

**Data flow:**

```
Listener.start_test(test_id)
        │
        ▼
_kernel/context.set_current_test_id(test_id)
        │
        ▼
mcp.Start Server (per-test scope) ─────────────────────┐
        │                                              │
        ▼                                              ▼
coding_agent.Connect Agent ─→ Send Prompt           [Library-hosted MCP server]
        │                            │                  │
        │                            │                  │
        ▼                            ▼                  ▼
[Agent runs internally]    [LLM calls]         [tools/call observed]
        │                            │                  │
        │                            │                  │
        └──── emits spans ──→ telemetry.spans ←─────────┘
                                       │
                                       ▼
                              _kernel/trace_store (per test_id)
                                       │
                                       ▼
                              [Memory + JSONL + (P2) OTLP backends]
                                       │
                                       ▼
                              Metric.Get Tool Hit Rate (reads via projection)
                                       │
                                       ▼
                              AssertionEngine (via _assertions/adapter)
                                       │
                                       ▼
                              evidence block → RF log
        │
        ▼
Listener.end_test(test_id) ─→ JSONL backend writes trace + RunManifest
                            ─→ MCP servers torn down (per-test scope)
                            ─→ test_id context cleared
```

### File Organization Patterns

**Configuration files (root):** `pyproject.toml` (single source of truth); `uv.lock`; `ruff.toml`; `mypy.ini`; `.env.example`; `.python-version`. NO `setup.py`, NO `requirements.txt`, NO `setup.cfg`.

**Source organization:** `src/AgentEval/` package; sub-libraries one-directory-each per Step-5 module-organization convention; `_kernel/` for cross-cutting helpers (leading underscore = internal); `_assertions/` for AssertionEngine kernel (leading underscore = internal).

**Test organization:** 3-tier per NFR-REL-01/02/03 + `tests/conformance/` (Phase 1 deliverable per FR45) + `tests/benchmarks/` (per NFR-PERF-02) + `tests/fixtures/` (mock MCP servers, sample skill .md files, sample scenario YAMLs).

**Asset organization:** `docs/` for all documentation; `examples/` for user-facing runnable `.robot` files (NOT in `docs/` because they're meant to be copied as starting points).

### Development Workflow Integration

- **Local dev:** `uv sync` → all deps installed; `uv run robot examples/00_setup.robot` runs first test; `uv run pytest tests/unit/` runs unit tests.
- **Build process:** `uv build` produces `dist/*.whl` + `dist/*.tar.gz`; published via `uv publish` (OIDC trusted publishing in `release.yml`).
- **Deployment structure:** N/A (PyPI library — no runtime deployment beyond PyPI).
- **Doc build:** `docs-build.yml` runs libdoc generation; asserts every doc in `docs/contracts/` exists per NFR-MAINT-04.

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**

- **Step-1 decisions (Structure A / Hybrid ADR / Sandbox Phase 1)** consistent with Step-3 starter selection (agentguard reviewed as a project-layout reference; agenteval is independent) — no `pip install robotframework-agentguard` dependency anywhere; patterns reviewed across multiple references and evaluated on merit for agenteval.
- **Step-2 11 architectural concerns** all map to specific implementation modules (Step-6 project tree) and specific ADRs (`adr-backlog-from-architecture.md`). No orphaned concerns.
- **Step-4 4 critical decisions** each generate cascading implications fully reflected in Step-5 patterns + Step-6 file layout.
- **No version conflicts:** `mcp>=1.0,<2.0` + `litellm>=1.83` + `opentelemetry-api/sdk>=1.27` + `robotframework>=7.4,<9.0` + `robotframework-pythonlibcore>=4.5` + `robotframework-assertion-engine>=4.0,<5.0` + `pydantic>=2.0` + `scipy>=1.13` co-exist without overlap; verified against agentguard's working `pyproject.toml`.
- **No contradictory decisions:** Sandbox-Phase-1 (Step-1) + Sandbox Protocol + NullSandbox + SandboxRequiredError (Step-6 `security/`) + ADR-A8 (architecture sidecar) all align.

**Pattern Consistency:**

- Keyword naming convention (Step-5) consistent across all 12 sub-libraries (Step-6) — every sub-library directory uses `library.py` + `_internal.py` + `types.py` triplet; every keyword carries `@tier(N)` per Decision-1.
- Cross-sub-library import discipline (Step-5) enforceable via `tests/unit/conventions/test_import_graph.py` (Step-6) — sub-libraries import only from `_kernel/`, `_assertions/`, `errors.py`, `types.py`; no cross-sub-library imports.
- Error-raising convention (Step-5 + ADR-A3 + Step-6 `errors.py`) unified — single `AgentEvalError` base with 4 sub-bases mapping to FR50 exit codes.
- Async-to-sync convention (Step-5 + ADR-A1 + Step-6 `_kernel/run_async.py`) — single `_run_async()` canonical bridge; no per-sub-library reinvention.

**Structure Alignment:**

- Step-6 project tree supports every architectural decision: `_kernel/` directory hosts all cross-cutting helpers (ADR-A1/A2/A5/A6); `tests/conformance/` hosts all AC oracles (Decision-4 + ADR-A7); `.github/workflows/security-scan.yml` (CodeQL) replaces the retired `agentguard-drift-check.yml`; `docs/contracts/` holds all 9 doc deliverables per NFR-MAINT-04 + Step-4/Step-5 additions (agentguard-inheritance.md retired 2026-05-17).
- All Step-2 cross-cutting concerns have explicit file home (Cross-cutting Concern Locations table in Step-6).
- Per-test scope mechanism (Listener v3 `test_id` → `_kernel/context.py` → `mcp/observer.py` + `_kernel/trace_store.py` + adapter instances) threads coherently across MCP server lifecycle + trace recording + adapter binding.

### Requirements Coverage Validation ✅

**Functional Requirements Coverage (65 FRs):**

| FR group | Lives in | Verified by |
|---|---|---|
| FR1-6 (Static Inspection) | `src/AgentEval/{skills, subagents, hooks, mcp}/library.py` | `tests/unit/{skills,subagents,hooks,mcp}/*` + `tests/acceptance/smoke/02_static_inspection.robot` |
| FR7-11, FR11b (MCP Dynamic + cost/runtime guardrails) | `src/AgentEval/mcp/` + `_kernel/guardrails.py` | `tests/unit/mcp/*` + `tests/acceptance/tier3/tool_discoverability.robot` + `tests/conformance/test_ac_discover_*.py` |
| FR12 + FR13a-f (Protocol + 6 adapters) | `src/AgentEval/coding_agent/{base,in_process,subprocess,generic,claude_code_cli,claude_agent_sdk,openai_agents,codex_cli,copilot_cli}.py` | `tests/unit/coding_agent/*` + `tests/integration/test_*_live.py` |
| FR14-18 (Send Prompt / Run Scenario / MCP binding / Custom adapters / Scaffolding CLI) | `src/AgentEval/{coding_agent, scenarios, cli}.py` + `_kernel/discovery.py` | `tests/unit/scenarios/*` + `tests/unit/_kernel/test_discovery.py` |
| FR19-25 (Metrics + Trajectory + Response assertions) | `src/AgentEval/metrics/library.py` | `tests/unit/metrics/*` |
| FR26-31 (Stats + Tier model + Determinism) | `src/AgentEval/stats/` + `_kernel/tier.py` + `_assertions/adapter.py` | `tests/unit/{stats,_kernel,_assertions}/*` |
| FR32-40 (Trace + Observability) | `src/AgentEval/telemetry/` + `_kernel/{trace_store,redaction,coverage}.py` | `tests/unit/{telemetry,_kernel}/*` + `tests/conformance/test_ac_mcp_observe_*.py` |
| FR41-44 (Config + Extensibility) | `src/AgentEval/config.py` + `_kernel/discovery.py` | `tests/unit/test_config_precedence.py` |
| FR45-48 (Conformance + Compat) | `tests/conformance/` + `mcp/version_gate.py` + `coding_agent/*_cli.py` | `tests/conformance/test_ac_conformance_*.py` + `tests/unit/mcp/test_version_gate.py` |
| FR49-59 (Reporting + CI + First-Run) | `src/AgentEval/{reporting, cli}` + `.github/workflows/*.yml` + `docs/recipes/*.md` | `tests/unit/reporting/*` + `tests/acceptance/smoke/01_first_test.robot` |
| FR60-62 (Honest Failure Reporting) | `src/AgentEval/errors.py` + `telemetry/` warnings + `_kernel/coverage.py` | `tests/unit/test_errors.py` + `tests/unit/_kernel/test_coverage.py` |
| FR63-65 (Determinism Contract + Stability Surface + Exit Criteria docs) | `docs/contracts/*.md` + `.github/workflows/docs-build.yml` | doc-build CI asserts required sections per NFR-MAINT-04 |

**All 65 FRs (Phase 1 + Phase 2) have architectural support.** Phase 2 FRs (FR10b, FR13c-f, FR29a/b/c, FR48 Judge, FR60 AdapterVersionDriftWarning, FR55 `as_html()`, FR33b OTLP) have file homes designated but implementation deferred per Product Scope > Growth Features.

**Non-Functional Requirements Coverage (25 NFRs):** (NFR-MAINT-06 was retired 2026-05-17 — see reframe note above.)

| NFR group | Architectural mechanism |
|---|---|
| NFR-PERF-01 (5-min time-to-first-test) | Bundled echo MCP server fixture in `tests/fixtures/mcp/echo_server.py` + zero-API-key Tier-1 path + `examples/00_setup.robot` happy path |
| NFR-PERF-02 (Tier-1 ≤50ms) | Pure-Python static keywords; `tests/benchmarks/bench_static_inspection.py` |
| NFR-PERF-03a/b/c/d (MCP startup) | Echo server lightweight (200ms); 3-mode `mcp_per_test` via `_kernel/context.py`; cookbook recipe #5 |
| NFR-PERF-04 + NFR-PERF-06 (guardrails) | `_kernel/guardrails.py` `@guarded_fanout` decorator per ADR-A5 |
| NFR-PERF-05 (pabot parallel) | Per-test MCP scope (FR40 / ADR-A6); conformance heavy-server fixture |
| NFR-REL-01-03 (test-tier reliability) | 3-tier `tests/{unit,integration,acceptance}/` layout + CI matrix |
| NFR-REL-04 (dep pinning) | `pyproject.toml` floors+ceilings + CHANGELOG |
| NFR-REL-05 (dogfood loop) | `.github/workflows/dogfood-integration.yml` |
| NFR-SEC-01 (credential redaction) | `_kernel/redaction.py` SpanProcessor — single choke point |
| NFR-SEC-02 (eval gate) | `_assertions/adapter.py` `validate` operator gate |
| NFR-SEC-03 (TLS) | Delegated to LiteLLM + MCP SDK; no relax knobs in `providers/` |
| NFR-SEC-04 (binary auto-install ban) | `coding_agent/*_cli.py` `UnsupportedBinaryVersionError` per FR47 + ADR-A8 |
| NFR-SEC-05 (no phone-home) | `telemetry=False` opt-out per FR44; `Assert No Egress To` conformance fixture |
| NFR-COMPAT-01-06 (compatibility ranges) | `pyproject.toml` + internal facade per dep (`telemetry/semconv.py`, `mcp/version_gate.py`, `providers/base.py` Protocol) |
| NFR-MAINT-01 (bus-factor mitigation) | `MAINTAINERS.md` + `CONTRIBUTING.md` + Mock adapter template + `SubprocessAdapter` ABC contributor surface |
| NFR-MAINT-02 (triage SLA) | `SUPPORT.md` |
| NFR-MAINT-03 (semver) | Release process |
| NFR-MAINT-04 (10 docs as first-class) | `docs-build.yml` doc-build CI asserts required sections |
| NFR-MAINT-05 (Stability Surface metadata) | `docs/contracts/stability-surface.md` per FR64 |
| ~~NFR-MAINT-06 (drift-check CI)~~ | RETIRED 2026-05-17 — agentguard reframed from dependency to inspiration; no drift-check needed |

**All 25 NFRs have architectural support.**

**Acceptance Criteria Coverage (9 ACs):**

| AC ID | Architectural enforcement |
|---|---|
| AC-SIMPLICITY-01 | `_assertions/adapter.py` evidence-block emission + `tests/conformance/test_ac_simplicity_01_evidence_block.py` |
| AC-SIMPLICITY-02 | Step-5 keyword conventions + `tests/conformance/test_ac_simplicity_02_keyword_idiom.py` + `tests/unit/conventions/test_import_graph.py` |
| AC-DISCOVER-01 | `mcp/library.py` Get Tool Discoverability + `tests/conformance/test_ac_discover_01_cohort.py` |
| AC-DISCOVER-02 | `_kernel/guardrails.py` `@guarded_fanout` + `tests/conformance/test_ac_discover_02_cost_guardrail.py` |
| AC-DOGFOOD-01 | `.github/workflows/dogfood-integration.yml` + `tests/conformance/test_ac_dogfood_01_replacement.py` |
| AC-CONFORMANCE-01 (fidelity oracles) | `tests/conformance/fixtures/` + `fixture-schema.json` per Decision-4 |
| AC-CONFORMANCE-02 (completeness) | `tests/conformance/harness.py` truncation-injection + `test_ac_conformance_02_completeness.py` |
| AC-MCP-OBSERVE-01 | `_kernel/coverage.py` `_check_mcp_coverage` + IncompleteTraceError + `test_ac_mcp_observe_01_coverage.py` |
| AC-MCP-OBSERVE-02 | `mcp/version_gate.py` UnsupportedMCPVersionError + `test_ac_mcp_observe_02_version_gate.py` |
| AC-MCP-OBSERVE-03 | `_kernel/context.py` Listener v3 test_id + `test_ac_mcp_observe_03_per_test_scope.py` |

**All 9 ACs have architectural enforcement paths.**

### Implementation Readiness Validation ✅

**Decision Completeness:**

- 4 critical Step-4 decisions all settled with implementation surface specified (LoC estimates + module paths + cascading implications).
- 17 ADRs in backlog (10 PRD + 7 active architecture-original — ADR-A1/A2/A3/A5/A6/A7/A8; ADR-A4 retired 2026-05-17) + ~14 reviewed agentguard patterns (Architectural Influences Catalog content) = ~31 total architectural decisions ratifiable at Phase 1 close.
- 3 Phase 1 estimation risks (hosted-MCP observer; per-test MCP cleanup; conformance suite golden-trace harness) explicitly resolved via spike-first approach (Stories 1.2-1.3 in Phase 1 Week 1 per Decision-3).
- All technology versions pinned per NFR-COMPAT-01..06.

**Structure Completeness:**

- Project tree (Step-6) enumerates **every file** that will exist in `src/AgentEval/`, `tests/`, `docs/`, `.github/workflows/`, `examples/`, and root config files.
- Each sub-library has documented `library.py` + `_internal.py` + `types.py` triplet per Step-5 module-organization convention.
- All 12 sub-libraries' responsibilities (Component Boundaries table) and ownership (Owns/Does NOT own columns) explicit.
- Integration points + data flow diagram show the trace store as message bus + Listener v3 lifecycle + entry-points discovery.

**Pattern Completeness:**

- 12 pattern categories defined in Step-5 with rule + concrete example + anti-pattern + CI enforcement mechanism.
- Every potential AI-agent conflict point identified during Step-5's first-principles audit.
- Naming + structure + communication + process patterns all specified.
- CI enforcement explicit: ruff + mypy + tests/unit/conventions/ + tests/conformance/ on PR + release.

### Gap Analysis Results

**Critical Gaps:** None. All blocking architectural decisions are settled OR have a spike-first plan (Decision-3) that produces decisions before sub-library implementation begins.

**Important Gaps (resolve before Phase 1 implementation; not blocking architecture document):**

1. **Architectural Influences Catalog content (agenteval ADR-001)** is referenced throughout but not drafted as a standalone document — the reconciliation matrix in `architecture.md` frontmatter contains the data, but the actual `docs/adr/ADR-001-architectural-influences-catalog.md` file content must be authored. **Action:** Story 1.1 (project bootstrap) includes "draft ADR-001-architectural-influences-catalog.md from architecture.md frontmatter reconciliationMatrix" as a sub-task.

2. **Performance benchmark methodology** for NFR-PERF-02 (Tier-1 ≤50ms median) — the `tests/benchmarks/bench_static_inspection.py` file is named but the measurement methodology (which keywords to benchmark, what "typical file size" means, how to compute median, what blocks release at 2× threshold) needs explicit definition. **Action:** Story 1.X (later in Foundation Epic) authors the benchmark spec; can be deferred until first benchmark implementation.

3. **`agenteval new-fixture` CLI subcommand** — mentioned in Decision-4 as Phase 2 scaffolding extension; not detailed in architecture. **Action:** Phase 2 epic-author writes the design.

**Minor Gaps (refinements; not blocking):**

1. **Phase 1 spike outputs (Stories 1.2-1.3)** will produce ADR amendments locking MCP observer implementation + MCP cleanup mechanism. Architecture document will need an update appendix at end of Phase 1 Week 1 with the spike outcomes.
2. **`coding-conventions.md`** doc structure not yet drafted — the Step-5 reference card needs to be authored alongside the patterns. **Action:** Story 1.X (later) drafts the doc.
3. **Recipe gallery content (8 recipes)** are file-path-placeholder only in Step-6; full content authoring is per-recipe story work during Phase 1.

### Validation Issues Addressed

No critical issues found during validation. The 3 important gaps + 3 minor gaps are documented above with explicit "Action" owners (Phase 1 Foundation Epic story slots or Phase 2 deferrals).

### Architecture Completeness Checklist

**Requirements Analysis**

- [x] Project context thoroughly analyzed (Step-2; 11 architectural concerns identified + 3 Phase 1 estimation risks surfaced)
- [x] Scale and complexity assessed (Step-2: HIGH at integration boundary, MEDIUM at core; 12 sub-libraries + 6 Tier-1 adapters)
- [x] Technical constraints identified (Step-2: pinned external deps + CLI binaries + Structure A code-copy patterns)
- [x] Cross-cutting concerns mapped (Step-2: 11 concerns categorized; 7 truly cross-cutting + 4 differently-categorized)

**Architectural Decisions**

- [x] Critical decisions documented with versions (Step-4: 4 critical decisions; all version-pinned via NFR-COMPAT-*)
- [x] Technology stack fully specified (Step-3 starter + Step-6 pyproject.toml deps + extras matrix)
- [x] Integration patterns defined (Step-6: trace store as message bus + Listener v3 lifecycle + entry-points discovery)
- [x] Performance considerations addressed (NFR-PERF-01..06 + Decision-3 spike-first for unknowns)

**Implementation Patterns**

- [x] Naming conventions established (Step-5: keyword + module + import + Pydantic field naming)
- [x] Structure patterns defined (Step-5: module organization triplet `library.py + _internal.py + types.py`)
- [x] Communication patterns specified (Step-6: trace store backplane + Protocol surfaces + entry-points discovery)
- [x] Process patterns documented (Step-5: error-raising + async bridge + logging + CI enforcement)

**Project Structure**

- [x] Complete directory structure defined (Step-6: every file enumerated)
- [x] Component boundaries established (Step-6: per-sub-library Owns / Does NOT own table)
- [x] Integration points mapped (Step-6: internal + external + data flow diagram)
- [x] Requirements to structure mapping complete (Step-6: 11 capability areas → directory mapping table)

**All 16 checklist items: ✅** No unchecked items.

### Architecture Readiness Assessment

**Overall Status:** **READY FOR IMPLEMENTATION**

All 16 checklist items pass. No critical gaps remain. 3 important gaps + 3 minor gaps documented with explicit Phase 1 story owners or Phase 2 deferrals.

**Confidence Level:** **high** — every FR/NFR/AC maps to a specific implementation surface; every cross-cutting concern has a kernel module; every cross-component data flow is documented; every CI enforcement mechanism is specified.

**Key Strengths:**

- **Influence from agentguard is honest and bounded.** Reconciliation matrix surfaced PRD's misframing (4 "influenced ADRs" was actually ~14 reviewed patterns); architecture explicitly catalogs the right set in the Architectural Influences Catalog. agenteval evaluates each pattern on merit and is free to diverge — no dependency, no required alignment.
- **Cross-cutting concerns are kernel-isolated.** `_kernel/` directory contains 7 modules each handling exactly one cross-cutting concern; sub-libraries depend on kernel but never on each other (CI-enforced).
- **Honesty-by-construction throughout.** AC-SIMPLICITY-01 (evidence blocks), AC-MCP-OBSERVE-01 (mcp_coverage), ADR-A3 (error hierarchy with `error_code`), ADR-A6 (detection-failure defaults to safer state) all enforce "loud refusal beats silent half-truth."
- **Phase 1 estimation risks surfaced explicitly + spike-resolved.** No silent over-commitment; the 3 unknowns (hosted-MCP observer, per-test cleanup, conformance harness) get Week-1 spikes before sub-library work commits.
- **Documentation contracts are first-class.** 10 contract docs in `docs/contracts/` + doc-build CI assertion + Stability Surface labels per release. Editorial-discipline-as-moat (PRD finding) operationalized.
- **Conformance suite as contract publication.** Phase 1 ships executable contract for community adapter authors; cross-language fixture format (JSON + jsonschema).

**Areas for Future Enhancement (post-Phase-1):**

- **Architectural Influences Catalog update cadence** — when agentguard ratifies new ADRs (currently 22 numbered; ADR-022 was newest at 2026-05-04), agenteval may review them as one input among many. Optional — agenteval is free to ignore agentguard changes if they don't serve agenteval better. No automated drift-check (NFR-MAINT-06 retired 2026-05-17).
- **Phase 1.5 hardening sprint trigger** — if any Decision-3 spike lands at "worst case" estimate, trigger Phase 1.5 per Risk Mitigation Strategy. Architecture document gets revised with re-baseline scope.
- **Phase 2 architectural additions** — Judge sub-library (FR48), OTLP exporter (FR33b OTLP backend), advanced Stat. primitives (FR29a/b/c), Codex CLI + Copilot CLI + SDK adapters (FR13c-f), AdapterVersionDriftWarning (FR60). All have file homes in Step-6 project tree; need architecture-level decisions during Phase 2 planning (one round of `/bmad-create-architecture` reuse, or amendments).
- **Phase 3 architectural additions** — Sandbox backends (Docker / ephemeral worktree / gVisor); LangGraph / CrewAI / AutoGen bridge adapters; HumanEval / SWE-bench fixture loaders; BFCL trajectory match port from agentguard. Out of architecture scope until Phase 2 close re-baseline.

### Implementation Handoff

**AI Agent Guidelines for Phase 1 implementation:**

1. **Follow all architectural decisions exactly as documented** — agenteval ADRs (renumbered 001-018; ADR-A4 retired), reviewed agentguard patterns (Architectural Influences Catalog, agenteval ADR-001), 4 Step-4 critical decisions.
2. **Use implementation patterns consistently** — Step-5 12 pattern categories; CI-enforced where possible.
3. **Respect project structure and boundaries** — Step-6 tree; sub-libraries never import from each other; cross-cutting concerns live in `_kernel/` or `_assertions/`.
4. **Refer to this document for all architectural questions** — `architecture.md` is the load-bearing artifact; ADR backlog sidecars (`adr-backlog-from-prd.md` + `adr-backlog-from-architecture.md`) provide ratification queue.
5. **Run conformance suite + conventions tests on every PR** — `pytest tests/conformance/ tests/unit/conventions/ -v` is a release-blocking gate.
6. **Optionally review Architectural Influences Catalog (ADR-001) when agentguard adds new ADRs** — optional; agenteval is free to ignore agentguard changes if they don't serve agenteval better. No automated drift-check CI (NFR-MAINT-06 / ADR-A4 retired 2026-05-17).

**First Implementation Priority:**

```bash
# Story 1.1 — Set up independent project (informed by agentguard layout review; per Step-3 + implementation-readiness-report-2026-05-16.md Section 5)
uv init --lib robotframework-agenteval

# Optional read-only reference review during implementation (DO NOT copy code from here into agenteval):
# git clone --depth 1 https://github.com/manykarim/robotframework-agentguard /tmp/agentguard-ref

# Then proceed per Step-3's detailed initialization sequence:
# 1. Write agenteval's own .github/workflows/ + docs/adr/README.md + pyproject.toml (informed by review)
# 2. Create src/AgentEval/ package (agenteval's own)
# 3. Write agenteval's own sub-libraries (some patterns borrowed from agentguard, evaluated on merit, free to diverge)
# 4. Add agenteval-specific kernel modules per Step-6 project tree
# 5. Ratify 18 ADRs into docs/adr/ (Architectural Influences Catalog = ADR-001; renumbered PRD + architecture sidecars = ADR-002..018; ADR-A4 retired 2026-05-17)
# 6. Verify `uv sync` + `uv run robot examples/00_setup.robot` runs green
```

Architecture document is **complete and ready for `/bmad-create-epics-and-stories`** to consume.

## Steps 8..N

(Workflow completion step follows.)
