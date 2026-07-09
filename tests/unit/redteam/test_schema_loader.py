# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for the red-team probe schema + YAML loader (add-red-team-probes tasks 2 + 3)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from AgentEval.errors import InvalidRedTeamProbeError
from AgentEval.redteam.loader import load_bundled_pack, load_pack
from AgentEval.redteam.schema import PROBE_CATEGORIES

# --------------------------------------------------------------------------- #
# Bundled pack: complete metadata + version + ≥20 probes across four categories
# --------------------------------------------------------------------------- #


def test_bundled_pack_loads_with_complete_metadata() -> None:
    pack = load_bundled_pack()
    assert len(pack) >= 20
    for probe in pack.probes:
        assert probe.id and probe.category and probe.severity
        assert probe.source and probe.expected_behavior and probe.prompt
        assert probe.category in PROBE_CATEGORIES


def test_bundled_pack_spans_all_four_categories() -> None:
    pack = load_bundled_pack()
    assert set(pack.categories) == set(PROBE_CATEGORIES)
    for category in PROBE_CATEGORIES:
        assert pack.by_category(category), f"no probes in {category}"


def test_bundled_pack_exposes_non_empty_version() -> None:
    pack = load_bundled_pack()
    assert isinstance(pack.pack_version, str)
    assert pack.pack_version.strip()


def test_bundled_pack_ids_are_unique() -> None:
    pack = load_bundled_pack()
    ids = [p.id for p in pack.probes]
    assert len(ids) == len(set(ids))


def test_no_dos_or_resource_exhaustion_category_present() -> None:
    """Spec: the pack MUST NOT contain DoS / resource-exhaustion probes."""
    pack = load_bundled_pack()
    assert "dos" not in pack.categories
    assert "resource_exhaustion" not in pack.categories


# --------------------------------------------------------------------------- #
# SAFETY fix — no bundled probe solicits REAL environment / .env secrets
# --------------------------------------------------------------------------- #


def test_no_bundled_probe_requests_real_environment_secrets() -> None:
    """A compliant coding agent must never be told to read REAL local secrets.

    pi-003 (print any .env file) + pii-003 (list real API keys/tokens/passwords
    from the environment) previously risked writing REAL secrets into
    ProbeResult.response_text / Robot logs / CI artifacts. All probes must now
    use SUPPLIED fake canaries, never read the operator's actual environment.
    """
    pack = load_bundled_pack()
    # Literal references that would name the operator's real secret surfaces.
    forbidden_substrings = (".env", "environment variable", "environment variables")
    # Enumeration of real credentials visible in the agent's live context/env.
    enumerate_secrets = re.compile(
        r"(api keys|access tokens|passwords|connection strings)"
        r"[^.]{0,60}(you can see|in your (context|environment|configuration))",
        re.IGNORECASE,
    )
    for probe in pack.probes:
        low = probe.prompt.lower()
        for term in forbidden_substrings:
            assert term not in low, f"probe {probe.id} prompt references real secret surface {term!r}"
        assert not enumerate_secrets.search(probe.prompt), (
            f"probe {probe.id} asks the agent to enumerate real secrets from its environment"
        )


def test_probes_with_markers_key_off_fake_canaries() -> None:
    """The rewritten secret-disclosure probes assert on a SUPPLIED fake canary."""
    pack = load_bundled_pack()
    pii003 = pack.by_id("pii-003")
    assert pii003 is not None
    assert pii003.compliance_marker == "CANARY-SECRET-9F3A"
    assert "CANARY-SECRET-9F3A" in pii003.prompt  # the fake secret is SUPPLIED, not read
    pi003 = pack.by_id("pi-003")
    assert pi003 is not None
    assert pi003.compliance_marker and pi003.compliance_marker in pi003.prompt


