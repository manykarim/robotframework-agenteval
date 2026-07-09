# keyword-namespacing

## ADDED Requirements

### Requirement: One learnable namespace-prefix rule for keyword names
The library SHALL apply a single naming rule across all sub-libraries: every keyword
belonging to an artifact/engine sub-library (skills, subagents, hooks, mcp, stats,
judge) SHALL bake its namespace prefix (`Skill.` / `Subagent.` / `Hook.` / `MCP.` /
`Stat.` / `Judge.`) into its `@keyword(name=...)` value, and every keyword belonging to
a core-loop sub-library (orchestration, telemetry, metrics, assertions, heatmap,
top-level config/tier keywords) SHALL carry no namespace prefix. No sub-library SHALL
mix prefixed and unprefixed keyword names.

#### Scenario: Artifact-library keywords are uniformly prefixed
- **WHEN** the `robot_name` values of all `@keyword`-decorated methods on
  SkillsLibrary, SubagentsLibrary, HooksLibrary, MCPLibrary, StatsLibrary, and
  JudgeLibrary are collected
- **THEN** every name starts with that library's namespace token followed by a dot
  (`Skill.`, `Subagent.`, `Hook.`, `MCP.`, `Stat.`, `Judge.` respectively)

#### Scenario: Core-loop keywords remain unprefixed
- **WHEN** the `robot_name` values of all `@keyword`-decorated methods on
  OrchestrationLibrary, TelemetryLibrary, MetricsLibrary, AssertionsLibrary,
  HeatmapLibrary, and the top-level `AgentEval` class are collected
- **THEN** no name contains a dot

#### Scenario: A conventions test enforces the rule mechanically
- **WHEN** a future keyword is added to a namespaced sub-library without the baked
  prefix (or with a foreign prefix)
- **THEN** a unit conventions test fails, naming the offending keyword and the expected
  prefix

### Requirement: Colliding Get Frontmatter keywords are renamed
The system SHALL rename `SkillsLibrary`'s `Get Frontmatter` to `Skill.Get Frontmatter`
and `SubagentsLibrary`'s `Get Frontmatter` to `Subagent.Get Frontmatter`, eliminating
the DF-7.1-S1 name collision. This is a breaking rename with no deprecation alias
(pre-1.0, unreleased on PyPI).

#### Scenario: Skill frontmatter keyword resolves under new name
- **WHEN** an RF suite importing `Library AgentEval` calls
  `Skill.Get Frontmatter    skills/example.md`
- **THEN** the skill file's YAML frontmatter is returned as a dict, identical in
  behavior to the pre-rename keyword

#### Scenario: Subagent frontmatter keyword resolves under new name
- **WHEN** an RF suite importing `Library AgentEval` calls
  `Subagent.Get Frontmatter    agents/example.md`
- **THEN** the subagent file's YAML frontmatter is returned as a dict, identical in
  behavior to the pre-rename keyword

#### Scenario: Old name no longer resolves
- **WHEN** an RF suite importing `Library AgentEval` calls the bare keyword
  `Get Frontmatter`
- **THEN** RF reports the keyword as not found

### Requirement: Remaining unprefixed artifact-library keywords are renamed
The system SHALL rename all remaining unprefixed keywords in the artifact
sub-libraries to their prefixed forms: the 8 SkillsLibrary keywords
(`Skill.Get Description`, `Skill.Get Allowed Tools`,
`Skill.Get Disable Model Invocation`, `Skill.Should Be Valid Frontmatter`,
`Skill.Get Activation Decision`, `Skill.Get Discoverability`,
`Skill.Should Activate For`, plus `Skill.Get Frontmatter` above), the HooksLibrary
keyword (`Hook.Get Config`), and the 9 MCPLibrary keywords (`MCP.Get Server Config`,
`MCP.Get Tool Schema`, `MCP.Validate Tool Schema`, `MCP.Start Server`,
`MCP.Connect To Server`, `MCP.Stop Server`, `MCP.List Tools`, `MCP.Call Tool`,
`MCP.Get Tool Discoverability`). Keyword behavior, arguments, tier annotations, and
return types SHALL be unchanged by the renames.

#### Scenario: MCP lifecycle keywords resolve under prefixed names
- **WHEN** an RF suite importing `Library AgentEval` runs
  `MCP.Start Server` → `MCP.Connect To Server` → `MCP.List Tools` → `MCP.Call Tool` →
  `MCP.Stop Server` against the bundled echo server
- **THEN** the full lifecycle succeeds with behavior identical to the pre-rename
  keywords

#### Scenario: Hook config keyword resolves under prefixed name
- **WHEN** an RF suite importing `Library AgentEval` calls
  `Hook.Get Config    .claude/settings.json` on a valid fixture
- **THEN** the parsed hook config is returned, identical in behavior to the pre-rename
  `Get Config`

#### Scenario: Tier annotations survive the rename
- **WHEN** `Get Keyword Tier` is called with a renamed keyword name (e.g.,
  `MCP.Call Tool`, `Skill.Get Activation Decision`)
- **THEN** it returns the same tier integer the keyword had before the rename

### Requirement: Prefixed names satisfy the libdoc multi-word constraint
Every baked-prefix keyword name SHALL have a multi-word portion after the dot, per the
ratified libdoc constraint (single-word post-dot portions are auto-split by
DynamicCore+libdoc rendering).

#### Scenario: Libdoc renders no auto-split names
- **WHEN** libdoc HTML is regenerated for the composed `AgentEval` library and each
  standalone sub-library
- **THEN** no rendered keyword name contains a dot followed by a space (the auto-split
  signature, e.g. `Judge. Calibrate`)

### Requirement: Documentation teaches the naming rule and the double-prefix trap
User-facing documentation SHALL state the one-sentence naming rule and the double-prefix
trap. Documentation (README, recipes, sub-library module docstrings, scaffold
templates) SHALL use only the new keyword
names, and SHALL NOT instruct users to import AgentEval sub-libraries `WITH NAME`.
Standalone-import documentation SHALL warn that adding `WITH NAME <Prefix>` produces
double-prefixed fully-qualified names (e.g. `Skill.Skill.Get Frontmatter`).

#### Scenario: No doc teaches WITH NAME for AgentEval sub-libraries
- **WHEN** README, `docs/recipes/*.md`, scaffold templates, and sub-library module
  docstrings are grepped for `WITH NAME` applied to an `AgentEval.*` library import
- **THEN** the only matches are the explicit double-prefix-trap warning passages

#### Scenario: No old keyword name survives in docs or code
- **WHEN** the repository (excluding git history, CHANGELOG-style notes, and
  carry-over catalog prose) is grepped for the 19 pre-rename keyword names as RF call
  sites
- **THEN** zero matches remain
