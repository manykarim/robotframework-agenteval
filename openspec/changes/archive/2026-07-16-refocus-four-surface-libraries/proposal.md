## Why

`robotframework-agenteval` grew into ~37k LOC across 22 modules and 104 keywords while chasing a broad "evaluate AI coding agents" mission. The result is heavy where it is least differentiated (vendor-adapter glue, enterprise telemetry/reporting, a cost-meter that is a provably-dead `0.0` stub) and thin where the market is wide open. The project's own landscape survey (`docs/ai-testing-tools-landscape.md`) names **Hooks and SubAgents** as white space with *no established testing framework* — and those are two of the smallest, cleanest modules already in the tree.

This change refocuses the library on the four artifacts of the agentic stack that a test engineer actually ships and needs to guard — **MCP servers, Agent Skills, SubAgents, and Hooks** — each testable three ways: **deterministically, with an LLM judge, or by driving a real coding agent**. No backwards compatibility is retained; this is a from-scratch focus-down that keeps the sound cores and deletes the ballast.

## What Changes

- **BREAKING** — Replace the single flat `AgentEval` mega-library (14 composed sub-libraries, one 104-keyword namespace) with **four independently importable Robot Framework libraries**: `MCPLibrary`, `SkillsLibrary`, `SubagentsLibrary`, `HooksLibrary`. Each is imported à la carte (`Library    HooksLibrary`) and pulls only the dependencies its modes need.
- **New shared spine** (`AgentEval._core`, internal — not a Library): a small ~2k-LOC layer providing the adapter seam (`run(prompt) -> AgentRunResult` + one LiteLLM adapter), the LLM judge (rubric → prompt → score), stats (run-N / pass@k / Wilson CI), the trace/evidence projection (spans + tool-calls), the `@tier(1|2|3)` marker, a slim error hierarchy, and shared types.
- **Dependency extras** so the base install is deterministic and tiny: `[mcp]` (live MCP SDK), `[llm]` (litellm for judge + agent modes), `[all]`. `Library HooksLibrary` requires nothing beyond stdlib + PyYAML.
- **BREAKING — Remove outright**: `baseline`, `redteam`, `conversation`, `conformance` (permanent stub), `_heatmap`, `scenarios`, judge calibration, the stats A/B trio (Mann-Whitney / Cliff's delta / bootstrap), and the discoverability cross-adapter comparison. Doors left open as future optional extras where noted.
- **BREAKING — Rebuild thin**: `coding_agent` (6 vendor CLI adapters → 1 generic LiteLLM adapter), `_kernel` (keep `@tier` + async bridge + slim trace/MCP-lifecycle; delete the dead cost-meter, host-budget plumbing, version-drift, and `inspect.stack()` ACL), `telemetry` (keep span + tool-call emission; delete OTLP/JSONL/JUnit/EvidenceBlock reporting).
- **Simplify the four surface cores**: collapse duplicated activation/substring heuristics, merge near-duplicate tier keywords, and strip per-keyword FR/AC/ADR/Story provenance docstrings (the "archaeology") down to terse, useful libdoc.
- **Honest mode matrix**: Hooks are deterministic programs → Tier-1 only. Do not force LLM/agent modes onto surfaces where they do not apply.
- **Identity + voice reframe**: keep the `robotframework-agenteval` PyPI name; reframe the tagline and mission from "evaluate AI coding agents" to "test the agentic stack." Rewrite all readable content (README, recipes, keyword docstrings, error messages) in the Robot Framework voice — friendly, direct, dry, no fluff. Add the missing SubAgents recipe.

## Capabilities

This change re-cuts the existing 26-capability spec baseline (which reflects the old
sprawling architecture) into **five consolidated capabilities** and removes the rest.
The four surface capabilities are declared new because their shape changes fundamentally
(independent libraries, honest mode matrix, dropped A/B apparatus) and each consolidates
several old granular specs; the superseded specs are listed under Removed.

### New Capabilities
- `mcp-testing`: Test MCP servers — deterministic tool-schema validation, server lifecycle + tool-call assertions, coverage metrics, and agent/LLM-mode tool-discoverability scoring. (`MCPLibrary`; consolidates + supersedes `mcp-tool-invocation`.)
- `skills-testing`: Test Agent Skills — deterministic frontmatter parse/validation, LLM-judge and agent-mode activation checks with pass@k, and discoverability. (`SkillsLibrary`; the old `skill-ab-benchmark` A/B path is dropped, the activation/discoverability core is kept and reshaped.)
- `subagent-testing`: Test SubAgents — deterministic config-drift checks (declared skills/tools) and delegation extraction, plus agent-mode routing-accuracy with pass@k. (`SubagentsLibrary`; consolidates + supersedes `subagent-config-validation` + `subagent-delegation-assertions`.)
- `hook-testing`: Test Hooks — deterministic config parse, synthetic hook-event firing through a shared matcher engine, and decision/exit-code/output assertions (Tier-1 only). (`HooksLibrary`; consolidates + supersedes `hook-config-parsing` + `hook-config-simulation` + `hook-execution`.)
- `evaluation-core`: The shared internal spine every surface rides — the `@tier(1|2|3)` deterministic/LLM/agent model, the coding-agent adapter seam + single LiteLLM adapter, the LLM judge, the stats runner (run-N / pass@k / Wilson CI), the trace/evidence projection, the slim error hierarchy, shared types, the four-library packaging + dependency extras, and the identity/voice reframe. (Consolidates + supersedes `config-resolution`, `error-hierarchy`, `judge-criteria-shortcuts`, `keyword-namespacing`, `single-library-import`, `init-scaffold`, `documentation-accuracy`, `onboarding-documentation`.)

### Modified Capabilities
<!-- None retained in place. Every touched capability is either consolidated into one of
     the five new capabilities above (see supersession notes) or removed below. -->

### Removed Capabilities (BREAKING)
- **Dropped features** — `regression-baseline-tracking`, `red-team-probes`, `opencode-cli-adapter`, `budget-assertions`, `fanout-guardrails` (dead `0.0` cost meter), and the entire conversation stack: `conversation-judging`, `conversation-lifecycle`, `conversation-metrics`, `simulated-user`, `multi-turn-scenario-yaml`.
- **Superseded/consolidated** into the five new capabilities (see notes above): `mcp-tool-invocation`, `hook-config-parsing`, `hook-config-simulation`, `hook-execution`, `subagent-config-validation`, `subagent-delegation-assertions`, `skill-ab-benchmark`, `config-resolution`, `error-hierarchy`, `judge-criteria-shortcuts`, `keyword-namespacing`, `single-library-import`, `init-scaffold`, `documentation-accuracy`, `onboarding-documentation`.
- `package-pruning` was a prior one-off pruning effort — no longer a standing capability.

## Impact

- **Package shape**: `src/AgentEval/` reorganized into `AgentEval/_core/` + four `*Library/` packages. Estimated ~37k → ~9k LOC (~75% reduction). Optional thin `Library AgentEval` convenience composite retained (documented default is the four separate libraries).
- **Dependencies**: `mcp` and `litellm` move behind extras; base install drops to RF + robotlibcore + PyYAML. `scipy`/`numpy` removed with the A/B stats trio.
- **Public API**: every current keyword either moves under one of the four libraries, moves into `_core`, or is removed. No back-compat shims.
- **Tests**: ~11k LOC of unit tests coupled to dropped modules (`coding_agent` ~4.4k, `judge` calibration, `redteam`, `conversation`, `baseline`, `scenarios`) are removed or rewritten; the suite is already partitioned per-module so excision is clean.
- **Docs**: keep most `contracts/` and the MCP + infra ADRs; drop coding-agent-adapter and peripheral ADRs/recipes; rewrite surviving docs in the RF voice; add a SubAgents recipe.
- **Process artifacts** (`_bmad-output/` ~96 MB) are orthogonal and untouched.
