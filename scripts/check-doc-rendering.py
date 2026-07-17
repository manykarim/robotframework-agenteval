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

"""Documentation-rendering validation (design D3, prepare-v0-1-0-release).

Stdlib-only check that the generated docs render correctly. It asserts, and
exits non-zero naming the offending file/table/link, on any of:

(a) each ``docs/keywords/*.html`` parses and every ``<table>`` embedded in its
    libdoc keyword documentation is well-formed (has a header row, balanced
    rows/cells) and non-empty;
(b) every GitHub-flavored markdown table in ``README.md`` and ``docs/index.md``
    is well-formed (consistent column counts across rows plus a ``|---|---|``
    separator row);
(c) internal doc links resolve: relative links (not http/https/mailto) in
    ``README.md`` and every ``docs/**/*.md`` point to an existing file (a bare
    ``#anchor`` is in-page and skipped);
(d) exactly the five expected libdoc files exist and are non-empty.

Keyword-count correctness stays owned by ``check_doc_keyword_count.py``.
"""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
KEYWORDS_DIR = DOCS / "keywords"

EXPECTED_LIBDOCS = (
    "HooksLibrary",
    "MCPLibrary",
    "SkillsLibrary",
    "SubagentsLibrary",
    "AgentEval",
)


# --------------------------------------------------------------------------- #
# (a) HTML libdoc tables
# --------------------------------------------------------------------------- #


class _TableCollector(HTMLParser):
    """Collect ``<table>`` structures (rows -> per-row cell/th counts)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[dict[str, int]]] = []
        self._stack: list[list[dict[str, int]]] = []
        self._row: dict[str, int] | None = None

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag == "table":
            self._stack.append([])
        elif tag == "tr" and self._stack:
            self._row = {"cells": 0, "th": 0}
            self._stack[-1].append(self._row)
        elif tag in ("td", "th") and self._row is not None:
            self._row["cells"] += 1
            if tag == "th":
                self._row["th"] += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._stack:
            self.tables.append(self._stack.pop())
        elif tag == "tr":
            self._row = None


def _validate_html_string(html: str, where: str, failures: list[str]) -> None:
    """Validate every ``<table>`` inside an HTML documentation fragment."""
    parser = _TableCollector()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:  # pragma: no cover - html.parser is tolerant
        failures.append(f"{where}: HTML failed to parse ({exc}).")
        return

    for idx, rows in enumerate(parser.tables, start=1):
        label = f"{where}: table #{idx}"
        if not rows:
            failures.append(f"{label} is empty (no rows).")
            continue
        if all(r["cells"] == 0 for r in rows):
            failures.append(f"{label} is empty (no cells).")
            continue
        widths = {r["cells"] for r in rows if r["cells"] > 0}
        # A header row is only meaningful for multi-column data tables. RF
        # renders single-column source/example snippets in docstrings as
        # header-less `<table>`s, which are legitimate, so require a <th>
        # header only when the table has more than one column.
        if max(widths) > 1 and not any(r["th"] > 0 for r in rows):
            failures.append(f"{label} has no header row (no <th> cells).")
        if len(widths) > 1:
            failures.append(f"{label} has unbalanced columns across rows (row widths seen: {sorted(widths)}).")


def _iter_doc_html_strings(model: dict[str, object]):
    """Yield every authored HTML documentation string in a libdoc model."""
    if isinstance(model.get("doc"), str):
        yield "library doc", model["doc"]
    for kw in model.get("keywords", []) or []:
        if isinstance(kw, dict) and isinstance(kw.get("doc"), str):
            yield f"keyword {kw.get('name', '?')!r}", kw["doc"]
    for init in model.get("inits", []) or []:
        if isinstance(init, dict) and isinstance(init.get("doc"), str):
            yield "init doc", init["doc"]
    typedocs = model.get("typedocs")
    if isinstance(typedocs, list):
        for td in typedocs:
            if isinstance(td, dict) and isinstance(td.get("doc"), str):
                yield f"typedoc {td.get('name', '?')!r}", td["doc"]


_LIBDOC_MODEL_RE = re.compile(r"libdoc = (\{.*?\})\n</script>", re.DOTALL)


def check_html_tables(failures: list[str]) -> None:
    for name in EXPECTED_LIBDOCS:
        path = KEYWORDS_DIR / f"{name}.html"
        if not path.is_file():
            continue  # existence handled by check_libdoc_files
        text = path.read_text(encoding="utf-8")

        # Whole-file parse smoke: html.parser must consume it without raising.
        try:
            smoke = HTMLParser()
            smoke.feed(text)
            smoke.close()
        except Exception as exc:
            failures.append(f"docs/keywords/{name}.html failed to parse ({exc}).")
            continue

        m = _LIBDOC_MODEL_RE.search(text)
        if not m:
            failures.append(f"docs/keywords/{name}.html: could not locate the embedded `libdoc = {{...}}` model.")
            continue
        try:
            model = json.loads(m.group(1))
        except json.JSONDecodeError as exc:
            failures.append(f"docs/keywords/{name}.html: embedded libdoc JSON is invalid ({exc}).")
            continue
        if not model.get("keywords"):
            failures.append(f"docs/keywords/{name}.html: libdoc model lists no keywords.")
        for label, html in _iter_doc_html_strings(model):
            _validate_html_string(html, f"docs/keywords/{name}.html [{label}]", failures)


# --------------------------------------------------------------------------- #
# (b) GitHub-flavored markdown tables
# --------------------------------------------------------------------------- #

_SEP_CELL_RE = re.compile(r"^:?-{1,}:?$")


def _split_md_row(line: str) -> list[str]:
    """Split a markdown table row into cells, honoring escaped ``\\|`` pipes."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def _is_separator(line: str) -> bool:
    cells = _split_md_row(line)
    return bool(cells) and all(_SEP_CELL_RE.match(c) for c in cells)


