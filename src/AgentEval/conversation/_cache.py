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

"""`Simulate User` disk cache (add-multi-turn-conversation-testing D5 / Task 7.3).

`cache_key`-repeatable simulations (idea stolen from LangWatch Scenario,
adapted): each simulator-generated user message is cached on disk keyed by
``hash(cache_key, turn_index, transcript_so_far)`` under
``${OUTPUT_DIR}/agenteval/simulation-cache/``. Re-runs replay identical user
messages, isolating agent-side variance.

Because the key includes the transcript-so-far hash, a changed agent reply
mid-conversation naturally invalidates subsequent cached turns (the hash
diverges → cache miss → live regeneration). Per-turn hit/miss/disabled status
is surfaced on the transcript per the honesty philosophy.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from AgentEval.types import ConversationTurn

__all__ = ["SimulationCache"]

_log = logging.getLogger("AgentEval.conversation.cache")


def _resolve_output_dir() -> Path:
    """Resolve ``${OUTPUT_DIR}`` from RF context; fall back to CWD outside RF."""
    try:
        from robot.libraries.BuiltIn import BuiltIn

        value = BuiltIn().get_variable_value("${OUTPUT_DIR}")
        if value:
            return Path(str(value))
    except Exception:
        # Not running under RF (direct Python / unit tests) — CWD fallback.
        pass
    return Path.cwd()


class SimulationCache:
    """Disk cache for simulator-generated user messages, keyed per turn.

    A ``cache_key=None`` cache is disabled: every lookup is a miss with status
    ``"disabled"`` and nothing is written. When enabled, `lookup` returns the
    cached message (status ``"hit"``) or ``None`` (status ``"miss"``); the
    caller `store`s the freshly-generated message on a miss.
    """

    def __init__(self, cache_key: str | None, *, base_dir: Path | None = None) -> None:
        self.cache_key = cache_key
        self.enabled = bool(cache_key)
        if self.enabled:
            root = base_dir if base_dir is not None else _resolve_output_dir()
            self._dir: Path | None = root / "agenteval" / "simulation-cache"
        else:
            self._dir = None

    def _hash(self, turn_index: int, prior_turns: tuple[ConversationTurn, ...] | list[ConversationTurn]) -> str:
        transcript_so_far = "\n".join(f"{t.role}:{t.content}" for t in prior_turns)
        payload = f"{self.cache_key}\x00{turn_index}\x00{transcript_so_far}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _path_for(self, turn_index: int, prior_turns: tuple[ConversationTurn, ...] | list[ConversationTurn]) -> Path:
        assert self._dir is not None
        return self._dir / f"{self._hash(turn_index, prior_turns)}.txt"

    def lookup(
        self, turn_index: int, prior_turns: tuple[ConversationTurn, ...] | list[ConversationTurn]
    ) -> tuple[str | None, str]:
        """Return ``(cached_message_or_None, status)`` where status ∈ hit/miss/disabled."""
        if not self.enabled:
            return None, "disabled"
        path = self._path_for(turn_index, prior_turns)
        if path.exists():
            try:
                return path.read_text(encoding="utf-8"), "hit"
            except OSError as exc:  # pragma: no cover - defensive
                _log.warning("simulation-cache read failed for %s: %s; treating as miss", path, exc)
                return None, "miss"
        return None, "miss"

    def store(
        self, turn_index: int, prior_turns: tuple[ConversationTurn, ...] | list[ConversationTurn], message: str
    ) -> None:
        """Persist a freshly-generated user message for future replay (no-op when disabled)."""
        if not self.enabled or self._dir is None:
            return
        path = self._path_for(turn_index, prior_turns)
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            path.write_text(message, encoding="utf-8")
        except OSError as exc:  # pragma: no cover - defensive
            _log.warning("simulation-cache write failed for %s: %s; simulation stays live", path, exc)
