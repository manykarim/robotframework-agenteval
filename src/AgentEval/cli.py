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

"""The ``agenteval`` command-line entry point.

Exit-code mapping lives in ``AgentEval._core.errors`` - the one source of
truth - and is re-exported here for the process boundary. The ``init`` scaffold
returns with the packaging pass.
"""

from __future__ import annotations

import argparse
import sys

from AgentEval._core.errors import error_code_to_exit_code

__all__ = ["error_code_to_exit_code", "main"]


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level ``agenteval`` parser."""
    return argparse.ArgumentParser(
        prog="agenteval",
        description="Test the agentic stack - MCP servers, Skills, SubAgents, and Hooks.",
    )


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. With no subcommand, point people at the four libraries."""
    parser = _build_parser()
    parser.parse_args(argv)
    sys.stderr.write(
        "agenteval: import the library you need from a .robot suite -\n"
        "    Library    MCPLibrary\n"
        "    Library    SkillsLibrary\n"
        "    Library    SubagentsLibrary\n"
        "    Library    HooksLibrary\n"
        "Project scaffolding returns with a later release.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
