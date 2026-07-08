# Troubleshooting

First-run issues and their fixes, aggregated from the recipe gallery and the
scaffold. Each entry links back to the recipe it came from. Entries are grouped
by where the symptom shows up.

## Scaffold and setup

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `agenteval init` exits with "file already exists" warnings | The target directory already has some of the scaffolded files. | Re-run with `--force` to overwrite, or pick a fresh directory. See [Recipe #1](../recipes/01-first-eval-in-five-minutes.md). |
| Mock provider raises `AdapterDiscoveryError` | `agenteval` is not installed in the active environment. | `uv add robotframework-agenteval` or `pip install robotframework-agenteval`. See [Recipe #1](../recipes/01-first-eval-in-five-minutes.md). |
| A scaffold from an older version fails (its MCP example calls `echo` / `message=` / `${result.success}`) | The project was scaffolded before the current templates. | Re-run `agenteval init --force` in a fresh directory to regenerate, or update the example to call the `echo_back` tool with `text=` and assert on `${result.is_error}` / `${result.content}`. |

## Listener and reports

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `output.xml` has no `trace_id` tag | The module-path-only listener form was used. | Switch to the explicit class path `AgentEval.telemetry.listener.Listener`. See [Recipe #1](../recipes/01-first-eval-in-five-minutes.md). |
| `junit.xml` has no `agenteval.*` properties | The listener is not loaded, or no agent keywords fired (only built-in keywords like `Log`). | Verify the listener flag, and make sure at least one test calls an agent keyword (`Send Prompt`, `MCP.Call Tool`, ...). See [Recipe #1](../recipes/01-first-eval-in-five-minutes.md). |

## Statistical keywords and budgets

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Stat.Get Pass At K` returns `0.0` every time | The default predicate does not match your keyword's result type. | Pass a custom `predicate=` argument. See [Recipe #2](../recipes/02-pass-at-k-over-polling.md). |
| `PollingDisallowedError` fires | A `polling=` argument was passed to a Tier-2/3 keyword, or the `validate` operator was used without opt-in. | Wrap the stochastic call in `Stat.Run N Times` instead. See [Recipe #2](../recipes/02-pass-at-k-over-polling.md). |
| `CostExceededError` fires mid-run | The cohort exceeds `agenteval.yaml`'s `max_cost_usd`. | Lower the number of trials, or raise `max_cost_usd` via CLI argument or environment variable. See [Recipe #2](../recipes/02-pass-at-k-over-polling.md). |

## Running against a real model

For provider selection, model string format, and API keys, see
[Running against a real model](../running-against-a-real-model.md).
