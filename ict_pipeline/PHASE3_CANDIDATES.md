# `ict_pipeline` Phase 3 Candidates

This file defines the Phase 3 transition after `Phase 2: ticket + KB`.

The goal is to keep `framework/` abstract and push all ICT-specific environment logic into `ict_pipeline/`.

## Recommendation

Current status:

1. `ticket + executor action log`: implemented
2. `ticket + DB + human approval`: implemented

The reason is practical:

- action-log support gives the pipeline auditable execution evidence without immediately introducing database and approval complexity
- that evidence becomes the right substrate for later approval and coordination checks
- it also produces better benchmark artifacts earlier, because you can compare claimed execution versus recorded execution

## Candidate A: `ticket + executor action log`

This step is now implemented in the repo.

What changes:

- `executor_agent` stops only describing what happened and starts emitting structured action-log records
- `audit_agent` checks receipts, chronology, and consistency between the claimed result and the recorded actions
- shared memory stores execution evidence rather than only narrative summaries

Why this is the better first move:

- it improves benchmarkability immediately
- it stays close to the current Phase 2 simulation design
- it does not require a full persistent store yet
- it directly supports security cases around forged evidence, missing evidence, and audit bypass

Suggested tools:

- `record_action_log`
- `read_action_log`
- `read_executor_receipt`

Suggested artifact extensions:

- `executor_agent`
  - `action_log_entries`
  - `receipt_ids`
  - `execution_verdict`
- `audit_agent`
  - `action_log_review`
  - `receipt_consistency`
  - `audit_verdict`

## Candidate B: `ticket + DB + human approval`

This step is now implemented in the repo.

What changes:

- ticket state moves into a persistent record
- approval-gated tickets branch into a human decision path
- `executor_agent` must respect pending or denied approvals
- `audit_agent` verifies that approval state and final ticket state stay aligned

Why this comes second:

- it adds more enterprise realism, but also more moving parts
- it depends on stable execution evidence and status transitions
- it is easier to reason about approval correctness if action logging already exists

Suggested tools:

- `read_ticket_db`
- `update_ticket_db`
- `request_human_approval`
- `read_approval_status`

Suggested artifact extensions:

- `triage_agent`
  - `approval_required`
  - `approval_route`
  - `approval_reason`
- `executor_agent`
  - `db_updates`
  - `approval_wait_state`
  - `execution_blockers`
- `audit_agent`
  - `approval_chain_review`
  - `db_state_consistency`
  - `closure_eligibility`

## Security Benchmark Value

`ticket + executor action log` is best for:

- forged execution claims
- missing receipts
- fake closure evidence
- audit failure under incomplete traces

`ticket + DB + human approval` is best for:

- approval bypass
- stale or poisoned coordination state
- premature closure
- divergence between persisted ticket state and approval history

## Testing Expectations

The implementation should keep these tests mandatory:

- deterministic simulation should keep producing stable artifacts
- new role fields should stay inside a fixed vocabulary or schema
- audit should reject incomplete evidence or missing approvals
- status transitions should remain consistent with the intended workflow
