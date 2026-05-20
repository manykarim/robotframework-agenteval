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

"""Tier ACL enforcement (Story 6.3 AC-6.3.5 + AC-6.3.6).

Two enforcement helpers landing here per architecture L1531 ("Determinism
handling + tier ACL → `_assertions/adapter.py` + `_kernel/tier.py`") + AC-6.3.5
rationale (LLM-side enforcement decoupled from AssertionEngine adapter):

- `enforce_tier1_no_llm()` — PRD FR30b: Tier-1 keywords may NOT invoke an LLM
  provider. Called from `LiteLLMAdapter.chat()` / `GenericAdapter.run()` entry
  points; walks the Python call stack to find the topmost
  `@keyword`-decorated frame and raises `TierViolationError` if its tier is 1.
- `enforce_validate_operator_disallowed()` — PRD FR43: companion gate for the
  `validate` AssertionEngine operator path. Raises `ValidateOperatorDisallowed`
  when `allow_validate_operator=False`.

Both are pure functions; no module-level state.
"""

from __future__ import annotations

import inspect
from typing import Any

from AgentEval._kernel.tier import find_tier_through_wrappers
from AgentEval.errors import TierViolationError, ValidateOperatorDisallowed


def enforce_tier1_no_llm() -> None:
    """Walk the call stack; raise `TierViolationError` if a Tier-1 keyword
    frame is calling into an LLM provider (PRD FR30b).

    Convention: every provider/adapter LLM-invocation entry point
    (`LiteLLMAdapter.chat`, `GenericAdapter.run`, future provider methods)
    calls this BEFORE any token-consuming action. The walker finds the
    topmost frame whose `__qualname__` resolves to a method on a class
    that's a `@keyword`-decorated AgentEval library; if that frame's
    method has `_agenteval_tier == 1`, raise.

    Behavior on missing context (no `@keyword`-decorated frame on the
    stack — e.g., pytest unit-test context): no-op (graceful degradation
    per Story 5.4 `feedback_dogfood_fake_green_precheck` / Listener-less
    context norm).
    """
    frames = inspect.stack()
    for frame_info in frames:
        frame = frame_info.frame
        self_obj = frame.f_locals.get("self")
        if self_obj is None:
            continue
        method_name = frame_info.function
        method = getattr(type(self_obj), method_name, None)
        if method is None:
            continue
        # Story 6.3 code-review HIGH-δ fix (Codex + Blind + Auditor 3-way):
        # `find_tier_through_wrappers` follows `__wrapped__` chains set by
        # `functools.wraps` / pythonlibcore decorators so the `@tier` metadata
        # is reachable regardless of decorator-order placement. Pre-edit only
        # checked direct `__func__` attrs — wrapped Tier-1 keywords evaded
        # FR30b entirely.
        target = getattr(method, "__func__", method)
        tier_value = find_tier_through_wrappers(target)
        # `robot_name` is set by `@keyword(name=...)` which is the OUTERMOST
        # decorator — read directly off the bound method.
        robot_name = getattr(target, "robot_name", None) or getattr(method, "robot_name", None)
        if tier_value is None or robot_name is None:
            continue
        # Story 6.3 code-review HIGH-δ semantic clarification (Blind HIGH-5 +
        # Auditor HIGH-9 3-way): `inspect.stack()` returns frames innermost-
        # first, so the loop matches the CLOSEST enclosing `@keyword` frame —
        # i.e., the keyword that is DIRECTLY calling into the provider. This
        # is the correct enforcement semantic: if a Tier-3 fan-out keyword
        # internally calls a Tier-2 keyword that calls chat(), the Tier-2
        # keyword is the LLM invoker + its tier governs the gate. The Tier-3
        # outer is already responsible for cost guardrails via @guarded_fanout.
        if tier_value == 1:
            raise TierViolationError(
                f"Tier-1 keyword {robot_name!r} attempted LLM invocation; "
                f"only Tier-2/3 keywords may call providers (PRD FR30b)."
            )
        # Tier-2/3 frame found — LLM invocation is allowed.
        return
    # No `@keyword`-decorated frame on the stack: pytest / Listener-less
    # context. Graceful no-op (consistent with `feedback_dogfood_fake_green_precheck`).
    return


