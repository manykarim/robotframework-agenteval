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

"""MCP server lifecycle keyword implementation (Story 3.1).

Per Story 3.1 Phase-1 design (mirrors agentguard's per-call-session
pattern; see `feedback_agentguard_inspiration_not_dependency`): the
keywords return lightweight handles that capture the connection
parameters; each subsequent operation (initialize, list tools, call
tool) re-opens the MCP session via the SDK + tears down at the end of
the keyword call. This avoids the "keep async session alive across
sync keyword calls" complexity that would otherwise require a
background-thread event loop.

Phase-1 trade-off documented honestly: stdio transport pays the
subprocess-startup latency on every `connect_to_server` call. The
overhead is captured separately via NFR-PERF metrics (NOT via tier
badge — these are still Tier-1 keywords, deterministic given same env
+ server binary). Phase-1.5 OR Epic 5 may add a pooled
`MCPLifecycleManager`-backed session-reuse path; Story 3.1 deliberately
ships the simpler shape first.

Architecture compliance:
- Stories 2.1-2.4 lessons inherited: no eager re-export; behavioral
  probes for tests; structured attrs on errors; deviation-tracker
  docstrings.
- `_kernel.run_async._run_async` bridges async SDK ↔ sync RF keyword
  per ADR-012 (no bare `async def @keyword`).
- `UnsupportedMCPVersionError` raised post-initialize per FR8 + FR46
  + AC-MCP-OBSERVE-02; structured attrs (`server_version`,
  `supported_range`) populated for programmatic consumers.
- `MCPLibrary` remains EXCLUDED from `_SUB_LIBRARIES` per Story 2.2
  collision-prevention norm.

Phase-1 scope (Story 3.1 carve-out):
- `stdio` + `in_memory` transports fully supported.
- `streamable_http` accepted as a transport name + passes through to
  the SDK's `streamablehttp_client`, but Phase-1 doesn't ship an HTTP
  echo fixture; full round-trip is deferred to Phase-1.5 OR Epic 3
  Story 3.2.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from AgentEval._kernel.run_async import _run_async
from AgentEval.errors import UnsupportedMCPVersionError
from AgentEval.mcp.transport import (
    Transport,
    open_in_memory_session,
    open_stdio_session,
)
from AgentEval.mcp.version_gate import check_protocol_version

__all__ = [
    "MCPServerHandle",
    "MCPSession",
    "start_server",
    "connect_to_server",
    "stop_server",
]


@dataclass(frozen=True)
class MCPServerHandle:
    """A handle describing how to (re-)open an MCP session to a server.

    The handle does NOT hold a live MCP client session (Story 3.1
    Phase-1 design: each operation re-opens). Subsequent keywords
    consume the handle to re-establish the session for THAT operation
    only.

    Story 3.1 design notes:
    - Stories using a long-lived session pattern (Phase-1.5 or Epic 5)
      will introduce a sibling `MCPSession` handle backed by a
      background event loop. The two coexist.
    - `frozen=True` for immutability; the `kwargs` dict is shallow-
      copied at construction per Story 1b.2 M_R6 pattern.
    """

    name: str
    transport: Transport
    # stdio-specific:
    command: str | None = None
    args: tuple[str, ...] = ()
    env: dict[str, str] | None = None
    # in_memory-specific: a no-arg callable returning a FastMCP server.
    server_factory: Callable[[], Any] | None = None
    # Story 3.1 code-review Codex LOW (2026-05-19): removed the
    # `extra: dict[str, Any]` field — `frozen=True` doesn't seal dict
    # mutation, so the field gave a false sense of immutability AND
    # was unused. Sub-libraries that need per-handle metadata can
    # introduce a typed extension dataclass when needed.


@dataclass(frozen=True)
class MCPSession:
    """Post-`Connect To Server` session metadata.

    Carries the negotiated MCP protocol version + server info AFTER a
    successful `initialize()` + version-gate pass. NOT a live session —
    the SDK session was torn down at the end of `connect_to_server`
    per Phase-1 per-call-session design.
    """

    name: str
    transport: Transport
    protocol_version: str
    server_info: dict[str, Any]


def start_server(
    *,
    name: str,
    transport: Transport,
    command: str | None = None,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    server_factory: Callable[[], Any] | None = None,
) -> MCPServerHandle:
    """Build an `MCPServerHandle` describing a server target.

    Per Story 3.1 Phase-1 design, this does NOT spawn a subprocess for
    `stdio` (the spawn happens during `connect_to_server`). The
    function is a pure constructor that validates the transport-
    appropriate parameters.

    Args:
        name: Caller-chosen identifier for the server (echoed back in
            error messages and handle representation).
        transport: One of `"stdio"`, `"streamable_http"`, `"in_memory"`
            per PRD FR7.
        command: stdio only — the executable name (e.g., `"python"`).
        args: stdio only — command-line arguments.
        env: stdio only — environment overlay.
        server_factory: in_memory only — no-arg callable returning a
            `FastMCP` server instance.

    Returns:
        `MCPServerHandle` describing the server target. Pass to
        `connect_to_server` to open + initialize a session.

    Raises:
        ValueError: If transport-required parameters are missing.
    """
    if transport == "stdio":
        if not command:
            raise ValueError("stdio transport requires `command`")
    elif transport == "in_memory":
        if server_factory is None:
            raise ValueError("in_memory transport requires `server_factory`")
    elif transport == "streamable_http":
        # Phase-1 passthrough: the keyword accepts the transport name
        # so future stories don't need a breaking change. Real HTTP
        # round-trip support lands in Phase-1.5 OR Epic 3 Story 3.2.
        # No required-parameter check today; future work will add
        # URL validation.
        pass
    else:
        raise ValueError(
            f"unsupported transport {transport!r}; must be one of 'stdio' | 'streamable_http' | 'in_memory' per PRD FR7"
        )
    # Story 3.1 code-review HIGH (Blind + Edge-cases 2-way 2026-05-19):
    # `env=dict(env) if env else None` collapses an empty dict `{}` to
    # `None`. SDK semantics differ: `env=None` → inherit parent; `env={}`
    # → strip all parent env. Use `is not None` so both shapes are
    # round-trip-preserved.
    return MCPServerHandle(
        name=name,
        transport=transport,
        command=command,
        args=tuple(args or ()),
        env=dict(env) if env is not None else None,
        server_factory=server_factory,
    )


def connect_to_server(handle: MCPServerHandle) -> MCPSession:
    """Open a fresh MCP `ClientSession`, run `initialize()`, gate-check the version.

    Per Story 3.1 Phase-1 design (per-call session): this function
    opens the session, runs the handshake, captures the negotiated
    protocol version + server info, then closes the session. The
    returned `MCPSession` carries the metadata for the caller's
    assertions; the underlying SDK session is no longer live.

    Args:
        handle: An `MCPServerHandle` from `start_server`.

    Returns:
        `MCPSession` with negotiated `protocol_version` + `server_info`.

    Raises:
        ValueError: If transport is `streamable_http` (Phase-1
            passthrough; no implementation yet).
        UnsupportedMCPVersionError: If the negotiated protocol version
            is outside the `mcp>=1.0,<2.0` range per
            `version_gate.check_protocol_version`.
    """
    if handle.transport == "streamable_http":
        raise ValueError(
            "streamable_http transport is Phase-1 passthrough; full HTTP "
            "round-trip support is deferred to Phase-1.5 OR Epic 3 Story 3.2"
        )

    # Story 3.1 code-review HIGH (Blind 2026-05-19): replace bare
    # `assert` (stripped under `python -O` / PYTHONOPTIMIZE) with
    # typed `ValueError` so direct `MCPServerHandle` construction
    # (bypassing `start_server`) still surfaces a clean failure.
    if handle.transport == "stdio" and not handle.command:
        raise ValueError("stdio transport requires `command` on the handle")
    if handle.transport == "in_memory" and handle.server_factory is None:
        raise ValueError("in_memory transport requires `server_factory` on the handle")

    async def _drive() -> MCPSession:
        if handle.transport == "stdio":
            assert handle.command is not None  # for mypy; checked above
            ts = await open_stdio_session(
                command=handle.command,
                args=list(handle.args),
                env=handle.env,
            )
        elif handle.transport == "in_memory":
            assert handle.server_factory is not None  # for mypy; checked above
            ts = await open_in_memory_session(handle.server_factory)
        else:
            # Defense-in-depth (Blind MED 2026-05-19): explicit else
            # raises rather than falling through to in_memory. The
            # caller-facing branch at the top of `connect_to_server`
            # already rejected `streamable_http`; any other value is
            # a programmatic error.
            raise ValueError(f"unsupported transport on handle: {handle.transport!r}")

        # Story 3.1 code-review HIGH (Edge-cases + Codex 2-way 2026-05-19):
        # run `initialize()` UNDER agenteval control + map the SDK's
        # bare `RuntimeError("Unsupported protocol version...")` to
        # typed `UnsupportedMCPVersionError`. The pre-edit shape
        # let the SDK error escape (AC-MCP-OBSERVE-02 was fake-green
        # on stdio).
        try:
            try:
                init_result = await ts.session.initialize()
            except RuntimeError as exc:
                if "Unsupported protocol version" in str(exc):
                    # SDK-first reject path: the SDK detected an
                    # out-of-range version BEFORE returning the
                    # `InitializeResult`. Extract the version string
                    # from the SDK's message + raise our typed error.
                    raw = str(exc)
                    # SDK message format:
                    # `Unsupported protocol version from the server: <version>`
                    server_version = raw.split(":", 1)[-1].strip() if ":" in raw else None
                    raise UnsupportedMCPVersionError(
                        f"MCP server version {server_version} outside library tested range mcp>=1.0,<2.0",
                        server_version=server_version,
                        supported_range="mcp>=1.0,<2.0",
                    ) from exc
                raise
            # Agenteval-late-gate: even if the SDK accepted the
            # version, run our own check (defense-in-depth; catches
            # cases where the SDK's allowlist drifts ahead of ours).
            negotiated = getattr(init_result, "protocolVersion", None)
            check_protocol_version(negotiated)
            server_info_raw = getattr(init_result, "serverInfo", None)
            if server_info_raw is None:
                server_info_dict: dict[str, Any] = {}
            elif hasattr(server_info_raw, "model_dump"):
                server_info_dict = server_info_raw.model_dump()
            elif isinstance(server_info_raw, dict):
                server_info_dict = dict(server_info_raw)
            else:
                server_info_dict = {}
            return MCPSession(
                name=handle.name,
                transport=handle.transport,
                protocol_version=negotiated or "",
                server_info=server_info_dict,
            )
        finally:
            await ts.stack.aclose()

    return _run_async(_drive())


def stop_server(handle: MCPServerHandle) -> None:
    """Tear down any per-handle resources.

    Per Story 3.1 Phase-1 design: each operation self-cleans (the SDK
    session is torn down at the end of `connect_to_server`). So
    `stop_server` is a no-op today — but the keyword surface ships
    now so .robot tests can use the canonical 3-step lifecycle without
    breaking when Phase-1.5 introduces pooled sessions that need
    explicit teardown.

    Args:
        handle: The `MCPServerHandle` to release.
    """
    # Phase-1: no-op. Phase-1.5 may close a pooled session keyed by
    # `handle.name`.
    _ = handle
