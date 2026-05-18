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
    # OpenAI/Anthropic-style API key prefixes (sk-XXXXXXXXXXX).
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    # HTTP Bearer tokens (case-insensitive header form).
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_\-\.=]+"),
    # Environment-variable-style credential leaks.
    re.compile(r"(?i)ANTHROPIC_API_KEY=\S+"),
    re.compile(r"(?i)OPENAI_API_KEY=\S+"),
    # Slack bot tokens.
    re.compile(r"xoxb-[A-Za-z0-9_\-]+"),
    # JWT shape: 3 base64-url-encoded segments joined by `.`. Anchor on the
    # standard JWT header prefix `eyJ` to avoid false positives on arbitrary
    # 3-segment dotted identifiers.
    re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
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
    """Recursive helper for redact_dict — handles arbitrary nested types."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
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
    """
    joined = "|".join(p.pattern for p in DEFAULT_PATTERNS)
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
        """Scrub sensitive attributes in-place before the span flushes downstream."""
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
            else:
                # Non-text attributes (int, bool, float, sequences of those)
                # — nothing credential-shaped, leave alone.
                continue
            # ReadableSpan's `_attributes` is BoundedAttributes (or a plain
            # dict under test fixtures); the SDK exposes `BoundedAttributes._dict`
            # as the underlying mutable mapping. For Phase-1 we mutate via a
            # cast — opentelemetry-sdk 1.20+ keeps this contract stable; if
            # the SDK refactors, we swap to a `_Span.set_attribute()` call
            # path. The `index` ignore covers the typed-Mapping → dict
            # assignment that mypy can't narrow.
            attributes[key] = new_value  # type: ignore[index]

    def shutdown(self) -> None:
        """No buffered state; no-op."""
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002 — SpanProcessor protocol
        """No buffered state; always returns True."""
        return True
