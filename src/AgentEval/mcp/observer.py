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

"""Hosted-MCP universal trace observer (Story 5.2 / FR35 / ADR-004).

Per ADR-004 ratified 2026-05-17 + Story 0.1 spike findings: agenteval
observes every `tools/call` server-side by wrapping
`Server.request_handlers[CallToolRequest]` at runtime — a dict-mutation
pattern. Works for `mcp.server.lowlevel.Server` AND
`mcp.server.fastmcp.FastMCP` (latter via the `_mcp_server` private attribute
the mcp SDK itself uses internally per `mcp/shared/memory.py:64`).

Why not subclassing / middleware:
    The mcp SDK 1.27+ exposes no middleware or interceptor API. Subclassing
    works but would force every consumer to use our subclass instead of
    `mcp.server.Server`/`FastMCP` directly. Dict-mutation is more flexible:
    consumers construct their servers normally + we attach post-construction.

3-value `mcp_coverage` per ADR-016 D1 trust-floor:
    - ``hosted_in_process`` — observer attached to an in-memory FastMCP/Server.
    - ``subprocess_with_observer`` — observer attached via the subprocess
      wrapper at stdio bootstrap (see ``_observer_subprocess_wrapper.py``).
    - ``external_mixed`` — adapter signaled external MCP configs present
      (e.g., Claude Code CLI detected `~/.claude.json` or `.mcp.json`); OR
      no library-hosted server attached. Detection-failure default per
      ADR-016 D1: ``external_mixed`` is safer than ``hosted_in_process``.

`AdapterVersionDriftWarning` (per ADR-004 Consequences + spike findings
§Limitations): emitted on first ``attach()`` call when the installed
``mcp`` SDK version is outside the tested range. Mitigates the
``request_handlers`` + ``_mcp_server`` private-attribute access risk.

References:
    - ADR-004: ``docs/adr/ADR-004-hosted-mcp-observation.md``
    - ADR-016: ``docs/adr/ADR-016-mcp-coverage-detection-default.md``
    - Spike findings: ``_bmad-output/spikes/spike-hosted-mcp-observer-findings.md``
    - Story 1b.2 ``trace_store`` projection accessors: source of truth for
      `ToolCallTrace` shape consumed downstream.
"""

from __future__ import annotations

import importlib.metadata
import time
import uuid
import warnings
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal

from AgentEval.types import ToolCallTrace

if TYPE_CHECKING:
    from mcp.server.lowlevel import Server

__all__ = [
    "HostedMcpObserver",
    "AdapterVersionDriftWarning",
    "ObservationPath",
    "MCPCoverage",
]


ObservationPath = Literal["hosted_in_process", "subprocess_with_observer"]
"""The strongest-complete-path values the observer can directly stamp on captured records."""

MCPCoverage = Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"]
"""3-value coverage Literal per ADR-016 D1 trust-floor."""


# Tested mcp SDK version range per ADR-004 + spike findings.
# Story 5.2 code-review 1-way Auditor HIGH-H fix 2026-05-20: pre-edit cited
# NFR-COMPAT-06 which governs OpenTelemetry, not mcp. The mcp SDK pin lives
# at NFR-COMPAT-04 (`mcp>=1.0,<2.0`) — but Story 0.1 spike empirically
# validated against mcp 1.27.x, so the OBSERVER floor (1, 27) is tighter
# than NFR-COMPAT-04's PRD floor of 1.0. The observer warns about ANY
# version outside its tested range so consumers running mcp 1.0..1.26 get
# advance notice that the wrap pattern wasn't empirically validated for
# their version even though it's within the PRD floor.
_TESTED_MCP_VERSION_FLOOR = (1, 27)
_TESTED_MCP_VERSION_CEILING = (2, 0)


class AdapterVersionDriftWarning(UserWarning):
    """Warned when the installed mcp SDK version is outside the tested range.

    Per ADR-004 Consequences + Story 0.1 spike findings §Limitations: the
    observer accesses ``Server.request_handlers`` + ``FastMCP._mcp_server``,
    both technically internal in the mcp SDK. A major-version bump could
    replace dict-dispatch with a closed registration mechanism. This
    warning gives operators advance notice + a paper trail when the
    coupling breaks in production.
    """


@dataclass
class _ObserverState:
    """Internal mutable state — guarded by an RLock on the parent observer.

    Frozen=False because we mutate `tool_calls` + `external_mixed_reason`
    on every observed call + on every adapter cooperation signal. The
    surrounding HostedMcpObserver wraps mutations behind a thread-safe
    interface so consumers don't have to reason about concurrent access.
    """

    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    observation_paths: set[ObservationPath] = field(default_factory=set)
    external_mixed_reasons: list[str] = field(default_factory=list)
    attached_servers: list[Any] = field(default_factory=list)
    version_drift_warned: bool = False
    sequence_counter: int = 0


