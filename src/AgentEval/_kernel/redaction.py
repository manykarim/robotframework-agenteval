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

"""Credential redaction for agenteval traces (NFR-SEC-01 / FR38a).

Two-layer API:

1. **Primitive functions** for use anywhere text or structured data flows:
   `redact(text)`, `redact_dict(d)`, `register_pattern(regex)`. These are the
   building blocks consumed by the SpanProcessor + by non-OTel paths (logging,
   JSONL serialization, error message construction).

2. **`RedactionProcessor(SpanProcessor)`** — the OTel SpanProcessor that wires
   redaction into the TracerProvider pipeline per architecture L679 + L1193:
   `RedactionProcessor → InMemoryExporter` chain. Single choke point for
   credential scrubbing on every span attribute. Epic 5 Story 5.1's
   TracerProvider configuration adds this processor BEFORE the
   BatchSpanProcessor-wrapped exporter.

The pattern set covers common credential shapes:

    - OpenAI / Anthropic API key prefix: `sk-...`
    - HTTP bearer tokens: `Bearer <token>`
    - Environment-variable-style credential leaks: `ANTHROPIC_API_KEY=...`,
      `OPENAI_API_KEY=...`
    - Slack bot tokens: `xoxb-...`
    - JWT shape (3 base64-url-encoded segments joined by `.`): `eyJ...`

Callers can extend via `register_pattern(regex)`. **Thread-safety caveat:**
Phase-1 implementation is NOT lock-protected; callers register at library
import time (single-threaded), NOT per-test from concurrent pabot workers.

`redaction_policy_hash()` returns a stable SHA-256 hex of the active pattern
set; `RunManifest.redaction_policy_hash` per FR39 consumes this.

References:
    - PRD §FR38a — credential redaction at trace-emission time
    - PRD §NFR-SEC-01 — no credentials in published traces
    - architecture L679 — `RedactionProcessor → InMemoryExporter` SpanProcessor chain
    - architecture L1193 — `_kernel/redaction.py` location
    - docs/contracts/evidence-block-format.md — downstream consumer of redacted spans
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from opentelemetry.context import Context  # OTel's own context, NOT contextvars.Context
    from opentelemetry.sdk.trace import ReadableSpan, Span
    from opentelemetry.sdk.trace import SpanProcessor as _OTelSpanProcessor
else:
    from opentelemetry.sdk.trace import SpanProcessor as _OTelSpanProcessor

__all__ = [
    "DEFAULT_PATTERNS",
    "redact",
    "redact_dict",
    "register_pattern",
    "redaction_policy_hash",
    "RedactionProcessor",
]


# Module-level mutable list — extended via register_pattern().
# Thread-safety caveat documented in module docstring + register_pattern().
DEFAULT_PATTERNS: list[re.Pattern[str]] = [
    # OpenAI / Anthropic API key prefixes. Two patterns for full coverage:
    #   - `sk-` followed by 16+ chars (covers OpenAI sk-AbCdEfGh1234567890XYZ shape)
    #   - `sk-ant-` followed by 8+ chars (covers Anthropic sk-ant-foo123 short shape)
    # The dedicated sk-ant- pattern fixes M_R2 (sk- 16+ floor missed naked sk-ant-foo123).
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]+"),
    # HTTP Bearer tokens. Require 20+ chars after `Bearer ` to avoid M_R3
    # over-redaction of prose like "Bearer expected at line 3".
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_\-\.=]{20,}"),
    # Environment-variable-style credential leaks.
    re.compile(r"(?i)ANTHROPIC_API_KEY=\S+"),
    re.compile(r"(?i)OPENAI_API_KEY=\S+"),
    # AWS access keys (M_R7).
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # GitHub personal access tokens, OAuth tokens, server tokens, user tokens (M_R7).
    re.compile(r"gh[psoru]_[A-Za-z0-9]{36}"),
    # HuggingFace user tokens (M_R7).
    re.compile(r"hf_[A-Za-z0-9]{34}"),
    # Slack token family: bot (xoxb-), app (xoxa-), user (xoxp-), refresh (xoxr-),
    # session (xoxs-). M_R7 expands the original xoxb-only pattern.
    re.compile(r"xox[abprs]-[A-Za-z0-9_\-]+"),
    # JWT shape: 3 base64-url-encoded segments joined by `.`. Anchor on the
    # standard JWT header prefix `eyJ` to avoid false positives on arbitrary
    # 3-segment dotted identifiers. M_R8 adds `=` to the charset for
    # standard-base64-padded variants some libraries leak.
    re.compile(r"eyJ[A-Za-z0-9_\-=]+\.[A-Za-z0-9_\-=]+\.[A-Za-z0-9_\-=]+"),
]

# Replacement string used by all patterns. Kept as a module constant so the
# RunManifest hash + tests can assert the literal.
_REDACTED_REPLACEMENT = "[REDACTED]"

# OTel span attribute keys that the RedactionProcessor scrubs on every span.
# Documented as part of AC-1b.2.5; callers wanting additional keys extend via
# subclassing RedactionProcessor and overriding `_SENSITIVE_ATTRIBUTE_KEYS`.
_SENSITIVE_ATTRIBUTE_KEYS: tuple[str, ...] = (
    "gen_ai.request.messages",
    "gen_ai.response.text",
    "gen_ai.tool.args",
    "agenteval.tool.args",
    "agenteval.tool.result",
)


def redact(text: str, patterns: list[re.Pattern[str]] | None = None) -> str:
    """Scrub known credential patterns from text.

    Args:
        text: Input string to scan.
        patterns: Optional override of the pattern list; defaults to
            `DEFAULT_PATTERNS`.

    Returns:
        The text with every pattern match replaced by `"[REDACTED]"`. Idempotent
        (re-applying produces the same output).
    """
    active_patterns = patterns if patterns is not None else DEFAULT_PATTERNS
    for pattern in active_patterns:
        text = pattern.sub(_REDACTED_REPLACEMENT, text)
    return text


def redact_dict(d: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively scrub credential patterns from a nested data structure.

    Behavior:
        - `str` values get `redact()`.
        - Nested `dict` / `list` / `tuple` get recursive treatment.
        - Other types pass through unchanged.

    Args:
        d: Input mapping (treated as read-only; a new dict is returned).

    Returns:
        New dict with the same key structure and scrubbed string values.
    """
    return {k: _redact_value(v) for k, v in d.items()}


