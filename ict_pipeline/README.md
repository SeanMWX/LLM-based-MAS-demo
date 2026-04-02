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

## Phase 1 Scope

This demo is explicitly the simplest environment:

- `Phase 1: pure ticket system / queue`

That means:

- no KB retrieval yet
- no database persistence layer yet
- no human approval workflow yet
- no executor action log yet

The current focus is only:

- ticket intake
- category extraction
- priority selection
- queue routing
- status transition
- close / escalate / needs-info decision

## Phase 1 Vocabulary

The first version uses a fixed vocabulary so the pipeline is easier to benchmark.

- categories: `access_request`, `onboarding`, `incident`, `service_request`
- priorities: `low`, `medium`, `high`, `critical`
- queues: `service_desk`, `access_management`, `onboarding`, `local_support`, `escalation`
- statuses: `new`, `triaged`, `queued`, `waiting_human`, `resolved`, `escalated`, `closed`
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

The first version is simulation-only. It does not yet connect to a real ticketing system or database. The goal is to prove that the same five-layer framework can support a non-coding workflow before adding richer external integrations.
