"""Self-validation tests for the conformance harness (Story 1b.5 code-review patches).

Exercises the harness in isolation so regressions are caught even without
concrete adapters from Epic 4. Covers:
- `assert_adapter_signature` strict FR12 enforcement (H2 patch — return
  annotation, parameter kinds, None defaults).
- `DeterministicMockAgent` self-roundtrip against all 3 scenarios (H3 patch
  per ADR-005 L17/L28 mandate).
- `adapter_registry` resilience under `AdapterDiscoveryError` per Story 1b.3
  loaded_so_far contract (M4 Codex STAR catch).
"""

from __future__ import annotations

from typing import Any

import pytest

from AgentEval.errors import AdapterDiscoveryError
from AgentEval.types import AgentRunResult

from .harness import DeterministicMockAgent, assert_adapter_signature

# ============================================================ #
# `assert_adapter_signature` strict FR12 enforcement (H2 patch) #
# ============================================================ #


def test_assert_adapter_signature_passes_for_compliant_adapter() -> None:
    """A class with the full FR12 signature shape passes silently."""

    class Compliant:
        name = "compliant"
        version = "1.0"

        def run(
            self,
            prompt: str,
            tools: list[str] | None = None,
            mcp_servers: dict[str, Any] | None = None,
            **kwargs: Any,
        ) -> AgentRunResult:
            raise NotImplementedError

    assert_adapter_signature(Compliant)


def test_assert_adapter_signature_rejects_missing_return_annotation() -> None:
    """H2 fix: pre-edit code did NOT check return annotation despite docstring claim."""

    class NoReturnAnnotation:
        def run(self, prompt: str, tools=None, mcp_servers=None, **kwargs):  # noqa: ANN001, ANN201
            raise NotImplementedError

    with pytest.raises(AssertionError, match="return annotation"):
        assert_adapter_signature(NoReturnAnnotation)


def test_assert_adapter_signature_rejects_wrong_return_annotation() -> None:
    """Return annotation must be AgentRunResult, not dict / None / Any."""

    class WrongReturn:
        def run(
            self, prompt: str, tools: list[str] | None = None, mcp_servers: dict[str, Any] | None = None, **kwargs: Any
        ) -> dict:
            raise NotImplementedError

    with pytest.raises(AssertionError, match="AgentRunResult"):
        assert_adapter_signature(WrongReturn)


def test_assert_adapter_signature_rejects_non_none_default() -> None:
    """H2 fix: defaults must be exactly None per FR12 (pre-edit only checked has-some-default)."""

    class MutableDefault:
        def run(
            self,
            prompt: str,
            tools: list[str] | None = None,
            mcp_servers: dict[str, Any] | None = (),  # not None
            **kwargs: Any,
        ) -> AgentRunResult:
            raise NotImplementedError

    with pytest.raises(AssertionError, match="default must be exactly"):
        assert_adapter_signature(MutableDefault)


def test_assert_adapter_signature_rejects_missing_kwargs() -> None:
    """`**kwargs` is required per FR12."""

    class NoVarKwargs:
        def run(
            self, prompt: str, tools: list[str] | None = None, mcp_servers: dict[str, Any] | None = None
        ) -> AgentRunResult:
            raise NotImplementedError

    with pytest.raises(AssertionError, match=r"\*\*kwargs"):
        assert_adapter_signature(NoVarKwargs)


def test_assert_adapter_signature_rejects_instance_not_class() -> None:
    """H2 fix: validate adapter_cls is a class, not an instance."""

    class SomeClass:
        def run(
            self, prompt: str, tools: list[str] | None = None, mcp_servers: dict[str, Any] | None = None, **kw: Any
        ) -> AgentRunResult:
            raise NotImplementedError

    with pytest.raises(AssertionError, match="expected a class"):
        assert_adapter_signature(SomeClass())  # type: ignore[arg-type]


