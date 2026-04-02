# `coding_agent` Demo

This is the first demo in the repository. It models a minimal coding workflow with four agents:

- `planner`
- `coder`
- `tester`
- `reviewer`

The role order is:

`planner -> coder -> tester -> reviewer`

## Five-Layer Mapping

- `perception`: normalize the task and repository context
- `communication`: prepare the handoff brief for the active role
- `inference`: run the active role in simulation mode or with a live model
- `behavior`: choose the next role and stop when the workflow completes
- `coordination`: initialize shared memory and commit outputs after each step

## Files

- `demo.py`: demo-specific implementation that subclasses `FiveLayerDemo` and keeps coding-only behavior out of `framework/`
- `benchmark_cases.json`: the local scenarios for this demo
- `seeds/`: optional seeded proposal artifacts for reviewer/tester-start evaluation

## Run

```powershell
conda activate py12langgraph
python .\coding_agent\demo.py list
python .\coding_agent\demo.py render --case simple_feature_python
python .\coding_agent\demo.py run --case simple_feature_python
```

To start from a seeded reviewer/tester-style evaluation instead of `planner`, use:

```powershell
conda activate py12langgraph
python .\coding_agent\demo.py run `
  --case simple_feature_python `
  --seed-file .\coding_agent\seeds\reviewer_hypothesis.json
```

The seed file can inject:

- `start_role`
- prior `seed_role_artifacts` or `seed_role_outputs`
- seeded `test_run_result`
- extra `seed_context` such as a hypothetical diff or proposal summary

With a real repository in read-only mode plus real test execution:

```powershell
conda activate py12langgraph
python .\coding_agent\demo.py run `
  --case simple_feature_python `
  --repo-path . `
  --test-command "python -m pytest tests -q" `
  --test-timeout 120
```

This does not allow file writes. It only:

- snapshots the target repo during `perception`
- reads a small set of real text files and includes numbered excerpts in the brief
- allows live-model roles to ask for extra `search` or `read_file` context before returning final JSON
- exposes `search`, `read_file`, and `run_tests`
- runs the configured command during the `tester` step

When `--invoke` is used together with `--repo-path`, a role may request more context with JSON like:

```json
{"tool_request":{"tool":"search","query":"normalize_slug","top_k":5}}
```

or:

```json
{"tool_request":{"tool":"read_file","path":"utils/helpers.py"}}
```

The framework appends the result to the brief and asks the role again. These rounds are recorded in `tool_events`.
The overall workflow also records a higher-level `action_trace` and `action_trace_text`.

With API keys:

```powershell
python .\coding_agent\demo.py run --case simple_feature_python --invoke
```

With MiniMax:

```powershell
conda activate py12langgraph
copy .env.example .env
# then edit .env and fill in MINIMAX_API_KEY
python .\coding_agent\demo.py run --case simple_feature_python --invoke
```

Current repository-side `.env` fields:

```env
MINIMAX_API_KEY=your_key
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
MINIMAX_MODEL=MiniMax-M2.5
MINIMAX_MAX_TOKENS=1024
```

## Test

```powershell
conda activate py12langgraph
python -m pytest tests -q
```

## Purpose

This demo is the baseline scaffold for future MAS demos. It keeps the graph simple on purpose so the repository can grow by adding more demo directories instead of overloading one monolithic script.
The shared rule is: `framework/` stays abstract; coding-specific tool, test, and review behavior stays in `coding_agent/`.
