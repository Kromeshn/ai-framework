---
name: human-plan-code-review
description: Review code changes after another agent implemented a Human Plan. Use when asked to check an implementation against a Human Plan, review another agent's code, find behavioral regressions, runtime risks, missing tests, and Python quality issues using dignified-python as the Python checklist when available.
---

# Human Plan Code Review

Review code as a second agent after implementation. Do not implement fixes unless explicitly asked.

## Review Priority

Report findings first. Prioritize:

1. Behavior that contradicts the Human Plan.
2. Runtime bugs, broken edge cases, swallowed errors, bad API behavior, and regressions.
3. Missing tests for planned behavior or risky branches.
4. Python quality issues that affect correctness or maintainability.

Do not report taste-only refactors, broad rewrites, or improvements outside the requested scope.

## Workflow

1. Find the relevant Human Plan. If it is not discoverable, ask which plan to use.
2. Inspect git status and diff. If there is no clean diff, review the current implementation against the plan and say so.
3. Read only the files needed to understand the changed behavior.
4. Run available focused checks such as tests, import/compile checks, lint, or type checks. Do not install tools unless asked.
5. Compare implementation against three layers:
   - Human Plan compliance: does the code implement exactly the planned behavior, boundaries, and validation?
   - Behavior/runtime risks: errors, edge cases, regressions, broken contracts, and swallowed exceptions.
   - Dignified Python: boring, explicit, local code; LBYL; no swallowed exceptions; type hints; minimal changes. If the `dignified-python` skill is available, use it as the Python checklist.
6. Report concrete findings with file and line references.

## Output Format

Start with `Findings`.

For each finding include:

- severity: P0, P1, P2, or P3
- concrete problem
- file and line reference
- why it matters
- expected behavior from the Human Plan when relevant

Then include:

- `Test Gaps`
- `Checks Run`
- `Residual Risk`

If no issues are found, say so clearly and still mention unverified areas.
