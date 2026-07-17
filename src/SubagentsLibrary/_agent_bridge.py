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

"""Shim: load Claude-style subagent ``.md`` files into a harness ``SubAgents``.

Claude Code writes each subagent as a markdown file with ``name`` /
``description`` / ``tools`` frontmatter under ``.claude/agents/``. The
pydantic-ai-harness ``SubAgents`` capability auto-discovers exactly that shape
from any folder you point ``agent_folders`` at, building one delegate per file
with the parent run's model. This shim wires a directory of those files into a
``SubAgents`` capability the in-process adapter can carry, tolerating Claude's
extra frontmatter keys (``model`` / ``color`` / ...) which the harness parser
ignores.

``allowed-tools`` is NOT enforced here (see the adapter ``validation_ceiling``):
by default a no-op ``tool_resolver`` maps every declared tool name to zero
toolsets, so a subagent can still be *routed to* without granting real tools.
Pass a real ``tool_resolver`` to attach toolsets by name. pydantic-ai +
pydantic-ai-harness ship with the ``[agent]`` extra and are imported lazily.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from AgentEval._core import InvalidConfigError
from AgentEval._core.errors import MissingExtraError

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["load_subagents_capability", "noop_tool_resolver"]

_MISSING_AGENT = (
    "SubagentsLibrary's in-process subagent bridge needs pydantic-ai + "
    "pydantic-ai-harness, which ship with the [agent] extra. Install with: "
    "pip install 'robotframework-agenteval[agent]'"
)


def noop_tool_resolver(tool_name: str) -> tuple[Any, ...]:
    """Resolve any declared subagent tool name to *no* toolsets, without warning.

    Returning an empty sequence (rather than ``None``) tells the harness the name
    is known-but-grants-nothing, so it attaches no tools and emits no
    ``Unknown tool`` warning. This is the proxy default: a subagent is routable
    without its Claude ``tools`` list being honored (per the validation ceiling).
    """
    return ()


def load_subagents_capability(
    agents_dir: str | Path,
    *,
    tool_resolver: Any = None,
    tool_name: str = "delegate_task",
    **kwargs: Any,
) -> Any:
    """Build a harness ``SubAgents`` capability from a dir of Claude subagent ``.md``.

    ``agents_dir`` must be an existing directory holding at least one ``.md``
    subagent definition; an absent directory or one with no ``.md`` files raises
    ``InvalidConfigError`` rather than yielding a silently empty capability.
    ``tool_resolver`` defaults to :func:`noop_tool_resolver`; pass a callable
    ``(tool_name) -> Sequence[AgentToolset] | None`` to attach real toolsets.
    Extra ``kwargs`` pass through to ``SubAgents`` (e.g. ``inherit_tools=True``).
    """
    try:
        from pydantic_ai_harness.subagents import SubAgents
    except ImportError as exc:
        raise MissingExtraError(_MISSING_AGENT, extra="agent") from exc

    dir_path = Path(agents_dir)
    if not dir_path.is_dir():
        raise InvalidConfigError(
            f"Subagent directory not found (or not a directory): {dir_path}.",
            file_path=str(dir_path),
            fix="Point the keyword at an existing folder of Claude subagent `.md` files.",
        )
    md_files = sorted(dir_path.glob("*.md"))
    if not md_files:
        raise InvalidConfigError(
            f"Subagent directory holds no `.md` files: {dir_path}.",
            file_path=str(dir_path),
            fix="Add at least one Claude subagent `.md` (name/description frontmatter) to the folder.",
        )

    resolver = tool_resolver if tool_resolver is not None else noop_tool_resolver
    folders: Sequence[Path] = [dir_path]
    return SubAgents(
        agent_folders=folders,
        tool_resolver=resolver,
        tool_name=tool_name,
        **kwargs,
    )
