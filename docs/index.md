# robotframework-agenteval — documentation index

Robot Framework library for evaluating AI coding agents — skills, subagents, hooks, MCP servers, and tool calls.

This site hosts the project's keyword reference + architectural decision records + doc contracts + recipes. The canonical README + install + status lives in the [GitHub repository](https://github.com/manykarim/robotframework-agenteval#readme).

## Keyword reference (libdoc)

11 libraries · 59 keywords total, all reachable through a single `Library    AgentEval` import. Regenerated per release via `python -m robot.libdoc`.

Since the `compose-single-library-import` change, every shipped sub-library is composed into the top-level `AgentEval` library via `_SUB_LIBRARIES`, so all 59 keywords are callable after one `Library    AgentEval` line — no `WITH NAME` needed. Each sub-library is still importable standalone (by module path) for per-library budget scoping; the baked namespace prefixes (`Skill.` / `Subagent.` / `Hook.` / `MCP.` / `Stat.` / `Judge.`) make the call sites identical under both import styles.

| Library | Keywords | Reference |
| --- | --- | --- |
| `AgentEval` (composed top-level — all 59 keywords) | 59 | [`AgentEval.html`](./keywords/AgentEval.html) |
| `AgentEval.skills.library.SkillsLibrary` — `Skill.*` skill `.md` static + activation + discoverability | 10 | [`SkillsLibrary.html`](./keywords/SkillsLibrary.html) |
| `AgentEval.mcp.library.MCPLibrary` — `MCP.*` server lifecycle + tool inspection | 10 | [`MCPLibrary.html`](./keywords/MCPLibrary.html) |
| `AgentEval.judge.library.JudgeLibrary` — `Judge.*` LLM-judge scoring + rubric calibration | 2 | [`JudgeLibrary.html`](./keywords/JudgeLibrary.html) |
| `AgentEval.subagents.library.SubagentsLibrary` — `Subagent.Get Frontmatter` static | 1 | [`SubagentsLibrary.html`](./keywords/SubagentsLibrary.html) |
| `AgentEval.hooks.library.HooksLibrary` — `Hook.Get Config` static | 1 | [`HooksLibrary.html`](./keywords/HooksLibrary.html) |

The 56-keyword total is the composed `AgentEval` surface; the per-sub-library rows show the same keywords available standalone (the counts overlap because the sub-libraries are composed into `AgentEval`, not additive to it).

## Architecture decisions

The architecture decision records cover adapter protocols, tier rules, MCP observation, coverage semantics, and the error hierarchy. See [`adr/`](./adr/) for the index.

## Doc contracts

Stable doc contracts governing public surfaces. See [`contracts/`](./contracts/) for the index.

## Recipes

Worked examples of the keyword surface. See [`recipes/`](./recipes/) for the index.

## Status + roadmap

- **Phase 1 closed** 2026-05-25 — `0.0.1` feature-complete for the Phase 1 surface
- **Phase 2 launched** — native Agent SDK adapters for Anthropic + OpenAI
- **Pre-1.0** — see [`contracts/exit-criteria-0x-to-1x.md`](./contracts/exit-criteria-0x-to-1x.md) for the ratified promotion criteria

## License

[Apache 2.0](https://github.com/manykarim/robotframework-agenteval/blob/main/LICENSE).
