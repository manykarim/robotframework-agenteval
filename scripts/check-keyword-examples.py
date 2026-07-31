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

"""Keyword-example phantom-reference gate.

Derives the libdoc documentation for every shipped ``AgentEval`` library,
extracts each keyword's runnable usage example (the Robot Framework
``| ... |`` pipe-table lines), and verifies that every namespaced keyword the
example invokes resolves to a keyword a shipped Library actually exports.

A phantom reference - an example that names, say, ``Stat.Run N Times`` when no
shipped Library exports it - fails the gate, exits non-zero, and names both the
owning keyword and the unresolvable reference. This is the doc-drift analogue of
``check_doc_keyword_count.py``: a broken example never reaches a user.

The check is namespace-scoped. Only references carrying a shipped-library
prefix (``Hook.``, ``MCP.``, ``Skill.``, ``Subagent.``, ``Metric.``, ``Stat.``)
are resolved; bare BuiltIn keywords such as ``Should Be True`` are intentionally
left alone, since they are not part of this project's surface.

Stdlib + Robot Framework's own ``libdoc`` only - no third-party dependency.
"""

from __future__ import annotations

import re
import sys

from robot.libdocpkg import LibraryDocumentation

# Every shipped library whose keyword docs are scanned. ``AgentEval`` is the
# composite (it re-exposes the sub-library keywords under the same baked names);
# the sub-libraries and the metrics/stat surfaces are listed so a standalone
# import path is covered too. Keyword names are unique across the set, so the
# union is the resolvable universe and reports dedupe naturally by name.
SHIPPED_LIBRARIES = (
    "AgentEval",
    "HooksLibrary",
    "MCPLibrary",
    "SkillsLibrary",
    "SubagentsLibrary",
    "MetricsLibrary",
    "StatLibrary",
    "AgentLibrary",
)

# The keyword-name prefixes each shipped Library bakes in (``@keyword(name=
# "Prefix.Multi Word")``). A cell that opens with one of these prefixes is a
# reference this gate must resolve - including prefixes of libraries that ship
# zero keywords today (e.g. ``Metric.``), so a phantom into a not-yet-built
# surface still fails rather than being silently skipped.
NAMESPACE_PREFIXES = frozenset({"Hook", "MCP", "Skill", "Subagent", "Metric", "Stat", "Agent"})

# A pipe-table cell that names a shipped-library keyword, e.g. ``Stat.Run N
# Times`` or ``Skill.Get Activation Decision``. The prefix is captured so it can
# be matched against ``NAMESPACE_PREFIXES``; the whole cell is the reference.
_NAMESPACED_CELL = re.compile(r"^([A-Za-z][\w]*)\.[A-Za-z]")


def derive_keyword_docs() -> dict[str, str]:
    """Return ``{keyword_name: documentation}`` across every shipped library.

    Keyword names are unique across the shipped surface, so re-exposed composite
    keywords collapse onto the same entry (identical docs) - each keyword is
    checked once, by name.
    """
    docs: dict[str, str] = {}
    for lib in SHIPPED_LIBRARIES:
        for kw in LibraryDocumentation(lib).keywords:
            docs[kw.name] = kw.doc
    return docs


def _cells(line: str) -> list[str]:
    """Split one Robot Framework pipe-table line into its cells.

    Cells are separated by a pipe or by two-or-more spaces; a single space is
    part of a keyword name (``Get Activation Decision``), so it never splits.
    """
    body = line.strip().lstrip("|")
    return [cell for cell in re.split(r"\s*\|\s*|\s{2,}", body.strip()) if cell]


def referenced_keywords(doc: str) -> list[str]:
    """Return the namespaced keyword references invoked by a keyword's examples.

    Scans only pipe-table (``| ... |``) lines and keeps cells whose prefix is a
    shipped-library namespace; everything else (variables, values, BuiltIn
    keywords) is ignored.
    """
    refs: list[str] = []
    for line in doc.splitlines():
        if not line.strip().startswith("|"):
            continue
        for cell in _cells(line):
            match = _NAMESPACED_CELL.match(cell)
            if match and match.group(1) in NAMESPACE_PREFIXES:
                refs.append(cell)
    return refs


def check() -> tuple[list[str], int]:
    """Return ``(failures, keywords_scanned)``; failures empty when all resolve."""
    docs = derive_keyword_docs()
    universe = set(docs)
    failures: list[str] = []
    for name in sorted(docs):
        for ref in referenced_keywords(docs[name]):
            if ref not in universe:
                failures.append(f"{name!r}: example references {ref!r}, which no shipped Library exports")
    return failures, len(docs)


def main() -> int:
    """Run the gate; print failures and return a process exit code."""
    failures, scanned = check()
    if failures:
        print("Phantom keyword-example references found:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            "\nFix the example to reference a real shipped keyword (or ship the missing keyword).",
            file=sys.stderr,
        )
        return 1
    print(f"OK: every documented keyword example resolves ({scanned} keywords scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