def _strip_code_fences(lines: list[str]) -> list[bool]:
    """Return a mask; True where the line is inside a fenced code block."""
    in_fence = False
    fence = ""
    mask: list[bool] = []
    for line in lines:
        stripped = line.lstrip()
        m = re.match(r"^(```+|~~~+)", stripped)
        if m and not in_fence:
            in_fence = True
            fence = m.group(1)[0]
            mask.append(True)
            continue
        if m and in_fence and stripped.startswith(fence * 3):
            in_fence = False
            mask.append(True)
            continue
        mask.append(in_fence)
    return mask


def check_markdown_tables(failures: list[str]) -> None:
    for rel in ("README.md", "docs/index.md"):
        path = REPO_ROOT / rel
        lines = path.read_text(encoding="utf-8").splitlines()
        in_code = _strip_code_fences(lines)
        i = 0
        n = len(lines)
        while i < n:
            if in_code[i] or "|" not in lines[i]:
                i += 1
                continue
            # A table needs a header line followed by a separator line.
            if i + 1 < n and not in_code[i + 1] and _is_separator(lines[i + 1]):
                header_line = i + 1  # line number (1-indexed) of the header
                width = len(_split_md_row(lines[i]))
                sep_width = len(_split_md_row(lines[i + 1]))
                if sep_width != width:
                    failures.append(
                        f"{rel}:{header_line}: table separator has {sep_width} columns but the header has {width}."
                    )
                # Consume body rows.
                j = i + 2
                while j < n and not in_code[j] and "|" in lines[j] and lines[j].strip():
                    row_width = len(_split_md_row(lines[j]))
                    if row_width != width:
                        failures.append(f"{rel}:{j + 1}: table row has {row_width} columns but the header has {width}.")
                    j += 1
                i = j
            else:
                i += 1


# --------------------------------------------------------------------------- #
# (c) internal doc links
# --------------------------------------------------------------------------- #

_LINK_RE = re.compile(r"(?<!\\)!?\[(?:[^\]]*)\]\(\s*([^)]*?)\s*\)")


def _link_targets(text: str):
    """Yield raw link targets from inline markdown links/images."""
    in_code = _strip_code_fences(text.splitlines())
    for lineno, line in enumerate(text.splitlines()):
        if in_code[lineno]:
            continue
        for m in _LINK_RE.finditer(line):
            yield lineno + 1, m.group(1)


def _is_external(target: str) -> bool:
    return bool(re.match(r"^(https?:|mailto:|tel:|ftp:|//)", target, re.IGNORECASE))


def check_internal_links(failures: list[str]) -> None:
    md_files = [REPO_ROOT / "README.md"]
    md_files.extend(sorted(DOCS.rglob("*.md")))
    for path in md_files:
        rel = path.relative_to(REPO_ROOT)
        text = path.read_text(encoding="utf-8")
        for lineno, raw in _link_targets(text):
            target = raw.strip()
            # Strip an optional title:  path "Title"  or  path 'Title'
            target = re.split(r"\s+", target, maxsplit=1)[0]
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            if not target or _is_external(target):
                continue
            if target.startswith("#"):
                continue  # in-page anchor
            # Drop query/anchor fragments.
            fragless = target.split("#", 1)[0].split("?", 1)[0]
            if not fragless:
                continue
            resolved = (path.parent / fragless).resolve()
            if not resolved.exists():
                failures.append(f"{rel}:{lineno}: internal link target does not exist: {target!r} -> {fragless}")


# --------------------------------------------------------------------------- #
# (d) expected libdoc files
# --------------------------------------------------------------------------- #


def check_libdoc_files(failures: list[str]) -> None:
    if not KEYWORDS_DIR.is_dir():
        failures.append("docs/keywords/ directory is missing.")
        return
    present = {p.stem for p in KEYWORDS_DIR.glob("*.html")}
    expected = set(EXPECTED_LIBDOCS)
    for name in EXPECTED_LIBDOCS:
        path = KEYWORDS_DIR / f"{name}.html"
        if not path.is_file():
            failures.append(f"docs/keywords/{name}.html is missing.")
        elif path.stat().st_size == 0:
            failures.append(f"docs/keywords/{name}.html is empty.")
    for extra in sorted(present - expected):
        failures.append(
            f"docs/keywords/{extra}.html is not an expected libdoc file "
            "(only the five surface libraries should have libdoc)."
        )


# --------------------------------------------------------------------------- #


def main() -> int:
    failures: list[str] = []
    check_libdoc_files(failures)
    check_html_tables(failures)
    check_markdown_tables(failures)
    check_internal_links(failures)

    if failures:
        print("::error::Documentation-rendering check failed:")
        for f in failures:
            print(f"  - {f}")
        print(f"\n{len(failures)} problem(s) found. Fix the docs and re-run.")
        return 1

    print(
        "PASS: documentation renders correctly — "
        f"{len(EXPECTED_LIBDOCS)} libdoc HTML files parse with well-formed "
        "keyword tables, README/docs/index.md markdown tables are balanced, "
        "and all internal doc links resolve."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