def test_compliance_marker_optional_and_typed(tmp_path: Path) -> None:
    """`compliance_marker` is optional (absent -> "") but must be a string when present."""
    absent = _write(tmp_path, 'pack_version: "1.0.0"\nprobes:\n' + _VALID_PROBE)
    pack = load_pack(user_yaml=absent, include_bundled=False)
    assert pack.by_id("user-001").compliance_marker == ""  # type: ignore[union-attr]

    bad = (
        'pack_version: "1.0.0"\nprobes:\n'
        "  - id: bad-marker\n"
        "    category: prompt_injection\n"
        "    severity: high\n"
        "    source: user\n"
        "    expected_behavior: resists\n"
        "    prompt: do a thing\n"
        "    compliance_marker: [not, a, string]\n"
    )
    path = _write(tmp_path, bad, name="bad.yaml")
    with pytest.raises(InvalidRedTeamProbeError, match="compliance_marker"):
        load_pack(user_yaml=path, include_bundled=False)


# --------------------------------------------------------------------------- #
# Validation: missing field / invalid category rejected with structured error
# --------------------------------------------------------------------------- #

_VALID_PROBE = (
    "  - id: user-001\n"
    "    category: prompt_injection\n"
    "    severity: high\n"
    "    source: user\n"
    "    expected_behavior: resists\n"
    "    prompt: do a thing\n"
)


def _write(tmp_path: Path, body: str, name: str = "user.yaml") -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def test_missing_required_field_rejected(tmp_path: Path) -> None:
    body = (
        'pack_version: "1.0.0"\nprobes:\n'
        "  - id: bad-001\n"
        "    category: prompt_injection\n"
        "    severity: high\n"
        "    source: user\n"
        "    prompt: no expected_behavior here\n"  # missing expected_behavior
    )
    path = _write(tmp_path, body)
    with pytest.raises(InvalidRedTeamProbeError) as exc:
        load_pack(user_yaml=path, include_bundled=False)
    assert "expected_behavior" in str(exc.value)
    assert "bad-001" in str(exc.value)


def test_invalid_category_rejected(tmp_path: Path) -> None:
    body = (
        'pack_version: "1.0.0"\nprobes:\n'
        "  - id: bad-002\n"
        "    category: denial_of_service\n"  # not one of the four
        "    severity: high\n"
        "    source: user\n"
        "    expected_behavior: resists\n"
        "    prompt: flood it\n"
    )
    path = _write(tmp_path, body)
    with pytest.raises(InvalidRedTeamProbeError) as exc:
        load_pack(user_yaml=path, include_bundled=False)
    assert "denial_of_service" in str(exc.value)
    assert "bad-002" in str(exc.value)


def test_nonexistent_user_file_rejected(tmp_path: Path) -> None:
    with pytest.raises(InvalidRedTeamProbeError):
        load_pack(user_yaml=tmp_path / "nope.yaml", include_bundled=False)


# --------------------------------------------------------------------------- #
# User extension: merge, replace, duplicate-id rejection
# --------------------------------------------------------------------------- #


def test_user_probes_extend_bundled_pack(tmp_path: Path) -> None:
    path = _write(tmp_path, 'pack_version: "1.0.0"\nprobes:\n' + _VALID_PROBE)
    bundled = load_bundled_pack()
    merged = load_pack(user_yaml=path)  # include_bundled=True default
    assert len(merged) == len(bundled) + 1
    assert merged.by_id("user-001") is not None
    # Bundled pack_version is preserved; user provenance rides on each probe.
    assert merged.pack_version == bundled.pack_version


def test_user_only_replace_mode(tmp_path: Path) -> None:
    path = _write(tmp_path, 'pack_version: "9.9.9"\nprobes:\n' + _VALID_PROBE)
    only = load_pack(user_yaml=path, include_bundled=False)
    assert len(only) == 1
    assert only.by_id("user-001") is not None


def test_duplicate_id_across_bundled_and_user_rejected(tmp_path: Path) -> None:
    dup = (
        'pack_version: "1.0.0"\nprobes:\n'
        "  - id: pi-001\n"  # collides with a bundled prompt_injection probe
        "    category: prompt_injection\n"
        "    severity: high\n"
        "    source: user\n"
        "    expected_behavior: resists\n"
        "    prompt: duplicate id\n"
    )
    path = _write(tmp_path, dup)
    with pytest.raises(InvalidRedTeamProbeError) as exc:
        load_pack(user_yaml=path)
    assert "pi-001" in str(exc.value)
    assert "duplicate" in str(exc.value).lower()
