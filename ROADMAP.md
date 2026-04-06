# Repository Roadmap

Last updated: April 7, 2026

This file is the working roadmap for the repository.
Use it together with `DEMO_STAGE_SNAPSHOT.md`:

- `DEMO_STAGE_SNAPSHOT.md` tells you where each demo is now
- `ROADMAP.md` tells you what should be built next

## Shared Goal

The repository is moving toward a reusable five-layer MAS research framework with multiple domain demos that can later support security benchmark work.

The design rule stays fixed:

- `framework/` owns the shared five-layer runtime and generic extension hooks
- each demo folder owns domain logic, schemas, prompts, environment assets, and post-role behavior

## Current State

### `framework/`

Current role:

- shared five-layer runtime
- shared CLI and scenario runner
- shared state, tracing, seeding, provider loading, and parsing utilities

Already in place:

- demo-agnostic `FiveLayerDemo` hooks
- seeding support
- action trace and tool trace
- provider support including MiniMax
- read-only repo tooling for demos that need it

Main gap:

- the framework still lacks a benchmark-oriented scoring layer shared across demos

## `coding_agent`

Current stage:

- proposal-level and read-only coding workflow scaffold

Current strengths:

- stable `planner -> coder -> tester -> reviewer` flow
- simulation mode and live MiniMax mode
- read-only repository inspection
- optional real `test_command`
- seeded evaluation starting from `tester` or `reviewer`
- live-model read-only tool loop for `search` and `read_file`

### Must-Have Next

1. Structured candidate patch artifact
   Make `coder` produce a machine-usable patch representation instead of only `patch_summary`.
2. Candidate-repo execution
   Apply the candidate patch in an isolated temporary workspace or worktree.
3. Candidate test result
   Distinguish `baseline_test_result` from `candidate_test_result`.
4. Diff-based reviewer
   Let `reviewer` inspect the real candidate diff instead of only proposal text.

### Nice-to-Have

- repair loop from `tester/reviewer` back to `coder`
- richer patch schema with touched files and intent annotations
- selective test targeting instead of one command string
- model-side planning vs execution separation

### Security-Benchmark-Specific

- seeded malicious patch cases
- fake claim / fake test / fake summary cases
- metrics such as:
  - `unsafe_patch_accepted`
  - `false_pass_on_candidate`
  - `review_false_approve`
  - `tool_overreach`

### Recommended Next Step

- implement `coder -> candidate patch artifact -> isolated apply -> candidate test -> reviewer on diff`

## `ict_pipeline`

Current stage:

- `Phase 3B: ticket + KB + executor action log + DB + human approval`

Current strengths:

- KB-backed routing
- action-log and receipt evidence
- simulated ticket DB snapshot
- approval-state tracking
- approval-history review
- audit over KB, execution evidence, DB state, and approval chain

### Must-Have Next

1. Benchmark case expansion
   Add adversarial and failure-oriented ticket cases instead of only normal workflow cases.
2. More explicit actor model
   Represent requester, executor, approver, and affected system identity more clearly.
3. Time and SLA semantics
   Add overdue, escalation timeout, and stale-approval conditions.

### Nice-to-Have

- multi-ticket queue state
- asynchronous pause/resume flow
- external adapter boundary for DB and approval backends
- ticket lifecycle analytics and aggregate queue metrics

### Security-Benchmark-Specific

- approval spoofing and stale approval
- forged action-log or receipt mismatch
- KB poisoning or wrong-route evidence
- DB inconsistency after executor step
- cross-ticket state contamination

### Recommended Next Step

- build adversarial benchmark cases on top of the current simulated DB and approval model before connecting real backends

## `daily_assistant`

Current stage:

- `Phase 3B: sandboxed mail/drive adapters`

Current strengths:

- email + drive routing
- policy-aware gating
- confirmation queue
- assistant action log
- sandboxed adapter receipts
- review-side adapter evidence

### Must-Have Next

1. Confirmation resolution flow
   Add what happens after the user confirms or rejects a queued action.
2. Adapter state transition model
   Make sandbox adapters move between staged, approved, rejected, and expired states.
3. Permission model
   Add clearer recipient/file sensitivity and sharing-boundary checks.

### Nice-to-Have

- calendar and task sources
- contact and org-context signals
- richer attachment/file-body reasoning
- multi-step assistant sessions instead of one-shot scenarios

### Security-Benchmark-Specific

- prompt injection from email content
- poisoned drive metadata
- over-sharing to external recipients
- wrong-thread or wrong-file association
- privacy leak through confirmation bypass

### Recommended Next Step

- implement `confirmation queue -> user decision -> sandbox adapter state transition -> final review`

## Cross-Demo Benchmark Roadmap

The repository is not yet at one unified benchmark format.
That should be the next repo-level milestone after the next demo-specific steps.

### Must-Have Shared Benchmark Pieces

1. Shared benchmark artifact schema
   Common fields for traces, evidence, verdicts, safety outcomes, and failure reasons.
2. Shared scoring layer
   Demo-specific metrics can vary, but the framework should expose a common score envelope.
3. Shared case taxonomy
   Separate:
   - normal workflow cases
   - seeded-result cases
   - adversarial cases
   - recovery / retry cases

### Nice-to-Have Shared Pieces

- benchmark result exporter
- aggregate report generation
- per-demo scorecards
- compare-two-model or compare-two-config runs

## Suggested Build Order

If the goal is to move toward security benchmark research efficiently, the recommended order is:

1. `coding_agent`: candidate patch + candidate test + diff review
2. `daily_assistant`: confirmation resolution and adapter state transitions
3. `ict_pipeline`: adversarial benchmark cases over approval / DB / KB evidence
4. shared benchmark artifact and scoring schema

## Resume Prompts

- `Read ROADMAP.md and DEMO_STAGE_SNAPSHOT.md, then continue coding_agent from the recommended next step.`
- `Read ROADMAP.md and DEMO_STAGE_SNAPSHOT.md, then continue ict_pipeline from the recommended next step.`
- `Read ROADMAP.md and DEMO_STAGE_SNAPSHOT.md, then continue daily_assistant from the recommended next step.`
