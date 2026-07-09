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

"""Shared transcript renderer (add-multi-turn-conversation-testing Task 2.5).

ONE role-tagged text rendering shared by three consumers (design Open
Question 3 resolution):

- the `replayed_history` continuation preamble (`render_replay_prompt`),
- the judge-over-transcript prompt (`render_transcript_text`, D6),
- the `Simulate User` simulator prompt (D5).

Keeping a single renderer means the text an agent re-reads under replay, the
text a judge scores, and the text a simulator conditions on are byte-consistent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from AgentEval.types import ConversationTurn

__all__ = ["render_transcript_text", "render_replay_prompt"]

_ROLE_LABELS = {"user": "User", "agent": "Assistant"}


def render_transcript_text(turns: tuple[ConversationTurn, ...] | list[ConversationTurn]) -> str:
    """Render turns as a role-tagged plain-text transcript.

    Each turn becomes ``"<Role>: <content>"`` on its own block, in
    chronological order. Empty content renders as ``"(no content)"`` so a
    turn is never silently blank.
    """
    lines: list[str] = []
    for turn in turns:
        label = _ROLE_LABELS.get(turn.role, turn.role.capitalize())
        content = turn.content if turn.content else "(no content)"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def render_replay_prompt(prior_turns: tuple[ConversationTurn, ...] | list[ConversationTurn], new_message: str) -> str:
    """Compose the `replayed_history` single-`run()` prompt.

    A delimited preamble of prior turns followed by the new user message. The
    agent re-reads the history as text (honestly weaker than a native session —
    no persistent tool/workspace state across turns; the `continuation` field
    records this).
    """
    preamble = render_transcript_text(prior_turns)
    return (
        "[Conversation so far — you are continuing this multi-turn conversation. "
        "Prior turns are shown for context.]\n"
        f"{preamble}\n\n"
        "[Current user message — respond to this]\n"
        f"User: {new_message}"
    )
