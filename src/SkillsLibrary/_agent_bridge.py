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

"""Bridge a Claude-style ``SKILL.md`` onto a deferred pydantic-ai ``Capability``.

The in-process agent adapter (``AgentEval._core.agent_adapter``) lives in
``_core`` and must not import a surface library, so the ``SKILL.md``->Capability
shim lives here, in SkillsLibrary. It reuses SkillsLibrary's own frontmatter
parser (``_parser.parse_frontmatter`` + ``validate_frontmatter_structure``) and
maps the skill onto a *deferred* capability:

    name        -> Capability.id
    description -> Capability.description
    body        -> Capability.instructions   (markdown after the frontmatter)
    (always)       defer_loading=True

``defer_loading=True`` is the whole point: pydantic-ai advertises only the
skill's ``description`` up front and the model *activates* the skill by calling
the framework ``load_capability({"id": ...})`` tool - which the adapter records
as a normal tool call, so activation is derivable from
``AgentRunResult.tool_calls`` (see ``Skill.Get Activated Skills``).

VALIDATION CEILING: this maps only ``name``/``description``/body. The Claude
``allowed-tools`` and ``disable-model-invocation`` frontmatter fields are NOT
enforced - pydantic-ai capabilities have no equivalent, so a model that
activates the skill may still call tools the skill would forbid. This is a proxy
for a competent generic agent's treatment of the skill's *discoverability*, not
a Claude-runtime tool-permission sandbox.

pydantic-ai ships behind the optional ``[agent]`` extra; the import is lazy so
building or importing SkillsLibrary never pulls it in.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from AgentEval._core.errors import MissingExtraError
from SkillsLibrary._parser import parse_frontmatter, validate_frontmatter_structure

__all__ = ["skill_to_capability", "load_capabilities_from_dir", "read_skill_body"]


_MISSING_AGENT = (
    "Skill.As Capability needs pydantic-ai, which ships with the [agent] extra. "
    "Install it with: pip install 'robotframework-agenteval[agent]'"
)


def _import_capability() -> Any:
    """Import ``Capability`` lazily, or raise a clear missing-extra error."""
    try:
        from pydantic_ai.capabilities import Capability
    except ImportError as exc:
        raise MissingExtraError(_MISSING_AGENT, extra="agent") from exc
    return Capability


def read_skill_body(path: str | Path) -> str:
    """Return the markdown body of a skill ``.md`` file (everything after the frontmatter).

    Mirrors ``_parser.parse_frontmatter``'s delimiter scan: the body is whatever
    follows the closing ``---`` line, stripped of surrounding whitespace. A file
    whose frontmatter is not closed is rejected by ``parse_frontmatter`` first,
    so by the time this runs a closing delimiter is guaranteed to exist.
    """
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    # lines[0] is the leading `---`; find the closing `---` and take the rest.
    end_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            end_index = index
            break
    if end_index is None:
        return ""
    return "\n".join(lines[end_index + 1 :]).strip()


def skill_to_capability(path: str | Path) -> Any:
    """Load one Claude-style ``SKILL.md`` into a deferred pydantic-ai ``Capability``.

    Reuses SkillsLibrary's frontmatter parser + validator (so the same required
    ``name``/``description`` contract applies) and maps name->id,
    description->description, body->instructions, ``defer_loading=True``. The
    ``allowed-tools`` / ``disable-model-invocation`` fields are parsed+validated
    but NOT carried onto the capability (pydantic-ai does not enforce them - see
    this module's validation-ceiling note). Raises ``MissingExtraError`` naming
    ``[agent]`` if pydantic-ai is absent, or ``InvalidConfigError`` if the skill
    frontmatter is malformed.
    """
    capability_cls = _import_capability()
    frontmatter = parse_frontmatter(path)
    validate_frontmatter_structure(frontmatter, file_path=str(path))
    name = str(frontmatter["name"])
    description = str(frontmatter["description"])
    body = read_skill_body(path)
    return capability_cls(
        id=name,
        description=description,
        instructions=body or description,
        defer_loading=True,
    )


def load_capabilities_from_dir(directory: str | Path, *, pattern: str = "*.md") -> list[Any]:
    """Load every skill ``.md`` under ``directory`` into a deferred ``Capability``.

    Globs ``directory`` (non-recursively by default via ``pattern``) in sorted
    order for deterministic capability ordering, mapping each file through
    `skill_to_capability`. Raises ``MissingExtraError`` naming ``[agent]`` if
    pydantic-ai is absent, ``FileNotFoundError`` if ``directory`` does not exist,
    or ``InvalidConfigError`` on the first malformed skill file.
    """
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise FileNotFoundError(f"skills directory not found: {dir_path}")
    # Fail loud early on a missing extra rather than after globbing.
    _import_capability()
    return [skill_to_capability(p) for p in sorted(dir_path.glob(pattern))]
