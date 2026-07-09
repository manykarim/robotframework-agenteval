# Proposal: compose-single-library-import

## Why

`Library AgentEval` should give you everything, but today 3 of the shipped sub-libraries
(SkillsLibrary, SubagentsLibrary, MCPLibrary) are excluded from the top-level DynamicCore
composition and require the expert-only
`Library AgentEval.<pkg>.library.<Cls> WITH NAME <X>` incantation. All 4 independent
fresh-user CLI trials (codex / claude / kilo / opencode — findings dossier E4) burned at
least one iteration on this import sprawl. The root cause is a single keyword-name
collision: `Get Frontmatter` is declared by both `SkillsLibrary` and `SubagentsLibrary`
(DF-7.1-S1 / carry-over C55), which forced the Story 2.2 carve-out that excluded the
colliding libraries (and, by norm-inheritance, MCPLibrary) from `_SUB_LIBRARIES` in
`src/AgentEval/__init__.py`. A secondary confusion compounds it: some keywords bake a
namespace prefix into their `@keyword(name=...)` (`Stat.Run N Times`, `Judge.Get Score`,
`MCP.Compare Tool Discoverability`, `Skill.Compare Discoverability`) while siblings in
the *same* library have none (`Call Tool`, `Get Frontmatter`), so no single naming rule
is learnable, and standalone `WITH NAME` imports produce the double-prefix trap
(`Skill.Skill.Compare Discoverability`).

The project is pre-1.0 and unreleased on PyPI, so breaking keyword renames are allowed
now at near-zero user cost — this is the last cheap window to fix the naming surface.

## What Changes

- **BREAKING** — Resolve the `Get Frontmatter` collision by renaming the colliding
  keywords (exact form — `Skill.Get Frontmatter` / `Subagent.Get Frontmatter`
  namespace-prefixed vs `Get Skill Frontmatter` / `Get Subagent Frontmatter` — is
  decided in design.md).
- **BREAKING** — Define ONE learnable namespace-prefix rule and apply it uniformly, so a
  library never mixes prefixed and unprefixed keyword names (today SkillsLibrary and
  MCPLibrary both mix). All renames respect the ratified libdoc constraint that the
  post-dot portion of a prefixed name MUST be multi-word
  (`feedback_libdoc_namespace_keyword_must_be_multiword`).
- Compose SkillsLibrary, SubagentsLibrary, and MCPLibrary into the top-level `AgentEval`
  library via `_SUB_LIBRARIES` (HooksLibrary is already composed), forwarding
  `max_cost_usd` / `max_runtime_seconds` to the `_HostBudgetPlumbing` subclasses
  (SkillsLibrary, MCPLibrary) the same way StatsLibrary / JudgeLibrary already receive
  them. This also closes the C55 budget-enforcement gap: `Skill.Get Activation Decision`'s
  `@guarded_fanout` finally receives budgets under `Library AgentEval`.
- Keep the existing import-time collision detector in `_build_components()` as the guard
  against future regressions (it now runs over the full composition).
- Keep standalone direct imports working (`Library AgentEval.skills.library.SkillsLibrary
  max_cost_usd=2.0` — some operators pass budgets there); document that `WITH NAME` is no
  longer needed and warn about the double-prefix trap when it is used anyway.
- Update all user-facing surfaces to the single-import story: README import examples +
  keyword tables, `docs/recipes/*`, `agenteval init` scaffold templates
  (`src/AgentEval/_init/templates/*.robot`), regenerated libdoc under `docs/keywords/`,
  and `docs/contracts/stability-surface.md`.

NOT in scope: content/doc-drift fixes beyond the import/rename mechanics (owned by the
`fix-first-run-experience` change); any new keywords or behavior changes to existing
keyword bodies.

## Capabilities

### New Capabilities

- `keyword-namespacing`: One uniform, learnable rule for which AgentEval keywords carry a
  baked-in namespace prefix in `@keyword(name=...)`, applied across every sub-library;
  includes the collision-resolving renames and the multi-word-after-dot libdoc constraint.
- `single-library-import`: `Library AgentEval` exposes every public keyword of every
  shipped sub-library with no name collisions, with budget/config forwarding to composed
  components, while standalone per-sub-library imports (with constructor kwargs such as
  `max_cost_usd`) keep working.

### Modified Capabilities

<!-- none — the only existing spec is opencode-cli-adapter, whose requirements are
     unaffected by keyword naming or composition. -->

## Impact

- **Code**: `src/AgentEval/__init__.py` (`_SUB_LIBRARIES` registry + carve-out comments +
  budget forwarding), `src/AgentEval/skills/library.py`,
  `src/AgentEval/subagents/library.py`, `src/AgentEval/mcp/library.py`,
  `src/AgentEval/hooks/library.py` (`@keyword(name=...)` values + module docstrings that
  document the `WITH NAME` pattern).
- **Tests**: every `.robot` and pytest file that invokes a renamed keyword or relies on
  the exclusion (unit conventions tests, tier-ACL tests, dogfood suites under
  `tests/dogfood/`, integration suites). The composition collision detector gets
  regression coverage for the newly included libraries.
- **Docs**: README (import blocks at L46/L116/L161/L176/L195 + keyword tables),
  `docs/recipes/*.md`, `docs/contracts/stability-surface.md`,
  `docs/phase-1-5-carry-overs.md` C55 closure evidence, regenerated
  `docs/keywords/*.html` libdoc.
- **Scaffold**: `src/AgentEval/_init/templates/example_mcp_runtime.robot` +
  `example_skill_validation.robot` (currently teach the `WITH NAME` pattern / call
  keywords the top-level import cannot see).
- **Compatibility**: breaking RF keyword renames — acceptable because the package is
  pre-1.0 and unreleased on PyPI; no downstream users exist. Announced in CHANGELOG-level
  notes within the same change.
