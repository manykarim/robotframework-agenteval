# Recipe Gallery

Worked examples covering the agenteval keyword surface, spanning skill
authoring (validating skill `.md` files and measuring activation reliability),
agent integration (building MCP servers, shipping custom adapters, porting
downstream test corpora), and CI wiring (release gates, smoke checks,
conformance suites).

## Index

| # | Recipe | What it shows |
|---|---|---|
| 1 | [First eval in 5 minutes](./01-first-eval-in-five-minutes.md) | Minimal `Send Prompt` + tool-call assertion — the `agenteval init` walkthrough |
| 2 | [Pass@k over polling](./02-pass-at-k-over-polling.md) | `Stat.Pass At K` as the polling replacement (polling is prohibited) |
| 3 | [Tool discoverability cohort](./03-tool-discoverability-cohort.md) | `MCP.Get Tool Discoverability` Pass@k across N trials × M tasks |
| 4 | [Skill-author stacked validation](./04-skill-author-stacked-validation.md) | Tier-1 frontmatter check → Tier-2 activation → Tier-3 Pass@k stacked validation |
| 5 | [Dogfood — replacing custom Python tests](./05-dogfood-replacing-custom-tests.md) | Port a downstream library's pytest corpus to `.robot` suites — rf-mcp + agentskills worked examples |
| 6 | [Custom protocol adapter](./06-custom-protocol-adapter.md) | Implement `CodingAgentAdapter` for a non-canonical agent (Protocol vs SubprocessAdapter vs InProcessAdapter) |
| 7 | [First MCP server test (Tier-1)](./07-first-mcp-server-test-tier-1.md) | Static-inspection-only MCP config validation (`MCP.Get Server Config`) |
| 8 | [CI integration](./08-ci-integration.md) | `dogfood-integration.yml` + `parity-suite-smoke` patterns + release-pending label gating |
| 9 | [Testing Claude Code hooks](./09-testing-claude-code-hooks.md) | Fire synthetic hook events + assert block/allow decisions (`Hook.Fire Hook Event`, Tier-1, no API keys) |
| 10 | [Multi-turn conversations](./10-multi-turn-conversations.md) | Scripted `Send Message` sequences + `Simulate User` (persona/goal) over a `ConversationHandle` |
| 11 | [Red-team probes](./11-red-team-probes.md) | Defensive single-turn adversarial-robustness gate — `RedTeam.Run Probe` → attack-success-rate (lower is safer) |

## How to use

Each recipe:

1. Names the use case ("I want to ...")
2. Lists the keywords involved + their tier annotations
3. Shows the minimal `.robot` snippet

## Validation

Recipes are validated via:

- A per-recipe smoke-execute precheck — every fenced `robotframework` code block runs through `robot --dryrun` before the recipe is shipped
- **CI extraction harness (`tests/integration/recipes/test_all_recipes_dryrun.py`):** walks every `docs/recipes/*.md` file, extracts all fenced `robotframework` blocks, and runs `robot --dryrun` on each **dryrun-eligible** block (those containing `*** Test Cases ***`). Non-eligible blocks (settings-only + standalone-fragment) are SKIPPED with explicit reasons. Every eligible block passes; the `_KNOWN_BROKEN_BLOCKS` skip list is empty and stays as the mechanism for triaging any future breakage.

## Cross-references

- [Keyword reference (libdoc HTML)](../keywords/AgentEval.html) · [SkillsLibrary libdoc](../keywords/SkillsLibrary.html)
- [Stability surface contract](../contracts/stability-surface.md) — which keyword surfaces are `stable` / `provisional` / `experimental`
- [Conformance fixture format](../contracts/conformance-fixture-format.md) — the "fidelity oracle" mechanism ([why fidelity oracles](../adr/ADR-005-conformance-suite-fidelity-oracles.md))
- [Phase-1.5 carry-over catalog](../phase-1-5-carry-overs.md) — growing catalog of carry-over items (71 at Phase-1 close; see the file for the current count)
