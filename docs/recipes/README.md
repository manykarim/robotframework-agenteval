# Recipe gallery

Worked examples, one per surface plus CI wiring. Every recipe names a real use
case, lists the keywords and their tier, and shows a runnable `.robot` snippet.

New here? Start with the first one — it runs in five minutes with no API keys.

## The recipes

| # | Recipe | Surface | Tier |
|---|--------|---------|------|
| 1 | [First eval in five minutes](./01-first-eval-in-five-minutes.md) | Skills | 1 |
| 2 | [First MCP server test](./07-first-mcp-server-test-tier-1.md) | MCP | 1 |
| 3 | [Stacked skill validation](./04-skill-author-stacked-validation.md) | Skills | 1 → 2 → 3 |
| 4 | [Testing Claude Code hooks](./09-testing-claude-code-hooks.md) | Hooks | 1 |
| 5 | [SubAgent config drift and routing](./10-subagent-config-drift-and-routing.md) | SubAgents | 1 + 3 |
| 6 | [CI integration](./08-ci-integration.md) | all four | 1 + 2/3 |
| 7 | [End-to-end agent metrics through a CLI adapter](./11-e2e-agent-metrics-cli-adapters.md) | Metrics + CLI adapters | 3 → 1 |

## The tiers, in one line each

- **Tier 1** — deterministic. Parse files, project traces, assert. No model, no
  keys. Runs on the base install.
- **Tier 2** — LLM judge. Ask a model whether the output really did the thing.
  Needs the `[llm]` extra.
- **Tier 3** — coding agent. Drive a real agent and read back what it did. Needs
  the `[llm]` extra.

Hooks are deterministic programs, so the hooks recipe is **Tier 1 only** — no
judge, no agent, no keys.

## Cross-references

- [Docs home](../index.md) — the four libraries and the install matrix.
- Keyword reference:
  [`MCPLibrary`](../keywords/MCPLibrary.html) ·
  [`SkillsLibrary`](../keywords/SkillsLibrary.html) ·
  [`SubagentsLibrary`](../keywords/SubagentsLibrary.html) ·
  [`HooksLibrary`](../keywords/HooksLibrary.html).
- [Stability surface contract](../contracts/stability-surface.md) — which
  surfaces are `stable` / `provisional` / `experimental`.
