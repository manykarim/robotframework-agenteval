# agenteval starter project

Scaffolded by `agenteval init` (Story 8b.1).

## Running the example tests

```bash
robot --listener AgentEval.telemetry.listener.Listener \
      --xunit junit.xml \
      tests/
```

**The `--listener AgentEval.telemetry.listener.Listener` flag is REQUIRED.**
Without it:

- Per-test trace IDs do not surface in `output.xml`.
- The `--xunit junit.xml` file is NOT enriched with `agenteval.*` properties
  (cost, tokens, latency, coverage, completeness, trace_id, adapter, model,
  tier, tier_breakdown).
- The JSONL trace backend does NOT write per-test trace files.

Use the **explicit `Module.Class`** path (`AgentEval.telemetry.listener.Listener`).
The shorter `AgentEval.telemetry.listener` (module-path-only) form is accepted
by RF without error but the listener's hooks do NOT fire on RF 7.x (empirical
finding from Story 8a.2 dev 2026-05-25).

## What's in this project

| Path | Purpose |
| --- | --- |
| `tests/example_skill_validation.robot` | Static skill-frontmatter inspection (Epic 2). |
| `tests/example_mcp_runtime.robot` | Bundled echo-MCP-server roundtrip (Epic 3). |
| `tests/example_agent_run.robot` | `Send Prompt` against the Mock provider (Epic 4). |
| `tests/fixtures/example-skill.md` | Sample skill with valid frontmatter. |
| `tests/fixtures/.mcp.json` | Sample MCP config pointing at the bundled echo server. |
| `tests/fixtures/scenario.yaml` | Sample scenario YAML for `Run Scenario` (Story 4.3). |
| `agenteval.yaml` | Config defaults (model, budgets, trace backend). |

## Next steps

- **Recipes:** [`docs/recipes/01-first-eval-in-five-minutes.md`](https://github.com/manykarim/robotframework-agenteval/blob/main/docs/recipes/01-first-eval-in-five-minutes.md) walks through this scaffolded project. Other recipes in the gallery cover Pass@k, Tool Discoverability, Skill Author validation, CI integration, etc.
- **Custom adapters:** Run `agenteval new-adapter --name my-adapter` (lands Story 8b.2) to scaffold a custom adapter package.
- **CI integration:** the `--xunit junit.xml` output is consumed by GitHub Actions test-reporter, Jenkins JUnit plugin, GitLab CI, and Allure — no extra configuration needed.

## Documentation

Full library docs at <https://github.com/manykarim/robotframework-agenteval>.
