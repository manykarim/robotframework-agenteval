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

"""Tier annotation mechanism per architecture L620 + Decision-1.

Every public keyword in `src/AgentEval/*/library.py` is annotated with
`@tier(N)` where N is 1, 2, or 3:

- **Tier 1 — Deterministic.** Static-inspection, ACL-gated determinism is
  enforced by the conformance suite; e.g., `Skill Get Activation Decision`.
- **Tier 2 — Stochastic Single-Shot.** Single LLM round-trip per keyword
  invocation; e.g., `Agent Run`.
- **Tier 3 — Stochastic Fan-Out.** Multi-trial fan-out via the
  `@guarded_fanout` decorator (ADR-015); e.g., `Stat Run N Times`.

The `_agenteval_tier` attribute (single-underscore convention per architecture
L620, NOT `__agenteval_tier__` dunder) is attached to the decorated function.
Story 1b.6's convention enforcer asserts every `@keyword`-decorated method has
a `@tier()` annotation; missing annotation raises `KeywordTierMissingError`
at library import.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, TypeVar

F = TypeVar("F", bound=Callable[..., object])

__all__ = ["tier", "get_keyword_tier", "tier_badge"]


_TIER_BADGES: dict[int, str] = {
    1: "[Tier 1 — Deterministic]",
    2: "[Tier 2 — Stochastic Single-Shot]",
    3: "[Tier 3 — Stochastic Fan-Out]",
}


def tier(n: Literal[1, 2, 3]) -> Callable[[F], F]:
    """Tier-annotation decorator factory.

    Args:
        n: Tier level — 1 (deterministic), 2 (stochastic single-shot),
            or 3 (stochastic fan-out).

    Returns:
        A decorator that attaches `_agenteval_tier = n` to the wrapped
        function and returns the function unchanged.

    Raises:
        ValueError: If `n` is not 1, 2, or 3. Raised at decoration time.
    """
    if n not in (1, 2, 3):
        raise ValueError("tier must be 1, 2, or 3")

    def _decorate(func: F) -> F:
        func._agenteval_tier = n  # type: ignore[attr-defined]
        return func

    return _decorate


def get_keyword_tier(func: Callable[..., object]) -> int | None:
    """Return the tier of a `@tier`-annotated function, or None if unannotated."""
    return getattr(func, "_agenteval_tier", None)


def tier_badge(tier_level: int) -> str:
    """Return the libdoc badge text for a tier level.

    Args:
        tier_level: 1, 2, or 3.

    Returns:
        Exact badge string (one of "[Tier 1 — Deterministic]",
        "[Tier 2 — Stochastic Single-Shot]", "[Tier 3 — Stochastic Fan-Out]").

    Raises:
        ValueError: If `tier_level` is not 1, 2, or 3.
    """
    try:
        return _TIER_BADGES[tier_level]
    except KeyError as exc:
        raise ValueError("tier must be 1, 2, or 3") from exc
