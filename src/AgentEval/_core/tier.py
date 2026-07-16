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

"""Tier marker for the four surface libraries.

Every public keyword declares its mode with ``@tier(1|2|3)``:

- Tier 1 — deterministic, no model.
- Tier 2 — one LLM round-trip (the judge).
- Tier 3 — a real coding agent.

The tier is just an attribute stamped on the function; ``Get Keyword Tier``
reads it back. The deterministic guard replaces the old stack-walking ACL:
open a ``deterministic_scope()`` around Tier-1 work and any adapter call inside
it raises loudly. It is a single context-var read, not an ``inspect.stack()``
walk.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal, TypeVar

from AgentEval._core.errors import TierViolationError

F = TypeVar("F", bound=Callable[..., object])

__all__ = [
    "tier",
    "get_keyword_tier",
    "find_tier_through_wrappers",
    "tier_badge",
    "deterministic_scope",
    "enforce_no_model",
]


_TIER_BADGES: dict[int, str] = {
    1: "[Tier 1 - Deterministic]",
    2: "[Tier 2 - LLM Judge]",
    3: "[Tier 3 - Coding Agent]",
}


def tier(n: Literal[1, 2, 3]) -> Callable[[F], F]:
    """Stamp ``_agenteval_tier = n`` on a keyword and return it unchanged.

    Rejects ``bool`` explicitly: ``True == 1`` in Python, so ``@tier(True)``
    would silently read as Tier-1 without this guard.
    """
    if isinstance(n, bool) or n not in (1, 2, 3):
        raise ValueError("tier must be 1, 2, or 3")

    def _decorate(func: F) -> F:
        func._agenteval_tier = n  # type: ignore[attr-defined]
        return func

    return _decorate


def get_keyword_tier(func: Callable[..., object]) -> int | None:
    """Return the tier of a ``@tier``-annotated function, or None if unmarked."""
    value = getattr(func, "_agenteval_tier", None)
    return value if isinstance(value, int) else None


def find_tier_through_wrappers(func: object) -> int | None:
    """Walk the ``__wrapped__`` chain looking for a tier marker.

    A ``@tier`` can sit either side of a ``functools.wraps`` decorator, so we
    check every level from outer to inner and return the first tier found.
    """
    seen: set[int] = set()
    current: object = func
    for _ in range(20):
        if id(current) in seen:
            return None
        seen.add(id(current))
        value = getattr(current, "_agenteval_tier", None)
        if isinstance(value, int):
            return value
        wrapped = getattr(current, "__wrapped__", None)
        if wrapped is None or wrapped is current:
            return None
        current = wrapped
    return None


def tier_badge(tier_level: int) -> str:
    """Return the libdoc badge text for a tier level."""
    try:
        return _TIER_BADGES[tier_level]
    except KeyError as exc:
        raise ValueError("tier must be 1, 2, or 3") from exc


# --------------------------------------------------------------------------- #
# Deterministic guard - the cheap replacement for the stack-walking ACL.       #
# --------------------------------------------------------------------------- #

_DETERMINISTIC: ContextVar[bool] = ContextVar("agenteval_deterministic", default=False)


@contextmanager
def deterministic_scope() -> Iterator[None]:
    """Mark the enclosed block as Tier-1: any model/agent call inside raises."""
    token = _DETERMINISTIC.set(True)
    try:
        yield
    finally:
        _DETERMINISTIC.reset(token)


def enforce_no_model() -> None:
    """Raise ``TierViolationError`` when called inside a ``deterministic_scope``.

    Adapters and the judge call this before reaching a provider so a Tier-1
    keyword can never smuggle in a stochastic call.
    """
    if _DETERMINISTIC.get():
        raise TierViolationError(
            "a deterministic (Tier-1) keyword tried to call a model or agent; Tier-1 keywords must stay model-free"
        )
