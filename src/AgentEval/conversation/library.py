# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

# ruff: noqa: E501
# Browser-Library-style docstring tables can carry long descriptions on a
# single physical line; libdoc renders them correctly. The per-line 120-char
# limit is waived for this file per the Phase 2 docstring-refresh convention.

"""``ConversationLibrary`` — multi-turn conversation keyword surface (add-multi-turn-conversation-testing).

Ships the conversation lifecycle keywords that turn Robot Framework's natural
keyword-sequence-as-conversation-script advantage into shipped capability:

- ``Start Conversation`` (Tier-1) → a test-owned ``ConversationHandle``.
- ``Send Message`` (Tier-2) → one threaded user→agent turn; returns the turn's
  ``AgentRunResult`` so the existing assertion + metric vocabulary applies.
- ``Get Conversation Transcript`` (Tier-1) → a frozen ``ConversationTranscript``.
- ``End Conversation`` (Tier-1) → close + release native resources.
- ``Transcript Should Contain`` (Tier-1) → full-transcript content assertion.
- ``Simulate User`` (Tier-3, ``@guarded_fanout``) → an LLM-driven user simulator.

Composed into ``_SUB_LIBRARIES`` (top-level ``AgentEval`` import gets the
keywords — no import sprawl). ``ConversationTurn`` + ``ConversationTranscript``
live in ``AgentEval.types`` per architecture L853 (judge + metrics + conversation
all consume them). The optional adapter ``run_turn()`` continuation contract +
the honest per-turn ``continuation`` degradation field live in
``AgentEval.conversation.state`` (design D4).

References:
    - add-multi-turn-conversation-testing design D1-D9.
    - ADR-016 (``mcp_coverage`` honesty-field philosophy that ``continuation`` mirrors).
    - ADR-015 (``@guarded_fanout`` cost/runtime budgets on Tier-3 ``Simulate User``).
    - Story 3.1 (test-owns-the-handle pattern, ratified for ``MCPServerHandle``).
"""

from __future__ import annotations

import re
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.adapter_kwargs import split_adapter_kwargs
from AgentEval._kernel.discovery import get_adapter
from AgentEval._kernel.guardrails import guarded_fanout
from AgentEval._kernel.host_budget_plumbing import _HostBudgetPlumbing
from AgentEval._kernel.tier import tier
from AgentEval.conversation._handle import ConversationHandle
from AgentEval.conversation._threading import execute_turn, snapshot_transcript
from AgentEval.conversation.simulator import run_simulation
from AgentEval.errors import ConversationClosedError, ConversationContinuationUnsupportedError
from AgentEval.types import AgentRunResult, ConversationTranscript, ConversationTurn

__all__ = ["ConversationLibrary"]

# Browser-Library-style docstring migration marker.
_BROWSER_STYLE_MIGRATED = True


def _turns_of(conv: ConversationHandle | ConversationTranscript) -> tuple[ConversationTurn, ...]:
    """Extract the ordered turns from a live handle OR a frozen transcript."""
    if isinstance(conv, ConversationTranscript):
        return conv.turns
    if isinstance(conv, ConversationHandle):
        return conv.turns
    raise TypeError(
        f"expected a ConversationHandle (from `Start Conversation`) or a "
        f"ConversationTranscript (from `Get Conversation Transcript`); got {type(conv).__name__}"
    )


