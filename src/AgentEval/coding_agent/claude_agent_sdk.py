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

"""`ClaudeAgentSDKAdapter` — native Anthropic Agent SDK adapter (Story 10.1 / FR13c).

Phase-2 launch adapter. Wraps Anthropic's `claude-agent-sdk` PyPI package
(distinct from the LLM-only `anthropic` client) for native Agent SDK
semantics: system prompts, tools, multi-turn, in-process MCP.

Story 10.1 drift resolutions documented in
`_bmad-output/implementation-artifacts/10-1-claude-agent-sdk-adapter.md`:

- D-1: ``[claude-sdk]`` extra (NOT ``[claude]`` — disambiguates from
  ``[claude-code]`` which gates the CC CLI adapter).
- D-2: Subclasses ``InProcessAdapter`` + override ``run()`` directly per
  ADR-003 L22-23 (no ``_invoke_llm`` / ``_run_async`` hooks — the spec text
  describing those was speculative; the actual ABC at
  ``src/AgentEval/coding_agent/base.py:197-226`` has no abstract hooks).
- D-3: Uses ``claude-agent-sdk`` package, NOT ``anthropic``. The Agent SDK
  exposes the hosted-MCP path the spec's ``mcp_coverage="hosted_in_process"``
  claim requires; the bare ``anthropic`` LLM client does not.
- D-4: ``mcp_coverage`` follows ADR-A6 L384 honesty contract — defaults
  to ``hosted_in_process`` only when MCP attachment is verified or absent;
  falls back to ``external_mixed`` on detection failure (safer per ADR-A6).
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
    "ClaudeAgentSDKAdapter requires the `claude-agent-sdk` package + `anyio`. "
    "Install with: `pip install robotframework-agenteval[claude-sdk]` "
    "(or `uv pip install -e '.[claude-sdk]'` for dev installs)."
)


class ClaudeAgentSDKAdapter(InProcessAdapter):
    """`InProcessAdapter` driving Anthropic's Claude Agent SDK.

    Subclasses ``InProcessAdapter`` per ADR-003 direct-override pattern.
    The SDK is async-only (``anyio``-based); ``run()`` synchronously drives
    the async generator via ``anyio.run()``.

    Construct with::

        ClaudeAgentSDKAdapter(model="claude-sonnet-4-5", max_turns=5, system_prompt="You are a helpful agent.")

    ``mcp_coverage`` detection contract per AC-10.1.2 + ADR-A6 L384
    (post-cross-LLM-review HIGH-2 patch):

    1. ``mcp_servers`` is None / empty → ``"hosted_in_process"`` (nothing
       to cover; trivially honest).
    2. ``mcp_servers`` is non-empty AND no verified hosted-attachment
       signal exists yet → ``"external_mixed"`` per ADR-A6 L384 safer-
       default rule. The ``HostedMcpObserver`` wiring that would upgrade
       branch 2 to ``"hosted_in_process"`` empirically is tracked at
       **C68** (``DF-10.1-S2``). Until C68 lands, claiming hosted
       coverage we cannot verify violates the honesty contract.

    The Agent SDK ``ResultMessage.total_cost_usd`` is the source of truth
    for cost (empirically verified via ``dataclasses.fields()`` during
    the cross-LLM review). The ``ResultMessage.usage`` field is a
    ``dict[str, Any] | None`` — accessed via ``dict.get()``, NOT
    ``getattr()`` (review HIGH-1 patch).
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        max_turns: int = 5,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            import anyio  # noqa: F401 — proves anyio is importable at construction
            import claude_agent_sdk  # noqa: F401 — proves the SDK is installable
        except ImportError as exc:
            raise ImportError(_SDK_IMPORT_ERROR_MSG) from exc

        super().__init__(
            model=model,
            max_turns=max_turns,
            system_prompt=system_prompt,
            **kwargs,
        )
        self._model = model
        self._max_turns = max_turns
        self._system_prompt = system_prompt

    @property
    def name(self) -> str:
        return "ClaudeAgentSDKAdapter"

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
        """Drive a Claude Agent SDK ``query()`` synchronously and project the
        result into the normalized ``AgentRunResult`` shape.

        Per Story 6.3 AC-6.3.5 + PRD FR30b: ``enforce_tier1_no_llm()`` is
        called at run-entry — matches the ``GenericAdapter.run()`` precedent
        at ``src/AgentEval/coding_agent/generic.py:194-197``.

        Story 10.1 explicit non-goals (carry-over candidates):

        - Phase-1-style ``tools`` Robot-Framework keyword binding is out
          of scope here; the SDK's native tool surface (``@tool``-decorated
          callables passed via ``ClaudeAgentOptions``) is what's wired.
        - Hooks integration (Agent SDK ``SessionHooks``) is deferred.
        - Streaming-mode partial-message capture is deferred; we collect
          the full async iterator before projection.
        """
        # Tier-1 ban (matches GenericAdapter precedent).
        from AgentEval._kernel.tier_acl import enforce_tier1_no_llm

        enforce_tier1_no_llm()

        # Lazy imports — already verified at __init__ time.
        import anyio
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            TextBlock,
            ToolUseBlock,
            query,
        )

        # Story 10.1 review HIGH-4 patch: wire Story 5.3 RunManifest sidecar
        # via the shared helpers — previously the SHA-256 was computed and
        # immediately discarded, leaving Agent SDK runs absent from the
        # manifest. Pattern mirrors `generic.py:246-257`.
        from AgentEval.coding_agent.generic import (
            _hash_prompt,
            _manifest_entries_from_servers,
            _record_run_metadata,
        )

        mcp_coverage = self._detect_mcp_coverage(mcp_servers)

        options_kwargs: dict[str, Any] = {}
        if self._model is not None:
            options_kwargs["model"] = self._model
        if self._system_prompt is not None:
            options_kwargs["system_prompt"] = self._system_prompt
        if self._max_turns is not None:
            options_kwargs["max_turns"] = self._max_turns
        if mcp_servers:
            options_kwargs["mcp_servers"] = dict(mcp_servers)
        if tools:
            options_kwargs["allowed_tools"] = list(tools)

        async def _drive() -> tuple[str, list[ToolUseBlock], ResultMessage | None]:
            options = ClaudeAgentOptions(**options_kwargs)
            text_parts: list[str] = []
            tool_uses: list[ToolUseBlock] = []
            result_msg: ResultMessage | None = None
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in getattr(message, "content", []) or []:
                        if isinstance(block, TextBlock):
                            text_parts.append(getattr(block, "text", ""))
                        elif isinstance(block, ToolUseBlock):
                            tool_uses.append(block)
                elif isinstance(message, ResultMessage):
                    result_msg = message
            return "".join(text_parts), tool_uses, result_msg

        start = time.monotonic()
        try:
            response_text, tool_use_blocks, result_msg = anyio.run(_drive)
        except Exception:
            # Detection-failure path per ADR-A6 — degrade mcp_coverage
            # honestly + re-raise so callers see the underlying error.
            mcp_coverage = "external_mixed"
            raise
        finally:
            latency_seconds = time.monotonic() - start

        cost_usd = _extract_cost(result_msg)
        usage = _extract_usage(result_msg)
        tool_calls = _project_tool_calls(tool_use_blocks)

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
        # Story 5.3 RunManifest sidecar — no-op when no Listener is active.
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
        """Honest detection per AC-10.1.2 + ADR-A6 L384 safer-default rule.

        Story 10.1 cross-LLM review HIGH-2 patch: the original implementation
        returned ``"hosted_in_process"`` from both branches, making the
        3-branch contract a fake. ADR-A6 L384 ratified contract:
        **"Detection-failure defaults to ``external_mixed`` (NOT
        ``hosted_in_process``) — safer than silent partial truth."**

        Honest contract:

        - ``mcp_servers`` is None / empty → ``"hosted_in_process"`` (no MCP
          to cover; trivially honest).
        - ``mcp_servers`` is non-empty AND no verified hosted-attachment
          signal exists yet → ``"external_mixed"`` per ADR-A6 detection-
          failure default. The ``HostedMcpObserver`` wiring that would
          upgrade this to ``"hosted_in_process"`` empirically is tracked
          at C68 (``DF-10.1-S2``). Until C68 lands, the SAFER default is
          to claim ``external_mixed`` rather than optimistically claim
          hosted coverage we cannot verify.
        """
        if not mcp_servers:
            return "hosted_in_process"
        # ADR-A6 L384 + Story 10.1 review HIGH-2: safer default until C68
        # (HostedMcpObserver wiring) lands.
        return "external_mixed"


