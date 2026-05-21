# robotframework-agenteval

Robot Framework library for evaluating AI coding agents — skills, subagents, hooks, MCP servers, and tool calls.

## Status

**Pre-alpha — Phase 1 in active development (v0.0.1).** The core keyword surface is functional and dogfooded against [`robotframework-agentskills`](https://github.com/manykarim/robotframework-agentskills). No stable public API yet; breaking changes can happen before 1.0.

## Install

```bash
uv add robotframework-agenteval
```

Once published. Pre-release, clone and sync:

```bash
git clone https://github.com/manykarim/robotframework-agenteval.git
cd robotframework-agenteval
uv sync
uv run python -c "import AgentEval; print(AgentEval.__version__)"
# → 0.0.1
```

## Quick start

```robotframework
*** Settings ***
Library    AgentEval    WITH NAME    AgentEval

*** Test Cases ***
Agent calls the right tool
    ${result}=    AgentEval.Send Prompt
    ...    prompt=Search the web for Robot Framework tutorials
    ...    adapter=litellm
    ...    model=claude-sonnet-4-5
    AgentEval.Tool Call Should Have Occurred    ${result}    web_search
    Should Be Equal As Numbers    ${result.cost_usd}    0    msg=sanity: non-zero cost
```

## Keywords at a glance

### `AgentEval` library (29 keywords)

Full libdoc: [`docs/keywords/AgentEval.html`](./docs/keywords/AgentEval.html)

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
| **Stat.Get Pass At K** | 1 | HumanEval Pass@k estimate |
| **Stat.Get Pass At K Confidence Interval** | 1 | Wilson score CI for Pass@k |
| **Stat.Assert Run Determinism** | 1 | Assert bit-identical Tier-1 output across 2 runs |
| **Get Keyword Tier** | 1 | Return the tier annotation for any RF keyword |
| **Get Spans** | 1 | All trace spans for the given test ID |
| **Get Run Manifest** | 1 | 7-field `RunManifest` for a test run |
| **Get Last Warnings** | 1 | Warnings emitted during the run |
| **Get Config** | 1 | Parse a Claude Code `settings.json` hook configuration |
| **Get Effective Config** | 1 | Resolved config dict or single `ConfigValue` |
| **Get Effective Config With Provenance** | 1 | Full settings map with per-key provenance |

### `AgentEval.skills.library.SkillsLibrary` (8 keywords)

> Import directly — `SkillsLibrary` is not composed into the top-level `AgentEval` library.

Full libdoc: [`docs/keywords/SkillsLibrary.html`](./docs/keywords/SkillsLibrary.html)

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
| **Get Discoverability** | 3 | Cohort discoverability evaluation — runs N trials × M tasks, returns per-task activation rates + aggregate summary |

## Keyword tiers

Keywords are annotated with a determinism tier that governs when results can be cached and how many times you should run them:

| Tier | Label | Determinism | Use case |
|---|---|---|---|
| **1** | Deterministic | Bit-identical across runs | Metrics, assertions, static inspection — run once |
| **2** | Stochastic Single-Shot | One LLM call per invocation | `Send Prompt`, activation decisions — re-run on flake |
| **3** | Stochastic Fan-Out | Multiple independent LLM calls | `Stat.Run N Times`, `Get Discoverability` — use statistical assertions |

Inspect tier at runtime:

```robotframework
${tier}=    AgentEval.Get Keyword Tier    Get Tool Call Count
Should Be Equal As Integers    ${tier}    1
```

## What this library is for

When you write Robot Framework tests for AI coding agents — Claude Code, Copilot CLI, Codex, OpenAI Agents SDK, custom MCP-using agents — `robotframework-agenteval` gives you the keyword vocabulary + trace observability + conformance harness to evaluate them honestly:

- **Tool-call inspection** — see what tools the agent called, what MCP servers it touched, where coverage degraded.
- **Skill / subagent / hook validation** — static-inspection keywords for the Claude-style skill ecosystem; activation-decision tests; cohort discoverability with Pass@k statistics.
- **Cohort comparison** — same scenario, multiple models, statistical assertions (Wilson CI, Pass@k, determinism).
- **Hosted-MCP observation** — universal trace fallback via the `Server.request_handlers` wrap pattern ([ADR-004](./docs/adr/ADR-004-hosted-mcp-observation.md)).
- **Honesty fields** — `mcp_coverage` with D1 trust-floor semantics ([ADR-016](./docs/adr/ADR-016-mcp-coverage-detection-default.md)) so partial-observation runs don't masquerade as full-coverage runs.

## Recipes

| Recipe | Description |
|---|---|
| [`04-skill-author-stacked-validation.md`](./docs/recipes/04-skill-author-stacked-validation.md) | Devon's stacked validation recipe — verifying a skill file passes all Tier-1 checks then measuring activation reliability with Pass@k |

## Documentation

- **Keyword reference** — [`docs/keywords/AgentEval.html`](./docs/keywords/AgentEval.html) · [`docs/keywords/SkillsLibrary.html`](./docs/keywords/SkillsLibrary.html) (generated by `python -m robot.libdoc`)
- **Architecture decisions** — [`docs/adr/`](./docs/adr/) — 19 ADRs covering adapter protocols, tier rules, MCP observation, coverage semantics, error hierarchy, and more
- **Contracts** — [`docs/contracts/`](./docs/contracts/) — stable surfaces consumers can rely on
- **Recipes** — [`docs/recipes/`](./docs/recipes/) — copy-paste solutions for common evaluation patterns
- **Troubleshooting** — [`docs/troubleshooting/`](./docs/troubleshooting/) — first-day issues and workarounds

## Generate keyword docs locally

```bash
uv run python -m robot.libdoc AgentEval docs/keywords/AgentEval.html
uv run python -m robot.libdoc AgentEval.skills.library.SkillsLibrary docs/keywords/SkillsLibrary.html
```

## Known limitations

- **macOS validation deferred to Phase-1.5.** Phase 1 validates on Linux only per D2.1 architect waiver (Story 0.2). Community macOS reproductions welcome.
- **Exact version pins.** `mcp==1.27.1` + `robotframework==7.4.2` + `robotframework-pabot==5.2.2` + `anyio==4.13.0` are spike-validated. `AdapterVersionDriftWarning` (planned for Phase-1.5) will detect future MCP SDK refactors that break the `request_handlers` wrap pattern.
- **`SkillsLibrary` not in the top-level `AgentEval` import.** It must be imported directly as `AgentEval.skills.library.SkillsLibrary` — the name collision with `SubagentsLibrary` on `Get Frontmatter` prevents it being composed in ([DF-7.1-S1](./docs/phase-1-5-carry-overs.md)).
- **No PyPI release yet.** Phase 1 is foundational. Public release and semver stability at 1.0.

## Project posture

**Solo + AI-agent-assisted** development using the [BMad method](https://github.com/bmad-sim/bmad-method). See [MAINTAINERS.md](./MAINTAINERS.md) for the maintenance model and ratified review-methodology norms.

## License

[Apache 2.0](./LICENSE).
