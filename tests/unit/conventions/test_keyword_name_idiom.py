"""Conventions test: `@keyword` function names use snake_case + start with a verb.

Story 1b.6 AC-1b.6.5 per `docs/contracts/coding-conventions.md`: every
`@keyword`-decorated function name MUST:
1. Match `^[a-z][a-z0-9_]*$` (snake_case; RF converts to Title Case at
   registration via pythonlibcore).
2. Start with a verb from the `_VERB_ALLOWLIST` constant.

Future stories that need a new verb prefix MUST extend `_VERB_ALLOWLIST`
+ cite the new verb in their story spec (per Story 1b.6 Phase-1 limitations).

End-of-Epic-1b state: zero `@keyword` functions → trivially pass.
"""

from __future__ import annotations

import re

import pytest

from ._walk import find_library_modules, iter_keyword_functions, load_module_from_path

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# Verb allowlist — extend in future stories per Story 1b.6 Phase-1 limitations.
# Each verb is the first `_`-separated token of a snake_case keyword name.
# Growth log:
#   Story 2.1 (2026-05-19): added "should" for `Should Be Valid Frontmatter`
#       (Phase-1 plain @keyword pending Phase-2 ADR-022 AssertionEngine adoption).
#   Story 3.2 (2026-05-19): added "call" for `MCP.Call Tool` per PRD FR9b.
#   Story 6.2 (2026-05-20): added "trajectory" + "tool" + "agent" for the
#       PRD FR23-25-mandated assertion keyword surface (`Trajectory Should Match`,
#       `Tool Call Should Have Occurred`, `Agent Response Should Contain` +
#       `Match Regex` + `Match Schema`). These verbs are domain nouns-as-actions
#       per the BFCL trajectory/tool-call/response evidence-layer framing —
#       the PRD names are load-bearing and can't be coerced into a generic verb.
_VERB_ALLOWLIST: frozenset[str] = frozenset(
    {
        "get",
        "set",
        "run",
        "send",
        "assert",
        "check",
        "validate",
        "compute",
        "list",
        "start",
        "stop",
        "connect",
        "disconnect",
        "inspect",
        "load",
        "save",
        "read",
        "write",
        "parse",
        "wait",
        "should",
        "call",
        # Story 6.2 — PRD FR23-25 assertion library:
        "trajectory",
        "tool",
        "agent",
        # Story 12.2 — Tier-2 judge calibration:
        "calibrate",
    }
)


def test_keyword_names_use_snake_case(capsys: pytest.CaptureFixture[str]) -> None:
    library_modules = find_library_modules()
    if not library_modules:
        print("[CONVENTIONS] no library.py modules yet — no keywords to check")
        return
    violations: list[str] = []
    for path in library_modules:
        module = load_module_from_path(path)
        for name, _func in iter_keyword_functions(module):
            short = name.split(".")[-1]  # strip ClassName. prefix
            if not _SNAKE_CASE_RE.match(short):
                violations.append(f"{path}::{name} (not snake_case)")
    assert not violations, f"@keyword function names not in snake_case per coding-conventions.md: {violations!r}"


def test_keyword_names_start_with_allowlist_verb(capsys: pytest.CaptureFixture[str]) -> None:
    library_modules = find_library_modules()
    if not library_modules:
        print("[CONVENTIONS] no library.py modules yet — no keywords to check")
        return
    violations: list[str] = []
    for path in library_modules:
        module = load_module_from_path(path)
        for name, _func in iter_keyword_functions(module):
            short = name.split(".")[-1]
            first_token = short.split("_")[0]
            if first_token not in _VERB_ALLOWLIST:
                violations.append(f"{path}::{name} (first token {first_token!r} not in verb allowlist)")
    assert not violations, (
        f"@keyword names whose first token is not in the verb allowlist: "
        f"{violations!r}. Allowlist: {sorted(_VERB_ALLOWLIST)!r}. Extend "
        f"`_VERB_ALLOWLIST` in tests/unit/conventions/test_keyword_name_idiom.py "
        f"if a new verb is needed."
    )
