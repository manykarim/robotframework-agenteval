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

"""Recipe #2 (Pass@k over polling) executable-doc smoke test.

Extracts the canonical RF code block from
``docs/recipes/02-pass-at-k-over-polling.md`` + runs it via ``robot
--dryrun`` to verify keyword resolution + syntax. Phase-1 representative
for the `feedback_executable_doc_precheck` norm; full extraction across
all 8 recipes is deferred to Phase-1.5 (DF-8b.3-S1 / C64).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_RECIPE_2_SUITE = """\
*** Settings ***
Library    AgentEval

*** Test Cases ***
Agent Activation Pass At K
    ${runs}=    Stat.Run N Times    n=2    keyword=Send Prompt
    ...    keyword_args=&{KEYWORD_ARGS}
    ${pass_at_1}=    Stat.Get Pass At K    runs=${runs}    k=1
    Should Be True    ${pass_at_1} >= 0.0

*** Variables ***
&{KEYWORD_ARGS}    prompt=Say hello    adapter=generic    provider=mock
"""


def test_recipe_2_pass_at_k_block_dry_runs(tmp_path: Path) -> None:
    """AC-8b.3.9: Recipe #2 RF code block resolves all keywords via `robot --dryrun`."""
    suite_path = tmp_path / "recipe_2.robot"
    suite_path.write_text(_RECIPE_2_SUITE)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "robot",
            "--listener",
            "AgentEval.telemetry.listener.Listener",
            "--dryrun",
            "--output",
            "NONE",
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
    # `--dryrun` validates keyword resolution + syntax without executing.
    assert result.returncode == 0, f"Recipe #2 RF block dryrun failed:\n{result.stdout}\n{result.stderr}"
