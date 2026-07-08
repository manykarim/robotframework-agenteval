# agenteval starter project

Scaffolded by `agenteval init`. Everything here runs with no API keys — the
examples use the mock provider and a bundled echo MCP server.

## Running the example tests

```bash
robot --listener AgentEval.telemetry.listener.Listener --xunit junit.xml tests/
```

The `--listener AgentEval.telemetry.listener.Listener` flag turns on agenteval's
tracing and JUnit XML enrichment. Without it the tests still pass, but:

- Per-test trace IDs do not surface in `output.xml`.
- The `--xunit junit.xml` file is not enriched with `agenteval.*` properties
  (cost, tokens, latency, coverage, completeness, trace id, adapter, model).
- The JSONL trace backend does not write per-test trace files.

Use the full `Module.Class` path (`AgentEval.telemetry.listener.Listener`). The
shorter `AgentEval.telemetry.listener` form is accepted by Robot Framework but
does not fire the listener hooks.

## What's in this project

| Path | Purpose |
| --- | --- |
| `tests/example_skill_validation.robot` | Validate a skill file's frontmatter (static check). |
| `tests/example_mcp_runtime.robot` | Call a tool on the bundled echo MCP server. |
| `tests/example_agent_run.robot` | `Send Prompt` against the mock provider. |
| `tests/fixtures/example-skill.md` | Sample skill with valid frontmatter. |
| `tests/fixtures/.mcp.json` | Sample MCP config pointing at the bundled echo server. |
| `tests/fixtures/scenario.yaml` | Sample scenario for `Load Scenario` / `Run Scenario`. |
| `agenteval.yaml` | Config defaults (model, budgets, trace backend). |

## Next steps

- **Run against a real model:** the examples use the mock provider. To switch to
  a live model, see the
  [Running against a real model](https://github.com/manykarim/robotframework-agenteval/blob/main/docs/running-against-a-real-model.md)
  guide.
- **Recipes:** the
  [recipe gallery](https://github.com/manykarim/robotframework-agenteval/tree/main/docs/recipes)
  covers Pass@k, tool discoverability, skill-author validation, CI integration,
  and more.
- **Custom adapters:** run `agenteval new-adapter <name>` to scaffold a custom
  coding-agent adapter package.

## Documentation

Full library docs: <https://github.com/manykarim/robotframework-agenteval>.
