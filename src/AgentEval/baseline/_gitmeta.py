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

"""Best-effort git metadata capture (design Decision 10).

``git rev-parse HEAD`` + ``git status --porcelain`` via ``subprocess.run`` with
a short timeout. ANY failure (no git binary, not a repo, timeout) yields
``(None, None)`` — a missing SHA MUST NEVER block a snapshot (CI environments
without ``.git`` must still be able to compare). A ``GITHUB_SHA``-style env var
is a secondary source when the subprocess fails.
"""

from __future__ import annotations

import os
import subprocess

__all__ = ["capture_git_metadata"]

_TIMEOUT_SECONDS = 3.0
# Env fallbacks in priority order (design D10 — CI recipe is a primary consumer).
_ENV_SHA_KEYS = ("GITHUB_SHA", "GIT_COMMIT", "CI_COMMIT_SHA")


def _run_git(args: list[str]) -> str | None:
    try:
        proc = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def capture_git_metadata() -> tuple[str | None, bool | None]:
    """Return ``(git_sha, git_dirty)`` — best-effort, never raises.

    Returns:
        ``(sha, dirty)`` where ``sha`` is the full HEAD hash (or an env
        fallback), and ``dirty`` is True when ``git status --porcelain`` is
        non-empty. Both are ``None`` when git is unavailable and no env SHA is
        set; ``dirty`` is ``None`` when only an env SHA is known (no working
        tree to inspect).
    """
    sha = _run_git(["rev-parse", "HEAD"])
    if sha:
        status = _run_git(["status", "--porcelain"])
        # status is "" (clean) vs non-empty (dirty); None means the status
        # probe itself failed → we cannot claim clean, so report None.
        dirty: bool | None = (status != "") if status is not None else None
        return (sha, dirty)

    for key in _ENV_SHA_KEYS:
        env_sha = os.environ.get(key)
        if env_sha:
            return (env_sha.strip(), None)
    return (None, None)