def _extract_cost(result_msg: Any) -> float:
    """Read total cost from the SDK's ``ResultMessage``.

    Per ``feedback_codex_probe_fitness`` Epic 2 retro + Story 10.1 cross-LLM
    review MED-2 patch: only ``total_cost_usd`` exists on the real
    ``ResultMessage`` (empirically verified via ``dataclasses.fields()``).
    The earlier ``or getattr(..., "cost_usd")`` fallback was defensive
    dead-code referencing a field that doesn't exist; removed.
    """
    if result_msg is None:
        return 0.0
    cost = getattr(result_msg, "total_cost_usd", None)
    return float(cost) if cost is not None else 0.0


def _extract_usage(result_msg: Any) -> Usage:
    """Project ``ResultMessage.usage`` (a ``dict[str, Any] | None``) into the
    project's frozen ``Usage`` dataclass.

    Story 10.1 cross-LLM review HIGH-1 patch: empirical probe of the real
    ``claude_agent_sdk.ResultMessage`` shows ``usage`` is declared as
    ``dict[str, typing.Any] | None`` — **not** an object with attributes.
    The original implementation used ``getattr(usage_obj, ...)`` which
    returns the default for every dict access; every live run reported
    ``Usage(0, 0, 0)``. The fake-test masked this because the test's
    ``_FakeUsage`` shim was attribute-bearing.
    """
    if result_msg is None:
        return Usage(input_tokens=0, output_tokens=0, cached_input_tokens=0)
    usage = getattr(result_msg, "usage", None) or {}
    if not isinstance(usage, dict):  # defensive against pre-1.0 SDK shape drift
        return Usage(input_tokens=0, output_tokens=0, cached_input_tokens=0)
    return Usage(
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        output_tokens=int(usage.get("output_tokens", 0) or 0),
        cached_input_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
    )


