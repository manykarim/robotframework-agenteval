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

"""DebugListener probe — canonical reference for RF Listener v3 API-surface checks.

Per `feedback_listener_hook_api_surface_empirical_check` (Epic 8 retro NEW
norm 2026-05-25): when extending an RF Listener v3 hook to write data that
surfaces in `output.xml`, empirically verify which API surface
(`data.tags` vs `result.tags`, etc.) is the production-correct one BEFORE
committing.

Use this probe as a one-off subprocess invocation to verify the surfacing
behavior — DO NOT register as the project listener. The probe is
intentionally minimal and stderr-prints both candidate surfaces so an
operator can compare against `output.xml` content.

Canonical invocation pattern (from `/tmp/`):

    cat > /tmp/probe-suite.robot <<'EOF'
    *** Test Cases ***
    Probe
        Log    probe
    EOF
    uv run robot \\
      --listener tests/integration/probes/debug_listener.py \\
      --output /tmp/probe-output.xml \\
      --report NONE --log NONE \\
      /tmp/probe-suite.robot
    # Then inspect /tmp/probe-output.xml:
    grep -B 1 -A 1 "from_data\\|from_result" /tmp/probe-output.xml
    # Empirical truth on RF 7.x: only `<tag>from_result</tag>` surfaces.

Story 8a.2 D-5 empirical finding (2026-05-25) validated via this probe:
`data.tags.add(...)` does NOT surface in `output.xml`; only
`result.tags.add(...)` does. Listener.py L389 reflects this.
"""

from __future__ import annotations

import sys
from typing import Any

# RF Listener v3 module-level entry: when invoked via `--listener
# tests/integration/probes/debug_listener.py`, RF treats the module as
# the listener (no class wrapper needed because there's a top-level
# `ROBOT_LISTENER_API_VERSION`).

ROBOT_LISTENER_API_VERSION = 3


def start_test(data: Any, result: Any) -> None:
    """Add probe tags to both `data.tags` and `result.tags`; print to stderr."""
    sys.stderr.write(
        f"[DebugListener] start_test "
        f"data.tags-type={type(getattr(data, 'tags', None)).__name__} "
        f"result.tags-type={type(getattr(result, 'tags', None)).__name__}\n"
    )
    data_tags = getattr(data, "tags", None)
    if data_tags is not None:
        try:
            data_tags.add("from_data")
        except Exception as exc:  # noqa: BLE001 — probe must never raise
            sys.stderr.write(f"[DebugListener] data.tags.add raised: {exc}\n")
    result_tags = getattr(result, "tags", None)
    if result_tags is not None:
        try:
            result_tags.add("from_result")
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"[DebugListener] result.tags.add raised: {exc}\n")
