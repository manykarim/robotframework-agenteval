*** Settings ***
Documentation    Story 1a.6 smoke test — verifies that `Library AgentEval`
...              resolves via Robot Framework's static-library discovery
...              model (class with same name as the module) AND that the
...              `Get Effective Config` keyword is discoverable + returns
...              the FR42 + FR11b defaults.
...
...              A regression in the `@keyword` decorator wiring or
...              class-name resolution would break this test while
...              Python-only tier1 tests still pass — this is the RF-side
...              guardrail that complements
...              tests/acceptance/tier1/test_ac_fr42_library_defaults.py.

Library    AgentEval

*** Test Cases ***
AgentEval Library Loads And Get Effective Config Works
    ${config}=    Get Effective Config
    Should Be Equal    ${config["provider"]}    litellm
    Should Be Equal    ${config["trace_backend"]}    memory
    Should Be Equal    ${config["allow_validate_operator"]}    ${False}
    Should Be Equal    ${config["mcp_per_test"]}    ${True}
    Should Be Equal    ${config["allow_external_mcp_blind"]}    ${False}
