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

"""A minimal stdio MCP server that records each spawn to a marker file.

Run as ``python _stdio_marker_server.py`` under a ``stdio`` transport. On
startup it appends one ``<pid>`` line to the file named by the
``MCP_SPAWN_MARKER`` env var, then serves ``echo_back`` over stdio. Line count
in the marker file is the exact number of process spawns; the last line's pid
lets a test confirm the subprocess is gone after ``Stop Server``.
"""

from __future__ import annotations

import os


def main() -> None:
    marker = os.environ.get("MCP_SPAWN_MARKER")
    if marker:
        # Line-buffered append + fsync so the parent observes the spawn
        # deterministically before it issues the first op.
        with open(marker, "a", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()}\n")
            handle.flush()
            os.fsync(handle.fileno())

    from mcp.server.fastmcp import FastMCP

    server = FastMCP("mcplibrary-stdio-marker")

    @server.tool(description="Echo the input text verbatim.")
    def echo_back(text: str) -> str:
        return text

    server.run()


if __name__ == "__main__":
    main()
