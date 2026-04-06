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
- draft-only replies and recommendations
- no automatic send, move, or share actions

## Phase 1 Scope

This demo currently runs in:

- `Phase 1: email + drive read-only draft mode`

That means:

- user requests are routed across email and drive context
- email threads can be summarized and turned into draft replies
- drive items can be searched and turned into suggested file actions
- the final review step checks whether user confirmation is still required

Still not included yet:

- no real email send capability
- no file move or permission-change capability
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

The Phase 1 demo keeps the tool surface small and read-only:

- `search_email`
- `read_email_thread`
- `draft_reply`
- `search_drive`
- `read_drive_metadata`
- `suggest_drive_action`

These are still simulated. The current goal is to validate routing, artifact structure, and safety gating before adding any live integrations.

## Current Scope

This demo is still simulation-only. Its main purpose is to prove that the same five-layer framework can support a personal productivity assistant with multi-source routing and review constraints, while keeping the framework itself domain-agnostic.
