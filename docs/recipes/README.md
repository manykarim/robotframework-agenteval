# Recipe Gallery

Eight worked examples covering the agenteval keyword surface — written for three personas:

- **Devon** (Skill Author) — writes skill `.md` files, validates their frontmatter + measures activation reliability.
- **Raj** (Library Maintainer / Agent Developer) — builds MCP servers, ships custom adapters, ports downstream test corpora.
- **Many** (Project Lead / CI Integrator) — wires agenteval into release gates, dogfood smoke checks, conformance suites.

## Index

| # | Recipe | Persona | What it shows |
|---|---|---|---|
| 1 | [First eval in 5 minutes](./01-first-eval-in-five-minutes.md) | All | Minimal `Send Prompt` + tool-call assertion — the `agenteval init` walkthrough |
| 2 | [Pass@k over polling](./02-pass-at-k-over-polling.md) | Devon | `Stat.Pass At K` as the polling replacement (ADR-019 prohibits polling per FR56) |
| 3 | [Tool discoverability cohort](./03-tool-discoverability-cohort.md) | Raj | `MCP.Get Tool Discoverability` Pass@k across N trials × M tasks |
| 4 | [Skill-author stacked validation](./04-skill-author-stacked-validation.md) | Devon | Tier-1 frontmatter check → Tier-2 activation → Tier-3 Pass@k stacked validation |
| 5 | [Dogfood — replacing custom Python tests](./05-dogfood-replacing-custom-tests.md) | Raj | Port a downstream library's pytest corpus to `.robot` suites — rf-mcp + agentskills worked examples |
| 6 | [Custom protocol adapter](./06-custom-protocol-adapter.md) | Raj | Implement `CodingAgentAdapter` for a non-canonical agent (Protocol vs SubprocessAdapter vs InProcessAdapter) |
| 7 | [First MCP server test (Tier-1)](./07-first-mcp-server-test-tier-1.md) | Raj | Static-inspection-only MCP config validation (`MCP.Get Server Config`) |
| 8 | [CI integration](./08-ci-integration.md) | Many | `dogfood-integration.yml` + `parity-suite-smoke` patterns + release-pending label gating |

## How to use

Each recipe:

1. Names the use case ("I want to ...")
2. Lists the keywords involved + their tier annotations
3. Shows the minimal `.robot` snippet
4. Documents the dogfood-finding (if any) that motivated it — recipes often crystallize patterns surfaced during interleaved dogfood ports (Story 3.3, 5.5, 6.4, 7.4)

## Validation

Recipes are validated via:

- The `docs-build.yml` per-file section-presence check (every recipe carries `## Use case` / `## Keywords used` / `## Walkthrough` headings)
- Per-recipe smoke-execute precheck per `feedback_executable_doc_precheck` (Epic 7 retro NEW norm) — every fenced `robotframework` code block runs through `robot --dryrun` before the recipe is shipped
- Phase-1.5 hygiene work-item: CI extraction harness for all 8 recipes (catalogued at C64 / `DF-8b.3-S1`). Phase-1 ships only Recipe #2 (Pass@k over polling) as a CI-extracted smoke test via `tests/integration/recipes/test_pass_at_k_recipe.py`.

## Cross-references

- [Keyword reference (libdoc HTML)](../keywords/AgentEval.html) · [SkillsLibrary libdoc](../keywords/SkillsLibrary.html)
- [Stability surface contract](../contracts/stability-surface.md) — which keyword surfaces are `stable` / `provisional` / `experimental`
- [Conformance fixture format](../contracts/conformance-fixture-format.md) — the "fidelity oracle" mechanism per ADR-005
- [Phase-1.5 carry-over catalog](../phase-1-5-carry-overs.md) — 71 entries at Phase-1 close
