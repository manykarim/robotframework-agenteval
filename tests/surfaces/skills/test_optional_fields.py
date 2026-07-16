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

"""Regression: allowed-tools / disable-model-invocation are OPTIONAL (Agent Skills spec).

Dogfood finding: the real published skills carry only name + description, so the
validator must accept them and the getters must default gracefully.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from AgentEval._core import InvalidConfigError
from SkillsLibrary import SkillsLibrary

MINIMAL = """---
name: rf-results
description: Parse Robot Framework output.xml into JSON summaries.
---

# Robot Framework Results
"""


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "SKILL.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_minimal_skill_is_valid(tmp_path: Path) -> None:
    lib = SkillsLibrary()
    fm = lib.get_frontmatter(_write(tmp_path, MINIMAL))
    lib.should_be_valid_frontmatter(fm)  # must not raise


def test_absent_optional_fields_default(tmp_path: Path) -> None:
    lib = SkillsLibrary()
    path = _write(tmp_path, MINIMAL)
    assert lib.get_allowed_tools(path) == []
    assert lib.get_disable_model_invocation(path) is False
    assert lib.get_description(path) == "Parse Robot Framework output.xml into JSON summaries."


def test_present_but_mistyped_optional_still_raises(tmp_path: Path) -> None:
    lib = SkillsLibrary()
    body = MINIMAL.replace("---\n\n# Robot", "allowed-tools: Read, Write\n---\n\n# Robot")
    with pytest.raises(InvalidConfigError):
        lib.should_be_valid_frontmatter(lib.get_frontmatter(_write(tmp_path, body)))
