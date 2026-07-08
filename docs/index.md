# robotframework-agenteval — documentation index

Robot Framework library for evaluating AI coding agents — skills, subagents, hooks, MCP servers, and tool calls.

This site hosts the project's keyword reference + architectural decision records + doc contracts + recipes. The canonical README + install + status lives in the [GitHub repository](https://github.com/manykarim/robotframework-agenteval#readme).

## Keyword reference (libdoc)

6 libraries · 56 keywords total. Regenerated per release via `python -m robot.libdoc`.

| Library | Keywords | Reference |
| --- | --- | --- |
| `AgentEval` (top-level — metrics + assertions + stats + orchestration + telemetry + heatmap + composed judge/hook keywords) | 35 | [`AgentEval.html`](./keywords/AgentEval.html) |
| `AgentEval.skills.library.SkillsLibrary` — skill `.md` static + activation + discoverability | 10 | [`SkillsLibrary.html`](./keywords/SkillsLibrary.html) |
| `AgentEval.mcp.library.MCPLibrary` — MCP server lifecycle + tool inspection | 10 | [`MCPLibrary.html`](./keywords/MCPLibrary.html) |
| `AgentEval.judge.library.JudgeLibrary` — LLM-judge scoring + rubric calibration (composed into `AgentEval`) | 2 | [`JudgeLibrary.html`](./keywords/JudgeLibrary.html) |
| `AgentEval.subagents.library.SubagentsLibrary` — subagent `.md` static | 1 | [`SubagentsLibrary.html`](./keywords/SubagentsLibrary.html) |
| `AgentEval.hooks.library.HooksLibrary` — hook `settings.json` config | 1 | [`HooksLibrary.html`](./keywords/HooksLibrary.html) |

The total counts unique keywords: `JudgeLibrary`'s 2 keywords and `HooksLibrary`'s 1 keyword are composed into (re-exported through) the top-level `AgentEval` library, so they are counted once (35 + 10 + 10 + 1 = 56).

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
