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

"""The one adapter seam every Tier-3 keyword drives.

An adapter is anything with ``run(prompt) -> AgentRunResult``. We ship exactly
one concrete adapter, ``GenericAdapter``, backed by LiteLLM so it reaches 140+
providers through a single path. LiteLLM lives behind the ``[llm]`` extra: the
import is lazy and a clear ``MissingExtraError`` names the extra if it's absent.

``run_async`` bridges async provider calls to the synchronous keyword world,
including the nested-event-loop case (IDE runners) via a worker thread.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import os
import threading
import time
import uuid
from collections.abc import Coroutine
from typing import Any, Literal, Protocol, runtime_checkable

from AgentEval._core.errors import AdapterError, MissingExtraError
from AgentEval._core.tier import enforce_no_model
from AgentEval._core.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage

__all__ = [
    "Adapter",
    "GenericAdapter",
    "get_adapter",
    "resolve_config",
    "run_async",
]


@runtime_checkable
class Adapter(Protocol):
    """A coding-agent adapter: run a prompt, get a normalized result.

    ``name`` identifies the adapter; ``run`` does the work. Any object with
    this shape works - no vendor base class required.
    """

    name: str

    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        """Execute a single prompt and return an ``AgentRunResult``."""
        ...


def resolve_config(
    kwarg_value: str | None = None,
    *,
    env_var: str | None = None,
    default: str | None = None,
) -> str | None:
    """Resolve a config value by precedence: explicit kwarg, then env, then default."""
    if kwarg_value is not None:
        return kwarg_value
    if env_var is not None:
        env_value = os.environ.get(env_var)
        if env_value:
            return env_value
    return default


class GenericAdapter:
    """LiteLLM-backed adapter - the single generic path to any provider.

    Set ``model`` at construction (or per call via ``run(..., model=...)``, or
    the ``AGENTEVAL_MODEL`` env var). Extra keyword arguments are forwarded to
    ``litellm.completion`` (e.g. ``temperature``, ``seed``, ``api_base``).
    """

    name = "generic"

    def __init__(self, *, model: str | None = None, **kwargs: Any) -> None:
        self._model = model
        self._extra_kwargs: dict[str, Any] = dict(kwargs)

    def run(self, prompt: str, **kwargs: Any) -> AgentRunResult:
        """Send ``prompt`` to the configured model and normalize the response.

        Raises ``MissingExtraError`` if LiteLLM is not installed, ``AdapterError``
        if no model is configured, and ``TierViolationError`` if called inside a
        deterministic (Tier-1) scope.
        """
        enforce_no_model()
        litellm = _import_litellm()

        model = resolve_config(
            kwargs.pop("model", None) or self._model,
            env_var="AGENTEVAL_MODEL",
        )
        if not model:
            raise AdapterError(
                "GenericAdapter needs a model - pass model= to the library, the keyword, or set AGENTEVAL_MODEL"
            )

        call_kwargs: dict[str, Any] = {**self._extra_kwargs, **kwargs}
        messages = [{"role": "user", "content": prompt}]

        start = time.monotonic()
        response = litellm.completion(model=model, messages=messages, **call_kwargs)
        latency_seconds = time.monotonic() - start

        return _map_completion(litellm, response, latency_seconds)


def _import_litellm() -> Any:
    """Import litellm lazily; translate a missing install into a clear error."""
    try:
        import litellm
    except ImportError as exc:
        raise MissingExtraError(
            "GenericAdapter needs LiteLLM, which ships with the [llm] extra. "
            "Install it with: pip install 'robotframework-agenteval[llm]'",
            extra="llm",
        ) from exc
    return litellm


def _map_completion(litellm: Any, response: Any, latency_seconds: float) -> AgentRunResult:
    """Map a LiteLLM completion response onto ``AgentRunResult``."""
    text = ""
    choices = _safe_get(response, "choices") or []
    if choices:
        message = _safe_get(choices[0], "message")
        content = _safe_get(message, "content")
        if isinstance(content, str):
            text = content

    usage_raw = _safe_get(response, "usage")
    # cached-token count lives under prompt_tokens_details.cached_tokens on
    # providers that report it (OpenAI/Anthropic prompt caching).
    details = _safe_get(usage_raw, "prompt_tokens_details")
    usage = Usage(
        input_tokens=_as_int(_safe_get(usage_raw, "prompt_tokens")),
        output_tokens=_as_int(_safe_get(usage_raw, "completion_tokens")),
        cached_input_tokens=_as_int(_safe_get(details, "cached_tokens")),
    )

    tool_calls = _parse_tool_calls(message if choices else None)

    cost_usd = 0.0
    metric_source: Literal["native", "derived", "none"] = "none"
    try:
        raw_cost = litellm.completion_cost(completion_response=response)
    except Exception:  # noqa: BLE001 - some providers publish no pricing metadata
        raw_cost = None
    if raw_cost is not None:
        cost_usd = float(raw_cost)
        metric_source = "derived"  # litellm computes cost from tokens + its price table

    return AgentRunResult(
        response_text=text,
        tool_calls=tool_calls,
        usage=usage,
        metadata=AgentRunMetadata(
            completeness="complete", mcp_coverage="hosted_in_process", metric_source=metric_source
        ),
        cost_usd=cost_usd,
        latency_seconds=latency_seconds,
        trace_id=uuid.uuid4().hex,
    )


def _parse_tool_calls(message: Any) -> list[ToolCallTrace]:
    """Project a chat message's ``tool_calls`` into ``ToolCallTrace`` records.

    These are the tool calls the model *requested* on this turn - a one-shot
    completion does not execute them, so ``result`` stays ``None``. Arguments
    arrive as a JSON string on ``function.arguments``; a non-JSON string is kept
    verbatim under ``{"_raw": ...}`` rather than dropped.
    """
    raw_calls = _safe_get(message, "tool_calls") or []
    traces: list[ToolCallTrace] = []
    for index, call in enumerate(raw_calls):
        fn = _safe_get(call, "function")
        name = _safe_get(fn, "name") or ""
        raw_args = _safe_get(fn, "arguments")
        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                args = {"_raw": raw_args}
        elif isinstance(raw_args, dict):
            args = raw_args
        else:
            args = {}
        if not isinstance(args, dict):
            args = {"_raw": args}
        traces.append(
            ToolCallTrace(
                name=str(name),
                args=args,
                tool_call_id=str(_safe_get(call, "id") or ""),
                sequence_index=index,
                source="adapter",
            )
        )
    return traces


def _safe_get(obj: Any, key: str) -> Any:
    """Read ``key`` from an object by attribute or dict lookup; None on miss."""
    if obj is None:
        return None
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key)
    return None


def _as_int(value: Any) -> int:
    """Coerce a token-count value to int, defaulting to 0 on anything odd."""
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# Registry of built-in adapters by slug. The four surfaces resolve Tier-3
# adapters through here; a caller may also hand a keyword its own adapter
# object, which never touches this map.
_ADAPTERS: dict[str, type[Adapter]] = {"generic": GenericAdapter}


def get_adapter(name_or_adapter: str | Adapter = "generic", **kwargs: Any) -> Adapter:
    """Return an adapter instance.

    Pass a slug (currently only ``"generic"``) to build a built-in adapter, or
    pass an object that already satisfies the ``Adapter`` protocol to use it as
    is. Unknown slugs raise ``AdapterError``.
    """
    if isinstance(name_or_adapter, str):
        adapter_cls = _ADAPTERS.get(name_or_adapter)
        if adapter_cls is None:
            known = ", ".join(sorted(_ADAPTERS)) or "(none)"
            raise AdapterError(f"unknown adapter {name_or_adapter!r}; known adapters: {known}")
        return adapter_cls(**kwargs)
    if isinstance(name_or_adapter, Adapter):
        return name_or_adapter
    raise AdapterError(
        f"expected an adapter slug or an object with run(prompt) -> AgentRunResult; "
        f"got {type(name_or_adapter).__name__}"
    )


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine to completion from synchronous keyword code.

    Fast path when no loop is running: ``asyncio.run``. When a loop is already
    running (IDE runners, nested executions) a worker thread with its own loop
    runs the coroutine inside a copy of the caller's context so context-vars
    survive the thread boundary. Exceptions propagate verbatim.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    caller_ctx = contextvars.copy_context()
    result: list[T] = []
    exception: list[BaseException] = []

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        try:
            result.append(loop.run_until_complete(coro))
        except BaseException as exc:  # noqa: BLE001 - re-raised across the thread boundary
            exception.append(exc)
        finally:
            loop.close()

    thread = threading.Thread(target=lambda: caller_ctx.run(_runner), daemon=False)
    thread.start()
    thread.join()

    if exception:
        raise exception[0]
    return result[0]
