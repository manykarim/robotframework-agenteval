# Troubleshooting

First-run issues and their fixes. Most trouble is one of two things: a missing
extra, or a keyword aimed at the wrong tier.

## Install and imports

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'HooksLibrary'` (or `MCPLibrary`, ...) | The package isn't installed in the active environment. | `pip install robotframework-agenteval` (or `uv add robotframework-agenteval`). |
| A keyword raises `MissingExtraError` naming `[llm]` | You called a Tier-2 (judge) or Tier-3 (agent) keyword without the LLM extra. | `pip install 'robotframework-agenteval[llm]'`. See [Running against a real model](../running-against-a-real-model.md). |
| A keyword raises `MissingExtraError` naming `[mcp]` | You called a live MCP keyword (`MCP.Start Server`, `MCP.Call Tool`, ...) without the MCP SDK. | `pip install 'robotframework-agenteval[mcp]'`. Tier-1 schema validation needs no extra. |

## Live models

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `GenericAdapter needs a model` | A Tier-2/Tier-3 keyword ran with no model set. | Pass `model=` on the keyword, or export `AGENTEVAL_MODEL`. See [Running against a real model](../running-against-a-real-model.md). |
| A LiteLLM authentication error | The provider API key isn't in the environment. | Export the provider key (e.g. `ANTHROPIC_API_KEY`), or put it in a `.env` file. Never commit real keys. |
| Real-model runs are slow or costly | Tier-3 fan-out multiplies the calls. | Keep stochastic runs on a schedule, not on every push; start with few trials. See [CI integration](../recipes/08-ci-integration.md). |

## Tiers and results

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| A pass@k result looks wrong | The default predicate doesn't match your keyword's result type. | Pass a custom `predicate=`, or use the surface's own pass@k keyword (e.g. `Skill.Get Activation Pass At K`). |
| `MCP.Call Tool` complains about arguments | You supplied both the dict form and inline `kwargs`. | Use one form or the other, not both. |
