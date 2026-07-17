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

"""Regression: accept the Claude-canonical comma-separated `tools` string.

Dogfood finding: real Claude Code subagents write `tools: Read, Edit, Bash`
(a string), which the parser must normalize to a list.
"""

from __future__ import annotations

from pathlib import Path

from SubagentsLibrary import SubagentsLibrary

COMMA_TOOLS = """---
name: github-modes
description: Operate on GitHub repositories and issues.
tools: Read, Write, Bash
---

# GitHub Modes
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "agent.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_comma_string_tools_normalize_to_list(tmp_path: Path) -> None:
    lib = SubagentsLibrary()
    fm = lib.get_frontmatter(_write(tmp_path, COMMA_TOOLS))
    assert fm["tools"] == ["Read", "Write", "Bash"]


def test_tools_should_be_subset_of_accepts_string_form(tmp_path: Path) -> None:
    lib = SubagentsLibrary()
    path = _write(tmp_path, COMMA_TOOLS)
    lib.tools_should_be_subset_of(path, "Read", "Write", "Bash", "Edit")  # subset -> passes
