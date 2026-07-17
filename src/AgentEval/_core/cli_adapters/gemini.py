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

"""gemini CLI adapter (fidelity FULL).

Invocation: ``gemini -p "<prompt>" --output-format json``. The CLI emits a
single JSON object on stdout carrying the assistant ``response`` plus a
``stats`` block with per-model token counts and aggregate per-tool call counts.
Tokens are read natively; cost is *derived* via ``litellm.completion_cost``
(the CLI does not report a native dollar cost).

VALIDATION-CEILING: ``--output-format json`` reports tool calls only in
*aggregate* (per-tool counts + success/fail), not as individually-argumented
invocations. This adapter therefore expands the aggregate into one
``ToolCallTrace`` per counted call with empty ``args`` and an ``error`` set on
the failed ones - the total-call and passed/failed metrics are faithful, but
per-call arguments and results are not available in this mode (they require the
richer ``--output-format stream-json`` event stream, out of scope here).
"""

from __future__ import annotations

import json
from typing import Any, ClassVar, Literal

from AgentEval._core.cli_adapter import Fidelity, MetricSource, SubprocessCLIAdapter
from AgentEval._core.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage


class GeminiAdapter(SubprocessCLIAdapter):
    """Google ``gemini`` CLI: ``gemini -p --output-format json``.

    FULL fidelity for tool-call counts + token usage (read natively from the
    ``stats`` block); cost is derived via ``litellm.completion_cost`` because the
    CLI does not report a native dollar cost.
    """

    slug: ClassVar[str] = "gemini"
    binary_name: ClassVar[str] = "gemini"
    fidelity: ClassVar[Fidelity] = "FULL"
    validation_ceiling: ClassVar[str] = (
        "Reports per-model token usage and aggregate per-tool call counts from "
        "--output-format json; cost is derived from tokens + a price table, not "
        "native. Per-call tool arguments/results are NOT captured in json mode "
        "(only aggregate counts + success/fail); they require stream-json."
    )
    # JSON stdout output stabilized around @google/gemini-cli 0.6.x; older
    # versions lack --output-format json entirely.
    pinned_version_range: ClassVar[tuple[str, str] | None] = ("0.6.0", "0.9.0")
    install_hint: ClassVar[str] = (
        "Install with: npm install -g @google/gemini-cli (JSON output requires a recent version, ~0.6.1+)."
    )

    def build_argv(self, prompt: str) -> list[str]:
        """``gemini -p "<prompt>" --output-format json``. No secrets on argv."""
        return [self.binary_name, "-p", prompt, "--output-format", "json"]

    def parse_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        session_dir: str | None,
    ) -> AgentRunResult:
        """Normalize the ``--output-format json`` object into an ``AgentRunResult``."""
        payload = _load_json_object(stdout)

        response_text = _coerce_str(payload.get("response"))
        stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
        assert isinstance(stats, dict)

        usage, model_name = _parse_model_stats(stats)
        tool_calls, latency_seconds = _parse_tool_stats(stats)

        # Cost is derived: gemini json does not report a native dollar amount.
        # Feed a minimal completion_response so litellm prices from tokens.
        cost_usd = 0.0
        metric_source: MetricSource = "none"
        if model_name and (usage.input_tokens or usage.output_tokens):
            # ASSUMPTION: the stats model key is a bare gemini model id
            # (e.g. "gemini-2.5-pro"); prepend the litellm "gemini/" provider
            # route when it carries no provider prefix so pricing resolves.
            priced_model = model_name if "/" in model_name else f"gemini/{model_name}"
            cost_usd, metric_source = self.resolve_cost(
                None,
                completion_response={
                    "model": priced_model,
                    "usage": {
                        "prompt_tokens": usage.input_tokens,
                        "completion_tokens": usage.output_tokens,
                        "total_tokens": usage.input_tokens + usage.output_tokens,
                    },
                },
            )

        completeness: Literal["complete", "partial"] = "complete" if exit_code == 0 else "partial"
        return AgentRunResult(
            response_text=response_text,
            tool_calls=tool_calls,
            usage=usage,
            metadata=AgentRunMetadata(
                completeness=completeness,
                mcp_coverage="subprocess_with_observer",
                metric_source=metric_source,
                # agent_version left blank: the base stamps the probed --version.
            ),
            cost_usd=cost_usd,
            latency_seconds=latency_seconds,
        )


