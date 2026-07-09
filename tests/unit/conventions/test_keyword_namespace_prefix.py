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

"""Namespace-prefix conventions test (`compose-single-library-import` change).

Enforces the one learnable naming rule mechanically (keyword-namespacing spec):

- Every `@keyword` on an artifact/engine sub-library (Skills, Subagents,
  Hooks, MCP, Stats, Judge) MUST bake its namespace token + dot into its
  `robot_name` (`Skill.` / `Subagent.` / `Hook.` / `MCP.` / `Stat.` /
  `Judge.`).
- Every `@keyword` on a core-loop sub-library (Orchestration, Telemetry,
  Metrics, Assertions, Heatmap) and on the top-level `AgentEval` class MUST
  contain NO dot.
- No sub-library mixes prefixed and unprefixed keyword names.
- The multi-word-after-dot libdoc constraint holds (single-word post-dot
  portions are auto-split by DynamicCore+libdoc — `feedback_libdoc_namespace
  _keyword_must_be_multiword`).
- Libdoc renders no auto-split names (no dot-followed-by-space).

Every discovered `*Library` class (plus the top-level `AgentEval`) MUST be
categorized below — a new, uncategorized library class fails the test,
forcing an explicit prefixed/unprefixed decision at ship time.
"""

from __future__ import annotations

import pytest

from ._walk import find_library_modules, load_module_from_path

# Class name -> required namespace token (post-dot portion of every keyword).
_NAMESPACED: dict[str, str] = {
    "SkillsLibrary": "Skill",
    "SubagentsLibrary": "Subagent",
    "HooksLibrary": "Hook",
    "MCPLibrary": "MCP",
    "StatsLibrary": "Stat",
    "JudgeLibrary": "Judge",
    # add-red-team-probes: defensive adversarial-robustness engine — every
    # keyword carries the `RedTeam.` prefix (post-dot portion multi-word).
    "RedTeamLibrary": "RedTeam",
}

# Assertion-form keywords that intentionally carry NO namespace prefix even
# though they live on a namespaced library. They follow the `AssertionsLibrary`
# `X Should ...` naming idiom (they read as assertions to operators) but must
# live on a Tier-2 library because they make an LLM call — `AssertionsLibrary`
# is a Tier-1 surface. Documented in add-judge-criteria-shortcuts design D6.
# This is a NARROW, per-name allowlist: every OTHER keyword on the namespaced
# library is still enforced to carry the prefix, and any NEW unprefixed keyword
# not listed here still fails `test_namespaced_libraries_prefix_every_keyword`.
_UNPREFIXED_ASSERTION_FORMS: dict[str, frozenset[str]] = {
    "JudgeLibrary": frozenset({"Judge Score Should Be Above", "Judge Turn Should Pass"}),
}

# Class names whose keywords MUST carry no namespace prefix (no dot).
_UNPREFIXED: frozenset[str] = frozenset(
    {
        "OrchestrationLibrary",
        "TelemetryLibrary",
        "MetricsLibrary",
        "AssertionsLibrary",
        "HeatmapLibrary",
        # add-multi-turn-conversation-testing: conversation lifecycle keywords
        # (`Start Conversation`, `Send Message`, `Simulate User`, …) are part of
        # the shared run-measure-assert loop, not an artifact/engine namespace —
        # unprefixed like Orchestration + Metrics.
        "ConversationLibrary",
        # add-regression-baseline-tracking: baseline snapshot/compare/trend
        # keywords (`Save Metrics Baseline`, `Metrics Should Not Regress`,
        # `Get Metric Trend`) are part of the shared run-measure-assert loop,
        # not an artifact/engine namespace — unprefixed like Metrics.
        "BaselineLibrary",
        "AgentEval",  # top-level composed class (its own config/tier keywords)
    }
)


def _keyword_names_by_class() -> dict[str, list[str]]:
    """Map every library class name -> list of its `@keyword` `robot_name`s."""
    out: dict[str, list[str]] = {}
    import importlib

    modules = [load_module_from_path(p) for p in find_library_modules()]
    # The top-level `AgentEval` class lives in `__init__.py`, not a
    # `library.py`, so import it explicitly.
    classes: list[type] = [importlib.import_module("AgentEval").AgentEval]
    for module in modules:
        for attr in vars(module).values():
            if isinstance(attr, type) and attr.__module__ == module.__name__ and attr.__name__.endswith("Library"):
                classes.append(attr)

    for cls in classes:
        names: list[str] = []
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue
            try:
                attr = getattr(cls, attr_name)
            except Exception:
                continue
            target = getattr(attr, "__func__", attr)
            robot_name = getattr(target, "robot_name", None)
            if robot_name is not None:
                names.append(robot_name)
        out.setdefault(cls.__name__, []).extend(names)
    return out


