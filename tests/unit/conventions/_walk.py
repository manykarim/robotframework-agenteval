"""Shared helpers for Story 1b.6 conventions tests.

Walks `src/AgentEval/**/library.py` modules + iterates `@keyword`-decorated
functions for the 5 conventions tests. End-of-Epic-1b state: zero
`library.py` modules; all conventions tests trivially pass via the empty-set
case. Epic 2+ adds real `library.py` files; conventions tests start
catching violations at that time.

Story 1b.6 design note (corrected per Codex LOW catch in code review):
`@keyword` from `robot.api.deco` DOES add public marker attributes at
runtime — specifically `robot_name`, `robot_tags`, and `robot_types` per
`robot/api/deco.py:4-7` source. pythonlibcore + RF's DynamicCore consume
these attributes at library-registration time. The conventions tests'
"marker" check is therefore `hasattr(func, 'robot_name')` (the canonical
RF marker; works for any class hosting `@keyword`-decorated methods, NOT
just `*Library`-suffixed classes — Story 1b.6 code-review Codex+Edge
catch corrected the pre-edit `*Library`-suffix heuristic which would
have missed pythonlibcore's own `Library1` / `Library2` / `MyPlugi`
examples).
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

    Story 1b.6 code-review Edge fix: asserts `SRC_ROOT` exists to prevent
    fake-green when the tests-vs-src parents[3] traversal drifts. Skips
    `__pycache__` + `.venv` + dotted dirs to avoid scanning vendored
    copies. Filters out symlinks to prevent symlink-cycle recursion.
    """
    assert SRC_ROOT.exists(), (
        f"SRC_ROOT not found: {SRC_ROOT} — conventions tests would fake-green "
        f"if `find_library_modules()` returns []. Check the parents[3] "
        f"traversal in _walk.py if the tests dir moved relative to src/."
    )
    results: list[pathlib.Path] = []
    for p in SRC_ROOT.rglob("library.py"):
        # Skip vendored / cached / hidden dirs.
        if any(part.startswith(".") or part == "__pycache__" for part in p.parts):
            continue
        if p.is_symlink():
            continue
        results.append(p)
    return sorted(results)


def load_module_from_path(path: pathlib.Path) -> ModuleType:
    """Load a Python module from an absolute path with the canonical fully-qualified package name.

    Story 1b.6 code-review Codex+Edge fix: derives the module name from the
    `src/AgentEval/.../library.py` path (e.g.,
    `AgentEval.skills.library`) rather than the pre-edit `path.stem` which
    was always `"library"` — this caused two `library.py` files to collide
    in `sys.modules` + broke relative imports inside the loaded module.

    Args:
        path: Absolute path to a `library.py` file under `src/AgentEval/`.

    Returns:
        The loaded module, registered in `sys.modules` under its
        fully-qualified package name.

    Raises:
        ImportError: spec creation or `exec_module` failed.
    """
    # Derive the fully-qualified module name from the path relative to SRC_ROOT's parent.
    # path = .../src/AgentEval/skills/library.py → module_name = AgentEval.skills.library
    src_parent = SRC_ROOT.parent  # .../src
    relative = path.relative_to(src_parent)
    module_name = ".".join(relative.with_suffix("").parts)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load module from {path} as {module_name!r}")
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec_module so relative imports resolve.
    import sys

    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        # Roll back the sys.modules registration on failure.
        sys.modules.pop(module_name, None)
        raise
    return module


def iter_keyword_functions(module: ModuleType) -> Iterable[tuple[str, Any]]:
    """Yield `(name, func)` for every `@keyword`-decorated callable in a module.

    The canonical RF marker is the `robot_name` attribute (set by
    `robot.api.deco.keyword(name=...)` or default-name-derivation at
    decoration time per `robot/api/deco.py:4-7`). pythonlibcore + RF's
    DynamicCore both consume this attribute at library-registration time.

    Story 1b.6 code-review Codex+Edge fix: walks EVERY module-level class
    for `@keyword`-decorated methods (NOT just `*Library`-suffixed
    classes). The pre-edit heuristic missed pythonlibcore's own examples
    (`Library1`, `Library2`, `MyPlugi`) + would miss future agenteval
    sub-library classes named `Skills` / `MCP` / `RunScenario`.

    Story 1b.6 code-review Edge fix: handles `classmethod` /
    `staticmethod` descriptors by unwrapping via `__func__` so the
    `robot_name` attribute on the underlying function is visible.

    For Phase-1 (end-of-Epic-1b zero `library.py` files), this iterator
    yields nothing. As Epic 2+ adds real keywords, it yields the
    `@keyword`-marked functions for the conventions checks.
    """
    for name in dir(module):
        if name.startswith("_"):
            continue
        try:
            obj = getattr(module, name)
        except Exception:
            # Property/descriptor with side-effect that raises; skip.
            continue
        if callable(obj) and hasattr(obj, "robot_name"):
            yield name, obj
        # Walk EVERY module-level class — pythonlibcore + DynamicCore
        # accept any class hosting `@keyword`-decorated methods (Story
        # 1b.6 code-review fix; dropped the `*Library` suffix heuristic).
        if isinstance(obj, type):
            for attr_name in dir(obj):
                if attr_name.startswith("_"):
                    continue
                try:
                    attr = getattr(obj, attr_name)
                except Exception:
                    continue
                # Unwrap classmethod / staticmethod descriptors so
                # the underlying function's `robot_name` is reachable.
                target = getattr(attr, "__func__", attr)
                if callable(target) and hasattr(target, "robot_name"):
                    yield f"{name}.{attr_name}", target
