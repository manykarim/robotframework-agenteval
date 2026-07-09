#!/usr/bin/env python3
"""Fixture hook: writes an invalid UTF-8 byte to stdout, exit 0.

Used to assert the runner decodes subprocess output with ``errors="replace"``
so a hook emitting non-UTF-8 bytes is RECORDED (with replacement chars), not a
`UnicodeDecodeError` crash in the parent (Codex security review LOW).
"""

import sys

if __name__ == "__main__":
    sys.stdout.buffer.write(b"\xff")
    sys.stdout.flush()
    sys.exit(0)
