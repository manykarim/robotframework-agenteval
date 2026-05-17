*** Settings ***
Documentation     Story 0.2 spike — suite-scope / process-scope candidate suite d.
...               4 tests per suite × 4 suites = 16 tests total (matches AC-0.2.1's 16-test mandate).
...               Used WITHOUT --testlevelsplit so multiple tests share a worker.

*** Test Cases ***
D01    Log    suite-d-T01
D02    Log    suite-d-T02
D03    Log    suite-d-T03
D04    Log    suite-d-T04
