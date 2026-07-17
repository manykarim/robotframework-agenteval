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

"""The live-dep keywords surface a clear MissingExtraError when [llm] is absent.

We simulate the missing extra by monkeypatching the lazy litellm import so the
test never depends on whether litellm happens to be installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import AgentEval._core.adapter as adapter_module
from AgentEval._core import MissingExtraError
from SkillsLibrary import SkillsLibrary


@pytest.fixture
def lib() -> SkillsLibrary:
    return SkillsLibrary()


@pytest.fixture
def no_llm_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args: Any, **kwargs: Any) -> Any:
        raise MissingExtraError(
            "GenericAdapter needs LiteLLM, which ships with the [llm] extra.",
            extra="llm",
        )

    monkeypatch.setattr(adapter_module, "_import_litellm", _raise)


@pytest.mark.usefixtures("no_llm_extra")
def test_activation_decision_generic_adapter_reports_missing_extra(lib: SkillsLibrary, skill_file: Path) -> None:
    with pytest.raises(MissingExtraError) as excinfo:
        lib.get_activation_decision(skill_file, "find news", model="gpt-4o")
    assert excinfo.value.extra == "llm"


@pytest.mark.usefixtures("no_llm_extra")
def test_should_activate_for_generic_adapter_reports_missing_extra(lib: SkillsLibrary, skill_file: Path) -> None:
    with pytest.raises(MissingExtraError):
        lib.should_activate_for("find news", skill_file, model="gpt-4o")


@pytest.mark.usefixtures("no_llm_extra")
def test_judge_activation_generic_adapter_reports_missing_extra(lib: SkillsLibrary, skill_file: Path) -> None:
    with pytest.raises(MissingExtraError):
        lib.get_judge_activation_decision("some response", skill_file, model="gpt-4o")


@pytest.mark.usefixtures("no_llm_extra")
def test_discoverability_generic_adapter_reports_missing_extra(
    lib: SkillsLibrary, skill_file: Path, tmp_path: Path
) -> None:
    tasks = tmp_path / "tasks.yaml"
    tasks.write_text(
        "tasks:\n  - id: t\n    prompt: find news\n    should_activate: true\n",
        encoding="utf-8",
    )
    with pytest.raises(MissingExtraError):
        lib.get_discoverability(skill_file, tasks, model="gpt-4o")
