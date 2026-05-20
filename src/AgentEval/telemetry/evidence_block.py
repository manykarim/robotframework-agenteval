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

"""Evidence Block emitter (Story 5.3 / PRD AC-SIMPLICITY-01 / FR34a/b).

Per PRD §Editorial Moat + AC-SIMPLICITY-01: every assertion outcome ships a
self-contained Evidence Block that captures (a) the exact threshold, (b)
the observed value, (c) the raw agent artifact that produced the verdict.
A reviewer determines correctness without re-running the test or
consulting external dashboards.

Phase-1 ships the **trace-based assertion family** only — metric-based +
judge-based families are Phase-2 carve-outs per the contract at
``docs/contracts/evidence-block-format.md``.

Redaction integration: both ``to_dict()`` and ``to_markdown()`` apply
``_kernel/redaction.redact()`` to every text field before emission per
NFR-SEC-01 / FR38a + AC-5.3.7. This is defense-in-depth — the OTel
``RedactionProcessor`` already scrubs span attributes during emission, but
the Evidence Block builds from ``AgentRunResult`` fields (NOT span
attributes), so the emit-time redaction is the only guard.

References:
    - PRD AC-SIMPLICITY-01: evidence-block legibility as a codified contract
    - PRD FR34a/b: evidence-block format + visual contract
    - PRD FR38a + NFR-SEC-01: credential redaction at emit time
    - `docs/contracts/evidence-block-format.md`: ratified Phase-1 schema
    - Story 1b.2 `_kernel/redaction`: redact/redact_dict primitives
"""

from __future__ import annotations

import dataclasses
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from AgentEval._kernel.redaction import redact

if TYPE_CHECKING:
    from AgentEval.types import AgentRunResult, ToolCallTrace

__all__ = ["EvidenceBlock", "EvidenceBlockEmitter", "Outcome"]


Outcome = Literal["pass", "fail", "skip", "degraded"]
"""Allowed assertion outcomes per `docs/contracts/evidence-block-format.md`."""


