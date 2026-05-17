*** Settings ***
Documentation     Story 0.2 spike — Task 7 Listener v3 reliability under test timeout.
...               Architecture.md L710 specifically calls this out: "if Listener v3 hooks
...               prove unreliable (e.g., `end_test` not firing on test timeout), spike
...               pivots to context-manager-per-test + `atexit` fallback."
...
...               Each test sleeps PAST its [Timeout]. RF should abort and we observe:
...                   (a) Does end_test fire and release_test get called?
...                   (b) Does the atexit failsafe in MCPLifecycleManager need to act?

*** Test Cases ***
Timeout During Test 1
    [Timeout]    500ms
    Sleep    2s

Timeout During Test 2
    [Timeout]    500ms
    Sleep    2s

Timeout During Test 3
    [Timeout]    500ms
    Sleep    2s

Timeout During Test 4
    [Timeout]    500ms
    Sleep    2s
