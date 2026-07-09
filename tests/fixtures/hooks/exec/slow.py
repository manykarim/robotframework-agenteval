#!/usr/bin/env python3
"""Fixture hook: sleeps far longer than any test timeout, then exits 0.

Used to exercise the runner's hard-timeout + process-group-kill path
(`status="timed_out"`). Never allowed to actually complete in a test.
"""

import sys
import time

if __name__ == "__main__":
    time.sleep(60)
    sys.exit(0)