@dataclass(frozen=True)
class EvidenceBlock:
    """One assertion outcome's full evidence record per AC-SIMPLICITY-01.

    Frozen dataclass — serialize via `to_dict()` (post-redaction) for JSON
    emission OR `to_markdown()` for human-readable rendering.
    """

    evidence_id: str
    assertion_name: str
    outcome: Outcome
    prompt: str
    response: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    cost_usd: float = 0.0
    coverage: Literal["hosted_in_process", "subprocess_with_observer", "external_mixed"] = "external_mixed"
    completeness: Literal["complete", "truncated", "partial"] = "complete"
    redaction_report: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # M_R6 defensive copies for mutable fields.
        object.__setattr__(self, "tool_calls", [dict(tc) for tc in self.tool_calls])
        object.__setattr__(self, "redaction_report", list(self.redaction_report))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict with all text fields redacted.

        Per AC-5.3.7: every text field passes through `redact()` before
        emission. The `tool_calls` list's per-record `args` + `result`
        fields are also redacted via `redact_dict` traversal.
        """
        raw = dataclasses.asdict(self)
        return _redact_evidence_dict(raw)

    def to_markdown(self) -> str:
        """Return the human-readable 80-char-wide rendering per AC-SIMPLICITY-01.

        Format matches the schema documented in
        `docs/contracts/evidence-block-format.md`. All text fields passed
        through `redact()` before assembly.
        """
        safe_prompt = redact(self.prompt)
        safe_response = redact(self.response)
        # Tool-call summary line.
        tool_call_count = len(self.tool_calls)
        hosted = sum(1 for tc in self.tool_calls if tc.get("source") == "hosted_mcp")
        adapter = sum(1 for tc in self.tool_calls if tc.get("source") == "adapter")
        # Per-tool-call lines (truncated for legibility). Story 5.3 code-review
        # 1-way HIGH-L fix 2026-05-20 (Edge-cases E1 empirical): coerce
        # `latency_ms=None` to 0 BEFORE formatting — `tc.get('latency_ms', 0)`
        # only fell back when the KEY was missing, so a present-but-None
        # value crashed `f"{None:.1f}ms"` with TypeError mid-stream.
        tool_call_lines = [
            f"  {tc.get('name', '<unknown>')}({_args_summary(tc.get('args', {}))}) "
            f"→ {'err' if tc.get('error') else 'ok'} in "
            f"{(tc.get('latency_ms') or 0):.1f}ms"
            for tc in self.tool_calls
        ]
        redaction_summary = ", ".join(self.redaction_report) if self.redaction_report else "none"
        return _ASSEMBLE_MARKDOWN(
            assertion_name=self.assertion_name,
            outcome=self.outcome,
            evidence_id=self.evidence_id,
            prompt=_wrap_80(safe_prompt),
            response=_wrap_80(safe_response),
            tool_call_count=tool_call_count,
            hosted=hosted,
            adapter=adapter,
            tool_call_lines=tool_call_lines,
            cost_usd=self.cost_usd,
            coverage=self.coverage,
            completeness=self.completeness,
            redaction_summary=redaction_summary,
        )


class EvidenceBlockEmitter:
    """Build an `EvidenceBlock` from an `AgentRunResult` + assertion context.

    The emitter does NOT itself emit (write to disk / append to OTel span /
    etc.) — that's the caller's responsibility. The emitter constructs the
    block + applies redaction + returns the immutable record.
    """

    def emit(
        self,
        result: AgentRunResult,
        *,
        assertion_name: str,
        outcome: Outcome,
        prompt: str,
        cost_usd: float | None = None,
    ) -> EvidenceBlock:
        """Build an `EvidenceBlock` from `result` + caller-provided assertion context.

        Args:
            result: The `AgentRunResult` produced by an adapter `run()`.
            assertion_name: RF keyword name (e.g., `"Send Prompt"`).
            outcome: `pass` / `fail` / `skip` / `degraded`.
            prompt: The user prompt the agent saw.
            cost_usd: Optional override for the cost field; defaults to
                ``result.cost_usd``.

        Returns:
            A frozen `EvidenceBlock` with text fields redacted at emit time
            (in `to_dict` + `to_markdown`).
        """
        tool_call_records = [_tool_call_to_dict(tc) for tc in result.tool_calls]
        applied_redactions = _detect_applied_redactions(prompt, result)
        return EvidenceBlock(
            evidence_id=uuid.uuid4().hex,
            assertion_name=assertion_name,
            outcome=outcome,
            prompt=prompt,
            response=result.response_text,
            tool_calls=tool_call_records,
            cost_usd=float(cost_usd if cost_usd is not None else result.cost_usd),
            coverage=result.metadata.mcp_coverage,
            completeness=result.metadata.completeness,
            redaction_report=applied_redactions,
            metadata={},
        )


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _tool_call_to_dict(tc: ToolCallTrace) -> dict[str, Any]:
    """Convert a `ToolCallTrace` to a JSON-serializable dict for embedding in EvidenceBlock."""
    return {
        "name": tc.name,
        "args": dict(tc.args) if tc.args else {},
        "result": tc.result,
        "error": tc.error,
        "latency_ms": tc.latency_ms,
        "source": tc.source,
        "gen_ai_tool_call_id": tc.gen_ai_tool_call_id,
        "sequence_index": tc.sequence_index,
    }


def _redact_evidence_dict(d: Mapping[str, Any]) -> dict[str, Any]:
    """Walk an evidence-block dict + redact every string field; recurse into nested dicts/lists."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, str):
            out[k] = redact(v)
        elif isinstance(v, Mapping):
            out[k] = _redact_evidence_dict(v)
        elif isinstance(v, list):
            out[k] = [
                _redact_evidence_dict(item)
                if isinstance(item, Mapping)
                else (redact(item) if isinstance(item, str) else item)
                for item in v
            ]
        else:
            out[k] = v
    return out


