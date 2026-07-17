# Changelog

All notable changes to **robotframework-agenteval** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
