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

"""In-process PreToolUse-style tool gate over pydantic-ai tool-approval.

The Claude Code hook runtime this library normally tests (``Hook.Fire Hook
Event``) executes *external command scripts* declared in ``settings.json``. This
module adds a **PARTIAL, in-process** complement: it drives a prompt through an
in-process pydantic-ai agent whose tool calls must be *approved*, applies an
allow/deny policy at the approval point, and records each decision. That is the
programmatic analog of a PreToolUse allow/deny hook - the one hook decision that
pydantic-ai can surface *in-process*, with no subprocess and no LLM stub in the
production path.

Why tool-approval (and not Guardrails): pydantic-ai 2.12 ships first-class
per-tool-call approval. A tool marked ``requires_approval`` (or any toolset
wrapped in ``ApprovalRequiredToolset``) raises ``ApprovalRequired`` on first
call; the run pauses and returns a ``DeferredToolRequests`` whose ``approvals``
list carries the pending ``ToolCallPart``s. The caller resolves each with a
``DeferredToolResults`` (``True`` -> execute, ``ToolDenied`` -> block) and
resumes. That pause/resolve seam is exactly a PreToolUse gate, and every
allow/deny is observable there. Harness ``Guardrails`` (InputGuard/OutputGuard)
gate whole-prompt input/whole-run output, not individual tool calls, so they are
a coarser fit for PreToolUse and are left as a documented alternative.

CEILING (honest): this is a PROXY for a generic in-process agent's tool calls,
NOT the Claude Code hook runtime. It covers PreToolUse-style allow/deny of tool
CALLS only - no ``settings.json`` command scripts, no PostToolUse / Stop /
SessionStart events, no stdout-JSON hook protocol, and no ``allowed-tools``
enforcement. For real command-hook scripts use ``Hook.Fire Hook Event``.

pydantic-ai ships behind the optional ``[agent]`` extra; the import is lazy so
importing HooksLibrary never pulls it in.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from AgentEval._core.adapter import run_async
from AgentEval._core.errors import HookExecutionError, MissingExtraError

__all__ = [
    "GUARD_CEILING",
    "PolicyFunc",
    "ToolDecision",
    "ToolPolicyReport",
    "run_tool_policy",
]

# A policy maps ``(tool_name, args)`` -> allow. It may return a plain bool, or a
# ``(allow, reason)`` tuple to attach a human-readable reason to the decision
# (the reason is surfaced to the model on a denial and stored on the record).
PolicyFunc = Callable[[str, dict[str, Any]], "bool | tuple[bool, str]"]

GUARD_CEILING = (
    "PARTIAL PROXY: an in-process PreToolUse-style allow/deny gate over pydantic-ai "
    "tool-approval. Measures allow/deny decisions for the tool CALLS a generic in-process "
    "agent makes; it is NOT the Claude Code external-command hook runtime (no settings.json "
    "scripts, no PostToolUse/Stop/SessionStart events, no stdout-JSON protocol, no "
    "allowed-tools enforcement). For real command-hook scripts use `Hook.Fire Hook Event`."
)

_MISSING_AGENT = (
    "Hook.Get Tool Decisions needs pydantic-ai, which ships with the [agent] extra. "
    "Install it with: pip install 'robotframework-agenteval[agent]'"
)


@dataclass(frozen=True)
class ToolDecision:
    """One PreToolUse-style allow/deny decision over a single tool call.

    ``decision`` is ``"allow"`` or ``"deny"``. ``sequence_index`` orders the
    decisions across the whole run (0-based, in the order the model requested the
    calls). ``reason`` is the policy's rationale (empty for a bare-bool allow).
    """

    tool_name: str
    args: dict[str, Any]
    decision: str
    reason: str
    sequence_index: int


@dataclass(frozen=True)
class ToolPolicyReport:
    """Every allow/deny decision from one gated agent run, plus the final text.

    ``rounds`` counts the approval pause/resume cycles the run needed (one per
    batch of pending approvals). ``denied`` / ``allowed`` project the tool names
    for quick assertions; ``decisions_for`` returns every decision for a tool.
    """

    decisions: tuple[ToolDecision, ...]
    response_text: str
    rounds: int

    @property
    def denied(self) -> tuple[str, ...]:
        """Tool names that were denied, in decision order (may repeat)."""
        return tuple(d.tool_name for d in self.decisions if d.decision == "deny")

    @property
    def allowed(self) -> tuple[str, ...]:
        """Tool names that were allowed, in decision order (may repeat)."""
        return tuple(d.tool_name for d in self.decisions if d.decision == "allow")

    def decisions_for(self, tool_name: str) -> tuple[ToolDecision, ...]:
        """Every decision recorded for ``tool_name`` (case-sensitive), in order."""
        return tuple(d for d in self.decisions if d.tool_name == tool_name)


def _import_pydantic_ai() -> tuple[Any, Any, Any, Any, Any]:
    """Import the tool-approval surface lazily, or raise a clear missing-extra error."""
    try:
        from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, ToolDenied
        from pydantic_ai.toolsets import ApprovalRequiredToolset
    except ImportError as exc:
        raise MissingExtraError(_MISSING_AGENT, extra="agent") from exc
    return Agent, DeferredToolRequests, DeferredToolResults, ToolDenied, ApprovalRequiredToolset


def _coerce_args(raw: Any) -> dict[str, Any]:
    """Normalize a ``ToolCallPart.args`` (dict or JSON string) into a plain dict."""
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"_raw": raw}
        return parsed if isinstance(parsed, dict) else {"_value": parsed}
    return {}


def _normalize_policy_result(result: Any, default_deny_reason: str) -> tuple[bool, str]:
    """Coerce a policy return (bool or ``(allow, reason)``) into ``(allow, reason)``."""
    if isinstance(result, tuple):
        allow = bool(result[0])
        reason = str(result[1]) if len(result) > 1 and result[1] else ""
    else:
        allow, reason = bool(result), ""
    if not allow and not reason:
        reason = default_deny_reason
    return allow, reason


def run_tool_policy(
    model: Any,
    prompt: str,
    *,
    toolset: Any,
    policy: PolicyFunc | None = None,
    gated_tools: set[str] | None = None,
    default_deny_reason: str = "denied by tool policy",
    max_rounds: int = 12,
    retries: int = 3,
) -> ToolPolicyReport:
    """Drive ``prompt`` through a gated agent and record every allow/deny decision.

    ``model`` is a pydantic-ai model object (a live ``OpenAIChatModel`` in the
    keyword path, a deterministic ``FunctionModel`` in unit tests). ``toolset``
    is any pydantic-ai toolset (e.g. an ``MCP.As Agent Toolset`` result). Every
    call to a *gated* tool must be approved: ``policy(tool_name, args)`` decides
    (``None`` allows all while still recording each call). ``gated_tools``
    restricts which tools require approval - ``None`` gates every tool, so every
    call is observed.

    Returns a ``ToolPolicyReport``. Raises ``MissingExtraError`` naming
    ``[agent]`` if pydantic-ai is absent, and ``HookExecutionError`` if the
    approval loop does not converge within ``max_rounds`` (a runaway agent).
    """
    (
        agent_cls,
        deferred_requests_cls,
        deferred_results_cls,
        tool_denied_cls,
        approval_toolset_cls,
    ) = _import_pydantic_ai()

    if gated_tools is None:
        approval_required_func = lambda ctx, tool_def, args: True  # noqa: E731 - gate every tool
    else:
        gated = set(gated_tools)
        approval_required_func = lambda ctx, tool_def, args: tool_def.name in gated  # noqa: E731

    guarded = approval_toolset_cls(toolset, approval_required_func=approval_required_func)
    agent = agent_cls(model, toolsets=[guarded], output_type=[str, deferred_requests_cls], retries=retries)

    async def _drive() -> ToolPolicyReport:
        decisions: list[ToolDecision] = []
        result = await agent.run(prompt)
        rounds = 0
        while isinstance(result.output, deferred_requests_cls) and rounds < max_rounds:
            rounds += 1
            approvals: dict[str, Any] = {}
            for call in result.output.approvals:
                args = _coerce_args(getattr(call, "args", None))
                if policy is None:
                    allow, reason = True, ""
                else:
                    allow, reason = _normalize_policy_result(policy(call.tool_name, args), default_deny_reason)
                decisions.append(
                    ToolDecision(
                        tool_name=str(call.tool_name),
                        args=args,
                        decision="allow" if allow else "deny",
                        reason=reason,
                        sequence_index=len(decisions),
                    )
                )
                approvals[call.tool_call_id] = True if allow else tool_denied_cls(message=reason)
            result = await agent.run(
                message_history=result.all_messages(),
                deferred_tool_results=deferred_results_cls(approvals=approvals),
            )

        if isinstance(result.output, deferred_requests_cls):
            raise HookExecutionError(
                f"tool-policy approval loop did not converge after {max_rounds} rounds "
                f"({len(decisions)} decision(s) recorded); the agent kept requesting tool "
                "calls. Raise max_rounds if this is expected, or tighten the prompt."
            )

        return ToolPolicyReport(
            decisions=tuple(decisions),
            response_text=str(result.output or ""),
            rounds=rounds,
        )

    return run_async(_drive())
