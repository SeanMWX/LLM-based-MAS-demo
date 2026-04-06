# Demo Stage Snapshot

Last updated: April 6, 2026

This file is the quickest way to resume work in a future session.

## Shared Rule

- `framework/` is the shared five-layer abstraction and runtime
- domain-specific logic belongs in implementation folders such as `coding_agent/`, `ict_pipeline/`, and `daily_assistant/`
- future demos should subclass `FiveLayerDemo` instead of pushing one-off business logic into `framework/`

## `coding_agent`

Current stage:

- proposal-level and read-only coding workflow scaffold

Roles:

- `planner`
- `coder`
- `tester`
- `reviewer`

Implemented:

- simulation mode and live MiniMax invocation
- read-only repository inspection
- optional real `test_command` execution during `tester`
- structured role artifacts
- seeded reviewer/tester evaluation
- read-only tool loop for `search` and `read_file`
- action trace and tool trace

Not implemented yet:

- no real file-write or patch-apply step
- no candidate-repo execution after applying a patch
- no real diff-based reviewer step yet

Research use right now:

- workflow-level and proposal-level security benchmark work
- seeded-result or hypothetical-result evaluation
- read-only coding-agent orchestration studies

## `ict_pipeline`

Current stage:

- `Phase 3B: ticket + KB + executor action log + DB + human approval`

Roles:

- `intake_agent`
- `triage_agent`
- `executor_agent`
- `audit_agent`

Implemented:

- KB-backed routing and execution guidance
- executor action-log entries and receipt evidence
- simulated ticket DB snapshot
- approval-state tracking and approval-history review
- audit review over KB evidence, execution evidence, DB state, and approval chain

Not implemented yet:

- no real external ticketing backend
- no real human approval backend
- no adversarial benchmark cases yet

Research use right now:

- enterprise workflow benchmark design
- approval-aware multi-agent state tracking
- action-log and audit-trace studies
- process-level security benchmark work

## `daily_assistant`

Current stage:

- `Phase 1: email + drive read-only draft mode`

Roles:

- `intake_router_agent`
- `email_manager_agent`
- `drive_manager_agent`
- `assistant_review_agent`

Implemented:

- email and drive routing
- draft-only email reply generation
- drive reference and archive suggestions
- review step for confirmation and permission checks

Not implemented yet:

- no real email send
- no real file move or share
- no calendar or task integrations

Research use right now:

- personal-assistant workflow studies
- cross-source routing between email and drive
- privacy and confirmation-gating benchmark design

## Suggested Resume Prompts

- `Read DEMO_STAGE_SNAPSHOT.md and continue coding_agent from its current stage.`
- `Read DEMO_STAGE_SNAPSHOT.md and continue ict_pipeline from Phase 3B.`
- `Read DEMO_STAGE_SNAPSHOT.md and continue daily_assistant from Phase 1.`
