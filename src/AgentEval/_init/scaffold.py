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

"""Scaffold writer for `agenteval init` (Story 8b.1).

Writes the 8 scaffolded files (3 .robot tests + 3 fixtures + agenteval.yaml +
README.md) from the embedded templates in `templates/`. Refuses to overwrite
existing files unless `force=True`.

Canonical invocation pinned in scaffolded files uses the **explicit
`Module.Class` listener path** per Story 8a.2 D-6 empirical finding:

    robot --listener AgentEval.telemetry.listener.Listener --xunit junit.xml tests/

The shorter `--listener AgentEval.telemetry.listener` (module-path-only)
form is accepted by RF 7.x without error but the `Listener` class hooks
do NOT fire (module-as-listener path; no top-level
`ROBOT_LISTENER_API_VERSION`).
"""

from __future__ import annotations

import sys
from pathlib import Path

__all__ = ["scaffold"]

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Map of relative-output-path → template-filename.
_SCAFFOLD_FILES: dict[str, str] = {
    "tests/example_skill_validation.robot": "example_skill_validation.robot",
    "tests/example_mcp_runtime.robot": "example_mcp_runtime.robot",
    "tests/example_agent_run.robot": "example_agent_run.robot",
    "tests/fixtures/example-skill.md": "example-skill.md",
    "tests/fixtures/.mcp.json": "mcp.json",
    "tests/fixtures/scenario.yaml": "scenario.yaml",
    "agenteval.yaml": "agenteval.yaml",  # FACADE_GREP_SKIP — filename, not an OTel attribute key.
    "README.md": "README.md",
}


def scaffold(*, output_dir: Path, force: bool = False) -> int:
    """Scaffold the agenteval starter project at ``output_dir``.

    Args:
        output_dir: target directory (created if absent).
        force: if True, overwrite existing files; otherwise skip + warn per file.

    Returns:
        0 on success; non-zero only if the operation fails fatally (which
        currently cannot happen — all file-write failures bubble up as
        exceptions handled at the CLI layer).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    skipped: list[str] = []
    overwritten: list[str] = []

    for rel_path, template_name in _SCAFFOLD_FILES.items():
        target = output_dir / rel_path
        template_path = _TEMPLATES_DIR / template_name
        if not template_path.exists():
            sys.stderr.write(f"agenteval init: missing template '{template_name}'; skipping {rel_path}\n")
            continue
        if target.exists() and not force:
            sys.stderr.write(f"agenteval init: {rel_path} already exists; use --force to overwrite\n")
            skipped.append(rel_path)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        content = template_path.read_text(encoding="utf-8")
        was_existing = target.exists()
        target.write_text(content, encoding="utf-8")
        if was_existing:
            overwritten.append(rel_path)
            sys.stderr.write(f"agenteval init: overwrote {rel_path}\n")
        else:
            written.append(rel_path)

    # 5-line summary on stdout per AC-8b.1.1.
    sys.stdout.write(
        f"agenteval init: scaffolded {len(written) + len(overwritten)} files "
        f"({len(written)} new, {len(overwritten)} overwritten, "
        f"{len(skipped)} skipped) at {output_dir}.\n"
    )
    sys.stdout.write("\nNext steps:\n")
    sys.stdout.write("  robot --listener AgentEval.telemetry.listener.Listener --xunit junit.xml tests/\n")
    sys.stdout.write("\nSee docs/recipes/01-first-eval-in-five-minutes.md for details.\n")
    return 0
