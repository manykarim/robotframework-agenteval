#!/usr/bin/env python3
"""Fixture PreToolUse hook: exit 0 with `permissionDecision: "allow"` stdout JSON."""

import json
import sys

if __name__ == "__main__":
    sys.stdout.write(
        json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
        )
    )
    sys.exit(0)
