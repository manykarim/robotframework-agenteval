"""agenteval CLI entry point.

Phase-1 placeholder per FR18 + FR52. Real subcommand routing (`init`,
`new-adapter`) lands in Epic 8b Story 8b.1 (init) + Story 8b.2 (new-adapter).

Wired up early so the `[project.scripts] agenteval = "AgentEval.cli:main"`
entry point in pyproject.toml resolves cleanly. Without this stub, `uv run
agenteval` raises ModuleNotFoundError — caught by Story 1a.1 code review
(Codex CLI + Claude Opus, 2026-05-17).
"""

import sys


def main() -> int:
    """CLI entry point. Phase-1 placeholder.

    Returns 0 with a help message until Epic 8b ships the real subcommand
    implementations. The current exit code is intentionally success (0) so that
    contributors can verify the entry point is wired (`uv run agenteval`)
    without the bootstrap looking like a hard failure.
    """
    sys.stderr.write(
        "agenteval CLI: subcommands not yet implemented.\n"
        "  Planned subcommands (Epic 8b deliverables per FR18 + FR52):\n"
        "    agenteval init           — scaffold a new agenteval test suite\n"
        "    agenteval new-adapter    — scaffold a new CodingAgentAdapter\n"
        "See https://github.com/manykarim/robotframework-agenteval for roadmap.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
