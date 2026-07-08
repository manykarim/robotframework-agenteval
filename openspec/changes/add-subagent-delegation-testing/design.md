## Context

AgentEval normalizes every coding-agent run into `AgentRunResult`
(`src/AgentEval/types.py:346`) whose `tool_calls: list[ToolCallTrace]` carries
one frozen record per tool invocation (`name`, `args` mapping, `result`,
`error`, `latency_ms`, `sequence_index`, `gen_ai_tool_call_id`). When an
orchestrator agent delegates to a subagent, the delegation surfaces as a
**Task-tool invocation** in exactly this stream (e.g. Claude Code's `Task` tool
with `subagent_type` + `prompt` in its args). So the evidence needed for
delegation-routing assertions is already captured; nothing new must be traced.

The subagent library (`src/AgentEval/subagents/library.py`) currently has one
keyword, `Get Frontmatter` (parse + validate `name`/`description`, optional
typed `tools`/`model` — `subagents/_parser.py`). The skills library
(`src/AgentEval/skills/library.py`) has a mature, ratified keyword-family shape
for "did the agent pick X for prompt Y" questions:

- `Should Activate For` — Tier-2 assertion wrapper (single adapter run, FR28
  polling ban, integrity error with `prompt`/`reasoning`/`fix_suggestion`).
- `Get Activation Decision` — Tier-3 `@guarded_fanout` getter returning a
  decision dataclass, composable with `Stat.Run N Times`.
- `Skill.Get Activation Pass At K` — Tier-1, HumanEval estimator via
  `stats._internal._compute_pass_at_k` with the pass-predicate **hard-coded**
  (C59: the generic predicate silently returns 0.0 for foreign result types).
- `Get Discoverability` — Tier-3 cohort over a tasks YAML (N tasks × M trials)
  returning per-task + summary stats.

