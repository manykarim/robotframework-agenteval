#!/usr/bin/env python3
"""Fixture hook: dumps its received environment as stdout JSON, exit 0.

Used to assert the runner's env sanitization — a parent secret must be
absent by default, present only under `inherit_env=True`.
"""

import json
import os
import sys

if __name__ == "__main__":
    sys.stdout.write(json.dumps({"env": dict(os.environ)}))
    sys.exit(0)
