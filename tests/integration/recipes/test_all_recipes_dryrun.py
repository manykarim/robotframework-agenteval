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

"""Recipe CI extraction harness (Story 14.3 deliverable).

Walks every ``docs/recipes/*.md`` file, extracts every fenced
` ```robotframework ` block, classifies each, and runs ``robot --dryrun``
against each dryrun-eligible block (blocks containing ``*** Test Cases ***``).

Closes 3 retro action items (3 epics carryover chain) + 1 catalog row:
- Epic 11 retro Action #7 (2026-05-27, original).
- Epic 12 retro Action #9 (2026-06-01, carried).
- Epic 13 retro Action #9 (2026-06-03, carried again).
- C64 / DF-8b.3-S1 (catalog row at ``docs/phase-1-5-carry-overs.md`` L88).

Block classification (per Story 14.3 D-1):
- ``dryrun_eligible``: contains ``*** Test Cases ***``. Wrapped with
  ``*** Settings ***\\nLibrary    AgentEval\\n\\n`` if no settings header
  is present, then dryrun'd.
- ``settings_only``: contains ``*** Settings ***`` only (no test cases —
  recipe-8 OTLP config examples). SKIPPED with ``pytest.skip(reason=...)``.
- ``fragment``: no section headers (standalone keyword calls referencing
  variables defined earlier in the recipe prose — recipe-2 / recipe-3 /
  recipe-7 inline snippets). SKIPPED with ``pytest.skip(reason=...)``.

Intentional overlap with ``tests/integration/recipes/test_pass_at_k_recipe.py``
per AC-14.3.4: Recipe #2's block-0 (the full suite) is now exercised by both
tests. The Phase-1 representative is retained as redundant coverage; removal
would shrink the test surface.

Story 14.2's catalog-gate hook scans staged diffs for ``DF-X.Y-SZ`` references.
This file does NOT contain any ``DF-`` reference in test fixtures (the
broken-block fixture uses ``Get From Dictionary``, which is NOT a DF ref).
The harness only walks ``docs/recipes/*.md`` — never ``tests/`` — so no
self-recursion concern.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RECIPES_DIR = REPO_ROOT / "docs" / "recipes"

_TEST_CASES_RE = re.compile(r"^\*\*\* Test Cases \*\*\*\s*$", re.MULTILINE)
_SETTINGS_RE = re.compile(r"^\*\*\* Settings \*\*\*\s*$", re.MULTILINE)


@dataclass(frozen=True)
class FencedRobotBlock:
    """A fenced ``robotframework`` code block extracted from a recipe markdown file."""

    recipe: str  # Basename of the source `.md` (e.g., "02-pass-at-k-over-polling.md").
    block_index: int  # 0-based ordinal within the recipe.
    raw: str  # Block content without the fence markers (trailing newline preserved).
    source_line: int  # 1-based line in source `.md` where the opening fence sits.

    @property
    def test_id(self) -> str:
        return f"{self.recipe}::block-{self.block_index}"


_ROBOT_FENCE_OPEN_RE = re.compile(r"^(?P<fence>`{3,})robotframework\s*$")


def extract_robotframework_blocks(path: Path) -> list[FencedRobotBlock]:
    """Walk ``path`` line-by-line and return every fenced ``robotframework`` block.

    Closes on a bare fence of the SAME LENGTH as the opener (per CommonMark
    GFM fenced-code-block semantics). This handles nested fenced examples
    inside a robot block — e.g., an inner ```` ```python ```` example
    with shorter or differently-tagged fence is preserved verbatim rather
    than truncating the outer block (per Story 14.3 Codex HIGH-A).

    Handles edge cases:
    - Empty blocks (raw="") are returned (caller may classify them).
    - Unclosed blocks raise ``ValueError``.
    """
    text = path.read_text(encoding="utf-8")
    blocks: list[FencedRobotBlock] = []
    in_block = False
    block_lines: list[str] = []
    open_line: int = 0
    block_index = 0
    open_fence: str = ""
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not in_block:
            m = _ROBOT_FENCE_OPEN_RE.match(line)
            if m:
                in_block = True
                block_lines = []
                open_line = lineno
                open_fence = m.group("fence")
            continue
        # in_block == True — close only on a bare fence matching the opener's length.
        stripped = line.rstrip()
        if stripped == open_fence:
            raw = "\n".join(block_lines)
            if block_lines:
                raw += "\n"
            blocks.append(
                FencedRobotBlock(
                    recipe=path.name,
                    block_index=block_index,
                    raw=raw,
                    source_line=open_line,
                )
            )
            block_index += 1
            in_block = False
            block_lines = []
            open_fence = ""
            continue
        block_lines.append(line)
    if in_block:
        raise ValueError(
            f"Unclosed ```robotframework block in {path} starting at line {open_line}"
        )
    return blocks