def _project_tool_calls(tool_use_blocks: list[Any]) -> list[ToolCallTrace]:
    """Project SDK ``ToolUseBlock`` instances into ``ToolCallTrace``.

    Story 10.1 carve-out (DF-10.1-S3 candidate): the Agent SDK reports
    tool USES (the model calling a tool) but the tool RESULT lives on
    ``ToolResultBlock`` items in the next ``UserMessage``. Pairing
    use+result requires per-call-id correlation; Story 10.1 ships the
    minimal projection (``name`` + ``args`` + ``gen_ai_tool_call_id``;
    ``result``/``error`` left None; ``latency_ms`` = 0.0). The full
    use+result pairing lands in DF-10.1-S3.
    """
    traces: list[ToolCallTrace] = []
    for idx, block in enumerate(tool_use_blocks):
        name = str(getattr(block, "name", ""))
        raw_input = getattr(block, "input", None)
        args = dict(raw_input) if isinstance(raw_input, dict) else {}
        call_id = str(getattr(block, "id", "") or "")
        traces.append(
            ToolCallTrace(
                name=name,
                args=args,
                result=None,
                error=None,
                latency_ms=0.0,
                source="adapter",
                gen_ai_tool_call_id=call_id,
                sequence_index=idx,
            )
        )
    return traces
