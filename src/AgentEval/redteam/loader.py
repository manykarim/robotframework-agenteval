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

"""Probe-pack YAML loader (add-red-team-probes / design D1 + tasks §2).

Loads the bundled probe corpus from ``redteam/probes/*.yaml`` (one file per
category, per the resolved Open Question) through a typed schema, and merges in
user-supplied YAML without forking. Every probe — bundled or user — is
validated against the same schema; structural failures raise
``InvalidRedTeamProbeError`` naming the offending probe + field in the
project's File/Line/Field/Fix style.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from AgentEval.errors import InvalidRedTeamProbeError
from AgentEval.redteam.schema import PROBE_CATEGORIES, Probe, ProbePack

__all__ = ["BUNDLED_PROBES_DIR", "load_bundled_pack", "load_pack"]

BUNDLED_PROBES_DIR = Path(__file__).resolve().parent / "probes"

# Required per-probe fields (the five metadata fields + the attack payload).
_REQUIRED_FIELDS = ("id", "category", "severity", "source", "expected_behavior", "prompt")


def _load_yaml_file(path: Path) -> dict[str, Any]:
    """Read + parse one probe YAML file, returning the top-level mapping."""
    if not path.exists():
        raise InvalidRedTeamProbeError(
            f"probe pack file not found: {path}",
            file_path=str(path),
            field_name="",
            fix_suggestion="Verify the path exists and is readable.",
        )
    if path.suffix.lower() not in (".yaml", ".yml"):
        raise InvalidRedTeamProbeError(
            f"probe pack file must have a .yaml or .yml extension; got {path.suffix!r}",
            file_path=str(path),
            field_name="",
            fix_suggestion="Rename the file to use a .yaml or .yml extension.",
        )
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidRedTeamProbeError(
            f"failed to read probe pack file: {exc}",
            file_path=str(path),
            field_name="",
            fix_suggestion="Verify the file is readable + UTF-8 encoded.",
        ) from exc
    except UnicodeDecodeError as exc:
        raise InvalidRedTeamProbeError(
            f"probe pack file is not valid UTF-8: {exc}",
            file_path=str(path),
            field_name="",
            fix_suggestion="Re-save the file as UTF-8 (no BOM).",
        ) from exc
    try:
        parsed: Any = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        line = getattr(getattr(exc, "problem_mark", None), "line", None)
        raise InvalidRedTeamProbeError(
            f"malformed probe YAML: {exc}",
            file_path=str(path),
            line_number=line + 1 if line is not None else None,
            field_name="",
            fix_suggestion="Validate the YAML with `python -c 'import yaml; yaml.safe_load(open(...))'`.",
        ) from exc
    if not isinstance(parsed, dict):
        raise InvalidRedTeamProbeError(
            f"probe YAML top-level must be a mapping with `pack_version` + `probes`; got {type(parsed).__name__}",
            file_path=str(path),
            field_name="",
            fix_suggestion="Wrap the content in a top-level mapping with `pack_version:` and `probes:` keys.",
        )
    return parsed


def _parse_probe(entry: Any, *, idx: int, file_path: str) -> Probe:
    """Validate one probe mapping and construct a ``Probe``."""
    if not isinstance(entry, dict):
        raise InvalidRedTeamProbeError(
            f"probe #{idx} must be a mapping; got {type(entry).__name__}",
            file_path=file_path,
            field_name=f"probes[{idx}]",
            fix_suggestion=(
                "Format each probe as a YAML mapping with id/category/severity/source/expected_behavior/prompt."
            ),
        )
    for required in _REQUIRED_FIELDS:
        if required not in entry or entry[required] is None:
            probe_ref = entry.get("id") if isinstance(entry.get("id"), str) else f"#{idx}"
            raise InvalidRedTeamProbeError(
                f"probe {probe_ref} is missing required field {required!r}",
                file_path=file_path,
                field_name=f"{probe_ref}.{required}",
                fix_suggestion=f"Add a non-empty `{required}:` field to the probe.",
            )
        if not isinstance(entry[required], str) or not entry[required].strip():
            probe_ref = entry.get("id") if isinstance(entry.get("id"), str) else f"#{idx}"
            raise InvalidRedTeamProbeError(
                f"probe {probe_ref} field {required!r} must be a non-empty string; got {entry[required]!r}",
                file_path=file_path,
                field_name=f"{probe_ref}.{required}",
                fix_suggestion=f"Provide a non-empty string value for `{required}`.",
            )
    # `compliance_marker` is OPTIONAL (attack-success canary). When present it
    # MUST be a string; empty/absent means "no positive marker" and the probe
    # falls back to refusal-language / judge detection alone.
    compliance_marker = entry.get("compliance_marker", "")
    if compliance_marker is None:
        compliance_marker = ""
    if not isinstance(compliance_marker, str):
        probe_ref = entry.get("id") if isinstance(entry.get("id"), str) else f"#{idx}"
        raise InvalidRedTeamProbeError(
            f"probe {probe_ref} field 'compliance_marker' must be a string; got {compliance_marker!r}",
            file_path=file_path,
            field_name=f"{probe_ref}.compliance_marker",
            fix_suggestion="Provide a string regex/literal marker (or omit the field for no positive marker).",
        )
    category = entry["category"]
    if category not in PROBE_CATEGORIES:
        raise InvalidRedTeamProbeError(
            f"probe {entry['id']!r} declares category {category!r} outside the four allowed categories "
            f"{sorted(PROBE_CATEGORIES)}",
            file_path=file_path,
            field_name=f"{entry['id']}.category",
            fix_suggestion=(
                "Use one of prompt_injection / jailbreak / pii_leakage / encoding_obfuscation. "
                "DoS / resource-exhaustion probes are out of mission and not permitted."
            ),
        )
    return Probe(
        id=entry["id"],
        category=category,
        severity=entry["severity"],
        source=entry["source"],
        expected_behavior=entry["expected_behavior"],
        prompt=entry["prompt"],
        compliance_marker=compliance_marker,
    )


def _parse_pack_file(path: Path) -> tuple[list[Probe], str | None]:
    """Parse one probe YAML file into (probes, pack_version)."""
    doc = _load_yaml_file(path)
    pack_version = doc.get("pack_version")
    if pack_version is not None and (not isinstance(pack_version, str) or not pack_version.strip()):
        raise InvalidRedTeamProbeError(
            f"`pack_version` must be a non-empty string; got {pack_version!r}",
            file_path=str(path),
            field_name="pack_version",
            fix_suggestion="Set `pack_version:` to a non-empty version string (e.g. '1.0.0').",
        )
    probes_raw = doc.get("probes")
    if not isinstance(probes_raw, list) or not probes_raw:
        raise InvalidRedTeamProbeError(
            "probe YAML `probes` must be a non-empty list",
            file_path=str(path),
            field_name="probes",
            fix_suggestion="Add a `probes:` list with at least one probe entry.",
        )
    probes = [_parse_probe(entry, idx=idx, file_path=str(path)) for idx, entry in enumerate(probes_raw)]
    return probes, (pack_version if isinstance(pack_version, str) else None)


def _dedupe_and_pack(
    probe_groups: list[tuple[list[Probe], str | None, str]],
    *,
    default_version: str,
) -> ProbePack:
    """Merge probe groups, enforcing unique ids + a single pack_version.

    ``probe_groups`` is a list of ``(probes, declared_version, origin_label)``.
    Duplicate ids across ANY group raise (silent override would corrupt ASR
    accounting). The pack_version is the first non-None declared version; a
    conflicting declared version raises.
    """
    seen: dict[str, str] = {}  # probe_id -> origin_label
    merged: list[Probe] = []
    resolved_version: str | None = None
    resolved_origin: str = ""
    for probes, declared_version, origin in probe_groups:
        if declared_version is not None:
            if resolved_version is None:
                resolved_version, resolved_origin = declared_version, origin
            elif declared_version != resolved_version:
                raise InvalidRedTeamProbeError(
                    f"conflicting pack_version: {resolved_origin} declares {resolved_version!r} but "
                    f"{origin} declares {declared_version!r}",
                    file_path=origin,
                    field_name="pack_version",
                    fix_suggestion="Make every bundled probe file agree on a single `pack_version`.",
                )
        for probe in probes:
            if probe.id in seen:
                raise InvalidRedTeamProbeError(
                    f"duplicate probe id {probe.id!r}: declared in both {seen[probe.id]} and {origin}",
                    file_path=origin,
                    field_name=f"{probe.id}.id",
                    fix_suggestion=(
                        "Probe ids MUST be unique across the bundled pack + any user-supplied files. "
                        "Rename the duplicate id in your user YAML."
                    ),
                )
            seen[probe.id] = origin
            merged.append(probe)
    return ProbePack(probes=tuple(merged), pack_version=resolved_version or default_version)


def load_bundled_pack() -> ProbePack:
    """Load the curated probe pack shipped with the library.

    Reads every ``*.yaml`` file under ``redteam/probes/`` (one per category),
    validates each probe, and returns a single ``ProbePack``. The bundled files
    all declare the same ``pack_version``; a mismatch raises.

    Raises:
        InvalidRedTeamProbeError: on any parse / schema / duplicate-id failure.
    """
    files = sorted(BUNDLED_PROBES_DIR.glob("*.yaml"))
    if not files:
        raise InvalidRedTeamProbeError(
            f"no bundled probe files found under {BUNDLED_PROBES_DIR}",
            file_path=str(BUNDLED_PROBES_DIR),
            field_name="",
            fix_suggestion="The library install is incomplete; reinstall robotframework-agenteval.",
        )
    groups: list[tuple[list[Probe], str | None, str]] = []
    for f in files:
        probes, version = _parse_pack_file(f)
        groups.append((probes, version, str(f)))
    return _dedupe_and_pack(groups, default_version="0.0.0")


def load_pack(
    user_yaml: str | Path | list[str | Path] | None = None,
    *,
    include_bundled: bool = True,
) -> ProbePack:
    """Load a probe pack, optionally extending / replacing with user YAML.

    Args:
        user_yaml: path(s) to user-supplied probe YAML file(s) conforming to the
            same schema. ``None`` loads only the bundled pack.
        include_bundled: when ``True`` (default), user probes EXTEND the bundled
            pack; when ``False``, ONLY the user files are loaded (replace mode).

    Every user probe is validated against the same schema as bundled probes. A
    user probe reusing a bundled id raises ``InvalidRedTeamProbeError`` rather
    than silently overriding.

    Raises:
        InvalidRedTeamProbeError: on any parse / schema / duplicate-id failure,
            or when ``include_bundled=False`` and no user files are given.
    """
    groups: list[tuple[list[Probe], str | None, str]] = []
    if include_bundled:
        bundled = load_bundled_pack()
        groups.append((list(bundled.probes), bundled.pack_version, "<bundled>"))

    if user_yaml is not None:
        paths = user_yaml if isinstance(user_yaml, list) else [user_yaml]
        for raw_path in paths:
            path = Path(raw_path)
            probes, _version = _parse_pack_file(path)
            # User packs do NOT get to override the bundled pack_version; their
            # provenance is recorded per-probe via `source`.
            groups.append((probes, None, str(path)))

    if not groups:
        raise InvalidRedTeamProbeError(
            "load_pack(include_bundled=False) requires at least one user YAML file",
            file_path="",
            field_name="",
            fix_suggestion="Pass `user_yaml=<path>` or keep `include_bundled=True`.",
        )
    return _dedupe_and_pack(groups, default_version="0.0.0")
