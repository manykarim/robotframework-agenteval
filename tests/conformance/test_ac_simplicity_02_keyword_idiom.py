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

"""AC-SIMPLICITY-02 conformance test (Story 2.4 un-skip; was Story 1b.6 skeleton).

Story 2.4 populates this previously-skipped conformance test:
- Every `@keyword`-decorated method on every sub-library has `@tier(N)`.
- No sub-library exposes a `Should *` keyword EXCEPT the Story 2.1
  Phase-1 carve-out (`Skill.Should Be Valid Frontmatter` per
  architecture L838 carve-out registry).
- Every keyword name follows snake_case + verb-allowlist per the
  Story 1b.6 `_VERB_ALLOWLIST`.
- The runtime collision-detector in `AgentEval._build_components`
  catches any cross-sub-library `@keyword(name=...)` collision —
  asserted by instantiating `AgentEval()` (which would raise if the
  current `_SUB_LIBRARIES` contains colliding keywords).

Owning epic: Epic 1b Story 1b.6 (conventions) AND Epic 2 Story 2.4
(this story populates the previously-skipped skeleton).
"""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path
from typing import Any

from AgentEval._kernel.tier import get_keyword_tier

# Story 2.1 Phase-1 carve-out per architecture L838 registry: the ONLY
# allowed sub-library `Should *` keyword in Phase-1 is
# `Skill.Should Be Valid Frontmatter` (Phase-2 ADR-022 AssertionEngine
# adoption retires the carve-out). Future stories that ship additional
# sub-library `Should *` keywords MUST extend BOTH the architecture
# carve-out registry AND this allowlist with explicit ratification.
_PHASE_1_SHOULD_CARVE_OUTS: frozenset[tuple[str, str]] = frozenset(
    {
        ("SkillsLibrary", "Should Be Valid Frontmatter"),
        # Story 6.2 (2026-05-20) — PRD FR23a/FR23b/FR24/FR25 assertion library:
        # the BFCL three-layer evidence framing (trajectory / tool-call / response)
        # uses `Should *` keyword names verbatim from the PRD. AssertionEngine
        # adoption (ADR-022) is deferred to Story 6.3 per Story 6.2 D-1 drift
        # fix; until then these are Phase-1 plain @keyword definitions.
        ("AssertionsLibrary", "Trajectory Should Match"),
        ("AssertionsLibrary", "Tool Call Should Have Occurred"),
        ("AssertionsLibrary", "Agent Response Should Contain"),
        ("AssertionsLibrary", "Agent Response Should Match Regex"),
        ("AssertionsLibrary", "Agent Response Should Match Schema"),
    }
)

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "AgentEval"


def _all_library_classes() -> list[type]:
    """Discover all sub-library classes (each `src/AgentEval/<name>/library.py`).

    Mirrors the Story 1b.6 `_walk.find_library_modules` discovery but
    returns the *Library classes (not just modules) for keyword-set
    introspection.
    """
    classes: list[type] = []
    for path in sorted(SRC_ROOT.rglob("library.py")):
        if any(part.startswith(".") or part == "__pycache__" for part in path.parts):
            continue
        # Derive fully-qualified module name (e.g., `AgentEval.skills.library`).
        rel = path.relative_to(SRC_ROOT.parent)
        module_name = ".".join(rel.with_suffix("").parts)
        module = importlib.import_module(module_name)
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            # Filter to classes hosting at least one `@keyword`-decorated method.
            if obj.__module__ != module_name:
                continue
            for attr_name in dir(obj):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(obj, attr_name, None)
                target = getattr(attr, "__func__", attr) if attr else attr
                if target is not None and hasattr(target, "robot_name"):
                    classes.append(obj)
                    break
    return classes


def _iter_keywords(cls: type) -> list[tuple[str, Any]]:
    """Yield `(rf_keyword_name, func)` for every `@keyword`-decorated method on cls."""
    found: list[tuple[str, Any]] = []
    for attr_name in dir(cls):
        if attr_name.startswith("_"):
            continue
        attr = getattr(cls, attr_name, None)
        target = getattr(attr, "__func__", attr) if attr else attr
        if target is not None and hasattr(target, "robot_name"):
            found.append((target.robot_name, target))
    return found


def test_every_keyword_has_tier_annotation() -> None:
    """Every `@keyword` on every sub-library has `_agenteval_tier` set."""
    violations: list[str] = []
    for cls in _all_library_classes():
        for kw_name, func in _iter_keywords(cls):
            if get_keyword_tier(func) is None:
                violations.append(f"{cls.__name__}.{kw_name}")
    assert not violations, f"keywords missing @tier(N): {violations!r}"


def test_no_unauthorized_sub_library_should_keywords() -> None:
    """Sub-library `Should *` keywords are anti-pattern UNLESS in the Phase-1 carve-out registry."""
    violations: list[tuple[str, str]] = []
    for cls in _all_library_classes():
        for kw_name, _func in _iter_keywords(cls):
            if kw_name.startswith("Should "):
                key = (cls.__name__, kw_name)
                if key not in _PHASE_1_SHOULD_CARVE_OUTS:
                    violations.append(key)
    assert not violations, (
        f"sub-library `Should *` keywords outside Phase-1 carve-out registry: {violations!r}. "
        f"Allowlist: {sorted(_PHASE_1_SHOULD_CARVE_OUTS)!r}. Extend both this allowlist AND the "
        f"architecture L838 carve-out registry with explicit ratification before shipping new "
        f"`Should *` sub-library keywords."
    )


