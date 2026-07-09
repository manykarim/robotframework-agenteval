"""Unit tests for `scripts/check-catalog-references.py` (Story 14.2 deliverable).

Covers AC-14.2.4 cases: Mode A (staged diff via monkeypatch), Mode B
(--all-tracked via --catalog override), edge cases (Epic-1b alphanumeric
story numbering DF-1b.4-S1; catalog-self-exclusion).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-catalog-references.py"


def _load_script_module() -> Any:
    """Load the dashed-filename script as a Python module for direct testing.

    `scripts/check-catalog-references.py` cannot be imported directly because
    its filename uses dashes (path-style invocation per Story 1a.5
    `check-license-headers.py` precedent). Load it via importlib.util so the
    tests exercise the actual script code, not a copy.
    """
    spec = importlib.util.spec_from_file_location("_check_catalog_references", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_check_catalog_references"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script_module() -> Any:
    return _load_script_module()


@pytest.fixture
def tmp_catalog_with_rows(tmp_path: Path) -> Path:
    """A tmp catalog file with backticked rows for `DF-7.3-S1` + `DF-1b.4-S1`."""
    catalog = tmp_path / "phase-1-5-carry-overs.md"
    catalog.write_text(
        "# Phase-1.5 Carry-Overs Catalog\n\n"
        "| **C59** | Epic 7: default-predicate (`DF-7.3-S1`). | ... |\n"
        "| **C24** | Epic 1b: lifecycle (`DF-1b.4-S1`). | ... |\n",
        encoding="utf-8",
    )
    return catalog


@pytest.fixture
def tmp_empty_catalog(tmp_path: Path) -> Path:
    """A tmp catalog file with NO backticked DF rows."""
    catalog = tmp_path / "phase-1-5-carry-overs.md"
    catalog.write_text("# Phase-1.5 Carry-Overs Catalog\n\n(no rows yet)\n", encoding="utf-8")
    return catalog


def test_regex_extracts_standard_df_reference(script_module: Any) -> None:
    """D-2: standard `DF-X.Y-SZ` (numeric story prefix) extracted."""
    refs = script_module.extract_references_from_text("See DF-7.3-S1 for the carry-over.")
    assert refs == {"DF-7.3-S1"}


def test_regex_extracts_epic_1b_alphanumeric_story_prefix(script_module: Any) -> None:
    """D-2 edge case: `DF-1b.4-S1` (Epic-1b alphanumeric story numbering) extracted.

    This was the original spec-text shorthand drift caught at create-story-time.
    The narrow `\\d+\\.\\d+` regex would silently miss this — the wider
    `[0-9a-z]+\\.[0-9a-z]+` regex covers it.
    """
    refs = script_module.extract_references_from_text("Per `DF-1b.4-S1` (Epic 1b carry-over).")
    assert refs == {"DF-1b.4-S1"}


def test_regex_extracts_multiple_references_per_line(script_module: Any) -> None:
    refs = script_module.extract_references_from_text("Closes DF-4.4-S1 + DF-13.5-S1 + DF-1b.4-S1 in one line.")
    assert refs == {"DF-4.4-S1", "DF-13.5-S1", "DF-1b.4-S1"}


def test_catalog_rows_only_match_backticked_references(script_module: Any, tmp_catalog_with_rows: Path) -> None:
    """Verification regex requires backtick wrapping — prose mentions don't count."""
    cataloged = script_module.catalog_rows(tmp_catalog_with_rows)
    assert "DF-7.3-S1" in cataloged
    assert "DF-1b.4-S1" in cataloged


def test_catalog_rows_skip_unbackticked_unbolded_mentions(script_module: Any, tmp_path: Path) -> None:
    """A reference without backticks AND without bold-row prefix does NOT count.

    Prose mentions like "as discussed for DF-99.99-S99 above" must not
    satisfy the gate; only actual row entries (backticked OR bold-row) count.
    """
    catalog = tmp_path / "phase-1-5-carry-overs.md"
    catalog.write_text(
        "Some prose mentions DF-99.99-S99 without backticks or bold.\n",
        encoding="utf-8",
    )
    cataloged = script_module.catalog_rows(catalog)
    assert cataloged == set()


def test_catalog_rows_bold_row_format_deferred_work(script_module: Any, tmp_path: Path) -> None:
    """deferred-work.md uses bold-row prefix `**DF-X.Y-SZ (...)**` format."""
    catalog = tmp_path / "deferred-work.md"
    catalog.write_text(
        "## Source story 4.1\n\n"
        "- **DF-4.1-S2 (Generic adapter MCP-tool-surface integration)** — "
        "Phase-1 Generic adapter `run()` accepts `mcp_servers=` kwarg.\n"
        "- **DF-4.2-S1 (mcp_servers temp .mcp.json)** — Phase-1 adapter.\n",
        encoding="utf-8",
    )
    cataloged = script_module.catalog_rows(catalog)
    assert "DF-4.1-S2" in cataloged
    assert "DF-4.2-S1" in cataloged


