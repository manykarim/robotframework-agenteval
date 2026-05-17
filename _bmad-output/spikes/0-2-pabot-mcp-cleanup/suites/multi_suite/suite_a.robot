*** Settings ***
Documentation     Story 0.2 spike — suite-scope / process-scope candidate suite a.
...               4 tests per suite × 4 suites = 16 tests total (matches AC-0.2.1's 16-test mandate).
...               Used WITHOUT --testlevelsplit so multiple tests share a worker.

*** Test Cases ***
A01    Log    suite-a-T01
A02    Log    suite-a-T02
A03    Log    suite-a-T03
A04    Log    suite-a-T04
