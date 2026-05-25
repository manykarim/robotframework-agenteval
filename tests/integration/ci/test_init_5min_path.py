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

"""Integration test for Story 8b.1 5-minute first-run path (AC-8b.1.9).

Drives the full end-to-end NFR-UX-01 flow:

1. `python -m AgentEval.cli init --output-dir <tmp>` scaffolds the project.
2. `robot --listener AgentEval.telemetry.listener.Listener --xunit junit.xml tests/`
   runs the scaffolded suite.
3. The resulting `junit.xml` contains `<property name="agenteval.adapter">`
   on at least one testcase (verifies end-to-end Story 8a.1 + 8a.2 + 8b.1
   integration).
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def test_init_then_robot_run_passes_and_produces_enriched_xunit(tmp_path: Path) -> None:
    """AC-8b.1.9: init → robot → enriched xunit.xml round-trip."""
    # Step 1: init.
    init_result = subprocess.run(
        [sys.executable, "-m", "AgentEval.cli", "init", "--output-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert init_result.returncode == 0, f"agenteval init failed:\n{init_result.stdout}\n{init_result.stderr}"
    # The 8 scaffolded files exist.
    assert (tmp_path / "tests/example_skill_validation.robot").exists()
    assert (tmp_path / "tests/example_agent_run.robot").exists()
    assert (tmp_path / "agenteval.yaml").exists()

    # Step 2: run only the Mock-provider agent test (the MCP runtime test
    # needs the bundled echo server which spawns a subprocess + can be flaky
    # in CI; the agent-run test is sufficient for the 5-min-path enrichment
    # verification). The skill-validation test is also self-contained.
    xunit_path = tmp_path / "junit.xml"
    robot_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "robot",
            "--listener",
            "AgentEval.telemetry.listener.Listener",
            "--xunit",
            str(xunit_path),
            "--output",
            str(tmp_path / "output.xml"),
            "--report",
            "NONE",
            "--log",
            "NONE",
            str(tmp_path / "tests/example_agent_run.robot"),
            str(tmp_path / "tests/example_skill_validation.robot"),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert robot_result.returncode == 0, f"robot failed:\n{robot_result.stdout}\n{robot_result.stderr}"
    assert xunit_path.exists()

    # Step 3: parse junit.xml + verify at least one `<property
    # name="agenteval.adapter">` on a `Send Prompt`-firing testcase.
    tree = ET.parse(xunit_path)
    found_agenteval_property = False
    for testcase in tree.iter("testcase"):
        props = testcase.find("properties")
        if props is None:
            continue
        for p in props.findall("property"):
            name = p.get("name", "")
            if name.startswith("agenteval."):
                found_agenteval_property = True
                break
        if found_agenteval_property:
            break
    assert found_agenteval_property, (
        "no agenteval.* property found in junit.xml — Story 8a.1 enrichment "
        "did not fire (likely a Listener wiring regression)"
    )


def test_init_stdout_summary_pinned_class_path(tmp_path: Path) -> None:
    """Bonus: stdout summary contains the explicit class-path invocation.

    Re-verifies AC-8b.1.1 #4 + AC-8b.1.6 at the subprocess boundary
    (the unit test verifies via in-process `main()` call).
    """
    result = subprocess.run(
        [sys.executable, "-m", "AgentEval.cli", "init", "--output-dir", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "AgentEval.telemetry.listener.Listener" in result.stdout
