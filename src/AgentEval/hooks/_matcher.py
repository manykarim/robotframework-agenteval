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

"""Hook matcher engine — shared by static simulation and live execution.

OpenSpec change `add-hooks-execution-testing`, design Decision 5. Implements
the documented Claude Code matcher character-class dispatch
(https://code.claude.com/docs/en/hooks, snapshot 2026-07-08):

- ``*`` / empty string / omitted (``None``) → match ALL subjects.
- A matcher containing ONLY ``[A-Za-z0-9_\\- ,|]`` → an exact match or a
  ``|`` / ``,``-separated list of exact matches.
- Anything else → compiled with Python ``re`` and matched UNANCHORED via
  ``re.search``.

**Python ``re`` is NOT JavaScript RegExp.** Claude Code compiles matchers
with the JS RegExp engine; Python's ``re`` diverges on some constructs
(lookbehind flavor, ``\\u{...}`` unicode escapes, named-group syntax, etc.).
`validate_matcher` surfaces this so users have a deterministic pre-flight.
Both the static simulation (`Hook.Get Hooks For Event`) and the live runner
(`Hook.Fire Hook Event`) call `matcher_matches` here, so simulation and
execution can NEVER disagree about which hooks match (design Decision 5).
"""

from __future__ import annotations

import re
import signal
import threading
from dataclasses import dataclass
from types import FrameType

from AgentEval.errors import HookExecutionError

__all__ = [
    "MatcherValidation",
    "matcher_matches",
    "validate_matcher",
    "safe_search",
    "MATCHER_ENGINE_NOTE",
    "MAX_MATCHER_SUBJECT_LEN",
]

# --------------------------------------------------------------------------- #
# ReDoS guard (Codex security review HIGH, 2026-07-09)
# --------------------------------------------------------------------------- #
#
# Regex matcher evaluation (`re.search`) runs IN THE AGENTEVAL PARENT PROCESS
# during `Hook.Fire Hook Event` matcher resolution AND `Hook.Validate Matcher
# Syntax`, BEFORE any hook subprocess (and therefore before the hook `timeout`)
# exists. A catastrophic-backtracking matcher such as `(a+)+$` against a
# subject like `"a" * 28 + "!"` would hang the whole test runner with the hook
# `timeout` never applying. `safe_search` bounds that risk two ways:
#
# 1. Subject length is capped — an absurdly long subject is rejected loud.
# 2. On the MAIN thread the search runs under a `SIGALRM`/`setitimer` wall-clock
#    guard that interrupts a runaway `re.search` (empirically reliable in this
#    POSIX-only Phase-1 environment). Off the main thread `signal.signal`
#    raises `ValueError`; there we fall back to the length-bounded search only
#    (documented residual: a pathological matcher can still spin on a worker
#    thread — RF keyword bodies run on the main thread, the common case).

# Absurdly long subjects are rejected rather than searched. Matcher subjects
# are tool names (`Bash`, `mcp__server__tool`, ...) — kilobytes is already
# far past any legitimate value.
MAX_MATCHER_SUBJECT_LEN: int = 4096

# Default wall-clock budget for a single regex search (seconds).
_MATCHER_SEARCH_TIMEOUT_S: float = 1.0


class _RegexTimeoutError(Exception):
    """Internal: raised by the SIGALRM handler to interrupt a runaway search."""


def _raise_regex_timeout(signum: int, frame: FrameType | None) -> None:
    raise _RegexTimeoutError


def safe_search(
    pattern: str | re.Pattern[str],
    subject: str,
    timeout_s: float | None = None,
) -> re.Match[str] | None:
    """`re.search`, guarded against catastrophic-backtracking (ReDoS) hangs.

    Caps subject length, and on the main thread runs the search under a
    ``SIGALRM`` wall-clock timeout. Raises `HookExecutionError` (naming the
    offending pattern) when the subject is over-long or the search exceeds
    ``timeout_s`` — callers get a fast, clear failure instead of a hung runner.

    ``timeout_s`` defaults (``None`` → resolved at call time) to the module-level
    ``_MATCHER_SEARCH_TIMEOUT_S`` so tests can tighten the budget by patching it.
    """
    if timeout_s is None:
        timeout_s = _MATCHER_SEARCH_TIMEOUT_S
    pattern_repr = pattern.pattern if isinstance(pattern, re.Pattern) else pattern
    if len(subject) > MAX_MATCHER_SUBJECT_LEN:
        raise HookExecutionError(
            f"matcher subject is {len(subject)} chars, over the "
            f"{MAX_MATCHER_SUBJECT_LEN}-char cap for regex matcher {pattern_repr!r} "
            "(rejected to prevent a ReDoS hang before the hook timeout applies).",
            field_name="matcher",
            fix_suggestion=(
                "Shorten the matcher subject (tool name), or narrow the regex matcher so it "
                "does not need to scan an over-long subject."
            ),
        )

    def _do_search() -> re.Match[str] | None:
        if isinstance(pattern, re.Pattern):
            return pattern.search(subject)
        return re.search(pattern, subject)

    # Off the main thread `signal.signal` raises ValueError — fall back to the
    # length-bounded search (documented residual risk above).
    if threading.current_thread() is not threading.main_thread():
        return _do_search()

    previous_handler = signal.signal(signal.SIGALRM, _raise_regex_timeout)
    try:
        signal.setitimer(signal.ITIMER_REAL, timeout_s)
        try:
            return _do_search()
        except _RegexTimeoutError:
            raise HookExecutionError(
                f"regex matcher {pattern_repr!r} did not finish within {timeout_s}s against a "
                f"{len(subject)}-char subject — likely catastrophic backtracking (ReDoS). It was "
                "interrupted before it could hang the test runner.",
                field_name="matcher",
                fix_suggestion=(
                    "Rewrite the matcher to avoid nested quantifiers (e.g. `(a+)+`); prefer a simple "
                    "`|`/`,` tool-name list, or an anchored linear-time pattern."
                ),
            ) from None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


