## Why

Subagent testing is white space in the market: `docs/ai-testing-tools-landscape.md`
§7 documents it as convention-driven with **no dedicated framework** — the two
named test classes are delegation-routing tests ("does the orchestrator delegate
to the right subagent for a prompt?", asserted via Task-tool invocations) and
config-drift checks (subagents do NOT inherit parent skills, so explicit
frontmatter preloading must be lint-verified). AgentEval today ships exactly
**one** subagent keyword (`Get Frontmatter` in
`src/AgentEval/subagents/library.py`) while the raw delegation evidence is
already captured for free: every adapter run normalizes tool invocations —
including orchestrator→subagent `Task` calls — into
`AgentRunResult.tool_calls: list[ToolCallTrace]`. The gap is E6 MAJOR in the
2026-07-08 findings dossier; closing it is the second white-space differentiator
alongside the sibling `add-hooks-execution-testing` change.

## What Changes

- **Tier-1 delegation-routing assertions over an existing `AgentRunResult`**
  (deterministic — no new agent calls): `Subagent.Get Delegations` (which
  subagents were invoked, with prompts), `Subagent.Should Have Delegated To`,
  and `Subagent.Should Not Have Delegated`, all built on Task-tool-invocation
  extraction from the already-captured `ToolCallTrace` list.
- **Tier-2 routing probe** `Subagent.Should Delegate To` — given a prompt, run
  it via a named adapter once and assert the expected subagent was chosen;
  mirrors the ratified `Skill.Should Activate For` design idioms (adapter/model
  kwargs, FR28 polling ban, diagnostic integrity error with `fix_suggestion`).
- **Tier-3 decision getter** `Subagent.Get Delegation Decision` returning a
  `DelegationDecision` (delegated flag, delegation records, reasoning, cost,
  latency) — the `Stat.Run N Times`-composable sibling, mirroring
  `Skill.Get Activation Decision`.
- **Routing-accuracy statistics reusing existing Pass@k machinery**:
  `Subagent.Get Routing Pass At K` (Tier-1, hard-coded pass-predicate per the
  C59 silent-zero lesson behind `Skill.Get Activation Pass At K`) and a Tier-3
  cohort keyword `Subagent.Get Routing Accuracy` over a routing-tasks YAML
  (prompt → expected subagent), mirroring `Skill.Get Discoverability`.
- **Subagent config static checks beyond `Get Frontmatter`**:
  `Subagent.Should Declare Skills` (config-drift check — skills must be
  explicitly listed in frontmatter because subagents don't inherit them) and
  `Subagent.Tools Should Be Subset Of` (tools allowlist validation; an absent
  `tools` field means inherit-everything and fails loud). The frontmatter
  parser gains type validation for the optional `skills` field.
- New shared types (`DelegationRecord`, `DelegationDecision`,
  `SubagentRoutingResult`) in `subagents/types.py`; three narrowly-scoped new
  error classes (`SubagentDelegationAssertionError`, `SubagentConfigDriftError`,
  `InvalidSubagentRoutingTasksError`), each with ≥1 raise site by design (the
  E5 errors.py-bloat finding is a named constraint).

No existing keyword or adapter behavior changes; this change is purely additive.

**Not in scope** (sibling changes): hooks execution testing
(`add-hooks-execution-testing`) and multi-turn conversation testing
(`add-multi-turn-conversation-testing`).

## Capabilities

### New Capabilities
- `subagent-delegation-assertions`: Delegation-routing evaluation — Tier-1
  trace assertions over `AgentRunResult` (get/should-have/should-not-have
  delegated), the Tier-2 routing probe, the Tier-3 delegation-decision getter,
  and routing-accuracy statistics (Pass@k + tasks-YAML cohort) reusing the
  existing stats primitives.
- `subagent-config-validation`: Static config-drift checks on subagent `.md`
  files — explicit `skills:` preloading assertion, tools allowlist validation,
  and typed validation of the optional `skills` frontmatter field.

### Modified Capabilities

None. `openspec/specs/` contains only `opencode-cli-adapter`, whose
requirements are untouched.

## Impact

- **New code**: `src/AgentEval/subagents/types.py`,
  `src/AgentEval/subagents/_internal.py` (delegation extraction + routing
  cohort helpers), `src/AgentEval/subagents/_tasks.py` (routing-tasks YAML
  loader), new keywords in `src/AgentEval/subagents/library.py`.
- **Modified code**: `src/AgentEval/subagents/_parser.py` (optional `skills`
  field type check), `src/AgentEval/errors.py` (3 new classes),
  `src/AgentEval/subagents/__init__.py` (re-exports).
- **Tests**: `tests/unit/subagents/` (fixture-driven `AgentRunResult` +
  `ToolCallTrace` construction; stub adapter emitting Task-tool traces for the
  Tier-2/3 paths), routing-tasks YAML fixtures.
- **Docs**: README keyword table + libdoc; keyword docstrings follow the
  Browser-style migrated format already enforced for this library.
- **Dependencies**: none added. Reuses `AgentEval.stats._internal._compute_pass_at_k`,
  the `@tier`/`@guarded_fanout` kernel decorators, and the adapter discovery
  path used by `SkillsLibrary`.
- **Constraint carried, not solved**: the `Get Frontmatter` name collision
  (DF-7.1-S1) that keeps `SubagentsLibrary` out of top-level composition is
  owned by the sibling `compose-single-library-import` change; all NEW keywords
  here use `Subagent.`-prefixed multi-word names so they are composition-safe
  either way.
