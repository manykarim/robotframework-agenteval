#!/usr/bin/env python3
"""Fixture PreToolUse hook: block dangerous `rm -rf` Bash commands.

Reads the synthetic Claude Code hook stdin JSON, inspects
`tool_input.command`, and BLOCKS (exit code 2, message on stderr per the
protocol) when the command looks like a destructive recursive delete;
otherwise ALLOWS (exit 0, no output = no opinion).

Deterministic, stdlib-only, portable (`#!/usr/bin/env python3`). Committed
under tests/fixtures/hooks/exec/ by the OpenSpec change
`add-hooks-execution-testing`.
"""

import json
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    tool_input = payload.get("tool_input") or {}
    command = ""
    if isinstance(tool_input, dict):
        command = str(tool_input.get("command", ""))

    normalized = command.replace("  ", " ").strip()
    if "rm -rf" in normalized or "rm -fr" in normalized:
        # Exit 2 = blocking error; stderr is the message shown to the agent.
        sys.stderr.write(f"blocked dangerous command: {command!r}\n")
        return 2

    # No opinion — let the tool call proceed.
    return 0


if __name__ == "__main__":
    sys.exit(main())
