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

"""Integration test: `python -m AgentEval.conformance` CLI emits well-formed
JSON + Markdown reports (Story 8a.2 AC-8a.2.10 — FR57 verification).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cli_emits_valid_json_and_md(tmp_path: Path) -> None:
    """AC-8a.2.10: CLI writes both reports + JSON has the 5 top-level keys."""
    output_dir = tmp_path / "conformance-report"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "AgentEval.conformance",
            "--adapter",
            "mock",
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"CLI failed:\n{result.stdout}\n{result.stderr}"

    json_report = output_dir / "conformance-report.json"
    md_report = output_dir / "conformance-report.md"
    assert json_report.exists()
    assert md_report.exists()

    # JSON: all 5 top-level keys present per AC-8a.2.3 schema.
    payload = json.loads(json_report.read_text())
    for key in ("agenteval_version", "adapter", "executed_at", "summary", "fixtures"):
        assert key in payload, f"missing top-level key: {key}"
    assert payload["adapter"] == "mock"

    # Markdown: heading + summary table line present.
    md = md_report.read_text()
    assert "# Conformance Report" in md
    assert "## Summary" in md
    assert "| Total |" in md
