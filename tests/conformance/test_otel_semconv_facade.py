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

"""NFR-COMPAT-06 facade-enforcer (Story 5.1).

Greps `src/AgentEval/` for hardcoded `"gen_ai."` or `"agenteval."` string
literals OUTSIDE `src/AgentEval/telemetry/semconv.py`. Any match indicates
a producer bypassed the facade — which makes future attribute-name churn a
grep-and-replace exercise across the codebase instead of a single-file
update. Per NFR-COMPAT-06.

Pre-existing exemptions (intentional callers that pre-date Story 5.1):
- `_kernel/trace_store.py` references `"agenteval.test_id"` in its
  Story 1b.2 docstring + projection accessor logic; that file is the
  load-bearing consumer of the Resource attribute and predates the
  facade. Listed in `_EXEMPT_FILES`.
- `_kernel/redaction.py` references `"agenteval.tool.args"` etc in
  `_SENSITIVE_ATTRIBUTE_KEYS`; similarly load-bearing + predates.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "AgentEval"

# Files in src/AgentEval/ that may legitimately reference the literal keys
# because they predate the facade or implement the lookup machinery itself.
_EXEMPT_FILES = {
    SRC_ROOT / "telemetry" / "semconv.py",
    SRC_ROOT / "_kernel" / "trace_store.py",
    SRC_ROOT / "_kernel" / "redaction.py",
}

# Skip lines containing this marker; the conformance test's own docstring
# mentions the literal keys when documenting exemptions, which would
# otherwise self-trigger the grep.
_SKIP_LINE_MARKER = "FACADE_GREP_SKIP"

# Match the OTel/agenteval SPAN ATTRIBUTE KEY shapes documented at
# architecture L1001-1010 — NOT entry-point group names like
# `agenteval.providers` / `agenteval.coding_agents` / `agenteval.sandboxes`
# (those are separate concerns governed by ADR-013, not the OTel facade).
#
# Story 5.1 code-review 3-way fix 2026-05-20 (Codex LOW + Blind MED-5 +
# Edge-cases LOW-1): pre-edit patterns required specific sub-namespaces
# (`gen_ai.(system|request|response|usage|tool).*` + `agenteval.(test_id|tool.|tier).*`).
# This created false negatives: future OTel additions (`gen_ai.client.*`,
# restored `gen_ai.completion.*`) + alternate `agenteval.*` shapes like
# `agenteval.tool_total_count` (FR55 cohort heatmap) would slip the guard.
# Now matches the broad `gen_ai.<anything>` + `agenteval.<anything>` shape;
# entry-point group names are excluded via `_ENTRY_POINT_GROUPS` exemption.
_GEN_AI_RE = re.compile(r'"gen_ai\.[a-z_]+(?:[._][a-z_]+)*"')
_AGENTEVAL_RE = re.compile(r'"agenteval\.[a-z_]+(?:[._][a-z_]+)*"')

# Entry-point group names governed by ADR-013, NOT the OTel facade.
# Skip lines that ONLY mention these names + nothing else flagged.
_ENTRY_POINT_GROUPS = frozenset(
    {
        "agenteval.providers",
        "agenteval.coding_agents",
        "agenteval.sandboxes",
        "agenteval.judges",
    }
)


def _line_is_entry_point_only(line: str) -> bool:
    """Return True if line's only `agenteval.*` reference is an entry-point group."""
    matches = _AGENTEVAL_RE.findall(line)
    if not matches:
        return False
    # Strip surrounding quotes for membership check.
    stripped = [m.strip('"') for m in matches]
    return all(s in _ENTRY_POINT_GROUPS for s in stripped)


def _scan_for_facade_bypass() -> list[tuple[Path, int, str]]:
    """Return list of (file, line_number, line_content) for any facade bypass."""
    offenders: list[tuple[Path, int, str]] = []
    for py_file in SRC_ROOT.rglob("*.py"):
        if py_file in _EXEMPT_FILES:
            continue
        text = py_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _SKIP_LINE_MARKER in line:
                continue
            gen_ai_hit = _GEN_AI_RE.search(line)
            agenteval_hit = _AGENTEVAL_RE.search(line)
            if not gen_ai_hit and not agenteval_hit:
                continue
            # Entry-point group names are governed by ADR-013, not the
            # OTel facade — exempt if the only `agenteval.*` literal is an
            # entry-point group name.
            if agenteval_hit and not gen_ai_hit and _line_is_entry_point_only(line):
                continue
            offenders.append((py_file.relative_to(REPO_ROOT), lineno, line.strip()))
    return offenders


def test_no_hardcoded_gen_ai_or_agenteval_attribute_keys_outside_semconv() -> None:
    """NFR-COMPAT-06: all `gen_ai.*` + `agenteval.*` attribute keys must route through
    `src/AgentEval/telemetry/semconv.py`. Hardcoded literals elsewhere defeat the
    single-file-churn-absorption purpose of the facade.
    """
    offenders = _scan_for_facade_bypass()
    if offenders:
        msg = "\n".join(f"  {p}:{ln}: {content}" for p, ln, content in offenders)
        raise AssertionError(
            f"NFR-COMPAT-06 violation: {len(offenders)} hardcoded "
            "`gen_ai.*` or `agenteval.*` attribute keys outside "
            "`src/AgentEval/telemetry/semconv.py`. Import from semconv "
            f"instead.\n\n{msg}"
        )
