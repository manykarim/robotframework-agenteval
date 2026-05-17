*** Settings ***
Documentation     Story 0.1 spike — pabot concurrency probe (post-D1+D2+D3+P11).
...               15 tests across all THREE mcp_coverage states (AC-0.1.1):
...                 - 6× dual-transport probe → hosted_in_process (D1 trust-floor when both paths fire)
...                 - 3× in-memory-only probe → hosted_in_process
...                 - 3× subprocess-only probe → subprocess_with_observer (D2 handler-wrap in subprocess)
...                 - 3× external_mixed probe → external_mixed (adapter signals path failure)
...               Per-test fresh observer instance (TEST scope library).
Library           SpikeLibrary.py

*** Test Cases ***
T01 Dual Transport
    Run Dual Transport Probe              T01
    Assert MCP Coverage Was               hosted_in_process
    Assert Tool Call Count Was            4

T02 Dual Transport
    Run Dual Transport Probe              T02
    Assert MCP Coverage Was               hosted_in_process
    Assert Tool Call Count Was            4

T03 Dual Transport
    Run Dual Transport Probe              T03
    Assert MCP Coverage Was               hosted_in_process
    Assert Tool Call Count Was            4

T04 Dual Transport
    Run Dual Transport Probe              T04
    Assert MCP Coverage Was               hosted_in_process
    Assert Tool Call Count Was            4

T05 Dual Transport
    Run Dual Transport Probe              T05
    Assert MCP Coverage Was               hosted_in_process
    Assert Tool Call Count Was            4

T06 Dual Transport
    Run Dual Transport Probe              T06
    Assert MCP Coverage Was               hosted_in_process
    Assert Tool Call Count Was            4

T07 Hosted In Process Only
    Run Hosted In Process Probe           T07
    Assert MCP Coverage Was               hosted_in_process
    Assert Tool Call Count Was            2

T08 Hosted In Process Only
    Run Hosted In Process Probe           T08
    Assert MCP Coverage Was               hosted_in_process
    Assert Tool Call Count Was            2

T09 Hosted In Process Only
    Run Hosted In Process Probe           T09
    Assert MCP Coverage Was               hosted_in_process
    Assert Tool Call Count Was            2

T10 Subprocess Only
    Run Subprocess Only Probe             T10
    Assert MCP Coverage Was               subprocess_with_observer
    Assert Tool Call Count Was            2

T11 Subprocess Only
    Run Subprocess Only Probe             T11
    Assert MCP Coverage Was               subprocess_with_observer
    Assert Tool Call Count Was            2

T12 Subprocess Only
    Run Subprocess Only Probe             T12
    Assert MCP Coverage Was               subprocess_with_observer
    Assert Tool Call Count Was            2

T13 External Mixed
    Run External Mixed Probe              T13
    Assert MCP Coverage Was               external_mixed
    Assert Tool Call Count Was            1

T14 External Mixed
    Run External Mixed Probe              T14
    Assert MCP Coverage Was               external_mixed
    Assert Tool Call Count Was            1

T15 External Mixed
    Run External Mixed Probe              T15
    Assert MCP Coverage Was               external_mixed
    Assert Tool Call Count Was            1
