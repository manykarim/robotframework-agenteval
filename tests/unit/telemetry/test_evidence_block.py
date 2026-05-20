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

"""Unit tests for `EvidenceBlock` + `EvidenceBlockEmitter` (Story 5.3)."""

from __future__ import annotations

from AgentEval.telemetry.evidence_block import EvidenceBlock, EvidenceBlockEmitter
from AgentEval.types import (
    AgentRunMetadata,
    AgentRunResult,
    ToolCallTrace,
    Usage,
)


def _make_run_result(
    response_text: str = "ok",
    tool_calls: list[ToolCallTrace] | None = None,
    cost_usd: float = 0.001,
) -> AgentRunResult:
    return AgentRunResult(
        response_text=response_text,
        tool_calls=tool_calls or [],
        usage=Usage(input_tokens=10, output_tokens=20),
        metadata=AgentRunMetadata(
            completeness="complete",
            mcp_coverage="hosted_in_process",
        ),
        cost_usd=cost_usd,
        latency_seconds=0.05,
        trace_id="trace-id-" + "0" * 22,
    )


def test_evidence_block_to_dict_has_all_required_fields() -> None:
    """Per AC-5.3.5 + evidence-block-format.md contract."""
    result = _make_run_result(response_text="hello")
    block = EvidenceBlockEmitter().emit(result, assertion_name="Send Prompt", outcome="pass", prompt="say hi")
    d = block.to_dict()
    required = {
        "evidence_id",
        "assertion_name",
        "outcome",
        "prompt",
        "response",
        "tool_calls",
        "cost_usd",
        "coverage",
        "completeness",
        "redaction_report",
        "metadata",
    }
    assert required.issubset(d.keys())
    assert d["assertion_name"] == "Send Prompt"
    assert d["outcome"] == "pass"
    assert d["coverage"] == "hosted_in_process"
    assert d["completeness"] == "complete"


def test_evidence_block_to_markdown_renders_per_contract() -> None:
    """`to_markdown()` matches the visual schema in evidence-block-format.md."""
    block = EvidenceBlock(
        evidence_id="abc123",
        assertion_name="Send Prompt",
        outcome="pass",
        prompt="say hi",
        response="hello",
        tool_calls=[],
        cost_usd=0.001,
        coverage="hosted_in_process",
        completeness="complete",
    )
    md = block.to_markdown()
    assert "EVIDENCE BLOCK" in md
    assert "Send Prompt" in md
    assert "pass" in md
    assert "say hi" in md
    assert "hello" in md
    assert "$0.0010" in md
    assert "hosted_in_process" in md
    assert "complete" in md
    assert "Redactions: none" in md


def test_evidence_block_redacts_api_key_in_response() -> None:
    """Story 5.3 AC-5.3.7: redaction wired through `to_dict()` + `to_markdown()`."""
    result = _make_run_result(response_text="key sk-1234567890abcdef1234567890abcdef")
    block = EvidenceBlockEmitter().emit(result, assertion_name="Send Prompt", outcome="pass", prompt="hi")
    # to_dict response is redacted.
    d = block.to_dict()
    assert "sk-1234567890abcdef" not in d["response"]
    # to_markdown also redacts.
    md = block.to_markdown()
    assert "sk-1234567890abcdef" not in md
    # `redaction_report` flags that redaction was applied.
    assert block.redaction_report == ["redaction_applied"]


def test_evidence_block_redacts_api_key_in_prompt() -> None:
    """Redaction at emit time also catches credentials in the input prompt."""
    result = _make_run_result(response_text="ok")
    block = EvidenceBlockEmitter().emit(
        result,
        assertion_name="Send Prompt",
        outcome="pass",
        prompt="key sk-abcdefghijklmnopqrstuvwxyz0123456789",
    )
    d = block.to_dict()
    assert "sk-abcdef" not in d["prompt"]
    md = block.to_markdown()
    assert "sk-abcdef" not in md
    assert block.redaction_report == ["redaction_applied"]


def test_evidence_block_tool_call_records_preserved() -> None:
    """Tool calls flow into `EvidenceBlock.tool_calls` as JSON-serializable dicts."""
    tc = ToolCallTrace(
        name="echo_back",
        args={"text": "hi"},
        result="hi",
        error=None,
        latency_ms=12.5,
        source="hosted_mcp",
        gen_ai_tool_call_id="tc-1",
        sequence_index=1,
    )
    result = _make_run_result(tool_calls=[tc])
    block = EvidenceBlockEmitter().emit(result, assertion_name="Send Prompt", outcome="pass", prompt="hi")
    assert len(block.tool_calls) == 1
    assert block.tool_calls[0]["name"] == "echo_back"
    assert block.tool_calls[0]["source"] == "hosted_mcp"
    md = block.to_markdown()
    assert "echo_back" in md
    assert "hosted_mcp=1" in md


