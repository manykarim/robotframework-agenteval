#!/usr/bin/env python3
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
"""Phase-1.5 carry-over catalog references check (Story 14.2 deliverable).

Scans Git changes (Mode A: `git diff --cached`) OR the whole tree (Mode B:
`--all-tracked`) for inline `DF-X.Y-SZ` references and verifies each has a
matching row in EITHER `docs/phase-1-5-carry-overs.md` (curated execution
catalog; backticked-reference format) OR
`_bmad-output/implementation-artifacts/deferred-work.md` (source-of-record
by source story; bold-row-prefix format). Fail-loud (exit 1) if any reference
lacks a row in BOTH catalogs.

Honest framing on the row-detection regex: `catalog_rows()` matches ANY
backticked or bold-prefixed occurrence of a DF ref in the catalog file. It
does NOT verify that the occurrence is actually the leading-token of a
markdown table-row / list-item (i.e., the canonical "row" the gate's name
suggests). A ref merely name-dropped in backticks inside another row's
narrative would satisfy the gate without its OWN row existing. The looseness
is documented + accepted: tightening to `^\\s*[|\\-]`-anchored is a future
refinement (per Story 14.2 Opus MED-1 triage).

Closes 3 retro action items (3 epics carryover chain):
- Epic 11 retro Action #2 (2026-05-27, original).
- Epic 12 retro Action #6 (2026-06-01, carried).
- Epic 13 retro Action #7 (2026-06-03, carried again).

Used by:
- `.pre-commit-config.yaml` `catalog-references` hook (Mode A; runs on every
  local commit).
- `.github/workflows/ci.yml` `Catalog references check (Phase-1.5)` step (Mode B;
  defense-in-depth — catches `--no-verify` bypass per Story 1a.5 precedent).

Past-incident evidence (per `feedback_honest_framing`):
- Story 11.2 + 11.3 (per Epic 11 retro L62 + L119-121 + L152): inline
  `DF-X-SY` references were added during dev-time writeup that landed AFTER
  the pre-create catalog gate ran; the cross-LLM reviewers caught the gap at
  review-time + a post-review catalog row was added each time
  (`DF-11.2-S3` in `copilot_cli.py:198` + `DF-11.3-S1` in 3 adapter files +
  stability-surface). The commit-time gate this script ships would have
  blocked both at staging.

Regex (D-2 in-flight spec amendment from epic L2279 shorthand `DF-\\d+\\.\\d+-S\\d+`):
the actual catalog corpus includes Epic-1b's alphanumeric story numbering
(`DF-1b.4-S1` etc.) — the wider `DF-[0-9a-z]+\\.[0-9a-z]+-S[0-9]+` regex is
required to cover Epic 1b. The narrow regex would silently skip those
references, producing a fake-green gate (per `feedback_codex_probe_fitness`:
re-derive regex against actual catalog data, not against epic prose
shorthand).

Self-exclusion: the script SKIPS `docs/phase-1-5-carry-overs.md` +
`_bmad-output/implementation-artifacts/deferred-work.md` as input sources
(both ARE the catalog — references inside them ARE the rows being verified).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DF_REFERENCE_RE = re.compile(r"DF-[0-9a-z]+\.[0-9a-z]+-S[0-9]+")

CATALOG_PATH_DEFAULT = "docs/phase-1-5-carry-overs.md"
SOURCE_OF_RECORD_PATH_DEFAULT = "_bmad-output/implementation-artifacts/deferred-work.md"

SELF_EXCLUDED_FILES = (
    "docs/phase-1-5-carry-overs.md",
    "_bmad-output/implementation-artifacts/deferred-work.md",
)

# Directory-prefix exclusions: workflow infrastructure + audit artifacts
# (cross-LLM review findings, story specs, retros) legitimately discuss
# DF-X.Y-SZ references — those references may or may not be catalogued
# depending on the document's role (e.g., reviewer-proposed candidates are
# not catalogued until ratified). The gate's PRODUCTION target is inline
# references in actual source/test/docs code paths.
EXCLUDED_PATH_PREFIXES = (
    "_bmad/",
    "_bmad-output/",
    "docs/keywords/",  # generated libdoc HTML output
    "CHANGELOG.md",  # release-note historical references
    # This gate's OWN machinery legitimately contains DF-X.Y-SZ literals:
    # the script's docstring uses `DF-1b.4-S1` as the Epic-1b regex example,
    # and the test fixtures use forged refs (`DF-99.99-S99`) that must NEVER
    # be catalogued. Without these two exclusions the gate blocks its own
    # commit (Mode A) and turns CI red (Mode B) the instant Story 14.2 is
    # tracked. Keep SURGICAL (these two paths only) — excluding all of
    # scripts/ or tests/ would reopen a real coverage hole.
    "scripts/check-catalog-references.py",
    "tests/unit/scripts/",
)

SCANNED_EXTENSIONS = (".py", ".md", ".yaml", ".yml", ".toml", ".robot")


def extract_references_from_text(text: str) -> set[str]:
    """Return the set of unique `DF-X.Y-SZ` references found in `text`."""
    return set(DF_REFERENCE_RE.findall(text))


def catalog_rows(catalog_path: Path) -> set[str]:
    """Return the set of `DF-X.Y-SZ` references that have a row in the catalog.

    Two catalog formats are recognized:

    1. `docs/phase-1-5-carry-overs.md` (curated execution catalog) uses
       backticked references inside table rows: `` (`DF-X.Y-SZ`) ``.
    2. `_bmad-output/implementation-artifacts/deferred-work.md`
       (source-of-record by source story) uses bold references at the
       row prefix: `- **DF-X.Y-SZ (...)** — ...`.

    Either format counts as a "catalog row" — operators record carry-overs
    in EITHER file depending on whether it's higher-priority (curated) or
    lower-priority (source-of-record).
    """
    if not catalog_path.exists():
        return set()
    text = catalog_path.read_text(encoding="utf-8")
    refs: set[str] = set()
    backticked_re = re.compile(r"`(DF-[0-9a-z]+\.[0-9a-z]+-S[0-9]+)`")
    refs.update(backticked_re.findall(text))
    bold_row_re = re.compile(r"\*\*(DF-[0-9a-z]+\.[0-9a-z]+-S[0-9]+)\b")
    refs.update(bold_row_re.findall(text))
    return refs


def all_catalog_rows(catalog_paths: list[Path]) -> set[str]:
    """Union the catalog rows across all configured catalog files."""
    refs: set[str] = set()
    for p in catalog_paths:
        refs.update(catalog_rows(p))
    return refs


def is_self_excluded(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if any(normalized.endswith(excluded) for excluded in SELF_EXCLUDED_FILES):
        return True
    return any(normalized.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES)


class GitInvocationError(RuntimeError):
    """Raised when a `git` invocation fails (non-git working dir, broken repo, etc.).

    Distinct from "nothing to scan" — a failed git call MUST exit non-zero
    instead of fake-greening the gate on a misconfigured working directory.
    Per Story 14.2 Codex MED-1.
    """


def staged_diff_lines() -> list[tuple[str, int, str]]:
    """Return added-line triples (filepath, line_number_in_new, line_text) from `git diff --cached`.

    Skips `+++` file-header lines and the SELF_EXCLUDED catalog files themselves.
    Returns one entry per added/modified line (the `+`-prefixed lines in the diff).

    Raises `GitInvocationError` if the git call itself fails (non-git working
    dir, broken repo). Empty staged set is `[]`, NOT an error.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--unified=0"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GitInvocationError(
            f"`git diff --cached --unified=0` exited {result.returncode}: "
            f"{result.stderr.strip() or '(no stderr)'}"
        )
    return _parse_unified_diff(result.stdout)