def _redact_value(value: Any) -> Any:
    """Recursive helper for redact_dict — handles arbitrary nested types.

    H_R12 fix (Story 1b.2 code review): recurse on the broader `Mapping` type
    (not just `dict`), so nested `BoundedAttributes` / `MappingProxyType` /
    `frozendict` payloads also get scrubbed.
    """
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, Mapping):
        return redact_dict(value)
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(v) for v in value)
    return value


def register_pattern(regex: str) -> None:
    """Append a compiled pattern to `DEFAULT_PATTERNS`.

    Thread-safety: NOT lock-protected. Callers MUST register at library
    import time (single-threaded), not per-test from concurrent pabot
    workers. Phase-1 simplification.
    """
    DEFAULT_PATTERNS.append(re.compile(regex))


def redaction_policy_hash() -> str:
    """Return a stable SHA-256 hex of the current `DEFAULT_PATTERNS` set.

    Consumed by `RunManifest.redaction_policy_hash` per FR39 so downstream
    consumers can verify the redaction policy in effect at run time.

    H_R9 fix (Story 1b.2 code review): includes `p.flags` in the hash input
    so semantically-identical pattern strings with different flags (e.g.,
    `re.compile("foo", re.IGNORECASE)` vs `re.compile("(?i)foo")`) produce
    different hashes. Without this, a future flag change could silently
    break FR39 reproducibility.
    """
    joined = "|".join(f"{p.pattern}|flags={p.flags}" for p in DEFAULT_PATTERNS)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class RedactionProcessor(_OTelSpanProcessor):
    """OTel SpanProcessor that scrubs credential patterns from span attributes.

    Wires `redact()` / `redact_dict()` into the TracerProvider pipeline at
    `on_end(span)` time per architecture L679 chain order:

        RedactionProcessor → BatchSpanProcessor(InMemoryExporter)

    Epic 5 Story 5.1's TracerProvider configuration adds this processor
    BEFORE the exporter so scrubbing happens once on every span — single
    choke point for NFR-SEC-01 compliance.

    Scrubbed attribute keys (per `_SENSITIVE_ATTRIBUTE_KEYS`):
        - `gen_ai.request.messages` — LLM prompt content
        - `gen_ai.response.text` — LLM response content
        - `gen_ai.tool.args` — tool-call argument blob (OTel GenAI semconv)
        - `agenteval.tool.args` — agenteval-specific tool args
        - `agenteval.tool.result` — agenteval-specific tool result

    Phase-1 implementation mutates span.attributes in-place. The OTel SDK's
    `_Span` (the runtime type of `ReadableSpan` during `on_end`) exposes
    `_attributes` as a mutable mapping — we set values via `set_attribute(k,
    v)` which goes through the SDK's public API.
    """

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:  # noqa: ARG002 — SpanProcessor protocol
        """No-op at span start; nothing to redact until attributes are populated."""
        return None

    def on_end(self, span: ReadableSpan) -> None:
        """Scrub sensitive attributes in-place before the span flushes downstream.

        H_R1 fix (Story 1b.2 code review — 4-way reviewer confirmation):
        Real OTel `ReadableSpan.attributes` is `BoundedAttributes` (a
        `MappingProxyType`-backed read-only Mapping). The earlier
        `attributes[key] = new_value` path passed mock tests with plain dicts
        but raised `TypeError`/silently no-op'd against real spans. The fix
        mutates the underlying `_dict` of the SDK's `_Span._attributes`
        directly — opentelemetry-sdk 1.20+ keeps this contract stable;
        pyproject.toml pins the range.

        Sequence-typed credentials (Blind 2's NFR-SEC-01 concern): a list/tuple
        of strings now gets element-wise `redact()` instead of falling through.
        """
        attributes = span.attributes
        if attributes is None:
            return
        for key in _SENSITIVE_ATTRIBUTE_KEYS:
            if key not in attributes:
                continue
            value = attributes[key]
            new_value: Any
            if isinstance(value, str):
                new_value = redact(value)
            elif isinstance(value, Mapping):
                new_value = redact_dict(value)
            elif isinstance(value, (list, tuple)) and value and all(isinstance(v, str) for v in value):
                # Real-OTel-shaped Sequence[str] (gen_ai.request.messages is
                # commonly emitted as a list). Previously these fell through
                # unredacted — Blind 2's NFR-SEC-01 concern.
                redacted_seq = [redact(v) for v in value]
                new_value = tuple(redacted_seq) if isinstance(value, tuple) else redacted_seq
            else:
                # Non-text attributes (int, bool, float, non-string sequences)
                # — nothing credential-shaped, leave alone.
                continue
            _set_span_attribute_in_place(span, key, new_value)

    def shutdown(self) -> None:
        """No buffered state; no-op."""
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002 — SpanProcessor protocol
        """No buffered state; always returns True."""
        return True


