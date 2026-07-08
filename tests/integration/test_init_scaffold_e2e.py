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

"""End-to-end scaffold smoke test for `agenteval init`.

Runs `agenteval init` in a temp directory (the same entry point users hit),
then executes the scaffolded example suites with the documented run command
(mock provider + bundled echo MCP server — no API keys), and asserts Robot
Framework exits 0. Additionally loads the scaffolded `scenario.yaml` through
the library's own `Load Scenario` path.

This is a forcing function: if any scaffold template regresses (missing
import, wrong keyword shape, invalid YAML), this test fails on the offending
push before merge. Keyless + deterministic; the subprocess calls are
timeout-bounded to contain any stdio-subprocess hang.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Hard timeouts so a hung stdio MCP subprocess fails the test rather than the job.
_INIT_TIMEOUT_S = 60
_ROBOT_TIMEOUT_S = 180


def _robot_module_available() -> bool:
    """Return True iff the `robot` module is importable in the current interpreter."""
    return importlib.util.find_spec("robot") is not None


def _run(cmd: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=os.environ.copy(),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _scaffold(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Run `agenteval init` into ``tmp_path`` via the module entry point."""
    return _run(
        [sys.executable, "-m", "AgentEval.cli", "init", "--output-dir", str(tmp_path)],
        cwd=tmp_path,
        timeout=_INIT_TIMEOUT_S,
    )


def test_scaffolded_suites_run_green(tmp_path: Path) -> None:
    """`agenteval init` then the documented run command exits 0 with zero edits."""
    if not _robot_module_available():  # pragma: no cover — `uv` env always ships robot
        pytest.skip("robot module not importable from current sys.executable; cannot run scaffold.")

    init = _scaffold(tmp_path)
    assert init.returncode == 0, (
        f"`agenteval init` failed (exit={init.returncode}):\n"
        f"--- stdout ---\n{init.stdout}\n--- stderr ---\n{init.stderr}\n"
    )
    # Sanity: the example suites were written.
    tests_dir = tmp_path / "tests"
    assert (tests_dir / "example_mcp_runtime.robot").exists()
    assert (tests_dir / "example_agent_run.robot").exists()
    assert (tests_dir / "example_skill_validation.robot").exists()

    result = _run(
        [
            sys.executable,
            "-m",
            "robot",
            "--listener",
            "AgentEval.telemetry.listener.Listener",
            "--xunit",
            "junit.xml",
            "--outputdir",
            str(tmp_path / "rf_out"),
            str(tests_dir),
        ],
        cwd=tmp_path,
        timeout=_ROBOT_TIMEOUT_S,
    )
    assert result.returncode == 0, (
        f"scaffolded suites failed under the documented run command "
        f"(exit={result.returncode}):\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}\n"
    )


def test_scaffolded_scenario_yaml_loads(tmp_path: Path) -> None:
    """`Load Scenario` accepts the scaffolded `tests/fixtures/scenario.yaml`."""
    from AgentEval.scenarios.loader import load_scenario
    from AgentEval.scenarios.schema import Scenario

    init = _scaffold(tmp_path)
    assert init.returncode == 0, f"`agenteval init` failed (exit={init.returncode}):\n{init.stderr}"
    scenario_path = tmp_path / "tests" / "fixtures" / "scenario.yaml"
    assert scenario_path.exists(), f"scaffolded scenario.yaml missing at {scenario_path}"

    scenario = load_scenario(scenario_path)
    assert isinstance(scenario, Scenario)
    # mcp_servers must be a list of strings per the shipped schema.
    assert scenario.mcp_servers == ["bundled-echo"]
    assert all(isinstance(name, str) for name in scenario.mcp_servers)
    assert len(scenario.evals) >= 1