class ConversationLibrary(_HostBudgetPlumbing):
    """Multi-turn conversation keyword surface (add-multi-turn-conversation-testing).

    Inherits ``_HostBudgetPlumbing`` so the Tier-3 ``Simulate User`` keyword
    enforces ``max_cost_usd`` + ``max_runtime_seconds`` via ``@guarded_fanout()``
    (budgets auto-wired from the top-level ``AgentEval`` config through
    ``_build_components``). Accepts ``default_provider`` (mirroring
    ``OrchestrationLibrary``) so ``AgentEval(provider="mock")`` routes
    conversations through the mock provider.
    """

    def __init__(
        self,
        *,
        default_provider: str | None = None,
        max_cost_usd: float | None = None,
        max_runtime_seconds: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(max_cost_usd=max_cost_usd, max_runtime_seconds=max_runtime_seconds, **kwargs)
        self._default_provider: str | None = default_provider

    def _inject_provider(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        effective = dict(kwargs)
        if self._default_provider is not None and "provider" not in effective:
            effective["provider"] = self._default_provider
        return effective

    @keyword(name="Start Conversation")
    @tier(1)
    def start_conversation(
        self,
        adapter: str = "generic",
        require_native: bool = False,
        **kwargs: Any,
    ) -> ConversationHandle:
        """Starts a multi-turn conversation and returns a test-owned ``ConversationHandle`` (add-multi-turn-conversation-testing).

        [Tier 1 — Deterministic] — pure setup: resolves the adapter + splits
        adapter/run kwargs via the SAME discovery + introspection rules as
        `Send Prompt`, constructs ONE adapter instance reused across turns
        (session affinity), and returns a handle. NO ``run()`` invocation
        happens here — the first LLM call is deferred to the first `Send Message`.

        | =Arguments= | =Description= |
        | ``adapter`` | Adapter name registered via ``agenteval.coding_agents``. Defaults to ``"generic"`` (LiteLLM-backed). |
        | ``require_native`` | When ``True``, fail fast with ``ConversationContinuationUnsupportedError`` if the adapter does NOT implement the optional ``run_turn`` continuation method — for tests where history-replay semantics would invalidate the eval. Default ``False`` (replay-only adapters degrade honestly). |

        Additional keyword arguments are split between the adapter constructor
        and per-turn ``run()`` exactly like `Send Prompt` (e.g.
        ``model=anthropic/claude-sonnet-4-6``, ``provider=mock``).

        The returned handle is OWNED by the test — store it in a variable and
        pass it to every subsequent conversation keyword. Handles are NOT
        thread-safe; sequential use only (the test-owns-the-handle pattern).

        Raises ``AdapterDiscoveryError`` when ``adapter`` is not registered.
        Raises ``ConversationContinuationUnsupportedError`` when
        ``require_native=True`` and the adapter lacks ``run_turn`` — before any
        LLM call.

        Example:
        | ${conv} =    `Start Conversation`    adapter=generic    model=mock/mock-model    provider=mock
        | ${r1} =    `Send Message`    ${conv}    Book a flight to Oslo
        | ${r2} =    `Send Message`    ${conv}    Actually make it business class
        | `End Conversation`    ${conv}

        Notes:
        - Tier-1: no LLM call until the first `Send Message` (Tier-2).
        - The adapter instance is reused across turns for session affinity (unlike `Send Prompt`'s per-call construction).
        - Native continuation is capability-probed via a duck-typed ``run_turn`` (design D4); ``generic`` + ``claude-code-cli`` thread natively, others degrade to ``replayed_history`` honestly.
        - Sibling keywords: `Send Message`, `Get Conversation Transcript`, `End Conversation`, `Simulate User`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        effective = self._inject_provider(kwargs)
        adapter_cls = get_adapter(adapter)
        ctor_kwargs, run_kwargs = split_adapter_kwargs(adapter_cls, effective)
        adapter_instance = adapter_cls(**ctor_kwargs)
        supports_native = callable(getattr(adapter_instance, "run_turn", None))
        if require_native and not supports_native:
            raise ConversationContinuationUnsupportedError(
                f"adapter {adapter!r} does not implement native session continuation "
                f"(no `run_turn` method) but `require_native=True` was requested",
                adapter=adapter,
                fix_suggestion=(
                    "Omit `require_native=True` to allow honest history-replay degradation "
                    "(each turn will record continuation='replayed_history'), OR use an adapter "
                    "that implements `run_turn` (e.g. `generic` or `claude-code-cli`)."
                ),
            )
        return ConversationHandle(
            adapter_name=adapter,
            adapter_instance=adapter_instance,
            run_kwargs=run_kwargs,
            supports_native=supports_native,
        )

    @keyword(name="Send Message")
    @tier(2)
    def send_message(self, conversation: ConversationHandle, message: str, **kwargs: Any) -> AgentRunResult:
        """Sends one user message and returns the agent turn's ``AgentRunResult`` (add-multi-turn-conversation-testing).

        [Tier 2 — Stochastic Single-Shot] — appends a user turn + an agent turn
        to the handle and returns the agent turn's ``AgentRunResult`` (unchanged
        shape — ``response_text``, ``tool_calls``, ``usage``, ``metadata``,
        ``cost_usd``, ``latency_seconds``, ``trace_id``), so ALL existing
        single-result assertion + metric keywords apply to a turn with zero
        adaptation. Later turns see earlier turns — natively via the adapter's
        ``run_turn`` (``continuation="native_session"``) or via a rendered
        history preamble passed to ``run()`` (``continuation="replayed_history"``);
        the first agent turn is ``continuation="initial"``.

        | =Arguments= | =Description= |
        | ``conversation`` | The ``ConversationHandle`` returned by `Start Conversation`. |
        | ``message`` | The user message text for this turn. |

        Additional keyword arguments are merged over the handle's frozen run
        kwargs (per-call wins) and forwarded to the adapter for this turn.

        Raises ``ConversationClosedError`` when the handle was already ended.

        Example:
        | ${r1} =    `Send Message`    ${conv}    Book a flight to Oslo
        | ${r2} =    `Send Message`    ${conv}    Actually make it business class
        | `Tool Call Should Have Occurred`    ${r2}    search_flights
        | ${cost} =    `Get Cost Total`    ${r2}

        Notes:
        - A scripted conversation IS a plain sequence of `Send Message` keywords — RF is the DSL, no new syntax.
        - The returned value is a plain ``AgentRunResult`` — feed it to `Judge.Get Score`, `Get Tool Call Count`, etc.
        - Continuation honesty field is recorded per agent turn; inspect via `Get Conversation Transcript`.
        - Sibling keywords: `Simulate User` (LLM-driven), `Get Conversation Transcript`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return execute_turn(conversation, message, call_kwargs=self._inject_provider(kwargs))

    @keyword(name="Get Conversation Transcript")
    @tier(1)
    def get_conversation_transcript(self, conversation: ConversationHandle) -> ConversationTranscript:
        """Returns an immutable ``ConversationTranscript`` snapshot of the conversation (add-multi-turn-conversation-testing).

        [Tier 1 — Deterministic] — a frozen snapshot: the ordered turns tuple
        plus aggregates (``turn_count`` = agent turns, ``total_cost_usd``,
        ``total_latency_seconds``, ``continuation_mode``, ``stop_reason``). The
        snapshot does NOT mutate when the conversation continues afterward, and
        remains readable after `End Conversation`.

        | =Arguments= | =Description= |
        | ``conversation`` | The ``ConversationHandle`` returned by `Start Conversation`. |

        Aggregates reconcile with per-turn results: ``total_cost_usd`` equals the
        sum of agent turns' ``result.cost_usd`` (plus any simulator costs when
        the conversation was driven by `Simulate User`).

        Example:
        | ${t} =    `Get Conversation Transcript`    ${conv}
        | Should Be Equal As Integers    ${t.turn_count}    2
        | Should Be Equal    ${t.continuation_mode}    native_session
        | Length Should Be    ${t.turns}    4

        Notes:
        - Snapshots are stable: a transcript taken after 2 turns still reports 2 turns after a 3rd `Send Message`.
        - ``continuation_mode`` reports the conversation-wide threading mode (honesty field per ADR-016 philosophy).
        - Feed the transcript straight to `Judge.Get Score` (whole-conversation judging) or `Get Conversation Results` (metrics).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return snapshot_transcript(conversation)

    @keyword(name="End Conversation")
    @tier(1)
    def end_conversation(self, conversation: ConversationHandle) -> None:
        """Closes the conversation handle and releases any native session resources (add-multi-turn-conversation-testing).

        [Tier 1 — Deterministic] — marks the handle closed. Subsequent
        `Send Message` / `Simulate User` calls raise ``ConversationClosedError``.
        `Get Conversation Transcript` remains readable after close (the recorded
        turns survive).

        | =Arguments= | =Description= |
        | ``conversation`` | The ``ConversationHandle`` to close. |

        Idempotent: ending an already-closed handle is a no-op.

        Example:
        | `End Conversation`    ${conv}
        | ${t} =    `Get Conversation Transcript`    ${conv}    # still works after close

        Notes:
        - Handles are per-test-owned; leaked handles are a logged concern only (design Open Question 1: no listener coupling in Phase-1).
        - Native CLI adapters release their session reference here.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        conversation._closed = True
        conversation._session_ref = None

    @keyword(name="Transcript Should Contain")
    @tier(1)
    def transcript_should_contain(
        self,
        conversation: ConversationHandle | ConversationTranscript,
        text: str,
        role: str = "any",
        as_regex: bool = False,
    ) -> None:
        """Asserts a conversation turn of the selected role contains ``text`` (add-multi-turn-conversation-testing).

        [Tier 1 — Deterministic] — pure inspection. Fails the test when NO turn
        of the selected role contains ``text`` (substring by default; regex
        search when ``as_regex=True``). The failure message reports the searched
        text, the role filter, and the number of turns inspected.

        | =Arguments= | =Description= |
        | ``conversation`` | A live ``ConversationHandle`` OR a frozen ``ConversationTranscript``. |
        | ``text`` | The substring (or regex pattern when ``as_regex=True``) to search for. |
        | ``role`` | ``"agent"``, ``"user"``, or ``"any"`` (default) — which turns to inspect. |
        | ``as_regex`` | When ``True``, treat ``text`` as a Python regex (``re.search``). Default ``False`` (plain substring). |

        Raises ``AssertionError`` (RF test failure) when no matching turn is found.
        Raises ``ValueError`` on an unknown ``role``.

        Example:
        | `Transcript Should Contain`    ${conv}    booking confirmed    role=agent
        | `Transcript Should Contain`    ${conv}    flight \\\\d+    role=agent    as_regex=True

        Notes:
        - Role-filtered: ``role=agent`` inspects only agent turns; ``role=user`` only user turns.
        - Sibling keyword: `Get Conversation Transcript` for structured inspection.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        if role not in ("any", "user", "agent"):
            raise ValueError(f"role must be one of 'any', 'user', 'agent'; got {role!r}")
        turns = _turns_of(conversation)
        candidates = [t for t in turns if role == "any" or t.role == role]
        for turn in candidates:
            if as_regex:
                if re.search(text, turn.content):
                    return
            elif text in turn.content:
                return
        raise AssertionError(
            f"Transcript does not contain {text!r} (role filter={role!r}, as_regex={as_regex}); "
            f"inspected {len(candidates)} of {len(turns)} turn(s)."
        )

    @keyword(name="Simulate User")
    @tier(3)
    @guarded_fanout()
    def simulate_user(
        self,
        conversation: ConversationHandle,
        persona: str,
        goal: str,
        max_turns: int = 5,
        simulator_adapter: str = "generic",
        simulator_model: str | None = None,
        cache_key: str | None = None,
        **kwargs: Any,
    ) -> ConversationTranscript:
        """Drives the conversation with an LLM user simulator until a stop condition (add-multi-turn-conversation-testing).

        [Tier 3 — Stochastic Fan-Out] — repeatedly (a) generates the next user
        message from a simulator LLM prompted with ``persona`` + ``goal`` + the
        rendered transcript so far, then (b) threads it via the SAME machinery as
        `Send Message`, until a stop condition. Returns the final
        ``ConversationTranscript``. Wraps ``@guarded_fanout`` — the library-level
        ``max_cost_usd`` / ``max_runtime_seconds`` budgets govern the whole loop
        (refusing entry or aborting mid-loop exactly as other Tier-3 fan-outs).

        Stop conditions (design D5): the simulator emits ``<<GOAL_ACHIEVED>>`` or
        ``<<GIVING_UP>>`` when the goal is met or unmeetable (sentinels are
        STRIPPED from recorded turns); ``max_turns`` is the hard cap. The
        transcript records ``stop_reason ∈ {"goal_achieved", "gave_up", "max_turns"}``
        so a test can assert HOW the conversation ended, not just that it did.

        | =Arguments= | =Description= |
        | ``conversation`` | The ``ConversationHandle`` to drive (may already carry scripted opening turns — the mixed style). |
        | ``persona`` | The simulated user's persona (e.g. ``impatient traveler``). |
        | ``goal`` | The goal the simulated user pursues (e.g. ``book the cheapest flight to Oslo``). |
        | ``max_turns`` | Hard cap on simulated user turns (default ``5``). |
        | ``simulator_adapter`` | Adapter driving the simulator LLM (default ``"generic"``), mirroring ``judge_adapter``. |
        | ``simulator_model`` | Model for the simulator adapter, mirroring ``judge_model``. |
        | ``cache_key`` | When set, each generated user message is cached on disk keyed by ``hash(cache_key, turn_index, transcript_so_far)``; re-runs replay identical user messages. Per-turn cache status (``hit``/``miss``/``disabled``) is recorded on the transcript. |

        Additional keyword arguments are forwarded to the AGENT's per-turn call
        (not the simulator). Simulator-call costs are added to the transcript's
        ``total_cost_usd`` alongside agent-turn costs.

        Raises ``ConversationClosedError`` on a closed handle. Raises the
        existing cost/runtime budget errors on breach.

        Example:
        | ${conv} =    `Start Conversation`    adapter=generic    provider=mock    model=mock/mock
        | ${t} =    `Simulate User`    ${conv}    persona=impatient traveler    goal=book the cheapest flight to Oslo    max_turns=3
        | Should Be Equal    ${t.stop_reason}    goal_achieved
        | ${score} =    `Judge.Get Score`    result=${t}    rubric=${CURDIR}/rubrics/goal-completion.md

        Notes:
        - Scripted (`Send Message` sequences) is the CO-EQUAL style; mix scripted opening turns then `Simulate User` on the same handle.
        - Tier-3 budget-guarded (2×turns LLM calls); ``cache_key`` re-runs cost ~half (simulator side cached).
        - Foundation for sibling `add-red-team-probes` (Crescendo-style multi-turn attack loops build on this surface).
        - Sibling keywords: `Send Message` (scripted), `Get Conversation Transcript`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        # add-multi-turn-conversation-testing codex-review MED fix: enforce the
        # closed-handle contract BEFORE constructing/calling the simulator. The
        # per-turn `execute_turn` guard only fires once a non-empty user message
        # is produced, so a simulator whose first message strips to empty (e.g. a
        # bare `<<GOAL_ACHIEVED>>`) would otherwise return a transcript — and
        # spend a simulator LLM call — on a closed conversation. Fail fast here
        # (a defensive per-iteration guard also lives in `run_simulation`).
        if conversation._closed:
            raise ConversationClosedError(
                f"conversation on adapter {conversation.adapter_name!r} is closed; "
                f"`Simulate User` cannot drive it (it already has "
                f"{conversation.agent_turn_count} agent turn(s))",
                fix_suggestion=(
                    "Start a fresh conversation with `Start Conversation` before simulating a user; "
                    "`Get Conversation Transcript` still works on a closed handle."
                ),
            )
        run_simulation(
            conversation,
            persona=persona,
            goal=goal,
            max_turns=max_turns,
            simulator_adapter=simulator_adapter,
            simulator_model=simulator_model,
            cache_key=cache_key,
            agent_call_kwargs=self._inject_provider(kwargs),
            simulator_kwargs=self._inject_provider({}),
        )
        return snapshot_transcript(conversation)
