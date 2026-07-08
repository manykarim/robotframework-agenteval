# single-library-import Specification

## Purpose
TBD - created by archiving change compose-single-library-import. Update Purpose after archive.
## Requirements
### Requirement: Library AgentEval exposes every public keyword
The top-level `AgentEval` RF library SHALL compose all shipped sub-libraries
(HooksLibrary, OrchestrationLibrary, TelemetryLibrary, MetricsLibrary,
AssertionsLibrary, StatsLibrary, HeatmapLibrary, JudgeLibrary, SkillsLibrary,
SubagentsLibrary, MCPLibrary) via the `_SUB_LIBRARIES` DynamicCore registry, so that a
suite containing only `Library    AgentEval` can call every public keyword. The Story
2.2 carve-out excluding SkillsLibrary, SubagentsLibrary, and MCPLibrary SHALL be
removed.

#### Scenario: Single import reaches all sub-library keywords
- **WHEN** an RF suite declares only `Library    AgentEval` and calls one keyword from
  each of the 11 sub-libraries (e.g. `Skill.Get Frontmatter`,
  `Subagent.Get Frontmatter`, `Hook.Get Config`, `MCP.Get Server Config`,
  `Stat.Get Pass At K`, `Judge.Get Score`, `Send Prompt`, `Get Spans`,
  `Get Tool Call Count`, `Trajectory Should Match`, `Get Cohort Heatmap`)
- **THEN** every keyword resolves and executes without a "No keyword found" error

#### Scenario: Composed keyword count matches the sum of the parts
- **WHEN** the composed library's DynamicCore keyword registry is compared against the
  union of all sub-libraries' `@keyword`-decorated methods plus the top-level keywords
- **THEN** the sets are equal — no keyword is shadowed or dropped by composition

### Requirement: Composition has no name collisions and keeps the loud collision guard
The composed keyword namespace SHALL contain no duplicate RF keyword names, and
`_build_components()` SHALL retain its import-time collision detector that raises
`RuntimeError` naming both owning classes if two components ever declare the same
keyword name.

#### Scenario: Full composition passes the collision detector
- **WHEN** `AgentEval()` is instantiated with the full 11-component registry
- **THEN** construction succeeds and no `RuntimeError` is raised

#### Scenario: A future duplicate still fails loudly
- **WHEN** a test registers two stub components that both declare the same
  `robot_name` and builds the composition
- **THEN** a `RuntimeError` is raised identifying the colliding keyword name and both
  owning classes

### Requirement: Budget forwarding to composed budget-aware sub-libraries
`AgentEval._build_components()` SHALL forward the resolved `max_cost_usd` and
`max_runtime_seconds` settings to every component class that subclasses
`_HostBudgetPlumbing` (today: StatsLibrary, JudgeLibrary, SkillsLibrary, MCPLibrary),
so that `@guarded_fanout` keywords enforce budgets under the single import. This closes
carry-over C55 (DF-7.1-S1 budget-enforcement gap).

#### Scenario: Skill fan-out keyword enforces the library-level budget (C55 closure)
- **WHEN** a suite imports `Library    AgentEval    max_cost_usd=0.0` and invokes
  `Skill.Get Activation Decision` with a stubbed adapter reporting nonzero cost
- **THEN** the `@guarded_fanout` budget layer raises its cost-exceeded error instead of
  running unmetered

#### Scenario: MCP fan-out keyword receives budgets under composition
- **WHEN** a suite imports `Library    AgentEval    max_cost_usd=1.0    max_runtime_seconds=60`
  and the composed MCPLibrary component is inspected
- **THEN** its `_max_cost_usd` is 1.0 and `_max_runtime_seconds` is 60.0

#### Scenario: Future mixin adopters are forwarded automatically
- **WHEN** a component class in `_SUB_LIBRARIES` subclasses `_HostBudgetPlumbing`
- **THEN** it receives `max_cost_usd` + `max_runtime_seconds` at construction without
  requiring a new class-name branch in `_build_components()`

### Requirement: Standalone direct sub-library imports keep working
Each sub-library SHALL remain importable directly by module path with constructor
kwargs (e.g. `Library    AgentEval.skills.library.SkillsLibrary    max_cost_usd=2.0`),
without `WITH NAME`, and keyword call sites SHALL be textually identical under
standalone and composed imports (the baked prefixes make `WITH NAME` unnecessary).

#### Scenario: Standalone import with budget kwargs
- **WHEN** a suite imports
  `Library    AgentEval.skills.library.SkillsLibrary    max_cost_usd=2.0` and calls
  `Skill.Get Frontmatter    skills/example.md`
- **THEN** the keyword resolves and the library instance carries `_max_cost_usd == 2.0`

#### Scenario: Call sites are portable between import styles
- **WHEN** the same test body calling `MCP.Get Server Config` runs once under
  `Library    AgentEval` and once under
  `Library    AgentEval.mcp.library.MCPLibrary`
- **THEN** both runs resolve the keyword and produce identical results with no edits to
  the call site

### Requirement: Missing-sub-library tolerance and constructor-failure loudness are preserved
The composition SHALL continue to skip sub-libraries whose module import fails
(`ImportError` / `AttributeError` logged at DEBUG) so partial installs stay green, and
SHALL continue to propagate constructor exceptions from successfully imported
sub-libraries.

#### Scenario: Missing module is skipped silently
- **WHEN** a registry entry's module cannot be imported
- **THEN** `AgentEval()` still constructs, the component is absent, and a DEBUG log
  records the skip

#### Scenario: Constructor failure propagates
- **WHEN** an importable sub-library raises from its constructor during composition
- **THEN** `AgentEval()` raises rather than exposing a partial keyword namespace

### Requirement: User-facing surfaces teach the single-import pattern
User-facing surfaces SHALL present the single-import pattern as the default. README,
`docs/recipes/*`, the `agenteval init` scaffold templates, regenerated libdoc
under `docs/keywords/`, and `docs/contracts/stability-surface.md` SHALL present
`Library    AgentEval` as the canonical import and SHALL NOT present per-sub-library
module-path imports except in the documented standalone-budget-scoping context.

#### Scenario: Scaffold output runs against the single import
- **WHEN** the `agenteval init` templates' `*** Settings ***` blocks are inspected
- **THEN** they import only `Library    AgentEval` (plus non-AgentEval libraries), and
  every AgentEval keyword they call resolves under that import in a dryrun

#### Scenario: README quick-start uses one import line
- **WHEN** the README import examples are inspected
- **THEN** the former `WITH NAME` blocks for Judge/Skill/MCP are replaced by the single
  `Library    AgentEval` import, with standalone module-path import shown only in the
  budget-scoping subsection

