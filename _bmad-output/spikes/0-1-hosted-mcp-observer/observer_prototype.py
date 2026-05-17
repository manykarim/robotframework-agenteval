"""Spike prototype: hosted-MCP universal observer for Story 0.1.

THIS IS SCRATCH CODE for the Story 0.1 spike. Discarded after Story 0.3
ratifies ADR-007. Epic 5 Story 5.2 implements the production version
under `src/AgentEval/mcp/observer.py` against the ratified ADR.

Key finding: mcp Python SDK 1.27.1 does NOT expose a middleware API.
The only viable observation hook is `Server.request_handlers` dict mutation
— wrap the registered handler for `CallToolRequest` with an instrumentation
shim. This works for both lowlevel Server AND FastMCP (which composes
Server at the private `_mcp_server` attribute).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

import mcp.types as types
from mcp.server import Server
from mcp.server.fastmcp import FastMCP


# ---- Data shapes (spike-scoped; production lives in src/AgentEval/types.py) ----

McpCoverage = Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]


@dataclass
class ToolCallTrace:
    """One tool call observed by the hosted MCP observer."""

    sequence_index: int
    tool_name: str
    arguments: dict[str, Any]
    result_summary: str
    latency_ms: float
    transport: str  # "in_memory" | "stdio" | "streamable_http" | "external"
    observation_path: str  # "hosted_in_process" | "subprocess_with_observer" | "external"
    started_at_unix: float
    test_id: str | None = None


@dataclass
class AgentRunResult:
    """Spike-scoped AgentRunResult. Production version per ADR-A6 / FR36b."""

    run_id: str
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    mcp_coverage: McpCoverage = "external_mixed"  # safe default per ADR-A6
    metadata: dict[str, Any] = field(default_factory=dict)


# ---- The observer ----


class HostedMcpObserver:
    """Wraps Server.request_handlers[CallToolRequest] for observation.

    Works against both `mcp.server.lowlevel.Server` AND `mcp.server.fastmcp.FastMCP`
    (the latter exposes `_mcp_server` which is a lowlevel Server instance).

    Lifecycle:
        observer = HostedMcpObserver(transport="in_memory")
        observer.attach(server)        # wraps request_handlers[CallToolRequest]
        # ... run agent ...
        result = observer.finalize()   # returns AgentRunResult with mcp_coverage
    """

    def __init__(self, transport: str, test_id: str | None = None) -> None:
        self.transport = transport
        self.test_id = test_id
        self._traces: list[ToolCallTrace] = []
        self._seq = 0
        self._attached_servers: list[Server[Any]] = []
        # external_mixed reasons accumulate (do NOT overwrite per D4 + review F-edge-6).
        # Declared field, not ad-hoc attribute, so mypy + IDE catch typos at refactor time.
        self._external_mixed_reasons: list[str] = []

    def _resolve_lowlevel(self, server: Server[Any] | FastMCP) -> Server[Any]:
        if isinstance(server, FastMCP):
            return server._mcp_server  # type: ignore[attr-defined]
        return server

    def attach(self, server: Server[Any] | FastMCP, observation_path: str = "hosted_in_process") -> None:
        """Wrap the CallToolRequest handler on `server`.

        observation_path:
            - "hosted_in_process": server runs in the same process as the library
            - "subprocess_with_observer": server runs as a subprocess that the library spawned
              and instrumented via a wrapper-script that proxies calls (NOT modeled in this
              spike's in-process attach() — see subprocess_observer.py for that path).
        """
        lowlevel = self._resolve_lowlevel(server)
        handler = lowlevel.request_handlers.get(types.CallToolRequest)
        if handler is None:
            # Spec: a server that has no tools registered yet. Defer wrapping until call_tool
            # is registered. For the spike: we require tools be registered before attach().
            raise RuntimeError(
                "Observer.attach() called before server.call_tool() was registered. "
                "Register tools first, then attach()."
            )

        observed_path = observation_path
        observer = self

        async def wrapped_handler(req: types.CallToolRequest) -> types.ServerResult:
            tool_name = req.params.name
            arguments = dict(req.params.arguments or {})
            started = time.time()
            try:
                result = await handler(req)
            except Exception:
                # Even on failure, record the attempt with observation_path
                observer._record(
                    tool_name=tool_name,
                    arguments=arguments,
                    result_summary="<exception>",
                    latency_ms=(time.time() - started) * 1000,
                    observation_path=observed_path,
                    started=started,
                )
                raise
            observer._record(
                tool_name=tool_name,
                arguments=arguments,
                result_summary=_summarize_result(result),
                latency_ms=(time.time() - started) * 1000,
                observation_path=observed_path,
                started=started,
            )
            return result

        lowlevel.request_handlers[types.CallToolRequest] = wrapped_handler
        self._attached_servers.append(lowlevel)
        # NOTE: `_library_hosted` and `_has_subprocess_observation` removed — they were dead code
        # (review F-blind-2). Coverage is now derived strictly from `paths_observed` in finalize().

    def _record(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        result_summary: str,
        latency_ms: float,
        observation_path: str,
        started: float,
    ) -> None:
        self._seq += 1
        self._traces.append(
            ToolCallTrace(
                sequence_index=self._seq,
                tool_name=tool_name,
                arguments=arguments,
                result_summary=result_summary,
                latency_ms=latency_ms,
                transport=self.transport,
                observation_path=observation_path,
                started_at_unix=started,
                test_id=self.test_id,
            )
        )

    def mark_external_mixed(self, reason: str) -> None:
        """Caller signals that at least one tool call went to an MCP server the
        observer did NOT instrument (external_mixed degradation).

        Per ADR-A6, the safe default on path failure is `external_mixed`.
        This method is explicit acknowledgement that the run touched uninstrumented servers.
        Multiple calls accumulate reasons (do NOT overwrite — production observer needs
        full forensic trail per D4 ratified ADR-A6 adapter contract).
        """
        if reason is None or reason == "":
            return  # do not register empty signals — caller should pass a real reason
        self._external_mixed_reasons.append(reason)

    def finalize(self) -> AgentRunResult:
        """Produce the run result. Computes mcp_coverage per ADR-A6 D1 trust-floor rule.

        Decision tree (D1 trust-floor: strongest complete path wins):
        - If any external_mixed signal raised → "external_mixed" (path failure dominates)
        - Else if at least one trace's path is "hosted_in_process"
              → "hosted_in_process" (strongest complete path observed)
        - Else if at least one trace's path is "subprocess_with_observer"
              → "subprocess_with_observer"
        - Else (no traces AND no signals) → "external_mixed" (catch-all safe default)

        Rationale per D1: a run that observed BOTH hosted_in_process AND subprocess_with_observer
        successfully gets credit for the STRONGER path. `external_mixed` is reserved for runs
        with a known uninstrumented gap (explicit signal from adapter or empty observations).
        """
        coverage: McpCoverage
        external_mixed_signal = bool(self._external_mixed_reasons)
        paths_observed = {t.observation_path for t in self._traces}

        # Decision order matches strongest-to-weakest trust ordering per D1.
        # The ordering MUST match findings doc §Verdict ADR-A6 amendment.
        if external_mixed_signal:
            coverage = "external_mixed"
        elif "hosted_in_process" in paths_observed:
            coverage = "hosted_in_process"
        elif "subprocess_with_observer" in paths_observed:
            coverage = "subprocess_with_observer"
        else:
            coverage = "external_mixed"

        # observed_paths ordered strongest-to-weakest per the same trust ordering,
        # NOT alphabetical (P-blind-14 fix).
        trust_order = ("hosted_in_process", "subprocess_with_observer", "external_mixed")
        observed_paths_ordered = [p for p in trust_order if p in paths_observed]

        return AgentRunResult(
            run_id=str(uuid.uuid4()),
            tool_calls=list(self._traces),
            mcp_coverage=coverage,
            metadata={
                "transport": self.transport,
                "test_id": self.test_id,
                "external_mixed_reasons": list(self._external_mixed_reasons),
                "observed_paths": observed_paths_ordered,
            },
        )


def _summarize_result(result: Any) -> str:
    """One-line summary of a ServerResult for trace logging."""
    try:
        if hasattr(result, "root") and hasattr(result.root, "content"):
            blocks = result.root.content
            if blocks and hasattr(blocks[0], "text"):
                txt = blocks[0].text
                return (txt[:80] + "...") if len(txt) > 80 else txt
        return f"<{type(result).__name__}>"
    except Exception:  # pragma: no cover - defensive
        return "<unknown>"


# ---- Trace persistence (JSONL — Phase 1 backend per architecture.md telemetry.backends) ----


def write_jsonl(path: str, result: AgentRunResult) -> None:
    """Write the run result as a single JSONL line. Append-mode safe for pabot concurrent writes."""
    record = {
        "run_id": result.run_id,
        "mcp_coverage": result.mcp_coverage,
        "tool_call_count": len(result.tool_calls),
        "metadata": result.metadata,
        "tool_calls": [
            {
                "sequence_index": t.sequence_index,
                "tool_name": t.tool_name,
                "arguments": t.arguments,
                "result_summary": t.result_summary,
                "latency_ms": round(t.latency_ms, 3),
                "transport": t.transport,
                "observation_path": t.observation_path,
                "started_at_unix": t.started_at_unix,
                "test_id": t.test_id,
            }
            for t in result.tool_calls
        ],
    }
    # O_APPEND on POSIX is atomic for writes ≤ PIPE_BUF (4096 on Linux);
    # a JSON line per run is well under that limit.
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
