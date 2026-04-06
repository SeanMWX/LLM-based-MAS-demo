# LLM-based MAS Framework

This repository is organized as a small framework for building `LangGraph` demos around a five-layer view of LLM-based multi-agent systems:

1. `perception`
2. `inference`
3. `communication`
4. `behavior`
5. `coordination`

The first demo now lives in `coding_agent/`. It models a simple coding workflow with four agents:

- `planner`
- `coder`
- `tester`
- `reviewer`

There is now a second demo in `ict_pipeline/`. It models a simple enterprise ICT ticket flow with four agents:

- `intake_agent`
- `triage_agent`
- `executor_agent`
- `audit_agent`

The current `ict_pipeline` version is explicitly `Phase 3B: ticket + KB + executor action log + DB + human approval`.

There is now a third demo in `daily_assistant/`. It models a personal productivity workflow with four agents:

- `intake_router_agent`
- `email_manager_agent`
- `drive_manager_agent`
- `assistant_review_agent`

The current `daily_assistant` version is explicitly `Phase 1: email + drive read-only draft mode`.

## Environment

Use the Conda environment `py12langgraph`.

```powershell
conda env create -f environment.yml
conda activate py12langgraph
```

The framework auto-loads the repo-root `.env` file when it starts.

## Repository Layout

```text
LLM-based-MAS-demo/
|-- .env.example
|-- .gitignore
|-- DEMO_STAGE_SNAPSHOT.md
|-- framework/
|   |-- __init__.py
|   |-- core.py
|   |-- runtime.py
|   |-- workflow.py
|   |-- cli.py
|   |-- repo_tools.py
|   |-- seeding.py
|   |-- providers.py
|   |-- text_utils.py
|   |-- env.py
|   \-- models.py
|-- coding_agent/
|   |-- README.md
|   |-- __init__.py
|   |-- demo.py
|   |-- benchmark_cases.json
|   \-- seeds/
|-- ict_pipeline/
|   |-- README.md
|   |-- __init__.py
|   |-- demo.py
|   |-- kb_articles.json
|   |-- PHASE3_CANDIDATES.md
|   |-- phase3_candidates.json
|   \-- benchmark_cases.json
|-- daily_assistant/
|   |-- README.md
|   |-- __init__.py
|   |-- demo.py
|   |-- benchmark_cases.json
|   |-- email_threads.json
|   \-- drive_index.json
|-- tests/
|-- mas_benchmark_demo.py
|-- environment.yml
|-- requirements.txt
|-- FIVE_LAYER_CODING_MAS.md
|-- EXPLOITABILITY_MATRIX.md
\-- mas_target.tex
```

`framework/runtime.py` is now a thin facade over the shared framework surface.
`framework/workflow.py` holds graph-node behavior, runtime transitions, and scenario execution.
`framework/cli.py` holds CLI parsing and scenario rendering helpers.
`framework/core.py` is kept as a narrow compatibility layer for legacy imports used by existing demos and tests.
`mas_benchmark_demo.py` is kept as a compatibility entrypoint and forwards to `coding_agent/demo.py`.
Scenario files now live under each demo directory rather than the repository root, for example `coding_agent/benchmark_cases.json` and `ict_pipeline/benchmark_cases.json`.
The tracked `.vscode/` settings file was intentionally removed; local IDE settings are now treated as user-local and ignored by Git.

Framework rule:
- `framework/` is the shared five-layer abstraction and runtime.
- domain-specific behavior belongs in implementation folders such as `coding_agent/`
- future demos should subclass `FiveLayerDemo` and override hooks instead of adding one-off domain logic to framework internals

Stage snapshot:
- `DEMO_STAGE_SNAPSHOT.md` records the current implementation stage of the existing demos so a future session can resume from a stable checkpoint quickly

Current `FiveLayerDemo` extension hooks include:
- `resolve_access_mode(...)`
- `resolve_available_tools(...)`
- `extend_perception_observations(...)`
- `extend_shared_memory(...)`
- `extend_brief_sections(...)`
- `postprocess_role_execution(...)`

