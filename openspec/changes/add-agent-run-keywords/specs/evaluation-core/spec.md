## MODIFIED Requirements

### Requirement: One coding-agent adapter seam with a single generic adapter

The spine SHALL define an `AgentRunResult` type and a `run(prompt) -> AgentRunResult` adapter protocol, and SHALL ship the generic adapter backed by LiteLLM as the default. It MAY ship additional built-in adapters — the in-process pydantic-ai adapter and the coding-agent CLI adapters — provided every one satisfies the same protocol and resolves through this one seam. Any surface keyword that drives an agent SHALL resolve its adapter through this seam.

#### Scenario: Agent-mode keyword runs through the generic adapter

- **WHEN** a Tier-3 keyword is invoked with a configured model and no explicit adapter
- **THEN** it constructs the generic LiteLLM adapter, runs the prompt, and returns a populated `AgentRunResult`

#### Scenario: A custom adapter satisfies the protocol

- **WHEN** a user passes an object exposing `run(prompt) -> AgentRunResult`
- **THEN** the keyword uses it without requiring any vendor-specific base class

#### Scenario: A built-in adapter is selected by slug through the one seam

- **WHEN** a user resolves an adapter by a built-in slug (`generic`, `in-process`, or a coding-agent CLI)
- **THEN** the seam returns a concrete adapter satisfying the protocol, and its result is a normalized `AgentRunResult`

## ADDED Requirements

### Requirement: The adapter seam is reachable via a stable public entrypoint

The adapter factory (`get_adapter`) and the `Adapter` protocol SHALL be reachable
from a stable, public import path (`AgentEval.get_adapter` / `AgentEval.Adapter`),
not only from the internal `_core` namespace that the stability contract marks as
non-public. The re-export SHALL NOT eagerly import the optional LLM/agent
dependencies (they SHALL remain lazily imported at run time), and documentation and
examples SHALL reference the public entrypoint or the `Agent.*` keywords rather than
the `_core` path. The internal `_core` path SHALL continue to function so existing
callers are not broken.

#### Scenario: Public entrypoint resolves an adapter

- **WHEN** a user imports `get_adapter` from the top-level `AgentEval` package and
  requests an adapter by slug
- **THEN** an adapter satisfying the `Adapter` protocol is returned, without the
  LLM/agent extras being imported unless and until a run occurs

#### Scenario: Docs no longer teach the internal path

- **WHEN** the shipped documentation and keyword examples show how to obtain an
  adapter
- **THEN** they reference the stable public entrypoint (or the `Agent.*` keywords),
  not `AgentEval._core.adapter.get_adapter`