def enforce_validate_operator_disallowed(
    allow_validate_operator: bool,
    keyword_name: str,
) -> None:
    """Raise `ValidateOperatorDisallowed` per PRD FR43 when the `validate`
    AssertionEngine operator is used without explicit opt-in.

    Args:
        allow_validate_operator: Library-level kwarg (default `False` per
            FR42). When `True`, the gate is open.
        keyword_name: RF name of the calling keyword — included in the
            error message per FR56-style template (D-8 resolution).

    Raises:
        ValidateOperatorDisallowed: when `allow_validate_operator is False`.
    """
    if allow_validate_operator:
        return
    raise ValidateOperatorDisallowed(_build_validate_disallowed_message(keyword_name))


def _build_validate_disallowed_message(keyword_name: str) -> str:
    """FR56-style error message (D-8 resolution — sibling format to PollingDisallowedError).

    Contains: (a) keyword name, (b) RF test file path + line number when
    inspectable, (c) verbatim opt-in remediation snippet, (d) ADR link.
    """
    path_line = _extract_caller_path_line()
    location = f" at {path_line}" if path_line else ""
    return (
        f"ValidateOperatorDisallowed: keyword {keyword_name!r} used the `validate` "
        f"AssertionEngine operator{location} but `allow_validate_operator=False` "
        f"(the default per PRD FR42 — the `validate` operator uses `eval()` which "
        f"executes arbitrary expressions). To opt in:\n"
        f"    Library    AgentEval    allow_validate_operator=True\n"
        f"See ADR-019 (AssertionEngine Adoption + Polling Ban + Validate Disabled "
        f"by Default) for the rationale."
    )


def _extract_caller_path_line() -> str | None:
    """Walk the call stack for the topmost `.robot`-originated frame's path:line.

    Used by both `PollingDisallowedError` + `ValidateOperatorDisallowed` message
    builders (FR56 verbatim "RF test file path + line number from call stack").
    Returns `None` when no `.robot` frame is detectable (pytest context).

    Story 6.3 code-review HIGH-ε fix (Codex + Edge + Auditor 3-way): pre-edit
    matched `"/robot/" in filename` which false-positives on any path containing
    `/robot/` (e.g., `~/.cache/robot/...`, `.venv/lib/.../site-packages/robot/...`).
    Now matches `.endswith(".robot")` only — the FR56 verbatim contract is "RF
    test file path" which is by definition a `.robot` source file.
    """
    for frame_info in inspect.stack():
        if frame_info.filename.endswith(".robot"):
            return f"{frame_info.filename}:{frame_info.lineno}"
    return None


__all__ = ["enforce_tier1_no_llm", "enforce_validate_operator_disallowed"]


# Re-export for caller convenience; the helper is symmetric with the AssertionEngine
# adapter's polling-ban message builder.
def build_polling_disallowed_message(
    keyword_name: str,
    keyword_args: dict[str, Any] | None = None,
) -> str:
    """FR56 verbatim error message for `PollingDisallowedError` (Story 6.3 AC-6.3.5).

    Args:
        keyword_name: RF name of the Tier-2/3 keyword.
        keyword_args: Original kwargs to the keyword (for the remediation snippet).

    Returns:
        Multi-line message string per FR56: (a) keyword name + (b) RF test file
        path + line number + (c) verbatim `Stat.Run N Times ...` remediation
        snippet + (d) ADR link.
    """
    path_line = _extract_caller_path_line()
    location = f" at {path_line}" if path_line else ""
    # Story 6.3 code-review HIGH-8 fix (Blind 1-way): render `keyword_args` as
    # RF-valid list-of-`key=value` syntax (NOT Python dict literal repr). A
    # `{"prompt": "Hi"}` dict was previously rendered as `{'prompt': 'Hi'}`
    # which RF parses as a single string. The list-of-strings form is RF's
    # canonical named-arg syntax + works as copy-paste into `.robot` tests.
    args_repr = "[" + ", ".join(f"{k}={v}" for k, v in keyword_args.items()) + "]" if keyword_args else "[]"
    return (
        f"PollingDisallowedError: keyword {keyword_name!r} received a `polling=` "
        f"argument{location}, but polling is not allowed on Tier-2/Tier-3 "
        f"keywords (non-deterministic by construction per PRD FR28). "
        f"Use the statistical primitive instead:\n"
        f"    ${{runs}}=    Stat.Run N Times    n=10    keyword={keyword_name}    "
        f"keyword_args={args_repr}\n"
        f"See ADR-019 (AssertionEngine Adoption + Polling Ban + Validate Disabled "
        f"by Default) for the rationale."
    )
