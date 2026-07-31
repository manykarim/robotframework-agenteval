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

"""The one home for the run-failure taxonomy an agent run can raise.

``classify_run_exception`` maps an exception raised by *any* adapter family into a
skippable category (``budget_exceeded`` / ``provider_error`` / ``timeout``) or
``None``. ``None`` means "not a known transient/budget condition" - a genuine
config/auth/harness fault the caller SHOULD re-raise, never skip.

It keys on **structured signals** - an HTTP ``status_code``, an exception
``__cause__`` type, ``isinstance`` against the provider SDKs' typed bases - not on
exception-class-name string matching, so it distinguishes a retryable 429 from a
non-retryable 401 (which must fail loud). The heavy SDKs are imported lazily inside
the function so this module stays free of the ``[agent]``/``[llm]`` extras and the
dependency direction is preserved.
"""

from __future__ import annotations

import subprocess
from typing import Literal

from AgentEval._core.errors import AdapterError

__all__ = ["RunFailureCategory", "classify_run_exception"]

RunFailureCategory = Literal["budget_exceeded", "provider_error", "timeout"]

# Transient 4xx statuses worth a retry/skip (request timeout / conflict / rate
# limit). Any 5xx is also retryable (see `_retryable_status`), matching openai's
# "all >=500 are server-side" rule and covering Anthropic's 529 Overloaded. Every
# other 4xx (400/401/403/404/422) is a non-retryable config/auth fault that raises.
_RETRYABLE_STATUS = frozenset({408, 409, 429})


def classify_run_exception(exc: BaseException) -> RunFailureCategory | None:
    """Classify a run failure into a skippable category, or ``None`` to raise.

    Tries each adapter family's typed signals in turn; the families raise disjoint
    exception types, so order does not cause double-classification. Returns ``None``
    for anything not recognized as transient/budget (the safe default: fail loud).
    """
    for classifier in (_classify_in_process, _classify_generic, _classify_cli):
        category = classifier(exc)
        if category is not None:
            return category
    return None


def _retryable_status(code: object) -> bool:
    """True when an HTTP status is worth a retry/skip rather than a hard failure.

    A transient 4xx (in ``_RETRYABLE_STATUS``) or ANY 5xx server-side error - so the
    in-process ``ModelHTTPError`` path and the generic ``InternalServerError`` path
    agree on every 5xx (incl. 529 Overloaded), not just a hand-picked subset.
    """
    if not isinstance(code, (int, str)):
        return False
    try:
        status = int(code)
    except (TypeError, ValueError):
        return False
    return status in _RETRYABLE_STATUS or status >= 500


def _classify_in_process(exc: BaseException) -> RunFailureCategory | None:
    """pydantic-ai wraps provider errors, so key on its typed exceptions."""
    try:
        from pydantic_ai.exceptions import (
            ModelAPIError,
            ModelHTTPError,
            UnexpectedModelBehavior,
            UsageLimitExceeded,
        )
    except ImportError:
        return None

    if isinstance(exc, UsageLimitExceeded):
        return "budget_exceeded"
    # ModelHTTPError subclasses ModelAPIError - check it first so the status branch
    # wins over the blanket ModelAPIError -> provider_error below.
    if isinstance(exc, ModelHTTPError):
        return "provider_error" if _retryable_status(getattr(exc, "status_code", None)) else None
    if isinstance(exc, ModelAPIError):
        return "provider_error"
    if isinstance(exc, UnexpectedModelBehavior):
        # Overloaded class: only the validated-provider-response subset is transient;
        # everything else (a genuine prompt/harness bug) must raise. The substring is
        # pydantic-ai's OpenAI-compatible-model wording; this is deliberately narrow
        # and fails safe (over-raises rather than silently skipping) for other model
        # backends whose malformed-response wording differs.
        return "provider_error" if "Invalid response from" in str(exc) else None
    return None


def _classify_generic(exc: BaseException) -> RunFailureCategory | None:
    """The LiteLLM one-shot path raises litellm errors, which subclass openai's.

    litellm hard-depends on openai and its exception classes subclass the openai
    namesakes, so keying on the openai bases catches the litellm errors too - no
    separate litellm import needed (which would also fire heavy import warnings on
    the error path).
    """
    transient_bases: tuple[type, ...] = ()
    status_error_base: type | None = None
    try:
        import openai

        transient_bases = (
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.InternalServerError,
        )
        status_error_base = openai.APIStatusError
    except ImportError:
        return None

    if isinstance(exc, transient_bases):
        return "provider_error"
    # A status-bearing error with a retryable code; a non-retryable one (401/403/…)
    # returns None so it raises.
    if status_error_base is not None and isinstance(exc, status_error_base):
        return "provider_error" if _retryable_status(getattr(exc, "status_code", None)) else None
    return None


def _classify_cli(exc: BaseException) -> RunFailureCategory | None:
    """CLI adapters raise ``AdapterError``; a timeout chains from ``TimeoutExpired``."""
    if isinstance(exc, AdapterError) and isinstance(exc.__cause__, subprocess.TimeoutExpired):
        return "timeout"
    return None
