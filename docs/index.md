# robotframework-agenteval — documentation index

Robot Framework library for evaluating AI coding agents — skills, subagents, hooks, MCP servers, and tool calls.

This site hosts the project's keyword reference + architectural decision records + doc contracts + recipes. The canonical README + install + status lives in the [GitHub repository](https://github.com/manykarim/robotframework-agenteval#readme).

## Keyword reference (libdoc)

5 libraries · 49 keywords total. Regenerated per release via `python -m robot.libdoc`.

| Library | Keywords | Reference |
| --- | --- | --- |
| `AgentEval` (top-level — metrics + assertions + stats + orchestration + telemetry + heatmap) | 30 | [`AgentEval.html`](./keywords/AgentEval.html) |
| `AgentEval.skills.library.SkillsLibrary` — skill `.md` static + activation + discoverability | 8 | [`SkillsLibrary.html`](./keywords/SkillsLibrary.html) |
| `AgentEval.mcp.library.MCPLibrary` — MCP server lifecycle + tool inspection | 9 | [`MCPLibrary.html`](./keywords/MCPLibrary.html) |
| `AgentEval.subagents.library.SubagentsLibrary` — subagent `.md` static | 1 | [`SubagentsLibrary.html`](./keywords/SubagentsLibrary.html) |
| `AgentEval.hooks.library.HooksLibrary` — Claude Code `settings.json` hook config | 1 | [`HooksLibrary.html`](./keywords/HooksLibrary.html) |

## Architecture decisions

19 ratified ADRs (ADR-001 catalog + ADR-002 → ADR-019). See [`adr/`](./adr/) for the index.

## Doc contracts

12 stable doc contracts governing public surfaces. See [`contracts/`](./contracts/) for the index.

## Recipes

8 worked examples covering Devon (skill author) + Raj (library maintainer / agent developer) + Many (CI integrator). See [`recipes/`](./recipes/) for the index.

## Status + roadmap

- **Phase 1 closed** 2026-05-25 — `0.0.1` feature-complete for the Phase 1 surface
- **Phase 2 launched** — Epic 10 shipped native Agent SDK adapters for Anthropic + OpenAI
- **Pre-1.0** — see [`contracts/exit-criteria-0x-to-1x.md`](./contracts/exit-criteria-0x-to-1x.md) for the 6 ratified promotion criteria

## License

[Apache 2.0](https://github.com/manykarim/robotframework-agenteval/blob/main/LICENSE).