def test_dynamic_core_composition_collision_free() -> None:
    """Instantiating `AgentEval()` must not raise the collision-detector RuntimeError.

    The detector in `AgentEval._build_components` raises if any 2
    components register the same `@keyword(name=...)` value. Story 2.2
    introduced the detector; Stories 2.1+2.2+2.3 ratified the
    exclusion-based composition pattern (Skills, Subagents, MCP NOT
    composed; Hooks composed). This test pins that ratification by
    asserting clean composition.
    """
    from AgentEval import AgentEval as AgentEvalLib

    # Just instantiating it would raise on collision — but assert no
    # RuntimeError leaks for clarity.
    library = AgentEvalLib()
    assert library is not None


def test_keyword_names_use_snake_case_method_names() -> None:
    """Every `@keyword`-decorated method's PYTHON-LEVEL name (`func.__name__`) is snake_case + verb-prefixed.

    Mirrors `tests/unit/conventions/test_keyword_name_idiom.py` checks
    but runs as a conformance gate (not just a unit-test gate). The
    method name (not the RF `keyword name=` attribute) is checked per
    Story 1b.6's idiom contract.
    """
    import re

    snake = re.compile(r"^[a-z][a-z0-9_]*$")
    # Verb allowlist — kept in sync with
    # `tests/unit/conventions/test_keyword_name_idiom.py:_VERB_ALLOWLIST`.
    # Story 6.2 (2026-05-20) added `trajectory` + `tool` + `agent` for the
    # PRD FR23-25 assertion library (Trajectory/ToolCall/AgentResponse
    # Should-* keywords). Names are load-bearing per PRD.
    verb_allowlist = {
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
    }
    violations: list[str] = []
    for cls in _all_library_classes():
        for _kw_name, func in _iter_keywords(cls):
            method_name = func.__name__
            if not snake.match(method_name):
                violations.append(f"{cls.__name__}.{method_name} (not snake_case)")
                continue
            first_token = method_name.split("_")[0]
            if first_token not in verb_allowlist:
                violations.append(f"{cls.__name__}.{method_name} (verb {first_token!r} not in allowlist)")
    assert not violations, f"snake_case/verb-allowlist violations: {violations!r}"


def test_at_least_one_sub_library_present() -> None:
    """Story 2.4 sanity check: AT LEAST 4 sub-libraries are shipped (skills/subagents/hooks/mcp)."""
    names = {cls.__name__ for cls in _all_library_classes()}
    assert {"SkillsLibrary", "SubagentsLibrary", "HooksLibrary", "MCPLibrary"} <= names, (
        f"expected SkillsLibrary + SubagentsLibrary + HooksLibrary + MCPLibrary; found {names!r}"
    )


def test_core_ergonomic_should_keywords_have_paired_getters() -> None:
    """AC-SIMPLICITY-02b: every CORE `Should *` keyword has a paired `Get *` keyword.

    Story 2.4 code-review Auditor MED-1 fix 2026-05-19: pre-edit
    SIMPLICITY-02 conformance test shipped only the (a) half of the
    rule (no sub-library `Should *`); architecture L830 names BOTH
    halves. The (b) half is core-keyword-paired-getter enforcement.
    Phase-1 has no CORE ergonomic `Should *` keywords yet (the top-
    level `AgentEval` library exposes only `Get Effective Config` +
    composed `Hook.Get Config`); this test trivially passes today but
    becomes load-bearing the moment Epic 4 lands `Tool Call Should
    Have Occurred` + its paired `Get Tool Calls` getter per PRD AC-
    SIMPLICITY-02b L339-350.
    """
    # Walk the top-level `AgentEval` class for core ergonomic keywords
    # (excluding composed sub-library keywords which are checked by
    # `test_no_unauthorized_sub_library_should_keywords`).
    from AgentEval import AgentEval as AgentEvalLib

    core_should_names: list[str] = []
    core_get_names: list[str] = []
    for attr_name in dir(AgentEvalLib):
        if attr_name.startswith("_"):
            continue
        attr = getattr(AgentEvalLib, attr_name, None)
        target = getattr(attr, "__func__", attr) if attr else attr
        if target is None:
            continue
        rf_name = getattr(target, "robot_name", None)
        if rf_name is None:
            continue
        if rf_name.startswith("Should "):
            core_should_names.append(rf_name)
        elif rf_name.startswith("Get "):
            core_get_names.append(rf_name)

    # For each `Should X` core keyword, assert there is a paired `Get X-fragment`.
    # Convention per PRD L347: `Tool Call Should Have Occurred` pairs with
    # `Get Tool Calls`. We don't enforce the exact rename rule (Phase-1
    # has no examples to ground it); we enforce existence of ANY `Get *`
    # core keyword for each `Should *` core keyword — Phase-2 stories
    # adding the first pair will tighten this if the convention
    # crystallizes.
    if core_should_names:
        assert core_get_names, (
            f"core `Should *` keywords {core_should_names!r} but no paired `Get *` keyword "
            f"exists on the top-level `AgentEval` library; violates PRD AC-SIMPLICITY-02b."
        )
    # Phase-1 trivially-passes when core_should_names is empty (the
    # current state). Test surface is load-bearing for Epic 4+.
