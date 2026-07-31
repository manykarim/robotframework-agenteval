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

"""The run-failure classifier: structured signals, not class-name strings."""

from __future__ import annotations

import subprocess

import pytest

from AgentEval._core.errors import AdapterError, MissingExtraError, TierViolationError
from AgentEval._core.run_classifier import classify_run_exception


def test_config_and_unknown_faults_are_not_classified() -> None:
    # None => "raise, do not skip" (a genuine config/harness fault).
    assert classify_run_exception(MissingExtraError("need [agent]", extra="agent")) is None
    assert classify_run_exception(TierViolationError("no model here")) is None
    assert classify_run_exception(ValueError("something else")) is None


def test_cli_timeout_vs_binary_missing() -> None:
    timeout = AdapterError("'kilo' CLI exceeded the 600s timeout")
    timeout.__cause__ = subprocess.TimeoutExpired("kilo", 600)
    assert classify_run_exception(timeout) == "timeout"

    # binary-missing AdapterError has no TimeoutExpired cause -> raise, not skip.
    binary_missing = AdapterError("codex binary not found; install with ...")
    assert binary_missing.__cause__ is None
    assert classify_run_exception(binary_missing) is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, "provider_error"),
        (503, "provider_error"),
        (500, "provider_error"),
        (408, "provider_error"),
        # Any 5xx is retryable, so the in-process ModelHTTPError path agrees with the
        # generic InternalServerError path (incl. Anthropic's 529 Overloaded).
        (529, "provider_error"),
        (507, "provider_error"),
    ],
)
def test_in_process_retryable_http_is_provider_error(status: int, expected: str) -> None:
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.exceptions import ModelHTTPError

    assert classify_run_exception(ModelHTTPError(status, "m")) == expected


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_in_process_non_retryable_http_raises(status: int) -> None:
    # THE load-bearing case: an auth/config HTTP fault must NOT be classified as a
    # skippable transient, even though it is a ModelHTTPError.
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.exceptions import ModelHTTPError

    assert classify_run_exception(ModelHTTPError(status, "m")) is None


def test_in_process_budget_and_api_and_behavior() -> None:
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior, UsageLimitExceeded

    assert classify_run_exception(UsageLimitExceeded("request_limit of 50")) == "budget_exceeded"
    assert classify_run_exception(ModelAPIError("m", "connection reset")) == "provider_error"
    # UnexpectedModelBehavior straddles the boundary: only the validated-response
    # subset is transient; a genuine tool-loop bug must raise.
    assert classify_run_exception(UnexpectedModelBehavior("Invalid response from provider")) == "provider_error"
    assert classify_run_exception(UnexpectedModelBehavior("Exceeded maximum retries")) is None


def test_generic_litellm_transient_is_provider_error() -> None:
    pytest.importorskip("litellm")
    import litellm

    assert classify_run_exception(litellm.RateLimitError("rate limited", "gpt-4o", "openai")) == "provider_error"
