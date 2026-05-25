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

"""Integration test: `trace_id:<full_name>` tag surfaces in `output.xml`
when RF runs with `--listener AgentEval.telemetry.listener` (Story 8a.2
AC-8a.2.8 — FR51 verification).
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_SMOKE_ROBOT = """\
*** Test Cases ***
Smoke Alpha
    Log    alpha

Smoke Beta
    Log    beta
"""


def test_trace_id_tag_present_on_each_test(tmp_path: Path) -> None:
    """AC-8a.2.8: every `<test>` in `output.xml` has a `<tag>trace_id:<full_name></tag>`."""
    suite_path = tmp_path / "smoke.robot"
    suite_path.write_text(_SMOKE_ROBOT)
    output_xml = tmp_path / "output.xml"
    # Use the explicit `Module.Class` listener path. Empirical RF 7.x
    # behavior (Story 8a.2 dev probe 2026-05-25): the shorter
    # `AgentEval.telemetry.listener` module-path form is resolved by RF
    # but `start_suite`/`start_test` hooks do NOT fire on the `Listener`
    # class instance — RF appears to use the module-as-listener path
    # which has no `ROBOT_LISTENER_API_VERSION` at module level. The
    # explicit class path makes RF instantiate the class correctly.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "robot",
            "--listener",
            "AgentEval.telemetry.listener.Listener",
            "--output",
            str(output_xml),
            "--report",
            "NONE",
            "--log",
            "NONE",
            str(suite_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0, f"robot failed:\n{result.stdout}\n{result.stderr}"
    assert output_xml.exists(), "robot did not write output.xml"

    tree = ET.parse(output_xml)
    test_elements = list(tree.iter("test"))
    assert len(test_elements) == 2, f"expected 2 tests, got {len(test_elements)}"

    for test in test_elements:
        # RF writes `<tag>` children inside an enclosing element; flatten to
        # all tag elements under this test.
        tag_texts = [t.text or "" for t in test.iter("tag")]
        trace_id_tags = [t for t in tag_texts if t.startswith("trace_id:")]
        assert trace_id_tags, f"no trace_id tag on test {test.get('name')!r}; tags found: {tag_texts!r}"
        # The tag value must equal `trace_id:<full_name>` per FR51 + Story 8a.2 D-2.
        # RF full_name format: `Smoke.Smoke Alpha` (suite.test).
        expected = f"trace_id:Smoke.{test.get('name')}"
        assert expected in trace_id_tags, f"expected {expected!r} on test {test.get('name')!r}; got {trace_id_tags!r}"