def _parse_unified_diff(diff_text: str) -> list[tuple[str, int, str]]:
    """Parse a unified-diff and return (file, line_in_new_file, line_text) for each added line."""
    out: list[tuple[str, int, str]] = []
    current_file: str | None = None
    current_lineno: int = 0
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            # +++ b/path/to/file  → strip the b/ prefix.
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            current_file = path if path != "/dev/null" else None
            continue
        if line.startswith("--- "):
            continue
        if line.startswith("@@"):
            m = hunk_re.match(line)
            if m and current_file is not None:
                current_lineno = int(m.group(1))
            continue
        # Non-content markers (per Story 14.2 Opus MED-2): `\ No newline at
        # end of file`, `diff --git ...`, `index ...`, `similarity index ...`,
        # `rename from/to ...`, `new file mode ...`, `deleted file mode ...`.
        # These appear inside hunks (the `\ ` marker) or as file-header
        # metadata. Without explicit skip, the catch-all `elif not
        # line.startswith("-")` increments `current_lineno` against them,
        # skewing reported line numbers of subsequent added refs.
        _non_content_prefixes = (
            "\\ ",
            "diff ",
            "index ",
            "similarity ",
            "rename ",
            "new file ",
            "deleted file ",
            "old mode ",
            "new mode ",
        )
        if line.startswith(_non_content_prefixes):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            text = line[1:]
            if current_file is not None and not is_self_excluded(current_file):
                out.append((current_file, current_lineno, text))
            current_lineno += 1
        elif not line.startswith("-"):
            # Context line in the new file.
            current_lineno += 1
        # '-' lines exist only in the old file → no new-file line consumed.
    return out


