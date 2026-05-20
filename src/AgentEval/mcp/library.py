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

"""MCP sub-library — static-inspection keywords for `.mcp.json` files.

Story 2.3 ships 3 Tier-1 keywords per PRD FR5 + FR6 Phase-1 scope:
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


class MCPLibrary:
    """Static-inspection keywords for `.mcp.json` files [Tier 1 — Deterministic]."""

    @keyword(name="Get Server Config")
    @tier(1)
    def get_server_config(self, path: str | Path) -> dict[str, dict[str, Any]]:
        """Parse a `.mcp.json` file's `mcpServers` declarations.

        [Tier 1 — Deterministic] — pure file-read + JSON parse + per-entry
        validation. Does NOT spawn any MCP server subprocesses (verifiable
        via process inventory diff). Median ≤ 50 ms per NFR-PERF-02.

        Args:
            path: Filesystem path to the `.mcp.json` file.

        Returns:
            A dict mapping `<server_name>` → server-entry dict. Each
            entry has at minimum `command` (str); may contain `args`
            (list[str]), `env` (dict[str,str]), `transport`
            (str ∈ {`stdio`, `streamable_http`, `in_memory`} per PRD
            FR7), `tools` (dict[str, JSON Schema] — Phase-1 declarative
            extension).

        Raises:
            InvalidMCPServerConfigError: On any structural failure —
                file not found, wrong extension, malformed JSON, missing
                `command`, wrong types, unsupported transport. The
                `field_name` attribute carries an RFC 6901 JSON Pointer
                into the offending location.
        """
        return parse_mcp_servers(path)

    @keyword(name="Get Tool Schema")
    @tier(1)
    def get_tool_schema(
        self,
        config_path: str | Path,
        tool_name: str,
        server_name: str | None = None,
    ) -> dict[str, Any]:
        """Return a tool's input JSON Schema from `.mcp.json:tools`.

        [Tier 1 — Deterministic] — Phase-1 reads from the declarative
        `tools` extension on each server entry (Story 2.3 drift-check
        D-D 2026-05-19). PRD FR6's "against a running or configured
        MCP server" runtime path is Phase-2 + Epic 3 scope.

        Args:
            config_path: Path to the `.mcp.json` file.
            tool_name: Name of the tool whose schema to retrieve.
            server_name: When `None`, search every server in
                declaration order + return the first match. When set,
                only consult the named server.

        Returns:
            The tool's input JSON Schema as a dict.

        Raises:
            InvalidMCPServerConfigError: On `.mcp.json` structural
                failure.
            InvalidMCPToolSchemaError: If the tool is not declared on
                any candidate server (or on the named server when
                `server_name` is set).
        """
        return get_tool_schema(config_path, tool_name=tool_name, server_name=server_name)

    @keyword(name="Validate Tool Schema")
    @tier(1)
    def validate_tool_schema(
        self,
        config_path: str | Path,
        tool_name: str,
        server_name: str | None = None,
    ) -> None:
        """Validate a tool's schema against the jsonschema Draft 2020-12 meta-schema.

        [Tier 1 — Deterministic] — verifies the schema-validity of an
        MCP tool's input schema. Does NOT validate any tool-call's
        ARGUMENTS against the schema — that's a runtime concern Epic 3
        will own. Median ≤ 50 ms per NFR-PERF-02.

        Args:
            config_path: Path to the `.mcp.json` file.
            tool_name: Tool whose schema to validate.
            server_name: Optional server scoping (see `Get Tool Schema`).

        Returns:
            None on success.

        Raises:
            InvalidMCPServerConfigError: On `.mcp.json` structural
                failure.
            InvalidMCPToolSchemaError: If the tool is not declared OR
                its schema fails Draft 2020-12 meta-schema validation.
                `field_name` carries an RFC 6901 JSON Pointer into the
                offending sub-schema; the wrapped jsonschema exception
                is available via `__cause__`.
        """
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
        """Build an MCP server handle per PRD FR7.

        [Tier 1 — Deterministic] — pure handle construction. For
        `stdio` + `in_memory` transports, this DOES NOT spawn or
        instantiate the server yet (per Story 3.1 Phase-1 per-call-
        session design); the actual server start happens during
        `Connect To Server`. The `streamable_http` transport name is
        accepted as a Phase-1 passthrough; full HTTP round-trip
        support lands Phase-1.5 OR Epic 3 Story 3.2.

        Args:
            name: Caller-chosen server identifier (echoed in errors).
            transport: One of `"stdio"` / `"streamable_http"` /
                `"in_memory"` per PRD FR7 transport enum.
            command: stdio only — executable path/name (e.g.,
                `"python"`).
            args: stdio only — command-line arguments.
            env: stdio only — environment overlay.
            server_factory: in_memory only — no-arg callable returning
                a `FastMCP` server instance.

        Returns:
            `MCPServerHandle` describing the server target. Consume via
            `Connect To Server`.

        Raises:
            ValueError: If transport-required parameters are missing.
        """
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
        """Open + initialize an MCP `ClientSession`, gate-check the version (PRD FR8 + FR46).

        [Tier 1 — Deterministic] — per Story 3.1 Phase-1 per-call-
        session design, opens the session, runs `initialize()`,
        captures the negotiated protocol version + server info, runs
        the version gate (`UnsupportedMCPVersionError` on out-of-range
        per AC-MCP-OBSERVE-02 + NFR-COMPAT-04 `mcp>=1.0,<2.0`), then
        closes the underlying SDK session. The returned `MCPSession`
        is metadata only — NOT a live SDK session.

        Args:
            handle: An `MCPServerHandle` from `Start Server`.

        Returns:
            `MCPSession` with negotiated `protocol_version` +
            `server_info`.

        Raises:
            UnsupportedMCPVersionError: If the negotiated protocol
                version is outside the agenteval-supported range
                (`mcp>=1.0,<2.0`).
            ValueError: If `handle.transport == "streamable_http"`
                (Phase-1 passthrough; not yet implemented).
        """
        return connect_to_server(handle)

    @keyword(name="Stop Server")
    @tier(1)
    def stop_server(self, handle: MCPServerHandle) -> None:
        """Tear down any per-handle resources.

        [Tier 1 — Deterministic] — Phase-1 no-op (each `Connect To
        Server` self-cleans the SDK session). The keyword ships now so
        `.robot` tests can adopt the canonical 3-step lifecycle
        without breaking when Phase-1.5 introduces pooled sessions
        that need explicit teardown.

        Args:
            handle: The `MCPServerHandle` from `Start Server`.

        Returns:
            None.
        """
        stop_server(handle)

    # --------------------------------------------------------------- #
    # Story 3.2: MCP tool inspection keywords (PRD FR9a + FR9b)
    # --------------------------------------------------------------- #

    @keyword(name="List Tools")
    @tier(1)
    def list_tools(self, handle: MCPServerHandle) -> list[MCPTool]:
        """List the tools advertised by the MCP server at `handle` (PRD FR9a).

        [Tier 1 — Deterministic] — opens a fresh per-call MCP session
        (per Story 3.1 Phase-1 pattern), runs `initialize()`, calls
        the MCP spec's `list_tools` operation, then tears down. Each
        call pays the full handshake cost; Phase-1.5 may introduce
        pooled sessions for hot loops.

        Args:
            handle: An `MCPServerHandle` from `Start Server`.

        Returns:
            A list of `MCPTool` dataclasses (one per advertised tool)
            with `name`, `description`, `input_schema`, and optional
            `output_schema` per the MCP spec.

        Raises:
            ValueError: If transport is `streamable_http` (Phase-1
                passthrough) or required handle params are missing.
            UnsupportedMCPVersionError: If `initialize()` rejects the
                negotiated protocol version.
            MCPConnectionLostError: If the transport layer fails
                mid-call.
        """
        return list_tools(handle)

    @keyword(name="Call Tool")
    @tier(1)
    def call_tool(
        self,
        handle: MCPServerHandle,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        """Invoke a tool by name on the MCP server at `handle` (PRD FR9b).

        [Tier 1 — Deterministic] — given a deterministic server tool,
        opens a fresh per-call MCP session, runs `initialize()`,
        invokes the named tool, computes wall-clock latency, then
        tears down. Tool-LEVEL error responses surface as
        `MCPToolResult(is_error=True, ...)` — first-class data, NOT
        exceptions. Infrastructure failures raise
        `MCPConnectionLostError`.

        Args:
            handle: An `MCPServerHandle` from `Start Server`.
            tool_name: The tool name as advertised by the server.
            arguments: Optional dict of tool-specific arguments
                (default `{}`).

        Returns:
            `MCPToolResult` with `content` (list of content blocks),
            `is_error`, `error_message`, `latency_ms` (wall-clock from
            request-send to response-receive), and per-call
            `correlation_id` (Phase-1 uuid4 hex placeholder; Epic 5
            wires real trace-id lookup).

        Raises:
            ValueError: If transport is `streamable_http` (Phase-1
                passthrough) or required handle params are missing.
            UnsupportedMCPVersionError: If `initialize()` rejects the
                negotiated protocol version.
            MCPConnectionLostError: If the transport layer fails
                mid-call (subprocess crash, anyio stream closed, etc.).
        """
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
        """Drive N-trial discoverability evaluation of an MCP server's tools (PRD FR10a).

        [Tier 3 — Stochastic Fan-Out] — for each task in the YAML, dispatches
        `trials_per_task` adapter.run() calls and inspects `tool_calls` to
        compute Pass@k with Wilson CI bounds.

        Phase-1 carve-out (DF-4.4-S1): `@guarded_fanout` enforcement of
        `max_cost_usd` + `max_runtime_seconds` is DEFERRED — same architectural
        gap as Story 4.3 DF-4.3-S6 (MCPLibrary is excluded from
        `_SUB_LIBRARIES` per Story 2.2 norm; no clean path to inject
        library-level budgets without architectural change). The kwargs are
        accepted + tracked on the result but NOT enforced. Operators must
        bound cost manually until Phase-1.5 plumbs the cross-library config.

        Phase-1 carve-out (DF-4.1-S2 + DF-4.2-S1): `mcp_server=` is NOT
        forwarded to `adapter.run(mcp_servers=...)` because both Phase-1
        adapters (Generic + Claude Code CLI) raise `NotImplementedError`
        on non-empty `mcp_servers`. The kwarg is accepted for forward-
        compatibility + validated as non-empty; tool-call success is
        gated on what the model returns from prompt alone (useful for
        stub-adapter tests; meaningful for real LLMs only when
        DF-4.1-S2 + DF-4.2-S1 land).

        Empty-`expected_tools` semantics (Story 4.4 code-review 3-way
        MED-A 2026-05-20): when a task's `expected_tools` is `[]`, the
        keyword treats ANY tool call as success (wildcard mode — useful
        for "did the agent invoke ANY tool?" probes). `competing_tools_picked`
        in this case collects ALL called tool names (since there's no
        expected set to subtract); operators get the same visibility
        regardless of whether `expected_tools` is populated.

        Args:
            mcp_server: Name of the MCP server (per `MCP.Start Server`).
                Must be a non-empty string. Phase-1: accepted but NOT
                forwarded to `adapter.run()` (DF-4.1-S2 + DF-4.2-S1).
            adapter: Adapter name (default `"generic"`).
            model: Model identifier (e.g., `"anthropic/claude-sonnet-4-6"`).
            tasks: Path to the discoverability tasks YAML.
            trials_per_task: Number of trials per task (Pass@k semantics).
            max_cost_usd: Budget cap (Phase-1: tracked, NOT enforced —
                DF-4.4-S1 carry-over).
            max_runtime_seconds: Runtime cap (Phase-1: tracked, NOT enforced).
            **kwargs: Provider/adapter forward-compat kwargs.

        Returns:
            `DiscoverabilityResult` with `per_task_results` + `summary`
            (aggregate pass rate + cost + runtime) + `mcp_coverage`,
            per PRD FR10a L1499 ratified shape.

        Raises:
            InvalidDiscoverabilityTasksError: on tasks YAML parse/schema failure.
            AdapterDiscoveryError: on unknown adapter name.
            ValueError: when required kwargs are missing/empty.
        """
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
