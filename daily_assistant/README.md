# `daily_assistant` Demo

This demo models a personal daily-assistant workflow with four agents:

- `intake_router_agent`
- `email_manager_agent`
- `drive_manager_agent`
- `assistant_review_agent`

The role order is:

`intake_router_agent -> email_manager_agent -> drive_manager_agent -> assistant_review_agent`

## Purpose

This is the third demo in the repository. It validates that the shared five-layer framework can also support a personal productivity workflow rather than a coding or enterprise ticketing workflow.

The current version is intentionally conservative:

- read-only email and drive context
- local policy-rule context
- confirmation queue and assistant action-log context
- sandboxed mail and drive adapter context
- draft-only replies and recommendations
- no automatic send, move, or share actions

## Current Phase

This demo currently runs in:

- `Phase 3B: sandboxed mail/drive adapters`

That means:

- everything from Phase 3A still applies
- proposed email and drive actions are recorded in an assistant action log
- confirmation-gated steps are enqueued into a confirmation queue
- sandboxed mail/drive staging receipts are generated for proposed actions
- the review step now returns queue, action-log, and adapter verdicts

## Phase 1

Phase 1 implemented:

- user requests are routed across email and drive context
- email threads can be summarized and turned into draft replies
- drive items can be searched and turned into suggested file actions
- the final review step checks whether user confirmation is still required

## Phase 2 Scope

Phase 2 adds:

- local policy-rule retrieval
- email-side policy flags
- drive-side sharing requirements
- policy evidence review before final response
- explicit safe-action gating for external send/share scenarios

## Phase 3A Scope

Phase 3A adds:

- assistant action-log entries for proposed email and drive steps
- generated receipt ids for proposed actions
- confirmation queue records for confirmation-gated actions
- review-side queue and action-log checks
- simulation-time auditability for future benchmark cases

Still not included yet:

- no real email send capability
- no file move or permission-change capability
- no external calendar or task backend

## Phase 3B Scope

Phase 3B adds:

- local sandbox adapter manifests for email and drive
- simulated mail-adapter staging receipts
- simulated drive-adapter staging receipts
- review-side adapter evidence and adapter verdicts
- a clearer boundary between proposed actions and sandbox-staged actions

Still not included yet:

- no real email send capability
- no real file move or permission-change capability
- sandbox adapters are still synthetic, not live integrations
- no external calendar or task backend

## Five-Layer Mapping

- `perception`: normalize the user request plus email/drive context
- `communication`: prepare the handoff brief between assistant roles
- `inference`: let each role classify, summarize, or review the request
- `behavior`: move to the next role and end after review
- `coordination`: maintain shared context and commit structured artifacts

## Files

- `demo.py`: demo-specific implementation that subclasses `FiveLayerDemo`
- `benchmark_cases.json`: local daily-assistant scenarios
- `email_threads.json`: local email-thread metadata used by the demo
- `drive_index.json`: local drive-item metadata used by the demo
- `policy_rules.json`: local policy rules used for confirmation gating and review
- `sandbox_adapters.json`: local sandbox-adapter manifests used by Phase 3B
- `PHASES.md`: a compact record of what Phase 1, Phase 2, Phase 3A, and Phase 3B mean
- `phase_status.json`: machine-readable phase status

## Run

```powershell
conda activate py12langgraph
python .\daily_assistant\demo.py list
python .\daily_assistant\demo.py render --case reply_with_latest_quarterly_deck
python .\daily_assistant\demo.py run --case reply_with_latest_quarterly_deck
```

Run all daily-assistant scenarios:

```powershell
conda activate py12langgraph
python .\daily_assistant\demo.py run --case all
```

## Available Tools

The current phase keeps the tool surface small and read-only:

- `search_email`
- `read_email_thread`
- `draft_reply`
- `search_drive`
- `read_drive_metadata`
- `suggest_drive_action`
- `search_policy`
- `read_policy_rule`
- `record_assistant_action`
- `read_assistant_action_log`
- `record_confirmation_request`
- `read_confirmation_queue`
- `stage_mail_adapter_action`
- `read_mail_adapter_receipts`
- `stage_drive_adapter_action`
- `read_drive_adapter_receipts`

These are still simulated. The current goal is to validate routing, artifact structure, safety gating, and sandbox-adapter evidence before adding any live integrations.

## Current Scope

This demo is still simulation-only. Its main purpose is to prove that the same five-layer framework can support a personal productivity assistant with multi-source routing, policy-aware gating, confirmation queues, auditable action traces, and sandboxed execution-adapter evidence, while keeping the framework itself domain-agnostic.
