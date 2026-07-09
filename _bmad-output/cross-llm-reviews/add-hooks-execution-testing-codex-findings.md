# Codex security review: add-hooks-execution-testing

Scope reviewed: working-tree diff for `src/AgentEval/hooks/_matcher.py`, `_payload.py`, `_runner.py`, additions to `hooks/library.py`, and OpenSpec files under `openspec/changes/add-hooks-execution-testing/`.

## Findings

### HIGH: Catastrophic regex matchers can hang the parent process before hook timeout applies

- Location: `src/AgentEval/hooks/_matcher.py:110`, `src/AgentEval/hooks/_matcher.py:140`, `src/AgentEval/hooks/library.py:322`, `src/AgentEval/hooks/library.py:561`, `src/AgentEval/hooks/library.py:594`
- Problem: matcher evaluation uses Python `re.search()` directly in the AgentEval parent process. `Fire Hook Event` evaluates matchers before spawning the hook subprocess, and `Validate Matcher Syntax` can also run `compiled.search(subject)`. The subprocess timeout and process-group kill do not apply to this phase.
- Exploit/failure scenario: a config with matcher `(a+)+$` and a subject such as `"a" * 28 + "!"` blocks the test runner before any hook is spawned. A malicious or accidentally pathological matcher can DoS the suite, and the hook `timeout` setting is irrelevant because execution never reaches `Popen`.
- Reproduction run:
  - `timeout 5 uv run python - <<'PY' ... lib.fire_hook_event({'PreToolUse':[{'type':'command','matcher':'(a+)+$','command':'echo should-not-run'}]}, 'PreToolUse', tool_name='a'*28+'!', default_timeout=1) ... PY`
  - Result: external `timeout` killed the Python process with `exit=124`.
  - The same external-timeout result occurred for `lib.validate_matcher_syntax('(a+)+$', subject='a'*28+'!')`.
- Recommended fix: use a regex engine with time limits or linear-time guarantees (for example RE2-style semantics), add match/validation timeouts around regex evaluation, or reject/limit regex patterns and subject lengths. Invalid-regex compile checking is not enough; valid regexes can still be pathological.

### MED: `LC_*` env prefix leaks parent secret-bearing variables despite default-deny intent

- Location: `src/AgentEval/hooks/_runner.py:69`, `src/AgentEval/hooks/_runner.py:180`, `src/AgentEval/hooks/_runner.py:190`
- Problem: default-deny mode copies every parent variable whose name starts with `LC_`. That is broader than locale variables and allows arbitrary secret-bearing names such as `LC_SECRET_TOKEN`, `LC_OPENAI_API_KEY`, or `LC_AWS_SECRET_ACCESS_KEY` to reach the hook subprocess even when `inherit_env=False`.
- Exploit/failure scenario: a CI/test environment has a secret stored under an `LC_`-prefixed variable, or an attacker with control over parent env naming places a secret under `LC_AWS_SECRET_ACCESS_KEY`. A third-party hook script can read it from `os.environ` during `Hook.Fire Hook Event` despite the documented "parent secrets NOT inherited" default.
- Reproduction run:
  - Parent env set: `ANTHROPIC_API_KEY=anthropic-secret`, `OPENAI_API_KEY=openai-secret`, `AWS_SECRET_ACCESS_KEY=aws-secret`, `AWS_SESSION_TOKEN=aws-token`, `LC_SECRET_TOKEN=lc-secret`.
  - Fired `tests/fixtures/hooks/exec/echo_env.py` with default `inherit_env=False`.
  - Observed in child env: API/AWS keys absent, but `LC_SECRET_TOKEN` present.
- Recommended fix: replace prefix copying with an explicit locale allowlist (`LC_ALL`, `LC_COLLATE`, `LC_CTYPE`, `LC_MESSAGES`, `LC_MONETARY`, `LC_NUMERIC`, `LC_TIME`, etc.), and/or apply a final deny filter for names containing `SECRET`, `TOKEN`, `KEY`, `AWS`, `ANTHROPIC`, `OPENAI`.

### MED: Timeout cleanup can leave intentionally detached descendants running

