"""FR42 acceptance tests — Library defaults wiring (Story 1a.6).

First non-collect-only Phase-1 test. Verifies the 9 PRD FR42 + FR11b defaults
are wired correctly into `AgentEval.__init__` + retrievable via the
`Get Effective Config` keyword.

References:
- PRD FR42 (Library defaults set)
- PRD FR11b (max_runtime_seconds default None)
- PRD FR43 (allow_validate_operator default False)
- PRD FR44 (telemetry default True, opt-out via False)
- ADR-009 (mcp_per_test default True)
- docs/contracts/stability-surface.md (Phase-1 registry for these params)
"""

from __future__ import annotations

from AgentEval import AgentEval


def test_ac_fr42_defaults_with_no_kwargs() -> None:
    """All 9 documented defaults apply when AgentEval() is instantiated with no kwargs."""
    agent = AgentEval()
    config = agent.get_effective_config()

    assert config["provider"] == "litellm"
    assert config["telemetry"] is True
    assert config["trace_backend"] == "memory"
    assert config["allow_validate_operator"] is False
    assert config["default_temperature"] == 0.0
    assert config["mcp_per_test"] is True
    assert config["allow_external_mcp_blind"] is False
    assert config["max_cost_usd"] == 5.00
    assert config["max_runtime_seconds"] is None


def test_ac_fr42_defaults_with_kwarg_overrides() -> None:
    """Kwarg overrides apply; non-overridden defaults remain."""
    agent = AgentEval(allow_validate_operator=True, telemetry=False)
    config = agent.get_effective_config()

    # Overridden
    assert config["allow_validate_operator"] is True
    assert config["telemetry"] is False

    # Defaults still apply
    assert config["provider"] == "litellm"
    assert config["trace_backend"] == "memory"
    assert config["default_temperature"] == 0.0
    assert config["mcp_per_test"] is True
    assert config["allow_external_mcp_blind"] is False
    assert config["max_cost_usd"] == 5.00
    assert config["max_runtime_seconds"] is None


def test_ac_fr42_mcp_per_test_suite_mode() -> None:
    """mcp_per_test accepts the 'suite' Literal per ADR-009 + architecture L314 3-mode."""
    agent = AgentEval(mcp_per_test="suite")
    config = agent.get_effective_config()

    assert config["mcp_per_test"] == "suite"


def test_ac_fr42_mcp_per_test_false_mode() -> None:
    """mcp_per_test accepts False (shared instance) per ADR-009."""
    agent = AgentEval(mcp_per_test=False)
    config = agent.get_effective_config()

    assert config["mcp_per_test"] is False


def test_ac_fr42_max_runtime_seconds_opt_in() -> None:
    """max_runtime_seconds accepts an explicit float per FR11b opt-in."""
    agent = AgentEval(max_runtime_seconds=120.0)
    config = agent.get_effective_config()

    assert config["max_runtime_seconds"] == 120.0


def test_ac_fr42_all_kwargs_keyword_only() -> None:
    """All 9 __init__ params are keyword-only — positional invocation raises TypeError."""
    import pytest

    with pytest.raises(TypeError):
        AgentEval("litellm")  # type: ignore[misc]  # positional arg disallowed
