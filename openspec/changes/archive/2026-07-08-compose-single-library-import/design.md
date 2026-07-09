# Design: compose-single-library-import

## Context

`src/AgentEval/__init__.py` composes sub-libraries into the top-level `AgentEval` class
via `robotlibcore.DynamicCore` over the `_SUB_LIBRARIES` registry (currently 8 entries:
Hooks, Orchestration, Telemetry, Metrics, Assertions, Stats, Heatmap, Judge). Three
shipped sub-libraries are excluded by the Story 2.2 carve-out:

- `SkillsLibrary` — excluded because its `Get Frontmatter` collides with
  `SubagentsLibrary.Get Frontmatter` (DF-7.1-S1; carve-over C55).
- `SubagentsLibrary` — same collision.
- `MCPLibrary` — excluded preemptively (Story 2.3 Auditor MED-2 norm-inheritance),
  despite all its keyword names being unique at the time.

DynamicCore flattening is last-wins on duplicate keyword names; `_build_components()`
carries an import-time collision detector (RuntimeError) that guards against silent
shadowing. Excluded libraries require
`Library AgentEval.<pkg>.library.<Cls> WITH NAME <X>`, which all 4 fresh-user CLI trials
failed to discover without burning iterations (dossier E4).

A second, compounding inconsistency: `@keyword(name=...)` prefixes are applied
per-keyword, not per-library. StatsLibrary (7/7 keywords `Stat.*`) and JudgeLibrary (2/2
`Judge.*`) are internally consistent; SkillsLibrary mixes (8 unprefixed + 2 `Skill.*`)
and MCPLibrary mixes (9 unprefixed + 1 `MCP.*`). HooksLibrary's single keyword is the
generic, collision-prone `Get Config`. There is no rule a user can learn.

The double-prefix trap: because RF's `WITH NAME` prefix stacks on top of baked-in name
prefixes, `Library ...SkillsLibrary WITH NAME Skill` makes the fully-qualified form of
`Skill.Compare Discoverability` become `Skill.Skill.Compare Discoverability`, while its
unprefixed siblings qualify as `Skill.Get Frontmatter` — two different shapes in one
import.

Constraints:

- `feedback_libdoc_namespace_keyword_must_be_multiword` (ratified Epic 12 retro,
  confirmed N=2): the post-dot portion of a baked-prefix keyword name MUST be multi-word,
  or DynamicCore+libdoc auto-splits it (`Judge.Calibrate` → `Judge. Calibrate`).
- `tests/unit/conventions/test_keyword_name_idiom.py` verb-allowlist check operates on
  `name.split(".")[-1]`, so prefixed names are already idiom-compatible.
- `_HostBudgetPlumbing` (Story 14.6) is the constructor mixin through which excluded
  libraries receive `max_cost_usd` / `max_runtime_seconds` when imported standalone;
  SkillsLibrary and MCPLibrary inherit it, SubagentsLibrary and HooksLibrary do not
  (no `@guarded_fanout` keywords).
- Pre-1.0, unreleased on PyPI: breaking renames are acceptable and there is no
  deprecation-alias obligation.

## Goals / Non-Goals

**Goals:**

- `Library AgentEval` exposes every public keyword of every shipped sub-library, with
  zero name collisions and correct budget forwarding.
- One sentence a user can learn that predicts every keyword's name.
- Standalone direct imports keep working, including constructor kwargs
  (`max_cost_usd=...`), without `WITH NAME` and without double-prefix surprises.
- All user-facing surfaces (README, recipes, scaffold templates, libdoc,
  stability-surface contract) teach only the single-import pattern.

**Non-Goals:**

- No new keywords, no behavior changes inside keyword bodies.
- No deprecation aliases for the old names (pre-1.0; nothing released).
- No content/doc-drift fixes beyond the import/rename mechanics
  (owned by `fix-first-run-experience`).
- No change to the Orchestration/Metrics/Telemetry/Assertions/Heatmap keyword names.

## Decisions

### D1 — Naming rule: namespace-prefix ALL keywords of artifact/engine sub-libraries; core-loop keywords stay unprefixed

**The rule (user-facing, one sentence):** *Keywords that operate on a specific artifact
or engine — skills, subagents, hooks, MCP servers, statistics, LLM-judge — are prefixed
with that namespace (`Skill.` / `Subagent.` / `Hook.` / `MCP.` / `Stat.` / `Judge.`);
the shared run-measure-assert loop (Send Prompt, Get Tool Call Count, Trajectory Should
Match, Get Effective Config, ...) is unprefixed.*