## First Demo: `coding_agent`

Run the demo with:

```powershell
conda activate py12langgraph
python .\coding_agent\demo.py list
python .\coding_agent\demo.py render --case simple_feature_python
python .\coding_agent\demo.py run --case simple_feature_python
```

To evaluate a seeded hypothetical proposal instead of starting from `planner`, pass a seed file:

```powershell
conda activate py12langgraph
python .\coding_agent\demo.py run `
  --case simple_feature_python `
  --seed-file .\coding_agent\seeds\reviewer_hypothesis.json
```

This mode lets you pre-populate prior role artifacts, hypothetical diffs or claims, seeded test results, and a `start_role` such as `tester` or `reviewer`.

To let the demo inspect a real repository in read-only mode and have the `tester` run a real command, pass `--repo-path` and `--test-command`:

```powershell
conda activate py12langgraph
python .\coding_agent\demo.py run `
  --case simple_feature_python `
  --repo-path . `
  --test-command "python -m pytest tests -q" `
  --test-timeout 120
```

In this mode the framework:

- collects a lightweight repository snapshot during `perception`
- reads a small set of real text files and injects numbered excerpts into the agent brief
- lets live-model roles request extra read-only context with `search` and `read_file` tool requests
- narrows available tools to `search`, `read_file`, and `run_tests`
- executes the real test command during the `tester` step
- stores the command result in `test_run_result` and injects it into the reviewer brief

Those coding-specific behaviors are implemented by the `coding_agent` demo class, not by the shared framework core.

For live model calls in read-only mode, the framework also supports an internal tool-request loop. A role can ask for more context by returning JSON such as:

```json
{"tool_request":{"tool":"search","query":"normalize_slug","top_k":5}}
```

or:

```json
{"tool_request":{"tool":"read_file","path":"utils/helpers.py"}}
```

The framework executes the request, appends the result to the brief, and asks the role again. Executed tool rounds are exposed in `tool_events`.
At the workflow level, the framework also emits a higher-level `action_trace` plus human-readable `action_trace_text`.

If an API key is configured, you can switch from deterministic simulation to live model calls:

```powershell
python .\coding_agent\demo.py run --case simple_feature_python --invoke
python .\coding_agent\demo.py run --case all --invoke
```

### MiniMax

`framework/providers.py` now supports MiniMax through the official Anthropic-compatible SDK flow documented by MiniMax.
The simplest local setup is:

```powershell
conda activate py12langgraph
copy .env.example .env
# then edit .env and fill in MINIMAX_API_KEY
python .\coding_agent\demo.py run --case simple_feature_python --invoke
```

The current repository expects MiniMax settings in `.env`, for example:

```env
MINIMAX_API_KEY=your_key
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
MINIMAX_MODEL=MiniMax-M2.5
MINIMAX_MAX_TOKENS=1024
```

Optional:

- set `MINIMAX_MAX_TOKENS` if you want a different completion budget
- set `--model ...` on the command line to override `MINIMAX_MODEL`

If you prefer exporting environment variables in the shell instead of using `.env`, this also works:

```powershell
conda activate py12langgraph
$env:ANTHROPIC_API_KEY="your_minimax_key"
$env:ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
python .\coding_agent\demo.py run --case simple_feature_python --invoke --model MiniMax-M2.5
```

Compatibility entrypoint:

```powershell
python .\mas_benchmark_demo.py list
```

## Second Demo: `ict_pipeline`

Run the ICT pipeline demo with:

```powershell
conda activate py12langgraph
python .\ict_pipeline\demo.py list
python .\ict_pipeline\demo.py render --case vpn_access_reset
python .\ict_pipeline\demo.py run --case vpn_access_reset
```

