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

"""Unit tests for `agenteval new-adapter` scaffolding (Story 8b.2 AC-8b.2.6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval.cli import main


def test_new_adapter_creates_four_scaffolded_files(tmp_path: Path) -> None:
    """AC-8b.2.6 #1: `new-adapter --name x` creates the 4 scaffolded files."""
    rc = main(["new-adapter", "--name", "my-adapter", "--output-dir", str(tmp_path)])
    assert rc == 0
    pkg = tmp_path / "my-adapter"
    assert (pkg / "pyproject.toml").exists()
    assert (pkg / "my_adapter" / "__init__.py").exists()
    assert (pkg / "my_adapter" / "adapter.py").exists()
    assert (pkg / "tests" / "test_my_adapter.py").exists()


def test_name_normalization_kebab_to_snake(tmp_path: Path) -> None:
    """AC-8b.2.6 #2: kebab-case `--name` produces snake_case module name."""
    main(["new-adapter", "--name", "foo-bar-baz", "--output-dir", str(tmp_path)])
    assert (tmp_path / "foo-bar-baz" / "foo_bar_baz" / "adapter.py").exists()
    assert (tmp_path / "foo-bar-baz" / "tests" / "test_foo_bar_baz.py").exists()


def test_subprocess_type_scaffolds_subprocess_adapter(tmp_path: Path) -> None:
    """AC-8b.2.6 #3: `--type subprocess` (default) scaffolds SubprocessAdapter subclass."""
    main(["new-adapter", "--name", "sa", "--output-dir", str(tmp_path)])
    adapter_text = (tmp_path / "sa" / "sa" / "adapter.py").read_text()
    assert "SubprocessAdapter" in adapter_text
    assert "_spawn" in adapter_text


def test_inprocess_type_scaffolds_inprocess_adapter(tmp_path: Path) -> None:
    """AC-8b.2.6 #4: `--type inprocess` scaffolds InProcessAdapter subclass."""
    main(["new-adapter", "--name", "ip", "--type", "inprocess", "--output-dir", str(tmp_path)])
    adapter_text = (tmp_path / "ip" / "ip" / "adapter.py").read_text()
    assert "InProcessAdapter" in adapter_text
    assert "def run(" in adapter_text


def test_exit_code_zero_on_success(tmp_path: Path) -> None:
    """AC-8b.2.6 #5: exit code is 0 on success."""
    rc = main(["new-adapter", "--name", "ok", "--output-dir", str(tmp_path)])
    assert rc == 0


def test_pyproject_declares_entry_point(tmp_path: Path) -> None:
    """Bonus: scaffolded pyproject.toml declares the FR17a entry-points group."""
    main(["new-adapter", "--name", "ep", "--output-dir", str(tmp_path)])
    pyproject = (tmp_path / "ep" / "pyproject.toml").read_text()
    assert "agenteval.coding_agents" in pyproject
    assert "ep =" in pyproject  # entry-point name = module name


def test_refuses_overwrite_without_force(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Bonus: re-run without `--force` does NOT overwrite."""
    main(["new-adapter", "--name", "x", "--output-dir", str(tmp_path)])
    sentinel = "SENTINEL"
    target = tmp_path / "x" / "x" / "adapter.py"
    target.write_text(sentinel)
    main(["new-adapter", "--name", "x", "--output-dir", str(tmp_path)])
    assert target.read_text() == sentinel
    assert "already exists" in capsys.readouterr().err
