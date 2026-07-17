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

"""Tests for the slim error hierarchy and the exit-code table."""

from __future__ import annotations

from AgentEval._core import errors
from AgentEval._core.errors import (
    EXIT_CODE_FALLBACK,
    EXIT_CODES,
    AgentEvalError,
    IncompleteTraceError,
    InvalidConfigError,
    MissingExtraError,
    error_code_to_exit_code,
)


def _leaf_classes() -> list[type[AgentEvalError]]:
    return [
        obj
        for obj in vars(errors).values()
        if isinstance(obj, type) and issubclass(obj, AgentEvalError) and obj is not AgentEvalError
    ]


def test_hierarchy_is_slim() -> None:
    # ~12 leaves, one base - not the old 40+.
    leaves = _leaf_classes()
    assert 10 <= len(leaves) <= 14
    for leaf in leaves:
        assert issubclass(leaf, AgentEvalError)


def test_error_code_prefixes_str() -> None:
    exc = IncompleteTraceError("trace too thin")
    assert str(exc) == "INCOMPLETE_TRACE: trace too thin"


def test_base_without_code_has_no_prefix() -> None:
    assert str(AgentEvalError("bare")) == "bare"


def test_catch_all_via_base() -> None:
    try:
        raise MissingExtraError("need it", extra="llm")
    except AgentEvalError as exc:
        assert isinstance(exc, MissingExtraError)
        assert exc.extra == "llm"


def test_every_leaf_code_is_in_exit_table() -> None:
    leaf_codes = {leaf.error_code for leaf in _leaf_classes()}
    assert leaf_codes == set(EXIT_CODES), (
        "exit-code table drifted from the leaf classes; "
        f"table-only={set(EXIT_CODES) - leaf_codes}, leaf-only={leaf_codes - set(EXIT_CODES)}"
    )


def test_exit_code_lookup() -> None:
    assert error_code_to_exit_code("INCOMPLETE_TRACE") == 67
    assert error_code_to_exit_code("MISSING_EXTRA") == 78
    assert error_code_to_exit_code("BUDGET_EXCEEDED") == 66


def test_exit_code_fallback_for_unknown_and_none() -> None:
    assert error_code_to_exit_code("NOPE") == EXIT_CODE_FALLBACK
    assert error_code_to_exit_code(None) == EXIT_CODE_FALLBACK
    assert error_code_to_exit_code("") == EXIT_CODE_FALLBACK


def test_structured_config_error_context() -> None:
    exc = InvalidConfigError("bad", file_path="/x.json", field="/hooks/0", fix="fix it")
    assert exc.file_path == "/x.json"
    assert exc.field == "/hooks/0"
    assert exc.fix == "fix it"
    assert str(exc).startswith("INVALID_CONFIG: ")


def test_invalid_config_error_str_carries_context() -> None:
    exc = InvalidConfigError("bad", file_path="/x.json", fix="fix it")
    rendered = str(exc)
    assert rendered.startswith("INVALID_CONFIG: ")
    assert "/x.json" in rendered
    assert "fix it" in rendered