def test_every_library_class_is_categorized() -> None:
    """A new library class must be explicitly placed in `_NAMESPACED` or `_UNPREFIXED`."""
    by_class = _keyword_names_by_class()
    known = set(_NAMESPACED) | _UNPREFIXED
    uncategorized = sorted(set(by_class) - known)
    assert not uncategorized, (
        f"library classes not categorized in test_keyword_namespace_prefix.py: {uncategorized!r}. "
        f"Add each to `_NAMESPACED` (prefix ALL its keywords) or `_UNPREFIXED` (no dot) and "
        f"apply the matching rename."
    )


def _prefix_violations(cls_name: str, token: str, names: list[str]) -> list[str]:
    """Return prefix-rule violations for one class's keyword names.

    Shared by the real enforcement test and the failing-case test so both
    exercise the exact same predicate (per Tier-1 review LOW-1: the
    failing-case must route a synthetic bad keyword through the real check,
    not assert a standalone string fact).
    """
    prefix = f"{token}."
    return [
        f"{cls_name}: keyword {name!r} is missing the required {prefix!r} prefix"
        for name in names
        if not name.startswith(prefix)
    ]


def test_namespaced_libraries_prefix_every_keyword() -> None:
    """Artifact/engine libraries prefix ALL keywords with their token + dot."""
    by_class = _keyword_names_by_class()
    violations: list[str] = []
    for cls_name, token in _NAMESPACED.items():
        exceptions = _UNPREFIXED_ASSERTION_FORMS.get(cls_name, frozenset())
        names = [n for n in by_class.get(cls_name, []) if n not in exceptions]
        violations.extend(_prefix_violations(cls_name, token, names))
    assert not violations, "namespace-prefix violations:\n" + "\n".join(violations)


def test_unprefixed_libraries_have_no_dotted_keyword() -> None:
    """Core-loop libraries + top-level AgentEval carry no namespace prefix (no dot)."""
    by_class = _keyword_names_by_class()
    violations: list[str] = []
    for cls_name in _UNPREFIXED:
        for name in by_class.get(cls_name, []):
            if "." in name:
                violations.append(f"{cls_name}: keyword {name!r} must NOT contain a namespace prefix (dot)")
    assert not violations, "unexpected prefixed core-loop keyword:\n" + "\n".join(violations)


def test_prefixed_names_are_multiword_after_dot() -> None:
    """Post-dot portion of every prefixed name must be multi-word (libdoc auto-split guard)."""
    by_class = _keyword_names_by_class()
    violations: list[str] = []
    for cls_name in _NAMESPACED:
        for name in by_class.get(cls_name, []):
            post_dot = name.split(".", 1)[1] if "." in name else name
            if len(post_dot.split()) < 2:
                violations.append(
                    f"{cls_name}: keyword {name!r} has a single-word post-dot portion "
                    f"({post_dot!r}) — DynamicCore+libdoc would auto-split it"
                )
    assert not violations, "multi-word-after-dot violations:\n" + "\n".join(violations)


def test_foreign_prefix_trips_the_rule() -> None:
    """A namespaced-library keyword with a FOREIGN prefix is caught by the same check.

    Failing-case demonstration: a hypothetical SkillsLibrary keyword named
    `MCP.Do Thing` (foreign `MCP.` prefix instead of `Skill.`) must fail the
    prefix check with the offending name + expected prefix.
    """
    # Route a synthetic mis-prefixed keyword through the REAL enforcement
    # predicate (not a standalone string assertion), so a regression that
    # weakened `_prefix_violations` would be caught here.
    violations = _prefix_violations("SkillsLibrary", "Skill", ["Skill.Get Frontmatter", "MCP.Do Thing"])
    assert violations == ["SkillsLibrary: keyword 'MCP.Do Thing' is missing the required 'Skill.' prefix"], violations
    # And a correctly-prefixed set produces no violation.
    assert _prefix_violations("SkillsLibrary", "Skill", ["Skill.Get Frontmatter"]) == []


def test_libdoc_renders_no_auto_split_names() -> None:
    """Libdoc HTML for the composed library + each standalone sub-library has no `. ` names."""
    from robot.libdocpkg import LibraryDocumentation

    libraries = [
        "AgentEval",
        "AgentEval.skills.library.SkillsLibrary",
        "AgentEval.subagents.library.SubagentsLibrary",
        "AgentEval.hooks.library.HooksLibrary",
        "AgentEval.mcp.library.MCPLibrary",
        "AgentEval.stats.library.StatsLibrary",
        "AgentEval.judge.library.JudgeLibrary",
    ]
    violations: list[str] = []
    for lib in libraries:
        doc = LibraryDocumentation(lib)
        for kw in doc.keywords:
            # The auto-split signature is a dot immediately followed by a space
            # (e.g. `Judge. Calibrate`). A correctly multi-word post-dot name
            # renders as `Judge.Calibrate Rubric` (no space after the dot).
            if ". " in kw.name:
                violations.append(f"{lib}: keyword {kw.name!r} rendered with an auto-split dot-space")
    assert not violations, "libdoc auto-split names detected:\n" + "\n".join(violations)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
