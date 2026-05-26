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

"""Docstring-style conventions tests (Browser-Library-style refresh, 2026-05-26).

Per the docstring refresh proposal at
`_bmad-output/planning-artifacts/docstring-refresh-proposal-2026-05-26.md`,
keyword docstrings adopt Browser-Library style with three mandatory
structural elements:

1. **Arguments table** — pipe-delimited header `| =Arguments= | =Description= |`
2. **Example section** — `Example:` heading followed by ≥1 pipe-prefixed RF
   syntax line.
3. **Citation consistency** — any FR/ADR/Story identifier in the docstring
   body must also appear in the `Notes:` tail section (Kilo CRITIQUE 4
   bidirectional-consistency mitigation).

Phase-1 enforcement scope (2026-05-26): only `SubagentsLibrary` +
`HooksLibrary` (the 2 keywords refactored in Phase 1). Phases 2-7 add
more keywords to the `MIGRATED_LIBRARIES` allow-list as they ship.

The `Example:` block validity is enforced by
`test_docstring_examples_dryrun.py` (Phase 8a CI extraction).
"""

from __future__ import annotations

import re

import pytest

from ._walk import (
    find_library_modules,
    iter_keyword_functions,
    load_module_from_path,
)


def _get_migrated_libraries() -> frozenset[str]:
    """Derive the set of Browser-style-migrated libraries from a module-level marker.

    Kilo Phase 1 review HIGH (Patch C, 2026-05-26): the previous hardcoded
    ``MIGRATED_LIBRARIES = frozenset({"AgentEval.subagents.library", ...})``
    required a manual update at every migration commit + drifted silently
    when new libraries shipped without the test-file edit. The flag-derived
    pattern is self-documenting: a developer adding a new
    ``src/AgentEval/foo/library.py`` but forgetting
    ``_BROWSER_STYLE_MIGRATED = True`` gets a test failure when the new
    library's docstrings aren't checked — exactly the right correction
    signal.
    """
    out: set[str] = set()
    for path in find_library_modules():
        module = load_module_from_path(path)
        if getattr(module, "_BROWSER_STYLE_MIGRATED", False):
            out.add(module.__name__)
    return frozenset(out)


MIGRATED_LIBRARIES = _get_migrated_libraries()

_ARGUMENTS_TABLE_HEADER = re.compile(r"^\s*\|\s*=Arguments=\s*\|\s*=Description=\s*\|", re.MULTILINE)
# Allow trailing parenthetical annotations after `Example:` (e.g. for
# `Example (illustrative — assumes a real adapter): ...`). The Phase 3
# Codex review surfaced the need for these annotations on mock-incompatible
# examples; treating bare `Example:` AND `Example (...):` as valid is the
# pragmatic compromise.
_EXAMPLE_BLOCK = re.compile(r"^\s*Example(?:\s*\([^)]*\))?:\s*$", re.MULTILINE)
_EXAMPLE_LINE = re.compile(r"^\s*\|\s+\S+", re.MULTILINE)
_NOTES_SECTION = re.compile(r"^\s*Notes:\s*$", re.MULTILINE)

# Citation patterns the bidirectional-consistency check enforces:
# any of these in the body MUST also be present in the Notes: tail OR
# in an inline parenthetical with the same identifier text.
_FR_PATTERN = re.compile(r"\bFR\d+[a-z]?\b")
_ADR_PATTERN = re.compile(r"\bADR-\d+\b")
_STORY_PATTERN = re.compile(r"\bStory \d+[ab]?\.\d+\b")


def _all_migrated_keywords() -> list[tuple[str, str, str, str]]:
    """Yield ``(module_name, class_name, kw_name, docstring)`` for every
    `@keyword`-decorated method in a migrated library.

    `iter_keyword_functions` yields ``(name, func)`` tuples per the
    Story 1b.6 walker contract. The class name is derived from the
    function's ``__qualname__`` (e.g. ``SubagentsLibrary.get_frontmatter``
    → ``SubagentsLibrary``).
    """
    out: list[tuple[str, str, str, str]] = []
    for path in find_library_modules():
        module = load_module_from_path(path)
        if module.__name__ not in MIGRATED_LIBRARIES:
            continue
        for func_name, func in iter_keyword_functions(module):
            doc = func.__doc__ or ""
            kw_name = getattr(func, "robot_name", func_name)
            qualname = getattr(func, "__qualname__", "") or func_name
            class_name = qualname.split(".", 1)[0] if "." in qualname else "<module>"
            out.append((module.__name__, class_name, kw_name, doc))
    return out


