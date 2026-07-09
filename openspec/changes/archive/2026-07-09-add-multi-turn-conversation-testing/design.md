## Context

AgentEval's execution surface is single-shot end to end:

- `Send Prompt` constructs a fresh adapter instance and performs exactly one
  `adapter.run()` (`src/AgentEval/orchestration/library.py:152-238`).
- `Run Scenario` loops `evals[] × repeat` independent `run()` calls; multi-turn
  threading has been an explicit carry-over since Story 4.3 (DF-4.3-S4, named
  in the module docstring and the `Run Scenario` docstring).
- `GenericAdapter.run()` builds `messages = [Message(role="user",
  content=prompt)]` fresh every call (`coding_agent/generic.py:216`).
- `OpenAIAgentsAdapter` explicitly scopes sessions out
  (`coding_agent/openai_agents.py:149`).
- `ClaudeCodeCLIAdapter` already *observes* a session id (the stream-json
  `system`/`init` event carries session metadata) but never resumes it.

The market context (dossier E6, CRITICAL): LangWatch Scenario's whole product
is simulated-user multi-turn tests (`scenario.run(agents=[Agent(),
UserSimulatorAgent()], script=[...], max_turns, cache_key)`); DeepEval's
`ConversationalTestCase` is a `turns: [Turn(role, content, tools_called)]`
list with scenario/expected_outcome context and dedicated conversational
metrics. Neither has AgentEval's structural advantage: an RF test body is
already a readable, versionable conversation script.

Existing machinery this design deliberately reuses rather than reinvents:

- `@tier(N)` determinism annotations + `@guarded_fanout()` cost/runtime
  budgets with `_HostBudgetPlumbing` auto-wiring (`_kernel/guardrails.py`,
  `_kernel/host_budget_plumbing.py`).
- `AgentRunResult` as the universal per-run currency — metrics keywords
  already accept `AgentRunResult | list[AgentRunResult]`
  (`metrics/library.py`), and `Judge.Get Score` already takes a single
  `AgentRunResult` (`judge/library.py:117`), which makes per-turn judging
  free.
- The `mcp_coverage` honesty-field philosophy (ADR-016): when the system
  cannot deliver the strong form of a capability, it degrades and *says so*
  in a machine-readable metadata field rather than silently pretending.

Constraints:

- PRD FR12: the `CodingAgentAdapter` Protocol has a SINGLE `run()` method.
  Multi-turn must not grow the required Protocol surface.
- Pre-1.0: breaking scenario-schema changes are acceptable and flagged.
- Dossier E4: no new `Library AgentEval.x.library.Y WITH NAME` import sprawl —
  new keywords must compose into the top-level `AgentEval` library.
- Dossier E5: errors.py already has 30 classes; add the minimum.

## Goals / Non-Goals

**Goals:**

- Scripted multi-turn conversations as plain RF keyword sequences
  (`Start Conversation` → N × `Send Message` → assertions) — the RF-native
  style, zero new syntax.
- LLM-driven simulated-user conversations (`Simulate User`) with persona,
  goal, `max_turns`, budget guards, and `cache_key` repeatability.
- Judge and metrics reuse at turn and transcript granularity with near-zero
  new API (the transcript exposes `list[AgentRunResult]`).
- Honest, machine-readable adapter-capability degradation for session
  continuation (`continuation` field), mirroring `mcp_coverage`.
- Scenario YAML `turns:` so declarative suites get multi-turn too.
- Determinism-tier annotations on every new keyword; mock-provider
  conversations deterministic by default so unit tests need no API keys.

**Non-Goals:**

- Red-team multi-turn attack orchestration (Crescendo etc.) — sibling
  `add-red-team-probes` builds on this foundation; this change only ensures
  `ConversationHandle` + `Simulate User` are usable as that foundation.
- Subagent delegation-routing assertions — sibling
  `add-subagent-delegation-testing`.
- Native `run_turn()` for ALL adapters. Phase-1 natives: `generic` (message
  history — trivial and exercises the mock provider) and `claude-code-cli`
  (`--resume`). Codex/Copilot/opencode/openai-agents degrade honestly;
  each gets a named follow-up marker, not silent scope creep.
- DeepEval-style prebuilt conversational quality metrics (KnowledgeRetention,
  RoleAdherence…). The rubric-driven judge over a transcript covers these
  Phase-1; named presets belong with sibling `add-judge-criteria-shortcuts`.
- Parallel/concurrent conversations sharing one native CLI session.
  One handle = one session, sequential sends.

## Decisions

### D1 — New `conversation/` sub-library; shared types live in `types.py`

