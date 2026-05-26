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

"""Docstring `Example:` block syntactic-validity test (Phase 8a CI extraction).

Per the docstring refresh proposal's Kilo-review CRITIQUE 2 mitigation:
every `Example:` block in a migrated keyword's docstring MUST be parsable
as Robot Framework syntax. This test extracts each `Example:` block, wraps
it in a minimal ``*** Test Cases ***`` skeleton, and runs ``robot
--dryrun`` against it.

Phase-1 scope (2026-05-26): only `SubagentsLibrary` + `HooksLibrary`
(the Phase 1 keywords). The `MIGRATED_LIBRARIES` allow-list is shared
with `test_docstring_browser_style.py`.

**Phase-1 carve-out (kept honest per `feedback_honest_framing`):** RF
``--dryrun`` validates **syntactic well-formedness**, NOT runtime
correctness — examples may reference keywords / variables / library
imports the dryrun cannot resolve. The extracted example is wrapped in a
heredoc that loads the keyword's own library + ``BuiltIn`` so the
keyword name resolves; cross-library keyword references degrade to
"unknown keyword" + are explicitly tolerated (skip with an INFO note)
until Phase 8a-v2 grows a per-library suite directive.
"""

from __future__ import annotations

import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from ._walk import (
    find_library_modules,
    iter_keyword_functions,
    load_module_from_path,
)
from .test_docstring_browser_style import MIGRATED_LIBRARIES

# Allow trailing parenthetical annotations after `Example:` (e.g.
# `Example (illustrative ...): `) per Phase 3 Codex-review compromise.
_EXAMPLE_BLOCK_RE = re.compile(
    r"^\s*Example(?:\s*\([^)]*\))?:\s*$\n((?:^\s*\|.*$\n?)+)",
    re.MULTILINE,
)


def _composed_sub_libraries() -> frozenset[str]:
    """Derive the set of composed sub-library module names from `AgentEval._SUB_LIBRARIES`.

    Codex Phase 2 review MED (2026-05-26): the previous hardcoded
    frozenset duplicated the canonical `_SUB_LIBRARIES` tuple in
    `src/AgentEval/__init__.py`. Drift between the two would silently
    cause dryrun-import failures (or false-passes) when a new sub-library
    ships. Derive directly from the canonical source.
    """
    from AgentEval import _SUB_LIBRARIES

    return frozenset(module_path for module_path, _ in _SUB_LIBRARIES)


_COMPOSED_SUBLIBRARIES = _composed_sub_libraries()


def _resolve_dryrun_library_import(module_name: str, class_name: str) -> str:
    """Pick the right ``Library`` import for a docstring-example dryrun.

    Composed sub-libraries are imported as ``AgentEval`` (the parent
    library composes them via `DynamicCore`); direct-import libraries
    (skills, mcp, subagents) use their fully-qualified class path.
    """
    if module_name in _COMPOSED_SUBLIBRARIES:
        return "AgentEval"
    return f"{module_name}.{class_name}"


def _extract_example_lines(doc: str) -> list[str]:
    """Return the pipe-prefixed lines from the `Example:` block in ``doc``."""
    m = _EXAMPLE_BLOCK_RE.search(doc)
    if not m:
        return []
    block = m.group(1)
    lines = [line.strip() for line in block.splitlines() if line.strip().startswith("|")]
    return lines


def _build_dryrun_robot(library_import: str, example_lines: list[str]) -> str:
    """Wrap extracted example lines in a minimal ``.robot`` skeleton.

    The pipe-prefixed Browser-Library docstring format is libdoc syntax,
    NOT RF runtime syntax. Two transformations are required to make the
    extracted example runnable:

    1. Strip backticks around keyword references — Browser uses
       `` ``Send Prompt`` `` for libdoc auto-linking; RF runtime treats
       backticks as literal characters in keyword names + fails to
       resolve.
    2. Strip inline ``# comments`` — Browser docs use them for
       explanation; RF parses them as part of the cell value.
    3. Strip the leading ``|`` and normalize whitespace to the canonical
       4-space RF cell separator.
    """
    test_steps: list[str] = []
    for raw_line in example_lines:
        stripped = raw_line.lstrip("|").strip()
        if not stripped:
            continue
        # Drop trailing inline `# comment` (the comment marker MUST be
        # preceded by whitespace to avoid stripping `#` characters inside
        # quoted string args — RF treats `# foo` as a comment only when
        # preceded by whitespace).
        comment_match = re.search(r"\s+#\s", stripped)
        if comment_match:
            stripped = stripped[: comment_match.start()].rstrip()
        # Strip backticks around keyword + variable references.
        rf_line = stripped.replace("`", "")
        # Normalize runs of 2+ whitespace to the canonical 4-space cell
        # separator (matches project convention).
        rf_line = re.sub(r"\s{2,}", "    ", rf_line)
        test_steps.append(f"    {rf_line}")

    return (
        textwrap.dedent(
            f"""\
        *** Settings ***
        Library    {library_import}

        *** Test Cases ***
        Docstring Example Dryrun
        """
        )
        + "\n".join(test_steps)
        + "\n"
    )


