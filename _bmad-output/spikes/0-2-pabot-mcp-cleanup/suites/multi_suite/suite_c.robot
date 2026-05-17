*** Settings ***
Documentation     Story 0.2 spike — suite-scope / process-scope candidate suite c.
...               4 tests per suite × 4 suites = 16 tests total (matches AC-0.2.1's 16-test mandate).
...               Used WITHOUT --testlevelsplit so multiple tests share a worker.

*** Test Cases ***
C01    Log    suite-c-T01
C02    Log    suite-c-T02
C03    Log    suite-c-T03
C04    Log    suite-c-T04