This demo is intentionally non-coding. It uses the same five-layer runtime to model intake, triage, execution, and audit for enterprise ICT ticket workflows.
Its current focus is `Phase 3B: ticket + KB + executor action log + DB + human approval`, with local knowledge-base articles bundled inside `ict_pipeline/kb_articles.json`.
Its planned next-step candidates are documented in `ict_pipeline/PHASE3_CANDIDATES.md` and `ict_pipeline/phase3_candidates.json`.

## Third Demo: `daily_assistant`

Run the daily-assistant demo with:

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

This demo is intentionally read-only and draft-only. It uses the same five-layer runtime to model a personal assistant that routes across email and drive context, drafts email replies, suggests drive actions, and finishes with a review step that enforces confirmation and permission checks.
Its current focus is `Phase 1: email + drive read-only draft mode`, with local synthetic datasets bundled inside `daily_assistant/email_threads.json` and `daily_assistant/drive_index.json`.

## Testing

Run the offline test suite with:

```powershell
conda activate py12langgraph
python -m pytest tests -q
```

What is covered right now:

- framework hook defaults and extension points
- simulation-mode graph execution for all coding-agent scenarios
- simulation-mode graph execution for all ICT pipeline scenarios
- simulation-mode graph execution for all daily-assistant scenarios
- ICT pipeline Phase 3B vocabulary, KB matches, routing expectations, and approval-state behavior
- daily-assistant Phase 1 routing, vocabulary normalization, and email/drive dataset matching
- executor action-log and receipt-evidence behavior in the ICT pipeline
- ticket DB snapshot and approval-history behavior in the ICT pipeline
- read-only repository snapshot collection and real test-command execution
- seeded proposal and reviewer/tester-start evaluation
- structured output normalization and fallback parsing
- snapshot coverage for stable `role_artifacts`
- mocked provider coverage for `thinking + text`, invalid JSON, and truncated JSON
- environment loading behavior for `.env`
- communication-layer handoff narrowing

There is also an optional live MiniMax smoke test, but it is skipped by default:

```powershell
conda activate py12langgraph
$env:RUN_LIVE_MODEL_TESTS="1"
python -m pytest tests\test_live_model_optional.py -q
```

## Demo Convention

Each demo should be self-contained in its own top-level directory. The minimum recommended layout is:

```text
<demo_name>/
|-- README.md
|-- demo.py
|-- benchmark_cases.json
\-- seeds/   # optional
```

Recommended responsibilities:

- `README.md`: what this demo studies, which agents it uses, and how to run it
- `demo.py`: demo-specific implementation that subclasses `FiveLayerDemo` and owns domain hooks, prompts, schemas, and simulation logic
- `benchmark_cases.json`: the scenarios for that demo

## How To Add A New Demo

After `coding_agent` is stable, create a new demo with the same pattern:

1. Create a new folder such as `negotiation_agent/` or `memory_agent/`.
2. Copy the baseline files from an existing demo that is closest to your domain:
   `coding_agent/` for coding workflows, `ict_pipeline/` for operational workflows, or `daily_assistant/` for read-only assistant workflows.
3. In the new `demo.py`, subclass `FiveLayerDemo` and keep domain-specific behavior in the demo folder.
4. Use demo-level hooks for tool sets, environment actions, brief extras, and post-role execution behavior.
5. Replace the role list, prompts, schemas, and simulation logic with the new domain's implementation.
6. Update the scenario data in the local `benchmark_cases.json`.
7. Keep the five-layer mapping explicit, even if the role set changes.
8. Add the new demo to this root README with its run command.

Minimal checklist for a new demo:

- uses `conda activate py12langgraph`
- has a local `benchmark_cases.json`
- exposes `list`, `render`, and `run`
- imports the shared engine from `framework/`
- keeps domain logic out of `framework/`
- documents its agent roles
- states how its graph maps to the five layers

## Current Scope

Right now this repository focuses on framework setup and demo organization. It is not yet a full security benchmark suite; the current priority is to make each demo clean, modular, and easy to extend.
