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

"""Subagent ``.md`` frontmatter parser.

Reads the YAML block between leading ``---`` delimiters and validates the
required ``name`` + ``description`` fields plus the optional ``tools`` /
``model`` / ``skills`` shapes. Structural failures raise ``InvalidConfigError``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from AgentEval._core import InvalidConfigError

__all__ = [
    "REQUIRED_FIELDS",
    "parse_subagent_frontmatter",
    "validate_subagent_structure",
]

# `name` + `description` are required; `tools` / `model` / `skills` are optional.
REQUIRED_FIELDS: tuple[str, ...] = ("name", "description")


def parse_subagent_frontmatter(path: str | Path) -> dict[str, Any]:
    """Parse the YAML frontmatter at the head of a subagent ``.md`` file.

    Raises ``InvalidConfigError`` on any file- or YAML-level structural failure.
    """
    file_path = Path(path)
    file_path_str = str(file_path)

    if file_path.suffix != ".md":
        raise InvalidConfigError(
            f"Subagent file must have a .md extension; got {file_path.suffix!r}.",
            file_path=file_path_str,
            fix="Rename the file so it ends in `.md`.",
        )

    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise InvalidConfigError(
            f"Subagent file not found: {file_path_str}.",
            file_path=file_path_str,
            fix="Check the path; ensure the file exists and is readable.",
        ) from exc
    except OSError as exc:
        raise InvalidConfigError(
            f"Subagent file could not be read: {exc}.",
            file_path=file_path_str,
            fix="Check the file's permissions + encoding (expected UTF-8).",
        ) from exc

    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        raise InvalidConfigError(
            "Subagent file missing leading `---` YAML frontmatter delimiter at column 0 (line 1).",
            file_path=file_path_str,
            fix="Add `---` as the first line (column 0), followed by YAML, then a closing `---`.",
        )

    end_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            end_index = index
            break
    if end_index is None:
        raise InvalidConfigError(
            "Subagent file missing closing `---` YAML frontmatter delimiter at column 0.",
            file_path=file_path_str,
            fix="Add a closing `---` line (column 0) after the YAML block.",
        )

    yaml_block = "\n".join(lines[1:end_index])

    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        problem = getattr(exc, "problem", None)
        yaml_summary = str(problem) if problem else (str(exc).splitlines()[0] if str(exc) else "YAML parse error")
        raise InvalidConfigError(
            f"YAML frontmatter failed to parse: {yaml_summary}.",
            file_path=file_path_str,
            fix="Check YAML indentation + quoting; run a YAML linter on the block between the `---` delimiters.",
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidConfigError(
            f"YAML frontmatter must be a mapping; got {type(parsed).__name__}.",
            file_path=file_path_str,
            fix="Use `key: value` pairs inside the `---` delimiters.",
        )

    return parsed


def validate_subagent_structure(
    frontmatter: dict[str, Any],
    *,
    file_path: str | None = None,
) -> None:
    """Validate a parsed subagent frontmatter dict.

    Required: ``name`` (non-empty str), ``description`` (non-empty str).
    Optional but type-checked when present: ``tools`` (list[str]), ``model``
    (str), ``skills`` (list of non-empty str). Raises ``InvalidConfigError``.
    """
    missing = [field_name for field_name in REQUIRED_FIELDS if field_name not in frontmatter]
    if missing:
        raise InvalidConfigError(
            f"Subagent frontmatter missing required field(s): {missing!r}.",
            file_path=file_path,
            field=",".join(missing),
            fix=f"Add the missing field(s). Required: {list(REQUIRED_FIELDS)!r}.",
        )

    name = frontmatter["name"]
    if not isinstance(name, str) or not name:
        raise InvalidConfigError(
            f"`name` must be a non-empty string; got {type(name).__name__}.",
            file_path=file_path,
            field="name",
            fix="Set `name: <non-empty string>` in the YAML block.",
        )

    description = frontmatter["description"]
    if not isinstance(description, str) or not description:
        raise InvalidConfigError(
            f"`description` must be a non-empty string; got {type(description).__name__}.",
            file_path=file_path,
            field="description",
            fix="Set `description: <non-empty string>` in the YAML block.",
        )

    if "tools" in frontmatter:
        tools = frontmatter["tools"]
        if not isinstance(tools, list) or any(not isinstance(tool, str) for tool in tools):
            raise InvalidConfigError(
                f"`tools` (optional) must be a list of strings; got {type(tools).__name__}.",
                file_path=file_path,
                field="tools",
                fix="Set `tools: [tool_a, tool_b]` as a YAML list of strings, or omit the field.",
            )

    if "model" in frontmatter:
        model = frontmatter["model"]
        if not isinstance(model, str) or not model:
            raise InvalidConfigError(
                f"`model` (optional) must be a non-empty string; got {type(model).__name__}.",
                file_path=file_path,
                field="model",
                fix="Set `model: <model-identifier>` or omit the field for the default.",
            )

    if "skills" in frontmatter:
        skills = frontmatter["skills"]
        if not isinstance(skills, list) or any(not isinstance(s, str) or not s for s in skills):
            raise InvalidConfigError(
                f"`skills` (optional) must be a list of non-empty strings; got {type(skills).__name__}.",
                file_path=file_path,
                field="skills",
                fix="Set `skills: [skill_a, skill_b]` as a YAML list of non-empty strings, or omit it.",
            )