def _load_json_object(stdout: str) -> dict[str, Any]:
    """Parse stdout as a JSON object; ``{}`` when empty or unparseable.

    The last non-empty line is tried as a fallback when the CLI prefixes the
    object with banner/log lines.
    """
    text = stdout.strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        obj = None
    if not isinstance(obj, dict):
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                return candidate
        return {}
    return obj


def _parse_model_stats(stats: dict[str, Any]) -> tuple[Usage, str]:
    """Sum per-model token counts into one ``Usage`` and pick a model name for pricing.

    gemini reports ``stats.models.<model>.tokens`` with keys ``prompt`` /
    ``candidates`` / ``cached`` / ``thoughts`` / ``total``. We map
    ``input_tokens=prompt``, ``output_tokens=candidates+thoughts`` (reasoning
    tokens are billed as output), ``cached_input_tokens=cached``.
    """
    models = stats.get("models")
    if not isinstance(models, dict) or not models:
        return Usage(input_tokens=0, output_tokens=0), ""

    input_total = 0
    output_total = 0
    cached_total = 0
    # ASSUMPTION: a single model dominates a run; we price against the model
    # with the most prompt tokens (the primary conversation model), while
    # summing token counts across all models present.
    best_model = ""
    best_prompt = -1
    for model_name, entry in models.items():
        if not isinstance(entry, dict):
            continue
        tokens = entry.get("tokens") if isinstance(entry.get("tokens"), dict) else {}
        assert isinstance(tokens, dict)
        prompt = _as_int(tokens.get("prompt"))
        candidates = _as_int(tokens.get("candidates"))
        # ASSUMPTION: "thoughts" (reasoning) tokens count toward output/billed
        # completion tokens; "tool" tokens are excluded (they re-enter as input).
        thoughts = _as_int(tokens.get("thoughts"))
        cached = _as_int(tokens.get("cached"))
        input_total += prompt
        output_total += candidates + thoughts
        cached_total += cached
        if prompt > best_prompt:
            best_prompt = prompt
            best_model = str(model_name)

    return (
        Usage(input_tokens=input_total, output_tokens=output_total, cached_input_tokens=cached_total),
        best_model,
    )


def _parse_tool_stats(stats: dict[str, Any]) -> tuple[list[ToolCallTrace], float]:
    """Expand ``stats.tools.byName`` aggregates into ``ToolCallTrace`` records.

    Each tool's ``count`` becomes that many traces; the first ``fail`` of them
    carry an ``error`` marker so passed/failed metrics stay faithful. Per-call
    ``args``/``result`` are unavailable in json mode (see VALIDATION-CEILING).
    Returns the traces plus a best-effort latency (total tool duration in s).
    """
    tools = stats.get("tools") if isinstance(stats.get("tools"), dict) else {}
    assert isinstance(tools, dict)
    by_name = tools.get("byName") if isinstance(tools.get("byName"), dict) else {}
    assert isinstance(by_name, dict)

    traces: list[ToolCallTrace] = []
    sequence_index = 0
    for name, entry in by_name.items():
        if not isinstance(entry, dict):
            continue
        count = _as_int(entry.get("count"))
        fail = _as_int(entry.get("fail"))
        for i in range(count):
            # Attribute the known failure count to the first `fail` calls; we
            # cannot know which specific call failed from the aggregate.
            error = "tool call reported failure (aggregate json mode)" if i < fail else None
            traces.append(
                ToolCallTrace(
                    name=str(name),
                    args={},  # ASSUMPTION: json mode gives no per-call args
                    error=error,
                    source="adapter",
                    sequence_index=sequence_index,
                )
            )
            sequence_index += 1

    # Best-effort latency: gemini reports aggregate tool duration in ms.
    duration_ms = _as_int(tools.get("totalDurationMs"))
    return traces, duration_ms / 1000.0 if duration_ms else 0.0


def _coerce_str(value: Any) -> str:
    """Return ``value`` as a string; ``""`` for None/non-string."""
    return value if isinstance(value, str) else ""


def _as_int(value: Any) -> int:
    """Coerce a token/count value to a non-negative int, 0 on anything odd."""
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value if value >= 0 else 0
    try:
        result = int(value)
    except (TypeError, ValueError):
        return 0
    return result if result >= 0 else 0
