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
|-- framework/
|   |-- __init__.py
|   \-- core.py
|-- coding_agent/
|   |-- README.md
|   |-- __init__.py
|   |-- demo.py
|   |-- benchmark_cases.json
|   \-- seeds/
|-- tests/
|-- mas_benchmark_demo.py
|-- environment.yml
|-- requirements.txt
|-- FIVE_LAYER_CODING_MAS.md
|-- EXPLOITABILITY_MATRIX.md
\-- mas_target.tex
```

`framework/core.py` holds the shared five-layer engine, scenario loading, and CLI plumbing.
`mas_benchmark_demo.py` is kept as a compatibility entrypoint and forwards to `coding_agent/demo.py`.
The active scenario file for this demo is `coding_agent/benchmark_cases.json`; scenarios now live under each demo directory rather than the repository root.

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

`framework/core.py` now supports MiniMax through the official Anthropic-compatible SDK flow documented by MiniMax.
The simplest local setup is:

```powershell
conda activate py12langgraph
copy .env.example .env
# then edit .env and fill in MINIMAX_API_KEY
python .\coding_agent\demo.py run --case simple_feature_python --invoke
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

## Testing

Run the offline test suite with:

```powershell
conda activate py12langgraph
python -m pytest tests -q
```

What is covered right now:

- simulation-mode graph execution for all coding-agent scenarios
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
- `demo.py`: demo-specific configuration that imports the shared engine from `framework/`
- `benchmark_cases.json`: the scenarios for that demo

## How To Add A New Demo

After `coding_agent` is stable, create a new demo with the same pattern:

1. Create a new folder such as `negotiation_agent/` or `memory_agent/`.
2. Copy the three baseline files from `coding_agent/`: `README.md`, `demo.py`, and `benchmark_cases.json`.
3. In the new `demo.py`, keep the shared import from `framework/` and only replace the role list, prompts, and simulation logic.
4. Update the scenario data in the local `benchmark_cases.json`.
5. Keep the five-layer mapping explicit, even if the role set changes.
6. Add the new demo to this root README with its run command.

Minimal checklist for a new demo:

- uses `conda activate py12langgraph`
- has a local `benchmark_cases.json`
- exposes `list`, `render`, and `run`
- imports the shared engine from `framework/`
- documents its agent roles
- states how its graph maps to the five layers

## Current Scope

Right now this repository focuses on framework setup and demo organization. It is not yet a full security benchmark suite; the current priority is to make each demo clean, modular, and easy to extend.
