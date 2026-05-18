"""Unit tests for _kernel/redaction.py (AC-1b.2.4, AC-1b.2.5)."""

from __future__ import annotations

import re
from typing import Any
from unittest.mock import MagicMock

from AgentEval._kernel.redaction import (
    DEFAULT_PATTERNS,
    RedactionProcessor,
    redact,
    redact_dict,
    redaction_policy_hash,
    register_pattern,
)

# ---- AC-1b.2.4: redact() default patterns ------------------------------ #


def test_redact_openai_anthropic_key_prefix() -> None:
    text = "My key is sk-AbCdEfGh1234567890XYZxyz end"
    assert "sk-AbCdEfGh" not in redact(text)
    assert "[REDACTED]" in redact(text)


def test_redact_bearer_token() -> None:
    text = "Authorization: Bearer abc.def.ghi-12345"
    out = redact(text)
    assert "abc.def.ghi-12345" not in out
    assert "[REDACTED]" in out


def test_redact_bearer_token_case_insensitive() -> None:
    out = redact("bearer xyzABC123")
    assert "[REDACTED]" in out
    assert "xyzABC123" not in out


def test_redact_anthropic_api_key_env_var() -> None:
    text = "ANTHROPIC_API_KEY=sk-ant-foo123"
    out = redact(text)
    assert "sk-ant-foo123" not in out


def test_redact_openai_api_key_env_var() -> None:
    text = "openai_api_key=sk-foo"
    out = redact(text)
    assert "sk-foo" not in out
    assert "[REDACTED]" in out


def test_redact_slack_bot_token() -> None:
    text = "Slack bot: xoxb-12345-67890-abcdef"
    out = redact(text)
    assert "xoxb-12345-67890-abcdef" not in out


def test_redact_jwt_shape() -> None:
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    text = f"Token: {jwt}"
    out = redact(text)
    assert jwt not in out
    assert "[REDACTED]" in out


def test_redact_plain_text_unchanged() -> None:
    text = "Just a normal sentence with no credentials."
    assert redact(text) == text


def test_redact_idempotent() -> None:
    text = "API key: sk-AbCdEfGh1234567890XYZ"
    once = redact(text)
    twice = redact(once)
    assert once == twice


def test_redact_custom_patterns_override_default() -> None:
    """Passing patterns= replaces (not augments) the default set."""
    custom = [re.compile(r"hello")]
    out = redact("hello sk-AbCdEfGh1234567890XYZxyz hello", patterns=custom)
    # `hello` redacted via custom; `sk-...` NOT redacted because default not active.
    assert "hello" not in out
    assert "sk-AbCdEfGh" in out


# ---- AC-1b.2.4: redact_dict() recursive scrubbing ---------------------- #


def test_redact_dict_top_level_strings() -> None:
    d = {"safe": "hello", "leak": "key=sk-AbCdEfGh1234567890XYZ"}
    out = redact_dict(d)
    assert out["safe"] == "hello"
    assert "sk-AbCdEfGh" not in out["leak"]


def test_redact_dict_nested_dicts() -> None:
    d = {"level1": {"level2": {"credentials": "Bearer secrettoken123"}}}
    out = redact_dict(d)
    assert "secrettoken123" not in out["level1"]["level2"]["credentials"]


def test_redact_dict_list_and_tuple_recursion() -> None:
    d = {"keys": ["sk-AbCdEfGh1234567890XYZ", "safe"]}
    out = redact_dict(d)
    assert "sk-AbCdEfGh" not in out["keys"][0]
    assert out["keys"][1] == "safe"

    d2 = {"creds": ("sk-FoooooooooooooooBar", "ok")}
    out2 = redact_dict(d2)
    assert "sk-Fooo" not in out2["creds"][0]


def test_redact_dict_non_string_passthrough() -> None:
    d = {"count": 42, "flag": True, "ratio": 3.14, "none": None}
    out = redact_dict(d)
    assert out["count"] == 42
    assert out["flag"] is True
    assert out["ratio"] == 3.14
    assert out["none"] is None


