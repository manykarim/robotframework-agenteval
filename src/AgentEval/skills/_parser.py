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

"""Skill `.md` frontmatter parser (Story 2.1).

Reads the YAML frontmatter block between leading `---` delimiters at the
top of a `.md` file and returns it as a `dict[str, Any]`. Raises
`InvalidSkillFrontmatterError` per FR59 on any structural failure with
the structured `(file_path, line_number, field_name, fix_suggestion)`
attributes set so callers can react programmatically.

Per architecture L832-849: `_parser.py` is the sub-library's
implementation-helper module (the `_internal.py`-equivalent named for
its specific purpose). `library.py` owns the user-facing
`@keyword`-decorated methods + the structural validators that surface
`InvalidSkillFrontmatterError` to the test author.

Phase-1 scope: structural validation only. No expression evaluation of
frontmatter values; no model-API-key gated activation (FR4 lands in
Epic 7). The 4 required fields are `name`, `description`,
`allowed-tools`, `disable-model-invocation`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from AgentEval.errors import InvalidSkillFrontmatterError

__all__ = [
    "REQUIRED_FIELDS",
    "parse_frontmatter",
    "validate_frontmatter_structure",
]


REQUIRED_FIELDS: tuple[str, ...] = (
    "name",
    "description",
    "allowed-tools",
    "disable-model-invocation",
)


def parse_frontmatter(path: str | Path) -> dict[str, Any]:
    """Parse the YAML frontmatter at the head of a skill `.md` file.

    Args:
        path: Filesystem path to the skill `.md` file (string or Path).

    Returns:
        The parsed YAML frontmatter as a dict.

    Raises:
        InvalidSkillFrontmatterError: On any structural failure — file
            does not exist, wrong extension, missing delimiters, broken
            YAML, or frontmatter that doesn't parse to a mapping. The
            error's `file_path`, `line_number`, `field_name`,
            `fix_suggestion` attributes are populated for callers that
            need machine-readable diagnostics.
    """
    file_path = Path(path)
    file_path_str = str(file_path)

    if file_path.suffix != ".md":
        raise InvalidSkillFrontmatterError(
            f"Skill file must have a .md extension; got {file_path.suffix!r}.",
            file_path=file_path_str,
            fix_suggestion="Rename the file so it ends in `.md`.",
        )

    try:
        text = file_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise InvalidSkillFrontmatterError(
            f"Skill file not found: {file_path_str}.",
            file_path=file_path_str,
            fix_suggestion="Check the path; ensure the file exists and is readable.",
        ) from exc
    except OSError as exc:
        raise InvalidSkillFrontmatterError(
            f"Skill file could not be read: {exc}.",
            file_path=file_path_str,
            fix_suggestion="Check the file's permissions + encoding (expected UTF-8).",
        ) from exc

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise InvalidSkillFrontmatterError(
            "Skill file missing leading `---` YAML frontmatter delimiter.",
            file_path=file_path_str,
            line_number=1,
            fix_suggestion="Add `---` as the first line, followed by YAML, then a closing `---`.",
        )

    end_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise InvalidSkillFrontmatterError(
            "Skill file missing closing `---` YAML frontmatter delimiter.",
            file_path=file_path_str,
            line_number=len(lines),
            fix_suggestion="Add a closing `---` line after the YAML block.",
        )

    yaml_block = "\n".join(lines[1:end_index])

    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        # PyYAML attaches a `problem_mark` to many error subclasses; convert
        # the 0-indexed mark line to 1-indexed + offset into the file (add 1
        # because line 1 is the opening `---`).
        mark = getattr(exc, "problem_mark", None)
        mark_line: int | None = None
        if mark is not None and hasattr(mark, "line"):
            mark_line = int(mark.line) + 1 + 1
        raise InvalidSkillFrontmatterError(
            f"YAML frontmatter failed to parse: {exc}.",
            file_path=file_path_str,
            line_number=mark_line,
            fix_suggestion=(
                "Check YAML indentation + quoting; run a YAML linter on the block between the `---` delimiters."
            ),
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidSkillFrontmatterError(
            f"YAML frontmatter must be a mapping; got {type(parsed).__name__}.",
            file_path=file_path_str,
            line_number=2,
            fix_suggestion="Use `key: value` pairs inside the `---` delimiters.",
        )

    return parsed


def validate_frontmatter_structure(
    frontmatter: dict[str, Any],
    *,
    file_path: str | None = None,
) -> None:
    """Validate a parsed frontmatter dict has the 4 required fields + correct types.

    Args:
        frontmatter: The dict returned by `parse_frontmatter()`.
        file_path: Optional source path for diagnostics (echoed back in
            the raised error's `file_path` attr; pure metadata).

    Raises:
        InvalidSkillFrontmatterError: If any required field is missing
            OR if a field's value violates its type contract.
    """
    missing = [field for field in REQUIRED_FIELDS if field not in frontmatter]
    if missing:
        raise InvalidSkillFrontmatterError(
            f"Skill frontmatter missing required field(s): {missing!r}.",
            file_path=file_path,
            field_name=",".join(missing),
            fix_suggestion=(f"Add the missing field(s) to the YAML block. Required fields: {list(REQUIRED_FIELDS)!r}."),
        )

    name = frontmatter["name"]
    if not isinstance(name, str) or not name:
        raise InvalidSkillFrontmatterError(
            f"`name` must be a non-empty string; got {type(name).__name__}.",
            file_path=file_path,
            field_name="name",
            fix_suggestion="Set `name: <non-empty string>` in the YAML block.",
        )

    description = frontmatter["description"]
    if not isinstance(description, str) or not description:
        raise InvalidSkillFrontmatterError(
            f"`description` must be a non-empty string; got {type(description).__name__}.",
            file_path=file_path,
            field_name="description",
            fix_suggestion="Set `description: <non-empty string>` in the YAML block.",
        )

    allowed_tools = frontmatter["allowed-tools"]
    if not isinstance(allowed_tools, list) or any(not isinstance(tool, str) for tool in allowed_tools):
        raise InvalidSkillFrontmatterError(
            f"`allowed-tools` must be a list of strings; got {type(allowed_tools).__name__}.",
            file_path=file_path,
            field_name="allowed-tools",
            fix_suggestion="Set `allowed-tools: [tool_a, tool_b]` as a YAML list of strings.",
        )

    disable_model_invocation = frontmatter["disable-model-invocation"]
    if not isinstance(disable_model_invocation, bool):
        raise InvalidSkillFrontmatterError(
            f"`disable-model-invocation` must be a bool; got {type(disable_model_invocation).__name__}.",
            file_path=file_path,
            field_name="disable-model-invocation",
            fix_suggestion="Set `disable-model-invocation: true` or `disable-model-invocation: false`.",
        )