def all_tracked_files() -> list[Path]:
    """Return tracked files matching SCANNED_EXTENSIONS (excluding SELF_EXCLUDED).

    Raises `GitInvocationError` if `git ls-files` itself fails (non-git
    working dir, broken repo). An empty tracked set returns `[]`.
    """
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GitInvocationError(
            f"`git ls-files` exited {result.returncode}: "
            f"{result.stderr.strip() or '(no stderr)'}"
        )
    paths: list[Path] = []
    for entry in result.stdout.splitlines():
        if not entry:
            continue
        if is_self_excluded(entry):
            continue
        p = Path(entry)
        if p.suffix.lower() in SCANNED_EXTENSIONS:
            paths.append(p)
    return paths


def scan_all_tracked() -> list[tuple[str, int, str]]:
    """Return (file, line, text) triples for every `DF-X.Y-SZ` ref across all tracked files."""
    triples: list[tuple[str, int, str]] = []
    for path in all_tracked_files():
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for idx, line in enumerate(fh, start=1):
                    if DF_REFERENCE_RE.search(line):
                        triples.append((str(path), idx, line.rstrip("\n")))
        except OSError:
            continue
    return triples


def find_missing_references(
    triples: list[tuple[str, int, str]],
    catalog_paths: list[Path],
) -> list[tuple[str, str, int, str]]:
    """Return (reference, file, line, excerpt) for each reference whose row is missing.

    A reference can occur multiple times across files; we report each
    (reference, file, line) occurrence so the operator gets full context.
    The reference passes if it has a row in ANY of the configured catalog
    files (curated catalog OR source-of-record).
    """
    cataloged = all_catalog_rows(catalog_paths)
    missing: list[tuple[str, str, int, str]] = []
    for file, lineno, text in triples:
        for ref in extract_references_from_text(text):
            if ref not in cataloged:
                excerpt = text.strip()
                if len(excerpt) > 100:
                    excerpt = excerpt[:97] + "..."
                missing.append((ref, file, lineno, excerpt))
    return missing


def format_error_message(missing: list[tuple[str, str, int, str]]) -> str:
    """Compose the stderr error format per AC-14.2.1 D-5."""
    unique_refs = sorted({m[0] for m in missing})
    n = len(missing)
    out = [
        f"ERROR: pre-commit catalog-gate found {n} inline DF-X.Y-SZ reference(s) "
        "without catalog rows in docs/phase-1-5-carry-overs.md OR "
        "_bmad-output/implementation-artifacts/deferred-work.md:",
    ]
    for ref, file, lineno, excerpt in missing:
        out.append(f'  - {ref} in {file}:{lineno} (excerpt: "{excerpt}")')
    out.append(
        "Fix: add a row to docs/phase-1-5-carry-overs.md OR "
        "_bmad-output/implementation-artifacts/deferred-work.md for each "
        f"missing reference ({', '.join(unique_refs)}), OR remove the "
        "reference from the staged file(s)."
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase-1.5 carry-over catalog references check (Story 14.2).",
    )
    parser.add_argument(
        "--all-tracked",
        action="store_true",
        help=(
            "Scan ALL tracked files (Mode B / CI). Default is Mode A: scan "
            "`git diff --cached` (pre-commit invocation)."
        ),
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        action="append",
        default=None,
        help=(
            "Override the catalog path(s). May be passed multiple times. "
            f"Default: {CATALOG_PATH_DEFAULT} + {SOURCE_OF_RECORD_PATH_DEFAULT} "
            "(both curated execution catalog AND source-of-record). "
            "Use a single --catalog to override BOTH defaults (testable for "
            "unit tests)."
        ),
    )
    args = parser.parse_args(argv)

    catalog_paths: list[Path] = args.catalog or [
        Path(CATALOG_PATH_DEFAULT),
        Path(SOURCE_OF_RECORD_PATH_DEFAULT),
    ]

    try:
        triples = scan_all_tracked() if args.all_tracked else staged_diff_lines()
    except GitInvocationError as e:
        # Distinguish "git failed" from "nothing to scan" per Story 14.2
        # Codex MED-1: a misconfigured CI working directory (or running the
        # script from outside a git repo) must NOT fake-green the gate.
        print(
            f"ERROR: catalog-references check cannot run — {e}\n"
            "Ensure this script runs from inside a git repository.",
            file=sys.stderr,
        )
        return 2
    if not triples:
        return 0

    missing = find_missing_references(triples, catalog_paths)
    if not missing:
        return 0

    print(format_error_message(missing), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
