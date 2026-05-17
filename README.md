# robotframework-agenteval

Robot Framework library for evaluating AI coding agents (skills, subagents, hooks, MCP servers, tools).

## Status

**Pre-alpha — Phase 1 in active development.** No public API yet. Story 1a.1 (Project Bootstrap) ships an empty package; sub-libraries land in Epic 1b onward.

## Install

```bash
uv add robotframework-agenteval
```

Once published. Pre-release, clone the repo and run `uv sync`.

## Quick check

```bash
git clone https://github.com/manykarim/robotframework-agenteval.git
cd robotframework-agenteval
uv sync
uv run python -c "import AgentEval; print(AgentEval.__version__)"
```

Expected output: `0.0.1`.

To also exercise the lint + typecheck path (ships in `[dev]` extras):

```bash
uv sync --extra dev
uv run --extra dev ruff check src/
uv run --extra dev mypy src/AgentEval
```

Expected: ruff "All checks passed!"; mypy "Success: no issues found in 16 source files".

## What this library is for

When you write Robot Framework tests for AI coding agents — Claude Code, Copilot CLI, Codex, OpenAI Agents SDK, custom MCP-using agents — `robotframework-agenteval` gives you the keyword vocabulary + the trace observability + the conformance harness to evaluate them honestly:

- **Tool-call inspection** — see what tools the agent actually called, what MCP servers it touched, where coverage degraded.
- **Skill / subagent / hook validation** — Tier-1 static-inspection keywords for the Claude-style skill ecosystem; activation-decision tests for skill discoverability.
- **Cohort comparison** — same scenario, multiple models, statistical assertions (Wilson CI, pass@k, Mann-Whitney).
- **Hosted-MCP observation** — universal trace fallback via the `Server.request_handlers` wrap pattern (ratified by [ADR-004](./docs/adr/ADR-004-hosted-mcp-observation.md)). Agent-agnostic by design.
- **Honesty fields** — `mcp_coverage` with D1 trust-floor semantics ([ADR-016](./docs/adr/ADR-016-mcp-coverage-detection-default.md)) so partial-observation runs don't masquerade as full-coverage runs.

## Documentation

- [Architecture decisions](./docs/adr/) — start with [ADR-001](./docs/adr/ADR-001-architectural-influences-catalog.md) for the catalog of reviewed patterns (filled by Story 1a.3).
- [Contracts](./docs/contracts/) — stable surfaces consumers can rely on (filled by Story 1a.4).
- [Recipes](./docs/recipes/) — copy-paste solutions for common evaluation patterns (filled per Epic Recipe Gallery — Story 8b.3).
- [Coming from](./docs/coming-from/) — migration mappings from DeepEval, PromptFoo (filled later).
- [Troubleshooting](./docs/troubleshooting/) — first-day issues + workarounds.

## Known limitations

- **macOS validation: deferred to Phase-1.5.** Per D2.1 architect waiver from Story 0.2 review (2026-05-17), Phase 1 development validates on Linux only. macOS support is a planned Phase-1.5 deliverable; community macOS reproductions are welcome.
- **mcp / RF version pins are exact.** `mcp==1.27.1` + `robotframework==7.4.2` + `robotframework-pabot==5.2.2` + `anyio==4.13.0` are the Story 0.1+0.2 spike-validated versions. `AdapterVersionDriftWarning` (Epic 5 Story 5.2 deliverable per ADR-004) will detect future mcp SDK refactors that break the `request_handlers` dict-wrap pattern.
- **No public API in 0.0.x.** Phase 1 is foundational scaffolding. The public surface stabilizes when sub-libraries land (Epic 2 onward) and reaches semver stability at the 1.0 release.

## Project posture

**Solo + AI-agent-assisted.** See [MAINTAINERS.md](./MAINTAINERS.md) for the maintenance model and the three ratified review-methodology norms.

## License

[Apache 2.0](./LICENSE).
