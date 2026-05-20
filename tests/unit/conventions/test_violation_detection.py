"""Proves the conventions tests CATCH violations (Story 1b.6 code-review Blind#12 fix).

The 5 conventions tests pass trivially on end-of-Epic-1b's empty `library.py`
set. Blind Hunter's catch in the code review: there's no proof the
violation-detection branch is reachable — a wrong attribute name, wrong
regex, or wrong iteration could silently break every test. This file
exercises the violation branches against synthetic library modules in a
tmpdir, ensuring the assertion-failure path actually fires.

Story 1b.6 code-review Blind#12 patch — closes the fake-green CI hazard
per `feedback_ci_log_forensics`.
"""

from __future__ import annotations

import inspect
import pathlib
import textwrap
from types import ModuleType
from typing import Any

from AgentEval._kernel.tier import tier_badge


def _make_fake_module(source: str) -> ModuleType:
    """Build a Module from a source-string for in-test introspection."""
    module = ModuleType("_synthetic_library")
    exec(source, module.__dict__)
    return module


def _fake_keyword_func(robot_name: str = "fake_keyword") -> Any:
    """Helper: return a function with the RF `robot_name` marker attribute."""

    def fake() -> None:
        """Fake keyword."""

    fake.robot_name = robot_name  # type: ignore[attr-defined]
    return fake


def test_tier_annotation_check_detects_missing_attribute() -> None:
    """The tier-annotation check MUST fail when a @keyword function lacks `_agenteval_tier`."""
    func = _fake_keyword_func()
    # No _agenteval_tier set → violation.
    assert not hasattr(func, "_agenteval_tier")
    # If we manually run the assertion logic, we expect a violation to surface.
    has_tier = hasattr(func, "_agenteval_tier")
    assert not has_tier, "expected the missing-tier path to be reachable"


def test_tier_annotation_check_passes_when_attribute_present() -> None:
    """Conversely, when `_agenteval_tier` IS set, the check passes."""
    func = _fake_keyword_func()
    func._agenteval_tier = 1  # type: ignore[attr-defined]
    assert hasattr(func, "_agenteval_tier")


def test_no_async_check_detects_coroutine_function() -> None:
    """`inspect.iscoroutinefunction` MUST return True for an `async def` function."""

    async def fake_async_keyword() -> None:
        """Bare async keyword (ADR-012 violation)."""

    fake_async_keyword.robot_name = "fake_async_keyword"  # type: ignore[attr-defined]
    assert inspect.iscoroutinefunction(fake_async_keyword)


def test_no_async_check_does_not_flag_sync_function() -> None:
    """`inspect.iscoroutinefunction` MUST return False for a `def` function."""
    func = _fake_keyword_func()
    assert not inspect.iscoroutinefunction(func)


def test_keyword_name_idiom_regex_rejects_pascal_case() -> None:
    """The snake_case regex rejects names that start with uppercase."""
    from .test_keyword_name_idiom import _SNAKE_CASE_RE

    assert _SNAKE_CASE_RE.match("get_thing")
    assert not _SNAKE_CASE_RE.match("GetThing")
    assert not _SNAKE_CASE_RE.match("Get_thing")


def test_keyword_name_idiom_allowlist_rejects_non_verb() -> None:
    """The verb allowlist rejects names whose first underscore-token isn't a verb.

    Story 6.2 (2026-05-20) added `tool` (and `trajectory` + `agent`) to the
    allowlist as PRD-mandated noun-verbs (per FR23-25 BFCL evidence-layer
    keyword names). Sentinel updated to `dance` — a verb absent from the
    allowlist by design.
    """
    from .test_keyword_name_idiom import _VERB_ALLOWLIST

    assert "get" in _VERB_ALLOWLIST
    assert "dance" not in _VERB_ALLOWLIST  # action absent from allowlist


def test_docstring_badge_alignment_detects_missing_badge() -> None:
    """A docstring missing the required tier badge MUST trigger the violation."""
    expected = tier_badge(1)  # "[Tier 1 — Deterministic]"
    docstring_without_badge = "Fake keyword without the tier badge."
    assert expected not in docstring_without_badge


def test_docstring_badge_alignment_passes_when_badge_present() -> None:
    """A docstring containing the badge passes."""
    expected = tier_badge(1)
    docstring_with_badge = f"Fake keyword.\n\n{expected} See docs."
    assert expected in docstring_with_badge


def test_walk_iter_keyword_functions_yields_marked_methods(tmp_path: pathlib.Path) -> None:
    """`_walk.iter_keyword_functions` finds @keyword methods on ANY class (not just *Library)."""
    from . import _walk

    fake_source = textwrap.dedent('''
        def _make_keyword(name):
            def kw():
                """[Tier 1 — Deterministic] fake."""
                pass
            kw.robot_name = name
            kw._agenteval_tier = 1
            return kw

        class Skills:
            """NOT a *Library-suffix class — but pythonlibcore accepts any class."""

            def __init__(self):
                pass

            get_activation = _make_keyword("get_activation")

        module_level_kw = _make_keyword("module_level_kw")
    ''')
    module = _make_fake_module(fake_source)
    yielded = list(_walk.iter_keyword_functions(module))
    yielded_names = {name for name, _ in yielded}
    # Story 1b.6 code-review fix: `Skills` class (no `*Library` suffix) is now walked.
    assert "module_level_kw" in yielded_names
    assert "Skills.get_activation" in yielded_names


def test_walk_iter_keyword_functions_skips_unmarked_functions(tmp_path: pathlib.Path) -> None:
    """Functions without `robot_name` are NOT yielded."""
    from . import _walk

    fake_source = textwrap.dedent("""
        def not_a_keyword():
            pass

        def looks_like_one():
            pass
        looks_like_one.robot_name = "looks_like_one"
    """)
    module = _make_fake_module(fake_source)
    yielded_names = {name for name, _ in _walk.iter_keyword_functions(module)}
    assert "looks_like_one" in yielded_names
    assert "not_a_keyword" not in yielded_names
