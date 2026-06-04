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

from AgentEval._kernel.guardrails import guarded_fanout
from AgentEval._kernel.host_budget_plumbing import _HostBudgetPlumbing
from AgentEval._kernel.tier import tier
from AgentEval.discoverability.loader import load_discoverability_tasks
from AgentEval.discoverability.schema import (
    DiscoverabilityComparisonResult,
    DiscoverabilityResult,
)
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


class MCPLibrary(_HostBudgetPlumbing):
    """Static-inspection + cross-adapter keywords for `.mcp.json` files.

    Inherits ``_HostBudgetPlumbing`` (Story 14.6 / C20+C89 closure) so
    ``MCP.Get Tool Discoverability`` + ``MCP.Compare Tool Discoverability``
    enforce ``max_cost_usd`` + ``max_runtime_seconds`` budgets via
    ``@guarded_fanout()``. Operators MUST pass the budgets at RF
    ``Library`` import time per Story 2.2 ``_SUB_LIBRARIES`` exclusion —
    see the mixin's module docstring for the RF syntax.
    """

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
    @guarded_fanout()
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
        | ``max_cost_usd`` | Budget cap. Defaults to ``5.00``. Enforced via `@guarded_fanout()` per Story 14.6 (C20 closure) — MCPLibrary inherits `_HostBudgetPlumbing` so budgets passed at RF `Library` import time are honored end-to-end. |
        | ``max_runtime_seconds`` | Runtime cap. Defaults to ``None``. Enforced via `@guarded_fanout()` (Story 14.6 / C20 closure). |
        | ``**kwargs`` | Provider/adapter forward-compat kwargs. |

        Budget enforcement (Story 14.6 / C20 closure): `@guarded_fanout()`
        reads `_max_cost_usd` + `_max_runtime_seconds` from the
        MCPLibrary host instance via the `_HostBudgetPlumbing` mixin
        (`_kernel/host_budget_plumbing.py`). Operators pass budgets at
        RF `Library` import time per Story 2.2 `_SUB_LIBRARIES`
        exclusion — see the mixin's module docstring for the RF syntax.

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
        - Tier-3 stochastic; `max_cost_usd` + `max_runtime_seconds` budgets enforced via `@guarded_fanout()` (Story 14.6 / C20 closure).
        - Story 4.3 + Story 4.4 carve-out (architectural budget-injection gap) closed by Story 14.6's unified `_HostBudgetPlumbing` mixin.
        - Story 2.2 ratifies the ``_SUB_LIBRARIES`` composition norm (which excludes ``MCPLibrary``); operators pass budgets at RF `Library` import time per the mixin's documented RF syntax.
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

        # Story 13.3 refactor: per-adapter logic extracted to
        # `discoverability/_internal.run_single_adapter_discoverability` so
        # the new `MCP.Compare Tool Discoverability` keyword reuses it
        # without ~80 LoC duplication. Behavior MUST equal pre-refactor —
        # verified by Story 4.4's 50+ existing tests passing unchanged.
        from AgentEval.discoverability._internal import run_single_adapter_discoverability

        return run_single_adapter_discoverability(
            mcp_server=mcp_server,
            adapter=adapter,
            model=model,
            task_list=task_list,
            trials_per_task=trials_per_task,
            max_cost_usd=max_cost_usd,
            max_runtime_seconds=max_runtime_seconds,
            extra_adapter_kwargs=dict(kwargs),
            t_start=t_start,
        )

    # --------------------------------------------------------------- #
    # Story 13.3: Cross-adapter comparison (PRD FR10b)
    # --------------------------------------------------------------- #

    @keyword(name="MCP.Compare Tool Discoverability")
    @tier(3)
    @guarded_fanout()
    def get_tool_discoverability_comparison(
        self,
        mcp_server: str = "",
        adapters: list[str] | None = None,
        tasks: str = "",
        trials_per_task: int = 3,
        max_cost_usd: float = 20.00,
        max_runtime_seconds: float | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> DiscoverabilityComparisonResult:
        """Compares Tool Discoverability across ≥2 coding-agent adapters with statistical significance (PRD FR10b; Story 13.3).

        [Tier 3 — Stochastic Fan-Out] — runs `Get Tool Discoverability`
        once per adapter against the SAME task set, then computes
        pairwise Mann-Whitney U deltas across the per-task pass-rate
        distributions. Returns a `DiscoverabilityComparisonResult` with
        per-adapter results + cross-adapter deltas + multi-column
        cohort heatmap + aggregate summary.

        Requires the ``[agenteval-advanced]`` optional extra (scipy +
        numpy) for the Mann-Whitney U cross-adapter delta computation;
        raises ``ImportError`` on invocation WITHOUT the extra (fail-fast
        BEFORE running any per-adapter fan-out — operators discovering
        the missing extra should not pay 3-adapter trial cost first).

        | =Arguments= | =Description= |
        | ``mcp_server`` | Name of the MCP server (per `Start Server`). Same Phase-1 carve-out as `Get Tool Discoverability` (DF-4.1-S2 + DF-4.2-S1). |
        | ``adapters`` | REQUIRED ``list[str]`` of adapter names; ≥2 entries required. N=3+ enables ranking across Claude/GPT/Copilot/.... |
        | ``tasks`` | Path to the discoverability tasks YAML (loaded ONCE; shared across adapters). |
        | ``trials_per_task`` | Pass@k trials per task. Defaults to ``3``. |
        | ``max_cost_usd`` | Budget cap. Defaults to ``20.00`` per epics.md L2186 (4× the single-adapter default reflecting N=3-adapter typical cost). Enforced via `@guarded_fanout()` per Story 14.6 (C89 closure) — MCPLibrary inherits `_HostBudgetPlumbing` so budgets passed at RF `Library` import time are honored end-to-end. |
        | ``max_runtime_seconds`` | Runtime cap. Phase-1: tracked, NOT enforced. |
        | ``model`` | Optional ``str`` forwarded to ALL adapters' ctor. Phase-2.5 (DF-13.3-S4): per-adapter model overrides via `adapter_models: dict[str, str]` kwarg. |
        | ``**kwargs`` | Forward-compat kwargs routed to each adapter's ctor. |

        Returns ``DiscoverabilityComparisonResult`` with ``adapters`` +
        ``per_adapter_results`` (one ``DiscoverabilityResult`` per
        adapter) + ``cross_adapter_deltas`` (C(N, 2) ``PairwiseAdapterDelta``
        entries keyed ``f"{a1}_vs_{a2}"``) + ``heatmap`` (multi-column
        ``CohortHeatmap`` via ``from_comparison``) + ``summary``
        (``DiscoverabilityComparisonSummary``).

        Raises ``ImportError`` when ``[agenteval-advanced]`` extra is
        missing (Mann-Whitney U requires scipy/numpy). Raises
        ``ValueError`` on missing/empty ``mcp_server`` / ``tasks`` /
        ``adapters`` (≥2 required) / invalid ``trials_per_task``.
        Raises ``InvalidDiscoverabilityTasksError`` on tasks YAML
        parse/schema failure. Raises ``AdapterDiscoveryError`` on
        unknown adapter name.

        Example:
        | ${comparison}=    `MCP.Compare Tool Discoverability`
        | ...    mcp_server=rf-mcp
        | ...    adapters=${{['generic', 'claude_code_cli', 'codex_cli']}}
        | ...    tasks=${CURDIR}/tasks.yaml
        | ...    trials_per_task=5
        | ...    max_cost_usd=20.00
        | Should Be Equal As Strings    ${comparison.summary.best_adapter}    claude_code_cli
        | Should Be True    ${comparison.cross_adapter_deltas['generic_vs_codex_cli'].significant_at_alpha_05}

        Notes:
        - Story 13.3 (Epic 13) ships this Phase-2 keyword behind the ``[agenteval-advanced]`` optional extra (the Mann-Whitney U dependency from Story 13.1).
        - PRD FR10b ratifies the ``DiscoverabilityComparisonResult`` shape; epics.md L2186-2189 ratifies the keyword signature + behavior.
        - Math reference: ``AgentEval.stats.mannwhitney.compute_mann_whitney_u`` (Story 13.1 pure helper at ``src/AgentEval/stats/mannwhitney.py``). The keyword surface ``Stat.Mann Whitney U`` is NOT called here because the input is ``list[float]`` per-task pass rates (NOT ``list[KeywordRun]``).
        - ``@tier(3)`` per fan-out semantics — stochastic by tier definition; no bit-identical FR31a guarantee (Story 13.1 HIGH-C concern doesn't apply at @tier(3)).
        - Phase-1 carve-out DF-13.3-S1: ``@guarded_fanout`` enforcement DEFERRED (same MCPLibrary architectural gap as DF-4.4-S1 / C20).
        - Phase-2.5 carry-overs: DF-13.3-S2 (per-adapter MCP attachment gated on C72 + C68/C69/C73/C75); DF-13.3-S3 (Bonferroni / Holm multi-pairwise correction).
        - Sibling keyword: `MCP.Get Tool Discoverability` (Phase-1 single-adapter; this keyword's N=1 case is intentionally rejected via the ≥2 validation — single-adapter callers should use the simpler `Get` keyword).
        """  # TODO(agenteval-docs): add issue-link footer once forum/discussion choice is made
        t_start = time.monotonic()

        # Validate args (mirrors single-adapter Get + adds N≥2 constraint).
        if not mcp_server:
            raise ValueError(
                "MCP.Compare Tool Discoverability requires `mcp_server=<name>` kwarg "
                "(name of an MCP server started via `MCP.Start Server`); empty "
                "string is rejected even in Phase-1 where DF-4.1-S2 stubs the "
                "adapter-side integration."
            )
        if not tasks:
            raise ValueError("MCP.Compare Tool Discoverability requires `tasks=<yaml-path>` kwarg")
        if trials_per_task < 1:
            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")
        if adapters is None or len(adapters) < 2:
            raise ValueError(
                f"MCP.Compare Tool Discoverability requires adapters=[<adapter_1>, "
                f"<adapter_2>, ...] with >= 2 entries; got {adapters!r}"
            )
        if len(set(adapters)) != len(adapters):
            raise ValueError(
                f"MCP.Compare Tool Discoverability requires distinct adapter names; got duplicates in {adapters!r}"
            )

        # `[agenteval-advanced]` extras gate (D-6 + L-2). Fail-fast BEFORE
        # the per-adapter fan-out so operators discovering the missing
        # extra don't pay N-adapter trial cost first. Direct raise per
        # AC-13.3.4 in-flight decision (b) — the `Stat.`-prefixed helper
        # `_raise_advanced_extra_missing` would mis-frame the message
        # for an `MCP.`-prefixed keyword.
        #
        # Read the attribute via module-level access (NOT
        # `from X import Y` which binds a local) so test
        # `monkeypatch.setattr(stats_lib, "_ADVANCED_AVAILABLE", False)`
        # is observed correctly even when this code path runs AFTER
        # Story 13.1's `test_advanced_extras_gate.py` has run + cleaned
        # up its own monkeypatch in the same pytest session.
        from AgentEval.stats import library as _stats_lib

        if not _stats_lib._ADVANCED_AVAILABLE:
            raise ImportError(
                "MCP.Compare Tool Discoverability: scipy + numpy required. "
                "Install via: uv pip install robotframework-agenteval[agenteval-advanced]"
            )

        # Load tasks YAML ONCE (shared across adapters).
        task_list = load_discoverability_tasks(tasks)

        # Run per-adapter discoverability serially. Phase-2.5 may parallelize
        # via thread pool / asyncio; Phase-2 ships serial for simplicity +
        # safer cost accounting.
        from AgentEval._heatmap.models import CohortHeatmap
        from AgentEval.discoverability._internal import run_single_adapter_discoverability
        from AgentEval.discoverability.schema import (
            DiscoverabilityComparisonResult,
            DiscoverabilityComparisonSummary,
            PairwiseAdapterDelta,
        )
        from AgentEval.stats.mannwhitney import compute_mann_whitney_u

        per_adapter_results: dict[str, DiscoverabilityResult] = {}
        for adapter_name in adapters:
            # Per-adapter timer measures only THIS adapter's slice — useful
            # for per-adapter cost auditing. The comparison-level wall-clock
            # is measured separately from the keyword-entry `t_start` below.
            per_adapter_results[adapter_name] = run_single_adapter_discoverability(
                mcp_server=mcp_server,
                adapter=adapter_name,
                model=model,
                task_list=task_list,
                trials_per_task=trials_per_task,
                max_cost_usd=max_cost_usd,
                max_runtime_seconds=max_runtime_seconds,
                extra_adapter_kwargs=dict(kwargs),
                t_start=time.monotonic(),
            )

        # Build C(N, 2) pairwise deltas. Ordering: itertools.combinations
        # preserves input order so `adapter_a` always comes before
        # `adapter_b` in the input list.
        import itertools

        cross_adapter_deltas: dict[str, PairwiseAdapterDelta] = {}
        for adapter_a, adapter_b in itertools.combinations(adapters, 2):
            rates_a = [t.pass_rate for t in per_adapter_results[adapter_a].per_task_results]
            rates_b = [t.pass_rate for t in per_adapter_results[adapter_b].per_task_results]
            # Empty per-task lists guard: skip the comparison if either is
            # empty (would otherwise raise from `compute_mann_whitney_u`).
            if not rates_a or not rates_b:
                continue
            mwu = compute_mann_whitney_u(rates_a, rates_b)
            delta_key = f"{adapter_a}_vs_{adapter_b}"
            mean_a = sum(rates_a) / len(rates_a)
            mean_b = sum(rates_b) / len(rates_b)
            import math as _math

            cross_adapter_deltas[delta_key] = PairwiseAdapterDelta(
                adapter_a=adapter_a,
                adapter_b=adapter_b,
                pass_rate_delta=mean_a - mean_b,
                mann_whitney_result=mwu,
                significant_at_alpha_05=(not _math.isnan(mwu.p_value)) and mwu.p_value < 0.05,
            )

        # Build summary aggregate.
        pass_rate_per_adapter = {name: per_adapter_results[name].summary.overall_pass_rate for name in adapters}
        best_adapter = max(pass_rate_per_adapter, key=lambda a: pass_rate_per_adapter[a])
        worst_adapter = min(pass_rate_per_adapter, key=lambda a: pass_rate_per_adapter[a])
        total_cost = sum(r.summary.total_cost_usd for r in per_adapter_results.values())
        # Wall-clock measured from keyword-entry `t_start` — what the operator
        # ACTUALLY waited for (serial execution Phase-2; Phase-2.5 parallel
        # target). Story 13.3 code-review HIGH-A fix 2026-06-01 (Codex HIGH-1
        # + Opus MED-2 2-way): pre-fix `max(per-adapter runtimes)` reported
        # the slowest single adapter, underreporting actual wait time by
        # ~N-1× under serial execution. Per-adapter runtimes remain in
        # `per_adapter_results[adapter].summary.total_runtime_seconds`.
        total_runtime = time.monotonic() - t_start
        summary = DiscoverabilityComparisonSummary(
            total_cost_usd=total_cost,
            total_runtime_seconds=total_runtime,
            pass_rate_per_adapter=pass_rate_per_adapter,
            best_adapter=best_adapter,
            worst_adapter=worst_adapter,
        )

        # Build a provisional comparison result so CohortHeatmap.from_comparison
        # can read the per-adapter results. The CohortHeatmap construction
        # happens AFTER per_adapter_results is populated; we pass a
        # "placeholder" comparison via direct construction (the
        # CohortHeatmap.from_comparison reads result.adapters + result.per_adapter_results
        # only, NOT the heatmap field — no chicken-and-egg).
        #
        # Build the heatmap via a lightweight namespace stand-in: the
        # classmethod accesses .adapters + .per_adapter_results.
        class _ComparisonShim:
            pass

        shim = _ComparisonShim()
        shim.adapters = tuple(adapters)  # type: ignore[attr-defined]
        shim.per_adapter_results = per_adapter_results  # type: ignore[attr-defined]
        heatmap = CohortHeatmap.from_comparison(shim)  # type: ignore[arg-type]

        # Track end-to-end runtime (caller-side; not stored separately
        # but contributes to the per-adapter timers we MAX'd above).
        _ = t_start

        return DiscoverabilityComparisonResult(
            adapters=tuple(adapters),
            per_adapter_results=per_adapter_results,
            cross_adapter_deltas=cross_adapter_deltas,
            heatmap=heatmap,
            summary=summary,
        )
