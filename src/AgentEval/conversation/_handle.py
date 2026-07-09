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

"""`ConversationHandle` — the test-owned, mutable conversation object (design D2).

`Start Conversation` returns one; the `.robot` test stores it in a variable and
passes it to every subsequent keyword — the same test-owns-the-handle pattern
Story 3.1 ratified for `MCPServerHandle` (no hidden library-managed "current
conversation" global, which breaks under parallel suites). Handles are NOT
thread-safe; sequential use only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from AgentEval.types import ConversationTurn

__all__ = ["ConversationHandle"]


class ConversationHandle:
    """Mutable, test-owned handle carrying one conversation's live state.

    Carries: adapter name + the constructed adapter instance (reused across
    turns — session affinity requires it, unlike `Send Prompt`'s per-call
    construction), the frozen run kwargs, the growing turn list, the native
    session reference when one exists, and a closed flag. `End Conversation`
    marks it closed; sends after close raise `ConversationClosedError`.
    """

    def __init__(
        self,
        *,
        adapter_name: str,
        adapter_instance: Any,
        run_kwargs: dict[str, Any],
        supports_native: bool,
    ) -> None:
        self.adapter_name: str = adapter_name
        self._adapter: Any = adapter_instance
        self._run_kwargs: dict[str, Any] = dict(run_kwargs)
        self._turns: list[ConversationTurn] = []
        self._session_ref: Any = None
        self._closed: bool = False
        self.supports_native: bool = supports_native
        # Costs from `Simulate User` simulator LLM calls (design D5): added to
        # the transcript's `total_cost_usd` alongside agent-turn costs.
        self._simulator_cost_usd: float = 0.0
        # Set by `Simulate User`; None for scripted conversations.
        self._stop_reason: str | None = None

    @property
    def turns(self) -> tuple[ConversationTurn, ...]:
        """Immutable view of the turns recorded so far (user + agent)."""
        return tuple(self._turns)

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def agent_turn_count(self) -> int:
        return sum(1 for t in self._turns if t.role == "agent")

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"ConversationHandle(adapter={self.adapter_name!r}, "
            f"turns={len(self._turns)}, agent_turns={self.agent_turn_count}, "
            f"native={self.supports_native}, closed={self._closed})"
        )
