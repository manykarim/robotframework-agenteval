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

OpenSpec change `add-hooks-execution-testing`, design Decision 2. Builds the
one-JSON-object-per-event stdin payload the real Claude Code runtime hands a
command hook (https://code.claude.com/docs/en/hooks, snapshot 2026-07-08).

Common fields (always synthesized): ``session_id`` (a synthetic constant),
``transcript_path`` (a path under a temp dir), ``cwd``, ``hook_event_name``,
``permission_mode`` (``"default"``). Event-specific fields are supplied by the
caller as keyword fields and merged on top.

Exact synthesis is PINNED only for the three PRD FR4 events (``PreToolUse`` /
``PostToolUse`` / ``Stop``); any other (including future) event name passes the
common fields plus the caller's fields through verbatim — no error is raised
solely because the event is unknown (forward-compat with Claude Code's growing
event list, mirroring the parser's permissive stance).

A ``payload`` dict replaces the synthesized event-specific fields wholesale:
the synthesized common fields still fill gaps, and explicit keys in ``payload``
win over the common defaults.
"""

from __future__ import annotations

from typing import Any

__all__ = ["SYNTHETIC_SESSION_ID", "PINNED_EVENTS", "synthesize_payload"]

# Deterministic synthetic session id — NOT a real Claude Code session. A
# constant keeps fired payloads reproducible (no per-call UUID drift).
SYNTHETIC_SESSION_ID = "agenteval-synthetic-session"

# The three PRD FR4 events with pinned event-specific field schemas. Any
# other event name is handled permissively (common fields + caller fields).
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

    Args:
        event: The hook event name (e.g. ``"PreToolUse"``).
        cwd: The working directory reported to the hook (``cwd`` field +
            the value ``CLAUDE_PROJECT_DIR`` is derived from by the runner).
        transcript_path: Synthetic transcript path (under a temp dir).
        payload: Full-override dict for the event-specific fields. When set,
            it replaces the caller's ``event_fields`` wholesale; synthesized
            common fields still fill any gaps, and explicit keys in ``payload``
            win over the common defaults.
        event_fields: Event-specific fields passed as keyword args at the RF
            call site (``tool_name`` / ``tool_input`` / ``prompt`` / ...).

    Returns:
        The merged JSON-serializable payload dict.
    """
    common: dict[str, Any] = {
        "session_id": SYNTHETIC_SESSION_ID,
        "transcript_path": transcript_path,
        "cwd": cwd,
        "hook_event_name": event,
        "permission_mode": "default",
    }

    if payload is not None:
        # Full-override escape hatch: explicit keys win, common fills gaps.
        merged = dict(common)
        merged.update(payload)
        # Always reflect the fired event name unless the override set it.
        merged.setdefault("hook_event_name", event)
        return merged

    fields: dict[str, Any] = dict(event_fields or {})

    # Pinned events carry protocol-correct defaults for their required
    # event-specific fields so a caller that omits them still produces a
    # shape the hook can read. Explicit caller fields always win.
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
