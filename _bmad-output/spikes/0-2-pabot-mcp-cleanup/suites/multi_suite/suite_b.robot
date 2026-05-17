*** Settings ***
Documentation     Story 0.2 spike — suite-scope / process-scope candidate suite b.
...               4 tests per suite × 4 suites = 16 tests total (matches AC-0.2.1's 16-test mandate).
...               Used WITHOUT --testlevelsplit so multiple tests share a worker.

*** Test Cases ***
B01    Log    suite-b-T01
B02    Log    suite-b-T02
B03    Log    suite-b-T03
B04    Log    suite-b-T04
