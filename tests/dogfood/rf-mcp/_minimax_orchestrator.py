# Copyright 2026 Many Kasiriha
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Test-suite-local LLM↔MCP tool-use orchestrator (dogfood; DF-RFMCP-E2E-01).

Closes DF-4.1-S2 narrowly for the rf-mcp E2E dogfood path by inlining the
adapter-side MCP-bridge here instead of refactoring
`AgentEval.providers.litellm_adapter`. Phase-1.5+ migrates this logic into
`LiteLLMAdapter.run(mcp_servers=...)` proper (per `docs/phase-1-5-carry-overs.md`
DF-RFMCP-E2E-01).

Drives a minimax M2.7 model through an MCP server's tool surface, capturing
the full trajectory + token usage into an `AgentRunResult` that the standard
`metrics/` + `_assertions/` keyword surface can consume.

Side-effects:
- Reads `MINIMAX_API_KEY` / `MINIMAX_BASE_URL` / `MINIMAX_MODEL` from the
  process env (or `.env` via python-dotenv).
- Issues HTTPS calls to `MINIMAX_BASE_URL/chat/completions`.
- Dispatches MCP tool calls via `AgentEval.mcp.lifecycle.call_tool`.

NOT for production use — the LiteLLM-adapter promotion is tracked at
DF-RFMCP-E2E-01.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import httpx
from dotenv import load_dotenv
from robot.api.deco import keyword, library

from AgentEval.mcp.lifecycle import MCPServerHandle, call_tool, list_tools
from AgentEval.types import AgentRunMetadata, AgentRunResult, ToolCallTrace, Usage

# Load `.env` at module import so the keywords don't need to plumb env-loading
# through every call site. python-dotenv is already a transitive dep of litellm.
load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"), override=False)