This change transplants that shape onto delegation routing, plus static
config-drift checks per `docs/ai-testing-tools-landscape.md` §7 ("subagents do
not inherit parent skills — verify explicit preloading in frontmatter").

## Goals / Non-Goals

**Goals:**
- Deterministic (Tier-1) delegation assertions over an existing
  `AgentRunResult` — zero extra agent calls, zero API keys, CI-friendly.
- A Tier-2 routing probe + Tier-3 decision getter + Pass@k/cohort statistics
  that reuse the skill-activation idioms and existing stats primitives
  verbatim (no new estimator math).
- Static config checks that make the two landscape-doc §7 drift classes
  (missing `skills:` preloading; tools outside an allowlist) one-keyword
  assertions.
- Composition-safe naming so the sibling `compose-single-library-import`
  change can flatten this library without new collisions.

**Non-Goals:**
- Hooks execution testing (`add-hooks-execution-testing` sibling).
- Multi-turn conversation testing (`add-multi-turn-conversation-testing`
  sibling); the routing probe is single-shot by design.
- Resolving DF-7.1-S1 (the `Get Frontmatter` collision that keeps
  `SubagentsLibrary` out of top-level composition) — owned by
  `compose-single-library-import`.
- Span-based per-subagent scoring (child-span metrics à la Pydantic Evals) —
  Phase-2; Phase-1 works off the flat `tool_calls` projection.
- Verifying that a delegated subagent *succeeded* at its task — this change
  asserts routing, not subagent output quality.

## Decisions

### Decision 1: Delegation = Task-tool-trace extraction with a configurable tool-name set

A delegation is any `ToolCallTrace` whose `name` is in the delegation-tool set
(default `{"Task"}`, matched case-insensitively to absorb `task`/`Task`
variance across CLIs). The subagent identity is read from the trace `args` by
probing keys in a fixed order: `subagent_type` → `agent_type` → `agent` →
`name`. Both the tool-name set and nothing else are caller-overridable
(`delegation_tool=` kwarg on the extraction/assertion keywords) so non-Claude
CLIs with differently named dispatch tools (e.g. `dispatch_agent`) still work.
Every extracted `DelegationRecord` retains the raw `args` mapping for
diagnostics; a delegation-shaped trace whose args carry no recognizable
identity key yields a record with `subagent=""` that assertion keywords treat
as a non-match (observable in the error's observed-delegations listing rather
than silently dropped).

*Alternatives considered:* (a) regex over `response_text` — rejected; the
structured trace is strictly better evidence and already normalized. (b) A new
OTel span kind for delegations — rejected for Phase-1; it would require
touching every adapter, whereas the `tool_calls` projection needs none.

### Decision 2: Mirror the ratified skill-activation keyword family, tier for tier

| New keyword | Tier | Mirrors |
|---|---|---|
| `Subagent.Get Delegations` | 1 | `Get Tool Call Names` (pure projection) |
| `Subagent.Should Have Delegated To` / `Subagent.Should Not Have Delegated` | 1 | `Tool Call Should Have Occurred` (assertion over result) |
| `Subagent.Should Delegate To` | 2 | `Skill.Should Activate For` |
| `Subagent.Get Delegation Decision` | 3 + `@guarded_fanout` | `Skill.Get Activation Decision` |
| `Subagent.Get Routing Pass At K` | 1 | `Skill.Get Activation Pass At K` |
| `Subagent.Get Routing Accuracy` | 3 + `@guarded_fanout` | `Skill.Get Discoverability` |

The Tier-2/3 keywords carry the full ratified idiom set: `adapter=`/`model=`
kwargs resolved through the same adapter-discovery path `SkillsLibrary` uses,
`**kwargs` forwarded to the adapter constructor, an explicit `polling=None`
parameter that raises `PollingDisallowedError` when provided (FR28), and
budget plumbing via `@guarded_fanout` on the fan-out keywords.
`Subagent.Get Routing Pass At K` hard-codes its pass-predicate
(`isinstance(run.result, DelegationDecision) and run.result.delegated`) with
**no** `predicate` kwarg — the C59 silent-zero failure mode applies identically
here, and the fix is identical. Estimator math is delegated to
`stats._internal._compute_pass_at_k`; no new statistics are implemented.

*Alternative considered:* a single do-everything `Evaluate Routing` keyword —
rejected; the skills family proved the getter/assertion/statistic split
composes cleanly with `Stat.Run N Times` and keeps each keyword's tier honest.

### Decision 3: All new keywords use `Subagent.`-prefixed multi-word names

Every new `@keyword` name is `Subagent.<Multi Word Name>` (e.g.
`@keyword(name="Subagent.Get Delegations")`), following the
`Skill.Get Activation Pass At K` precedent. Two ratified constraints force
this: (1) `feedback_libdoc_namespace_keyword_must_be_multiword` — the post-dot
portion must be multi-word or DynamicCore+libdoc auto-splits it; all chosen
names comply; (2) DF-7.1-S1 keeps this library import-aliased today, but the
sibling composition change may flatten it into the top-level `AgentEval`
namespace — prefixed names cannot collide there. `Get Frontmatter` keeps its
existing unprefixed name (renaming it is a breaking change owned elsewhere).

### Decision 4: Three new error classes, no more (E5 bloat constraint)

The findings dossier (E5) flags `errors.py` at 30 classes with ~15 ever
raised. This change adds exactly three, each with ≥1 raise site and distinct
catch semantics:

- `SubagentDelegationAssertionError(AgentEvalIntegrityError)` — shared by all
  three delegation assertions (`Should Have Delegated To`,
  `Should Not Have Delegated`, `Should Delegate To`), mirroring
  `SkillDidNotActivateError`'s diagnostic shape (`prompt`,
  `expected_subagent`, `observed_delegations`, `reasoning`,
  `fix_suggestion`).
- `SubagentConfigDriftError(AgentEvalIntegrityError)` — shared by both static
  config checks (`Should Declare Skills`, `Tools Should Be Subset Of`);
  distinct from `InvalidSubagentDefinitionError` because the file *parses
  fine* — it drifts from the asserted expectation, which is a test failure,
  not an FR59 setup failure.
- `InvalidSubagentRoutingTasksError(_FR59Tier1SetupFailureError)` — routing
  tasks YAML structural failures, mirroring the skill-discoverability tasks
  error.

Parse/structure failures on the `.md` file itself keep raising the existing
`InvalidSubagentDefinitionError`. *Alternative considered:* per-assertion
error classes (`SubagentDidNotDelegateError`, `SubagentDelegatedUnexpectedly…`)
— rejected as exactly the 1-raise-site leaf pattern E5 calls out.

### Decision 5: Absent `tools` frontmatter means inherit-everything — the allowlist check fails loud