# ---- AC-1b.2.4: register_pattern() extension --------------------------- #


def test_register_pattern_appends_to_default_list() -> None:
    original_count = len(DEFAULT_PATTERNS)
    try:
        register_pattern(r"PROJECT_SECRET_[A-Z]+")
        assert len(DEFAULT_PATTERNS) == original_count + 1
        out = redact("PROJECT_SECRET_FOO appears here")
        assert "[REDACTED]" in out
    finally:
        # Restore default state — tests must not bleed pattern state.
        DEFAULT_PATTERNS.pop()


# ---- AC-1b.2.4: redaction_policy_hash() stability ---------------------- #


def test_redaction_policy_hash_is_stable_across_calls() -> None:
    h1 = redaction_policy_hash()
    h2 = redaction_policy_hash()
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_redaction_policy_hash_changes_when_pattern_added() -> None:
    h1 = redaction_policy_hash()
    try:
        register_pattern(r"HASH_TEST_[A-Z]+")
        h2 = redaction_policy_hash()
        assert h1 != h2
    finally:
        DEFAULT_PATTERNS.pop()


# ---- AC-1b.2.5: RedactionProcessor on_end mutation --------------------- #


def _make_span_mock(attributes: dict[str, Any]) -> Any:
    """Build a mock span with a mutable `_attributes` + read-only `attributes` view."""
    span = MagicMock()
    # OTel SDK exposes `attributes` as a read-only view of `_attributes`.
    span.attributes = attributes
    span._attributes = attributes
    return span


def test_redaction_processor_on_end_scrubs_gen_ai_request_messages() -> None:
    attrs = {"gen_ai.request.messages": "User said: my key is sk-AbCdEfGh1234567890XYZxyz"}
    span = _make_span_mock(attrs)
    RedactionProcessor().on_end(span)
    assert "sk-AbCdEfGh" not in attrs["gen_ai.request.messages"]


def test_redaction_processor_on_end_scrubs_agenteval_tool_args_dict() -> None:
    attrs = {"agenteval.tool.args": {"command": "echo $ANTHROPIC_API_KEY=sk-leak"}}
    span = _make_span_mock(attrs)
    RedactionProcessor().on_end(span)
    assert "sk-leak" not in str(attrs["agenteval.tool.args"])


def test_redaction_processor_on_end_skips_non_string_non_dict() -> None:
    """Numeric / bool attributes are left alone."""
    attrs = {"gen_ai.tool.args": 42, "agenteval.tool.result": True}
    span = _make_span_mock(attrs)
    RedactionProcessor().on_end(span)
    assert attrs["gen_ai.tool.args"] == 42
    assert attrs["agenteval.tool.result"] is True


def test_redaction_processor_on_end_missing_keys_noop() -> None:
    """Spans without sensitive keys should not be modified."""
    attrs = {"some.other.key": "value"}
    span = _make_span_mock(attrs)
    RedactionProcessor().on_end(span)
    assert attrs == {"some.other.key": "value"}


def test_redaction_processor_on_start_is_noop() -> None:
    """on_start should not touch span data."""
    attrs = {"gen_ai.request.messages": "User said: sk-AbCdEfGh1234567890XYZ"}
    span = _make_span_mock(attrs)
    RedactionProcessor().on_start(span)
    # No redaction at start; attributes unchanged.
    assert "sk-AbCdEfGh" in attrs["gen_ai.request.messages"]


def test_redaction_processor_shutdown_and_flush_are_noops() -> None:
    proc = RedactionProcessor()
    assert proc.shutdown() is None
    assert proc.force_flush() is True
    assert proc.force_flush(timeout_millis=1000) is True


def test_redaction_processor_on_end_handles_none_attributes() -> None:
    """A span with `attributes=None` (rare but possible) must not crash."""
    span = MagicMock()
    span.attributes = None
    span._attributes = None
    # Should not raise.
    RedactionProcessor().on_end(span)
