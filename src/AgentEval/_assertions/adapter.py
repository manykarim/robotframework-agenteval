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

"""AssertionEngine adapter — polling-ban + validate-gate + dispatch (Story 6.3 AC-6.3.5).

Per architecture L138/L266/L304/L647 (agentguard `_assertions/adapter.py:71-120`
pattern adapted via ADR-001 catalog row L87 → ADR-019 minted in Story 6.3):
the `assert_value()` free function is the canonical assertion gate for all
`Should *` keywords in agenteval. It runs three gates fail-fast:

1. **POLLING BAN** per PRD FR28: `tier >= 2 and polling is not None` →
   `PollingDisallowedError` with FR56 verbatim message format.
2. **VALIDATE GATE** per PRD FR43: `validate=True and not allow_validate_operator`
   → `ValidateOperatorDisallowed` with FR56-style message (D-8 resolution).
3. **DISPATCH** via `robotframework-assertion-engine>=4.0,<5.0` — invokes
   `assertionengine.verify_assertion(...)` for the actual comparison.

Tier-1 LLM-invocation ban (FR30b) is enforced ELSEWHERE — at provider/adapter
callsites that import `_kernel/tier_acl.enforce_tier1_no_llm()`. This split
keeps LLM-side enforcement decoupled from AssertionEngine gating.
"""

from __future__ import annotations

from typing import Any

from AgentEval._kernel.tier_acl import (
    build_polling_disallowed_message,
    enforce_validate_operator_disallowed,
)
from AgentEval.errors import PollingDisallowedError

__all__ = ["assert_value"]


def assert_value(
    actual: Any,
    operator: str | None,
    expected: Any,
    *,
    keyword_name: str,
    tier: int,
    polling: float | None = None,
    validate: bool = False,
    allow_validate_operator: bool = False,
    message: str | None = None,
    keyword_args: dict[str, Any] | None = None,
) -> None:
    """AssertionEngine-style gating + dispatch (Story 6.3 AC-6.3.5).

    Args:
        actual: Observed value.
        operator: AssertionEngine operator string (e.g., `"=="`, `"contains"`,
            `">="`, `"matches"`, `"validate"`). `None` skips dispatch (gates
            still run — useful for keywords that do their own matching but
            still want the polling-ban / validate-gate enforcement).
        expected: Expected value (or expression for `validate`).
        keyword_name: RF name of the calling keyword (verbatim for FR56 message
            format).
        tier: Tier of the calling keyword (1, 2, or 3).
        polling: Optional polling argument from the operator-facing keyword.
            When `tier >= 2 and polling is not None`, raises FR28.
        validate: `True` when the AssertionEngine `validate` operator is in use.
            When `True and not allow_validate_operator`, raises FR43.
        allow_validate_operator: Library-level opt-in (default `False` per FR42).
        message: Optional message string passed through to AssertionEngine /
            `AssertionError`.

    Raises:
        PollingDisallowedError: per FR28 trigger (D-2 amendment — `polling=`
            kwarg, NOT `validate` operator).
        ValidateOperatorDisallowed: per FR43 trigger.
        AssertionError: when AssertionEngine dispatch reports a mismatch.
    """
    # Gate 1: POLLING BAN (FR28) — Tier-2/3 keywords MUST NOT receive polling=.
    # Story 6.3 code-review LOW-10 fix (Codex + Blind 2-way): thread the
    # caller's original `keyword_args` through to the FR56 remediation snippet
    # so the operator-facing copy-paste recovery path includes actual args
    # instead of a misleading `[]`.
    if tier >= 2 and polling is not None:
        raise PollingDisallowedError(
            build_polling_disallowed_message(keyword_name=keyword_name, keyword_args=keyword_args)
        )

    # Gate 2: VALIDATE GATE (FR43) — validate operator requires opt-in.
    if validate:
        enforce_validate_operator_disallowed(allow_validate_operator, keyword_name)

    # Gate 3: DISPATCH to AssertionEngine for the actual comparison.
    if operator is None:
        # Gating-only mode: caller does its own matching. No dispatch.
        return
    try:
        from assertionengine import AssertionOperator, verify_assertion
    except ImportError as exc:  # pragma: no cover — dep is pinned in pyproject
        raise RuntimeError(
            "robotframework-assertion-engine not available; ensure it's installed "
            "(pinned in pyproject.toml as >=4.0,<5.0 per Story 6.3 / ADR-019)."
        ) from exc

    # Resolve the AssertionOperator enum from its string-value form (`==`, `>=`, etc.).
    try:
        op_enum = AssertionOperator(operator) if isinstance(operator, str) else operator
    except (KeyError, ValueError) as exc:
        raise ValueError(
            f"invalid AssertionEngine operator {operator!r}; see assertionengine.AssertionOperator for valid values."
        ) from exc

    # `verify_assertion`'s `message` param is typed as `str` upstream but
    # `None` is the documented "no extra message" sentinel; pass empty string
    # when message is None to satisfy the type checker.
    verify_assertion(actual, op_enum, expected, message=message or "")
