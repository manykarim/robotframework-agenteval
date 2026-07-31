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

"""Robot Framework library for testing MCP servers.

Three things, all under the ``MCP.`` prefix:

- *Schema* keywords read and validate a ``.mcp.json`` config with no server
  running - the base install is enough.
- *Live* keywords start a server, list and call its tools, and stop it. They
  need the MCP SDK from the ``[mcp]`` extra.
- *Coverage* keywords score which tools got exercised, and a Tier-3
  discoverability keyword drives a real agent and scores its tool picks.
"""

from __future__ import annotations

import importlib.util
import time
from typing import TYPE_CHECKING, Any, cast

from robot.api.deco import keyword

from AgentEval._core import tier
from AgentEval._core.errors import MCPError, MissingExtraError
from AgentEval._core.types import AgentRunResult, ToolCallTrace
from MCPLibrary import _config, _coverage
from MCPLibrary._discoverability import (
    DiscoverabilityResult,
    load_discoverability_tasks,
    run_discoverability,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from MCPLibrary._lifecycle import MCPServerHandle, MCPSession, MCPTool, MCPToolResult

__all__ = ["MCPLibrary"]

# The module the live keywords need. Overridable so tests can exercise the
# missing-extra path without uninstalling anything.
_LIVE_BACKEND_PROBE = "mcp"


def _load_backend() -> Any:
    """Import the live-server backend, or raise a clear missing-extra error."""
    if importlib.util.find_spec(_LIVE_BACKEND_PROBE) is None:
        raise MissingExtraError(
            "Live MCP server keywords need the MCP SDK from the [mcp] extra. "
            "Install it with: pip install 'robotframework-agenteval[mcp]'",
            extra="mcp",
        )
    from MCPLibrary import _lifecycle

    return _lifecycle


class MCPLibrary:
    """Test MCP servers: validate schemas, drive tools, score discoverability."""

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self) -> None:
        # Every ``MCP.Call Tool`` invocation is recorded here as a
        # ``ToolCallTrace`` so the coverage keywords can score live calls
        # natively (no hand-rolled projection). Reset with
        # ``MCP.Clear Recorded Tool Calls``.
        self._recorded_calls: list[ToolCallTrace] = []

    # ------------------------------------------------------------------ #
    # Schema keywords - Tier 1, no live server needed.                    #
    # ------------------------------------------------------------------ #

    @keyword(name="MCP.Get Server Config")
    @tier(1)
    def get_server_config(self, path: str) -> dict[str, dict[str, Any]]:
        """Parse a ``.mcp.json`` file into a ``{server_name: entry}`` dict.

        Pure file read and JSON parse - no server is spawned. Each entry has at
        least ``command`` and may carry ``args``, ``env``, ``transport``, and a
        declarative ``tools`` map.

        Example:
        | ${servers}=    MCP.Get Server Config    ${CURDIR}/.mcp.json
        | Should Be Equal    ${servers}[echo][transport]    stdio
        """
        return _config.parse_mcp_servers(path)

    @keyword(name="MCP.Get Tool Schema")
    @tier(1)
    def get_tool_schema(self, config_path: str, tool_name: str, server_name: str | None = None) -> dict[str, Any]:
        """Return a declared tool's input JSON Schema from the config.

        With ``server_name`` unset, every server is searched in order and the
        first match wins. Fails if the tool is not declared anywhere.

        Example:
        | ${schema}=    MCP.Get Tool Schema    ${CURDIR}/.mcp.json    search
        | Should Be Equal    ${schema}[type]    object
        """
        return _config.get_tool_schema(config_path, tool_name=tool_name, server_name=server_name)

    @keyword(name="MCP.Validate Tool Schema")
    @tier(1)
    def validate_tool_schema(self, config_path: str, tool_name: str, server_name: str | None = None) -> None:
        """Check a declared tool's schema against JSON Schema Draft 2020-12.

        Passes on a well-formed schema; a malformed one fails with a JSON
        Pointer to the offending field. Runs with no server - schema validity
        is a static property of the config.

        Example:
        | MCP.Validate Tool Schema    ${CURDIR}/.mcp.json    search
        """
        _config.validate_tool_schema(config_path, tool_name=tool_name, server_name=server_name)

    # ------------------------------------------------------------------ #
    # Live keywords - Tier 1, need the [mcp] extra.                       #
    # ------------------------------------------------------------------ #

    @keyword(name="MCP.Start Server")
    @tier(1)
    def start_server(
        self,
        name: str,
        transport: str,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        server_factory: Callable[[], Any] | None = None,
    ) -> MCPServerHandle:
        """Build a server handle for a later connect/list/call/stop.

        ``transport`` is ``stdio`` (needs ``command``/``args``/``env``) or
        ``in_memory`` (needs ``server_factory``). Nothing is spawned yet - the
        session opens on the first operation. Needs the ``[mcp]`` extra.

        Example:
        | ${h}=    MCP.Start Server    echo    stdio    command=python    args=${{['-m', 'my.echo']}}
        """
        backend = _load_backend()
        return cast(
            "MCPServerHandle",
            backend.start_server(
                name=name,
                transport=transport,
                command=command,
                args=args,
                env=env,
                server_factory=server_factory,
            ),
        )

    @keyword(name="MCP.Connect To Server")
    @tier(1)
    def connect_to_server(self, handle: MCPServerHandle) -> MCPSession:
        """Open a session, run the MCP handshake, and check the protocol version.

        Returns handshake metadata (negotiated version + server info). The
        session is torn down before the keyword returns. Needs the ``[mcp]``
        extra.

        Example:
        | ${session}=    MCP.Connect To Server    ${h}
        | Should Not Be Empty    ${session.protocol_version}
        """
        backend = _load_backend()
        return cast("MCPSession", backend.connect_to_server(handle))

    @keyword(name="MCP.Get Server Instructions")
    @tier(1)
    def get_server_instructions(self, session: MCPSession) -> str | None:
        """Return the server's advertised ``instructions``, or ``None`` if it ships none.

        The ``instructions`` field of the MCP handshake is a server's own
        how-to-use-me guidance. A compliant client surfaces it to the model; read
        it here to assert a server ships the expected guidance (config-drift), or to
        inject it into the in-process adapter
        (``get_adapter("in-process", instructions=${session.instructions})``).

        Example:
        | ${session}=    MCP.Connect To Server    ${h}
        | ${guide}=    MCP.Get Server Instructions    ${session}
        | Log    ${guide}
        """
        return session.instructions

    @keyword(name="MCP.List Tools")
    @tier(1)
    def list_tools(self, handle: MCPServerHandle) -> list[MCPTool]:
        """List the tools a server advertises.

        Opens a fresh session, lists tools (following pagination), tears down.
        Each entry has ``name``, ``description``, ``input_schema``, and an
        optional ``output_schema``. Needs the ``[mcp]`` extra.

        Example:
        | @{tools}=    MCP.List Tools    ${h}
        | Should Contain    ${{[t.name for t in $tools]}}    echo_back
        """
        backend = _load_backend()
        return cast("list[MCPTool]", backend.list_tools(handle))

    @keyword(name="MCP.Call Tool")
    @tier(1)
    def call_tool(
        self,
        handle: MCPServerHandle,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> MCPToolResult:
        """Call a tool by name and return its result.

        Pass arguments either as natural Robot Framework keyword arguments
        (``text=hi``) or as a single ``arguments=`` dict - not both. Supplying
        both forms is rejected. A tool that reports an error comes back as
        ``is_error=True`` data; a lost connection raises. Needs the ``[mcp]``
        extra.

        Example (named args):
        | ${r}=    MCP.Call Tool    ${h}    echo_back    text=hello
        | Should Be Equal    ${r.content}[0][text]    hello

        Example (dict form, for non-string or reserved-name arguments):
        | ${r}=    MCP.Call Tool    ${h}    echo_back    arguments=${{ {'text': 'hi'} }}
        """
        if kwargs and arguments is not None:
            raise MCPError(
                "MCP.Call Tool got both an `arguments=` dict and inline keyword arguments; "
                "supply only one form. Use inline args (tool    name=value) for simple string "
                "values, or `arguments=` for non-string values or names that collide with "
                "`handle` / `tool_name` / `arguments`."
            )
        backend = _load_backend()
        effective = arguments if arguments is not None else (dict(kwargs) if kwargs else None)
        result = cast("MCPToolResult", backend.call_tool(handle, tool_name, effective))
        self._recorded_calls.append(
            ToolCallTrace(
                name=tool_name,
                args=effective or {},
                result=result.content,
                error=result.error_message if result.is_error else None,
                latency_ms=result.latency_ms,
                source="hosted_mcp",
            )
        )
        return result

    @keyword(name="MCP.As Agent Toolset")
    @tier(1)
    def as_agent_toolset(self, handle: MCPServerHandle) -> Any:
        """Expose a connected server's tools as a pydantic-ai toolset for the in-process agent.

        Lists the tools on ``handle`` and wraps each as a pydantic-ai tool whose
        execution routes back through ``MCP.Call Tool`` on this same library
        instance - so a model driven by ``get_adapter("in-process",
        toolsets=[...])`` runs the *real* server, and every call it makes lands
        in both the agent's result and this library's recorder
        (``MCP.Get Recorded Tool Calls``). Connect the handle first. Needs the
        ``[agent]`` extra (pydantic-ai) on top of ``[mcp]``.

        Example:
        | ${h}=    MCP.Start Server    echo    in_memory    server_factory=${{build_echo_server}}
        | MCP.Connect To Server    ${h}
        | ${toolset}=    MCP.As Agent Toolset    ${h}
        | ${agent}=    Evaluate    AgentEval.get_adapter('in-process', toolsets=[$toolset])
        | ${result}=    Evaluate    $agent.run("Use echo_back on 'hi', then say DONE")
        """
        from MCPLibrary._agent_bridge import build_agent_toolset

        return build_agent_toolset(handle, list_tools=self.list_tools, call_tool=self.call_tool)

    @keyword(name="MCP.Stop Server")
    @tier(1)
    def stop_server(self, handle: MCPServerHandle) -> None:
        """Release any resources for a server handle.

        Sessions self-clean after each operation, so this is a no-op today; use
        it to keep the start/connect/stop shape in your tests. Needs the
        ``[mcp]`` extra.

        Example:
        | MCP.Stop Server    ${h}
        """
        backend = _load_backend()
        backend.stop_server(handle)

    # ------------------------------------------------------------------ #
    # Coverage keywords - Tier 1, over the shared trace projection.       #
    # ------------------------------------------------------------------ #

    @keyword(name="MCP.Get Recorded Tool Calls")
    @tier(1)
    def get_recorded_tool_calls(self) -> list[ToolCallTrace]:
        """Return the ``ToolCallTrace`` list recorded from live ``MCP.Call Tool`` calls.

        Every ``MCP.Call Tool`` invocation on this library instance is captured
        (``source="hosted_mcp"``), so the coverage keywords score live calls
        directly - no hand-rolled projection. Names and arguments come from the
        call inputs; ``result``/``error``/``latency_ms`` from its result. Reset
        with ``MCP.Clear Recorded Tool Calls``.

        Example:
        | MCP.Call Tool    ${h}    search    query=robots
        | ${calls}=    MCP.Get Recorded Tool Calls
        | ${n}=    MCP.Get Tool Call Count    ${calls}
        | Should Be Equal As Integers    ${n}    1
        """
        return list(self._recorded_calls)

    @keyword(name="MCP.Clear Recorded Tool Calls")
    @tier(1)
    def clear_recorded_tool_calls(self) -> None:
        """Drop all recorded ``MCP.Call Tool`` traces - call between tests to reset.

        Example:
        | MCP.Clear Recorded Tool Calls
        | ${calls}=    MCP.Get Recorded Tool Calls
        | Should Be Empty    ${calls}
        """
        self._recorded_calls.clear()

    @keyword(name="MCP.Get Tool Call Count")
    @tier(1)
    def get_tool_call_count(self, run: AgentRunResult | list[AgentRunResult] | list[ToolCallTrace]) -> int:
        """Count tool calls in a run, a list of runs, or a trace-call list.

        Example:
        | ${n}=    MCP.Get Tool Call Count    ${result}
        | Should Be Equal As Integers    ${n}    3
        """
        return _coverage.tool_call_count(run)

    @keyword(name="MCP.Get Tool Call Names")
    @tier(1)
    def get_tool_call_names(self, run: AgentRunResult | list[AgentRunResult] | list[ToolCallTrace]) -> list[str]:
        """Tool-call names in order, duplicates preserved.

        Example:
        | @{names}=    MCP.Get Tool Call Names    ${result}
        | Should Contain    ${names}    search
        """
        return _coverage.tool_call_names(run)

    @keyword(name="MCP.Get Tool Hit Rate")
    @tier(1)
    def get_tool_hit_rate(
        self,
        run: AgentRunResult | list[AgentRunResult] | list[ToolCallTrace],
        expected_tools: list[str],
    ) -> float:
        """Fraction of expected tools that were actually called (0.0 if none expected).

        Example:
        | ${rate}=    MCP.Get Tool Hit Rate    ${result}    ${{['search', 'fetch']}}
        | Should Be True    ${rate} >= 0.5
        """
        return _coverage.tool_hit_rate(run, expected_tools)

    @keyword(name="MCP.Get Tool Success Rate")
    @tier(1)
    def get_tool_success_rate(self, run: AgentRunResult | list[AgentRunResult] | list[ToolCallTrace]) -> float:
        """Fraction of tool calls that returned without an error (0.0 if no calls).

        Example:
        | ${rate}=    MCP.Get Tool Success Rate    ${result}
        | Should Be True    ${rate} >= 0.8
        """
        return _coverage.tool_success_rate(run)

    @keyword(name="MCP.Get Unnecessary Call Rate")
    @tier(1)
    def get_unnecessary_call_rate(
        self,
        run: AgentRunResult | list[AgentRunResult] | list[ToolCallTrace],
        expected_tools: list[str],
    ) -> float:
        """Fraction of tool calls that were not in ``expected_tools`` (0.0 if no calls).

        Example:
        | ${noise}=    MCP.Get Unnecessary Call Rate    ${result}    ${{['search']}}
        | Should Be True    ${noise} <= 0.2
        """
        return _coverage.unnecessary_call_rate(run, expected_tools)

    @keyword(name="MCP.Was Tool Called")
    @tier(1)
    def was_tool_called(
        self,
        run: AgentRunResult | list[AgentRunResult] | list[ToolCallTrace],
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> bool:
        """True if ``tool_name`` was called, optionally with ``arguments`` as a subset.

        Use it to assert an expected tool ran - or, negated, that one never did.

        Example:
        | ${hit}=    MCP.Was Tool Called    ${result}    search    ${{ {'query': 'robots'} }}
        | Should Be True    ${hit}
        """
        return _coverage.was_tool_called(run, tool_name, arguments)

    # ------------------------------------------------------------------ #
    # Discoverability - Tier 3, drives a real agent.                      #
    # ------------------------------------------------------------------ #

    @keyword(name="MCP.Get Tool Discoverability")
    @tier(3)
    def get_tool_discoverability(
        self,
        tasks: str,
        adapter: str | Any = "generic",
        model: str | None = None,
        mcp_server: str = "",
        trials_per_task: int = 3,
        **kwargs: Any,
    ) -> DiscoverabilityResult:
        """Drive an agent over a task set and score whether it picks the right tools.

        For each task, runs the adapter ``trials_per_task`` times and checks the
        tool calls against the task's ``expected_tools`` (any tool counts when a
        task expects none). Returns per-task Pass@k with Wilson bounds plus an
        aggregate summary. ``adapter`` is a slug (default ``generic``) or an
        object with ``run(prompt) -> AgentRunResult``. Cross-adapter comparison
        is out of scope for this library.

        Example:
        | ${r}=    MCP.Get Tool Discoverability    ${CURDIR}/tasks.yaml    model=anthropic/claude-sonnet-4-6
        | Should Be True    0.0 <= ${r.summary.overall_pass_rate} <= 1.0
        """
        t_start = time.monotonic()
        if not tasks:
            raise ValueError("MCP.Get Tool Discoverability requires `tasks=<yaml-path>`")
        if trials_per_task < 1:
            raise ValueError(f"trials_per_task must be >= 1; got {trials_per_task}")
        _ = mcp_server  # accepted for forward-compat; not forwarded to the adapter
        task_list = load_discoverability_tasks(tasks)
        return run_discoverability(
            tasks=task_list,
            adapter=adapter,
            model=model,
            trials_per_task=trials_per_task,
            extra_adapter_kwargs=dict(kwargs),
            t_start=t_start,
        )