`ConversationLibrary` lands at `src/AgentEval/conversation/library.py` and is
composed into `_SUB_LIBRARIES` (top-level `AgentEval` import gets the keywords
— no import sprawl). `ConversationTurn` + `ConversationTranscript` go in
`src/AgentEval/types.py` because judge + metrics + conversation all consume
them — the architecture L853 rule ("cross-sub-library data flow goes through
shared types in `types.py`") applies exactly.

*Alternative considered*: extend `OrchestrationLibrary`. Rejected — the
conversation state machine (handle registry, simulator, cache) is a coherent
unit; orchestration/library.py is already the FR14/FR15 surface and this keeps
`Run Scenario`'s multi-turn path a thin call into `conversation/`.

### D2 — `ConversationHandle` is test-owned, mutable, and explicit

`Start Conversation` returns a handle object the `.robot` test stores in a
variable and passes to every subsequent keyword — the same test-owns-the-handle
pattern Story 3.1 ratified for `MCPServerHandle` (no hidden library-managed
"current conversation" global, which breaks under parallel suites). The handle
carries: adapter name + constructed adapter instance (reused across turns —
unlike `Send Prompt`'s per-call construction, session affinity requires it),
frozen ctor/run kwargs, the growing turn list, the native session reference
when one exists, and a closed flag. `End Conversation` marks it closed and
releases any native resources; sends after close raise
`ConversationClosedError`. Handles are NOT thread-safe; sequential use only
(documented).

The transcript is an immutable snapshot: `Get Conversation Transcript` returns
a frozen `ConversationTranscript` (turns tuple + aggregates) so stored
transcripts don't mutate under later sends — consistent with the M_R6
defensive-copy discipline used across `types.py`.

### D3 — Turn model: role-tagged turns, `AgentRunResult` as the agent-turn payload

`ConversationTurn(index, role, content, result, continuation)` where
`role ∈ {"user", "agent"}`; `result` is the `AgentRunResult` for agent turns
and `None` for user turns; `continuation` (agent turns) records how the turn
was threaded (D4). One `Send Message` appends a user turn + an agent turn and
returns the agent turn's `AgentRunResult` directly — so the existing assertion
and metric vocabulary (`Tool Call Should Have Occurred`, `Get Latency`, …)
applies to a turn with zero adaptation. This is deliberately DeepEval-`Turn`-
compatible in shape (role/content) for future interop, while keeping
`AgentRunResult` — not a new type — as the unit of judgment/measurement.

### D4 — Continuation is an OPTIONAL duck-typed adapter method + honesty field

FR12 forbids growing the Protocol, so continuation is capability-probed:

- An adapter MAY implement `run_turn(prompt, *, conversation_state, **kwargs)
  -> AgentRunResult`, where `conversation_state` is a small dataclass
  (prior turns + adapter-opaque `session_ref` slot the adapter reads/writes).
  Detection is `callable(getattr(adapter, "run_turn", None))` — same
  duck-typed-optional pattern as `_assert_binary_version` overrides.
- **`native_session`** path: `generic` implements it by rebuilding the full
  `messages=[...]` history (the natural chat-API form; works on the mock
  provider ⇒ deterministic unit tests). `claude-code-cli` implements it by
  capturing the session id from the stream-json `system`/`init` event on turn
  1 and spawning subsequent turns with `--resume <session_id>` (empirical
  probe required before finalizing flags, per
  `feedback_listener_hook_api_surface_empirical_check` — exact resume flag
  behavior MUST be probed against the pinned 2.x binary).
- **`replayed_history`** fallback: for adapters without `run_turn`, the
  orchestration layer composes a delimited plain-text preamble of prior turns
  plus the new user message into a single `run()` prompt. Works for every
  adapter; honestly weaker (the agent re-reads history as text; no persistent
  tool/workspace state across turns).
- **Honesty field** (the `mcp_coverage` philosophy, ADR-016): every agent turn
  records `continuation: "initial" | "native_session" | "replayed_history"`,
  and `ConversationTranscript.continuation_mode` reports the conversation-wide
  mode. A user comparing Claude Code vs Copilot multi-turn behavior can see —
  in the transcript, not a doc footnote — that one threaded natively and one
  replayed.
- `Start Conversation    require_native=True` raises
  `ConversationContinuationUnsupportedError` up front for adapters without
  `run_turn`, for tests where replay semantics would invalidate the eval.

*Alternative considered*: pass `session_id=` through `run(**kwargs)`.
Rejected — silently swallowed by `**kwargs`-tolerant adapters (the
InProcessAdapter ctor pattern), producing fake-green threading with no error
and no honesty signal. The duck-typed method makes capability explicit.

*Alternative considered*: replay-only (no native path). Rejected — it erases
the most valuable eval signal for CLI agents (persistent session/workspace
state) and would misrepresent agents' real multi-turn behavior.

### D5 — `Simulate User`: judge-style LLM simulator, Tier-3, budget-guarded, cacheable

The simulator reuses the judge's architectural recipe (an adapter-backed
single-shot LLM call with a composed prompt, `judge/library.py` precedent):

- `Simulate User    ${conv}    persona=...    goal=...    max_turns=5` loops:
  compose simulator prompt (persona + goal + rendered transcript) →
  `simulator_adapter.run()` → extract next user message → `Send Message` →
  check stop. Simulator defaults to `simulator_adapter="generic"` with an
  explicit `simulator_model=`, mirroring `judge_adapter`/`judge_model` naming.
- **Stop conditions**: the simulator is instructed to emit a sentinel token
  (`<<GOAL_ACHIEVED>>` / `<<GIVING_UP>>`) when the goal is met or unmeetable
  (LangWatch's judge-decides-when-to-stop, simplified to the user side);
  `max_turns` is the hard cap. The returned transcript records
  `stop_reason: "goal_achieved" | "gave_up" | "max_turns"`.
- **Tier/budget**: `@tier(3)` + `@guarded_fanout()` — it is a fan-out of
  2×turns LLM calls; `_HostBudgetPlumbing` wiring makes library-level
  `max_cost_usd`/`max_runtime_seconds` apply with zero new budget code. The
  per-turn agent costs already flow through `AgentRunResult.cost_usd`;
  simulator-call costs are added to the transcript's `total_cost_usd`.
- **`cache_key` repeatability** (stolen from LangWatch Scenario, adapted):
  when `cache_key=` is given, each simulator-generated user message is cached
  on disk keyed by `hash(cache_key, turn_index, transcript_so_far)` under
  `${OUTPUT_DIR}/agenteval/simulation-cache/`. Re-runs replay identical user
  messages, isolating agent-side variance — which composes with the existing
  determinism-tier story (a cached simulation + seeded Tier-2 agent is
  LLM-deterministic). Cache lookups/misses are logged; the transcript records
  `simulator_cache: "hit" | "miss" | "disabled"` per the honesty philosophy.
- **Scripted style is co-equal**: a sequence of `Send Message` keywords IS a
  scripted conversation — no dedicated DSL needed because RF is the DSL. The
  recipe doc shows both styles side by side, including the mixed style
  (scripted opening turns, then `Simulate User` to finish — LangWatch's
  `script:` + auto-proceed idea, expressed as plain keyword ordering).

### D6 — Judge reuse: per-turn is free; transcript is a rendering concern

`Judge.Get Score    result=${turn_result}    rubric=...` already works — a
turn's `AgentRunResult` is a plain `AgentRunResult`. The extension: `result=`
also accepts a `ConversationTranscript`, in which case `_compose_judge_prompt`
renders the full role-tagged transcript (instead of one `response_text`) into
the judge prompt. `Judge Turn Should Pass    ${conv}    rubric=...    turn=-1`
is a Tier-2 convenience that scores the given turn (default: last agent turn)
and fails the RF test unless `pass_threshold_met` — the assertion-style
counterpart, un-namespaced like the existing `... Should ...` assertion
keywords. Rubric calibration (κ≥0.7 gate) applies unchanged — a transcript
rubric is still a rubric.

### D7 — Conversational metrics via extraction, not duplication

`Get Conversation Results    ${conv_or_transcript}` returns the ordered
`list[AgentRunResult]` of agent turns. Because every metrics keyword already
accepts `list[AgentRunResult]`, per-turn cost/latency/tool-call aggregation
over a conversation is the existing vocabulary:
`Get Cost Total    ${results}`, `Get Latency P95    ${results}`, etc. The only
genuinely new metric keyword is `Get Turn Count` (agent-turn count of a
conversation/transcript). `Transcript Should Contain    ${conv}    <text>
role=agent|user|any    as_regex=False` covers full-transcript content
assertions. No DeepEval-style metric zoo.

### D8 — Scenario YAML `turns:` (BREAKING, pre-1.0)

`ScenarioEval` gains `turns: list[str]` (user messages, threaded through one
conversation via the same D4 machinery). Validation becomes **exactly one of**
`prompt` | `turns` (previously `prompt` REQUIRED — this is the breaking edge;
existing files with `prompt:` remain valid). `repeat: N` repeats the whole
conversation N times, fresh handle each time. `Run Scenario` keeps returning a
flat `list[AgentRunResult]`; a multi-turn eval contributes one result per turn
per repeat — order-stable so index math stays predictable, and each result's
`continuation` honesty field survives in the flat list. Adapter capability
differences degrade exactly as D4 (no scenario-level `require_native` Phase-1;
the honesty fields carry the signal). A declarative `simulate_user:` block in
YAML is deliberately deferred — simulation belongs in `.robot` where budget
and persona iteration are visible.

*Alternative considered*: `turns:` at scenario top level. Rejected — per-eval
keeps `repeat` semantics and mixed suites (some single-shot, some multi-turn
evals) coherent.

### D9 — Errors: exactly two new leaves

`ConversationClosedError` (send/simulate on a closed handle) and
`ConversationContinuationUnsupportedError` (`require_native=True` against a
replay-only adapter), both with the File/Line/Field/Fix-style message
discipline and a `fix_suggestion`. Everything else reuses existing classes
(`InvalidScenarioYAMLError` for `turns:` validation, budget errors from the
kernel). This respects the E5 finding (30 error classes, ~15 ever raised) —
no per-condition leaf explosion.

## Risks / Trade-offs

- **[CLI `--resume` semantics drift across claude versions]** → The
  `claude-code-cli` `run_turn` lands behind an empirical probe task (capture
  real `--resume` stream-json against the pinned `>=2.0.0,<3.0.0` binary)
  before the parser is finalized, per
  `feedback_listener_hook_api_surface_empirical_check`; unit tests use
  captured fixtures. If resume proves unstable, the adapter honestly falls
  back to `replayed_history` — the honesty field means tests keep passing
  with the true mode visible rather than lying.
- **[Replayed history silently changes eval meaning]** (an agent that re-reads
  history performs differently from one with real session state) → the
  per-turn `continuation` field + `require_native=True` opt-in +
  transcript-level `continuation_mode` make the degradation first-class data;
  the recipe doc states the semantic difference explicitly.
- **[Simulator cost blowups]** (`max_turns=20` × 2 LLM calls/turn) →
  `@guarded_fanout` refuses entry/aborts on `max_cost_usd`; `max_turns` is a
  required-default (5), not unbounded; `cache_key` re-runs cost ~half
  (simulator side cached).
- **[Simulator loops that never terminate semantically]** (agent and simulator
  politely thanking each other) → sentinel-token stop + hard `max_turns` cap;
  `stop_reason="max_turns"` is visible so a test can assert the goal was
  actually achieved rather than timed out.
- **[Cache staleness: cached user messages diverge from live agent replies]**
  → cache key includes the transcript-so-far hash, so if the agent's replies
  change, subsequent turns are cache misses (correct behavior); documented.
- **[Handle reuse across threads / Pabot]** → explicitly unsupported +
  documented; handles are per-test-owned per the Story 3.1 pattern.
- **[Flat `Run Scenario` return conflates evals]** → order-stability is
  specced; a future transcript-returning variant can be added without
  breaking (the flat list is the compatibility surface today).
- **[Scope: 5 capabilities in one change]** → the capabilities are stackable
  and independently testable (lifecycle first; simulator/judge/metrics/YAML
  each build on it); tasks.md orders them so lifecycle + generic-adapter
  native path is a self-contained mergeable core.

## Migration Plan

1. Land shared types + errors + `conversation/` lifecycle with the `generic`
   native path (deterministic mock tests — no keys, no breaking changes).
2. Land judge + metrics extensions (additive).
3. Land `claude-code-cli` native `run_turn` behind the empirical probe.
4. Land `Simulate User` + cache (Tier-3, budget-guarded).
5. Land the scenario-schema `turns:` change LAST (the only breaking piece):
   loader validation switches from "prompt REQUIRED" to "exactly one of
   prompt|turns". Rollback = reverting the loader/schema commit; no stored
   data migrates. Release notes flag the pre-1.0 break; `agenteval init`
   template YAML is untouched by this change (single-shot remains valid).

## Open Questions

- Should `End Conversation` be auto-invoked by a suite-teardown-style listener
  for leaked handles (Story 1b.1 process-group hygiene precedent), or is a
  logged warning on GC enough for Phase-1? (Design default: logged warning;
  no listener coupling.)
- Exact `claude --resume` flag surface for non-interactive `-p` mode on the
  pinned 2.x line — resolved by the mandated empirical probe task.
- Whether `Get Conversation Transcript` should also render a human-readable
  text form (for judge prompts AND log.html attachments) via one shared
  renderer — leaning yes; the judge transcript rendering (D6) and the
  simulator prompt rendering (D5) should share it.