# Documented flavor divergence, echoed into `Validate Matcher Syntax` output.
MATCHER_ENGINE_NOTE: str = (
    "Matchers are evaluated with Python `re` (unanchored `re.search`), NOT "
    "JavaScript RegExp as Claude Code itself uses. Constructs that differ "
    "between the two engines (lookbehind flavor, `\\u{...}` escapes, some "
    "named-group syntax) may resolve differently — validate regex matchers "
    "here before relying on them."
)

# Character class that marks a matcher as a SIMPLE exact/list matcher rather
# than a regex: letters, digits, underscore, hyphen, space, comma, pipe.
_SIMPLE_CLASS_RE = re.compile(r"^[A-Za-z0-9_\- ,|]+$")


@dataclass(frozen=True)
class MatcherValidation:
    """Result of validating a single matcher against the dispatch rules.

    Attributes:
        matcher: The original matcher string (or ``None`` for omitted).
        kind: ``"match_all"`` / ``"list"`` / ``"regex"``.
        valid: ``True`` when the matcher compiles under its dispatch branch.
        error: Compile-failure message (offending pattern named) or ``None``.
        subject_matches: ``True`` / ``False`` when a subject was supplied and
            the matcher is valid; ``None`` when no subject was supplied or the
            matcher failed to compile.
    """

    matcher: str | None
    kind: str
    valid: bool
    error: str | None
    subject_matches: bool | None


def _is_match_all(matcher: str | None) -> bool:
    """Return True for the match-all cases: omitted / empty / literal ``*``."""
    return matcher is None or matcher == "" or matcher == "*"


def _split_simple_list(matcher: str) -> list[str]:
    """Split a simple-class matcher on ``|`` and ``,`` into stripped tokens."""
    return [token.strip() for token in re.split(r"[|,]", matcher) if token.strip()]


def matcher_matches(matcher: str | None, subject: str) -> bool:
    """Return whether ``matcher`` matches ``subject`` per the protocol dispatch.

    - Match-all (``*`` / ``""`` / ``None``) → always True.
    - Simple class → exact membership in the ``|``/``,``-split token list.
    - Otherwise → unanchored ``re.search`` of the matcher against ``subject``.

    A regex that fails to compile raises ``re.error`` — callers that want a
    graceful pre-flight should route through `validate_matcher` first. The
    live runner (`Fire Hook Event`) treats a matcher that can't compile as a
    non-match rather than crashing the whole fire.
    """
    if _is_match_all(matcher):
        return True
    assert matcher is not None  # narrowed by _is_match_all
    if _SIMPLE_CLASS_RE.match(matcher):
        return subject in _split_simple_list(matcher)
    return safe_search(matcher, subject) is not None


def validate_matcher(matcher: str | None, subject: str | None = None) -> MatcherValidation:
    """Validate a matcher under the dispatch rules; optionally test a subject.

    Never raises on a bad regex — reports it via ``valid=False`` +
    ``error`` naming the offending pattern (design Decision 5 / spec
    "Invalid regex reports the offending pattern").
    """
    if _is_match_all(matcher):
        subject_matches = True if subject is not None else None
        return MatcherValidation(matcher, "match_all", True, None, subject_matches)

    assert matcher is not None
    if _SIMPLE_CLASS_RE.match(matcher):
        subject_matches = (subject in _split_simple_list(matcher)) if subject is not None else None
        return MatcherValidation(matcher, "list", True, None, subject_matches)

    # Regex path.
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