def test_all_catalog_rows_unions_both_formats(script_module: Any, tmp_path: Path) -> None:
    """all_catalog_rows unions backticked + bold-row across both catalog files."""
    backticked = tmp_path / "phase-1-5-carry-overs.md"
    backticked.write_text("| **C59** | (`DF-7.3-S1`) | ... |\n", encoding="utf-8")
    bold_rows = tmp_path / "deferred-work.md"
    bold_rows.write_text("- **DF-4.1-S2 (Generic adapter)** — ...\n", encoding="utf-8")
    cataloged = script_module.all_catalog_rows([backticked, bold_rows])
    assert cataloged == {"DF-7.3-S1", "DF-4.1-S2"}


def test_find_missing_returns_empty_when_all_cataloged(script_module: Any, tmp_catalog_with_rows: Path) -> None:
    """Positive: triples reference DF-7.3-S1, catalog has the row → no missing."""
    triples = [
        ("src/foo.py", 42, "# DF-7.3-S1 enforcement deferred"),
    ]
    assert script_module.find_missing_references(triples, [tmp_catalog_with_rows]) == []


def test_find_missing_returns_uncataloged_references(script_module: Any, tmp_empty_catalog: Path) -> None:
    """Mode B fixture: catalog empty, references present → missing list populated."""
    triples = [
        ("src/bar.py", 7, "# DF-99.99-S99 not catalogued"),
        ("docs/recipe.md", 13, "Per DF-1b.4-S1 lifecycle."),
    ]
    missing = script_module.find_missing_references(triples, [tmp_empty_catalog])
    refs = sorted({m[0] for m in missing})
    assert refs == ["DF-1b.4-S1", "DF-99.99-S99"]


def test_format_error_message_lists_missing_refs(script_module: Any) -> None:
    missing = [
        ("DF-99.99-S99", "src/foo.py", 42, "# DF-99.99-S99 carry-over"),
    ]
    msg = script_module.format_error_message(missing)
    assert "DF-99.99-S99" in msg
    assert "src/foo.py:42" in msg
    assert "docs/phase-1-5-carry-overs.md" in msg
    assert "deferred-work.md" in msg