Prefix tokens follow the docs' established `WITH NAME` vocabulary: `Skill`, `Subagent`,
`Hook`, `MCP`, `Stat`, `Judge` (singular, matching existing baked prefixes and module
docstrings).

Resulting renames (all **BREAKING**, all satisfying the multi-word-after-dot
constraint — every post-dot portion below is ≥ 2 words):

| Library | Old name | New name |
|---|---|---|
| SkillsLibrary | Get Frontmatter | Skill.Get Frontmatter |
| SkillsLibrary | Get Description | Skill.Get Description |
| SkillsLibrary | Get Allowed Tools | Skill.Get Allowed Tools |
| SkillsLibrary | Get Disable Model Invocation | Skill.Get Disable Model Invocation |
| SkillsLibrary | Should Be Valid Frontmatter | Skill.Should Be Valid Frontmatter |
| SkillsLibrary | Get Activation Decision | Skill.Get Activation Decision |
| SkillsLibrary | Get Discoverability | Skill.Get Discoverability |
| SkillsLibrary | Should Activate For | Skill.Should Activate For |
| SubagentsLibrary | Get Frontmatter | Subagent.Get Frontmatter |
| HooksLibrary | Get Config | Hook.Get Config |
| MCPLibrary | Get Server Config | MCP.Get Server Config |
| MCPLibrary | Get Tool Schema | MCP.Get Tool Schema |
| MCPLibrary | Validate Tool Schema | MCP.Validate Tool Schema |
| MCPLibrary | Start Server | MCP.Start Server |
| MCPLibrary | Connect To Server | MCP.Connect To Server |
| MCPLibrary | Stop Server | MCP.Stop Server |
| MCPLibrary | List Tools | MCP.List Tools |
| MCPLibrary | Call Tool | MCP.Call Tool |
| MCPLibrary | Get Tool Discoverability | MCP.Get Tool Discoverability |

Already-conforming (no change): `Skill.Get Activation Pass At K`,
`Skill.Compare Discoverability`, `MCP.Compare Tool Discoverability`, all 7 `Stat.*`, both
`Judge.*`. Unprefixed core-loop keywords (Orchestration, Telemetry, Metrics, Assertions,
Heatmap, top-level config/tier keywords) are unchanged.

**Alternatives considered:**

- *Rename only the two colliders to `Get Skill Frontmatter` / `Get Subagent
  Frontmatter`.* Minimal churn, but it leaves three libraries with mixed
  prefixed/unprefixed names, leaves the generic `Get Config` / `Call Tool` /
  `Start Server` names one future library away from the next collision, and leaves no
  learnable rule — the E4 friction was the *pattern's* unpredictability, not just the
  collision.
- *Prefix everything, including Metrics/Telemetry/Orchestration.* Simplest rule, but
  wrecks the natural-prose reading of the highest-frequency keywords (`Send Prompt`,
  `Trajectory Should Match`) and would break every existing test and recipe for no
  disambiguation benefit — those names are already unique and domain-generic.
- *Drop all baked prefixes; make every name globally unique via descriptive nouns.*
  Un-ships the `Stat.` / `Judge.` prefixes users and docs already learned, loses the
  libdoc grouping benefit, and yields awkward names (`Get Statistical Pass At K
  Confidence Interval`).

Empirical support for the chosen rule: the `agenteval init` scaffold and all 4 CLI-trial
transcripts already *guessed* the `MCP.Start Server` shape under `Library AgentEval` —
this design makes the guessed name the real name.

### D2 — Composition: add the three excluded libraries to `_SUB_LIBRARIES`; forward budgets via a `_HostBudgetPlumbing` subclass check

`_SUB_LIBRARIES` gains `("AgentEval.skills.library", "SkillsLibrary")`,
`("AgentEval.subagents.library", "SubagentsLibrary")`,
`("AgentEval.mcp.library", "MCPLibrary")`. The carve-out comment block (L92-120 of
`__init__.py`) is replaced with a statement of the D1 naming rule and a pointer to the
collision detector.

Budget forwarding: instead of extending the `elif cls_name == ...` chain two more times,
`_build_components()` forwards `max_cost_usd` + `max_runtime_seconds` to any component
class that is a `_HostBudgetPlumbing` subclass (covers Stats, Judge, Skills, MCP today
and future mixin adopters automatically). `OrchestrationLibrary` (provider + budgets) and
`MetricsLibrary` / `AssertionsLibrary` (`allow_external_mcp_blind`) keep their explicit
branches. `SubagentsLibrary` and `HooksLibrary` construct with no kwargs. `MCPLibrary`
needs no `mcp_per_test` forwarding — its lifecycle keywords are handle-based
(`Start Server` returns an `MCPServerHandle`; scope plumbing is a separate, existing
concern).

