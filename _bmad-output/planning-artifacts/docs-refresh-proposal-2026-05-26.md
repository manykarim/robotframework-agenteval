# Documentation refresh proposal — README + onboarding docs

**Date:** 2026-05-26
**Author:** Amelia (Developer)
**Status:** PROPOSAL — no changes implemented yet. Awaiting user approval.
**Scope:** README.md + CHANGELOG.md + CONTRIBUTING.md + docs/recipes index + docs/contracts/README index + MAINTAINERS.md + a new `docs/getting-started.md` page.

## Why now

Phase 1 closed 2026-05-25 (Story 9.3 / Epic 9). Epic 10 (Phase 2 launch) shipped 2 native Agent SDK adapters. Cross-LLM review pipeline restored via kilocode/minimax (2026-05-26 retro batch). The current README still says "Pre-alpha — Phase 1 in active development" with a 29-keyword surface — both substantively out of date.

**Headline drift (machine-verified 2026-05-26):**

| Surface | README claim | Empirical reality |
| --- | --- | --- |
| Project status | "Pre-alpha — Phase 1 in active development (v0.0.1)" | Phase 1 closed; Epic 10 Phase 2 launched; v0.0.1 unchanged but ~50 stories shipped. |
| `AgentEval` keyword count | 29 keywords | **~68** RF-keyword methods on the top-level library. README table covers ~24 — silently drops Tier-3 stats keywords, telemetry-introspection, cohort heatmap, polishing keywords, and 6 init/new-adapter CLI hooks. |
| Adapters listed | None (only LiteLLM mentioned in quick-start) | 4 ratified Phase-1+2 adapters: `GenericAdapter` (LiteLLM) + `ClaudeCodeCLIAdapter` + **`ClaudeAgentSDKAdapter`** (Story 10.1) + **`OpenAIAgentsSDKAdapter`** (Story 10.2). |
| CLI subcommands | None | `agenteval init` (Story 8b.1) + `agenteval new-adapter` (Story 8b.2) + `python -m AgentEval.conformance` (Story 8a.2). |
| Recipes listed | 1 (`04-skill-author-stacked-validation.md`) | **8 recipes** in `docs/recipes/` ratified (01-08). |
| ADR count | "19 ADRs" | **19 ADRs accepted** (ADR-002 → ADR-019; ADR-001 catalog). ADR-019 = assertion engine adoption (Epic 6). README claim is correct but doesn't mention ADR-019 specifically. |
| `mcp_coverage` ADR | "ADR-016" | Correct — but the in-code citation drift caught by kilo/minimax 2026-05-26 review (16 `ADR-A6 L384` → `ADR-016 L59` corrections) is invisible in README. |
| Cross-LLM review methodology | Not mentioned | 23 ratified `feedback_*` norms; 9 substantive kilo/minimax cross-reviews delivered across Epic 8/9/10; `feedback_third_llm_family_fallback` CANDIDATE for ratification at next retro. Project-distinctive methodology. |
| CHANGELOG.md last entry | Story 1a.6 (Epic 1a close) | **~50 stories worth of work missing.** Epic 1b through Epic 10 entirely unrecorded. |
| Install path | `uv add robotframework-agenteval` | Same — but no mention of Phase-2 extras (`[claude-sdk]`, `[openai-agents]`). |

This proposal lays out **what to change**, **why**, and **suggested copy** — but defers implementation until you approve direction + scope.

## Proposal at a glance

