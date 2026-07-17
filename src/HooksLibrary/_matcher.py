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

"""Hook matcher engine - shared by static simulation and live execution.

One engine, so `Hook.Get Hooks For Event` (static) and `Hook.Fire Hook Event`
(live) can never disagree about which hooks match. Dispatch mirrors the Claude
Code matcher rules:

- ``*`` / empty / omitted (``None``) matches every subject.
- A matcher of only ``[A-Za-z0-9_- ,|]`` is an exact match or a ``|``/``,``
  list of exact matches.
- Anything else is compiled with Python ``re`` and matched unanchored via
  ``re.search``.

Matchers are evaluated with Python ``re``, not JavaScript RegExp as Claude Code
itself uses; a few constructs differ. `validate_matcher` gives you a
deterministic pre-flight. Over-long subjects are rejected with a hard length
cap so a pathological regex can't hang the runner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from AgentEval._core import HookExecutionError

__all__ = [
    "MATCHER_ENGINE_NOTE",
    "MAX_MATCHER_SUBJECT_LEN",
    "MatcherValidation",
    "matcher_matches",
    "safe_search",
    "validate_matcher",
]

# Matcher subjects are tool names (`Bash`, `mcp__server__tool`, ...). Anything
# past a few kilobytes is illegitimate; reject it rather than risk a
# catastrophic-backtracking hang in the parent process.
MAX_MATCHER_SUBJECT_LEN: int = 4096

# Documented flavor divergence, echoed into `Validate Matcher Syntax` output.
MATCHER_ENGINE_NOTE: str = (
    "Matchers are evaluated with Python `re` (unanchored `re.search`), NOT "
    "JavaScript RegExp as Claude Code itself uses. Constructs that differ "
    "between the two engines (lookbehind flavor, `\\u{...}` escapes, some "
    "named-group syntax) may resolve differently - validate regex matchers "
    "here before relying on them."
)

# A matcher of only these characters is a simple exact/list matcher, not a regex.
_SIMPLE_CLASS_RE = re.compile(r"^[A-Za-z0-9_\- ,|]+$")


def safe_search(pattern: str | re.Pattern[str], subject: str) -> re.Match[str] | None:
    """`re.search`, but reject an over-long subject before searching.

    Caps subject length so a catastrophic-backtracking matcher can't scan an
    absurd subject and hang the runner. Raises `HookExecutionError` (naming the
    pattern) when the subject exceeds the cap.
    """
    pattern_repr = pattern.pattern if isinstance(pattern, re.Pattern) else pattern
    if len(subject) > MAX_MATCHER_SUBJECT_LEN:
        raise HookExecutionError(
            f"matcher subject is {len(subject)} chars, over the "
            f"{MAX_MATCHER_SUBJECT_LEN}-char cap for regex matcher {pattern_repr!r}. "
            "Shorten the subject (tool name) or narrow the matcher."
        )
    if isinstance(pattern, re.Pattern):
        return pattern.search(subject)
    return re.search(pattern, subject)


@dataclass(frozen=True)
class MatcherValidation:
    """Result of validating a matcher against the dispatch rules.

    ``kind`` is ``"match_all"`` / ``"list"`` / ``"regex"``. ``valid`` is True
    when the matcher compiles under its branch. ``error`` names the offending
    pattern on failure, else ``None``. ``subject_matches`` is the boolean match
    result when a subject was supplied and the matcher is valid, else ``None``.
    """

    matcher: str | None
    kind: str
    valid: bool
    error: str | None
    subject_matches: bool | None


def _is_match_all(matcher: str | None) -> bool:
    """True for the match-all cases: omitted / empty / literal ``*``."""
    return matcher is None or matcher == "" or matcher == "*"


def _split_simple_list(matcher: str) -> list[str]:
    """Split a simple-class matcher on ``|`` and ``,`` into stripped tokens."""
    return [token.strip() for token in re.split(r"[|,]", matcher) if token.strip()]


def matcher_matches(matcher: str | None, subject: str) -> bool:
    """Return whether ``matcher`` matches ``subject`` per the dispatch rules.

    Match-all is always True; a simple class is exact membership in its
    ``|``/``,`` token list; anything else is an unanchored ``re.search``. A
    regex that won't compile raises ``re.error`` - route through
    `validate_matcher` for a graceful pre-flight.
    """
    if _is_match_all(matcher):
        return True
    assert matcher is not None  # narrowed by _is_match_all
    if _SIMPLE_CLASS_RE.match(matcher):
        return subject in _split_simple_list(matcher)
    return safe_search(matcher, subject) is not None


def validate_matcher(matcher: str | None, subject: str | None = None) -> MatcherValidation:
    """Validate a matcher under the dispatch rules; optionally test a subject.

    Never raises on a bad regex - reports it via ``valid=False`` + ``error``
    naming the offending pattern.
    """
    if _is_match_all(matcher):
        subject_matches = True if subject is not None else None
        return MatcherValidation(matcher, "match_all", True, None, subject_matches)

    assert matcher is not None
    if _SIMPLE_CLASS_RE.match(matcher):
        subject_matches = (subject in _split_simple_list(matcher)) if subject is not None else None
        return MatcherValidation(matcher, "list", True, None, subject_matches)

    try:
        compiled = re.compile(matcher)
    except re.error as exc:
        return MatcherValidation(
            matcher,
            "regex",
            False,
            f"matcher {matcher!r} is not a simple list and failed to compile as a Python regex: {exc}",
            None,
        )
    subject_matches = (safe_search(compiled, subject) is not None) if subject is not None else None
    return MatcherValidation(matcher, "regex", True, None, subject_matches)
