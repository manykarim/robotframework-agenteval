# robotframework-agenteval

Robot Framework library for evaluating AI coding agents — skills, subagents, hooks, MCP servers, and tool calls.

## Status

**Phase 1 complete (2026-05-25) · Phase 2 in progress.** Version `0.0.1` is feature-complete for the Phase 1 surface. Phase 2 has shipped native Agent SDK adapters for Anthropic + OpenAI, CLI adapters for Codex + Copilot with adapter-version-drift warnings, and the LLM-Judge + rubric-calibration surface (`Judge.Get Score` + `Judge.Calibrate Rubric` with a Cohen's-kappa hard-fail).

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

The examples run on the keyless **mock provider**. To switch to a real model, see [Running against a real model](./docs/running-against-a-real-model.md).

## Adapters

Four ratified adapters as of Phase 2 launch. Adapters are discovered via the `agenteval.coding_agents` entry-points group; the `register_adapter()` Python API is also supported.

| Adapter | Entry-point name | Extra | Stability |
|---|---|---|---|
| `GenericAdapter` (LiteLLM-backed) | `generic` | core (no extra) | `provisional` |
| `ClaudeCodeCLIAdapter` | `claude-code-cli` | `[claude-code]` | `provisional` |
| `ClaudeAgentSDKAdapter` | `claude-agent-sdk` | `[claude-sdk]` | `experimental` |
| `OpenAIAgentsSDKAdapter` | `openai-agents-sdk` | `[openai-agents]` | `experimental` |

See the [adapter protocol decision](./docs/adr/ADR-003-coding-agent-adapter-protocol-internal-class-split.md) for the `InProcessAdapter` / `SubprocessAdapter` split and the [entry-points discovery decision](./docs/adr/ADR-013-entry-points-discovery-infrastructure.md) for the discovery mechanism. The `experimental` adapters carry pre-1.0 SDK pins and may shift; promotion to `stable` is gated on the 3-month-no-break window.

## Command-line interface

```bash
# Scaffold a fresh starter project (8 files; the 5-minute first-run path)
agenteval init [directory]

# Scaffold a new CodingAgentAdapter (SubprocessAdapter or InProcessAdapter)
agenteval new-adapter <name> [--protocol stdio|inprocess]

# Run the conformance suite + emit JSON + Markdown reports
python -m AgentEval.conformance --adapter <name> --output-dir reports/

# Generate keyword reference HTML for all 6 libraries (RF libdoc)
uv run python -m robot.libdoc AgentEval docs/keywords/AgentEval.html
uv run python -m robot.libdoc AgentEval.skills.library.SkillsLibrary docs/keywords/SkillsLibrary.html
uv run python -m robot.libdoc AgentEval.subagents.library.SubagentsLibrary docs/keywords/SubagentsLibrary.html
uv run python -m robot.libdoc AgentEval.hooks.library.HooksLibrary docs/keywords/HooksLibrary.html
uv run python -m robot.libdoc AgentEval.mcp.library.MCPLibrary docs/keywords/MCPLibrary.html
uv run python -m robot.libdoc AgentEval.judge.library.JudgeLibrary docs/keywords/JudgeLibrary.html
```

Committing the regenerated `docs/keywords/*.html` updates GitHub Pages automatically (Pages is configured to serve from `main` branch's `/docs` folder).

Exit codes from `python -m AgentEval.conformance` follow the sysexits-style 24-leaf mapping at [`docs/contracts/error-class-hierarchy.md`](./docs/contracts/error-class-hierarchy.md) L66-L107 (`EXIT_CODE_FALLBACK = 70` when fixtures fail).

## Keywords at a glance

**98 keywords across 14 libraries — one import.** A single `Library    AgentEval` line composes every shipped sub-library (skills, subagents, hooks, MCP, stats, judge, red-team, regression baselines, plus the core run-measure-assert loop) and exposes all 98 keywords with no `WITH NAME` incantation. **Naming rule:** keywords that operate on a specific artifact or engine — skills, subagents, hooks, MCP servers, statistics, LLM-judge, red-team probes — carry that namespace prefix (`Skill.` / `Subagent.` / `Hook.` / `MCP.` / `Stat.` / `Judge.` / `RedTeam.`); the shared run-measure-assert loop (`Send Prompt`, `Get Tool Call Count`, `Trajectory Should Match`, `Get Effective Config`, …) is unprefixed. The tables below group the keywords by originating sub-library, but every one of them resolves under the single top-level import. Each sub-library remains importable standalone by module path (`Library    AgentEval.skills.library.SkillsLibrary    max_cost_usd=2.0`) for per-library budget scoping — the baked prefixes make the call sites identical under both styles, so no `WITH NAME` is needed (and adding it produces a pointless double prefix like `Skill.Skill.Get Frontmatter`).

### `AgentEval` — core-loop keywords (60 of the 95)

The composed `AgentEval` library holds all 98 keywords. The 63 below are the unprefixed run-measure-assert loop plus the `Stat.*`, `Judge.*`, and `Hook.*` keywords (including the three regression-baseline keywords `Save Metrics Baseline`, `Metrics Should Not Regress`, `Get Metric Trend`); the remaining 35 (`Skill.*`, `MCP.*`, `Subagent.*`, `RedTeam.*`) are listed in the sub-library sections further down and resolve under the same single import.

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
| **Cost Should Be Below** | 1 | Assert total USD cost is strictly below a threshold |
| **Latency Should Be Below** | 1 | Assert mean turn-level latency (ms) is strictly below a threshold |
| **Latency P95 Should Be Below** | 1 | Assert P95 latency (ms) is strictly below a threshold |
| **Token Usage Should Be Below** | 1 | Assert total tokens (input + output) is strictly below a threshold |
| **Stat.Run N Times** | 3 | Run a keyword `n` times independently (fan-out) |
| **Stat.Get Pass At K** | 1 | HumanEval Pass@k unbiased estimator |
| **Stat.Get Pass At K Confidence Interval** | 1 | Wilson score CI for Pass@k |
| **Stat.Assert Run Determinism** | 1 | Assert bit-identical Tier-1 output across 2 runs |
| **Stat.Mann Whitney U** | 1 | Mann-Whitney U test between two keyword-run distributions |
| **Stat.Cliff Delta** | 1 | Cliff's delta effect size between two distributions |
| **Stat.Bootstrap Confidence Interval** | 1 | Bootstrap confidence interval for a metric across runs |
| **Get Keyword Tier** | 1 | Return the tier annotation for any RF keyword |
| **Get Spans** | 1 | All trace spans for the given test ID |
| **Get Run Manifest** | 1 | `RunManifest` for a test run (7+ fields) |
| **Get Last Warnings** | 1 | Warnings emitted during the run |
| **Get Cohort Heatmap** | 1 | Pass@k cohort heatmap (ASCII + dict) |
| **Hook.Get Config** | 1 | Parse a Claude Code `settings.json` hook configuration |
| **Hook.Fire Hook Event** | 1 | Fire a synthetic hook event — execute matching command hooks + capture exit/stdout/decision (executes local scripts) |
| **Hook.Decision Should Be** | 1 | Assert a fired hook's normalized block/allow/ask/none decision (`deny` = `block`) |
| **Hook.Exit Code Should Be** | 1 | Assert a fired hook's raw subprocess exit code |
| **Hook.Output Field Should Be** | 1 | Assert a dotted field in a fired hook's parsed stdout JSON |
| **Hook.Get Hooks For Event** | 1 | Static "which hooks would fire for tool X?" simulation — no execution |
| **Hook.Validate Matcher Syntax** | 1 | Validate a matcher compiles (Python `re`), optionally test a subject |
| **Hook.Command Should Exist** | 1 | Assert each hook command's first token resolves to an executable on disk |
| **Get Effective Config** | 1 | Resolved config dict, or single `ConfigValue(value, source)` via `setting=<key>` |
| **Judge.Get Score** | 2 | LLM-judge scoring of an `AgentRunResult` against a Markdown rubric |
| **Judge.Calibrate Rubric** | 2 | Run the judge against a YAML calibration set; compute Cohen's kappa + threshold-tuning + bias diagnostics (κ ≥ 0.7 hard-fail) |
| **Judge.Score With Criteria** | 2 | One-line judging from a plain-language criteria string (no rubric file); returns `JudgeScore` with `calibrated=False` |
| **Judge.Get Faithfulness** | 2 | Metric preset — is every claim in the response supported by the supplied `context`? |
| **Judge.Get Answer Relevancy** | 2 | Metric preset — does the response address the supplied `question`? |
| **Judge.Get Hallucination Score** | 2 | Metric preset — grounding score (higher = less hallucination; 10.0 = none) vs the supplied `context` |
| **Judge.Get Preset Rubric** | 1 | Return a preset's `JudgeRubric` for the graduation path (→ `Judge.Calibrate Rubric`) |
| **Judge Score Should Be Above** | 2 | Judge-and-assert in one line from a criteria string; fails with the judge's reasoning |
| **Judge Turn Should Pass** | 2 | Score one conversation turn against a rubric; fail the test unless it passes (out-of-range turn fails without an LLM call) |
| **Start Conversation** | 1 | Start a multi-turn conversation; returns a test-owned `ConversationHandle` (no LLM call until the first `Send Message`) |
| **Send Message** | 2 | Send one user message; returns the agent turn's `AgentRunResult` (threaded natively or via honest history-replay) |
| **Get Conversation Transcript** | 1 | Immutable `ConversationTranscript` snapshot (turns + reconciled aggregates + `continuation_mode`) |
| **End Conversation** | 1 | Close the handle + release native session resources (transcript stays readable) |
| **Transcript Should Contain** | 1 | Assert a turn of the selected role contains text (substring or regex) |
| **Simulate User** | 3 | LLM-driven user simulator (persona/goal/max_turns); Tier-3 budget-guarded; `cache_key` repeatability |
| **Get Conversation Results** | 1 | Extract the per-turn `list[AgentRunResult]` so every metric keyword aggregates over a conversation |
| **Get Turn Count** | 1 | Number of agent turns in a conversation |

### `AgentEval.judge.library.JudgeLibrary` — 9 keywords

Full libdoc: **[manykarim.github.io/robotframework-agenteval/keywords/JudgeLibrary.html](https://manykarim.github.io/robotframework-agenteval/keywords/JudgeLibrary.html)** (GitHub Pages) · local: [`docs/keywords/JudgeLibrary.html`](./docs/keywords/JudgeLibrary.html)

Composed into `AgentEval` via `_SUB_LIBRARIES` — every `Judge.*` keyword (plus the un-namespaced `Judge Score Should Be Above` assertion) resolves under the plain `Library    AgentEval` import. The standalone module-path import works too (and lets operators pass `max_cost_usd` / `max_runtime_seconds` budgets directly — no `WITH NAME`, the `Judge.` prefix is already baked in):

```robotframework
Library    AgentEval.judge.library.JudgeLibrary    max_cost_usd=1.0
```

| Keyword | Tier | What it does |
|---|---|---|
| **Judge.Get Score** | 2 | LLM-judge scoring against a Markdown rubric; returns `JudgeScore` (numeric_score 0-10 + pass_threshold_met + reasoning + criteria_breakdown + cost_usd + `calibrated` + `rubric_source`) |
| **Judge.Calibrate Rubric** | 2 | Cohen's-kappa calibration over a YAML calibration set; returns `CalibrationReport` with `passes_hard_fail` (κ ≥ 0.7), `threshold_tuning`, `recommended_threshold`, `systematic_bias_diagnostics` |
| **Judge.Score With Criteria** | 2 | One-line judging from a plain-language `criteria` string — no rubric file (DeepEval G-Eval idiom). Always `calibrated=False`, `rubric_source="criteria_string"`, with a WARN-once graduation nudge |
| **Judge.Get Faithfulness** | 2 | Preset: every factual claim in the response is supported by the supplied `context` (`rubric_source="preset:faithfulness"`) |
| **Judge.Get Answer Relevancy** | 2 | Preset: the response directly addresses the supplied `question` (`rubric_source="preset:answer_relevancy"`) |
| **Judge.Get Hallucination Score** | 2 | Preset: grounding score, **higher = less hallucination** (10.0 = none detected), vs the supplied `context` — uniform `>= threshold` pass semantics (`rubric_source="preset:hallucination"`) |
| **Judge.Get Preset Rubric** | 1 | Return a preset's `JudgeRubric` (no LLM call) so it feeds `Judge.Calibrate Rubric` — the graduation path for presets |
| **Judge Score Should Be Above** | 2 | Judge-and-assert in one line from a `criteria` string; `>=` pass semantics; fails with the numeric score, threshold, uncalibrated marker, and judge reasoning |
| **Judge Turn Should Pass** | 2 | Score a selected conversation turn against a rubric (negative indices allowed); fails the test unless the turn passes; out-of-range index fails without an LLM call (add-multi-turn-conversation-testing) |

Two-tier honesty (the project brand): `Judge.Score With Criteria` + the presets are the **one-line on-ramp** — they always return `calibrated=False` and a truthful `rubric_source`, and emit a documented WARN-once pointing at the graduation path. For CI gates, graduate to a **calibrated rubric** (κ ≥ 0.7 hard-fail) — see the [Judge calibration cookbook](./docs/recipes/judge-calibration.md). Presets ship **uncalibrated by default** (no bundled κ claims); calibrate them against your own labels via `Judge.Get Preset Rubric` → `Judge.Calibrate Rubric` with the [per-preset templates](./docs/examples/judge-presets/).

### `AgentEval.skills.library.SkillsLibrary` — 11 keywords

Full libdoc: **[manykarim.github.io/robotframework-agenteval/keywords/SkillsLibrary.html](https://manykarim.github.io/robotframework-agenteval/keywords/SkillsLibrary.html)** (GitHub Pages) · local: [`docs/keywords/SkillsLibrary.html`](./docs/keywords/SkillsLibrary.html)

Reachable under the plain `Library    AgentEval` import. Standalone module-path import (for budget scoping) works too — no `WITH NAME`, the `Skill.` prefix is baked in:

```robotframework
Library    AgentEval.skills.library.SkillsLibrary    max_cost_usd=2.0
```

| Keyword | Tier | What it does |
|---|---|---|
| **Skill.Get Frontmatter** | 1 | Parse YAML frontmatter from a skill `.md` file |
| **Skill.Get Description** | 1 | Return the `description` field |
| **Skill.Get Allowed Tools** | 1 | Return the `allowed-tools` list |
| **Skill.Get Disable Model Invocation** | 1 | Return the `disable-model-invocation` bool |
| **Skill.Should Be Valid Frontmatter** | 1 | Assert the 4 required fields + correct types |
| **Skill.Get Activation Decision** | 2 | Query an agent; infer whether the skill was activated |
| **Skill.Should Activate For** | 2 | Assert that the skill activates for a given prompt |
| **Skill.Get Discoverability** | 3 | Cohort discoverability — N trials × M tasks + per-task activation rates + aggregate summary |
| **Skill.Get Activation Pass At K** | 1 | Pass@k activation rate for a skill from a discoverability result |
| **Skill.Compare Discoverability** | 3 | Compare skill discoverability across ≥2 adapters with statistical significance |
| **Skill.Compare Against Baseline** | 3 | A/B benchmark a skill vs a no-skill (or v1-vs-v2) baseline — per-arm pass rate/tokens/time + significance + blind grading + obsolescence verdict |

### `AgentEval.mcp.library.MCPLibrary` — 10 keywords

Full libdoc: **[manykarim.github.io/robotframework-agenteval/keywords/MCPLibrary.html](https://manykarim.github.io/robotframework-agenteval/keywords/MCPLibrary.html)** (GitHub Pages) · local: [`docs/keywords/MCPLibrary.html`](./docs/keywords/MCPLibrary.html)

Reachable under the plain `Library    AgentEval` import. Standalone module-path import (for budget scoping) works too — no `WITH NAME`, the `MCP.` prefix is baked in:

```robotframework
Library    AgentEval.mcp.library.MCPLibrary    max_cost_usd=10.0
```

| Keyword | Tier | What it does |
|---|---|---|
| **MCP.Get Server Config** | 1 | Parse a `.mcp.json` file's `mcpServers` declarations |
| **MCP.Start Server** | 1 | Build an `MCPServerHandle` (no spawn yet — Phase-1 per-call-session design) |
| **MCP.Connect To Server** | 1 | Actual MCP spawn + handshake (per-test scope) |
| **MCP.Stop Server** | 1 | Cleanup + process-group SIGTERM |
| **MCP.List Tools** | 1 | Enumerate tools advertised by a running MCP server |
| **MCP.Call Tool** | 1 | Roundtrip a tool call; returns `MCPToolResult` |
| **MCP.Get Tool Schema** | 1 | Tool input-schema JSON Schema dict |
| **MCP.Validate Tool Schema** | 1 | Assert a tool's input-schema satisfies a contract |
| **MCP.Get Tool Discoverability** | 3 | Cohort probe of whether the agent + MCP combo discovers the expected tools across N trials |
| **MCP.Compare Tool Discoverability** | 3 | Compare Tool Discoverability across ≥2 adapters with Mann-Whitney U significance |

### `AgentEval.subagents.library.SubagentsLibrary` — 10 keywords

Full libdoc: **[manykarim.github.io/robotframework-agenteval/keywords/SubagentsLibrary.html](https://manykarim.github.io/robotframework-agenteval/keywords/SubagentsLibrary.html)** (GitHub Pages) · local: [`docs/keywords/SubagentsLibrary.html`](./docs/keywords/SubagentsLibrary.html)

Static inspection:

- `Subagent.Get Frontmatter` — parse a subagent `.md`'s YAML frontmatter (parallel to `Skill.Get Frontmatter`; validates required `name`/`description` plus optional `tools`/`model`/`skills`).

Delegation-routing assertions over an `AgentRunResult` (Tier-1 — deterministic, no agent calls; delegations are read from the already-captured `Task`-tool invocations in `result.tool_calls`):

- `Subagent.Get Delegations` — extract the ordered list of orchestrator→subagent delegations.
- `Subagent.Should Have Delegated To` — assert the run delegated to a named subagent.
- `Subagent.Should Not Have Delegated` — assert no delegation (optionally to a specific subagent).
- `Subagent.Get Routing Pass At K` — HumanEval Pass@k over routing-decision trials (hard-coded predicate; pairs with `Stat.Run N Times`).

Routing probe + cohort (adapter-dependent):

- `Subagent.Should Delegate To` (Tier-2) — run a prompt once and assert the chosen subagent.
- `Subagent.Get Delegation Decision` (Tier-3) — return a routing decision (never raises on a miss).
- `Subagent.Get Routing Accuracy` (Tier-3) — tasks-YAML cohort → per-task Pass@k + aggregate routing accuracy.

Config-drift static checks (subagents do **not** inherit parent skills/tools, so absent declarations fail loud):

- `Subagent.Should Declare Skills` — assert explicit `skills:` preloading in the frontmatter.
- `Subagent.Tools Should Be Subset Of` — assert the declared `tools:` are within an allowlist.

All composed into the top-level `AgentEval` library; every keyword resolves under a single `Library    AgentEval` import.

### `AgentEval.hooks.library.HooksLibrary` — 1 keyword

Full libdoc: **[manykarim.github.io/robotframework-agenteval/keywords/HooksLibrary.html](https://manykarim.github.io/robotframework-agenteval/keywords/HooksLibrary.html)** (GitHub Pages) · local: [`docs/keywords/HooksLibrary.html`](./docs/keywords/HooksLibrary.html)

`Hook.Get Config` — Claude Code `settings.json` hook configuration parsing. Composed into the top-level `AgentEval` library, so it resolves under a plain `Library    AgentEval` import.

### `AgentEval.redteam.library.RedTeamLibrary` — 4 keywords

Full libdoc: **[manykarim.github.io/robotframework-agenteval/keywords/RedTeamLibrary.html](https://manykarim.github.io/robotframework-agenteval/keywords/RedTeamLibrary.html)** (GitHub Pages) · local: [`docs/keywords/RedTeamLibrary.html`](./docs/keywords/RedTeamLibrary.html)

**Defensive** single-turn adversarial-robustness testing of an agent you own — a curated, versioned probe pack (`prompt_injection` / `jailbreak` / `pii_leakage` / `encoding_obfuscation`, 24 attributed probes) plus keywords to run probes, detect refusals, and gate on an attack-success-rate. Composed into the top-level `AgentEval` library.

| Keyword | Tier | Purpose |
|---|---|---|
| `RedTeam.Run Probe` | 3 | Run one probe (`probe=<id>`) or a whole category (`probe=all`) against an adapter; returns a structured `ProbeResult` / `list[ProbeResult]`. Fan-out honors `max_cost_usd`. |
| `RedTeam.Should Refuse` | 2 | Assert a probe result is a refusal (the SAFE outcome); `strategy=pattern` (default, credential-free) / `judge` / `both`. |
| `RedTeam.Get Attack Success Rate` | 1 | Reduce probe results to the attack-success-rate — compliance fraction, **lower is safer**, a fully-refusing agent scores `0.0` — with a Wilson CI reused from the Pass@k machinery. |
| `RedTeam.Attack Success Rate Should Be Below` | 1 | CI-gating assertion: fail when the attack-success-rate is at or above a threshold. |

Multi-turn / Crescendo-style escalating attacks are a documented future extension (they build on `ConversationLibrary`'s `Simulate User`). Extend the corpus without forking via `RedTeam.Run Probe    probe_pack=your-probes.yaml`.

## Keyword tiers

Each keyword is tagged with a **determinism tier** (1 = deterministic, 2 = one LLM call, 3 = multiple LLM calls). Tier 1 keywords need no API key and run once; tiers 2 and 3 are stochastic. You rarely need to think about this to get started — the [determinism contract](./docs/contracts/determinism-contract.md) has the full model. Inspect any keyword's tier at runtime with `AgentEval.Get Keyword Tier`.

## What this library is for

When you write Robot Framework tests for AI coding agents — Claude Code, Copilot CLI, Codex, Claude Agent SDK, OpenAI Agents SDK, custom MCP-using agents — `robotframework-agenteval` gives you the keyword vocabulary + trace observability + conformance harness to evaluate them honestly:

- **Tool-call inspection** — see what tools the agent called, what MCP servers it touched, where coverage degraded.
- **Skill / subagent / hook validation** — static-inspection keywords for the Claude-style skill ecosystem; activation-decision tests; cohort discoverability with Pass@k statistics.
- **Cohort comparison** — same scenario, multiple models, statistical assertions (Wilson CI, Pass@k, determinism).
- **Hosted-MCP observation** — universal trace fallback via the [`Server.request_handlers` wrap pattern](./docs/adr/ADR-004-hosted-mcp-observation.md).
- **Honesty fields** — `mcp_coverage` with [trust-floor semantics](./docs/adr/ADR-016-mcp-coverage-detection-default.md) so partial-observation runs don't masquerade as full-coverage runs.
- **Conformance harness** — JSON + Markdown report generator with sysexits-mapped exit codes.
- **Cohort heatmap** — ASCII + dict renderer for Pass@k across (task × model) grids (`CohortHeatmap`).
- **Terminal run summary** — opt-in via `AGENTEVAL_TERMINAL_SUMMARY=1`.

## Writing a skill file

A skill is a Markdown file with a YAML frontmatter block. Four fields are
required:

| Field | Type | Meaning |
|---|---|---|
| `name` | string | The skill's identifier. |
| `description` | string | What the skill does / when it activates. |
| `allowed-tools` | list of strings | Tools the skill may use. |
| `disable-model-invocation` | boolean | Whether the model may auto-invoke the skill. |

A minimal, complete `SKILL.md`:

```markdown
---
name: example-search
description: Activates on prompts asking for search-related tasks.
allowed-tools: ["search", "fetch"]
disable-model-invocation: false
---

# Example Search Skill

Replace this with your own skill instructions.
```

Validate it with the `Skill.*` keywords (composed into the single import):

```robotframework
*** Settings ***
Library    AgentEval

*** Test Cases ***
Skill Frontmatter Is Valid
    ${frontmatter}=    Skill.Get Frontmatter    ${CURDIR}/SKILL.md
    Skill.Should Be Valid Frontmatter    ${frontmatter}
```

## Hook configuration

`Hook.Get Config` (composed into `AgentEval`) parses a `settings.json`
hook file in the real Claude Code schema: a top-level `hooks` mapping where each
key is an event name (`PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`, ...)
and the value is a list of **matcher groups**. Each group has an optional
`matcher` and a required `hooks` list of typed hook definitions (`type` is one
of `command`, `http`, `mcp_tool`, `prompt`, `agent`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "./scripts/guard.sh",
            "args": ["--strict"],
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

`Hook.Get Config` **flattens** matcher groups: each inner hook definition becomes one
entry keyed by the plain event name, with the group's `matcher` copied onto it
and a `type` field always present:

```robotframework
*** Settings ***
Library    AgentEval

*** Test Cases ***
Hook Config Parses
    ${config}=    Hook.Get Config    ${CURDIR}/settings.json
    # Hook.Get Config returns entries keyed by the plain event name.
    Should Contain    ${config}    PreToolUse
    Should Be Equal    ${config}[PreToolUse][0][type]    command
```

> **Note:** the legacy flat entry shape (a `command` directly in the event list,
> no matcher group) is still accepted for backward compatibility but emits a
> `DeprecationWarning` — migrate configs to the nested Claude Code schema above.

## Recipes

| # | Recipe | What it demonstrates |
|---|---|---|
| 1 | [First eval in 5 minutes](./docs/recipes/01-first-eval-in-five-minutes.md) | Minimal `Send Prompt` + tool-call assertion — the `agenteval init` walkthrough |
| 2 | [Pass@k over polling](./docs/recipes/02-pass-at-k-over-polling.md) | `Stat.Get Pass At K` as the replacement for polling-retry |
| 3 | [Tool discoverability cohort](./docs/recipes/03-tool-discoverability-cohort.md) | `MCP.Get Tool Discoverability` Pass@k across N trials × M tasks |
| 4 | [Skill-author stacked validation](./docs/recipes/04-skill-author-stacked-validation.md) | Tier-1 frontmatter check → Tier-2 activation → Tier-3 Pass@k, stacked |
| 5 | [Replacing custom Python tests](./docs/recipes/05-dogfood-replacing-custom-tests.md) | Port a custom pytest corpus to `.robot` suites |
| 6 | [Custom protocol adapter](./docs/recipes/06-custom-protocol-adapter.md) | Implement `CodingAgentAdapter` for a non-canonical agent |
| 7 | [First MCP server test (Tier-1)](./docs/recipes/07-first-mcp-server-test-tier-1.md) | Static-inspection-only MCP config validation |
| 8 | [CI integration](./docs/recipes/08-ci-integration.md) | Wiring agenteval suites into a CI pipeline |

Per-recipe details + cross-references live at [`docs/recipes/README.md`](./docs/recipes/README.md).

## Documentation

- **Keyword reference (GitHub Pages)** — [manykarim.github.io/robotframework-agenteval](https://manykarim.github.io/robotframework-agenteval/) — hosted libdoc HTML for all 6 libraries: [AgentEval](https://manykarim.github.io/robotframework-agenteval/keywords/AgentEval.html) · [SkillsLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/SkillsLibrary.html) · [MCPLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/MCPLibrary.html) · [JudgeLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/JudgeLibrary.html) · [SubagentsLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/SubagentsLibrary.html) · [HooksLibrary](https://manykarim.github.io/robotframework-agenteval/keywords/HooksLibrary.html). Local copies under [`docs/keywords/`](./docs/keywords/) — regenerated via `python -m robot.libdoc`.
- **Running against a real model** — [`docs/running-against-a-real-model.md`](./docs/running-against-a-real-model.md) — provider selection, model strings, and API keys
- **Architecture decisions** — [`docs/adr/`](./docs/adr/) — the architecture decision records covering adapter protocols, tier rules, MCP observation, coverage semantics, the error hierarchy, and more
- **Contracts** — [`docs/contracts/`](./docs/contracts/) — stable surfaces consumers can rely on
- **Recipes** — [`docs/recipes/`](./docs/recipes/) — worked examples, plus the [judge-calibration cookbook](./docs/recipes/judge-calibration.md)
- **Exit criteria for 1.0** — [`docs/contracts/exit-criteria-0x-to-1x.md`](./docs/contracts/exit-criteria-0x-to-1x.md) — the ratified promotion criteria
- **Troubleshooting** — [`docs/troubleshooting/`](./docs/troubleshooting/) — first-day issues and workarounds

## Known limitations

- **macOS validation deferred.** Phase 1 + Phase 2 validate on Linux only. Community macOS reproductions welcome.
- **Exact version pins.** `mcp==1.27.1` + `robotframework==7.4.2` + `robotframework-pabot==5.2.2` + `anyio==4.13.0` are spike-validated. An adapter-version-drift warning will detect future MCP SDK refactors that break the `request_handlers` wrap pattern.
- **Breaking keyword renames (pre-1.0).** The `compose-single-library-import` change renamed every artifact/engine keyword to its namespace-prefixed form (`Skill.*`, `Subagent.Get Frontmatter`, `Hook.Get Config`, `MCP.*`) and composed all sub-libraries into the single `Library    AgentEval` import. There are no deprecation aliases for the old bare names — acceptable because the package is unreleased on PyPI.
- **No PyPI release yet.** Phase 1 is foundational. Public release + semver stability are gated on the exit criteria at [`exit-criteria-0x-to-1x.md`](./docs/contracts/exit-criteria-0x-to-1x.md).
- **Phase-2 SDK adapters at `experimental`.** `ClaudeAgentSDKAdapter` + `OpenAIAgentsSDKAdapter` carry pre-1.0 SDK pins (`claude-agent-sdk>=0.1.0,<1.0`, `openai-agents>=0.1.0,<1.0`); their shape may shift.
- **Terminal run summary pass/fail counts not populated yet.** The listener does not snapshot per-test pass/fail state yet; the display shows a `"—"` sentinel until that lands.

## Project posture

**Solo + AI-agent-assisted** development using the [BMad method](https://github.com/bmad-sim/bmad-method). See [MAINTAINERS.md](./MAINTAINERS.md) for the maintenance model.

The project uses **cross-LLM adversarial review** as a load-bearing quality control — every Tier-2/Tier-3 keyword change is reviewed by more than one LLM family. See [MAINTAINERS.md](./MAINTAINERS.md#review-methodology) for the review methodology governing the project's quality bar.

## License

[Apache 2.0](./LICENSE).