| # | Document | Action | Effort |
| --- | --- | --- | --- |
| 1 | `README.md` | Significant rewrite — status section, full keyword surface, adapter listing, CLI subcommands, recipes index, ADR-019 mention, methodology callout, install with extras | M |
| 2 | `CHANGELOG.md` | Backfill **45+ missing entries** (Story 1b.1 → Story 10.2 + retros); group by Epic, link to story spec files | L |
| 3 | `CONTRIBUTING.md` | Add cross-LLM review section + reference to `feedback_*` norms registry + kilo/minimax invocation snippet | S |
| 4 | `docs/recipes/README.md` (NEW) | Recipe index with persona/use-case crosswalk; replaces the 1-recipe table in README | S |
| 5 | `docs/contracts/README.md` | Add row for ADR-019 + amend the `stability-surface.md` row to mention Epic 10 experimental adapters | XS |
| 6 | `MAINTAINERS.md` | Add §"Review methodology" section pointing at the 23 ratified `feedback_*` norms + the kilo/minimax third-LLM fallback discovery | S |
| 7 | `docs/getting-started.md` (NEW) | Single-page "0-to-running-an-eval" tutorial — synthesized from Recipe #1 + the new-adapter quickstart + Listener integration. Linked from README | M |
| 8 | `docs/contracts/exit-criteria-0x-to-1x.md` | Already at `accepted` (Story 9.3) — surface via README's status section (link, not duplicate) | XS |
| 9 | Phase-1 retro link | Surface `_bmad-output/planning-artifacts/phase-1-retrospective-2026-05-25.md` from CHANGELOG + MAINTAINERS | XS |

**Total effort:** ~L (1 large + 2 medium + 3 small + 3 extra-small). All changes are doc-only; no code, no tests required.

---

## 1) README.md rewrite

### Section-by-section diff plan

#### Title + tagline
Keep: `# robotframework-agenteval` + "Robot Framework library for evaluating AI coding agents — skills, subagents, hooks, MCP servers, and tool calls."

