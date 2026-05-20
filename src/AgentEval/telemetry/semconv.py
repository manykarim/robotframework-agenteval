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

"""OTel GenAI + agenteval semantic-convention attribute-name facade (Story 5.1).

Per NFR-COMPAT-06 ("GenAI semantic convention attribute names routed through
internal facade so attribute-name churn is a single-file update") + architecture
L999-1010 ratified `agenteval.*` namespacing extensions (Story 1b.2 H_R11
ratification 2026-05-19).

All callers in `src/AgentEval/` MUST import attribute keys from this module
rather than hardcoding the `"gen_ai.*"` or `"agenteval.*"` string literals.
Convention enforcement lives at `tests/conformance/test_otel_semconv_facade.py`
(grep-based: any hardcoded `"gen_ai."` or `"agenteval."` literal in
`src/AgentEval/` outside this file = test failure).

Why a facade instead of just using strings directly:

- OTel GenAI semconv is still pre-1.0 (per the OTel semantic-conventions repo)
  and attribute names have churned in the past (e.g., `gen_ai.completion.*` →
  `gen_ai.response.*`). A single-file update lets future-us absorb churn
  without grep-and-replace across the codebase.
- The `agenteval.*` namespace was ratified by Story 1b.2 H_R11 review
  (2026-05-19) and is governed by architecture L999-1010. New attributes go
  here AND get a row in that table.

References:
    - PRD NFR-COMPAT-06 — single-file update for attribute-name churn
    - architecture L984 — `gen_ai.*` + `agenteval.*` example
    - architecture L1001-1010 — ratified `agenteval.*` extensions table
    - Story 1b.2 H_R11 review — `agenteval.*` namespace ratification
    - Story 1b.2 M_R5 review — `agenteval.tier` attribute on every tier-annotated
      keyword's spans
    - Story 1b.2 H_R5 review — `agenteval.tool.args` JSON-encoded string (OTel
      SDK rejects dict attribute values)
"""

from __future__ import annotations

__all__ = [
    # gen_ai.* keys (per OTel GenAI semantic conventions)
    "GEN_AI_SYSTEM",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_USAGE_INPUT_TOKENS",
    "GEN_AI_USAGE_OUTPUT_TOKENS",
    "GEN_AI_USAGE_CACHED_INPUT_TOKENS",
    "GEN_AI_RESPONSE_FINISH_REASONS",
    "GEN_AI_TOOL_NAME",
    "GEN_AI_TOOL_CALL_ID",
    # agenteval.* keys (per architecture L1001-1010 ratified extensions)
    "AGENTEVAL_TEST_ID",
    "AGENTEVAL_TOOL_SUCCESS",
    "AGENTEVAL_TOOL_DURATION_MS",
    "AGENTEVAL_TOOL_SOURCE",
    "AGENTEVAL_TOOL_ARGS",
    "AGENTEVAL_TOOL_RESULT",
    "AGENTEVAL_TOOL_ERROR",
    "AGENTEVAL_TIER",
    # Span names (per architecture L980-982 OTel GenAI semconv hierarchy)
    "SPAN_INVOKE_AGENT",
    "SPAN_CHAT",
    "SPAN_EXECUTE_TOOL",
]


# --------------------------------------------------------------------------- #
# gen_ai.* — OTel GenAI semantic conventions                                  #
# --------------------------------------------------------------------------- #

GEN_AI_SYSTEM = "gen_ai.system"
"""Identifies the provider: ``"anthropic"`` / ``"openai"`` / ``"mcp"`` etc."""

GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
"""Model identifier: ``"claude-sonnet-4-6"`` / ``"gpt-4o"`` etc."""

GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
"""Prompt token count for the LLM round-trip."""

GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
"""Completion token count for the LLM round-trip."""

GEN_AI_USAGE_CACHED_INPUT_TOKENS = "gen_ai.usage.cached_input_tokens"
"""Prompt-cache-hit token count (Anthropic + OpenAI prompt-caching support)."""

GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
"""List of finish reasons: ``["stop"]`` / ``["tool_calls"]`` / ``["length"]`` etc."""

GEN_AI_TOOL_NAME = "gen_ai.tool.name"
"""Tool name on ``execute_tool`` spans."""

GEN_AI_TOOL_CALL_ID = "gen_ai.tool.call.id"
"""Unique tool-call identifier (uuid4 hex) for correlation with adapter-side records."""


# --------------------------------------------------------------------------- #
# agenteval.* — agenteval-specific extensions (architecture L1001-1010)       #
# --------------------------------------------------------------------------- #

AGENTEVAL_TEST_ID = "agenteval.test_id"
"""Listener v3 test identifier (TracerProvider Resource attribute per Story 1b.2 H_R2)."""

AGENTEVAL_TOOL_SUCCESS = "agenteval.tool.success"
"""``True`` when the tool call returned without error."""

AGENTEVAL_TOOL_DURATION_MS = "agenteval.tool.duration_ms"
"""Tool-call wall-clock duration in milliseconds."""

AGENTEVAL_TOOL_SOURCE = "agenteval.tool.source"
"""``Literal["adapter", "hosted_mcp"]`` — which observation path emitted the trace (FR35)."""

AGENTEVAL_TOOL_ARGS = "agenteval.tool.args"
"""Post-redaction tool-call arguments. JSON-encoded string per Story 1b.2 H_R5.

OTel SDK rejects ``dict`` attribute values; producers MUST JSON-serialize at
emission time. ``_kernel/trace_store.get_tool_calls`` JSON-parses at projection
time.
"""

AGENTEVAL_TOOL_RESULT = "agenteval.tool.result"
"""Post-redaction tool-call return value (OTel-compatible primitive or JSON-encoded string)."""

AGENTEVAL_TOOL_ERROR = "agenteval.tool.error"
"""Tool-call error message (``None``-equivalent absent attribute on success)."""

AGENTEVAL_TIER = "agenteval.tier"
"""``Literal[1, 2, 3]`` — span-attribute carrying the keyword's tier annotation.

Story 1b.2 M_R5 ratification: producers emit this on every ``@tier``-annotated
keyword's spans (Listener propagates from ``_agenteval_tier`` decorator
attribute → span attribute). Counted by ``RunManifest.agenteval_tier_breakdown``.
"""


# --------------------------------------------------------------------------- #
# Span names (per architecture L980-982 OTel GenAI semconv hierarchy)         #
# --------------------------------------------------------------------------- #

SPAN_INVOKE_AGENT = "invoke_agent"
"""Top-level span per agent run."""

SPAN_CHAT = "chat"
"""Per-LLM-round-trip span (child of ``invoke_agent``)."""

SPAN_EXECUTE_TOOL = "execute_tool"
"""Per-tool-call span (child of ``chat``)."""
