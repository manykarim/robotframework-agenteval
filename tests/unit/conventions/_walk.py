"""Shared helpers for Story 1b.6 conventions tests.

Walks `src/AgentEval/**/library.py` modules + iterates `@keyword`-decorated
functions for the 5 conventions tests. End-of-Epic-1b state: zero
`library.py` modules; all conventions tests trivially pass via the empty-set
case. Epic 2+ adds real `library.py` files; conventions tests start
catching violations at that time.

Story 1b.6 design note: `@keyword` from `robot.api.deco` does NOT add a
public marker attribute — it's a no-op at runtime that pythonlibcore + RF's
DynamicCore consume at library-registration time via `hasattr(meth,
'robot_name')`. The conventions tests' "marker" check is therefore
`hasattr(func, 'robot_name')` (RF convention) OR the function's qualname
suggests it's a public method of a `*Library`-suffixed class — Phase-1
uses the `robot_name` check since pythonlibcore is the canonical surface.
"""

from __future__ import annotations

import importlib.util
import pathlib
from collections.abc import Iterable
from types import ModuleType
from typing import Any

SRC_ROOT = pathlib.Path(__file__).resolve().parents[3] / "src" / "AgentEval"


def find_library_modules() -> list[pathlib.Path]:
    """Return all `library.py` files under `src/AgentEval/`.

    Phase-1 (end-of-Epic-1b): returns empty list — no sub-library has
    shipped its `library.py` yet. Epic 2+ adds real files.
    """
    if not SRC_ROOT.exists():
        return []
    return sorted(SRC_ROOT.rglob("library.py"))


def load_module_from_path(path: pathlib.Path) -> ModuleType:
    """Load a Python module from an absolute path (used for `library.py` walks)."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iter_keyword_functions(module: ModuleType) -> Iterable[tuple[str, Any]]:
    """Yield `(name, func)` for every `@keyword`-decorated callable in a module.

    The canonical RF marker is `robot_name` attribute (set by
    `robot.api.deco.keyword(name=...)` or default-name-derivation at
    decoration time). pythonlibcore + RF's DynamicCore both consume this
    attribute at library-registration time.

    For Phase-1 (end-of-Epic-1b zero `library.py` files), this iterator
    yields nothing. As Epic 2+ adds real keywords, it yields the
    `@keyword`-marked functions for the conventions checks.
    """
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if callable(obj) and hasattr(obj, "robot_name"):
            yield name, obj
        # Methods on `*Library` classes also surface here when the class
        # is module-level (RF's DynamicCore convention).
        if isinstance(obj, type) and name.endswith("Library"):
            for attr_name in dir(obj):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(obj, attr_name)
                if callable(attr) and hasattr(attr, "robot_name"):
                    yield f"{name}.{attr_name}", attr
