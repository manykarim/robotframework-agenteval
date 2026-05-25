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

"""Unit tests for `agenteval init` scaffolding (Story 8b.1 AC-8b.1.8)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from AgentEval.cli import main

EXPECTED_FILES: tuple[str, ...] = (
    "tests/example_skill_validation.robot",
    "tests/example_mcp_runtime.robot",
    "tests/example_agent_run.robot",
    "tests/fixtures/example-skill.md",
    "tests/fixtures/.mcp.json",
    "tests/fixtures/scenario.yaml",
    "agenteval.yaml",
    "README.md",
)


def test_init_creates_all_scaffolded_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """AC-8b.1.8 #1: `agenteval init --output-dir <tmp>` creates all 8 listed files."""
    rc = main(["init", "--output-dir", str(tmp_path)])
    assert rc == 0
    for rel in EXPECTED_FILES:
        target = tmp_path / rel
        assert target.exists(), f"missing scaffolded file: {rel}"
        assert target.stat().st_size > 0, f"scaffolded file is empty: {rel}"


def test_scaffolded_files_parse_correctly(tmp_path: Path) -> None:
    """AC-8b.1.8 #2: scaffolded files parse per their respective formats."""
    main(["init", "--output-dir", str(tmp_path)])
    # YAML files parse.
    yaml.safe_load((tmp_path / "agenteval.yaml").read_text())
    yaml.safe_load((tmp_path / "tests/fixtures/scenario.yaml").read_text())
    # JSON file parses.
    json.loads((tmp_path / "tests/fixtures/.mcp.json").read_text())
    # Markdown/Robot files are non-empty text (no native parser).
    assert "*** Test Cases ***" in (tmp_path / "tests/example_skill_validation.robot").read_text()
    assert "name: example-search" in (tmp_path / "tests/fixtures/example-skill.md").read_text()


def test_init_refuses_overwrite_without_force(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """AC-8b.1.8 #3: re-run without `--force` does NOT overwrite existing files."""
    main(["init", "--output-dir", str(tmp_path)])
    # Modify a scaffolded file in place.
    sentinel = "SENTINEL_DO_NOT_OVERWRITE"
    target = tmp_path / "README.md"
    target.write_text(sentinel)
    # Re-run without --force.
    rc = main(["init", "--output-dir", str(tmp_path)])
    assert rc == 0
    # Sentinel preserved.
    assert target.read_text() == sentinel
    # Stderr contains the skip warning.
    captured = capsys.readouterr()
    assert "README.md already exists" in captured.err


def test_init_force_overwrites(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """AC-8b.1.8 #4: re-run WITH `--force` overwrites + writes a notice."""
    main(["init", "--output-dir", str(tmp_path)])
    sentinel = "SENTINEL_TO_BE_OVERWRITTEN"
    target = tmp_path / "README.md"
    target.write_text(sentinel)
    rc = main(["init", "--output-dir", str(tmp_path), "--force"])
    assert rc == 0
    # Sentinel replaced with scaffold content.
    assert sentinel not in target.read_text()
    assert "robotframework-agenteval" in target.read_text()
    captured = capsys.readouterr()
    assert "overwrote README.md" in captured.err


def test_init_exit_code_zero_on_success(tmp_path: Path) -> None:
    """AC-8b.1.8 #5: exit code is 0 on success."""
    rc = main(["init", "--output-dir", str(tmp_path)])
    assert rc == 0


def test_stdout_summary_contains_canonical_invocation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """AC-8b.1.8 #6: stdout summary contains the explicit class-path invocation."""
    main(["init", "--output-dir", str(tmp_path)])
    captured = capsys.readouterr()
    assert "AgentEval.telemetry.listener.Listener" in captured.out, (
        f"stdout summary missing explicit class-path listener invocation: {captured.out!r}"
    )


def test_scaffolded_yaml_pins_explicit_listener_class_path(tmp_path: Path) -> None:
    """Bonus: agenteval.yaml comments include the explicit class-path invocation."""
    main(["init", "--output-dir", str(tmp_path)])
    yaml_text = (tmp_path / "agenteval.yaml").read_text()
    assert "AgentEval.telemetry.listener.Listener" in yaml_text


def test_scaffolded_readme_documents_listener_requirement(tmp_path: Path) -> None:
    """Bonus: README.md explains why the listener is required."""
    main(["init", "--output-dir", str(tmp_path)])
    readme = (tmp_path / "README.md").read_text()
    assert "AgentEval.telemetry.listener.Listener" in readme
    assert "REQUIRED" in readme.upper()


def test_new_adapter_requires_name_argument(capsys: pytest.CaptureFixture[str]) -> None:
    """`agenteval new-adapter` requires `--name` (Story 8b.2)."""
    with pytest.raises(SystemExit) as excinfo:
        main(["new-adapter"])
    # argparse exits 2 when required args are missing.
    assert excinfo.value.code == 2
