"""Conventions test: every `@keyword`-decorated function has `_agenteval_tier`.

Story 1b.6 AC-1b.6.2 per architecture L620 + Story 1b.1 `_kernel/tier.py`
L74-75: every `@keyword`-decorated function on every `src/AgentEval/**/library.py`
module MUST have a `_agenteval_tier` attribute set by the `@tier(N)` decorator.

End-of-Epic-1b state: zero `library.py` modules exist; this test passes
trivially with an explicit "no keywords yet — no violations possible" log
message. Epic 2+ adds real keywords; this test fails loudly when an Epic-2
keyword is missing the `@tier(N)` decoration.
"""

from __future__ import annotations

import pytest

from ._walk import find_library_modules, iter_keyword_functions, load_module_from_path


def test_every_keyword_has_tier_annotation(capsys: pytest.CaptureFixture[str]) -> None:
    library_modules = find_library_modules()
    if not library_modules:
        # Phase-1 trivial-pass: explicit log line so a future Epic-2 reader
        # knows the test ran + simply found nothing to assert against.
        print("[CONVENTIONS] no library.py modules yet — no keywords to check")
        return
    violations: list[str] = []
    for path in library_modules:
        module = load_module_from_path(path)
        for name, func in iter_keyword_functions(module):
            if not hasattr(func, "_agenteval_tier"):
                violations.append(f"{path}::{name}")
    assert not violations, (
        f"@keyword functions missing _agenteval_tier attribute (Story 1b.1 tier.py + architecture L620): {violations!r}"
    )