This closes carry-over **C55**: under `Library AgentEval    max_cost_usd=1.0`,
`Skill.Get Activation Decision`'s `@guarded_fanout` receives a real budget for the first
time.

The import-time collision detector in `_build_components()` is kept verbatim — after D1
all names are unique, and the detector remains the loud guard against future
regressions. The lazy-import ImportError-swallow also stays (it is what keeps
`Library AgentEval` green on partial installs).

**Alternative considered:** keep the carve-out and only fix docs to teach `WITH NAME`
better. Rejected: it retains the C55 budget gap, retains 3 extra import lines per suite,
and E4 shows even good docs do not save the iteration — discovery fails at the
"which class path do I import" step.

### D3 — Standalone imports: supported without `WITH NAME`; double-prefix trap documented, not blocked

Direct imports remain first-class for budget-scoping operators:

```robotframework
Library    AgentEval.skills.library.SkillsLibrary    max_cost_usd=2.0
```

Because every keyword now bakes its prefix, standalone imports need **no** `WITH NAME` —
the call sites read identically (`Skill.Get Frontmatter`) under both import styles, so
tests can migrate between the two without edits. Module docstrings and docs drop the
`WITH NAME Skill` idiom and instead carry a short warning: adding `WITH NAME Skill`
still works (RF resolves the unqualified baked name) but makes the fully-qualified form
`Skill.Skill.Get Frontmatter` — harmless, pointless, and confusing; don't do it. We do
not attempt runtime detection of `WITH NAME` usage — RF does not expose a clean hook for
it, and the failure mode is cosmetic.

### D4 — Documentation and scaffold surfaces updated in the same change

- README: replace the three `WITH NAME` import blocks (L161/L176/L195) with the single
  `Library AgentEval` import; keyword tables show the new prefixed names; add the
  one-sentence naming rule next to the import example.
- `docs/recipes/*`: same replacement wherever `WITH NAME` or an old keyword name
  appears; recipe code blocks must still pass the existing dryrun conventions gate
  (`feedback_executable_doc_precheck`).
- Scaffold templates (`src/AgentEval/_init/templates/*.robot`): drop the direct-path
  imports; `example_mcp_runtime.robot`'s `MCP.Start Server` call becomes valid as
  written (other template defects are `fix-first-run-experience` scope).
- Libdoc: regenerate all `docs/keywords/*.html`; the Story 14.1 libdoc-render smoke step
  verifies no auto-split names (multi-word-after-dot constraint).
- `docs/contracts/stability-surface.md` + `docs/phase-1-5-carry-overs.md` C55 row:
  updated to the new names / closure evidence.

## Risks / Trade-offs

- [Breaking renames invalidate every existing call site at once] → Pre-1.0, unreleased
  on PyPI; the blast radius is entirely in-repo. Mitigation: a repo-wide
  grep-and-replace pass over `tests/`, `docs/`, templates, plus the full test suite +
  recipe-dryrun conventions gate as the completeness check (no old name may survive
  outside CHANGELOG/history files).
- [DynamicCore composition of 11 components slows `Library AgentEval` import] →
  Components were already importable; the three added libraries are lightweight
  (parser + handle code, no subprocess spawn at construction). Existing import-time
  tests bound this.
- [`Hook.Get Config` rename churns the one already-composed library] → Accepted
  deliberately: leaving `Get Config` unprefixed would break the D1 rule on day one and
  the name is the most collision-prone in the codebase.
- [Future sub-library forgets the rule] → The import-time collision detector catches
  duplicate names loudly; a conventions test asserting "libraries with a namespace
  token prefix ALL their keywords" makes the rule mechanical rather than tribal.
- [Docs/tests drift between old and new names during the change] → Single change, single
  commit series; the final task is a repo-wide negative grep for the 19 old names.

## Migration Plan

1. Rename keywords (source `@keyword(name=...)` values + docstrings).
2. Update `_SUB_LIBRARIES` + `_build_components()` forwarding; delete carve-out comments.
3. Sweep tests, then docs/templates; regenerate libdoc.
4. Negative-grep gate: zero occurrences of the old names outside git history and
   carry-over/CHANGELOG prose.

Rollback: revert the change commits; no data or released-API migration exists.

## Open Questions

- None blocking. (Whether `Get Cohort Heatmap` should become `Stat.Get Cohort Heatmap`
  was considered and rejected: HeatmapLibrary is a cross-adapter reporting surface, not
  the stats engine; it stays unprefixed under the D1 rule.)