def classify_block(block: FencedRobotBlock) -> str:
    """Return one of ``"dryrun_eligible"``, ``"settings_only"``, or ``"fragment"``.

    - ``dryrun_eligible``: block contains ``*** Test Cases ***`` (whether or
      not ``*** Settings ***`` is also present).
    - ``settings_only``: block contains ``*** Settings ***`` only.
    - ``fragment``: block contains neither section header.
    """
    has_test_cases = bool(_TEST_CASES_RE.search(block.raw))
    has_settings = bool(_SETTINGS_RE.search(block.raw))
    if has_test_cases:
        return "dryrun_eligible"
    if has_settings:
        return "settings_only"
    return "fragment"


def wrap_block_for_dryrun(block: FencedRobotBlock) -> str:
    """Return the full RF suite text to write to a temp ``.robot`` file.

    - If block has ``*** Settings ***``: returns ``block.raw`` unchanged.
    - If block has ``*** Test Cases ***`` but NOT ``*** Settings ***``:
      prepends a minimal Library import block.
    - Settings-only or fragment blocks are NOT wrappable (they are SKIPPED
      upstream); raises ``ValueError`` on those classes for safety.
    """
    has_test_cases = bool(_TEST_CASES_RE.search(block.raw))
    has_settings = bool(_SETTINGS_RE.search(block.raw))
    if not has_test_cases:
        raise ValueError(
            f"Block {block.test_id} is not dryrun-eligible "
            "(no `*** Test Cases ***` header); cannot wrap."
        )
    if has_settings:
        return block.raw
    return f"*** Settings ***\nLibrary    AgentEval\n\n{block.raw}"


def _collect_all_blocks() -> list[FencedRobotBlock]:
    """Return every fenced ``robotframework`` block across every recipe `.md` file."""
    out: list[FencedRobotBlock] = []
    for md_path in sorted(RECIPES_DIR.glob("*.md")):
        out.extend(extract_robotframework_blocks(md_path))
    return out


def _collect_eligible_blocks() -> list[FencedRobotBlock]:
    return [b for b in _collect_all_blocks() if classify_block(b) == "dryrun_eligible"]


_ALL_BLOCKS = _collect_all_blocks()
_ELIGIBLE_BLOCKS = _collect_eligible_blocks()
_ELIGIBLE_COUNT = len(_ELIGIBLE_BLOCKS)

# The 4 previously-broken recipe blocks (recipe-3 block-0 missing the `MCP`
# namespace import, recipe-5 block-0/block-1, recipe-7 block-0 `Get Server
# Config` arity) were fixed against the shipped keyword surface, so the skip
# list is empty. It stays as the mechanism for triaging any future breakage:
# add a `"<recipe>.md::block-N": "<reason>"` entry to skip a block deliberately.
_KNOWN_BROKEN_BLOCKS: dict[str, str] = {}

# Cross-LLM review v2 correction (Opus HIGH-2): the v0.2.0 framing
# "AC-14.3.3 threshold relaxed ≥6→≥4" was a spurious amendment — it
# conflated *eligible* (8) with *passing* (4). AC-14.3.3 itself measures
# dryrun-ELIGIBLE blocks (8 ≥ 6, unamended). The passing count (4) is a
# SEPARATE metric tracking the retro actions' "≥6 passing" bar (Epic 11
# L157 + Epic 12 L168 + Epic 13 L186), which is NOT met until DF-14.3-S1
# fixes 2+ of the known-broken recipes. The assertion below is a
# DF-14.3-S1 regression-guard floor — NOT an AC-14.3.3 threshold.
_DF_14_3_S1_PASSING_FLOOR = 4
_PASSING_BLOCKS_COUNT = _ELIGIBLE_COUNT - len(_KNOWN_BROKEN_BLOCKS)
assert _PASSING_BLOCKS_COUNT >= _DF_14_3_S1_PASSING_FLOOR, (
    f"DF-14.3-S1 passing-floor regression: {_PASSING_BLOCKS_COUNT} "
    f"dryrun-eligible blocks are PASSABLE in CI ({_ELIGIBLE_COUNT} "
    f"eligible - {len(_KNOWN_BROKEN_BLOCKS)} known-broken-DF-14.3-S1), "
    f"below the DF-14.3-S1 passing-floor ≥ {_DF_14_3_S1_PASSING_FLOOR}. "
    "Either restore an eligible recipe OR fix a known-broken recipe + "
    "remove it from _KNOWN_BROKEN_BLOCKS OR re-check the count drift. "
    "(NB: separate from AC-14.3.3 which measures ≥6 ELIGIBLE blocks; "
    "8 eligible at HEAD ≥ 6 — AC-14.3.3 unamended.)"
)