def _detect_applied_redactions(prompt: str, result: AgentRunResult) -> list[str]:
    """Best-effort detection of which redaction patterns fired during this run.

    Phase-1 carve: compares raw vs. redacted versions of prompt + response;
    if they differ, the redaction pipeline fired. Also checks for the
    `[REDACTED]` substring (Story 5.3 code-review 1-way HIGH-I fix 2026-05-20
    Blind H1: pre-edit returned `[]` when the response arrived ALREADY
    redacted from an upstream layer — `redact(already_redacted) ==
    already_redacted` so the sentinel was silently omitted; reviewers
    reading `redaction_report: []` inferred "no redaction happened" while
    the response IS scrubbed). Now treats upstream-already-redacted as
    positive signal.

    Returns a single sentinel `"redaction_applied"` when redaction was
    detected; empty list when not. Phase-1.5 carry-over (DF-5.3-S4):
    attribute to specific pattern names via a richer `RedactionReport`
    type once `_kernel/redaction` exposes per-pattern hits.
    """
    redacted_prompt = redact(prompt)
    redacted_response = redact(result.response_text)
    if redacted_prompt != prompt or redacted_response != result.response_text:
        return ["redaction_applied"]
    # HIGH-I: upstream-already-redacted markers also count as positive signal.
    if "[REDACTED]" in prompt or "[REDACTED]" in result.response_text:
        return ["redaction_applied"]
    return []


def _args_summary(args: Mapping[str, Any]) -> str:
    """One-line summary of tool-call args for the markdown rendering."""
    if not args:
        return ""
    pairs = [f"{k}={v!r}" for k, v in list(args.items())[:3]]
    summary = ", ".join(pairs)
    if len(args) > 3:
        summary += ", ..."
    # Truncate aggressively — markdown lines are 80-char-wide.
    if len(summary) > 50:
        summary = summary[:47] + "..."
    return summary


def _wrap_80(text: str) -> str:
    """Wrap a string at 80 chars per line for the markdown rendering.

    Story 5.3 code-review 1-way HIGH-K fix 2026-05-20 (Blind H5 empirical):
    pre-edit wrapped at width=72 + the caller prefixes `"Prompt:    "` (11
    chars) producing lines up to 83 chars — violates the AC-SIMPLICITY-01
    80-char-wide promise. Now wraps at 69 (= 80 - 11 chars for the longest
    label prefix `"Response:  "`) so the final assembled line is ≤80 chars.
    `textwrap.wrap` returns a list of stripped lines; we re-indent with
    11 spaces on continuation lines so the column alignment is preserved.
    """
    if not text:
        return ""
    import textwrap

    # Width 69 = 80 - 11 (the `"Prompt:    "` / `"Response:  "` prefix length).
    wrapped = textwrap.wrap(text, width=69)
    if not wrapped:
        return text
    # First line goes after the prefix in the caller's f-string; continuation
    # lines are indented with 11 spaces so column 12 aligns with the first
    # line's content.
    return ("\n" + " " * 11).join(wrapped)


def _ASSEMBLE_MARKDOWN(  # noqa: N802 — descriptive constant-style name
    *,
    assertion_name: str,
    outcome: str,
    evidence_id: str,
    prompt: str,
    response: str,
    tool_call_count: int,
    hosted: int,
    adapter: int,
    tool_call_lines: list[str],
    cost_usd: float,
    coverage: str,
    completeness: str,
    redaction_summary: str,
) -> str:
    """Build the markdown rendering per the contract format."""
    header = "=" * 28 + " EVIDENCE BLOCK " + "=" * 28
    rule = "-" * 72
    footer = "=" * 72
    tool_block = "\n".join(tool_call_lines) if tool_call_lines else "  (no tool calls)"
    return "\n".join(
        [
            header,
            f"Assertion: {assertion_name}          Outcome: {outcome}",
            f"Evidence:  {evidence_id}",
            rule,
            f"Prompt:    {prompt}",
            f"Response:  {response}",
            rule,
            f"Tool calls: {tool_call_count} (source: hosted_mcp={hosted}, adapter={adapter})",
            tool_block,
            rule,
            f"Cost: ${cost_usd:.4f}    Coverage: {coverage}    Completeness: {completeness}",
            f"Redactions: {redaction_summary}",
            footer,
        ]
    )
