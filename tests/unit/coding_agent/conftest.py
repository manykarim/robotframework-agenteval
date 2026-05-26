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

"""Shared fixtures for `tests/unit/coding_agent/` (Story 4.2 + future adapters).

Story 4.2 code-review Edge-cases MED-1 fix 2026-05-20: the
`mock_claude_version` fixture was originally scoped to
`test_claude_code_cli.py` autouse-locally. Any future cross-module
test (e.g., one that imports + constructs `ClaudeCodeCLIAdapter`
indirectly through entry-points discovery) without monkeypatching
`subprocess.run` would shell out to the real `claude --version`,
which in some CI environments yields `UnsupportedBinaryVersionError(
detected=None)` and silently passes a "raises" assertion — a
fake-green CI failure mode per `feedback_ci_log_forensics`.

Hoisting the fixture to this `conftest.py` makes it apply across
the entire coding_agent test directory tree. Any new adapter test
file inherits the protection without opt-in.
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def mock_claude_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch `subprocess.run` so `_assert_binary_version("claude")` passes
    without requiring the real `claude` binary in CI.

    Scope: package-wide autouse across `tests/unit/coding_agent/`.
    """
    real_run = subprocess.run

    def _fake_run(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and len(cmd) >= 2 and cmd[0] == "claude" and cmd[1] == "--version":
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="2.1.144 (Claude Code)\n", stderr="")
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fake_run)


@pytest.fixture(autouse=True)
def mock_copilot_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch `subprocess.run` so `_assert_binary_version("copilot")` passes
    without requiring the real `copilot` binary in CI.

    Story 11.2 D-4 (cross-story UPSTREAM from Story 4.2 Edge-cases MED-1 +
    Story 11.1 D-4): fixture hoisted to `conftest.py` directly from the
    start so future cross-module Copilot CLI tests inherit the mock
    automatically.

    Default version: ``GitHub Copilot CLI 1.0.54.`` (local probe
    2026-05-26; trailing period is intentional — the base
    `_SEMVER_RE.search()` extracts the semver substring). Scope:
    package-wide autouse across `tests/unit/coding_agent/`.
    """
    real_run = subprocess.run

    def _fake_run(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and len(cmd) >= 2 and cmd[0] == "copilot" and cmd[1] == "--version":
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="GitHub Copilot CLI 1.0.54.\n", stderr="")
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fake_run)


@pytest.fixture(autouse=True)
def mock_codex_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch `subprocess.run` so `_assert_binary_version("codex")` passes
    without requiring the real `codex` binary in CI.

    Story 11.1 D-4 (cross-story UPSTREAM from Story 4.2 Edge-cases MED-1):
    fixture hoisted to `conftest.py` directly from the start so future
    cross-module Codex CLI tests inherit the mock automatically.

    Default version: ``codex-cli 0.133.0`` (local probe 2026-05-26).
    The `codex-cli ` prefix is included in the fake stdout so the
    base `_SEMVER_RE.search()` extracts ``0.133.0`` from the suffix.
    Scope: package-wide autouse across `tests/unit/coding_agent/`.
    """
    real_run = subprocess.run

    def _fake_run(cmd: Any, **kwargs: Any) -> Any:
        if isinstance(cmd, list) and len(cmd) >= 2 and cmd[0] == "codex" and cmd[1] == "--version":
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="codex-cli 0.133.0\n", stderr="")
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fake_run)
