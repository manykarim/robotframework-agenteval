## Why

Every AgentEval execution path is single-shot: `Send Prompt` performs exactly one
`adapter.run()` call (`src/AgentEval/orchestration/library.py`), scenario YAML is
one `prompt` per eval (`scenarios/schema.py`), and the multi-turn gap has been an
acknowledged carry-over since Story 4.3 (DF-4.3-S4 "multi-turn threading is
Phase-1.5"). Meanwhile multi-turn conversation testing is the single biggest
market gap identified in the 2026-07 exploration dossier (E6 CRITICAL — not on
any roadmap): LangWatch Scenario built an entire product around simulated-user
multi-turn tests, and DeepEval's `ConversationalTestCase`/`Turn` model is its
flagship agent-eval surface. AgentEval has a structural advantage neither can
match — **Robot Framework keyword sequences ARE a natural conversation-script
DSL** — so a `Send Message` keyword sequence reads as a conversation script with
zero new syntax. This change is the flagship Phase-2 expansion that turns that
advantage into shipped capability.

## What Changes

- **New `ConversationLibrary` sub-library** (composed into the top-level
  `AgentEval` library — no new import sprawl per dossier E4) with conversation
  lifecycle keywords: `Start Conversation` (returns a `ConversationHandle`),
  `Send Message` (returns a per-turn `AgentRunResult`), `Get Conversation
  Transcript`, `End Conversation`, and the transcript assertion
  `Transcript Should Contain`.
- **New shared types** in `AgentEval/types.py`: `ConversationTurn` (role +
  content + per-agent-turn `AgentRunResult` + honest `continuation` field) and
  `ConversationTranscript` (turns + aggregates), consumed cross-sub-library by
  judge and metrics per the architecture L853 shared-types rule.
- **Adapter conversation-continuation contract**: an OPTIONAL duck-typed
  `run_turn()` method adapters MAY implement for native session continuation
  (generic/LiteLLM via message-history replay in-process — the natural chat-API
  form; Claude Code CLI via `--resume <session_id>`). Adapters without it
  degrade to orchestration-layer history-replay prompting, and every agent turn
  records `continuation="native_session" | "replayed_history" | "initial"` —
  same honesty-field philosophy as `mcp_coverage` (ADR-016). The
  `CodingAgentAdapter` Protocol itself is UNCHANGED (single `run()` per FR12).
- **Simulated-user testing**: `Simulate User` keyword — an LLM-driven user
  simulator (persona + goal + max_turns) that drives a conversation
  Tier-3-style, budget-guarded via the existing `@guarded_fanout` /
  `max_cost_usd` machinery, with a LangWatch-Scenario-inspired `cache_key` for
  repeatable simulations. Scripted conversations (a plain sequence of
  `Send Message` keywords) are documented as the co-equal first style.
- **Judge at any turn**: `Judge.Get Score` already accepts a per-turn
  `AgentRunResult` (works today — documented); it is extended to accept a
  `ConversationTranscript` for whole-conversation judging, plus a
  `Judge Turn Should Pass` convenience assertion.
- **Conversational metrics**: `Get Turn Count` plus `Get Conversation Results`
  (extracts `list[AgentRunResult]` from a conversation) so ALL existing metric
  keywords (`Get Cost Total`, `Get Latency P95`, `Get Tool Call Count`, …)
  aggregate over conversations unchanged — they already accept
  `list[AgentRunResult]`.
- **BREAKING** (pre-1.0, acceptable): scenario YAML schema gains per-eval
  `turns: [<user message>, ...]` executed as one threaded conversation;
  `prompt` becomes "exactly one of `prompt` | `turns`" instead of REQUIRED.
  `Run Scenario` keeps its flat `list[AgentRunResult]` return (each multi-turn
  eval contributes one result per turn).
- New typed errors (at most 2, per the dossier E5 errors.py-bloat finding):
  `ConversationClosedError` and `ConversationContinuationUnsupportedError`.

NOT in scope (siblings): red-teaming attacks layered on conversations —
`add-red-team-probes` may later build Crescendo-style multi-turn attack loops
directly on `ConversationHandle` + `Simulate User` (this change is deliberately
its foundation); subagent delegation-routing assertions
(`add-subagent-delegation-testing`).

## Capabilities

### New Capabilities
- `conversation-lifecycle`: conversation handle lifecycle keywords
  (`Start Conversation` / `Send Message` / `Get Conversation Transcript` /
  `End Conversation` / `Transcript Should Contain`), the
  `ConversationTurn`/`ConversationTranscript` shared types, the optional
  adapter `run_turn()` continuation contract, and the honest per-turn
  `continuation` degradation field.
- `simulated-user`: the `Simulate User` LLM-driven user-simulator keyword —
  persona/goal/max_turns loop, Tier-3 budget guarding, `cache_key`
  repeatability, and stop conditions.
- `conversation-judging`: judge reuse at turn and transcript granularity —
  `Judge.Get Score` transcript support + `Judge Turn Should Pass`.
- `conversation-metrics`: `Get Turn Count` + `Get Conversation Results`
  extraction so existing list-accepting metric keywords aggregate per-turn
  cost/latency/tool-calls over conversations.
- `multi-turn-scenario-yaml`: the **BREAKING** scenario-schema extension
  (`turns:` alternative to `prompt`) and its `Run Scenario` execution
  semantics, including honest adapter-capability degradation.

### Modified Capabilities
<!-- None. openspec/specs/ contains only `opencode-cli-adapter`; its
     requirements are unchanged — the opencode adapter simply has no
     `run_turn()` in this change and degrades honestly to `replayed_history`
     (native `opencode run --session` continuation is a documented follow-up,
     not a requirement here). Judge, metrics, orchestration, and scenario
     schema behaviors being extended have no existing openspec spec, so their
     changes land as ADDED requirements in the new capabilities above. -->

## Impact

- **New code**: `src/AgentEval/conversation/` (library + simulator +
  simulation cache), `ConversationTurn`/`ConversationTranscript` in
  `src/AgentEval/types.py`, 2 error classes in `src/AgentEval/errors.py`.
- **Modified code**: `src/AgentEval/library.py` `_SUB_LIBRARIES` composition +
  budget plumbing wiring; `src/AgentEval/coding_agent/generic.py` (native
  `run_turn` via message history) and
  `src/AgentEval/coding_agent/claude_code_cli.py` (native `run_turn` via
  `--resume`, session id captured from the `system`/init event);
  `src/AgentEval/judge/library.py` (`Judge.Get Score` transcript acceptance +
  `Judge Turn Should Pass`); `src/AgentEval/metrics/library.py`
  (`Get Turn Count`, `Get Conversation Results`);
  `src/AgentEval/scenarios/schema.py` + `loader.py` (**BREAKING** `turns:`
  field) and `orchestration/library.py` `Run Scenario` execution loop.
- **Docs**: keyword docstrings (Browser-Library table style), a scripted-vs-
  simulated conversation recipe, determinism-tier annotations throughout.
- **Tests**: unit (mock-provider conversations are deterministic by default —
  the mock-first philosophy carries over), plus a gated live integration smoke
  mirroring `tests/integration/test_*_live.py`.
- **Budget/tier surface**: `Simulate User` and multi-turn `Run Scenario` are
  Tier-3 `@guarded_fanout`; `Send Message` is Tier-2; handle/transcript
  keywords are Tier-1. No changes to the guardrails kernel itself.
- **Compatibility**: `CodingAgentAdapter` Protocol unchanged; existing
  single-`prompt` scenario YAML files remain valid; the only breakage is
  schema validation now accepting `turns` XOR `prompt` (previously
  `prompt` REQUIRED).
