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

"""Read and validate the YAML frontmatter at the head of a skill ``.md`` file.

The frontmatter is the YAML block between the leading and trailing ``---``
delimiters. A skill declares two required fields - ``name`` and ``description``
- matching the Agent Skills spec. ``allowed-tools`` and
``disable-model-invocation`` are optional; they are type-checked only when
present. Anything malformed raises ``InvalidConfigError`` with the offending
field and a fix suggestion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from AgentEval._core import InvalidConfigError

__all__ = [
    "REQUIRED_FIELDS",
    "parse_frontmatter",
    "validate_frontmatter_structure",
]


# Per the Agent Skills spec only `name` + `description` are required. Real
# published skills routinely omit `allowed-tools` / `disable-model-invocation`,
# so those stay optional (type-checked when present, defaulted when absent).
REQUIRED_FIELDS: tuple[str, ...] = (
    "name",
    "description",
)


def parse_frontmatter(path: str | Path) -> dict[str, Any]:
    """Parse the YAML frontmatter block into a dict.

    Raises ``InvalidConfigError`` on any structural failure: wrong extension,
    missing file, missing delimiters, broken YAML, or frontmatter that is not a
    mapping.
    """
    file_path = Path(path)
    file_path_str = str(file_path)

    if file_path.suffix != ".md":
        raise InvalidConfigError(
            f"Skill file must have a .md extension; got {file_path.suffix!r}.",
            file_path=file_path_str,
            fix="Rename the file so it ends in `.md`.",
        )

    try:
        # utf-8-sig strips a UTF-8 BOM (common on Windows-authored files) so the
        # first line is a clean `---` rather than a BOM-prefixed delimiter.
        text = file_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise InvalidConfigError(
            f"Skill file not found: {file_path_str}.",
            file_path=file_path_str,
            fix="Check the path; ensure the file exists and is readable.",
        ) from exc
    except OSError as exc:
        raise InvalidConfigError(
            f"Skill file could not be read: {exc}.",
            file_path=file_path_str,
            fix="Check the file's permissions + encoding (expected UTF-8).",
        ) from exc

    lines = text.splitlines()
    # rstrip (not strip) so an indented `---` inside a YAML block scalar does not
    # masquerade as the delimiter.
    if not lines or lines[0].rstrip() != "---":
        raise InvalidConfigError(
            "Skill file missing leading `---` YAML frontmatter delimiter at column 0.",
            file_path=file_path_str,
            fix="Add `---` as the first line, followed by YAML, then a closing `---`.",
        )

    end_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            end_index = index
            break
    if end_index is None:
        raise InvalidConfigError(
            "Skill file missing closing `---` YAML frontmatter delimiter at column 0.",
            file_path=file_path_str,
            fix="Add a closing `---` line after the YAML block.",
        )

    yaml_block = "\n".join(lines[1:end_index])

    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        problem = getattr(exc, "problem", None)
        summary = str(problem) if problem else (str(exc).splitlines()[0] if str(exc) else "YAML parse error")
        raise InvalidConfigError(
            f"YAML frontmatter failed to parse: {summary}.",
            file_path=file_path_str,
            fix="Check YAML indentation + quoting between the `---` delimiters.",
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidConfigError(
            f"YAML frontmatter must be a mapping; got {type(parsed).__name__}.",
            file_path=file_path_str,
            fix="Use `key: value` pairs inside the `---` delimiters.",
        )

    return parsed


def validate_frontmatter_structure(
    frontmatter: dict[str, Any],
    *,
    file_path: str | None = None,
) -> None:
    """Assert the required fields are present and any optional fields are typed.

    Required: ``name`` + ``description`` (both non-empty strings). Optional but
    type-checked when present: ``allowed-tools`` (list of strings),
    ``disable-model-invocation`` (bool). Raises ``InvalidConfigError`` naming the
    missing or mistyped field.
    """
    missing = [field_name for field_name in REQUIRED_FIELDS if field_name not in frontmatter]
    if missing:
        raise InvalidConfigError(
            f"Skill frontmatter missing required field(s): {missing!r}.",
            file_path=file_path,
            field=",".join(missing),
            fix=f"Add the missing field(s). Required fields: {list(REQUIRED_FIELDS)!r}.",
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

    if "allowed-tools" in frontmatter:
        allowed_tools = frontmatter["allowed-tools"]
        if not isinstance(allowed_tools, list) or any(not isinstance(tool, str) for tool in allowed_tools):
            raise InvalidConfigError(
                f"`allowed-tools` (optional) must be a list of strings; got {type(allowed_tools).__name__}.",
                file_path=file_path,
                field="allowed-tools",
                fix="Set `allowed-tools: [tool_a, tool_b]` as a YAML list of strings, or omit the field.",
            )

    if "disable-model-invocation" in frontmatter:
        disable_model_invocation = frontmatter["disable-model-invocation"]
        if not isinstance(disable_model_invocation, bool):
            raise InvalidConfigError(
                f"`disable-model-invocation` (optional) must be a bool; got {type(disable_model_invocation).__name__}.",
                file_path=file_path,
                field="disable-model-invocation",
                fix="Set `disable-model-invocation: true`/`false`, or omit the field.",
            )