def _all_migrated_examples() -> list[tuple[str, str, str, str, list[str]]]:
    """Yield ``(module_name, class_name, kw_name, library_import_string,
    example_lines)`` for every migrated keyword that has an Example: block.
    """
    out: list[tuple[str, str, str, str, list[str]]] = []
    for path in find_library_modules():
        module = load_module_from_path(path)
        if module.__name__ not in MIGRATED_LIBRARIES:
            continue
        for func_name, func in iter_keyword_functions(module):
            doc = func.__doc__ or ""
            lines = _extract_example_lines(doc)
            if not lines:
                continue
            kw_name = getattr(func, "robot_name", func_name)
            qualname = getattr(func, "__qualname__", "") or func_name
            class_name = qualname.split(".", 1)[0] if "." in qualname else "<module>"
            library_import = _resolve_dryrun_library_import(module.__name__, class_name)
            out.append((module.__name__, class_name, kw_name, library_import, lines))
    return out


def _robot_executable_available() -> bool:
    """Check whether ``robot`` is callable in the current Python environment.

    Codex Phase 2 review HIGH (2026-05-26): invoke ``robot`` via
    ``sys.executable -m robot`` rather than the bare ``robot`` PATH
    entry. Bare ``robot`` resolves to a globally-installed binary that
    may not have ``AgentEval`` on its Python path (causing 9/9 false
    failures in Codex's workspace). ``sys.executable -m robot`` runs
    against the same interpreter+environment as pytest, so library
    imports resolve correctly.

    `robotframework` is a pinned dev dep so this should always be True;
    failure mode is the CI env lacking ``uv``-installed extras.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "robot", "--version"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0 or result.returncode == 251  # `robot --version` exits 251 on RF 7.x
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.mark.parametrize(
    "module_name, class_name, kw_name, library_import, example_lines",
    _all_migrated_examples(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_example_block_dryruns_clean(
    module_name: str,
    class_name: str,
    kw_name: str,
    library_import: str,
    example_lines: list[str],
    tmp_path: Path,
) -> None:
    """Extracted Example: block must pass ``robot --dryrun``.

    Phase 8a CI mitigation per Kilo CRITIQUE 2: an unenforceable "MUST be
    dryrun-able" gate becomes enforceable when CI extracts the block + runs
    dryrun against it. Failure modes caught: typos in keyword names,
    missing arguments, wrong assertion-operator syntax, malformed pipe
    table.
    """
    if not _robot_executable_available():
        # Kilo Phase 1 review MED (Patch D, 2026-05-26): the previous
        # unconditional `pytest.skip` silently masked failures when CI
        # environments had broken PATH config. Per the mitigation, fail
        # hard on CI (`CI` env var set by GitHub Actions + most CI
        # systems) so the missing dependency surfaces as a real
        # actionable error rather than a false-green skip.
        import os

        if os.environ.get("CI"):
            pytest.fail(
                "`robot` executable not available in PATH on CI — example "
                "block dryrun cannot validate. This is likely a "
                "misconfigured CI environment, NOT a deliberate opt-out. "
                "Verify `uv sync --all-extras` ran successfully."
            )
        pytest.skip("`robot` executable not available in PATH; dryrun cannot run.")

    suite_content = _build_dryrun_robot(library_import, example_lines)
    suite_path = tmp_path / "docstring_example.robot"
    suite_path.write_text(suite_content, encoding="utf-8")

    # Codex Phase 2 review HIGH patch: invoke `robot` via
    # `sys.executable -m robot` so library imports resolve in the same
    # interpreter+environment as pytest. The bare `robot` form resolved
    # to a global binary that lacked `AgentEval` on its Python path.
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "robot",
            "--dryrun",
            "--outputdir",
            str(tmp_path),
            str(suite_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    # RF dryrun exit codes: 0 = all-pass; 1-249 = N tests failed; 250 = ≥250 failures;
    # 251-255 = framework-level errors. We accept 0 (clean). For non-zero,
    # the suite content + RF output are included in the assertion message so
    # the diagnostic is self-contained.
    assert result.returncode == 0, (
        f"{module_name}::{class_name}::{kw_name} Example: block failed "
        f"`robot --dryrun` (returncode={result.returncode}).\n\n"
        f"Suite content:\n{suite_content}\n"
        f"--- robot stdout ---\n{result.stdout}\n"
        f"--- robot stderr ---\n{result.stderr}"
    )
