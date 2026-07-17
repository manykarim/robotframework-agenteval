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

"""Bridge an already-connected MCP server onto a pydantic-ai toolset.

The in-process agent adapter (``AgentEval._core.agent_adapter``) lives in
``_core`` and must not import a surface library, so the MCP->pydantic-ai bridge
lives here, in MCPLibrary. It reads a live server's tool list through the same
handle MCPLibrary/MetricsLibrary already use, and for each tool builds a
``pydantic_ai.Tool.from_schema`` over a closure that executes the tool *through*
``MCP.Call Tool``. Routing every model-driven call back through the library's
own ``call_tool`` means one execution path feeds both pydantic-ai's message
history (so the adapter can normalize executed calls into ``AgentRunResult``)
and MCPLibrary's own recorder (so the coverage/metric keywords see the call).

pydantic-ai ships behind the optional ``[agent]`` extra; the import is lazy so
building or importing MCPLibrary never pulls it in.

Sync/async: ``MCP.Call Tool`` is synchronous and drives the server on the warm
session's *own* background event-loop thread (see ``_lifecycle.WarmSession``).
The closure is therefore a plain sync function - when pydantic-ai invokes it the
call blocks the calling thread on a ``concurrent.futures.Future`` that a
*different* thread resolves, so there is no single-loop re-entrancy and no
deadlock, whether pydantic-ai runs the sync tool on its event loop or in a
worker thread.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from AgentEval._core.errors import MissingExtraError

if TYPE_CHECKING:
    from MCPLibrary._lifecycle import MCPServerHandle, MCPTool, MCPToolResult

__all__ = ["build_agent_toolset"]


_MISSING_AGENT = (
    "MCP.As Agent Toolset needs pydantic-ai, which ships with the [agent] extra. "
    "Install it with: pip install 'robotframework-agenteval[agent]'"
)


class _ToolLister(Protocol):
    def __call__(self, handle: MCPServerHandle) -> list[MCPTool]: ...


class _ToolCaller(Protocol):
    def __call__(
        self, handle: MCPServerHandle, tool_name: str, arguments: dict[str, Any] | None = ...
    ) -> MCPToolResult: ...


def _import_pydantic_ai() -> tuple[Any, Any]:
    """Import ``Tool`` + ``FunctionToolset`` lazily, or raise a clear missing-extra error."""
    try:
        from pydantic_ai import Tool
        from pydantic_ai.toolsets import FunctionToolset
    except ImportError as exc:
        raise MissingExtraError(_MISSING_AGENT, extra="agent") from exc
    return Tool, FunctionToolset


def _default_schema() -> dict[str, Any]:
    """A permissive object schema for tools that advertise no input schema."""
    return {"type": "object", "properties": {}}


def _extract_result(result: MCPToolResult) -> Any:
    """Project an ``MCPToolResult`` into the value pydantic-ai records as the tool return.

    Text content blocks are joined into a single string (what the model reads
    and what surfaces as ``ToolCallTrace.result``); anything without text falls
    back to the raw content list. Tool-level errors are returned as their error
    text so the model sees the failure rather than an opaque success.
    """
    if result.is_error:
        return result.error_message or "tool reported an error"
    texts = [
        block["text"]
        for block in result.content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    ]
    if texts:
        return "\n".join(texts)
    return result.content


def _make_tool_function(handle: MCPServerHandle, tool_name: str, call_tool: _ToolCaller) -> Any:
    """Build the closure pydantic-ai calls when the model invokes ``tool_name``.

    Executes the tool through ``call_tool`` (``MCP.Call Tool``) on the shared
    handle so both pydantic-ai's history and MCPLibrary's recorder capture it.
    """

    def _run_mcp_tool(**arguments: Any) -> Any:
        result = call_tool(handle, tool_name, arguments=arguments or None)
        return _extract_result(result)

    _run_mcp_tool.__name__ = tool_name
    return _run_mcp_tool


def build_agent_toolset(
    handle: MCPServerHandle,
    *,
    list_tools: _ToolLister,
    call_tool: _ToolCaller,
) -> Any:
    """Build a pydantic-ai ``FunctionToolset`` over a connected MCP server.

    ``list_tools`` and ``call_tool`` are MCPLibrary's own keyword methods bound
    to a library instance, so listing and every subsequent model-driven call go
    through the one warm session and land in MCPLibrary's recorder. Returns a
    ``FunctionToolset`` ready to hand to ``get_adapter("in-process",
    toolsets=[...])``. Raises ``MissingExtraError`` naming ``[agent]`` if
    pydantic-ai is absent.
    """
    tool_cls, function_toolset_cls = _import_pydantic_ai()
    toolset = function_toolset_cls()
    for tool in list_tools(handle):
        schema = tool.input_schema if isinstance(tool.input_schema, dict) and tool.input_schema else _default_schema()
        toolset.add_tool(
            tool_cls.from_schema(
                function=_make_tool_function(handle, tool.name, call_tool),
                name=tool.name,
                description=tool.description or None,
                json_schema=schema,
            )
        )
    return toolset