@pytest.mark.parametrize(
    "module_name, class_name, kw_name, doc",
    _all_migrated_keywords(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_arguments_table_present(module_name: str, class_name: str, kw_name: str, doc: str) -> None:
    """Browser-style ``| =Arguments= | =Description= |`` table required."""
    assert doc, f"{module_name}::{class_name}::{kw_name} has no docstring"
    assert _ARGUMENTS_TABLE_HEADER.search(doc), (
        f"{module_name}::{class_name}::{kw_name} docstring missing the "
        "`| =Arguments= | =Description= |` table header (Browser-Library "
        "style required for migrated libraries — see "
        "_bmad-output/planning-artifacts/docstring-refresh-proposal-2026-05-26.md)"
    )


@pytest.mark.parametrize(
    "module_name, class_name, kw_name, doc",
    _all_migrated_keywords(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_example_block_present(module_name: str, class_name: str, kw_name: str, doc: str) -> None:
    """Browser-style ``Example:`` block with ≥1 pipe-prefixed line required."""
    assert _EXAMPLE_BLOCK.search(doc), (
        f"{module_name}::{class_name}::{kw_name} docstring missing the "
        "`Example:` heading. Browser-Library style requires every keyword "
        "to ship ≥1 RF-syntax example for libdoc HTML rendering."
    )
    # At least one pipe-prefixed line must follow somewhere after the heading.
    example_start = _EXAMPLE_BLOCK.search(doc)
    assert example_start
    after = doc[example_start.end() :]
    assert _EXAMPLE_LINE.search(after), (
        f"{module_name}::{class_name}::{kw_name} `Example:` heading has no pipe-prefixed example line following it."
    )


@pytest.mark.parametrize(
    "module_name, class_name, kw_name, doc",
    _all_migrated_keywords(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_notes_section_present(module_name: str, class_name: str, kw_name: str, doc: str) -> None:
    """``Notes:`` tail section required for citation grepability."""
    assert _NOTES_SECTION.search(doc), (
        f"{module_name}::{class_name}::{kw_name} docstring missing the "
        "`Notes:` tail section. Browser-Library-style refactor groups "
        "FR/ADR/Story citations into `Notes:` per the docstring refresh "
        "proposal Kilo-review CRITIQUE 4 mitigation."
    )


@pytest.mark.parametrize(
    "module_name, class_name, kw_name, doc",
    _all_migrated_keywords(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_citation_bidirectional_consistency(module_name: str, class_name: str, kw_name: str, doc: str) -> None:
    """Citation drift check (Kilo CRITIQUE 4 bidirectional consistency).

    Any FR / ADR / Story identifier mentioned in the docstring body MUST
    also appear in the `Notes:` tail section. Prevents the failure mode
    where contributors edit the body + drift the Notes: section out of
    sync.

    Exception: identifiers wrapped in inline parentheticals
    ``(... FR42 ...)`` qualifying a specific Arguments table row are
    exempt — the row context IS the citation locality. Only
    paragraph-level body mentions trigger this check.
    """
    notes_match = _NOTES_SECTION.search(doc)
    if not notes_match:
        pytest.skip("No Notes: section — covered by test_notes_section_present")
    body = doc[: notes_match.start()]
    notes = doc[notes_match.end() :]

    body_ids = set()
    notes_ids = set()
    for pattern in (_FR_PATTERN, _ADR_PATTERN, _STORY_PATTERN):
        body_ids.update(pattern.findall(body))
        notes_ids.update(pattern.findall(notes))

    # Identifiers in the Arguments-table rows are NOT considered "body"
    # mentions — they qualify a specific row. Strip table rows from `body`
    # before computing the diff.
    body_no_table = re.sub(r"^\s*\|.*\|\s*$", "", body, flags=re.MULTILINE)
    body_no_table_ids = set()
    for pattern in (_FR_PATTERN, _ADR_PATTERN, _STORY_PATTERN):
        body_no_table_ids.update(pattern.findall(body_no_table))

    missing_in_notes = body_no_table_ids - notes_ids
    assert not missing_in_notes, (
        f"{module_name}::{class_name}::{kw_name} docstring body mentions "
        f"identifiers {sorted(missing_in_notes)!r} but they are NOT echoed "
        "in the `Notes:` tail section. Add a bullet to `Notes:` referencing "
        "each (Kilo CRITIQUE 4 bidirectional-consistency mitigation)."
    )