def _mcp_tool_to_openai(tool: Any) -> dict[str, Any]:
    """Convert an `MCPTool` (input_schema as JSON Schema dict) to the OpenAI
    `{"type": "function", "function": {...}}` shape minimax expects."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema or {"type": "object", "properties": {}},
        },
    }


def _content_blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    """Flatten MCP content blocks to a single string for the LLM message body.

    MCP content blocks are `{type: "text"|"image"|..., text|data|...}` per the
    MCP spec. Phase-1 only handles `text` blocks; non-text blocks render as a
    placeholder so the model still sees structure-bearing output.
    """
    parts: list[str] = []
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "text":
            parts.append(str(b.get("text", "")))
        else:
            parts.append(f"<non-text-block type={b.get('type', 'unknown')!r}>")
    return "\n".join(parts)


@library(scope="GLOBAL")
class MinimaxMcpOrchestrator:
    """RF library driving a minimax model through an MCP server (DF-RFMCP-E2E-01).

    Inlines the LLM↔MCP tool-use loop that DF-4.1-S2 defers from
    `LiteLLMAdapter.run(mcp_servers=...)`. NOT a production adapter — promote
    to `src/AgentEval/providers/litellm_adapter.py` per Phase-1.5 carry-over.
    """

    @keyword(name="Skip If Minimax Credentials Missing")
    def skip_if_minimax_credentials_missing(self) -> None:
        """Skip the current test if MINIMAX_API_KEY is absent from the env.

        SECURITY-CRITICAL: this keyword exists specifically so the credential
        VALUE never enters RF's variable namespace (where it would be logged
        plaintext to ``log.html`` by default). Always use this instead of
        ``Get Environment Variable    MINIMAX_API_KEY``.
        """
        if not os.environ.get("MINIMAX_API_KEY"):
            from robot.api.exceptions import SkipExecution

            raise SkipExecution(
                "MINIMAX_API_KEY not set — skipping live-LLM E2E "
                "(configure `.env` at repo root to enable)."
            )

    @keyword(name="Send Prompt With Mcp Tools")
    def send_prompt_with_mcp_tools(
        self,
        prompt: str,
        handle: MCPServerHandle,
        model: str | None = None,
        max_iterations: int = 8,
        max_tokens_per_call: int = 4096,
        request_timeout_seconds: float = 120.0,
    ) -> AgentRunResult:
        """Drive `model` through `handle`'s MCP tools until it stops calling tools.

        Returns an `AgentRunResult` carrying the full trajectory + aggregated
        token usage. Cost is reported as `0.0` (minimax pricing not in the
        Phase-1 cost catalog — Tier-3 cost gate is operator-side until the
        adapter promotion lands).

        | =Arguments= | =Description= |
        | ``prompt`` | The user prompt the model should fulfill. |
        | ``handle`` | An ``MCPServerHandle`` from `MCP.Start Server`. |
        | ``model`` | Minimax model id (default: ``$MINIMAX_MODEL`` env). |
        | ``max_iterations`` | Maximum LLM↔tool round-trips (safety cap). Defaults to ``8``. |
        | ``max_tokens_per_call`` | Per-call token cap. Defaults to ``4096``. |
        | ``request_timeout_seconds`` | HTTP timeout per LLM call. Defaults to ``120.0``. |
        """
        api_key = os.environ.get("MINIMAX_API_KEY")
        base_url = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
        model_id = model or os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7")
        if not api_key:
            raise RuntimeError(
                "MINIMAX_API_KEY not set; expected in `.env` at repo root or process env."
            )

        # Discover tools via the standard `mcp.lifecycle` accessor — same path the
        # MCPLibrary keywords use, so trajectory equivalence is preserved.
        tools = list_tools(handle)
        openai_tools = [_mcp_tool_to_openai(t) for t in tools]

        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        trajectory: list[ToolCallTrace] = []
        total_input = 0
        total_output = 0
        total_cached = 0
        final_text = ""
        t_start = time.monotonic()

        with httpx.Client(timeout=request_timeout_seconds) as client:
            for _iteration in range(max_iterations):
                resp = client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model_id,
                        "messages": messages,
                        "tools": openai_tools,
                        "max_tokens": max_tokens_per_call,
                    },
                )
                resp.raise_for_status()
                body = resp.json()

                usage = body.get("usage") or {}
                total_input += int(usage.get("prompt_tokens", 0))
                total_output += int(usage.get("completion_tokens", 0))
                # Minimax surfaces `cached_tokens` under `prompt_tokens_details`.
                ptd = usage.get("prompt_tokens_details") or {}
                total_cached += int(ptd.get("cached_tokens", 0))

                choice = (body.get("choices") or [{}])[0]
                msg = choice.get("message") or {}
                tool_calls = msg.get("tool_calls") or []
                content = msg.get("content") or ""

                # Append the assistant turn to the conversation BEFORE dispatching
                # tool calls — minimax requires the tool message to immediately
                # follow the assistant message that requested it.
                messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                        **({"tool_calls": tool_calls} if tool_calls else {}),
                    }
                )

                if not tool_calls:
                    final_text = content
                    break

                for tc in tool_calls:
                    tc_id = tc.get("id") or f"call_{uuid.uuid4().hex}"
                    fn = tc.get("function") or {}
                    tname = fn.get("name", "")
                    raw_args = fn.get("arguments") or "{}"
                    try:
                        targs = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
                    except json.JSONDecodeError:
                        targs = {"_raw_arguments": raw_args}

                    t_call_start = time.monotonic()
                    err: str | None = None
                    result_payload: Any = None
                    text_for_llm: str
                    try:
                        result = call_tool(handle, tname, targs)
                        latency_ms = (time.monotonic() - t_call_start) * 1000.0
                        if result.is_error:
                            err = result.error_message or "<tool returned is_error=True>"
                            text_for_llm = err
                        else:
                            result_payload = result.content
                            text_for_llm = _content_blocks_to_text(result.content) or "<no content>"
                    except Exception as exc:  # noqa: BLE001
                        latency_ms = (time.monotonic() - t_call_start) * 1000.0
                        err = f"{type(exc).__name__}: {exc}"
                        text_for_llm = err

                    trajectory.append(
                        ToolCallTrace(
                            name=tname,
                            args=targs,
                            result=result_payload,
                            error=err,
                            latency_ms=latency_ms,
                            source="adapter",
                            gen_ai_tool_call_id=tc_id,
                            sequence_index=len(trajectory),
                        )
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": text_for_llm,
                        }
                    )
            else:
                # max_iterations exhausted without natural completion — mark the
                # trace truncated so downstream metrics consumers see honest data.
                completeness = "truncated"
        # When the for-loop hit `break`, completeness is "complete"; the else
        # branch above pinned "truncated" otherwise. Set the default here.
        completeness = locals().get("completeness", "complete")

        latency_seconds = time.monotonic() - t_start

        return AgentRunResult(
            response_text=final_text,
            tool_calls=trajectory,
            usage=Usage(
                input_tokens=total_input,
                output_tokens=total_output,
                cached_input_tokens=total_cached,
            ),
            metadata=AgentRunMetadata(
                completeness=completeness,
                # rf-mcp runs as a stdio subprocess + we observe every tool call
                # via `mcp.lifecycle.call_tool`, so the FR36b state is
                # `subprocess_with_observer`.
                mcp_coverage="subprocess_with_observer",
            ),
            cost_usd=0.0,  # Minimax pricing not in Phase-1 cost catalog (DF-RFMCP-E2E-01).
            latency_seconds=latency_seconds,
            trace_id=uuid.uuid4().hex,
        )
