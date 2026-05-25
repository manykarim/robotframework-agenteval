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

"""`OpenAIAgentsSDKAdapter` — native OpenAI Agents SDK adapter (Story 10.2 / FR13d).

Phase-2 adapter. Wraps OpenAI's `openai-agents` PyPI package (import path
``agents``, distinct from the bare ``openai`` LLM client) for native Agent
SDK semantics: instructions, tools, multi-turn, MCP, sessions.

Story 10.2 drift resolutions documented in
``_bmad-output/implementation-artifacts/10-2-openai-agents-sdk-adapter.md``:

- D-1: Subclasses ``InProcessAdapter`` + override ``run()`` directly per
  ADR-003 (no ``_invoke_llm`` hook — spec text was speculative; the actual
  ABC has no abstract hooks).
- D-2: Uses ``openai-agents`` package (Python import: ``from agents import
  Agent, Runner``), NOT the bare ``openai`` client.
- D-3: ``RunResult.usage`` shape is empirically unverified at write time;
  ``_extract_usage()`` defensively branches on ``isinstance(usage, dict)``
  per the Story 10.1 HIGH-1 regression-guard lesson.
- D-4: ``mcp_coverage`` follows ADR-A6 L384 safer-default — non-empty
  ``mcp_servers`` returns ``external_mixed`` until ``HostedMcpObserver``
  wiring lands (``DF-10.2-S1``).
- D-5: Uses ``Runner.run_sync()`` (sync API) — Robot Framework calls
  keywords synchronously.
- D-6: ``_record_run_metadata`` wired from the start per Story 10.1 HIGH-4
  cross-LLM review lesson (RunManifest sidecar coverage).
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any

from AgentEval.coding_agent.base import InProcessAdapter, _default_version
from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage

if TYPE_CHECKING:
    from collections.abc import Mapping


_SDK_IMPORT_ERROR_MSG = (
    "OpenAIAgentsSDKAdapter requires the `openai-agents` package "
    "(import path: `agents`). "
    "Install with: `pip install robotframework-agenteval[openai-agents]` "
    "(or `uv pip install -e '.[openai-agents]'` for dev installs)."
)


class OpenAIAgentsSDKAdapter(InProcessAdapter):
    """`InProcessAdapter` driving OpenAI's Agents SDK.

    Subclasses ``InProcessAdapter`` per ADR-003 direct-override pattern.
    Drives ``Runner.run_sync(agent, prompt)`` synchronously — the SDK
    supports both sync + async; sync matches Robot Framework's calling
    convention.

    Construct with::

        OpenAIAgentsSDKAdapter(
            model="gpt-4o",
            name="agenteval-agent",
            instructions="You are a helpful agent.",
        )

    ``mcp_coverage`` detection contract per AC-10.2.2 + ADR-A6 L384:

    1. ``mcp_servers`` is None / empty → ``"hosted_in_process"`` (trivially
       honest; nothing to cover).
    2. ``mcp_servers`` is non-empty AND no verified hosted-attachment
       signal exists → ``"external_mixed"`` per ADR-A6 safer-default rule.
       The ``HostedMcpObserver`` wiring that would upgrade branch 2 to
       ``hosted_in_process`` empirically is **DF-10.2-S1** carry-over.

    ``RunResult.usage`` shape is **not empirically verified** at write
    time; the project's `feedback_listener_hook_api_surface_empirical_check`
    (Epic 8 retro) + Story 10.1 HIGH-1 lesson mandates defensive access.
    ``_extract_usage()`` branches on ``isinstance(usage, dict)`` so either
    attribute-bearing OR dict shapes work.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        name: str = "agenteval-agent",
        instructions: str | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            import agents  # noqa: F401 — proves the `openai-agents` SDK is installed
        except ImportError as exc:
            raise ImportError(_SDK_IMPORT_ERROR_MSG) from exc

        super().__init__(
            model=model,
            name=name,
            instructions=instructions,
            **kwargs,
        )
        self._model = model
        self._agent_name = name
        self._instructions = instructions

    @property
    def name(self) -> str:
        return "OpenAIAgentsSDKAdapter"

    @property
    def version(self) -> str:
        return _default_version(type(self).__module__)

    def run(
        self,
        prompt: str,
        tools: list[str] | None = None,
        mcp_servers: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> AgentRunResult:
        """Drive ``Runner.run_sync(agent, prompt)`` and project the result
        into the normalized ``AgentRunResult`` shape.

        Per Story 6.3 AC-6.3.5 + PRD FR30b: ``enforce_tier1_no_llm()`` is
        called at run-entry — matches the ``GenericAdapter.run()`` + Story
        10.1 ``ClaudeAgentSDKAdapter.run()`` precedents.

        Story 10.2 explicit non-goals (carry-over candidates):

        - MCP attachment via the SDK's native MCP host is NOT wired here;
          the README excerpt didn't include the attachment signature.
          Phase-2 must verify the actual MCP-attachment API empirically
          before wiring; until then, non-empty ``mcp_servers`` falls back
          to ``external_mixed`` per ADR-A6. Tracked at ``DF-10.2-S1``.
        - Tool-use ↔ tool-result pairing across multiple ``raw_responses``
          entries is deferred to Phase-2 if needed (``DF-10.2-S2`` if it
          surfaces during integration testing).
        - Sessions / multi-turn conversation history management is out of
          scope; each ``run()`` is a standalone single-shot.
        """
        # Tier-1 ban (matches GenericAdapter + Story 10.1 precedents).
        from AgentEval._kernel.tier_acl import enforce_tier1_no_llm

        enforce_tier1_no_llm()

        # Lazy imports — verified at __init__ time.
        from agents import Agent, Runner

        # Story 10.1 HIGH-4 lesson applied UPSTREAM: wire Story 5.3
        # RunManifest sidecar from the start.
        from AgentEval.coding_agent.generic import (
            _hash_prompt,
            _manifest_entries_from_servers,
            _record_run_metadata,
        )

        mcp_coverage = self._detect_mcp_coverage(mcp_servers)

        agent_kwargs: dict[str, Any] = {"name": self._agent_name}
        if self._instructions is not None:
            agent_kwargs["instructions"] = self._instructions
        if self._model is not None:
            agent_kwargs["model"] = self._model

        agent = Agent(**agent_kwargs)

        start = time.monotonic()
        try:
            sdk_result = Runner.run_sync(agent, prompt)
        except Exception:
            # ADR-A6 detection-failure path — re-raise so callers see the
            # underlying SDK error.
            raise
        finally:
            latency_seconds = time.monotonic() - start

        response_text = str(getattr(sdk_result, "final_output", "") or "")
        cost_usd = _extract_cost(sdk_result)
        usage = _extract_usage(sdk_result)
        tool_calls = _project_tool_calls(getattr(sdk_result, "raw_responses", None))

        result = AgentRunResult(
            response_text=response_text,
            tool_calls=tool_calls,
            usage=usage,
            metadata=AgentRunMetadata(
                completeness="complete",
                mcp_coverage=mcp_coverage,  # type: ignore[arg-type]
            ),
            cost_usd=cost_usd,
            latency_seconds=latency_seconds,
            trace_id=uuid.uuid4().hex,
        )
        # Story 5.3 RunManifest sidecar — no-op when no Listener active.
        _record_run_metadata(
            adapter_name=self.name,
            adapter_version=self.version,
            model=self._model,
            mcp_servers=_manifest_entries_from_servers(dict(mcp_servers) if mcp_servers else None),
            total_cost_usd=result.cost_usd,
            completeness=result.metadata.completeness,
            mcp_coverage=result.metadata.mcp_coverage,
            prompt_hashes=[_hash_prompt(prompt)],
        )
        return result

    @staticmethod
    def _detect_mcp_coverage(
        mcp_servers: Mapping[str, Any] | None,
    ) -> str:
        """Honest 2-branch detection per AC-10.2.2 + ADR-A6 L384.

        Mirrors the Story 10.1 patched contract (post-HIGH-2 review). The
        ADR-A6 ratified rule: detection-failure defaults to
        ``external_mixed``, NOT ``hosted_in_process``. Until the SDK's MCP
        attachment surface is empirically verified + the
        ``HostedMcpObserver`` wired (``DF-10.2-S1``), non-empty
        ``mcp_servers`` claims ``external_mixed``.
        """
        if not mcp_servers:
            return "hosted_in_process"
        return "external_mixed"


def _extract_cost(sdk_result: Any) -> float:
    """Read total cost from the SDK's ``RunResult``.

    Per ``feedback_codex_probe_fitness`` Epic 2 retro + Story 10.1 review
    MED-2: prefer ``total_cost_usd``; fall back to ``cost_usd`` as a
    defensive shim for pre-1.0 SDK shape variation. Default ``0.0``.

    Note: unlike the ClaudeAgentSDKAdapter where Story 10.1 review MED-2
    removed the ``cost_usd`` fallback after empirical probe, the
    ``openai-agents`` SDK's ``RunResult`` shape is **not empirically
    verified** at write time; the defensive fallback is kept and will be
    removed once Story 10.2's integration test runs against the live SDK
    + the exact attribute name is observed.
    """
    if sdk_result is None:
        return 0.0
    cost = getattr(sdk_result, "total_cost_usd", None)
    if cost is None:
        cost = getattr(sdk_result, "cost_usd", None)
    if cost is None:
        # The `result.usage` object may carry cost — defensive read.
        usage_obj = getattr(sdk_result, "usage", None)
        if usage_obj is not None:
            if isinstance(usage_obj, dict):
                cost = usage_obj.get("total_cost_usd") or usage_obj.get("cost_usd")
            else:
                cost = getattr(usage_obj, "total_cost_usd", None) or getattr(usage_obj, "cost_usd", None)
    return float(cost) if cost is not None else 0.0


def _extract_usage(sdk_result: Any) -> Usage:
    """Project ``RunResult.usage`` into the project's frozen ``Usage``.

    Story 10.2 D-3 + Story 10.1 HIGH-1 lesson: **shape is empirically
    unverified** at write time. Defensive dual-branch:

    - If ``usage`` is a ``dict``: read keys via ``dict.get()``.
    - Else: read attributes via ``getattr()``.

    Either branch returns the same ``Usage(input_tokens, output_tokens,
    cached_input_tokens)`` shape. Pinned by a regression-guard test
    ``test_extract_usage_handles_both_shapes``.
    """
    if sdk_result is None:
        return Usage(input_tokens=0, output_tokens=0, cached_input_tokens=0)
    usage = getattr(sdk_result, "usage", None)
    if usage is None:
        return Usage(input_tokens=0, output_tokens=0, cached_input_tokens=0)

    if isinstance(usage, dict):
        return Usage(
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            cached_input_tokens=int(usage.get("cached_input_tokens", 0) or 0),
        )

    # Attribute-bearing branch.
    return Usage(
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
        cached_input_tokens=int(getattr(usage, "cached_input_tokens", 0) or 0),
    )


def _project_tool_calls(raw_responses: Any) -> list[ToolCallTrace]:
    """Project tool-use entries from ``RunResult.raw_responses`` into
    ``ToolCallTrace``.

    Story 10.2 carve-out (``DF-10.2-S2`` candidate if needed): the OpenAI
    Agents SDK's ``raw_responses`` shape varies by model + tool type. This
    helper extracts what it can defensively. Phase-1 minimal projection:
    name + args; result/error left None; latency_ms = 0.0. Full
    use+result pairing (across multiple turns) is deferred.
    """
    if raw_responses is None or not isinstance(raw_responses, list):
        return []
    traces: list[ToolCallTrace] = []
    seq = 0
    for resp in raw_responses:
        # Tool calls typically land under `resp.tool_calls` or
        # `resp.output[*].tool_call`. Defensive against shape variation.
        tool_calls_attr = getattr(resp, "tool_calls", None)
        if not tool_calls_attr and isinstance(resp, dict):
            tool_calls_attr = resp.get("tool_calls")
        if not tool_calls_attr:
            continue
        if not isinstance(tool_calls_attr, list):
            continue
        for tc in tool_calls_attr:
            name = str(getattr(tc, "name", "") or (tc.get("name", "") if isinstance(tc, dict) else ""))
            raw_args = getattr(tc, "arguments", None)
            if raw_args is None and isinstance(tc, dict):
                raw_args = tc.get("arguments")
            args = dict(raw_args) if isinstance(raw_args, dict) else {}
            call_id = str(getattr(tc, "id", "") or (tc.get("id", "") if isinstance(tc, dict) else "") or "")
            traces.append(
                ToolCallTrace(
                    name=name,
                    args=args,
                    result=None,
                    error=None,
                    latency_ms=0.0,
                    source="adapter",
                    gen_ai_tool_call_id=call_id,
                    sequence_index=seq,
                )
            )
            seq += 1
    return traces
