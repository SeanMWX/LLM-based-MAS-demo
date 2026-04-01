# Five-Layer Coding MAS Mapping

This note describes the current `LangGraph` implementation of the minimal five-layer coding MAS.

## Core Idea

The five layers and the role system are different axes:

- the five layers describe system architecture
- the roles describe specialized reasoning responsibilities

Current roles:

- `planner`
- `coder`
- `tester`
- `reviewer`

## Layer-to-Graph Mapping

### 1. Perception

Goal:

- transform the raw scenario into normalized observations

Current node:

- `perception`

Current outputs:

- normalized task summary
- repository context summary
- available tool list
- acceptance criteria count

### 2. Inference

Goal:

- perform role-specific reasoning

Current node:

- `inference_execute`

Current behavior:

- dispatches by `active_role`
- runs either deterministic simulation or a live model call

### 3. Communication

Goal:

- prepare a narrower handoff packet for the next role

Current node:

- `communication_brief`

Current behavior:

- planner sees task and constraints
- coder sees planner output
- tester sees planner and coder outputs
- reviewer sees planner, coder, and tester outputs

### 4. Behavior

Goal:

- decide which role runs next and when the workflow terminates

Current node:

- `behavior_route`

Current policy:

- deterministic sequence
- `planner -> coder -> tester -> reviewer -> complete`

### 5. Coordination

Goal:

- hold shared state and commit role results

Current nodes:

- `coordination_prepare`
- `coordination_commit`

Current shared state:

- task
- repository context
- acceptance criteria
- available tools
- risk notes
- role outputs
- execution log
- final report

## Current Graph Shape

The graph loops through the five-layer cycle:

`perception -> coordination_prepare -> behavior_route -> communication_brief -> inference_execute -> coordination_commit -> behavior_route`

The loop stops when all four roles have completed.

## What Makes This a Good Minimal Baseline

- the layers are explicit
- the state is typed
- the routing logic is inspectable
- the role handoffs are narrow and testable
- the graph can run with or without API keys

## What Is Still Missing

- real repo tools
- real file artifacts
- retry loops
- reviewer rejection branch
- test-failure branch
- human approval gates
- checkpoint restore demo

## Recommended Next Step

The next useful upgrade is:

1. keep the current five-layer topology
2. add real repo observations to the perception layer
3. add a `tester -> coder` retry branch
4. add a `reviewer -> coder` correction branch
5. convert free-text outputs into typed artifacts

That will keep the architecture simple while making it much closer to a usable coding MAS.
