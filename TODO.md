# TODO

## Immediate

- Add a `tester -> coder` retry loop when verification fails.
- Add a `reviewer -> coder` correction loop for rejected patches.
- Add typed artifacts for `plan`, `patch_summary`, `test_report`, and `review_report`.
- Add a structured JSON output mode for each role.

## Short Term

- Replace simulated repo context with real repo adapters:
- `git status`
- file tree
- code search
- file read
- test command execution

- Add a basic tool policy per role:
- planner: read-only
- coder: read and edit
- tester: run tests and read diagnostics
- reviewer: read diffs and test reports

## Medium Term

- Add a checkpointer-backed resume flow.
- Add human approval before destructive actions.
- Add scenario scoring and CSV export.
- Add LangSmith traces for every layer.

## Security Follow-Up

- Benchmark perception-layer poisoning.
- Benchmark communication-layer prompt injection.
- Benchmark coordination-layer memory poisoning.
- Benchmark reviewer bypass and false-positive approval.