#### Status block (REPLACE)
**Current:**
> Pre-alpha — Phase 1 in active development (v0.0.1). The core keyword surface is functional and dogfooded against [`robotframework-agentskills`](https://github.com/manykarim/robotframework-agentskills). No stable public API yet; breaking changes can happen before 1.0.

**Proposed:**
> **Phase 1 complete (2026-05-25) · Phase 2 launched.** Version `0.0.1` is feature-complete for the Phase 1 surface (10+ epics, ~50 stories, 1380+ tests, 19 ratified ADRs, 23 ratified review-methodology norms). Phase 2 has shipped native Agent SDK adapters for Anthropic + OpenAI (Epic 10). The library remains pre-1.0 — see [`docs/contracts/exit-criteria-0x-to-1x.md`](./docs/contracts/exit-criteria-0x-to-1x.md) for the 6 ratified promotion criteria. Public API uses [`docs/contracts/stability-surface.md`](./docs/contracts/stability-surface.md) labels (`stable` / `provisional` / `experimental`); breaking changes are constrained by the 3-month-no-break window for `stable` surfaces.

#### Install (UPDATE — add Phase-2 extras)
**Current:**
```bash
uv add robotframework-agenteval
```

**Proposed:**
```bash
# Core install (Phase 1 surface: Generic + Claude Code CLI adapters)
uv add robotframework-agenteval

# Phase 2 native SDK adapters (optional extras)
uv add 'robotframework-agenteval[claude-sdk]'    # Anthropic Claude Agent SDK
uv add 'robotframework-agenteval[openai-agents]' # OpenAI Agents SDK
```

Pre-release dev install unchanged (`git clone ... && uv sync`).

#### Quick start (UPDATE — make adapter explicit)
The current quick-start uses `adapter=litellm` + asserts `cost_usd == 0`. The second assertion is wrong (it's a sanity-check on non-zero cost but uses `== 0`). Proposed:

```robotframework
*** Settings ***
Library    AgentEval

*** Test Cases ***
Agent calls the right tool
    ${result}=    AgentEval.Send Prompt
    ...    prompt=Search the web for Robot Framework tutorials
    ...    adapter=generic
    ...    model=anthropic/claude-sonnet-4-5
    AgentEval.Tool Call Should Have Occurred    ${result}    web_search
    Should Not Be Equal As Numbers    ${result.cost_usd}    0    msg=sanity: non-zero cost
```

#### Adapters (NEW SECTION)
Insert between Quick Start and Keywords:

> ### Adapters
>
> 4 ratified adapters as of Phase 2 launch:
>
> | Adapter | Entry-point name | Extra | Status | Story |
> | --- | --- | --- | --- | --- |
> | `GenericAdapter` (LiteLLM-backed) | `generic` | n/a (core) | `provisional` | Story 4.1 |
> | `ClaudeCodeCLIAdapter` | `claude-code-cli` | `[claude-code]` | `provisional` | Story 4.2 |
> | `ClaudeAgentSDKAdapter` | `claude-agent-sdk` | `[claude-sdk]` | `experimental` | Story 10.1 |
> | `OpenAIAgentsSDKAdapter` | `openai-agents-sdk` | `[openai-agents]` | `experimental` | Story 10.2 |
>
> Adapters are discovered via `agenteval.coding_agents` entry-points; `register_adapter()` is also supported. See [ADR-003](./docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-split.md) for the `InProcessAdapter` / `SubprocessAdapter` split and [ADR-013](./docs/adr/ADR-013-entry-points-discovery-infrastructure.md) for the discovery mechanism.

#### CLI (NEW SECTION)
Insert after Adapters:

> ### Command-line interface
>
> | Command | Purpose | Story |
> | --- | --- | --- |
> | `agenteval init` | Scaffold a starter project (3 .robot files + 3 fixtures + agenteval.yaml + README) | Story 8b.1 |
> | `agenteval new-adapter <name>` | Scaffold a new `CodingAgentAdapter` skeleton + conformance test | Story 8b.2 |
> | `python -m AgentEval.conformance --adapter <name>` | Run the conformance suite + emit JSON + Markdown reports + sysexits-mapped exit code | Story 8a.2 |
> | `python -m robot.libdoc AgentEval docs/keywords/AgentEval.html` | Generate the keyword reference HTML | n/a |

#### Keywords at a glance (REWRITE — full surface)
Current table lists 29 keywords on `AgentEval` + 8 on `SkillsLibrary` = 37 total. Empirical class-surface is ~68 on `AgentEval`. The drift comes from missing:

- **Stats Tier-3 keywords** (`Stat.Run N Times` is listed; missing: `Stat.Get Pass At K Comparison`, `Stat.Assert Tool Hit Rate Above`, etc. — verify against `src/AgentEval/stats/library.py`).
- **Telemetry-introspection** (`Get Spans`, `Get Run Manifest`, `Get Last Warnings` are listed but missing: `Get Cohort Heatmap` from Story 8b.2).
- **Conformance harness keywords** (Story 1b.5).
- **`SkillsLibrary` discoverability keyword extensions** (Story 7.4).

Action: regenerate the table from `python -m robot.libdoc AgentEval`'s output and pin both keyword counts (and the table) at the empirical surface. Mark Phase-2-experimental keywords distinctly (italic + experimental badge).

#### Keyword tiers (KEEP — minor refresh)
Current text is correct. Add a one-line note: *"Story 6.3 enforces Tier-1 LLM-invocation ban (PRD FR30b) at adapter-entry — see [ADR-002](./docs/adr/ADR-002-tier-1-adapter-ceiling-rule.md)."*

#### What this library is for (UPDATE — add new surfaces)
Add 3 new bullet points after the existing list:

- **Conformance harness** — JSON + Markdown report generator with sysexits-mapped exit codes ([FR50 + FR57](./docs/contracts/error-class-hierarchy.md)).
- **Cohort heatmap** — ASCII + dict renderer for Pass@k across (task × model) grids (Story 8b.2 `CohortHeatmap`).
- **Terminal run summary** — opt-in via `AGENTEVAL_TERMINAL_SUMMARY=1` (FR54; Story 8b.2). Note current Phase-1.5 carve-out per C71: pass/fail counts not yet captured.

#### Recipes (REPLACE — full table)
Current single-row table replaced with:

> | # | Recipe | Persona | What it shows |
> | --- | --- | --- | --- |
> | 1 | [First eval in 5 minutes](./docs/recipes/01-first-eval-in-five-minutes.md) | All | Minimal Send Prompt + tool-call assertion |
> | 2 | [Pass@k over polling](./docs/recipes/02-pass-at-k-over-polling.md) | Devon | Stat.Pass@k as the polling replacement (ADR-019 prohibits polling) |
> | 3 | [Tool discoverability cohort](./docs/recipes/03-tool-discoverability-cohort.md) | Raj | `MCP.Get Tool Discoverability` Pass@k across N trials × M tasks |
> | 4 | [Skill-author stacked validation](./docs/recipes/04-skill-author-stacked-validation.md) | Devon | Tier-1 frontmatter check → Tier-2 activation → Tier-3 Pass@k stacked |
> | 5 | [Dogfood — replacing custom Python tests](./docs/recipes/05-dogfood-replacing-custom-tests.md) | Raj | Port a downstream library's pytest corpus to `.robot` suites |
> | 6 | [Custom protocol adapter](./docs/recipes/06-custom-protocol-adapter.md) | Raj | Implement `CodingAgentAdapter` for a non-canonical agent |
> | 7 | [First MCP server test (Tier-1)](./docs/recipes/07-first-mcp-server-test-tier-1.md) | Raj | Static-inspection-only MCP config validation |
> | 8 | [CI integration](./docs/recipes/08-ci-integration.md) | All | dogfood-integration.yml + parity-suite-smoke patterns |

#### Documentation (UPDATE — broaden index)
Current shows 5 categories; add 2:

- **Methodology** — 23 ratified `feedback_*` review-methodology norms governing the project. Surfaced via [MAINTAINERS.md](./MAINTAINERS.md#review-methodology).
- **Retrospectives** — `_bmad-output/implementation-artifacts/epic-*-retro-*.md` + `_bmad-output/planning-artifacts/phase-1-retrospective-2026-05-25.md`.

#### Known limitations (REWRITE — current state)

**Current 4-item list is partly stale. Proposed:**

- **macOS validation deferred to Phase-1.5.** Phase-1 + Phase-2 validate on Linux only per D2.1 architect waiver. Community macOS reproductions welcome.
- **Exact version pins.** `mcp==1.27.1` + `robotframework==7.4.2` + `robotframework-pabot==5.2.2` + `anyio==4.13.0` are spike-validated. `AdapterVersionDriftWarning` (FR60, Phase-1.5) will detect future MCP SDK refactors that break the `request_handlers` wrap pattern.
- **`SkillsLibrary` not in the top-level `AgentEval` import.** Must be imported directly as `AgentEval.skills.library.SkillsLibrary` ([DF-7.1-S1](./docs/phase-1-5-carry-overs.md)).
- **No PyPI release yet.** Phase 1 is foundational. Public release + semver stability gated on the 6 exit criteria at [`exit-criteria-0x-to-1x.md`](./docs/contracts/exit-criteria-0x-to-1x.md).
- **Phase-2 SDK adapters at `experimental`.** `ClaudeAgentSDKAdapter` + `OpenAIAgentsSDKAdapter` carry pre-1.0 SDK pins (`claude-agent-sdk>=0.1.0,<1.0`, `openai-agents>=0.1.0,<1.0`); shape may shift. Defensive `_extract_usage` paths catalogued at C70 (`DF-10.2-S2`) for cleanup after live-SDK probe.
- **Terminal run summary pass/fail counts not populated** (Story 8b.2 honest framing). Listener does not snapshot `result.passed` yet; display shows `"—"` until C71 lands.

#### Project posture (UPDATE — add review methodology)
Current text:
> Solo + AI-agent-assisted development using the [BMad method](https://github.com/bmad-sim/bmad-method). See [MAINTAINERS.md](./MAINTAINERS.md) for the maintenance model and ratified review-methodology norms.

Proposed addition:
> The project uses **cross-LLM adversarial review** as a load-bearing quality control: every story is reviewed by ≥1 third-LLM-family reviewer (Claude CLI + Codex CLI + kilocode/minimax) per the `feedback_n_way_agreement_weight` norm. 30+ load-bearing catches across Epics 2-7; methodology preserved in Phase-2 via `feedback_third_llm_family_fallback` (kilo/minimax delivers when Claude+Codex CLIs degrade). See [MAINTAINERS.md §Review methodology](./MAINTAINERS.md#review-methodology).

---

## 2) CHANGELOG.md backfill

**Current state:** last entry is Story 1a.6 (Epic 1a close, 2026-05-18). Missing ~45 stories + Phase-1 retro + Epic 10 launch.

**Proposed structure** — add `## [Unreleased]` continuing from current top, but reorganize by Epic with story-grain bullets:

```markdown
## [Unreleased]

### Phase 2 — launched 2026-05-25

#### Epic 10 — Native Agent SDK adapters

- Story 10.1: `ClaudeAgentSDKAdapter(InProcessAdapter)` at `src/AgentEval/coding_agent/claude_agent_sdk.py` — wraps Anthropic's `claude-agent-sdk` PyPI package under `[claude-sdk]` extra. Entry-point `claude-agent-sdk`. Cross-LLM-reviewed v0.3.0 (Claude CLI 6 findings applied) + v0.4.0 (kilo/minimax 4 findings: 2 real + 2 false positives). Carry-overs: C67 (multi-turn + use+result pairing), C68 (HostedMcpObserver wiring).

- Story 10.2: `OpenAIAgentsSDKAdapter(InProcessAdapter)` at `src/AgentEval/coding_agent/openai_agents.py` — wraps `openai-agents` PyPI package (import: `from agents import ...`) under `[openai-agents]` extra. Entry-point `openai-agents-sdk`. 3-stage review chain (Claude/Codex empty → empirical SDK probe → kilo/minimax 5 findings); 15 unit tests + 1 env-gated integration. Carry-overs: C69 (MCP attachment), C70 (cost/usage shape verification).

### Phase 1 — closed 2026-05-25

#### Epic 9 — Dogfood closeout + Phase-1 close

- Story 9.1: rf-mcp full parity gap analysis (58 tests classified: 17 ported / 4 stays-custom / 38 Phase-2-batch). `parity-suite-smoke` workflow extension added.
- Story 9.2: agentskills full parity (Phase-1 surface 100% covered). `agentskills-parity-suite-smoke` workflow extension added.
- Story 9.3: Phase 1 retrospective at `_bmad-output/planning-artifacts/phase-1-retrospective-2026-05-25.md`; `docs/contracts/exit-criteria-0x-to-1x.md` rewritten from stub to `accepted` with 6 ratified criteria.

#### Epic 8b — CLI scaffolding + terminal summary + recipe gallery

- Story 8b.1: `agenteval init` CLI + 8 scaffolded files + Recipe #1.
- Story 8b.2: `agenteval new-adapter` CLI + FR54 terminal run summary + Story 8b.2 `CohortHeatmap` ASCII + dict renderer.
- Story 8b.3: 8-recipe gallery (Recipes 01-08) + OTel trace visual contract doc at `docs/contracts/otel-trace-visual.md`.

#### Epic 8a — JUnit XML enrichment + structured exit codes + conformance report

- Story 8a.1: JUnit XML enrichment via Listener v3 `xunit_file(path)` hook with 9 ratified `agenteval.*` properties; sysexits-style 21-leaf exit-code mapping; structured `AgentEvalError` hierarchy with `error_code` field per ADR-014.
- Story 8a.2: `trace_id` surfacing in `output.xml`; FR56 polling-ban error testability; FR57 conformance report (JSON + Markdown) + `python -m AgentEval.conformance` standalone CLI.

#### Epic 7 — Skill author validation + skill discoverability

- Story 7.1: `Skill.Get Activation Decision` keyword + `ActivationDecision` type.
- Story 7.2: `Skill.Get Discoverability` cohort discoverability with per-task aggregation.
- Story 7.3: 4-recipe stacked validation (Recipe #4 worked example).
- Story 7.4: `tests/dogfood/agentskills/test_skill_discoverability.robot` (4 tests; rf-browser-skill + 2 parallel-derived skills).

#### Epic 6 — Stats + assertion-engine adoption + Discoverability

- Story 6.1: `Stat.Run N Times` Tier-3 fan-out keyword + Wilson CI.
- Story 6.2: `Stat.Get Pass At K` + ADR-019 assertion-engine adoption.
- Story 6.3: Tier-1 LLM-invocation ban (PRD FR30b enforcement at adapter entry).
- Story 6.4: `robotframework-agentskills` metrics dogfood (36 tests; reframed parallel-derived after D-2 decision).

#### Epic 5 — Listener v3 + RunManifest + DegradedTraceWarning + observer

- Story 5.1: RF Listener v3 (`AgentEval.telemetry.listener.Listener`) + jsonl trace backend per FR51.
- Story 5.2: `HostedMcpObserver` wired into GenericAdapter; `mcp_coverage` detection per ADR-016.
- Story 5.3: `RunManifest` 7-field assembly + `record_run_metadata` Listener API.
- Story 5.4: `DegradedTraceWarning` collector + 5-key `WarningRecord` shape.
- Story 5.5: `tests/dogfood/rf-mcp/test_trace_observability_parity.robot` (8 tests).

#### Epic 4 — CodingAgentAdapter + GenericAdapter + Claude Code CLI + cost guardrails

- Story 4.1: `GenericAdapter(InProcessAdapter)` via LiteLLM; `LLMProviderAdapter` Protocol.
- Story 4.2: `ClaudeCodeCLIAdapter(SubprocessAdapter)` with FR47 binary version check.
- Story 4.3: cost + runtime `@guarded_fanout` decorator per ADR-015.
- Story 4.4: `MCP.Get Tool Discoverability` keyword.
- Story 4.5: `Send Prompt` + `Run Scenario` library keywords.

#### Epic 3 — MCP runtime + ServerHandle + tool dispatch

- Stories 3.1 / 3.2 / 3.3 / 3.4 ... [detailed bullets per story spec]

#### Epic 2 — Static inspection (Skills + Subagents + Hooks + MCP)

- Stories 2.1 / 2.2 / 2.3 / 2.4 ... [detailed bullets per story spec]

#### Epic 1b — Kernel + types + adapter ABCs + conformance harness

- Stories 1b.1 / 1b.2 / 1b.3 / 1b.4 / 1b.5 ... [detailed bullets per story spec]

### Methodology developments

- 23 ratified `feedback_*` review-methodology norms covering pre-create-story drift checks, carry-over catalog gates, cross-LLM adversarial review, fake-green test prevention, citation drift forensics, and more.
- Cross-LLM pipeline degraded in Epic 8 (Claude CLI empty + Codex CLI rate-limit) → restored 2026-05-26 via kilocode CLI / minimax-m2.7 third-LLM-family fallback (Epic 8 retro Action #1 step (iii) functionally resolved).
- `feedback_third_llm_family_fallback` candidate norm: 9 consecutive substantive cross-LLM reviews across Epic 8 + 9 + 10 retro-batch.

## [0.0.1] — 2026-05-17

[unchanged]
```

**Effort note:** the detailed Epic 1b → Epic 3 bullets can be auto-generated from the story spec files at `_bmad-output/implementation-artifacts/*.md` (each spec has a Change Log table). Suggest a one-time `scripts/build-changelog.py` helper that walks the directory + extracts per-story summaries; review the output manually before committing.

---

## 3) CONTRIBUTING.md additions

### New §"Cross-LLM Code Review" section

Insert before §"Code Style & Conventions":

```markdown
## Cross-LLM Code Review (Project Standard)

agenteval mandates **cross-LLM adversarial review** for every Tier-2/Tier-3 keyword PR + every architecture-touching change. Per `feedback_review_methodology_norms` (Epic 0 retro ratification), reviews come from ≥2 different LLM families to catch single-model blind spots.

### Invocations

Three reviewer CLIs are operationally supported:

| CLI | Invocation | When to use |
| --- | --- | --- |
| Claude CLI | `claude -p --dangerously-skip-permissions --model opus "$(cat /tmp/review-prompt.md)"` | Primary reviewer for code + spec reviews. |
| Codex CLI | `codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check "$(cat /tmp/review-prompt.md)"` | Second-family adversarial (catches what Claude misses). |
| kilocode CLI (preconfigured minimax) | `~/.kilo/bin/kilo run --auto --model minimax/MiniMax-M2.7 "$(cat /tmp/review-prompt.md)"` | **Third-LLM-family fallback** (Epic 8 retro Action #1 step (iii)). Operationally proven when Claude + Codex CLIs degrade. |

### What a review prompt should contain

- Story spec path
- New + modified files list
- Project conventions to verify against (re-derive citations from primary sources)
- Specific empirical claims to verify (e.g., "Does the real SDK expose attribute X?")
- Ask for HIGH/MED/LOW-ranked critiques with line numbers + patches
- End with: "Overall: ratify-as-is / ratify-with-patches / reject-and-revise"

### When to escalate to kilo/minimax third-LLM

If Claude CLI returns 0-byte output OR Codex CLI returns rate-limit error after retry, **switch to kilocode/minimax** rather than ship without cross-LLM review. The cross-LLM degradation pattern documented in Epic 8 retro produced 9 stories of substandard review quality before being resolved.

See [`_bmad-output/implementation-artifacts/epic-8-9-kilo-minimax-cross-review-2026-05-26.md`](_bmad-output/implementation-artifacts/epic-8-9-kilo-minimax-cross-review-2026-05-26.md) for the canonical pattern + 8 load-bearing catches the third-LLM delivered.
```

### Other small additions

- Mention `_bmad-output/implementation-artifacts/sprint-status.yaml` as the canonical story-state-of-the-world doc.
- Cross-reference the 23 ratified `feedback_*` norms registry (auto-memory at `/home/many/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/MEMORY.md` — but this is per-developer; suggest a public mirror at `docs/methodology/feedback-norms.md` as a separate work item).

---

## 4) NEW: docs/recipes/README.md (recipe index)

Currently the 8 recipes live as standalone files but there's no index page. Proposed `docs/recipes/README.md`:

```markdown
# Recipe Gallery

Eight worked examples covering the agenteval keyword surface — for **Devon** (skill author), **Raj** (library maintainer / agent developer), and **Many** (project lead).

[Same table content as the proposed README Recipes section above]

## How to use

Each recipe:
1. Names the use case ("I want to ...")
2. Lists the keywords involved
3. Shows the minimal `.robot` snippet
4. Documents the dogfood-finding (if any) that motivated it

Recipes are validated via the `docs-build.yml` per-file section-presence check + Phase-1.5 CI extraction (C64).
```

---

## 5) docs/contracts/README.md amendment

Add a row for the existing `error-class-hierarchy.md` Story 8a.2 FR56 amendment (already in the file but not surfaced in the contract index). Add cross-references between `mcp-coverage-detection.md` and ADR-016 + ADR-007. No structural change.

---

## 6) MAINTAINERS.md §"Review methodology" section

Add a new section after the existing maintenance-model content:

```markdown
## Review methodology

agenteval's quality bar is enforced through 23 ratified review-methodology norms (the `feedback_*` registry). Highlights:

- **`feedback_spec_vs_ratified_doc_precheck`** (Epic 1a retro) — 44 consecutive uses with 100% real-drift catch rate. Every story spec is cross-checked against ADRs + architecture + PRD before authoring.
- **`feedback_carry_over_catalog_gate` UPSTREAM** — 24 consecutive stories. Every new helper / contract / Phase-1.5 deferral is catalogued at `docs/phase-1-5-carry-overs.md` BEFORE invoking code-review.
- **`feedback_review_methodology_norms`** (Epic 0 retro) — cross-LLM adversarial review is the project standard. Single-LLM review is insufficient.
- **`feedback_test_name_assertion_match`** (Epic 3 retro) — every test name MUST match its assertion body. Fake-green patterns are unacceptable.
- **`feedback_n_way_agreement_weight`** — 3-way HIGH findings = near-certain bugs (100% TP across Epics 2-5).
- **`feedback_third_llm_family_fallback`** (CANDIDATE 2026-05-26) — when Claude + Codex CLIs degrade, kilocode/minimax substitutes. 9 consecutive substantive cross-LLM reviews delivered.

The full registry lives in the project's auto-memory at `/home/many/.claude/projects/-home-many-workspace-robotframework-agenteval/memory/MEMORY.md` (per-developer). A public mirror at `docs/methodology/feedback-norms.md` is a Phase-1.5 deliverable (not yet shipped).
```

---

## 7) NEW: docs/getting-started.md

A single-page "0-to-running-an-eval" tutorial synthesized from the existing surfaces. Outline:

1. **Install** (5 lines)
2. **Scaffold a project** — `agenteval init`
3. **Pick an adapter** — table from README + when to use which
4. **Write your first eval** — Recipe #1 walkthrough
5. **Run it** — `uv run robot --listener AgentEval.telemetry.listener.Listener tests/`
6. **Read the output** — JUnit XML + traces JSONL + run-manifest
7. **Next steps** — links to recipes, conformance, methodology

Length: ~150 lines. Replaces the current scattered "Quick start" experience.

---

## 8) Sequencing recommendation

If you approve, suggested sequence (each ~1 commit):

1. **CHANGELOG backfill** (do first — establishes the historical record)
2. **README rewrite** (do second — most user-visible)
3. **CONTRIBUTING.md additions** (do third — onboarding pattern)
4. **MAINTAINERS.md §Review methodology** (small; do alongside CONTRIBUTING)
5. **docs/recipes/README.md** (small; index)
6. **docs/getting-started.md** (last — replaces fragmented quick-start)

**Estimated total effort:** 1 large + 2 medium + 3 small + 3 extra-small. All doc-only changes; no test changes; no code changes. Each commit gated by `docs-build.yml` per-file section-presence checks.

---

## What's intentionally OUT of this proposal

- **Auto-generated keyword reference HTML** (`docs/keywords/*.html`) — already exists; regenerate per release.
- **ADR additions** — none proposed; existing 19 ADRs are accepted.
- **Recipe-CI extraction** (C64) — tracked separately as Phase-1.5 hygiene work.
- **macOS validation docs** — gated on actual macOS support work (still Phase-1.5).
- **`docs/methodology/feedback-norms.md`** — public mirror of the 23 ratified norms. Worth doing but a separate work-stream (involves curating the auto-memory entries into stable doc form; touches the norm-ratification process).

---

## Verification checklist before sending PR

- [ ] All keyword tables regenerated from `python -m robot.libdoc` (machine-truth, not transcribed)
- [ ] All adapter counts re-derived from `pyproject.toml` entry-points
- [ ] All recipe links resolve (8 recipes exist)
- [ ] All ADR cross-references resolve (none cite `ADR-A6` post-2026-05-26 patch)
- [ ] Cross-LLM review of README rewrite via kilo/minimax (per `feedback_third_llm_family_fallback`)
- [ ] `docs-build.yml` per-file section-presence check passes on all amended contract docs

---

## Decision needed

**Approve direction + scope?** Specifically:

1. Do you want **all 8 items** in scope, or a subset?
2. **CHANGELOG backfill granularity** — full per-story bullets (effort: L) vs Epic-grouped summaries (effort: M)?
3. **`docs/getting-started.md`** — add it (the README quick-start becomes a link), or keep it inline in README?
4. **Public `feedback-norms.md` mirror** — include in this work-stream, or defer?

Once you say go, I'll implement in the sequence above with cross-LLM review on each PR.