class HostedMcpObserver:
    """Records `tools/call` traffic on library-hosted MCP servers.

    Per ADR-004 + spike findings, the canonical pattern is:

        observer = HostedMcpObserver()
        observer.attach(my_fastmcp_server, observation_path="hosted_in_process")
        # ... agent runs against my_fastmcp_server ...
        coverage = observer.compute_coverage()  # "hosted_in_process"
        traces = observer.tool_calls()  # list[ToolCallTrace]

    Adapter cooperation per ADR-016 D4: when the adapter detects external
    MCP configs (e.g., Claude Code CLI parses `~/.claude.json`), it calls
    ``mark_external_mixed(reason)`` to flag the run. ``compute_coverage()``
    then resolves to ``"external_mixed"`` even if hosted observation also
    fired — adapter-signaled external presence is the source-of-truth.

    Thread-safety: all public methods are guarded by an RLock so concurrent
    use under pabot worker reuse + multi-threaded tool dispatch is safe.
    Per-test cleanup via ``clear()`` is called by Story 5.1's Listener at
    ``end_test`` (Listener has a registry of observers; Story 5.2 adds
    ``Listener.register_observer``).
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._state = _ObserverState()

    # ---------------------------------------------------------------- #
    # Public API — adapters + Listener consume these.
    # ---------------------------------------------------------------- #

    def attach(
        self,
        server: Server | Any,
        observation_path: ObservationPath = "hosted_in_process",
    ) -> None:
        """Wrap the server's `CallToolRequest` handler to record every tool call.

        Args:
            server: A `mcp.server.lowlevel.Server` instance OR a
                `mcp.server.fastmcp.FastMCP` instance. For FastMCP, the
                observer accesses the `_mcp_server` private attribute per
                ADR-004 (the mcp SDK itself uses the same coupling
                internally — see `mcp/shared/memory.py:64`).
            observation_path: ``"hosted_in_process"`` for in-memory
                FastMCP/Server; ``"subprocess_with_observer"`` when called
                from the subprocess wrapper bootstrap. ``"external_mixed"``
                is NOT a valid attach path — adapters use
                ``mark_external_mixed(reason)`` instead.

        Raises:
            AdapterVersionDriftWarning: on first attach if the installed
                mcp SDK version is outside the tested range.
            TypeError: if `server` is neither a Server nor FastMCP instance.

        Idempotency: attaching the same server twice is a no-op (the wrap
        is only applied once per server-id). This keeps the under-pabot-
        worker-reuse case clean.
        """
        with self._lock:
            self._maybe_emit_version_drift_warning()
            lowlevel = self._resolve_lowlevel_server(server)
            # Story 5.2 code-review 2-way HIGH-B fix 2026-05-20 (Blind H3 +
            # Edge-cases H2 empirical probe): pre-edit idempotency only
            # protected against the SAME observer re-attaching; a SECOND
            # HostedMcpObserver attaching to the same Server would wrap
            # the first observer's `_wrapped` as its "original" handler,
            # chaining wraps + double-recording tool calls. The fix:
            # ALSO refuse to wrap when the handler already carries the
            # `_agenteval_observer_wrap` sentinel (set by any prior
            # observer's wrap installation below). The new observer
            # still records its observation_path, but the existing
            # observer remains the recording sink — adapters that need
            # per-call traces should reuse the observer instance attached
            # to the server, OR explicitly clear() between consumers.
            if any(s is lowlevel for s in self._state.attached_servers):
                self._state.observation_paths.add(observation_path)
                return
            wrapped = self._wrap_call_tool_handler(lowlevel, observation_path)
            self._state.attached_servers.append(lowlevel)
            # Only credit the observation_path when the wrap was actually
            # installed. Story 5.2 code-review HIGH-I fix 2026-05-20
            # (Edge-cases H1): pre-edit recorded the path even when the
            # handler-was-missing fallback silently no-op'd, lying-by-
            # omission that compute_coverage() reports `hosted_in_process`
            # when ZERO observation can happen. Now an unwrapped attach
            # leaves observation_paths untouched → compute_coverage
            # honestly degrades to external_mixed (detection-failure
            # default per ADR-016 D1).
            if wrapped:
                self._state.observation_paths.add(observation_path)

    def mark_external_mixed(self, reason: str) -> None:
        """Signal adapter-detected external MCP configs per ADR-016 D4.

        Adapters (Claude Code CLI, Copilot CLI) parse their on-disk MCP
        configs at run-time. When external configs are present, the
        adapter calls this method with a human-readable reason. The
        observer records the reason + ``compute_coverage()`` will resolve
        to ``"external_mixed"`` regardless of whether hosted observation
        also fired.

        Args:
            reason: Operator-facing explanation of WHY the run degraded.
                Surfaces in ``IncompleteTraceError.fix_suggestion`` per FR37.
        """
        with self._lock:
            self._state.external_mixed_reasons.append(reason)

    def compute_coverage(self) -> MCPCoverage:
        """Resolve the 3-value `mcp_coverage` per ADR-016 D1 trust-floor.

        Decision tree:

        1. If ANY ``mark_external_mixed()`` was called → ``"external_mixed"``.
           Adapter-signaled external presence is the source-of-truth.
        2. Else, if ``"hosted_in_process"`` was observed → ``"hosted_in_process"``.
           Strongest path wins per spike findings §Verdict.
        3. Else, if ``"subprocess_with_observer"`` was observed → ``"subprocess_with_observer"``.
        4. Else → ``"external_mixed"`` (detection-failure default per
           ADR-016 D1: safer than claiming hosted observation when nothing
           was observed).
        """
        with self._lock:
            if self._state.external_mixed_reasons:
                return "external_mixed"
            if "hosted_in_process" in self._state.observation_paths:
                return "hosted_in_process"
            if "subprocess_with_observer" in self._state.observation_paths:
                return "subprocess_with_observer"
            return "external_mixed"

    def tool_calls(self) -> list[ToolCallTrace]:
        """Return the chronological list of observed `ToolCallTrace` records.

        Each record has ``source="hosted_mcp"`` per FR35, distinguishing
        from adapter-side traces (``source="adapter"``). Returned list is
        a defensive shallow copy.
        """
        with self._lock:
            return list(self._state.tool_calls)

    def external_mixed_reasons(self) -> list[str]:
        """Return the chronological list of adapter-signaled external-mixed reasons.

        Defensive shallow copy; consumer mutations don't leak.
        """
        with self._lock:
            return list(self._state.external_mixed_reasons)

    def clear(self) -> None:
        """Reset all observer state — called by Story 5.1's Listener at `end_test`.

        Per-test cleanup contract per ADR-009 (per-test MCP scope). After
        ``clear()``, the observer is reusable for the next test — attached
        servers stay attached (the wrap is idempotent), but ``tool_calls``,
        ``external_mixed_reasons``, and the sequence counter all reset.

        The handler wrap on the attached servers is NOT removed — pabot
        worker reuse + per-test scope means servers may be re-used across
        tests, and the wrap is idempotent so re-attaching wouldn't hurt
        either. We just need to forget the records.
        """
        with self._lock:
            self._state.tool_calls.clear()
            self._state.external_mixed_reasons.clear()
            self._state.sequence_counter = 0

    # ---------------------------------------------------------------- #
    # Internal helpers.
    # ---------------------------------------------------------------- #

    @staticmethod
    def _resolve_lowlevel_server(server: Any) -> Server:
        """Return the lowlevel ``Server`` instance from either a ``Server`` or ``FastMCP``.

        Per ADR-004: FastMCP composes a lowlevel Server at ``_mcp_server``.
        We access the private attribute (the mcp SDK itself does the same
        internally per `mcp/shared/memory.py:64`); no public hook exists
        in mcp 1.27.
        """
        # Lazy import to keep the module import-light + tolerate
        # mcp SDK absence in environments that don't need MCP.
        try:
            from mcp.server.fastmcp import FastMCP
            from mcp.server.lowlevel import Server
        except ImportError as exc:  # pragma: no cover — mcp is a required dep
            raise RuntimeError("HostedMcpObserver requires the `mcp` SDK to be installed") from exc

        if isinstance(server, Server):
            return server
        if isinstance(server, FastMCP):
            # _mcp_server is the canonical access path per ADR-004 + the
            # mcp SDK's own internal usage (mcp/shared/memory.py:64).
            return server._mcp_server  # noqa: SLF001 — see docstring
        raise TypeError(
            f"HostedMcpObserver.attach: expected `Server` or `FastMCP` instance, "
            f"got {type(server).__name__}; see ADR-004 for the supported types"
        )

    def _wrap_call_tool_handler(self, server: Server, observation_path: ObservationPath) -> bool:
        """Replace `server.request_handlers[CallToolRequest]` with a wrap that records each call.

        Returns:
            ``True`` if the wrap was installed; ``False`` if the wrap was
            skipped (no handler registered yet OR another observer's
            sentinel-marked wrap is already in place). Callers use the
            return value to decide whether to credit the observation_path
            (Story 5.2 code-review HIGH-I fix 2026-05-20).
        """
        # Lazy import.
        from mcp import types as mcp_types

        original_handler: Callable[..., Awaitable[Any]] | None = server.request_handlers.get(mcp_types.CallToolRequest)
        if original_handler is None:
            # Story 5.2 code-review HIGH-I fix 2026-05-20 (Edge-cases H1):
            # No `CallToolRequest` handler is registered yet — either the
            # server has zero tools OR tools were registered via a path
            # that doesn't populate the dict. Either way, our wrap would
            # be a no-op (the SDK overwrites the dict at later
            # registration time). Return False so the caller skips
            # crediting the observation_path; compute_coverage will then
            # honestly resolve to external_mixed per ADR-016 D1
            # detection-failure default.
            return False
        if getattr(original_handler, "_agenteval_observer_wrap", False):
            # Story 5.2 code-review 2-way HIGH-B fix 2026-05-20: another
            # HostedMcpObserver already wrapped this server's handler.
            # Refuse to stack a second wrap (which would chain + double-
            # record). Caller still credits the observation_path because
            # the first observer's wrap continues to record observations
            # honestly; this observer just doesn't get its own records.
            return True

        observer_state = self._state
        observer_lock = self._lock

        async def _wrapped(req: Any) -> Any:
            t0 = time.monotonic()
            error_msg: str | None = None
            result: Any = None
            tool_name = getattr(getattr(req, "params", None), "name", "<unknown>")
            tool_args = getattr(getattr(req, "params", None), "arguments", None) or {}
            try:
                result = await original_handler(req)
                return result
            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                latency_ms = (time.monotonic() - t0) * 1000.0
                with observer_lock:
                    observer_state.sequence_counter += 1
                    trace = ToolCallTrace(
                        name=tool_name,
                        args=dict(tool_args) if isinstance(tool_args, dict) else {},
                        result=_summarize_result(result) if error_msg is None else None,
                        error=error_msg,
                        latency_ms=latency_ms,
                        source="hosted_mcp",
                        gen_ai_tool_call_id=uuid.uuid4().hex,
                        sequence_index=observer_state.sequence_counter,
                    )
                    observer_state.tool_calls.append(trace)
                    _ = observation_path  # observation_path stays in state; not on trace

        # Story 5.2 code-review 2-way HIGH-B fix 2026-05-20: mark the wrap
        # with a sentinel so a second observer's attach() can detect it
        # and refuse to chain wraps.
        _wrapped._agenteval_observer_wrap = True  # type: ignore[attr-defined]
        server.request_handlers[mcp_types.CallToolRequest] = _wrapped
        return True

    def _maybe_emit_version_drift_warning(self) -> None:
        """Emit `AdapterVersionDriftWarning` on first attach if mcp version is outside tested range."""
        if self._state.version_drift_warned:
            return
        try:
            raw_version = importlib.metadata.version("mcp")
        except importlib.metadata.PackageNotFoundError:  # pragma: no cover
            self._state.version_drift_warned = True
            return
        try:
            parts = raw_version.split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) >= 2 else 0
        except (ValueError, IndexError):
            # Non-standard version string — emit drift warning conservatively.
            warnings.warn(
                f"mcp SDK version {raw_version!r} couldn't be parsed for compatibility "
                "check against ADR-004's tested range; observer wrap may break silently. "
                "See ADR-004 + spike findings §Limitations for context.",
                AdapterVersionDriftWarning,
                stacklevel=3,
            )
            self._state.version_drift_warned = True
            return

        current = (major, minor)
        if current < _TESTED_MCP_VERSION_FLOOR or current >= _TESTED_MCP_VERSION_CEILING:
            warnings.warn(
                f"mcp SDK version {raw_version!r} is outside the tested range "
                f"[{'.'.join(map(str, _TESTED_MCP_VERSION_FLOOR))}, "
                f"{'.'.join(map(str, _TESTED_MCP_VERSION_CEILING))}) per ADR-004. "
                "The observer's `Server.request_handlers` + `FastMCP._mcp_server` "
                "couplings are not advertised stability surfaces; a major bump "
                "could replace dict-dispatch with a closed registration mechanism. "
                "Validate observer behavior before relying on captured traces.",
                AdapterVersionDriftWarning,
                stacklevel=3,
            )
        self._state.version_drift_warned = True


def _summarize_result(result: Any) -> Any:
    """Best-effort summarization of an `mcp.types.ServerResult` for trace records.

    Phase-1 carve: we don't deep-walk the result structure; we return a
    short string representation safe for OTel attribute serialization
    downstream (`agenteval.tool.result` is a primitive-or-JSON-string per
    architecture L1008).
    """
    if result is None:
        return None
    # Best effort: try str(); fall back to repr() on TypeError.
    try:
        text = str(result)
    except Exception:  # noqa: BLE001
        text = repr(result)
    # Truncate aggressively — traces shouldn't bloat memory.
    if len(text) > 1024:
        text = text[:1021] + "..."
    return text
