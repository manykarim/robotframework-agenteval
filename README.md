# robotframework-agenteval

Robot Framework library for evaluating AI coding agents — skills, subagents, hooks, MCP servers, and tool calls.

## Status

**Phase 1 complete (2026-05-25) · Phase 2 launched.** Version `0.0.1` is feature-complete for the Phase 1 surface (10+ epics, ~50 stories, 1380+ tests, 19 ratified ADRs, 23 ratified review-methodology norms). Phase 2 has shipped native Agent SDK adapters for Anthropic + OpenAI (Epic 10).

The library remains pre-1.0 — see [`docs/contracts/exit-criteria-0x-to-1x.md`](./docs/contracts/exit-criteria-0x-to-1x.md) for the 6 ratified promotion criteria. Public API uses [`docs/contracts/stability-surface.md`](./docs/contracts/stability-surface.md) labels (`stable` / `provisional` / `experimental`); breaking changes on `stable` surfaces are constrained by the 3-month-no-break window.

## Install

```bash
# Core install — Phase 1 surface (Generic LiteLLM + Claude Code CLI adapters)
uv add robotframework-agenteval

# Phase 2 native SDK adapters — optional extras (pre-1.0 SDK pins; experimental)
uv add 'robotframework-agenteval[claude-sdk]'    # Anthropic Claude Agent SDK
uv add 'robotframework-agenteval[openai-agents]' # OpenAI Agents SDK
```

Once published. Pre-release, clone and sync:

```bash
git clone https://github.com/manykarim/robotframework-agenteval.git
cd robotframework-agenteval
uv sync --all-extras
uv run python -c "import AgentEval; print(AgentEval.__version__)"
# → 0.0.1
```

## Quick start

The fastest path is `agenteval init`, which scaffolds a working starter project (3 `.robot` files + 3 fixtures + `agenteval.yaml` + `README.md`) in a fresh directory:

```bash
mkdir my-agent-eval && cd my-agent-eval
agenteval init
uv run robot --listener AgentEval.telemetry.listener.Listener --xunit junit.xml tests/
```

Or write a minimal eval by hand:

```robotframework
*** Settings ***
Library    AgentEval

*** Test Cases ***
Agent Calls The Right Tool
    ${result}=    AgentEval.Send Prompt
    ...    prompt=Search the web for Robot Framework tutorials
    ...    adapter=generic
    ...    model=anthropic/claude-sonnet-4-5
    AgentEval.Tool Call Should Have Occurred    ${result}    web_search
    Should Not Be Equal As Numbers    ${result.cost_usd}    0    msg=sanity: non-zero cost
```

Run with the agenteval Listener so traces + JUnit XML enrichment + the optional terminal summary all light up:

```bash
uv run robot \
  --listener AgentEval.telemetry.listener.Listener \
  --xunit junit.xml \
  tests/
```

The trailing `.Listener` class path is required (RF 7.x accepts the module-path-only form but does not fire the class hooks — see [`docs/contracts/listener-integration.md`](./docs/contracts/listener-integration.md)).

## Adapters

Four ratified adapters as of Phase 2 launch. Adapters are discovered via the `agenteval.coding_agents` entry-points group; the `register_adapter()` Python API is also supported.

| Adapter | Entry-point name | Extra | Stability | Story |
|---|---|---|---|---|
| `GenericAdapter` (LiteLLM-backed) | `generic` | core (no extra) | `provisional` | Story 4.1 |
| `ClaudeCodeCLIAdapter` | `claude-code-cli` | `[claude-code]` | `provisional` | Story 4.2 |
| `ClaudeAgentSDKAdapter` | `claude-agent-sdk` | `[claude-sdk]` | `experimental` | Story 10.1 |
| `OpenAIAgentsSDKAdapter` | `openai-agents-sdk` | `[openai-agents]` | `experimental` | Story 10.2 |

See [ADR-003](./docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-split.md) for the `InProcessAdapter` / `SubprocessAdapter` split and [ADR-013](./docs/adr/ADR-013-entry-points-discovery-infrastructure.md) for the discovery mechanism. Phase-2 `experimental` adapters carry pre-1.0 SDK pins and may shift; promotion to `stable` is gated on the 3-month-no-break window per Exit Criterion #4.

## Command-line interface

