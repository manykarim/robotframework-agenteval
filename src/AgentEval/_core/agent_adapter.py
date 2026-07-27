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

"""The in-process agent adapter - a coding-agent PROXY on only an LLM key + base_url.

Runs a prompt through an in-process pydantic-ai agent loop against any
OpenAI-compatible endpoint. It executes tools (so ``ToolCallTrace.result`` is
populated, unlike the one-shot ``GenericAdapter``) and - given deferred skill
capabilities - lets the model *activate* a skill via the framework
``load_capability`` tool, which is captured as a normal tool call. Activated
skills are therefore derivable from ``AgentRunResult.tool_calls``.

This is a *proxy* for a competent generic agent, NOT a specific coding agent's
runtime - ``validation_ceiling`` says so. It lives behind the ``[agent]`` extra;
pydantic-ai is imported lazily with a clear ``MissingExtraError``.

The caller may raise the agent loop's usage/request limit (``request_limit`` /
``usage_limits``) and inject run-level ``instructions`` (e.g. an MCP server's own
guidance, read from ``session.instructions``). Both default to today's behavior
when unset; the adapter never auto-reads a server's instructions.
"""

from __future__ import annotations

import json
from typing import Any

from AgentEval._core.adapter import resolve_config, run_async
from AgentEval._core.errors import MissingExtraError
from AgentEval._core.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage

__all__ = ["InProcessAgentAdapter"]

_CEILING = (
    "PROXY: measures a generic in-process pydantic-ai agent, NOT a specific coding "
    "agent's runtime. Skill/subagent frontmatter maps onto pydantic-ai's model; "
    "`allowed-tools` / `disable-model-invocation` are NOT enforced. Cost is derived, "
    "not native. Caller-supplied `instructions` are injected only when passed "
    "explicitly (a *steered* proxy); the adapter never auto-reads an MCP server's "
    "instructions."
)


_MISSING_AGENT = (
    "InProcessAgentAdapter needs pydantic-ai + pydantic-ai-harness, which ship with the "
    "[agent] extra. Install with: pip install 'robotframework-agenteval[agent]'"
)


def _resolve_usage_limits(
    *,
    run_usage_limits: Any | None,
    run_request_limit: int | None,
    init_usage_limits: Any | None,
    init_request_limit: int | None,
    usage_limits_cls: Any,
) -> Any | None:
    """Resolve the effective usage-limit object by precedence.

    One rule: a value passed to ``run()`` overrides one passed to ``__init__`` as a
    whole, and within a level the full ``usage_limits`` object beats the
    ``request_limit`` shortcut. Everything unset returns ``None`` - the caller adds
    no override and pydantic-ai's built-in default (``request_limit=50``) applies.
    ``usage_limits_cls`` is pydantic-ai's ``UsageLimits``, passed in from ``run()``
    after the lazy import so this helper stays free of the ``[agent]`` dependency.
    ``request_limit`` is passed through unvalidated - the agent library owns its own
    limit semantics.
    """
    if run_usage_limits is not None:
        return run_usage_limits
    if run_request_limit is not None:
        return usage_limits_cls(request_limit=run_request_limit)
    if init_usage_limits is not None:
        return init_usage_limits
    if init_request_limit is not None:
        return usage_limits_cls(request_limit=init_request_limit)
    return None


def _resolve_instructions(run_instructions: str | None, init_instructions: str | None) -> str | None:
    """Run-level instructions override ``__init__``-level; ``None`` means unset."""
    return run_instructions if run_instructions is not None else init_instructions