In the Claude Code subagent format, omitting `tools` grants the subagent the
full parent tool set. `Subagent.Tools Should Be Subset Of` therefore treats a
missing/empty `tools` field as a violation whenever an allowlist is asserted,
with a `fix_suggestion` telling the author to declare an explicit `tools:`
list. *Alternative considered:* vacuous pass on missing field — rejected; it
inverts the security posture of the check (per `feedback_honest_framing`,
silently passing the least-constrained config is the worst outcome).

### Decision 6: `skills:` declaration check is presence + membership, not effect

`Subagent.Should Declare Skills` asserts the frontmatter has an explicit
`skills:` list containing every named skill — an entirely static check
(landscape §7 "lint/CI check" class). It deliberately does NOT run an agent to
verify the skill actually loads; that composes separately via the Tier-2/3
keywords. The parser gains a type check for the optional `skills` field
(list of non-empty strings, same treatment as the existing `tools` check in
`subagents/_parser.py::validate_subagent_structure`) so `Get Frontmatter`
rejects malformed declarations early. PRD FR3's required-field set
(`name`, `description`) is unchanged.

### Decision 7: Routing-tasks YAML gets its own minimal loader

`Subagent.Get Routing Accuracy` consumes a YAML of
`tasks: [{id, prompt, expected_subagent}]` via a new
`subagents/_tasks.py` loader mirroring the skill-discoverability tasks loader
(structure validation → `InvalidSubagentRoutingTasksError`). *Alternative
considered:* reusing the skill tasks schema — rejected; its fields are
skill-shaped (`expected_activation` semantics) and overloading it would couple
the two capabilities' schemas.

## Risks / Trade-offs

- **[Delegation tool-name variance across CLIs]** — the default `{"Task"}` set
  is Claude-Code-shaped; other adapters may name their dispatch tool
  differently or not expose delegation as a tool call at all. → Mitigation:
  `delegation_tool=` override on every extraction-based keyword; raw `args`
  retained on each `DelegationRecord`; docstrings state the default is
  Claude-Code-aligned. If an adapter never emits delegation traces, Tier-1
  keywords honestly return empty/fail with the observed-tool-names listing.
- **[Identity-key probe is a heuristic]** — `subagent_type → agent_type →
  agent → name` may mis-read an exotic adapter's args. → Mitigation: probe
  order is documented and deterministic; unrecognized shapes degrade to
  `subagent=""` visibly (never a silent match); Phase-2 can add per-adapter
  extractors behind the same keyword surface.
- **[Mock/default adapter emits no Task calls]** — the Tier-2/3 keywords will
  always fail/return `delegated=False` against the mock provider. →
  Mitigation: docstrings mark them adapter-dependent (same caveat as
  `Should Activate For`); unit tests use a stub adapter that emits synthetic
  Task `ToolCallTrace`s; Tier-1 keywords remain fully testable from
  constructed `AgentRunResult` fixtures.
- **[Cohort cost blow-up]** — N tasks × M trials × real adapter is a Tier-3
  fan-out. → Mitigation: `@guarded_fanout` budget plumbing identical to
  `Skill.Compare Discoverability` (`max_cost_usd` / runtime caps), FR28
  polling ban, `trials_per_task` validation (≥1).
- **[Exact-match subagent naming]** — assertions compare the expected subagent
  name case-sensitively against the extracted identity (structured data, not
  prose), which is stricter than the skills substring heuristic. → Trade-off
  accepted: structured args make exact matching the honest choice; the error
  message lists observed names so near-misses are one-glance diagnosable.

## Migration Plan

Purely additive — no existing keyword, type, or adapter changes shape.
Deploy by merging the new modules + parser extension + error classes; rollback
= revert the commit (nothing else references the new symbols). Gate with
`uv run pytest tests/`, `uv run ruff check src/ tests/`, `uv run mypy src/`,
plus the libdoc-render smoke (Story 14.1 step) for the new namespaced keyword
names.

## Open Questions

- Exact `args` key set emitted by each shipped CLI adapter's delegation traces
  (probe at implementation time per
  `feedback_listener_hook_api_surface_empirical_check`; the identity-probe
  order in Decision 1 is written to be satisfiable under the observed shapes
  and MUST be re-verified against a captured real trace before the Tier-2
  keyword is finalized).
- Whether `Subagent.Get Routing Accuracy` should also surface Wilson CIs in
  its summary (the skills cohort does via the shared summary builder) — decide
  at implementation by whichever keeps the reuse of
  `skills/_internal`-style helpers cleanest; the spec requires
  `routing_accuracy` + per-task Pass@k as the floor.
