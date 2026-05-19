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

"""Scenario YAML loader (Story 4.3 / PRD FR15).

Reads a YAML file from disk, parses + validates against the
`Scenario` schema, returns the dataclass on success or raises
`InvalidScenarioYAMLError` with an RFC 6901 JSON Pointer in
`field_name` on any structural failure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from AgentEval.errors import InvalidScenarioYAMLError
from AgentEval.scenarios.schema import Scenario, ScenarioEval

__all__ = ["load_scenario"]


def load_scenario(path: str | Path) -> Scenario:
    """Load + validate a scenario YAML file.

    Args:
        path: Filesystem path to the scenario YAML.

    Returns:
        Parsed `Scenario` dataclass.

    Raises:
        InvalidScenarioYAMLError: on any structural failure (file
            missing, wrong extension, malformed YAML, schema violation).
            The `field_name` attribute carries an RFC 6901 JSON Pointer
            into the offending location.
    """
    p = Path(path)
    if not p.exists():
        raise InvalidScenarioYAMLError(
            f"scenario YAML file not found: {p}",
            file_path=str(p),
            field_name="/",
            fix_suggestion="Verify the path exists and is readable.",
        )
    if p.suffix.lower() not in (".yaml", ".yml"):
        raise InvalidScenarioYAMLError(
            f"scenario file must have .yaml or .yml extension; got {p.suffix!r}",
            file_path=str(p),
            field_name="/",
            fix_suggestion="Rename the file to use .yaml or .yml extension.",
        )

    try:
        raw_text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidScenarioYAMLError(
            f"failed to read scenario YAML: {exc}",
            file_path=str(p),
            field_name="/",
            fix_suggestion="Verify the file is readable + UTF-8 encoded.",
        ) from exc

    try:
        parsed: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        # Best-effort line extraction from PyYAML's MarkedYAMLError.
        line = getattr(getattr(exc, "problem_mark", None), "line", None)
        raise InvalidScenarioYAMLError(
            f"malformed YAML: {exc}",
            file_path=str(p),
            line_number=line + 1 if line is not None else None,
            field_name="/",
            fix_suggestion="Validate the YAML with `python -c 'import yaml; yaml.safe_load(open(...))'`.",
        ) from exc

    if not isinstance(parsed, dict):
        raise InvalidScenarioYAMLError(
            f"scenario YAML top-level must be a mapping; got {type(parsed).__name__}",
            file_path=str(p),
            field_name="/",
            fix_suggestion="Wrap the content in a top-level YAML mapping with `evals:` key.",
        )

    return _parse_scenario(parsed, file_path=str(p))


def _parse_scenario(doc: dict[str, Any], *, file_path: str) -> Scenario:
    """Validate the top-level scenario shape + descend into `evals[]`."""
    if "evals" not in doc:
        raise InvalidScenarioYAMLError(
            "scenario YAML missing required `evals` field",
            file_path=file_path,
            field_name="/evals",
            fix_suggestion="Add a top-level `evals:` list of scenario evaluations.",
        )
    evals_raw = doc["evals"]
    if not isinstance(evals_raw, list):
        raise InvalidScenarioYAMLError(
            f"`evals` must be a list; got {type(evals_raw).__name__}",
            file_path=file_path,
            field_name="/evals",
            fix_suggestion="Format as a YAML list of eval entries.",
        )
    if not evals_raw:
        raise InvalidScenarioYAMLError(
            "scenario YAML `evals` list is empty; at least one eval is required",
            file_path=file_path,
            field_name="/evals",
            fix_suggestion="Add at least one eval entry with a `prompt:` field.",
        )

    evals: list[ScenarioEval] = []
    for idx, entry in enumerate(evals_raw):
        evals.append(_parse_eval(entry, idx=idx, file_path=file_path))

    # Optional top-level fields.
    model = _validate_optional_str(doc.get("model"), field_name="/model", file_path=file_path)
    provider = _validate_optional_str(doc.get("provider"), field_name="/provider", file_path=file_path)
    agent = _validate_optional_str(doc.get("agent"), field_name="/agent", file_path=file_path)
    mcp_servers_raw = doc.get("mcp_servers") or []
    if not isinstance(mcp_servers_raw, list):
        raise InvalidScenarioYAMLError(
            f"`mcp_servers` must be a list of names; got {type(mcp_servers_raw).__name__}",
            file_path=file_path,
            field_name="/mcp_servers",
            fix_suggestion="Format as a YAML list of strings.",
        )
    for idx, name in enumerate(mcp_servers_raw):
        if not isinstance(name, str):
            raise InvalidScenarioYAMLError(
                f"`mcp_servers[{idx}]` must be a string; got {type(name).__name__}",
                file_path=file_path,
                field_name=f"/mcp_servers/{idx}",
                fix_suggestion="Use string MCP server names.",
            )

    return Scenario(
        evals=evals,
        model=model,
        provider=provider,
        agent=agent,
        mcp_servers=list(mcp_servers_raw),
    )


def _parse_eval(entry: Any, *, idx: int, file_path: str) -> ScenarioEval:
    """Validate one `evals[<idx>]` entry."""
    if not isinstance(entry, dict):
        raise InvalidScenarioYAMLError(
            f"`evals[{idx}]` must be a mapping; got {type(entry).__name__}",
            file_path=file_path,
            field_name=f"/evals/{idx}",
            fix_suggestion="Format each eval as a YAML mapping with `prompt:` field.",
        )
    if "prompt" not in entry:
        raise InvalidScenarioYAMLError(
            f"`evals[{idx}]` missing required `prompt` field",
            file_path=file_path,
            field_name=f"/evals/{idx}/prompt",
            fix_suggestion="Add a `prompt:` key with the prompt text.",
        )
    prompt = entry["prompt"]
    if not isinstance(prompt, str):
        raise InvalidScenarioYAMLError(
            f"`evals[{idx}].prompt` must be a string; got {type(prompt).__name__}",
            file_path=file_path,
            field_name=f"/evals/{idx}/prompt",
            fix_suggestion="Use a string prompt.",
        )
    repeat_raw = entry.get("repeat", 1)
    if not isinstance(repeat_raw, int) or isinstance(repeat_raw, bool):
        # `bool` is a subclass of `int` in Python; explicitly reject.
        raise InvalidScenarioYAMLError(
            f"`evals[{idx}].repeat` must be an int; got {type(repeat_raw).__name__}",
            file_path=file_path,
            field_name=f"/evals/{idx}/repeat",
            fix_suggestion="Use an integer value for repeat count.",
        )
    if repeat_raw < 1:
        raise InvalidScenarioYAMLError(
            f"`evals[{idx}].repeat` must be >= 1; got {repeat_raw}",
            file_path=file_path,
            field_name=f"/evals/{idx}/repeat",
            fix_suggestion="Use a positive integer for repeat count.",
        )
    expect = entry.get("expect") or {}
    if not isinstance(expect, dict):
        raise InvalidScenarioYAMLError(
            f"`evals[{idx}].expect` must be a mapping; got {type(expect).__name__}",
            file_path=file_path,
            field_name=f"/evals/{idx}/expect",
            fix_suggestion="Format `expect` as a YAML mapping of assertion thresholds.",
        )
    judge = entry.get("judge") or {}
    if not isinstance(judge, dict):
        raise InvalidScenarioYAMLError(
            f"`evals[{idx}].judge` must be a mapping; got {type(judge).__name__}",
            file_path=file_path,
            field_name=f"/evals/{idx}/judge",
            fix_suggestion="Format `judge` as a YAML mapping (Phase-2 LLM-judge config).",
        )
    return ScenarioEval(prompt=prompt, repeat=repeat_raw, expect=expect, judge=judge)


def _validate_optional_str(value: Any, *, field_name: str, file_path: str) -> str | None:
    """Validate an optional top-level string field."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidScenarioYAMLError(
            f"`{field_name}` must be a string; got {type(value).__name__}",
            file_path=file_path,
            field_name=field_name,
            fix_suggestion="Use a string value.",
        )
    return value
