#!/usr/bin/env python3
"""Fixture hook: exit 2 (block) WHILE printing an `allow` decision on stdout.

Verifies the protocol rule that exit code 2 IGNORES stdout JSON — the
normalized decision must be `block`, never the `allow` this script prints.
"""

import json
import sys

if __name__ == "__main__":
    sys.stdout.write(
        json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}})
    )
    sys.stderr.write("blocking via exit code despite the allow on stdout\n")
    sys.exit(2)