```bash
# Scaffold a fresh starter project (Story 8b.1; 8 files; NFR-UX-01 5-min path)
agenteval init [directory]

# Scaffold a new CodingAgentAdapter (Story 8b.2; SubprocessAdapter or InProcessAdapter)
agenteval new-adapter <name> [--protocol stdio|inprocess]

# Run the conformance suite + emit JSON + Markdown reports (Story 8a.2; FR57)
python -m AgentEval.conformance --adapter <name> --output-dir reports/

# Generate keyword reference HTML for all 5 libraries (RF libdoc)
uv run python -m robot.libdoc AgentEval docs/keywords/AgentEval.html
uv run python -m robot.libdoc AgentEval.skills.library.SkillsLibrary docs/keywords/SkillsLibrary.html
uv run python -m robot.libdoc AgentEval.subagents.library.SubagentsLibrary docs/keywords/SubagentsLibrary.html
uv run python -m robot.libdoc AgentEval.hooks.library.HooksLibrary docs/keywords/HooksLibrary.html
uv run python -m robot.libdoc AgentEval.mcp.library.MCPLibrary docs/keywords/MCPLibrary.html
```

Committing the regenerated `docs/keywords/*.html` updates GitHub Pages automatically (Pages is configured to serve from `main` branch's `/docs` folder).

Exit codes from `python -m AgentEval.conformance` follow the sysexits-style 21-leaf mapping at [`docs/contracts/error-class-hierarchy.md`](./docs/contracts/error-class-hierarchy.md) L66-L101 (`EXIT_CODE_FALLBACK = 70` when fixtures fail).

## Keywords at a glance

5 libraries ship as of Phase 1 close. **49 keywords total**: 30 + 8 + 9 + 1 + 1. The top-level `AgentEval` library composes 30 keywords drawn from metrics + assertions + stats + orchestration + telemetry + heatmap surfaces. Three of the libraries (`SkillsLibrary`, `SubagentsLibrary`, `HooksLibrary`, `MCPLibrary`) require direct import — they are not composed into the top-level library.

### `AgentEval` library — 30 keywords

Full libdoc: **[manykarim.github.io/robotframework-agenteval/keywords/AgentEval.html](https://manykarim.github.io/robotframework-agenteval/keywords/AgentEval.html)** (GitHub Pages) · local: [`docs/keywords/AgentEval.html`](./docs/keywords/AgentEval.html)

```robotframework
Library    AgentEval
```

| Keyword | Tier | What it does |
|---|---|---|
| **Send Prompt** | 2 | Execute a single-shot prompt against a coding-agent adapter |
| **Run Scenario** | 2 | Execute a scenario YAML file's `evals[]` against an adapter |
| **Load Scenario** | 1 | Load + validate a scenario YAML without executing |
| **Get Tool Call Count** | 1 | Number of tool calls made |
| **Get Tool Call Names** | 1 | Tool-call names in chronological order |
| **Get Tool Calls** | 1 | Full `ToolCallTrace` records |
| **Get Tool Hit Rate** | 1 | `\|expected ∩ observed\| / \|expected\|` |
| **Get Tool Success Rate** | 1 | `non-error / total` |
| **Get Unnecessary Call Rate** | 1 | `not_in_expected / total` |
| **Get Token Usage** | 1 | Token usage (input + output) |
| **Get Cost Total** | 1 | Total USD cost |
| **Get Latency** | 1 | Mean turn-level latency in ms |
| **Get Latency P95** | 1 | P95 latency in ms |
| **Tool Call Should Have Occurred** | 1 | Assert a tool call with given name + args occurred |
| **Trajectory Should Match** | 1 | Assert the tool-call trajectory matches expected (exact / subsequence / set) |
| **Agent Response Should Contain** | 1 | Assert substring appears in `response_text` |
| **Agent Response Should Match Regex** | 1 | Assert regex matches `response_text` |
| **Agent Response Should Match Schema** | 1 | Assert `response_text` (parsed JSON) validates against schema |
| **Stat.Run N Times** | 3 | Run a keyword `n` times independently (fan-out) |
| **Stat.Get Pass At K** | 1 | HumanEval Pass@k unbiased estimator |
| **Stat.Get Pass At K Confidence Interval** | 1 | Wilson score CI for Pass@k |
| **Stat.Assert Run Determinism** | 1 | Assert bit-identical Tier-1 output across 2 runs |
| **Get Keyword Tier** | 1 | Return the tier annotation for any RF keyword |
| **Get Spans** | 1 | All trace spans for the given test ID |
| **Get Run Manifest** | 1 | `RunManifest` for a test run (7+ fields per FR39) |
| **Get Last Warnings** | 1 | Warnings emitted during the run |
| **Get Cohort Heatmap** | 1 | Pass@k cohort heatmap (ASCII + dict per FR55; new in Story 8b.2) |
| **Get Config** | 1 | Parse a Claude Code `settings.json` hook configuration |
| **Get Effective Config** | 1 | Resolved config dict or single `ConfigValue` |
| **Get Effective Config With Provenance** | 1 | Full settings map with per-key provenance |

### `AgentEval.skills.library.SkillsLibrary` — 8 keywords

Full libdoc: **[manykarim.github.io/robotframework-agenteval/keywords/SkillsLibrary.html](https://manykarim.github.io/robotframework-agenteval/keywords/SkillsLibrary.html)** (GitHub Pages) · local: [`docs/keywords/SkillsLibrary.html`](./docs/keywords/SkillsLibrary.html)

```robotframework
Library    AgentEval.skills.library.SkillsLibrary    WITH NAME    Skill
```

| Keyword | Tier | What it does |
|---|---|---|
| **Get Frontmatter** | 1 | Parse YAML frontmatter from a skill `.md` file |
| **Get Description** | 1 | Return the `description` field |
| **Get Allowed Tools** | 1 | Return the `allowed-tools` list |
| **Get Disable Model Invocation** | 1 | Return the `disable-model-invocation` bool |
| **Should Be Valid Frontmatter** | 1 | Assert the 4 required fields + correct types |
| **Get Activation Decision** | 2 | Query an agent; infer whether the skill was activated |
| **Should Activate For** | 2 | Assert that the skill activates for a given prompt |
| **Get Discoverability** | 3 | Cohort discoverability — N trials × M tasks + per-task activation rates + aggregate summary |

### `AgentEval.mcp.library.MCPLibrary` — 9 keywords

Full libdoc: **[manykarim.github.io/robotframework-agenteval/keywords/MCPLibrary.html](https://manykarim.github.io/robotframework-agenteval/keywords/MCPLibrary.html)** (GitHub Pages) · local: [`docs/keywords/MCPLibrary.html`](./docs/keywords/MCPLibrary.html)

```robotframework
Library    AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP
```

| Keyword | Tier | What it does |
|---|---|---|
| **Get Server Config** | 1 | Parse a `.mcp.json` file's `mcpServers` declarations |
| **Start Server** | 1 | Build an `MCPServerHandle` (no spawn yet — Phase-1 per-call-session design) |
| **Connect To Server** | 1 | Actual MCP spawn + handshake (per-test scope per ADR-009) |
| **Stop Server** | 1 | Cleanup + process-group SIGTERM |
| **List Tools** | 1 | Enumerate tools advertised by a running MCP server |
| **Call Tool** | 1 | Roundtrip a tool call; returns `MCPToolResult` |
| **Get Tool Schema** | 1 | Tool input-schema JSON Schema dict |
| **Validate Tool Schema** | 1 | Assert a tool's input-schema satisfies a contract |
| **Get Tool Discoverability** | 2 | Single-runtime probe of whether the agent + MCP combo can discover an expected tool (FR10a) |

### `AgentEval.subagents.library.SubagentsLibrary` — 1 keyword

Full libdoc: **[manykarim.github.io/robotframework-agenteval/keywords/SubagentsLibrary.html](https://manykarim.github.io/robotframework-agenteval/keywords/SubagentsLibrary.html)** (GitHub Pages) · local: [`docs/keywords/SubagentsLibrary.html`](./docs/keywords/SubagentsLibrary.html)

`Get Frontmatter` — parallel to `SkillsLibrary.Get Frontmatter` for subagent `.md` files. Direct import; not composed into the top-level `AgentEval` library because of the name collision with `Skill.Get Frontmatter` (see [DF-7.1-S1](./docs/phase-1-5-carry-overs.md)).

### `AgentEval.hooks.library.HooksLibrary` — 1 keyword

Full libdoc: **[manykarim.github.io/robotframework-agenteval/keywords/HooksLibrary.html](https://manykarim.github.io/robotframework-agenteval/keywords/HooksLibrary.html)** (GitHub Pages) · local: [`docs/keywords/HooksLibrary.html`](./docs/keywords/HooksLibrary.html)

`Get Config` — Claude Code `settings.json` hook configuration parsing (also re-exported through the top-level `AgentEval.Get Config`).

## Keyword tiers

Keywords are annotated with a determinism tier that governs when results can be cached and how many times you should run them:

| Tier | Label | Determinism | Use case |
|---|---|---|---|
| **1** | Deterministic | Bit-identical across runs | Metrics, assertions, static inspection — run once |
| **2** | Stochastic Single-Shot | One LLM call per invocation | `Send Prompt`, activation decisions — re-run on flake |
| **3** | Stochastic Fan-Out | Multiple independent LLM calls | `Stat.Run N Times`, `Get Discoverability` — use statistical assertions |

Story 6.3 enforces the Tier-1 LLM-invocation ban (PRD FR30b) at adapter-entry per [ADR-002](./docs/adr/ADR-002-tier-1-adapter-ceiling-rule.md) — Tier-1 keywords cannot transitively invoke LLMs. Inspect tier at runtime:

```robotframework
${tier}=    AgentEval.Get Keyword Tier    Get Tool Call Count
Should Be Equal As Integers    ${tier}    1
```

## What this library is for

When you write Robot Framework tests for AI coding agents — Claude Code, Copilot CLI, Codex, Claude Agent SDK, OpenAI Agents SDK, custom MCP-using agents — `robotframework-agenteval` gives you the keyword vocabulary + trace observability + conformance harness to evaluate them honestly:

- **Tool-call inspection** — see what tools the agent called, what MCP servers it touched, where coverage degraded.
- **Skill / subagent / hook validation** — static-inspection keywords for the Claude-style skill ecosystem; activation-decision tests; cohort discoverability with Pass@k statistics.
- **Cohort comparison** — same scenario, multiple models, statistical assertions (Wilson CI, Pass@k, determinism).
- **Hosted-MCP observation** — universal trace fallback via the `Server.request_handlers` wrap pattern ([ADR-004](./docs/adr/ADR-004-hosted-mcp-observation.md)).
- **Honesty fields** — `mcp_coverage` with D1 trust-floor semantics ([ADR-016](./docs/adr/ADR-016-mcp-coverage-detection-default.md)) so partial-observation runs don't masquerade as full-coverage runs.
- **Conformance harness** — JSON + Markdown report generator with sysexits-mapped exit codes (FR50 + FR57; Story 8a.2).
- **Cohort heatmap** — ASCII + dict renderer for Pass@k across (task × model) grids (FR55; Story 8b.2 `CohortHeatmap`).
- **Terminal run summary** — opt-in via `AGENTEVAL_TERMINAL_SUMMARY=1` (FR54; Story 8b.2). Current Phase-1.5 carve-out per C71: pass/fail counts not yet captured.

## Recipes

| # | Recipe | Persona | What it shows |
|---|---|---|---|
| 1 | [First eval in 5 minutes](./docs/recipes/01-first-eval-in-five-minutes.md) | All | Minimal `Send Prompt` + tool-call assertion — the `agenteval init` walkthrough |
| 2 | [Pass@k over polling](./docs/recipes/02-pass-at-k-over-polling.md) | Devon | `Stat.Pass At K` as the polling replacement (ADR-019 prohibits polling per FR56) |
| 3 | [Tool discoverability cohort](./docs/recipes/03-tool-discoverability-cohort.md) | Raj | `MCP.Get Tool Discoverability` Pass@k across N trials × M tasks |
| 4 | [Skill-author stacked validation](./docs/recipes/04-skill-author-stacked-validation.md) | Devon | Tier-1 frontmatter check → Tier-2 activation → Tier-3 Pass@k stacked validation |
| 5 | [Dogfood — replacing custom Python tests](./docs/recipes/05-dogfood-replacing-custom-tests.md) | Raj | Port a downstream library's pytest corpus to `.robot` suites |
| 6 | [Custom protocol adapter](./docs/recipes/06-custom-protocol-adapter.md) | Raj | Implement `CodingAgentAdapter` for a non-canonical agent |
| 7 | [First MCP server test (Tier-1)](./docs/recipes/07-first-mcp-server-test-tier-1.md) | Raj | Static-inspection-only MCP config validation |
| 8 | [CI integration](./docs/recipes/08-ci-integration.md) | All | `dogfood-integration.yml` + `parity-suite-smoke` patterns |

Per-recipe details + cross-references live at [`docs/recipes/README.md`](./docs/recipes/README.md).

## Documentation

- **Keyword reference (GitHub Pages)** — [manykarim.github.io/robotframework-agenteval](https://manykarim.github.io/robotframework-agenteval/) — hosted libdoc HTML for all 5 libraries: [AgentEval](https://manykarim.github.io/robotframework-agenteval/keywords/AgentEval.html) · [SkillsLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/SkillsLibrary.html) · [MCPLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/MCPLibrary.html) · [SubagentsLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/SubagentsLibrary.html) · [HooksLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/HooksLibrary.html). Local copies under [`docs/keywords/`](./docs/keywords/) — regenerated via `python -m robot.libdoc`.
- **Architecture decisions** — [`docs/adr/`](./docs/adr/) — 19 ADRs (ADR-001 catalog + ADR-002 → ADR-019) covering adapter protocols, tier rules, MCP observation, coverage semantics, error hierarchy, assertion-engine adoption, and more
- **Contracts** — [`docs/contracts/`](./docs/contracts/) — stable surfaces consumers can rely on (12 contract docs at Phase-1 close)
- **Recipes** — [`docs/recipes/`](./docs/recipes/) — 8 worked examples covering Devon + Raj + Many personas
- **Exit criteria for 1.0** — [`docs/contracts/exit-criteria-0x-to-1x.md`](./docs/contracts/exit-criteria-0x-to-1x.md) — 6 ratified promotion criteria (`accepted` status per Story 9.3)
- **Phase-1 retrospective** — [`_bmad-output/planning-artifacts/phase-1-retrospective-2026-05-25.md`](./_bmad-output/planning-artifacts/phase-1-retrospective-2026-05-25.md)
- **Phase-1.5 carry-over catalog** — [`docs/phase-1-5-carry-overs.md`](./docs/phase-1-5-carry-overs.md) — 71 entries at Phase-1 close, categorised XS/S/M/L by effort
- **Review methodology** — [MAINTAINERS.md §Review methodology](./MAINTAINERS.md#review-methodology) — the 23 ratified `feedback_*` norms governing project quality bar
- **Troubleshooting** — [`docs/troubleshooting/`](./docs/troubleshooting/) — first-day issues and workarounds

## Known limitations

- **macOS validation deferred to Phase-1.5.** Phase 1 + Phase 2 validate on Linux only per D2.1 architect waiver (inherited from Story 0.2). Community macOS reproductions welcome.
- **Exact version pins.** `mcp==1.27.1` + `robotframework==7.4.2` + `robotframework-pabot==5.2.2` + `anyio==4.13.0` are spike-validated. `AdapterVersionDriftWarning` (FR60, Phase-1.5) will detect future MCP SDK refactors that break the `request_handlers` wrap pattern.
- **`SkillsLibrary` + `SubagentsLibrary` + `HooksLibrary` + `MCPLibrary` not in the top-level `AgentEval` import.** They must be imported directly (see Quick start examples). The name collision on `Get Frontmatter` prevents composition ([DF-7.1-S1](./docs/phase-1-5-carry-overs.md)).
- **No PyPI release yet.** Phase 1 is foundational. Public release + semver stability gated on the 6 exit criteria at [`exit-criteria-0x-to-1x.md`](./docs/contracts/exit-criteria-0x-to-1x.md).
- **Phase-2 SDK adapters at `experimental`.** `ClaudeAgentSDKAdapter` + `OpenAIAgentsSDKAdapter` carry pre-1.0 SDK pins (`claude-agent-sdk>=0.1.0,<1.0`, `openai-agents>=0.1.0,<1.0`); shape may shift. Defensive `_extract_usage` paths catalogued at C70 (`DF-10.2-S2`) for cleanup after live-SDK probe.
- **Terminal run summary pass/fail counts not populated** (Story 8b.2 honest framing). Listener does not snapshot RF `result.passed` per test yet; display shows `"—"` sentinel + `[Phase-1.5 C71]` marker until C71 lands.

## Project posture

**Solo + AI-agent-assisted** development using the [BMad method](https://github.com/bmad-sim/bmad-method). See [MAINTAINERS.md](./MAINTAINERS.md) for the maintenance model.

The project uses **cross-LLM adversarial review** as a load-bearing quality control — every Tier-2/Tier-3 keyword PR is reviewed by ≥2 different LLM families (Claude CLI + Codex CLI + kilocode/minimax). 30+ load-bearing catches across Epics 2-7; methodology preserved into Phase 2 via `feedback_third_llm_family_fallback` (kilocode/minimax delivers when Claude + Codex CLIs degrade). See [MAINTAINERS.md §Review methodology](./MAINTAINERS.md#review-methodology) for the 23 ratified norms governing the project's quality bar.

## License

[Apache 2.0](./LICENSE).
