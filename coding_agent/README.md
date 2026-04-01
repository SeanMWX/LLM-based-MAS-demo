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

- `demo.py`: demo-specific configuration on top of the shared `framework/` engine
- `benchmark_cases.json`: the local scenarios for this demo

## Run

```powershell
conda activate py12langgraph
python .\coding_agent\demo.py list
python .\coding_agent\demo.py render --case simple_feature_python
python .\coding_agent\demo.py run --case simple_feature_python
```

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

## Test

```powershell
conda activate py12langgraph
python -m pytest tests -q
```

## Purpose

This demo is the baseline scaffold for future MAS demos. It keeps the graph simple on purpose so the repository can grow by adding more demo directories instead of overloading one monolithic script.
