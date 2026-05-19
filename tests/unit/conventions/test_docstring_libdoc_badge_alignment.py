"""Conventions test: `@keyword` docstrings contain the tier badge string.

Story 1b.6 AC-1b.6.6 per Story 1b.1 `_kernel/tier.py` `_BADGES` dict L45-49:
every `@keyword`-decorated function's docstring MUST contain its tier
badge text verbatim. Asserts the docstring tier badge (read by humans
via libdoc HTML) matches the `_agenteval_tier` attribute (read by the
tier-decorator at registration). No double-source-of-truth drift.

Exact badge strings per Story 1b.1 `tier.py` L45-49:
- `[Tier 1 — Deterministic]`
- `[Tier 2 — Single-call]`
- `[Tier 3 — Fan-out + Statistical]`

End-of-Epic-1b state: zero `@keyword` functions → trivially pass.
"""

from __future__ import annotations

import pytest

from AgentEval._kernel.tier import tier_badge

from ._walk import find_library_modules, iter_keyword_functions, load_module_from_path


def test_keyword_docstrings_contain_tier_badge(capsys: pytest.CaptureFixture[str]) -> None:
    library_modules = find_library_modules()
    if not library_modules:
        print("[CONVENTIONS] no library.py modules yet — no keywords to check")
        return
    violations: list[str] = []
    for path in library_modules:
        module = load_module_from_path(path)
        for name, func in iter_keyword_functions(module):
            tier_value = getattr(func, "_agenteval_tier", None)
            if tier_value is None:
                # tier-annotation-present test catches this case; skip here.
                continue
            expected_badge = tier_badge(tier_value)
            docstring = func.__doc__ or ""
            if expected_badge not in docstring:
                violations.append(f"{path}::{name} (tier={tier_value}; missing badge {expected_badge!r} in docstring)")
    assert not violations, f"@keyword docstrings missing tier badge per Story 1b.1 tier.py: {violations!r}"