- Location: `src/AgentEval/hooks/_runner.py:199`, `src/AgentEval/hooks/_runner.py:202`, `src/AgentEval/hooks/_runner.py:244`, `src/AgentEval/hooks/_runner.py:253`, `src/AgentEval/hooks/_runner.py:271`
- Problem: `start_new_session=True` plus `os.killpg(os.getpgid(proc.pid), SIGKILL)` kills the process group created for the immediate hook process. A hook can spawn a descendant that calls `setsid` / creates a new session before the timeout. That descendant is outside the killed process group and can continue after `Fire Hook Event` returns `timed_out`.
- Exploit/failure scenario: a malicious hook command can leave a local background process running after a timed-out test, continuing to mutate files, exfiltrate data over the network, or interfere with later tests. This contradicts the stronger documentation wording that orphaned children of a shell hook die too.
- Reproduction run:
  - Command: `setsid sh -c 'sleep 3; touch /tmp/agenteval_detached_timeout_child_marker' >/dev/null 2>&1 & sleep 60`, hook timeout `1`.
  - `Fire Hook Event` returned `status='timed_out'`.
  - Four seconds later, `/tmp/agenteval_detached_timeout_child_marker` existed.
- Recommended fix: document this as an explicit non-sandbox limitation, or use an OS containment primitive that can kill descendants outside the original process group (Linux cgroup/job object equivalent). At minimum, avoid claiming process-group kill reliably kills all orphaned descendants.

### LOW: Invalid UTF-8 stdout/stderr crashes `Fire Hook Event` instead of recording a result

- Location: `src/AgentEval/hooks/_runner.py:244`, `src/AgentEval/hooks/_runner.py:250`, `src/AgentEval/hooks/_runner.py:271`
- Problem: subprocess pipes are opened with `text=True`, so `communicate()` decodes output using the locale codec with strict errors. A hook that writes invalid bytes can raise `UnicodeDecodeError` in the parent. This aborts the fire and prevents later matching hooks from being reported, contrary to the "execution failures are recorded, not raised mid-fire" design goal.
- Reproduction run:
  - Exec-form hook: `python -c 'import sys; sys.stdout.buffer.write(b"\xff")'`
  - Result: `UnicodeDecodeError 'utf-8' codec can't decode byte 0xff ...`
- Recommended fix: capture bytes and decode with `errors="replace"` or set `errors="replace"` in `Popen`, then record the completed hook with replacement characters in stdout/stderr.

## Checks with no substantive findings

- Env default: `inherit_env` defaults to `False` in `Hook.Fire Hook Event` and `build_hook_env`; no path found that silently flips it to true.
- Specific provider secrets: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` were absent from the hook child env by default in the adversarial probe.
- `CLAUDE_PROJECT_DIR`: copied intentionally from `project_dir` / cwd and not a secret by itself. It is not sandboxing; hooks can still read files reachable by the invoking user.
- Shell injection: the synthesized hook payload is serialized with `json.dumps()` and passed via `proc.communicate(input=stdin_payload)`, not interpolated into the shell command. A payload containing shell metacharacters did not create a marker file.
- Exec form: when `args` is present, the runner passes `[command, *args]` with `shell=False`; an argument containing `; touch ...` was printed literally and did not execute.
- Timeout for ordinary descendants: a shell background child that remained in the hook process group was killed; marker file was not created.
- Decision normalization: exit code `2` returns `block` and ignores stdout JSON; exit `0` plus `permissionDecision` maps `deny` to `block`, `allow` to `allow`, `ask` to `ask`, `defer` to `none`; top-level `decision: "block"` works.
- Fake-green paths: zero-match fire raises `HookExecutionError`; spawn failures and timeouts are recorded as non-completed records; decision/exit-code assertions fail loud on non-completed records.

## Verification commands run

- `git status --short && git diff --stat && git diff -- src/AgentEval/hooks/_matcher.py src/AgentEval/hooks/_payload.py src/AgentEval/hooks/_runner.py src/AgentEval/hooks/library.py`
- `rg --files openspec/changes/add-hooks-execution-testing src/AgentEval/hooks tests | sort`
- `rg -n "inherit_env|allowlist|env|shell|subprocess|start_new_session|killpg|timeout|permissionDecision|decision|exit|matcher|regex|Fire Hook|Decision Should|Command Should|Validate Matcher|CLAUDE_PROJECT_DIR|ANTHROPIC|OPENAI|AWS" src/AgentEval/hooks openspec/changes/add-hooks-execution-testing tests`
- `uv run python - <<'PY' ...` adversarial probes for env leakage, shell/args payload injection, process-group timeout, detached timeout child, regex ReDoS, and invalid UTF-8 output.
- `uv run pytest tests/unit/hooks/test_execution.py -q` - 50 passed.
- `uv run pytest -q -k 'hook or hooks'` - 182 passed, 2119 deselected.
