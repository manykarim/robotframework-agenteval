# Changelog

All notable changes to **robotframework-agenteval** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.4.0] — 2026-07-27

In-process adapter overrides — drive real MCP servers on long scenarios and inject their own guidance.

### Added

- **In-process adapter usage-limit overrides.** `get_adapter("in-process", ...)`
  and `.run()` accept `request_limit` (a shortcut) and `usage_limits` (the full
  pydantic-ai `UsageLimits` escape hatch — token/tool-call caps) — keyword-only on
  both. Precedence, one rule: run-level overrides `__init__` as a whole, and within
  a level the full object beats the `request_limit` shortcut. This unblocks long
  agentic scenarios that need more than pydantic-ai's default of 50 requests.
- **In-process adapter instruction injection.** A new `instructions` argument
  (on `__init__` and `.run()`) is surfaced to the model as run-level instructions —
  e.g. an MCP server's own guidance — and **composes** with deferred skills (it does
  not clobber `load_capability`). The adapter never auto-reads a server's
  instructions; injection is caller-driven.
- **`MCP.Get Server Instructions`** — a Tier-1 reader for the server's advertised
  `instructions`, captured on connect into `MCPSession.instructions` (readable as
  `${session.instructions}`). Useful for config-drift checks and to feed the
  in-process adapter.

### Notes

- Purely additive and non-breaking — every new argument defaults to today's
  behavior (`usage_limits`/`request_limit` unset ⇒ the library default of 50;
  `instructions` unset ⇒ nothing injected).
- The in-process adapter remains a **proxy**: injecting `instructions` makes it a
  *steered* proxy, but `allowed-tools` / `disable-model-invocation` are still not
  enforced. Use the coding-agent CLI adapters when you need a specific vendor's real
  behavior.

---

## [0.3.0] — 2026-07-17

An in-process agent adapter — measure MCP tools, Skills, SubAgents, and Hooks with only an LLM key + base_url, no coding-agent CLI.

### Added

- **`in-process` adapter** (behind a new optional `[agent]` extra, pydantic-ai +
  pydantic-ai-harness): run a prompt through an in-process agent against any
  OpenAI-compatible endpoint (`AGENTEVAL_MODEL` + base_url + key) and measure all
  four surfaces — programmatically, no vendor CLI:
  - **MCP** — `MCP.As Agent Toolset` bridges a connected server; executed tool
    calls (with results) land in `AgentRunResult.tool_calls` and feed MetricsLibrary.
  - **Skills** — `Skill.As Capability` / `Skill.Load Capabilities From Dir` load a
    `SKILL.md` as a deferred capability; `Skill.Get Activated Skills` reports which
    skill the model actually activated (real activation, not a judge guess).
  - **SubAgents** — `Subagent.As Subagents Capability` loads Claude subagent `.md`;
    `Subagent.Get Routed Subagents` reports which named subagent the model delegated to.
  - **Hooks (partial)** — a PreToolUse-style tool-approval gate; `Hook.Get Tool
    Decisions` reports allow/deny per tool call.
- All four live-verified against MiniMax-M2.7.

### Notes

- The in-process adapter is a **proxy** for a competent generic agent, not a
  specific coding agent's runtime — never read its numbers as "how <a named
  agent> behaves." `allowed-tools` / `disable-model-invocation` are not enforced,
  and Hooks are in-process tool gates, not external command-script hooks. Use the
  coding-agent CLI adapters when you need a specific vendor's real behavior.

---

## [0.2.0] — 2026-07-17

Agent-run metrics + end-to-end coding-agent CLI adapters.

### Added

- **MetricsLibrary** (8 keywords) — read tokens, cost, and latency off a real
  agent run, get per-task **and per-tool** tool-call metrics (count, passed,
  failed, tokens, cost, latency), assert on token/cost budgets, and export a
  normalized run-metrics record (with an expected-tool contract + hit rate) to
  JSON. All numbers are ground truth from the recorded trace, never self-report.
- **StatLibrary** (3 keywords) — `Stat.Run N Times`, `Stat.Get Pass At K`,
  `Stat.Wilson Interval` for statistical rigor over stochastic runs.
