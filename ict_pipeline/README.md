# `ict_pipeline` Demo

This demo models a simple enterprise ICT ticket pipeline with four agents:

- `intake_agent`
- `triage_agent`
- `executor_agent`
- `audit_agent`

The role order is:

`intake_agent -> triage_agent -> executor_agent -> audit_agent`

## Purpose

This is a non-coding demo that validates the repository rule:

- `framework/` stays abstract and owns the five-layer runtime
- `ict_pipeline/` owns its domain roles, schemas, prompts, and simulated business behavior

The demo focuses on ticket intake, routing, execution planning, and audit/closure decisions for enterprise ICT workflows.

## Phase 3B Scope

This demo now runs in:

- `Phase 3B: ticket + KB + executor action log + DB + human approval`

That means:

- local KB retrieval is part of the workflow
- routing should be justified with KB evidence
- executor actions should stay aligned with KB recommendations
- executor steps should emit structured action-log entries and receipt IDs
- executor should also persist ticket-state and approval-state updates into a simulated ticket DB
- approval-gated work should stay blocked until the approval state is recorded
- audit should review KB evidence, execution evidence, ticket DB state, and approval history before closure or escalation

Still not included yet:

- no real external ticketing database yet
- no real human-in-the-loop approval backend yet

The current focus is only:

- ticket intake
- category extraction
- priority selection
- queue routing
- KB-backed routing evidence
- KB-backed execution guidance
- action-log capture
- receipt consistency review
- ticket DB snapshot updates
- approval-state tracking
- approval-history review
- status transition
- close / escalate / needs-info decision

## Phase 3B Vocabulary

The current version uses a fixed vocabulary so the pipeline is easier to benchmark.

- categories: `access_request`, `onboarding`, `incident`, `service_request`
- priorities: `low`, `medium`, `high`, `critical`
- queues: `service_desk`, `access_management`, `onboarding`, `local_support`, `escalation`
- statuses: `new`, `triaged`, `queued`, `waiting_human`, `resolved`, `escalated`, `closed`
- KB confidence: `low`, `medium`, `high`
- execution verdicts: `recorded`, `pending_human`, `escalated`, `completed`
- receipt consistency: `consistent`, `missing`, `inconsistent`
- audit verdicts: `evidence_ok`, `followup_required`, `reject`
- approval routes: `not_required`, `identity_verification`, `finance_manager_approval`
- approval wait states: `not_required`, `pending`, `approved`, `denied`
- DB state consistency: `consistent`, `missing_update`, `inconsistent`
- closure eligibility: `eligible`, `blocked_by_approval`, `blocked_by_state`
- audit decisions: `Close`, `Escalate`, `Needs info`

## Five-Layer Mapping

- `perception`: normalize the incoming ticket and environment context
- `communication`: build the handoff brief between the current and next agent
- `inference`: let the active agent classify, route, or decide the next action
- `behavior`: move the workflow to the next agent or end it
- `coordination`: maintain the shared ticket state and commit artifacts after each role

## Files

- `demo.py`: demo-specific implementation that subclasses `FiveLayerDemo`
- `benchmark_cases.json`: local ICT ticket scenarios
- `kb_articles.json`: local knowledge-base articles used by routing and execution
- `PHASE3_CANDIDATES.md`: the record of the Phase 3 implementation path
- `phase3_candidates.json`: machine-readable Phase 3 candidate specification

## Run

```powershell
conda activate py12langgraph
python .\ict_pipeline\demo.py list
python .\ict_pipeline\demo.py render --case vpn_access_reset
python .\ict_pipeline\demo.py run --case vpn_access_reset
```

Run all ICT scenarios:

```powershell
conda activate py12langgraph
python .\ict_pipeline\demo.py run --case all
```

## Current Scope

The current version is still simulation-only. It does not yet connect to a real external ticketing system or approval backend. The goal is to prove that the same five-layer framework can support a non-coding workflow with knowledge-backed routing, auditable execution evidence, and approval-aware state transitions before adding richer external integrations.

## Phase 3 Candidates

The next-step candidates are documented here:

- [PHASE3_CANDIDATES.md](/d:/Github_repo/LLM-based-MAS-demo/ict_pipeline/PHASE3_CANDIDATES.md)
- [phase3_candidates.json](/d:/Github_repo/LLM-based-MAS-demo/ict_pipeline/phase3_candidates.json)

Current status:

1. `ticket + executor action log`: implemented
2. `ticket + DB + human approval`: implemented

Phase 3 is now fully implemented inside `ict_pipeline/`. The next major step is no longer another Phase 3 candidate, but deciding whether Phase 4 should focus on real external integrations or benchmark-oriented adversarial cases.
