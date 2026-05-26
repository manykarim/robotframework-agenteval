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

# ruff: noqa: E501
# Browser-Library-style docstring tables can carry long descriptions
# on a single physical line. Per-line 120-char limit waived for this
# file per Phase 7 docstring-refresh proposal (2026-05-26).

"""MCP sub-library — `.mcp.json` static-inspection + Phase-1 lifecycle + discoverability keywords.

Static-inspection keywords (Story 2.3 / PRD FR5 + FR6):
- `Get Server Config` — parse a `.mcp.json` server-config file into a
  dict mapping `<server_name>` → entry (`command`, `args`, `env`,
  `transport`, `tools`).
- `Get Tool Schema` — return the JSON Schema for a declared tool from
  the Phase-1 `.mcp.json:tools` extension (Phase-2 + Epic 3 add
  runtime retrieval).
- `Validate Tool Schema` — verify the tool's schema is well-formed
  per the jsonschema Draft 2020-12 meta-schema; raise
  `InvalidMCPToolSchemaError` with an RFC 6901 JSON Pointer + the
  wrapped jsonschema error message.

Lifecycle keywords (Story 3.1 + 3.2 / PRD FR7 + FR8 + FR9a + FR9b):
- `Start Server` — pure handle construction over the 3-transport enum.
- `Connect To Server` — open session, run `initialize()`, gate on the
  agenteval-supported protocol range, then close.
- `Stop Server` — Phase-1 no-op cleanup hook.
- `List Tools` — per-call MCP `list_tools` projection.
- `Call Tool` — per-call MCP tool invocation (tool-error-as-data).

Discoverability keyword (Story 4.4 / PRD FR10a):
- `Get Tool Discoverability` — Tier-3 N-trial Pass@k evaluation with
  Wilson CI bounds.

Per Story 2.2 code-review HIGH-1 ratification (DynamicCore composition
keyword-name collision prevention): `MCPLibrary` is NOT registered in
`src/AgentEval/__init__.py:_SUB_LIBRARIES`. Users access via standalone
import:

    *** Settings ***
    Library    AgentEval.mcp.library.MCPLibrary    WITH NAME    MCP

    *** Test Cases ***
    Echo Server Declares Stdio Transport
        ${servers}=    MCP.Get Server Config    ${CURDIR}/.mcp.json
        Should Be Equal    ${servers["echo"]["transport"]}    stdio

Phase-1 limitations:
- Tool schemas come from the declarative `.mcp.json:tools` extension
  (Story 2.3 drift-check D-D); PRD FR6 runtime retrieval is Phase-2.
- Transport enum: only `stdio` / `streamable_http` / `in_memory` per
  PRD FR7.
- jsonschema validation uses Draft 2020-12 meta-schema only.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from robot.api.deco import keyword

from AgentEval._kernel.discovery import get_adapter
from AgentEval._kernel.tier import tier
from AgentEval.discoverability.loader import load_discoverability_tasks
from AgentEval.discoverability.schema import (
    DiscoverabilityResult,
    DiscoverabilitySummary,
    TaskResult,
)
from AgentEval.discoverability.wilson_ci import wilson_score_interval
from AgentEval.mcp._parser import (
    get_tool_schema,
    parse_mcp_servers,
    validate_tool_schema,
)
from AgentEval.mcp.lifecycle import (
    MCPServerHandle,
    MCPSession,
    MCPTool,
    MCPToolResult,
    call_tool,
    connect_to_server,
    list_tools,
    start_server,
    stop_server,
)
from AgentEval.mcp.transport import Transport

__all__ = ["MCPLibrary"]

# Browser-Library-style docstring migration marker (Phase 7, 2026-05-26).
_BROWSER_STYLE_MIGRATED = True


class MCPLibrary:
    """Static-inspection keywords for `.mcp.json` files [Tier 1 — Deterministic]."""

    @keyword(name="Get Server Config")
    @tier(1)
    def get_server_config(self, path: str | Path) -> dict[str, dict[str, Any]]:
        """Parses a ``.mcp.json`` file's ``mcpServers`` declarations (PRD FR5).

        [Tier 1 — Deterministic] — pure file-read + JSON parse + per-
        entry validation. Does NOT spawn any MCP subprocesses. Returns a
        dict mapping ``<server_name>`` → server-entry dict. Each entry
        has at minimum ``command`` (str); may carry ``args``, ``env``,
        ``transport`` (one of ``stdio`` / ``streamable_http`` /
        ``in_memory`` per FR7), ``tools`` (Phase-1 declarative
        extension). Median ≤ 50 ms per NFR-PERF-02.

        | =Arguments= | =Description= |
        | ``path`` | Filesystem path to the ``.mcp.json`` file. Accepts ``str`` OR ``pathlib.Path``. |

        Raises ``InvalidMCPServerConfigError`` on any structural
        failure. The error's ``field_name`` attribute carries an RFC
        6901 JSON Pointer into the offending location.

        Example:
        | ${servers} =    `Get Server Config`    ${CURDIR}/.mcp.json
        | Should Be Equal    ${servers}[echo][transport]    stdio
        | Should Contain    ${servers}[echo][args]    -m

        Notes:
        - PRD FR5 ratifies the ``.mcp.json`` parse contract; FR7 ratifies the transport enum.
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - Sibling keywords: `Get Tool Schema` + `Validate Tool Schema` for tool-schema introspection.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return parse_mcp_servers(path)

    @keyword(name="Get Tool Schema")
    @tier(1)
    def get_tool_schema(
        self,
        config_path: str | Path,
        tool_name: str,
        server_name: str | None = None,
    ) -> dict[str, Any]:
        """Returns a tool's input JSON Schema from the ``.mcp.json:tools`` extension (PRD FR6).

        [Tier 1 — Deterministic] — reads from the declarative ``tools``
        extension on each server entry (Story 2.3 D-D). Returns the
        schema as a ``dict``. PRD FR6's runtime "against a running MCP
        server" path is Phase-2 + Epic 3 scope.

        | =Arguments= | =Description= |
        | ``config_path`` | Filesystem path to the ``.mcp.json`` file. |
        | ``tool_name`` | Name of the tool whose input schema to retrieve. |
        | ``server_name`` | When ``None`` (default), search every server in declaration order + return the first match. When set, only consult the named server. |

        Raises ``InvalidMCPServerConfigError`` on ``.mcp.json``
        structural failure. Raises ``InvalidMCPToolSchemaError`` when
        the tool is not declared on any candidate server.

        Example:
        | ${schema} =    `Get Tool Schema`    ${CURDIR}/.mcp.json    tool_name=echo
        | Should Be Equal    ${schema}[type]    object
        | Should Contain    ${schema}[required]    message

        Notes:
        - PRD FR6 ratifies the tool-schema retrieval contract; Phase-1 scope per Story 2.3 D-D drift-check.
        - Sibling keywords: `Get Server Config` (full ``.mcp.json`` parse); `Validate Tool Schema` (Draft 2020-12 well-formedness check).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return get_tool_schema(config_path, tool_name=tool_name, server_name=server_name)

    @keyword(name="Validate Tool Schema")
    @tier(1)
    def validate_tool_schema(
        self,
        config_path: str | Path,
        tool_name: str,
        server_name: str | None = None,
    ) -> None:
        """Validates a tool's schema against the jsonschema Draft 2020-12 meta-schema.

        [Tier 1 — Deterministic] — verifies the schema-VALIDITY of an
        MCP tool's input schema. Does NOT validate any tool-call's
        ARGUMENTS against the schema — that's a runtime concern Epic 3
        owns. Median ≤ 50 ms per NFR-PERF-02.

        | =Arguments= | =Description= |
        | ``config_path`` | Filesystem path to the ``.mcp.json`` file. |
        | ``tool_name`` | Tool whose schema to validate. |
        | ``server_name`` | Optional server scoping (see `Get Tool Schema`). |

        Raises ``InvalidMCPServerConfigError`` on ``.mcp.json``
        structural failure. Raises ``InvalidMCPToolSchemaError`` when
        the tool is not declared OR its schema fails Draft 2020-12
        meta-schema validation. The error's ``field_name`` carries an
        RFC 6901 JSON Pointer; the wrapped jsonschema exception is
        available via ``__cause__``.

        Example:
        | `Validate Tool Schema`    ${CURDIR}/.mcp.json    tool_name=echo
        | Run Keyword And Expect Error    InvalidMCPToolSchemaError*    `Validate Tool Schema`    ${CURDIR}/.mcp.json    tool_name=nonexistent

        Notes:
        - Validates schema well-formedness, NOT argument conformance — that's runtime/Epic 3.
        - Error format per FR59 + `docs/contracts/error-class-hierarchy.md` L96-104.
        - Sibling keyword: `Get Tool Schema` for retrieving the schema dict.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        validate_tool_schema(config_path, tool_name=tool_name, server_name=server_name)

    # --------------------------------------------------------------- #
    # Story 3.1: MCP server lifecycle keywords (PRD FR7 + FR8 + FR46)
    # --------------------------------------------------------------- #

    @keyword(name="Start Server")
    @tier(1)
    def start_server(
        self,
        name: str,
        transport: Transport,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        server_factory: Callable[[], Any] | None = None,
    ) -> MCPServerHandle:
        """Builds an MCP server handle per the 3-transport enum (PRD FR7).

        [Tier 1 — Deterministic] — pure handle construction. For
        ``stdio`` + ``in_memory`` transports, does NOT spawn the server
        yet (per Story 3.1 per-call-session design); the actual server
        start happens during `Connect To Server`. The ``streamable_http``
        transport is accepted as a Phase-1 passthrough; full HTTP
        round-trip lands Phase-1.5 or Story 3.2.

        | =Arguments= | =Description= |
        | ``name`` | Caller-chosen server identifier (echoed in errors). |
        | ``transport`` | One of ``"stdio"`` / ``"streamable_http"`` / ``"in_memory"`` per FR7 transport enum. |
        | ``command`` | stdio only — executable path/name (e.g. ``"python"``). |
        | ``args`` | stdio only — list of command-line arguments. |
        | ``env`` | stdio only — environment overlay. |
        | ``server_factory`` | in_memory only — no-arg callable returning a ``FastMCP`` server instance. |

        Raises ``ValueError`` when transport-required parameters are
        missing (e.g. ``transport="stdio"`` without ``command``).

        Example:
        | ${handle} =    `Start Server`    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}
        | ${session} =    `Connect To Server`    ${handle}
        | @{tools} =    `List Tools`    ${handle}
        | `Stop Server`    ${handle}

        Notes:
        - PRD FR7 ratifies the 3-transport enum; Story 3.1 ratifies the per-call-session design.
        - Story 3.2 lands the full ``streamable_http`` round-trip (Phase-1 currently passthrough).
        - Sibling keywords: `Connect To Server` (handshake + version check); `List Tools`, `Call Tool`, `Stop Server`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return start_server(
            name=name,
            transport=transport,
            command=command,
            args=args,
            env=env,
            server_factory=server_factory,
        )

    @keyword(name="Connect To Server")
    @tier(1)
    def connect_to_server(self, handle: MCPServerHandle) -> MCPSession:
        """Opens + initializes an MCP ``ClientSession`` and gate-checks the version (PRD FR8 + FR46).

        [Tier 1 — Deterministic] — per Story 3.1 per-call-session
        design: opens session, runs ``initialize()``, captures the
        negotiated protocol version + server info, gates on the
        agenteval-supported range (``mcp>=1.0,<2.0``), then closes the
        underlying SDK session. Returns ``MCPSession`` metadata —
        **NOT a live SDK session**.

        | =Arguments= | =Description= |
        | ``handle`` | An ``MCPServerHandle`` from `Start Server`. |

        Raises ``UnsupportedMCPVersionError`` when the negotiated
        protocol version is outside the supported range. Raises
        ``ValueError`` when ``handle.transport == "streamable_http"``
        (Phase-1 passthrough; not yet implemented).

        Example:
        | ${handle} =    `Start Server`    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}
        | ${session} =    `Connect To Server`    ${handle}
        | Should Not Be Empty    ${session.protocol_version}
        | Should Contain    ${session.server_info}[name]    echo

        Notes:
        - PRD FR8 + FR46 ratify the version-gate + per-call-session contract.
        - Story 3.1 ratifies per-call-session design (no live session returned).
        - NFR-COMPAT-04 pins the MCP SDK at ``mcp>=1.0,<2.0``.
        - Sibling keywords: `Start Server` (handle construction); `Stop Server` (Phase-1 no-op cleanup); `List Tools` / `Call Tool` (per-call session-internal).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return connect_to_server(handle)

    @keyword(name="Stop Server")
    @tier(1)
    def stop_server(self, handle: MCPServerHandle) -> None:
        """Tears down any per-handle MCP resources.

        [Tier 1 — Deterministic] — Phase-1 no-op (each `Connect To
        Server` self-cleans the SDK session). The keyword ships now so
        ``.robot`` tests can adopt the canonical 3-step lifecycle
        without breaking when Phase-1.5 introduces pooled sessions
        that need explicit teardown.

        | =Arguments= | =Description= |
        | ``handle`` | The ``MCPServerHandle`` from `Start Server`. |

        Returns ``None``. Never raises in Phase-1 (no-op).

        Example:
        | ${handle} =    `Start Server`    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}
        | TRY
        |     ${result} =    `Call Tool`    ${handle}    echo    arguments=${{ {"message": "hi"} }}
        |     Should Be True    ${result.is_error} == False
        | FINALLY
        |     `Stop Server`    ${handle}
        | END

        Notes:
        - Phase-1 no-op per Story 3.1 design (per-call sessions self-clean).
        - The canonical 3-step lifecycle (`Start Server` → `Connect To Server` → `Stop Server`) is ratified now to avoid breakage when Phase-1.5 introduces pooled sessions.
        - Sibling keywords: `Start Server` + `Connect To Server` (companion lifecycle steps).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        stop_server(handle)

    # --------------------------------------------------------------- #
    # Story 3.2: MCP tool inspection keywords (PRD FR9a + FR9b)
    # --------------------------------------------------------------- #

    @keyword(name="List Tools")
    @tier(1)
    def list_tools(self, handle: MCPServerHandle) -> list[MCPTool]:
        """Lists the tools advertised by the MCP server at ``handle`` (PRD FR9a).

        [Tier 1 — Deterministic] — opens a fresh per-call MCP session
        per Story 3.1, runs ``initialize()``, calls the MCP spec's
        ``list_tools`` operation, then tears down. Each call pays the
        full handshake cost; Phase-1.5 may introduce pooled sessions
        for hot loops. Returns a ``list[MCPTool]`` with ``name``,
        ``description``, ``input_schema``, and optional ``output_schema``.

        | =Arguments= | =Description= |
        | ``handle`` | An ``MCPServerHandle`` from `Start Server`. |

        Raises ``ValueError`` when transport is ``streamable_http``
        (Phase-1 passthrough). Raises ``UnsupportedMCPVersionError``
        when ``initialize()`` rejects the negotiated protocol version.
        Raises ``MCPConnectionLostError`` when the transport layer
        fails mid-call.

        Example:
        | ${handle} =    `Start Server`    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}
        | @{tools} =    `List Tools`    ${handle}
        | Should Not Be Empty    ${tools}
        | Should Contain    ${{ [t.name for t in $tools] }}    echo_back

        Notes:
        - PRD FR9a ratifies the list-tools contract.
        - Story 3.1 ratifies per-call-session design.
        - Pooled-session optimization is Phase-1.5; Phase-1 pays per-call handshake.
        - Sibling keyword: `Call Tool` (invoke a tool by name); `Get Tool Schema` (declarative — reads from ``.mcp.json``).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return list_tools(handle)

    @keyword(name="Call Tool")
    @tier(1)
    def call_tool(
        self,
        handle: MCPServerHandle,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        """Invokes a tool by name on the MCP server at ``handle`` (PRD FR9b).

        [Tier 1 — Deterministic] (given a deterministic tool) — opens
        a fresh per-call MCP session, runs ``initialize()``, invokes
        the named tool, computes wall-clock latency, then tears down.
        Tool-LEVEL error responses surface as
        ``MCPToolResult(is_error=True, ...)`` — first-class data, NOT
        exceptions. Infrastructure failures raise
        ``MCPConnectionLostError``.

        | =Arguments= | =Description= |
        | ``handle`` | An ``MCPServerHandle`` from `Start Server`. |
        | ``tool_name`` | The tool name as advertised by the server. |
        | ``arguments`` | Optional dict of tool-specific arguments. Defaults to ``{}``. |

        Returns ``MCPToolResult`` with ``content`` (list of content
        blocks), ``is_error``, ``error_message``, ``latency_ms``, and
        ``correlation_id`` (Phase-1 uuid4 placeholder).

        Raises ``ValueError`` on ``streamable_http`` transport (Phase-1
        passthrough). Raises ``UnsupportedMCPVersionError`` on version
        gate failure. Raises ``MCPConnectionLostError`` on transport-
        layer failure mid-call (subprocess crash, etc.).

        Example:
        | ${handle} =    `Start Server`    name=echo    transport=stdio    command=python    args=${{['-m', 'AgentEval.mcp.bundled.echo']}}
        | ${result} =    `Call Tool`    ${handle}    echo_back    arguments=${{ {"text": "hi"} }}
        | Should Be Equal    ${result.is_error}    ${FALSE}
        | Should Contain    ${result.content}[0][text]    hi
        | `Stop Server`    ${handle}

        Notes:
        - PRD FR9b ratifies the tool-call contract; tool-error-as-data per AC-MCP-CALL-01.
        - ``correlation_id`` Phase-1 placeholder; Epic 5 wires real trace-id lookup.
        - Sibling keywords: `List Tools`, `Start Server`, `Stop Server`.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        return call_tool(handle, tool_name, arguments)

    # --------------------------------------------------------------- #
    # Story 4.4: MVP Tool Discoverability (PRD FR10a + AC-DISCOVER-01)
    # --------------------------------------------------------------- #

    @keyword(name="Get Tool Discoverability")
    @tier(3)
    def get_tool_discoverability(
        self,
        mcp_server: str = "",
        adapter: str = "generic",
        model: str | None = None,
        tasks: str = "",
        trials_per_task: int = 3,
        max_cost_usd: float = 5.00,
        max_runtime_seconds: float | None = None,
        **kwargs: Any,
    ) -> DiscoverabilityResult:
        """Drives N-trial discoverability evaluation of an MCP server's tools (PRD FR10a).

        [Tier 3 — Stochastic Fan-Out] — for each task in the YAML,
        dispatches ``trials_per_task`` adapter.run() calls and
        inspects ``tool_calls`` to compute Pass@k with Wilson CI bounds.

        | =Arguments= | =Description= |
        | ``mcp_server`` | Name of the MCP server (per `Start Server`). Must be a non-empty string. Phase-1: accepted but NOT forwarded to ``adapter.run()`` (DF-4.1-S2 + DF-4.2-S1). |
        | ``adapter`` | Adapter name. Defaults to ``"generic"``. |
        | ``model`` | Model identifier (e.g., ``"anthropic/claude-sonnet-4-6"``). |
        | ``tasks`` | Path to the discoverability tasks YAML. |
        | ``trials_per_task`` | Number of trials per task (Pass@k semantics). Defaults to ``3``. |
        | ``max_cost_usd`` | Budget cap. Phase-1: tracked, NOT enforced (DF-4.4-S1 carry-over). Defaults to ``5.00``. |
        | ``max_runtime_seconds`` | Runtime cap. Phase-1: tracked, NOT enforced. Defaults to ``None``. |
        | ``**kwargs`` | Provider/adapter forward-compat kwargs. |

        Phase-1 carve-out (DF-4.4-S1): ``@guarded_fanout`` enforcement
        of ``max_cost_usd`` + ``max_runtime_seconds`` is DEFERRED —
        same architectural gap as Story 4.3 DF-4.3-S6 (MCPLibrary is
        excluded from ``_SUB_LIBRARIES`` per Story 2.2 norm; no clean
        path to inject library-level budgets without architectural
        change). The kwargs are accepted + tracked on the result but
        NOT enforced. Operators must bound cost manually until
        Phase-1.5 plumbs the cross-library config.

        Phase-1 carve-out (DF-4.1-S2 + DF-4.2-S1): ``mcp_server=`` is
        NOT forwarded to ``adapter.run(mcp_servers=...)`` because both
        Phase-1 adapters (Generic + Claude Code CLI) raise
        ``NotImplementedError`` on non-empty ``mcp_servers``. The
        kwarg is accepted for forward-compatibility + validated as
        non-empty; tool-call success is gated on what the model
        returns from prompt alone (useful for stub-adapter tests;
        meaningful for real LLMs only when DF-4.1-S2 + DF-4.2-S1 land).

        Empty-``expected_tools`` semantics (Story 4.4 code-review 3-way
        MED-A 2026-05-20): when a task's ``expected_tools`` is ``[]``,
        the keyword treats ANY tool call as success (wildcard mode —
        useful for "did the agent invoke ANY tool?" probes).
        ``competing_tools_picked`` in this case collects ALL called
        tool names.

        Returns ``DiscoverabilityResult`` with ``per_task_results`` +
        ``summary`` (aggregate pass rate + cost + runtime) +
        ``mcp_coverage`` per PRD FR10a L1499 ratified shape.

        Raises ``InvalidDiscoverabilityTasksError`` on tasks YAML
        parse/schema failure. Raises ``AdapterDiscoveryError`` on
        unknown adapter name. Raises ``ValueError`` when required
        kwargs are missing/empty.

        Example (illustrative — assumes a real adapter or fixture stub):
        | ${result} =    `Get Tool Discoverability`
        | ...    mcp_server=echo
        | ...    adapter=generic
        | ...    provider=mock
        | ...    model=stub
        | ...    tasks=${CURDIR}/discoverability_tasks.yaml
        | ...    trials_per_task=3
        | Should Be True    0.0 <= ${result.summary.overall_pass_rate} <= 1.0
        | Should Not Be Empty    ${result.per_task_results}

        Notes:
        - PRD FR10a ratifies the keyword + ``DiscoverabilityResult`` shape.
        - Tier-3 stochastic; budgets tracked but NOT enforced in Phase-1 (DF-4.4-S1).
        - Story 4.3 + Story 4.4 ratify the carve-out (architectural budget-injection gap shared with `MetricsLibrary` family).
        - Story 2.2 ratifies the ``_SUB_LIBRARIES`` composition norm (which excludes ``MCPLibrary`` — driver of the carve-out).
        - Sibling keywords (same library): `Call Tool`, `List Tools`, `Start Server`.
        - Downstream keyword (separately composed sub-library): `HeatmapLibrary.Get Cohort Heatmap` consumes ``DiscoverabilityResult`` to render the FR55 cohort heatmap.
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        # Story 4.4 code-review MED-B fix 2026-05-20 (Codex empirical probe):
        # `total_runtime_seconds` must capture the full end-to-end wall time
        # operators care about for AC-DISCOVER-02 budget audit — including
        # tasks YAML load + adapter resolution + adapter construction, NOT
        # just the trial dispatch loop. Pre-edit `t_start` fired after ctor
        # and underreported by the ctor cost (probe: 0.0202 vs 0.3712 actual).
        t_start = time.monotonic()

        # Story 4.4 code-review MED-E fix 2026-05-20 (Edge-cases M2): pre-edit
        # accepted `mcp_server=""` silently — Phase-1 the field is unused
        # (DF-4.1-S2) but future-proofing means rejecting the empty-string
        # input now so existing callers don't lock in a no-op default.
        if not mcp_server:
            raise ValueError(
                "Get Tool Discoverability requires `mcp_server=<name>` kwarg "
                "(name of an MCP server started via `MCP.Start Server`); empty "
                "string is rejected even in Phase-1 where DF-4.1-S2 stubs the "
                "adapter-side integration."
            )
        if not tasks:
            raise ValueError("Get Tool Discoverability requires `tasks=<yaml-path>` kwarg")
        if trials_per_task < 1:
            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")

        # Load + validate the tasks YAML.
        task_list = load_discoverability_tasks(tasks)

        # Resolve the adapter (Phase-1 simplified: route ALL kwargs to ctor
        # like Story 4.3 pre-split-introspection — orchestration's split
        # logic lives on OrchestrationLibrary, not MCPLibrary; MCPLibrary
        # is a Phase-1 sub-library that doesn't yet inherit the split.
        # DF-4.4-S2 carry-over for ctor/run split parity.).
        adapter_cls = get_adapter(adapter)
        adapter_ctor_kwargs: dict[str, Any] = dict(kwargs)
        if model is not None:
            adapter_ctor_kwargs["model"] = model
        try:
            adapter_instance = adapter_cls(**adapter_ctor_kwargs)
        except TypeError as exc:
            # Story 4.4 code-review MED-D fix 2026-05-20 (Blind): pre-edit
            # comment claimed "fall back to no-kwarg construction + log the
            # dropped kwargs" but the handler actually re-raises with no
            # fallback. Fixed the comment-vs-code drift — re-raise is
            # intentional + DF-4.4-S2 carry-over plumbs the real split.
            raise TypeError(
                f"Adapter {adapter!r} doesn't accept kwargs {sorted(adapter_ctor_kwargs)}; "
                "DF-4.4-S2 carry-over (ctor/run split parity for MCPLibrary "
                "lands in Phase-1.5 — mirroring Story 4.3's "
                "`_split_adapter_kwargs` introspection on OrchestrationLibrary). "
                "For now, pass kwargs the adapter accepts."
            ) from exc

        # Per-call mcp_servers integration is DF-4.1-S2 / DF-4.2-S1; for now
        # we DON'T forward the mcp_server name since the adapter would just
        # raise NotImplementedError. Phase-1 dispatches WITHOUT MCP context;
        # tool-call success is gated on what the model returns from prompt
        # alone.
        _ = mcp_server

        per_task: list[TaskResult] = []
        total_cost = 0.0
        for task in task_list:
            tool_calls_per_trial: list[list[Any]] = []
            cost_per_trial: list[float] = []
            success_count = 0
            competing_set: set[str] = set()
            for _ in range(trials_per_task):
                run_result = adapter_instance.run(task.prompt)
                tool_calls_per_trial.append(list(run_result.tool_calls))
                cost_per_trial.append(run_result.cost_usd)
                total_cost += run_result.cost_usd
                called_names = {tc.name for tc in run_result.tool_calls}
                # Story 4.4 code-review 3-way MED-A fix 2026-05-20 (Edge-cases
                # M1 + Codex MED + Blind LOW-1): when expected_tools is empty,
                # wildcard-success mode is active — ANY tool call counts AND
                # ALL called names go into competing_tools_picked so the
                # verdict matrix retains visibility into what the model
                # picked. Pre-edit the `competing_set.update(...)` line was
                # only reachable in the `if task.expected_tools` branch,
                # leaving wildcard-mode tasks with permanently-empty
                # competing_tools_picked.
                if task.expected_tools:
                    expected_set = set(task.expected_tools)
                    if called_names & expected_set:
                        success_count += 1
                    competing_set.update(called_names - expected_set)
                else:
                    if called_names:
                        success_count += 1
                    competing_set.update(called_names)
            lower, upper = wilson_score_interval(success_count, trials_per_task)
            per_task.append(
                TaskResult(
                    task_id=task.id,
                    task_prompt=task.prompt,
                    trials_run=trials_per_task,
                    success_count=success_count,
                    tool_calls_per_trial=tool_calls_per_trial,
                    competing_tools_picked=sorted(competing_set),
                    cost_per_trial_usd=cost_per_trial,
                    wilson_ci_lower=lower,
                    wilson_ci_upper=upper,
                )
            )
        total_runtime = time.monotonic() - t_start

        # Overall pass rate: weighted by trials.
        total_trials = sum(t.trials_run for t in per_task)
        total_successes = sum(t.success_count for t in per_task)
        overall_pass_rate = (total_successes / total_trials) if total_trials else 0.0

        # Phase-1: mcp_coverage hardcoded to "hosted_in_process" since
        # Phase-1 doesn't yet attach real MCP via the adapter (DF-4.4-S3
        # carry-over: Epic 5 hosted-MCP observer wires real coverage detection).
        _ = max_cost_usd
        _ = max_runtime_seconds
        # Story 4.4 code-review HIGH-B fix 2026-05-20 (Auditor citation-drift
        # catch): PRD FR10a L1499 ratifies `summary` nesting for the aggregate
        # roll-up; pre-edit shape flattened the 3 summary fields into
        # top-level result attributes. "Fix-the-losing-source-NOW" pattern
        # per feedback_citation_drift_first_class — implementation realigned.
        return DiscoverabilityResult(
            per_task_results=per_task,
            summary=DiscoverabilitySummary(
                overall_pass_rate=overall_pass_rate,
                total_cost_usd=total_cost,
                total_runtime_seconds=total_runtime,
            ),
            mcp_coverage="hosted_in_process",
        )
