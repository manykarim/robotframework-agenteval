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

"""`ConversationState` + the optional duck-typed `run_turn()` adapter contract.

add-multi-turn-conversation-testing design D4. Continuation is capability-probed,
NOT baked into the `CodingAgentAdapter` Protocol (FR12 forbids growing the
required Protocol surface — the Protocol still has a single `run()`).

## Optional `run_turn()` contract (duck-typed)

An adapter MAY implement::

    def run_turn(self, prompt: str, *, conversation_state: ConversationState, **kwargs) -> AgentRunResult: ...

Detection at `Start Conversation` time is
``callable(getattr(adapter, "run_turn", None))`` — the same
duck-typed-optional pattern as the `_assert_binary_version` overrides. When
present, turns after the first thread NATIVELY (`continuation="native_session"`);
when absent, the conversation layer composes prior turns into a delimited
history preamble passed to the ordinary `run()` (`continuation="replayed_history"`).

The adapter reads `conversation_state.prior_turns` (turns BEFORE the current
`prompt`) and MAY read/write the adapter-opaque `conversation_state.session_ref`
slot across turns (e.g., the Claude Code CLI adapter stashes the stream-json
session id there for `--resume`). An adapter that discovers it cannot honor
native continuation for a given turn (e.g., the session id was never captured)
SHOULD set `conversation_state.continuation = "replayed_history"` so the honest
degradation surfaces in the transcript rather than the layer silently lying.

## Deferred follow-ups (carry-over catalog markers)

- **`DF-MTC-S1`** (C105): native `run_turn` for the codex / copilot / opencode /
  openai-agents adapters. Phase-1 natives are `generic` (message history) +
  `claude-code-cli` (`--resume`); every OTHER adapter degrades honestly to
  `replayed_history` today (never hard-fails). Native continuation for each
  (codex/opencode `run --session`, copilot resume flag, openai-agents Sessions)
  is a documented follow-up, NOT silent scope creep.
- **`DF-MTC-S2`** (C106): a declarative `simulate_user:` block in scenario YAML
  (deferred per design D8 — simulation belongs in `.robot` where budget +
  persona iteration are visible).
- **`DF-MTC-S3`** (C107): scenario-level `require_native` for `turns:` evals
  (deferred per design D8 — Phase-1 relies on the per-turn `continuation`
  honesty field to carry the degradation signal).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from AgentEval.types import ConversationTurn

__all__ = ["ConversationState"]


@dataclass
class ConversationState:
    """Mutable per-turn threading context handed to an adapter's `run_turn()`.

    Intentionally MUTABLE (unlike the frozen shared types) so an adapter can
    write back the session reference + the actual continuation mode it used:

    - `prior_turns`: ordered tuple of the conversation's turns BEFORE the
      current `prompt` (user + agent). The adapter rebuilds message history
      / decides resume-vs-replay from this.
    - `session_ref`: adapter-opaque slot the adapter reads on entry + writes
      on exit (e.g., a native CLI session id). The conversation layer persists
      whatever the adapter leaves here onto the handle for the next turn.
    - `continuation`: the adapter MAY set the ACTUAL mode it used
      (`"native_session"` | `"replayed_history"`). Left `None` means "native
      as advertised"; the layer defaults a non-first native turn to
      `"native_session"`. The first agent turn is always reported `"initial"`
      by the layer regardless of this field.
    """

    prior_turns: tuple[ConversationTurn, ...] = field(default_factory=tuple)
    session_ref: Any = None
    continuation: str | None = None
