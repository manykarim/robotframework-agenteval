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

"""Synthesis of the Claude Code hook stdin JSON payload.

Builds the one-JSON-object-per-event stdin payload the Claude Code runtime hands
a command hook. Common fields (``session_id``, ``transcript_path``, ``cwd``,
``hook_event_name``, ``permission_mode``) are always synthesized; event-specific
fields are merged on top.

Exact synthesis is pinned for ``PreToolUse`` / ``PostToolUse`` / ``Stop``; any
other event passes the common fields plus the caller's fields through verbatim.
A ``payload`` dict replaces the synthesized event-specific fields wholesale -
common fields fill gaps, explicit keys win.
"""

from __future__ import annotations

from typing import Any

__all__ = ["PINNED_EVENTS", "SYNTHETIC_SESSION_ID", "synthesize_payload"]

# Deterministic synthetic session id - a constant keeps fired payloads
# reproducible (no per-call UUID drift). NOT a real Claude Code session.
SYNTHETIC_SESSION_ID = "agenteval-synthetic-session"

# Events with pinned event-specific field defaults; others are permissive.
PINNED_EVENTS: frozenset[str] = frozenset({"PreToolUse", "PostToolUse", "Stop"})


def synthesize_payload(
    event: str,
    *,
    cwd: str,
    transcript_path: str,
    payload: dict[str, Any] | None = None,
    event_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the stdin JSON payload for one hook fire.

    ``payload``, when set, replaces ``event_fields`` wholesale; synthesized
    common fields still fill gaps and explicit keys in ``payload`` win. Returns
    the merged JSON-serializable payload dict.
    """
    common: dict[str, Any] = {
        "session_id": SYNTHETIC_SESSION_ID,
        "transcript_path": transcript_path,
        "cwd": cwd,
        "hook_event_name": event,
        "permission_mode": "default",
    }

    if payload is not None:
        merged = dict(common)
        merged.update(payload)
        merged.setdefault("hook_event_name", event)
        return merged

    fields: dict[str, Any] = dict(event_fields or {})

    if event == "PreToolUse":
        fields.setdefault("tool_name", "")
        fields.setdefault("tool_input", {})
    elif event == "PostToolUse":
        fields.setdefault("tool_name", "")
        fields.setdefault("tool_input", {})
        fields.setdefault("tool_response", {})
    elif event == "Stop":
        fields.setdefault("stop_hook_active", False)
    # Unknown events: caller fields pass through verbatim, no defaults added.

    merged = dict(common)
    merged.update(fields)
    return merged