class InProcessAgentAdapter:
    """Drive a prompt through an in-process pydantic-ai agent (any OpenAI-compatible LLM).

    Configure ``model`` (or ``AGENTEVAL_MODEL``), ``base_url``, and ``api_key``.
    Pass ``capabilities`` (pydantic-ai ``Capability`` objects, e.g. deferred skills)
    and ``toolsets`` (e.g. an MCP toolset) to shape what the agent can do.

    Raise the agent loop's usage limit with ``request_limit`` (a shortcut) or a full
    ``usage_limits`` object (pydantic-ai ``UsageLimits`` - token limits, tool-call
    limit, ...). Inject run-level ``instructions`` (a caller-composed string, e.g. an
    MCP server's own guidance) that reach the model and compose with skills. Each of
    these is accepted here and on ``run()``; a value passed to ``run()`` overrides the
    one passed here, and within a level the full ``usage_limits`` object beats the
    ``request_limit`` shortcut. All unset ⇒ pydantic-ai's defaults ⇒ non-breaking.
    """

    name = "in-process"
    validation_ceiling = _CEILING

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        capabilities: list[Any] | None = None,
        toolsets: list[Any] | None = None,
        retries: int = 3,
        request_limit: int | None = None,
        usage_limits: Any | None = None,
        instructions: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._api_key = api_key
        self._capabilities = capabilities or []
        self._toolsets = toolsets or []
        self._retries = retries
        self._request_limit = request_limit
        self._usage_limits = usage_limits
        self._instructions = instructions
        self._extra_kwargs = dict(kwargs)

    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        """Run ``prompt`` through the in-process agent and normalize the result."""
        try:
            from pydantic_ai import Agent
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.openai import OpenAIProvider
            from pydantic_ai.usage import UsageLimits
        except ImportError as exc:
            raise MissingExtraError(_MISSING_AGENT, extra="agent") from exc

        model_name = resolve_config(kwargs.pop("model", None) or self._model, env_var="AGENTEVAL_MODEL")
        base_url = resolve_config(kwargs.pop("base_url", None) or self._base_url, env_var="AGENTEVAL_BASE_URL")
        api_key = resolve_config(kwargs.pop("api_key", None) or self._api_key, env_var="AGENTEVAL_API_KEY")
        if not model_name:
            raise MissingExtraError(
                "InProcessAgentAdapter needs a model - pass model= or set AGENTEVAL_MODEL", extra="agent"
            )

        usage_limits = _resolve_usage_limits(
            run_usage_limits=kwargs.pop("usage_limits", None),
            run_request_limit=kwargs.pop("request_limit", None),
            init_usage_limits=self._usage_limits,
            init_request_limit=self._request_limit,
            usage_limits_cls=UsageLimits,
        )
        instructions = _resolve_instructions(kwargs.pop("instructions", None), self._instructions)

        provider = OpenAIProvider(base_url=base_url, api_key=api_key) if (base_url or api_key) else None
        model_obj = OpenAIChatModel(model_name, provider=provider) if provider else OpenAIChatModel(model_name)
        agent = Agent(
            model_obj,
            capabilities=self._capabilities or None,
            toolsets=self._toolsets or None,
            retries=self._retries,
        )

        # usage_limits=None reproduces pydantic-ai's default (request_limit=50);
        # instructions is omitted entirely when unset so the default path is unchanged.
        run_kwargs: dict[str, Any] = {"usage_limits": usage_limits}
        if instructions is not None:
            run_kwargs["instructions"] = instructions
        result = run_async(agent.run(prompt, **run_kwargs))
        return _map_agent_result(result)


def _map_agent_result(result: Any) -> AgentRunResult:
    """Project a pydantic-ai run result onto ``AgentRunResult``.

    Executed tool calls (including the framework ``load_capability`` skill-activation
    calls) are paired to their results by ``tool_call_id`` across the message history.
    """
    tool_returns: dict[str, Any] = {}
    for msg in result.all_messages():
        for part in getattr(msg, "parts", []):
            if getattr(part, "part_kind", "") == "tool-return":
                tool_returns[getattr(part, "tool_call_id", "")] = getattr(part, "content", None)

    traces: list[ToolCallTrace] = []
    text = str(getattr(result, "output", "") or "")
    for msg in result.all_messages():
        for part in getattr(msg, "parts", []):
            if getattr(part, "part_kind", "") != "tool-call":
                continue
            raw_args = getattr(part, "args", None)
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args) if raw_args else {}
                except json.JSONDecodeError:
                    args = {"_raw": raw_args}
            else:
                args = dict(raw_args) if isinstance(raw_args, dict) else {}
            call_id = getattr(part, "tool_call_id", "") or ""
            traces.append(
                ToolCallTrace(
                    name=str(getattr(part, "tool_name", "")),
                    args=args,
                    result=tool_returns.get(call_id),
                    tool_call_id=call_id,
                    sequence_index=len(traces),
                    source="adapter",
                )
            )

    usage = result.usage() if callable(getattr(result, "usage", None)) else result.usage
    return AgentRunResult(
        response_text=text,
        tool_calls=traces,
        usage=Usage(
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            cached_input_tokens=int(getattr(usage, "cache_read_tokens", 0) or 0),
        ),
        metadata=AgentRunMetadata(mcp_coverage="hosted_in_process", metric_source="derived"),
        trace_id="",
    )
