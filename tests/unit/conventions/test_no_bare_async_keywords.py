"""Conventions test: no `@keyword`-decorated function is `async def`.

Story 1b.6 AC-1b.6.4 per **ADR-012** (NOT ADR-A1 — pre-create-story drift
check D1): async ops MUST go through `_run_async` from
`src/AgentEval/_kernel/run_async.py` (Story 1b.1). Bare `async def`
`@keyword` functions break RF's synchronous Library Listener execution
model (pythonlibcore + DynamicCore expect sync callables).

End-of-Epic-1b state: zero `@keyword` functions → trivially pass.
"""

from __future__ import annotations

import inspect

import pytest

from ._walk import find_library_modules, iter_keyword_functions, load_module_from_path


def test_no_keyword_is_async_def(capsys: pytest.CaptureFixture[str]) -> None:
    library_modules = find_library_modules()
    if not library_modules:
        print("[CONVENTIONS] no library.py modules yet — no keywords to check (ADR-012)")
        return
    violations: list[str] = []
    for path in library_modules:
        module = load_module_from_path(path)
        for name, func in iter_keyword_functions(module):
            if inspect.iscoroutinefunction(func):
                violations.append(f"{path}::{name}")
    assert not violations, (
        f"@keyword functions defined with `async def` per ADR-012 violation: "
        f"{violations!r}. Wrap async ops via `_kernel/run_async._run_async` instead."
    )