def test_evidence_block_defensive_copy_on_construction() -> None:
    """`__post_init__` defensively copies mutable fields per M_R6 pattern."""
    source_tool_calls = [{"name": "t", "source": "adapter"}]
    block = EvidenceBlock(
        evidence_id="x",
        assertion_name="x",
        outcome="pass",
        prompt="",
        response="",
        tool_calls=source_tool_calls,
    )
    # Mutate the source list — block's copy is unaffected.
    source_tool_calls.append({"name": "extra"})
    assert len(block.tool_calls) == 1


def test_evidence_block_outcome_degraded_renders_correctly() -> None:
    """`outcome="degraded"` (Story 5.4 forward-ref) renders correctly."""
    result = _make_run_result()
    block = EvidenceBlockEmitter().emit(result, assertion_name="Send Prompt", outcome="degraded", prompt="hi")
    assert block.outcome == "degraded"
    md = block.to_markdown()
    assert "Outcome: degraded" in md


def test_evidence_block_emitter_uses_result_cost_when_override_missing() -> None:
    """When `cost_usd=None`, the emitter takes `result.cost_usd`."""
    result = _make_run_result(cost_usd=0.99)
    block = EvidenceBlockEmitter().emit(result, assertion_name="x", outcome="pass", prompt="hi")
    assert block.cost_usd == 0.99
    block_override = EvidenceBlockEmitter().emit(result, assertion_name="x", outcome="pass", prompt="hi", cost_usd=0.01)
    assert block_override.cost_usd == 0.01


def test_evidence_block_to_markdown_handles_long_prompt() -> None:
    """Long prompts get wrapped for 80-char-wide rendering per AC-SIMPLICITY-01.

    Story 5.3 code-review 1-way HIGH-K fix 2026-05-20 (Blind H5 empirical):
    pre-edit wrapped at width=72 + caller prefix `"Prompt:    "` (11 chars)
    produced lines up to 83 chars violating the AC-SIMPLICITY-01 80-char
    contract. Now wraps at width=69 so final lines stay ≤80.
    """
    long_prompt = "x" * 200
    result = _make_run_result()
    block = EvidenceBlockEmitter().emit(result, assertion_name="x", outcome="pass", prompt=long_prompt)
    md = block.to_markdown()
    # The prompt line is wrapped.
    prompt_section = md.split("Prompt:")[1].split("Response:")[0]
    assert "\n" in prompt_section
    # HIGH-K regression: every line in the rendered markdown must be ≤80 chars.
    for line in md.split("\n"):
        assert len(line) <= 80, f"line exceeds 80 chars ({len(line)}): {line!r}"


def test_evidence_block_to_markdown_handles_none_latency_ms() -> None:
    """Story 5.3 code-review 1-way HIGH-L fix 2026-05-20 (Edge-cases E1
    empirical): pre-edit `f"{tc.get('latency_ms', 0):.1f}ms"` only fell back
    when the KEY was missing — a present-but-None value crashed format with
    TypeError. Now `(tc.get('latency_ms') or 0)` coerces None → 0.
    """
    tc = ToolCallTrace(
        name="t",
        args={},
        result=None,
        error=None,
        latency_ms=0.0,  # ToolCallTrace requires float, but the dict path can carry None
        source="adapter",
        gen_ai_tool_call_id="x",
        sequence_index=1,
    )
    result = _make_run_result(tool_calls=[tc])
    block = EvidenceBlockEmitter().emit(result, assertion_name="x", outcome="pass", prompt="hi")
    # Force the tool_calls dict to carry latency_ms=None to simulate a
    # degraded run where the observer couldn't measure latency.
    object.__setattr__(block, "tool_calls", [{**block.tool_calls[0], "latency_ms": None}])
    # to_markdown must NOT raise even with latency_ms=None.
    md = block.to_markdown()
    assert "0.0ms" in md  # falls back to 0


def test_evidence_block_detects_redaction_when_already_redacted_in_response() -> None:
    """Story 5.3 code-review 1-way HIGH-I fix 2026-05-20 (Blind H1): pre-edit
    returned `[]` when response arrived ALREADY redacted (e.g., adapter
    built it from `RedactionProcessor`-scrubbed span attributes). Reviewers
    inferred "no redaction happened" while the response WAS scrubbed.
    Now treats upstream `[REDACTED]` markers as positive signal.
    """
    result = _make_run_result(response_text="Here is the secret: [REDACTED]")
    block = EvidenceBlockEmitter().emit(result, assertion_name="x", outcome="pass", prompt="hi")
    assert block.redaction_report == ["redaction_applied"], (
        "HIGH-I regression: response carrying `[REDACTED]` marker must register the redaction_applied sentinel"
    )