- **Coding-agent CLI adapters** — run a prompt end-to-end through a real agent
  CLI and gather its tool calls + token/cost usage: `claude-code` and `gemini`
  (full metrics), `codex` and `opencode` (partial), and best-effort `kilo` +
  `copilot` (degraded, with honest VALIDATION-CEILING markers that never
  fabricate numbers). One `SubprocessCLIAdapter` seam, version-drift detection.
- Per-tool token/cost attribution on `ToolCallTrace`; a `metric_source`
  (native/derived) honesty field; a keyword-example gate ensuring every
  documented example runs; a README setup section for live LLM + CLI-agent runs.

### Fixed

- `GenericAdapter` now captures the model's requested tool calls and cached
  input tokens (previously it recorded zero tool calls), so real-model runs
  produce real metrics.

---

## [0.1.0] — 2026-07-17

First published release — a from-scratch refocus into four independently
importable Robot Framework libraries for testing the agentic stack.

### Added

- **Four surface libraries**, each imported à la carte:
  - `HooksLibrary` (8 keywords, Tier-1) — parse Claude Code hook configs, fire
    synthetic hook events through a shared matcher engine, and assert on
    decisions, exit codes, and output fields.
  - `MCPLibrary` (17 keywords) — validate tool schemas (no live server needed),
    drive a live MCP server over stdio or in-memory with a warm session reused
    across calls, assert tool-call coverage, and score tool discoverability.
  - `SkillsLibrary` (10 keywords) — parse and validate Agent Skill frontmatter,
    check activation deterministically / with an LLM judge / in agent mode with
    pass@k, and score discoverability.
  - `SubagentsLibrary` (9 keywords) — check subagent config drift and delegation
    routing (deterministic checks plus agent-mode accuracy with pass@k).
- Optional `Library AgentEval` composite exposing all four surfaces under one import.
- The `@tier(1|2|3)` model — test each surface **deterministically**, with an
  **LLM judge**, or by driving a **real coding agent**.
- Shared spine `AgentEval._core` — a coding-agent adapter seam with one LiteLLM
  adapter, an LLM judge, stats (run-N / pass@k / Wilson CI), a trace/tool-call
  projection, and a slim error hierarchy.
- Dependency extras: a deterministic base install (`robotframework`,
  `robotlibcore`, `pyyaml`, `jsonschema`) plus `[mcp]` (live MCP SDK), `[llm]`
  (LiteLLM for judge + agent modes), and `[all]`.
- Recipes and generated keyword documentation for all four surfaces, in the
  Robot Framework voice.

### Changed

- Mission reframed from "evaluate AI coding agents" to "test the agentic stack —
  MCP servers, Skills, SubAgents, and Hooks."
- All readable content rewritten in the Robot Framework voice.

### Removed

- **BREAKING (pre-1.0, never published to PyPI):** the previous flat `AgentEval`
  mega-library and its 104-keyword single namespace, all vendor CLI adapters,
  enterprise telemetry / OTLP / JUnit reporting, judge calibration, cross-adapter
  A/B statistics, red-team probes, multi-turn conversation modeling, and
  regression baseline tracking. Source shrank ~82% (37k → 6.5k LOC).

### Fixed

- `SkillsLibrary` accepts real published skills that declare only `name` +
  `description` — `allowed-tools` and `disable-model-invocation` are optional per
  the Agent Skills spec.
- `SubagentsLibrary` accepts the canonical Claude Code `tools: A, B, C`
  comma-separated string form.
- `InvalidConfigError` messages now carry the offending file path and a fix
  suggestion.
- `Hook.Command Should Exist` resolves the target script (not just the
  interpreter) and expands `${CLAUDE_PLUGIN_ROOT}`; hook event names are
  validated against the known Claude Code set.

---

## [0.0.1] — 2026-05-17

### Added

- Initial repository scaffolding:
  - `pyproject.toml` with src-layout (`src/AgentEval/`) + hatchling build backend.
  - `[project.scripts] agenteval = "AgentEval.cli:main"`.
  - `src/AgentEval/` skeleton, test directories, docs directories, and
    config/doc boilerplate.

### Known limitations

- Empty package — no public API yet. `import AgentEval` succeeds but exposes only
  `__version__`. The four surface libraries land in 0.1.0.
