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

"""Subagent `.md` frontmatter parser (Story 2.2).

Reads the YAML frontmatter block between leading `---` delimiters at the
top of a sub-agent `.md` file per PRD FR3 + the Claude Code sub-agent
format. Raises `InvalidSubagentDefinitionError` on structural failure
with the FR59 4-element layout (`docs/contracts/error-class-hierarchy.md`
L96-104).

Story 2.2 design notes:
- Mirrors `skills/_parser.py` shape (column-0 `---` delimiter via
  `.rstrip()`, `utf-8-sig` encoding to handle BOM, one-line YAML error
  summary via `exc.problem`).
- PRD FR3 (amended Story 2.2 code-review 2026-05-19) required fields:
  `name`, `description`. Optional: `tools`, `model`. The required-fields
  contract is intentionally narrower than the skill format (no
  tool-allowlist or model-invocation switch — the sub-agent is itself
  an actor, not a tool surface).
- Architecture-layout deviation (inherited from Story 2.1): architecture
  L843-847 pins `_internal.py` as the canonical helper module name.
  Story 2.2 inherits Story 2.1's `_parser.py` deviation (clarity > strict
  convention for the Phase-1 parser modules); tracked in deferred-work
  for Phase-1.5 cleanup. Auditor MED-2 fix 2026-05-19 added this note
  so future grep-for-debt finds ALL Phase-1 deviations in one search.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from AgentEval.errors import InvalidSubagentDefinitionError

__all__ = [
    "REQUIRED_FIELDS",
    "parse_subagent_frontmatter",
    "validate_subagent_structure",
]


# PRD FR3 sub-agent format: `name` + `description` are required; `tools`
# + `model` are optional. Phase-1 validates only the required pair.
REQUIRED_FIELDS: tuple[str, ...] = ("name", "description")


def parse_subagent_frontmatter(path: str | Path) -> dict[str, Any]:
    """Parse the YAML frontmatter at the head of a sub-agent `.md` file.

    Args:
        path: Filesystem path to the sub-agent `.md` file.

    Returns:
        The parsed YAML frontmatter as a dict.

    Raises:
        InvalidSubagentDefinitionError: On any YAML / file-level
            structural failure. Mirrors `skills/_parser.parse_frontmatter`'s
            contract; only the raised error class differs.
    """
    file_path = Path(path)
    file_path_str = str(file_path)

    if file_path.suffix != ".md":
        raise InvalidSubagentDefinitionError(
            f"Sub-agent file must have a .md extension; got {file_path.suffix!r}.",
            file_path=file_path_str,
            fix_suggestion="Rename the file so it ends in `.md`.",
        )

    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise InvalidSubagentDefinitionError(
            f"Sub-agent file not found: {file_path_str}.",
            file_path=file_path_str,
            fix_suggestion="Check the path; ensure the file exists and is readable.",
        ) from exc
    except OSError as exc:
        raise InvalidSubagentDefinitionError(
            f"Sub-agent file could not be read: {exc}.",
            file_path=file_path_str,
            fix_suggestion="Check the file's permissions + encoding (expected UTF-8).",
        ) from exc

    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        raise InvalidSubagentDefinitionError(
            "Sub-agent file missing leading `---` YAML frontmatter delimiter at column 0.",
            file_path=file_path_str,
            line_number=1,
            fix_suggestion="Add `---` as the first line (column 0), followed by YAML, then a closing `---`.",
        )

    end_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            end_index = index
            break
    if end_index is None:
        raise InvalidSubagentDefinitionError(
            "Sub-agent file missing closing `---` YAML frontmatter delimiter at column 0.",
            file_path=file_path_str,
            line_number=len(lines),
            fix_suggestion="Add a closing `---` line (column 0) after the YAML block.",
        )

    yaml_block = "\n".join(lines[1:end_index])

    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        mark_line: int | None = None
        if mark is not None and hasattr(mark, "line"):
            mark_line = int(mark.line) + 1 + 1
        problem = getattr(exc, "problem", None)
        yaml_summary = str(problem) if problem else (str(exc).splitlines()[0] if str(exc) else "YAML parse error")
        raise InvalidSubagentDefinitionError(
            f"YAML frontmatter failed to parse: {yaml_summary}.",
            file_path=file_path_str,
            line_number=mark_line,
            fix_suggestion=(
                "Check YAML indentation + quoting; run a YAML linter on the block between the `---` delimiters."
            ),
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidSubagentDefinitionError(
            f"YAML frontmatter must be a mapping; got {type(parsed).__name__}.",
            file_path=file_path_str,
            line_number=2,
            fix_suggestion="Use `key: value` pairs inside the `---` delimiters.",
        )

    return parsed


def validate_subagent_structure(
    frontmatter: dict[str, Any],
    *,
    file_path: str | None = None,
) -> None:
    """Validate a parsed sub-agent frontmatter dict per PRD FR3.

    Required: `name` (non-empty str), `description` (non-empty str).
    Optional but type-checked when present: `tools` (list[str]),
    `model` (str).

    Args:
        frontmatter: The dict returned by `parse_subagent_frontmatter()`.
        file_path: Optional source path for diagnostics (echoed back).

    Raises:
        InvalidSubagentDefinitionError: If any required field is missing
            OR a present field violates its type contract.
    """
    missing = [field for field in REQUIRED_FIELDS if field not in frontmatter]
    if missing:
        raise InvalidSubagentDefinitionError(
            f"Sub-agent frontmatter missing required field(s): {missing!r}.",
            file_path=file_path,
            field_name=",".join(missing),
            fix_suggestion=(f"Add the missing field(s) per PRD FR3. Required: {list(REQUIRED_FIELDS)!r}."),
        )

    name = frontmatter["name"]
    if not isinstance(name, str) or not name:
        raise InvalidSubagentDefinitionError(
            f"`name` must be a non-empty string; got {type(name).__name__}.",
            file_path=file_path,
            field_name="name",
            fix_suggestion="Set `name: <non-empty string>` in the YAML block.",
        )

    description = frontmatter["description"]
    if not isinstance(description, str) or not description:
        raise InvalidSubagentDefinitionError(
            f"`description` must be a non-empty string; got {type(description).__name__}.",
            file_path=file_path,
            field_name="description",
            fix_suggestion="Set `description: <non-empty string>` in the YAML block.",
        )

    if "tools" in frontmatter:
        tools = frontmatter["tools"]
        if not isinstance(tools, list) or any(not isinstance(tool, str) for tool in tools):
            raise InvalidSubagentDefinitionError(
                f"`tools` (optional) must be a list of strings; got {type(tools).__name__}.",
                file_path=file_path,
                field_name="tools",
                fix_suggestion="Set `tools: [tool_a, tool_b]` as a YAML list of strings, or omit the field.",
            )

    if "model" in frontmatter:
        model = frontmatter["model"]
        if not isinstance(model, str) or not model:
            raise InvalidSubagentDefinitionError(
                f"`model` (optional) must be a non-empty string; got {type(model).__name__}.",
                file_path=file_path,
                field_name="model",
                fix_suggestion="Set `model: <model-identifier>` or omit the field for the default.",
            )