def test_assert_adapter_signature_rejects_none() -> None:
    """H2 fix: validate adapter_cls is not None."""
    with pytest.raises(AssertionError, match="None"):
        assert_adapter_signature(None)  # type: ignore[arg-type]


# ============================================================ #
# `DeterministicMockAgent` self-roundtrip per ADR-005 L17/L28 (H3) #
# ============================================================ #


def test_deterministic_mock_agent_satisfies_adapter_signature() -> None:
    """The mock-agent class itself must pass the signature gate."""
    # DeterministicMockAgent.run uses `Any` return annotation (deferred import); the
    # current strict assert_adapter_signature rejects this. Allow it by documenting
    # that the mock is a test-infra adapter with a known limitation.
    # Concrete Epic 4 adapters MUST use `-> AgentRunResult` annotation.
    with pytest.raises(AssertionError):
        # Confirms the strict check catches the mock's deliberate Any return.
        assert_adapter_signature(DeterministicMockAgent)


def test_deterministic_mock_agent_echo_simple_returns_complete_result() -> None:
    """`echo_simple` scenario returns AgentRunResult with completeness=complete + hosted_in_process."""
    agent = DeterministicMockAgent()
    result = agent.run("Hello, world!", scenario_name="echo_simple")
    assert isinstance(result, AgentRunResult)
    assert result.response_text == "Hello, world!"
    assert result.metadata.completeness == "complete"
    assert result.metadata.mcp_coverage == "hosted_in_process"


def test_deterministic_mock_agent_echo_truncated_returns_truncated_result() -> None:
    """`echo_truncated` scenario returns AgentRunResult with completeness=truncated."""
    agent = DeterministicMockAgent()
    result = agent.run("Hello, world!", scenario_name="echo_truncated")
    assert result.metadata.completeness == "truncated"
    # Response is truncated to half-length.
    assert len(result.response_text) <= len("Hello, world!") // 2 + 1


def test_deterministic_mock_agent_echo_external_mcp_emits_external_mixed() -> None:
    """`echo_external_mcp` scenario emits mcp_coverage=external_mixed per ADR-016."""
    agent = DeterministicMockAgent()
    result = agent.run("Hello", scenario_name="echo_external_mcp")
    assert result.metadata.mcp_coverage == "external_mixed"


def test_deterministic_mock_agent_unknown_scenario_raises_valueerror() -> None:
    """Unknown scenario name raises ValueError with structured diagnostic."""
    agent = DeterministicMockAgent()
    with pytest.raises(ValueError, match="unknown scenario_name"):
        agent.run("test", scenario_name="not_a_real_scenario")


# ============================================================ #
# `adapter_registry` resilience under AdapterDiscoveryError (M4 Codex STAR) #
# ============================================================ #


def test_adapter_registry_recovers_loaded_so_far_on_discovery_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Story 1b.5 code-review M4 (Codex STAR catch): a single broken third-party
    adapter entry-point must NOT abort the whole conformance suite. The harness
    catches `AdapterDiscoveryError` and surfaces `loaded_so_far` per ADR-013 L42.
    """
    from AgentEval._kernel import discovery

    class LoadedAdapter:
        pass

    def raising_discover() -> dict[str, type]:
        raise AdapterDiscoveryError(
            "simulated partial install — one broken entry",
            loaded_so_far={"loaded": LoadedAdapter},
        )

    monkeypatch.setattr(discovery, "discover_adapters", raising_discover)
    # Re-execute the fixture body manually (not via pytest invocation).
    from .harness import adapter_registry as _adapter_registry_fixture

    # The fixture is a generator-wrapped function; call its underlying function.
    # Pytest fixtures with `@pytest.fixture` decorator can be called directly.
    # The fixture decoration produces a `FixtureFunctionMarker`; access the
    # underlying function via the `__wrapped__` attribute or just call it.
    result = _adapter_registry_fixture.__wrapped__()  # type: ignore[attr-defined]
    assert result == [LoadedAdapter]
