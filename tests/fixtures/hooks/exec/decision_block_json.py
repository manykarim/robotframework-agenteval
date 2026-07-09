#!/usr/bin/env python3
"""Fixture PostToolUse/Stop-family hook: exit 0 with top-level `decision: "block"`."""

import json
import sys

if __name__ == "__main__":
    sys.stdout.write(json.dumps({"decision": "block", "reason": "blocked by fixture policy"}))
    sys.exit(0)
