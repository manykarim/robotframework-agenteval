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
    # Story 1b.2 M_R3 fix: Bearer pattern now requires 20+ chars after `Bearer `
    # (avoids over-redacting "Bearer expected at line 3").
    text = "Authorization: Bearer abcdef.ghi-12345-jklmn"
    out = redact(text)
    assert "abcdef.ghi-12345-jklmn" not in out
    assert "[REDACTED]" in out


def test_redact_bearer_token_case_insensitive() -> None:
    # 20+ chars after `bearer ` per M_R3 length floor.
    out = redact("bearer xyzABC1234567890ABCDEFG")
    assert "[REDACTED]" in out
    assert "xyzABC1234567890ABCDEFG" not in out


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
    d = {"level1": {"level2": {"credentials": "Bearer secrettoken123abcdefghij"}}}
    out = redact_dict(d)
    assert "secrettoken123abcdefghij" not in out["level1"]["level2"]["credentials"]


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


# ========================================================================= #
# Story 1b.2 code-review patches — new test coverage                       #
# ========================================================================= #


# ---- H_R1: RedactionProcessor against real OTel TracerProvider ---- #


def test_h_r1_redaction_processor_integration_real_otel() -> None:
    """H_R1: integration test verifying RedactionProcessor mutates span attributes
    against the REAL OTel TracerProvider → SimpleSpanProcessor(InMemorySpanExporter)
    chain — not just MagicMock fixtures. Pre-fix this raised TypeError; the
    `_set_span_attribute_in_place` helper handles BoundedAttributes correctly.
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    # Add RedactionProcessor FIRST per architecture L679 chain order.
    provider.add_span_processor(RedactionProcessor())
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tr = provider.get_tracer("agenteval.test")

    span = tr.start_span(
        "execute_tool",
        attributes={
            "gen_ai.request.messages": "User said: my key is sk-AbCdEfGh1234567890XYZxyz",
            "agenteval.tool.args": "command=Bearer ABCDEFGHIJ1234567890",
        },
    )
    span.end()

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    final_attrs = finished[0].attributes
    assert final_attrs is not None
    # Credentials scrubbed; [REDACTED] present.
    assert "sk-AbCdEfGh" not in final_attrs["gen_ai.request.messages"]
    assert "[REDACTED]" in final_attrs["gen_ai.request.messages"]
    assert "ABCDEFGHIJ1234567890" not in final_attrs["agenteval.tool.args"]


def test_h_r1_redaction_processor_handles_sequence_str_attribute() -> None:
    """H_R1/Blind 2: Sequence[str] attributes (gen_ai.request.messages can be a list)
    must be element-wise redacted, not silently dropped.
    """
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(RedactionProcessor())
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tr = provider.get_tracer("agenteval.test")

    span = tr.start_span(
        "chat",
        attributes={
            "gen_ai.request.messages": ("Hello", "sk-AbCdEfGh1234567890XYZxyz", "goodbye"),
        },
    )
    span.end()

    final_attrs = exporter.get_finished_spans()[0].attributes
    assert final_attrs is not None
    messages = final_attrs["gen_ai.request.messages"]
    assert "sk-AbCdEfGh" not in str(messages)
    assert "[REDACTED]" in str(messages)


# ---- M_R2: sk-ant- pattern catches naked Anthropic keys ---- #


def test_m_r2_redact_naked_sk_ant_key() -> None:
    """M_R2: standalone `sk-ant-foo123` without env-var prefix must be scrubbed."""
    out = redact("Anthropic key leaked: sk-ant-foo123 in error message")
    assert "sk-ant-foo123" not in out
    assert "[REDACTED]" in out


# ---- M_R3: Bearer doesn't over-redact prose ---- #


def test_m_r3_redact_bearer_prose_not_over_redacted() -> None:
    """M_R3: 'Bearer expected at line 3' (prose) MUST NOT be redacted."""
    out = redact("Bearer expected at line 3")
    # The 20-char minimum on the Bearer pattern means `expected` (8 chars) isn't matched.
    assert out == "Bearer expected at line 3", f"over-redacted: {out!r}"


def test_m_r3_redact_real_bearer_token_still_redacted() -> None:
    """Confirm real bearer tokens (20+ chars) still match."""
    out = redact("Authorization: Bearer abcdef1234567890ABCDEFGH")
    assert "abcdef1234567890ABCDEFGH" not in out
    assert "[REDACTED]" in out


# ---- M_R7: new credential pattern coverage ---- #


def test_m_r7_redact_aws_access_key() -> None:
    out = redact("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE in config")
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert "[REDACTED]" in out


def test_m_r7_redact_github_personal_access_token() -> None:
    pat = "ghp_AbCdEf1234567890AbCdEf1234567890AbCd"  # 36 chars after ghp_
    out = redact(f"GitHub PAT leak: {pat}")
    assert pat not in out
    assert "[REDACTED]" in out


def test_m_r7_redact_huggingface_token() -> None:
    pat = "hf_AbCdEf1234567890AbCdEf1234567890AbCd"  # 34 chars after hf_
    out = redact(f"HuggingFace: {pat}")
    assert pat not in out
    assert "[REDACTED]" in out


def test_m_r7_redact_slack_family() -> None:
    """Original test covered xoxb-; M_R7 expands to xoxa/xoxp/xoxr/xoxs."""
    for prefix in ("xoxa-", "xoxp-", "xoxr-", "xoxs-"):
        token = f"{prefix}1234-5678-abcdef"
        out = redact(f"Slack token: {token}")
        assert token not in out, f"{prefix} not redacted"


# ---- M_R8: JWT with standard-base64 padding ---- #


def test_m_r8_redact_jwt_with_base64_padding() -> None:
    """M_R8: JWT pattern accepts `=` padding for standard-base64-encoded segments."""
    jwt = "eyJhbGciOiJIUzI1NiJ9==.eyJzdWIiOiIxMjMifQ==.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c="
    out = redact(f"JWT: {jwt}")
    assert jwt not in out


# ---- H_R9: redaction_policy_hash includes flags ---- #


def test_h_r9_redaction_policy_hash_includes_flags() -> None:
    """H_R9: identical pattern strings with different flags produce DIFFERENT hashes."""
    original_count = len(DEFAULT_PATTERNS)
    try:
        h1 = redaction_policy_hash()
        # Add an IGNORECASE pattern, then check.
        DEFAULT_PATTERNS.append(re.compile(r"customfoo", re.IGNORECASE))
        h2 = redaction_policy_hash()
        assert h1 != h2

        # Swap to inline-flag variant (different flags value, same `.pattern`).
        DEFAULT_PATTERNS.pop()
        DEFAULT_PATTERNS.append(re.compile(r"(?i)customfoo"))
        h3 = redaction_policy_hash()
        # Different flags between h2 and h3 → different hash even though
        # behavior is semantically equivalent.
        assert h3 != h2
    finally:
        # Restore.
        while len(DEFAULT_PATTERNS) > original_count:
            DEFAULT_PATTERNS.pop()


# ---- H_R12: redact_dict recurses on Mapping (not just dict) ---- #


def test_h_r12_redact_dict_recurses_into_mappingproxytype() -> None:
    """H_R12: nested MappingProxyType (not just dict) must get scrubbed."""
    from types import MappingProxyType

    nested = MappingProxyType({"secret": "Bearer ABCDEFGHIJ1234567890ABCDEFG"})
    d = {"level1": nested}
    out = redact_dict(d)
    assert "ABCDEFGHIJ1234567890ABCDEFG" not in str(out["level1"])