def _set_span_attribute_in_place(span: ReadableSpan, key: str, value: Any) -> None:
    """Mutate a ReadableSpan's attribute in-place, supporting both real OTel + mock fixtures.

    Real OTel SDK: `span._attributes` is `BoundedAttributes` whose underlying
    storage is `_dict` (per opentelemetry-sdk 1.20+ source). Test mocks
    typically use a plain `dict` for both `.attributes` and `._attributes`.
    This helper handles both shapes; if neither works, surfaces a UserWarning
    so SDK refactors don't silently fail.
    """
    underlying = getattr(span, "_attributes", None)
    # Real BoundedAttributes path.
    if underlying is not None and hasattr(underlying, "_dict"):
        underlying._dict[key] = value
        return
    # Test mock path: plain dict assignment.
    if underlying is not None:
        try:
            underlying[key] = value
            return
        except TypeError:
            pass
    # Final fallback: try mutating the public `.attributes` (rare path).
    attrs = getattr(span, "attributes", None)
    if attrs is not None:
        try:
            attrs[key] = value
            return
        except TypeError:
            pass
    # Read-only view we can't penetrate; surface a warning so SDK refactors
    # don't silently leak credentials.
    import warnings as _warnings

    _warnings.warn(
        f"RedactionProcessor: unable to mutate span attribute {key!r} "
        "(OTel SDK contract may have changed; credentials may leak)",
        UserWarning,
        stacklevel=2,
    )