def test_main_mode_b_with_catalog_override_exits_1_on_missing(
    script_module: Any, tmp_empty_catalog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Forged-commit-style: Mode B against empty catalog with a missing ref → exit 1.

    We monkeypatch `scan_all_tracked` to return a hand-crafted triple list so
    the test doesn't depend on the actual repo state.
    """
    monkeypatch.setattr(
        script_module,
        "scan_all_tracked",
        lambda: [("src/forged.py", 1, "# DF-99.99-S99 forged reference")],
    )
    exit_code = script_module.main(["--all-tracked", "--catalog", str(tmp_empty_catalog)])
    assert exit_code == 1


def test_main_mode_b_exits_0_when_no_references(
    script_module: Any, tmp_empty_catalog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No DF references in tree → exit 0 + empty stderr."""
    monkeypatch.setattr(script_module, "scan_all_tracked", list)
    assert script_module.main(["--all-tracked", "--catalog", str(tmp_empty_catalog)]) == 0


def test_main_mode_a_exits_0_when_no_staged_diff(
    script_module: Any, tmp_empty_catalog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mode A with no staged changes → exit 0."""
    monkeypatch.setattr(script_module, "staged_diff_lines", list)
    assert script_module.main(["--catalog", str(tmp_empty_catalog)]) == 0


def test_main_mode_a_blocks_forged_inline_reference(
    script_module: Any, tmp_empty_catalog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mode A with a forged staged inline DF reference + empty catalog → exit 1.

    Models the forged-commit scenario AC-14.2.4 promises (a commit adds
    `DF-99.99-S99` to a source file without adding a catalog row).
    """
    monkeypatch.setattr(
        script_module,
        "staged_diff_lines",
        lambda: [("src/AgentEval/forged.py", 1, "# DF-99.99-S99 forged")],
    )
    assert script_module.main(["--catalog", str(tmp_empty_catalog)]) == 1


def test_is_self_excluded_catalog_files(script_module: Any) -> None:
    """Edge: the catalog file itself + the deferred-work file are self-excluded."""
    assert script_module.is_self_excluded("docs/phase-1-5-carry-overs.md")
    assert script_module.is_self_excluded("_bmad-output/implementation-artifacts/deferred-work.md")
    assert not script_module.is_self_excluded("src/AgentEval/foo.py")


def test_parse_unified_diff_skips_self_excluded_files(script_module: Any) -> None:
    """Edge: a staged diff that ADDS a `DF-99.99-S99` row to the catalog itself

    must NOT trigger the gate on that row — the row IS being added to the
    catalog in the same commit (which is exactly what the operator should do).
    """
    diff_text = (
        "diff --git a/docs/phase-1-5-carry-overs.md b/docs/phase-1-5-carry-overs.md\n"
        "--- a/docs/phase-1-5-carry-overs.md\n"
        "+++ b/docs/phase-1-5-carry-overs.md\n"
        "@@ -50,0 +51,1 @@\n"
        "+| **C100** | New entry (`DF-99.99-S99`). | ... |\n"
    )
    triples = script_module._parse_unified_diff(diff_text)
    assert triples == []


def test_parse_unified_diff_captures_added_lines_outside_catalog(
    script_module: Any,
) -> None:
    """Positive: an added line in `src/AgentEval/foo.py` IS captured."""
    diff_text = (
        "diff --git a/src/AgentEval/foo.py b/src/AgentEval/foo.py\n"
        "--- a/src/AgentEval/foo.py\n"
        "+++ b/src/AgentEval/foo.py\n"
        "@@ -10,0 +11,1 @@\n"
        "+    # Per DF-99.99-S99 placeholder.\n"
    )
    triples = script_module._parse_unified_diff(diff_text)
    assert len(triples) == 1
    file, lineno, text = triples[0]
    assert file == "src/AgentEval/foo.py"
    assert lineno == 11
    assert "DF-99.99-S99" in text


def test_parse_unified_diff_two_hunks_one_file(script_module: Any) -> None:
    """Codex MED-2: multi-hunk per file — line numbers must track per hunk."""
    diff_text = (
        "diff --git a/src/foo.py b/src/foo.py\n"
        "--- a/src/foo.py\n"
        "+++ b/src/foo.py\n"
        "@@ -10,0 +11,1 @@\n"
        "+    # Per DF-99.99-S99 first hunk.\n"
        "@@ -50,0 +99,1 @@\n"
        "+    # Per DF-99.99-S99 second hunk.\n"
    )
    triples = script_module._parse_unified_diff(diff_text)
    assert len(triples) == 2
    files = [t[0] for t in triples]
    linenos = [t[1] for t in triples]
    assert files == ["src/foo.py", "src/foo.py"]
    assert linenos == [11, 99]


def test_parse_unified_diff_two_files_one_diff(script_module: Any) -> None:
    """Codex MED-2: multi-file per diff — current_file must switch correctly."""
    diff_text = (
        "diff --git a/src/foo.py b/src/foo.py\n"
        "--- a/src/foo.py\n"
        "+++ b/src/foo.py\n"
        "@@ -10,0 +11,1 @@\n"
        "+    # DF-99.99-S99 in foo.py\n"
        "diff --git a/src/bar.py b/src/bar.py\n"
        "--- a/src/bar.py\n"
        "+++ b/src/bar.py\n"
        "@@ -7,0 +8,1 @@\n"
        "+    # DF-99.99-S99 in bar.py\n"
    )
    triples = script_module._parse_unified_diff(diff_text)
    assert len(triples) == 2
    assert triples[0][0] == "src/foo.py"
    assert triples[0][1] == 11
    assert triples[1][0] == "src/bar.py"
    assert triples[1][1] == 8


def test_parse_unified_diff_no_newline_marker_doesnt_skew_lineno(
    script_module: Any,
) -> None:
    """Opus MED-2: `\\ No newline at end of file` MUST NOT increment lineno."""
    diff_text = (
        "diff --git a/src/foo.py b/src/foo.py\n"
        "--- a/src/foo.py\n"
        "+++ b/src/foo.py\n"
        "@@ -10,0 +11,2 @@\n"
        "+    # DF-99.99-S99 at line 11\n"
        "\\ No newline at end of file\n"
        "+    # DF-99.99-S99 at line 12\n"
    )
    triples = script_module._parse_unified_diff(diff_text)
    assert len(triples) == 2
    assert triples[0][1] == 11
    assert triples[1][1] == 12, f"Expected line 12 but got {triples[1][1]} — backslash marker skewed lineno"


def test_main_returns_2_when_git_fails(
    script_module: Any, tmp_empty_catalog: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex MED-1: git failure must exit non-zero, not fake-green to 0."""

    def raise_git_error() -> list[tuple[str, int, str]]:
        raise script_module.GitInvocationError("not a git repository")

    monkeypatch.setattr(script_module, "scan_all_tracked", raise_git_error)
    exit_code = script_module.main(["--all-tracked", "--catalog", str(tmp_empty_catalog)])
    assert exit_code == 2


def test_staged_diff_lines_raises_git_invocation_error_on_git_failure(
    script_module: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mode A: git diff failure surfaces as GitInvocationError, not fake-green."""

    class _Result:
        returncode = 128
        stdout = ""
        stderr = "fatal: not a git repository"

    monkeypatch.setattr(script_module.subprocess, "run", lambda *a, **kw: _Result())
    with pytest.raises(script_module.GitInvocationError) as excinfo:
        script_module.staged_diff_lines()
    assert "not a git repository" in str(excinfo.value)


def test_main_passes_against_current_repo_state(script_module: Any) -> None:
    """Sanity: the live repo's `--all-tracked` mode passes against the live catalog.

    This is the AC-14.2.7 close-condition check: at HEAD, no stale
    `DF-X.Y-SZ` reference should be missing from the catalog. If this fails,
    the script has surfaced a real catalog-gate violation in HEAD that
    needs fixing BEFORE Story 14.2 closes.
    """
    exit_code = script_module.main(["--all-tracked"])
    assert exit_code == 0, (
        "Live repo has unreferenced DF-X.Y-SZ tags missing from the catalog. "
        "The script surfaced a real catalog-gate violation. Fix by adding "
        "rows OR removing references."
    )