def _robot_module_available() -> bool:
    """Return True iff `robot` module can be imported in the current `sys.executable`.

    Honest preflight per Story 14.3 Codex MED-1: `sys.executable -m robot`
    does NOT raise `FileNotFoundError` when robot is absent — it exits 1
    with `No module named robot` on stderr. Without this preflight a missing
    robot install would fail the suite, not skip it (contradicting
    AC-14.3.1 D-4).
    """
    return importlib.util.find_spec("robot") is not None


def _run_robot_dryrun(suite_text: str, tmp_path: Path, suite_name: str) -> subprocess.CompletedProcess[str]:
    """Write ``suite_text`` to ``tmp_path / suite_name`` and run ``robot --dryrun``."""
    suite_path = tmp_path / suite_name
    suite_path.write_text(suite_text, encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "robot",
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


@pytest.mark.parametrize(
    "block",
    _ALL_BLOCKS,
    ids=[b.test_id for b in _ALL_BLOCKS],
)
def test_recipe_block_dryruns(block: FencedRobotBlock, tmp_path: Path) -> None:
    """For each fenced robotframework block: dryrun if eligible, else skip with reason."""
    cls = classify_block(block)
    if cls == "settings_only":
        pytest.skip(
            f"{block.test_id}: settings-only fragment (configuration example; "
            "no testable surface to dryrun)."
        )
    if cls == "fragment":
        pytest.skip(
            f"{block.test_id}: documentation fragment (standalone keyword call "
            "without section headers — references variables defined in earlier "
            "recipe blocks)."
        )
    if block.test_id in _KNOWN_BROKEN_BLOCKS:
        pytest.skip(_KNOWN_BROKEN_BLOCKS[block.test_id])
    if not _robot_module_available():  # pragma: no cover — `uv` env always ships robot
        pytest.skip(
            "robot module not importable from current sys.executable; "
            "dryrun cannot run. Expected to be near-impossible under the "
            "project's `uv` env."
        )
    # Dryrun-eligible: wrap if needed + run.
    suite_text = wrap_block_for_dryrun(block)
    suite_name = f"{block.recipe.replace('.md', '')}_block_{block.block_index}.robot"
    result = _run_robot_dryrun(suite_text, tmp_path, suite_name)
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    assert result.returncode == 0, (
        f"{block.test_id} `robot --dryrun` failed (exit={result.returncode}):\n"
        f"--- suite ---\n{suite_text}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}\n"
    )
    assert "No keyword with name" not in combined, (
        f"{block.test_id} dryrun returned 0 but combined output contains "
        "'No keyword with name' — partial green:\n"
        f"--- combined ---\n{combined}\n"
    )


# ---------------------------------------------------------------------------
# Negative regression-guard tests (AC-14.3.2)
# ---------------------------------------------------------------------------


_BROKEN_GET_FROM_DICTIONARY_SUITE = """\
*** Settings ***
Library    AgentEval

*** Test Cases ***
Broken Dictionary Lookup
    ${d}=    Create Dictionary    a=1
    ${v}=    Get From Dictionary    ${d}    a
"""


_BROKEN_NONEXISTENT_KEYWORD_SUITE = """\
*** Settings ***
Library    AgentEval

*** Test Cases ***
Broken Nonexistent Keyword
    Should Never Resolve    arg=1
"""


def test_broken_block_rejected__get_from_dictionary_without_collections(
    tmp_path: Path,
) -> None:
    """Story 13.5 HIGH-B regression-guard: `Get From Dictionary` without `Library Collections`."""
    result = _run_robot_dryrun(
        _BROKEN_GET_FROM_DICTIONARY_SUITE,
        tmp_path,
        "broken_get_from_dictionary.robot",
    )
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    assert result.returncode != 0, (
        "Expected non-zero exit for `Get From Dictionary` without "
        f"`Library Collections`; got 0:\n{combined}"
    )
    assert "No keyword with name 'Get From Dictionary'" in combined, (
        "Expected 'No keyword with name Get From Dictionary' in combined "
        f"output; got:\n{combined}"
    )


def test_broken_block_rejected__nonexistent_keyword(tmp_path: Path) -> None:
    """Wraps a call to `Should Never Resolve` (no such keyword); asserts non-zero exit."""
    result = _run_robot_dryrun(
        _BROKEN_NONEXISTENT_KEYWORD_SUITE,
        tmp_path,
        "broken_nonexistent.robot",
    )
    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    assert result.returncode != 0, (
        f"Expected non-zero exit for nonexistent keyword; got 0:\n{combined}"
    )
    assert "No keyword with name" in combined, (
        f"Expected 'No keyword with name' in combined output; got:\n{combined}"
    )


# ---------------------------------------------------------------------------
# Helper-function unit tests (AC-14.3.5)
# ---------------------------------------------------------------------------


def test_extract_robotframework_blocks__returns_empty_for_md_with_no_blocks() -> None:
    """Recipe #1 (Python-only) has 0 fenced robotframework blocks."""
    blocks = extract_robotframework_blocks(RECIPES_DIR / "01-first-eval-in-five-minutes.md")
    assert blocks == []


def test_extract_robotframework_blocks__counts_match_grep() -> None:
    """Per-recipe block count matches an independent grep over the open-fence form.

    The grep pattern mirrors ``_ROBOT_FENCE_OPEN_RE`` (3+ backticks + ``robotframework``
    + only trailing whitespace) so the independent cross-check stays faithful to the
    parser's open-fence definition — a recipe using a 4-backtick outer fence (to embed
    an inner ```` ```python ```` example) is parsed AND counted by grep, instead of
    falsely failing this parity test (codex MED-1).
    """
    import subprocess as _sp  # local to avoid polluting module scope

    for md_path in sorted(RECIPES_DIR.glob("*.md")):
        blocks = extract_robotframework_blocks(md_path)
        result = _sp.run(
            ["grep", "-cE", "^`{3,}robotframework[[:space:]]*$", str(md_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        # grep -c with no match returns exit 1 + stdout "0\n"; treat as 0.
        grep_count = int(result.stdout.strip() or "0")
        assert len(blocks) == grep_count, (
            f"{md_path.name}: extracted {len(blocks)} blocks, grep counts "
            f"{grep_count}."
        )


def test_known_broken_blocks__matches_actual_failing_set(tmp_path: Path) -> None:
    """codex MED-2: pin BOTH halves of the `_KNOWN_BROKEN_BLOCKS` claim.

    Dryruns every dryrun-eligible block WITHOUT consulting the skip-list, then asserts
    the set that actually fails equals the skip-list. Guards against (a) a fixed recipe
    whose skip entry was never removed (silent under-testing — the passing-floor math
    still looks "correct") and (b) a newly-regressed eligible block hiding behind an
    unchanged floor count.
    """
    if not _robot_module_available():  # pragma: no cover — `uv` env always ships robot
        pytest.skip("robot module not importable; dryrun skip-list audit cannot run.")
    actual_failing: set[str] = set()
    for block in _ELIGIBLE_BLOCKS:
        suite_text = wrap_block_for_dryrun(block)
        suite_name = (
            f"audit_{block.recipe.replace('.md', '')}_block_{block.block_index}.robot"
        )
        result = _run_robot_dryrun(suite_text, tmp_path, suite_name)
        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        if result.returncode != 0 or "No keyword with name" in combined:
            actual_failing.add(block.test_id)
    assert actual_failing == set(_KNOWN_BROKEN_BLOCKS), (
        "Skip-list drift: the set of eligible blocks that actually FAIL `robot "
        "--dryrun` no longer matches `_KNOWN_BROKEN_BLOCKS`.\n"
        "  unlisted-but-failing (NEW regressions to triage): "
        f"{sorted(actual_failing - set(_KNOWN_BROKEN_BLOCKS))}\n"
        "  listed-but-passing (recipe fixed — remove from skip-list): "
        f"{sorted(set(_KNOWN_BROKEN_BLOCKS) - actual_failing)}\n"
    )


def _make_block(raw: str) -> FencedRobotBlock:
    return FencedRobotBlock(recipe="synthetic.md", block_index=0, raw=raw, source_line=1)


def test_classify_block__full_suite_is_dryrun_eligible() -> None:
    raw = "*** Settings ***\nLibrary    AgentEval\n\n*** Test Cases ***\nFoo\n    Log    hi\n"
    assert classify_block(_make_block(raw)) == "dryrun_eligible"


def test_classify_block__test_cases_only_is_dryrun_eligible() -> None:
    raw = "*** Test Cases ***\nFoo\n    Log    hi\n"
    assert classify_block(_make_block(raw)) == "dryrun_eligible"


def test_classify_block__settings_only_is_settings_only() -> None:
    raw = "*** Settings ***\nLibrary    AgentEval    trace_backend=otlp\n"
    assert classify_block(_make_block(raw)) == "settings_only"


def test_classify_block__fragment_is_fragment() -> None:
    raw = "Should Be True    ${pass_at_5} >= 0.8\n"
    assert classify_block(_make_block(raw)) == "fragment"


def test_wrap_block__settings_only_block_raises_value_error() -> None:
    raw = "*** Settings ***\nLibrary    AgentEval\n"
    with pytest.raises(ValueError, match="not dryrun-eligible"):
        wrap_block_for_dryrun(_make_block(raw))


def test_wrap_block__fragment_block_raises_value_error() -> None:
    raw = "Log    hi\n"
    with pytest.raises(ValueError, match="not dryrun-eligible"):
        wrap_block_for_dryrun(_make_block(raw))


def test_wrap_block__test_cases_only_block_prepends_library_import() -> None:
    raw = "*** Test Cases ***\nFoo\n    Log    hi\n"
    wrapped = wrap_block_for_dryrun(_make_block(raw))
    assert wrapped.startswith("*** Settings ***\nLibrary    AgentEval\n\n")
    assert "*** Test Cases ***" in wrapped


def test_wrap_block__full_suite_block_unchanged() -> None:
    raw = "*** Settings ***\nLibrary    AgentEval\n\n*** Test Cases ***\nFoo\n    Log    hi\n"
    assert wrap_block_for_dryrun(_make_block(raw)) == raw


def test_extract_robotframework_blocks__raises_value_error_on_unclosed_block(
    tmp_path: Path,
) -> None:
    """Opus MED-1: unclosed `robotframework` block raises ValueError."""
    md = tmp_path / "broken.md"
    md.write_text(
        "# Bad recipe\n\n"
        "```robotframework\n"
        "*** Test Cases ***\n"
        "Foo\n"
        "    Log    hi\n"
        # No closing fence.
        ,
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unclosed"):
        extract_robotframework_blocks(md)


def test_extract_robotframework_blocks__nested_inner_fence_preserved(
    tmp_path: Path,
) -> None:
    """Codex HIGH-A: an inner ` ```python ` fence inside a robot block MUST NOT truncate the outer block."""
    md = tmp_path / "nested.md"
    md.write_text(
        "# Recipe with nested example\n\n"
        "```robotframework\n"
        "*** Test Cases ***\n"
        "Outer Test\n"
        "    Log    before\n"
        "    # The next inner fence MUST NOT close the outer fence.\n"
        "    ```python\n"
        "    print('this is documentation inside a robot block')\n"
        "    ```\n"
        "    Log    after\n"
        "```\n",
        encoding="utf-8",
    )
    blocks = extract_robotframework_blocks(md)
    assert len(blocks) == 1
    assert "Log    before" in blocks[0].raw
    assert "Log    after" in blocks[0].raw, (
        "Nested ```python fence truncated the outer robot block — Codex HIGH-A regression."
    )


def test_eligible_blocks_meets_ac_14_3_3_unamended_threshold() -> None:
    """AC-14.3.3 (unamended per Opus HIGH-2): ≥6 dryrun-ELIGIBLE blocks at HEAD."""
    assert _ELIGIBLE_COUNT >= 6, (
        f"Recipe corpus has only {_ELIGIBLE_COUNT} dryrun-eligible blocks; "
        "AC-14.3.3 requires ≥6 (measured against eligible, not passing)."
    )


def test_passing_blocks_meets_df_14_3_s1_passing_floor() -> None:
    """DF-14.3-S1 regression guard: ≥4 passable blocks after subtracting known-broken.

    Tracks the retro actions' "≥6 passing" bar; currently at 4 (passing-floor)
    pending DF-14.3-S1 fix-recipe-rot work to raise to ≥6.
    """
    assert _PASSING_BLOCKS_COUNT >= _DF_14_3_S1_PASSING_FLOOR, (
        f"Recipe corpus has only {_PASSING_BLOCKS_COUNT} passable dryrun "
        f"blocks (eligible={_ELIGIBLE_COUNT} - "
        f"known-broken={len(_KNOWN_BROKEN_BLOCKS)}); DF-14.3-S1 passing-floor "
        f"requires ≥{_DF_14_3_S1_PASSING_FLOOR}."
    )
