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

"""`GenericAdapter` — `InProcessAdapter` backed by `LLMProviderAdapter` (Story 4.1 / PRD FR13a).

The generic Phase-1 `CodingAgentAdapter` implementation: routes the
`run(prompt, ...)` call through a configurable provider (default
LiteLLM) and returns a normalized `AgentRunResult`.

Per ADR-003 L22-23 (direct method-override pattern; NO abstract hooks)
and PRD FR12 (single `run()` method).

Story 5.2 DF-4.1-S2 absorption (per Epic 4 retro Action #5): `mcp_servers=`
non-empty NOW wires through `HostedMcpObserver` per ADR-004 + the per-
adapter detection contract at `docs/contracts/mcp-coverage-detection.md`.
The multi-turn tool-dispatch loop (model issues tool_call → dispatched
via observer-wrapped server → result returned to model) is still
Phase-2 scope (DF-5.2-S3); Story 5.2 lands the observer attachment +
mcp_coverage resolution so Story 5.5's dogfood port has the plumbing it
needs.

References:
    - PRD FR12 (single `run()` Protocol method)
    - PRD FR13a (Generic LiteLLM-backed adapter)
    - PRD FR36b (mcp_coverage field per ADR-016 3-value Literal)
    - ADR-003 (InProcessAdapter base; direct override)
    - ADR-004 (Hosted-MCP Observer — Story 5.2 ratified API)
    - ADR-016 (mcp_coverage detection default + D4 per-adapter contract)
    - Story 1b.4 `coding_agent/base.py:InProcessAdapter` + `_default_version`
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from AgentEval.coding_agent.base import InProcessAdapter, _default_version
from AgentEval.mcp.observer import HostedMcpObserver
from AgentEval.providers.base import LLMProviderAdapter, Message
from AgentEval.providers.factory import get_provider
from AgentEval.types import AgentRunMetadata, AgentRunResult, Usage


def _hash_prompt(prompt: str) -> str:
    """SHA-256 hex of a prompt string for RunManifest.prompt_hashes (PRD FR39)."""
    import hashlib

    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _manifest_entries_from_servers(
    mcp_servers: dict[str, Any] | None,
) -> list[dict[str, str]]:
    """Build mcp_servers entries for RunManifest from the adapter's `mcp_servers=` kwarg.

    Phase-1 carve (DF-5.3-S2): `version_or_sha` is `"<TBD Phase-1.5>"` —
    no canonical way to introspect a third-party MCP server's version yet.
    """
    if not mcp_servers:
        return []
    entries: list[dict[str, str]] = []
    for name, handle in mcp_servers.items():
        transport = getattr(handle, "transport", "<unknown>")
        entries.append(
            {
                "name": name,
                "transport": str(transport),
                "version_or_sha": "<TBD Phase-1.5>",  # DF-5.3-S2
            }
        )
    return entries


def _record_run_metadata(**metadata: Any) -> None:
    """Thin wrapper around `telemetry.listener.record_active_run_metadata`.

    Lazy-imports to avoid circular dependency between coding_agent and
    telemetry. No-op when no Listener is active (direct Python invocation
    outside RF).
    """
    from AgentEval.telemetry.listener import record_active_run_metadata

    record_active_run_metadata(**metadata)


__all__ = ["GenericAdapter"]


class GenericAdapter(InProcessAdapter):
    """`InProcessAdapter` routing `run()` through a configurable `LLMProviderAdapter`.

    Phase-1 default: `provider="litellm"`, model selectable per-instance.
    Story 5.2 DF-4.1-S2 absorption: `mcp_servers=` non-empty now wires
    through `HostedMcpObserver` per ADR-004 + the per-adapter detection
    contract. Multi-turn tool-dispatch loop is still Phase-2 (DF-5.2-S3).
    """

    def __init__(
        self,
        *,
        provider: str = "litellm",
        model: str | None = None,
        provider_instance: LLMProviderAdapter | None = None,
        **kwargs: Any,
    ) -> None:
        """Construct the Generic adapter.

        Args:
            provider: Provider name to resolve via the factory (default
                `"litellm"`). Ignored when `provider_instance` is set.
            model: Model string forwarded to the provider's `chat(model=...)`
                call (e.g., `"anthropic/claude-sonnet-4-6"`,
                `"openai/gpt-4o"`, `"ollama/llama3"`).
            provider_instance: Optional pre-constructed provider for
                testing / DI. When set, `provider` is ignored.
            **kwargs: Forwarded to `InProcessAdapter.__init__` (stored
                on `self._adapter_config`).
        """
        super().__init__(provider=provider, model=model, **kwargs)
        self._provider_name = provider
        self._model = model
        self._provider: LLMProviderAdapter = (
            provider_instance if provider_instance is not None else get_provider(provider)
        )

    @property
    def name(self) -> str:
        return "GenericAdapter"

    @property
    def version(self) -> str:
        return _default_version(type(self).__module__)

    def run(
        self,
        prompt: str,
        tools: list[str] | None = None,
        mcp_servers: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AgentRunResult:
        """Execute a single-shot prompt through the configured provider.

        Story 6.3 code-review HIGH-θ fix (Auditor 1-way on Task 11 verbatim):
        `enforce_tier1_no_llm()` wired at the entry point per PRD FR30b — was
        missing from Story 6.3 dev despite Task 11 explicitly enumerating
        `GenericAdapter.run()` as a required call-site (alongside the now-
        wired `LiteLLMAdapter.chat()` + `MockProvider.chat()`).

        Phase-1 scope (Story 5.2 absorbed DF-4.1-S2 per Epic 4 retro Action #5):
        - `tools` is still a Phase-1 carve-out — the multi-turn tool-dispatch
          loop is Phase-2 (DF-5.2-S3); Story 5.2 lands the observer wiring +
          mcp_coverage detection ONLY. Non-empty `tools` continues to raise.
        - `mcp_servers` non-empty NOW WIRES the HostedMcpObserver instead of
          raising. For each `(name, MCPServerHandle)`:
            - Attach `HostedMcpObserver.attach(server, "hosted_in_process")`
              when the handle's `transport="in_memory"` (call `server_factory()`
              to build the FastMCP/Server). Non-in_memory transports degrade
              to `mark_external_mixed(reason)` for Phase-1 since DF-5.2-S3
              defers the subprocess-wrapper hookup to Story 5.5.
            - `mcp_coverage` resolved via `observer.compute_coverage()`.
            - `tool_calls` populated from `observer.tool_calls()` (Phase-1
              they'll be empty without the multi-turn loop, but the observer
              chain is plumbed so Story 5.5's dogfood port + Phase-2's
              multi-turn tool dispatch can land without re-touching this
              method's surface).
        - Remaining `**kwargs` forwarded to the provider's `chat()` call.

        Returns:
            `AgentRunResult` with the Story 1b.4 ratified frozen-dataclass
            shape. `metadata.mcp_coverage` is now resolved from the observer
            when `mcp_servers` is non-empty; falls back to the trivially-
            ``hosted_in_process`` default (Generic LiteLLM has no
            external-config surface) when `mcp_servers` is None/empty.
        """
        if tools:
            raise NotImplementedError(
                "GenericAdapter.run does not advertise tools to the provider in "
                "Phase-1 (DF-5.2-S3); the multi-turn tool-dispatch loop is Phase-2 "
                "scope. Use `tools=None` for Phase-1 single-shot prompts."
            )

        # Story 6.3 AC-6.3.5: Tier-1 LLM-invocation ban per PRD FR30b.
        from AgentEval._kernel.tier_acl import enforce_tier1_no_llm

        enforce_tier1_no_llm()

        # Story 5.2 DF-4.1-S2 absorption: wire mcp_servers through the
        # HostedMcpObserver instead of raising NotImplementedError.
        observer: HostedMcpObserver | None = None
        if mcp_servers:
            observer = HostedMcpObserver()
            for name, handle in mcp_servers.items():
                _attach_handle_to_observer(observer, name, handle)
            # Story 5.2 code-review 1-way HIGH-C fix 2026-05-20 (Blind H2):
            # register the observer with the active RF Listener so
            # `end_test` calls `observer.clear()` for per-test cleanup per
            # ADR-009. Pre-edit the observer was constructed + used + then
            # garbage-collected at run() exit; the Listener's `register_observer`
            # API was dead code because no caller wired it.
            from AgentEval.telemetry.listener import register_active_observer

            register_active_observer(observer)

        messages = [Message(role="user", content=prompt)]
        t0 = time.monotonic()
        response = self._provider.chat(messages=messages, model=self._model, **kwargs)
        latency_seconds = time.monotonic() - t0

        # Resolve mcp_coverage:
        # - With observer (mcp_servers non-empty): use observer.compute_coverage()
        #   so trust-floor + adapter-signaled external_mixed flows through.
        # - Without observer: trivially ``hosted_in_process`` per
        #   ``docs/contracts/mcp-coverage-detection.md`` D4 table (Generic
        #   LiteLLM has no external-config surface to detect).
        mcp_coverage = observer.compute_coverage() if observer is not None else "hosted_in_process"
        observed_tool_calls = list(observer.tool_calls()) if observer is not None else []

        result = AgentRunResult(
            response_text=response.text,
            tool_calls=observed_tool_calls,
            usage=Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cached_input_tokens=response.usage.cached_input_tokens,
            ),
            metadata=AgentRunMetadata(
                completeness="complete",
                mcp_coverage=mcp_coverage,
            ),
            cost_usd=float(response.cost_usd) if response.cost_usd is not None else 0.0,
            latency_seconds=latency_seconds,
            trace_id=uuid.uuid4().hex,
        )
        # Story 5.3: record run metadata for the RunManifest sidecar. No-op
        # when no Listener is active (direct Python invocation outside RF).
        _record_run_metadata(
            adapter_name=self.name,
            adapter_version=self.version,
            model=self._model,
            mcp_servers=_manifest_entries_from_servers(mcp_servers),
            total_cost_usd=result.cost_usd,
            completeness=result.metadata.completeness,
            mcp_coverage=result.metadata.mcp_coverage,
            prompt_hashes=[_hash_prompt(prompt)],
        )
        return result


def _attach_handle_to_observer(observer: HostedMcpObserver, name: str, handle: Any) -> None:
    """Attach the observer to the server backing an `MCPServerHandle`.

    Phase-1 scope (DF-5.2-S3 carve-out): only `transport="in_memory"`
    handles are wired through; subprocess + streamable_http transports
    fall through to `mark_external_mixed(reason)` since the subprocess
    wrapper + HTTP observer paths are deferred to Story 5.5 dogfood port.
    """
    transport = getattr(handle, "transport", None)
    if transport == "in_memory":
        factory = getattr(handle, "server_factory", None)
        if callable(factory):
            try:
                server = factory()
            except Exception as exc:  # noqa: BLE001
                observer.mark_external_mixed(
                    f"GenericAdapter could not build in-memory server "
                    f"{name!r} via handle.server_factory(): {type(exc).__name__}: {exc}"
                )
                return
            observer.attach(server, observation_path="hosted_in_process")
            return
        observer.mark_external_mixed(
            f"GenericAdapter handle {name!r} (transport='in_memory') has no "
            "callable `server_factory`; cannot attach observer in-process"
        )
        return
    if transport in ("stdio", "streamable_http"):
        # DF-5.2-S3: subprocess wrapper + HTTP observer paths deferred to
        # Story 5.5 dogfood port. Phase-1 degrades to external_mixed so
        # the run honestly reports the observation gap.
        observer.mark_external_mixed(
            f"GenericAdapter handle {name!r} (transport={transport!r}) requires "
            "the subprocess wrapper / HTTP observer integration deferred to "
            "DF-5.2-S3 (Story 5.5 dogfood port lands this); Phase-1 reports "
            "external_mixed for honesty"
        )
        return
    observer.mark_external_mixed(
        f"GenericAdapter handle {name!r} has unknown transport={transport!r}; "
        "expected one of 'in_memory', 'stdio', 'streamable_http'"
    )
