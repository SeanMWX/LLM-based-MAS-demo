from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .models import FiveLayerState, Scenario
from .text_utils import bullet_list, compact_one_line, coerce_message_text, format_role_label
from .tracing import append_log, append_trace


def invoke_role_with_read_only_tools(
    demo: Any,
    role: str,
    state: FiveLayerState,
) -> tuple[str, str, list[dict[str, Any]], list[dict[str, Any]]]:
    repo_path = demo.resolve_repo_path(state.get("repo_path"))
    if repo_path is None:
        return demo.invoke_role_model(role, state), state["agent_brief"], [], []

    current_brief = state["agent_brief"]
    tool_events: list[dict[str, Any]] = []
    trace_events: list[dict[str, Any]] = []
    seen_requests: set[str] = set()
    max_tool_rounds = 3

    for round_index in range(1, max_tool_rounds + 1):
        raw_output = demo.invoke_role_model(
            role,
            state,
            agent_brief=current_brief,
        )
        request = demo.parse_tool_request(
            raw_output,
            state.get("available_tools", []),
        )
        if request is None:
            return raw_output, current_brief, tool_events, trace_events

        request_key = json.dumps(request, sort_keys=True, ensure_ascii=False)
        if request_key in seen_requests:
            trace_events.append(
                {
                    "event": "tool_request_rejected",
                    "role": role,
                    "round": round_index,
                    "summary": "duplicate tool request rejected",
                    "request": request,
                }
            )
            current_brief = (
                current_brief
                + "\n\nTool request rejected: duplicate request. "
                "Return final role JSON now without another tool_request."
            )
            continue
        seen_requests.add(request_key)
        trace_events.append(
            {
                "event": "tool_request",
                "role": role,
                "round": round_index,
                "summary": demo.summarize_tool_request(request),
                "request": request,
            }
        )

        result = demo.execute_read_only_tool(repo_path, request)
        tool_events.append(
            {
                "role": role,
                "request": request,
                "result": result,
            }
        )
        trace_events.append(
            {
                "event": "tool_result",
                "role": role,
                "round": round_index,
                "summary": demo.summarize_tool_result(result),
                "request": request,
                "result": result,
            }
        )
        current_brief = demo.append_tool_result_to_brief(
            current_brief,
            request,
            result,
            round_index=round_index,
        )

    final_output = demo.invoke_role_model(role, state, agent_brief=current_brief)
    return final_output, current_brief, tool_events, trace_events


def perception_node(demo: Any, state: FiveLayerState) -> FiveLayerState:
    repo_snapshot: dict[str, Any] = {}
    live_repository_context = ""
    live_file_context = ""
    read_only_files: list[dict[str, str]] = []
    repo_path = demo.resolve_repo_path(state.get("repo_path"))
    if repo_path is not None:
        repo_snapshot = demo.collect_repo_snapshot(repo_path)
        live_repository_context = demo.format_repo_snapshot(repo_snapshot)
        read_only_files = demo.collect_read_only_files(
            repo_path=repo_path,
            snapshot=repo_snapshot,
            state=state,
        )
        live_file_context = demo.format_read_only_files(read_only_files)

    observations = [
        f"Task: {state['task']}",
        f"Repository context: {state['repository_context']}",
        f"Available tools: {', '.join(state['available_tools'])}",
        f"Acceptance criteria count: {len(state['acceptance_criteria'])}",
    ]
    if repo_snapshot:
        observations.append(f"Live repo path: {repo_snapshot['repo_path']}")
        observations.append(f"Live repo file count: {repo_snapshot['file_count']}")
    if read_only_files:
        observations.append(
            f"Read-only file excerpts collected: {len(read_only_files)}"
        )
    observations.extend(
        demo.extend_perception_observations(
            state=state,
            repo_snapshot=repo_snapshot,
            read_only_files=read_only_files,
        )
    )

    return {
        "observations": observations,
        "repo_snapshot": repo_snapshot,
        "live_repository_context": live_repository_context,
        "read_only_files": read_only_files,
        "live_file_context": live_file_context,
        "action_trace": append_trace(
            state,
            {
                "event": "workflow_started",
                "summary": compact_one_line(
                    f"scenario={state['scenario_id']} repo_access_mode={state.get('repo_access_mode', 'synthetic')}"
                ),
            },
        ),
        "execution_log": append_log(
            state,
            "perception: normalized task and repository context",
        ),
    }


def coordination_prepare_node(demo: Any, state: FiveLayerState) -> FiveLayerState:
    seed_role_artifacts = {
        role: deepcopy(artifact)
        for role, artifact in state.get("seed_role_artifacts", {}).items()
        if role in demo.role_order
    }
    seed_role_outputs = demo.normalize_seed_role_outputs(
        state.get("seed_role_outputs", {}),
        seed_role_artifacts,
    )
    seeded_roles = set(seed_role_outputs) | set(seed_role_artifacts)
    next_role_index = demo.resolve_start_role_index(
        state.get("start_role"),
        seeded_roles,
    )

    shared_memory = {
        "task": state["task"],
        "acceptance_criteria": state["acceptance_criteria"],
        "role_outputs": dict(seed_role_outputs),
        "role_artifacts": dict(seed_role_artifacts),
    }
    if state.get("repo_snapshot"):
        shared_memory["repo_snapshot"] = state["repo_snapshot"]
    if state.get("read_only_files"):
        shared_memory["read_only_files"] = state["read_only_files"]
    if state.get("seed_context"):
        shared_memory["seed_context"] = deepcopy(state["seed_context"])
    if state.get("seed_tool_events"):
        shared_memory["tool_events"] = deepcopy(state["seed_tool_events"])
    if state.get("seed_test_run_result"):
        shared_memory["test_run_result"] = deepcopy(state["seed_test_run_result"])
    shared_memory.update(demo.extend_shared_memory(state))

    action_trace = list(state.get("action_trace", []))
    action_trace.extend(deepcopy(state.get("seed_action_trace", [])))
    if seeded_roles or state.get("seed_context") or state.get("start_role"):
        action_trace.append(
            {
                "event": "seed_loaded",
                "summary": compact_one_line(
                    " ".join(
                        part
                        for part in [
                            f"seeded_roles={','.join(sorted(seeded_roles))}"
                            if seeded_roles
                            else "",
                            f"start_role={state.get('start_role')}"
                            if state.get("start_role")
                            else "",
                        ]
                        if part
                    )
                    or "seed payload loaded"
                ),
            }
        )
    return {
        "shared_memory": shared_memory,
        "role_outputs": dict(seed_role_outputs),
        "role_artifacts": dict(seed_role_artifacts),
        "tool_events": deepcopy(state.get("seed_tool_events", [])),
        "test_run_result": deepcopy(state.get("seed_test_run_result", {})),
        "action_trace": action_trace,
        "next_role_index": next_role_index,
        "workflow_status": "running",
        "execution_log": append_log(
            state,
            "coordination: initialized shared memory",
        ),
    }


def behavior_route_node(demo: Any, state: FiveLayerState) -> FiveLayerState:
    index = state.get("next_role_index", 0)
    if index >= len(demo.role_order):
        completed_trace = append_trace(
            state,
            {
                "event": "workflow_completed",
                "summary": "all roles completed",
            },
        )
        final_report = state.get("final_report", "")
        if state.get("role_outputs"):
            final_report = build_final_report(
                demo,
                {**state, "action_trace": completed_trace},
                state.get("role_outputs", {}),
            )
        return {
            "active_role": "",
            "workflow_status": "completed",
            "action_trace": completed_trace,
            "final_report": final_report,
            "execution_log": append_log(
                state,
                "behavior: workflow marked complete",
            ),
        }

    role = demo.role_order[index]
    return {
        "active_role": role,
        "workflow_status": "running",
        "action_trace": append_trace(
            state,
            {
                "event": "role_selected",
                "role": role,
                "summary": f"next_role_index={index}",
            },
        ),
        "execution_log": append_log(
            state,
            f"behavior: selected next role `{role}`",
        ),
    }


def behavior_route_decision(state: FiveLayerState) -> str:
    return "end" if state.get("workflow_status") == "completed" else "continue"


def build_agent_brief(demo: Any, role: str, state: FiveLayerState) -> str:
    prior_outputs = state.get("role_outputs", {})
    role_index = demo.role_order.index(role)

    sections = [
        f"Role: {role}",
        f"User task:\n{state['task']}",
        f"Repository context:\n{state['repository_context']}",
        f"Available tools:\n{bullet_list(state.get('available_tools', []))}",
        f"Repo access mode:\n{state.get('repo_access_mode', 'synthetic')}",
        f"Acceptance criteria:\n{bullet_list(state['acceptance_criteria'])}",
        f"Risk notes:\n{bullet_list(state['risk_notes'])}",
    ]
    if state.get("live_repository_context"):
        sections.append(
            f"Live repository snapshot:\n{state['live_repository_context']}"
        )
    if state.get("live_file_context"):
        sections.append(f"Read-only file excerpts:\n{state['live_file_context']}")
    if state.get("seed_context"):
        sections.append(
            f"Seeded evaluation context:\n{demo.format_seed_context(state['seed_context'])}"
        )
    if (
        state.get("invoke_model")
        and state.get("repo_access_mode") == "read_only"
        and state.get("repo_path")
    ):
        sections.append(
            "\n".join(
                [
                    "Read-only tool protocol:",
                    "If you need more repository context, return JSON only in one of these shapes:",
                    '{"tool_request":{"tool":"search","query":"symbol or phrase","top_k":5}}',
                    '{"tool_request":{"tool":"read_file","path":"relative/path.py"}}',
                    "After you receive tool results, return your final role JSON only.",
                ]
            )
        )

    prior_roles = demo.role_order[:role_index]
    if not prior_roles:
        sections.append("No prior role outputs yet.")
    else:
        for prior_role in prior_roles:
            label = format_role_label(prior_role)
            sections.append(
                f"{label} output:\n{prior_outputs.get(prior_role, '(missing)')}"
            )
    sections.extend(demo.extend_brief_sections(role, state))

    return "\n\n".join(sections)


def communication_brief_node(demo: Any, state: FiveLayerState) -> FiveLayerState:
    role = state["active_role"]
    agent_brief = build_agent_brief(demo, role, state)
    return {
        "agent_brief": agent_brief,
        "action_trace": append_trace(
            state,
            {
                "event": "brief_built",
                "role": role,
                "summary": compact_one_line(agent_brief, max_chars=120),
            },
        ),
        "execution_log": append_log(
            state,
            f"communication: built handoff brief for `{role}`",
        ),
    }


def invoke_role_model(
    demo: Any,
    role: str,
    state: FiveLayerState,
    agent_brief: str | None = None,
) -> str:
    model = demo.build_model(state.get("model_name"))
    if model is None:
        return demo.simulate_role_output(role, state)

    messages = [
        SystemMessage(content=demo.role_system_prompts[role]),
        HumanMessage(content=agent_brief or state["agent_brief"]),
    ]
    response = model.invoke(messages)
    content = response.content

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return coerce_message_text(content)
    return str(content)


def normalize_role_response(
    demo: Any,
    role: str,
    raw_output: str,
    state: FiveLayerState,
) -> tuple[dict[str, Any], str]:
    if demo.normalize_role_output is None:
        return {"raw_output": raw_output}, raw_output
    return demo.normalize_role_output(role, raw_output, state)


def inference_execute_node(demo: Any, state: FiveLayerState) -> FiveLayerState:
    role = state["active_role"]
    tool_events = list(state.get("tool_events", []))
    action_trace = list(state.get("action_trace", []))
    updated_brief = state.get("agent_brief", "")
    if (
        state.get("invoke_model")
        and state.get("repo_access_mode") == "read_only"
        and state.get("repo_path")
    ):
        raw_output, updated_brief, new_tool_events, new_trace_events = invoke_role_with_read_only_tools(
            demo,
            role,
            state,
        )
        tool_events.extend(new_tool_events)
        action_trace.extend(new_trace_events)
    else:
        raw_output = (
            invoke_role_model(demo, role, state)
            if state.get("invoke_model")
            else demo.simulate_role_output(role, state)
        )
    artifact, normalized_output = normalize_role_response(
        demo,
        role,
        raw_output,
        state,
    )
    artifact, normalized_output, state_updates, extra_trace_events = demo.postprocess_role_execution(
        role=role,
        state=state,
        artifact=artifact,
        normalized_output=normalized_output,
    )
    if extra_trace_events:
        action_trace.extend(extra_trace_events)
    test_run_result = state_updates.get("test_run_result", state.get("test_run_result", {}))
    action_trace.append(
        {
            "event": "role_completed",
            "role": role,
            "summary": demo.summarize_artifact(role, artifact),
        }
    )
    return {
        "agent_brief": updated_brief,
        "latest_output": normalized_output,
        "latest_artifact": artifact,
        "test_run_result": test_run_result,
        "tool_events": tool_events,
        "action_trace": action_trace,
        "execution_log": append_log(state, f"inference: executed role `{role}`"),
        **{
            key: value
            for key, value in state_updates.items()
            if key != "test_run_result"
        },
    }


def build_final_report(
    demo: Any,
    state: FiveLayerState,
    updated_outputs: dict[str, str],
) -> str:
    sections = [f"Scenario: {state['title']}"]
    for role in demo.role_order:
        label = format_role_label(role)
        sections.append(f"{label}:\n{updated_outputs.get(role, '')}")
    if state.get("action_trace"):
        sections.append(
            "Action Trace:\n" + demo.format_action_trace(state["action_trace"])
        )
    return "\n\n".join(sections) + "\n"


def coordination_commit_node(demo: Any, state: FiveLayerState) -> FiveLayerState:
    role = state["active_role"]
    updated_outputs = dict(state.get("role_outputs", {}))
    updated_outputs[role] = state["latest_output"]
    updated_artifacts = dict(state.get("role_artifacts", {}))
    updated_artifacts[role] = dict(state.get("latest_artifact", {}))

    shared_memory = dict(state.get("shared_memory", {}))
    shared_memory["role_outputs"] = updated_outputs
    shared_memory["role_artifacts"] = updated_artifacts
    if state.get("tool_events"):
        shared_memory["tool_events"] = state["tool_events"]
    if state.get("action_trace"):
        shared_memory["action_trace"] = state["action_trace"]
    if state.get("test_run_result"):
        shared_memory["test_run_result"] = state["test_run_result"]
    shared_memory[f"{role}_done"] = True

    next_role_index = state.get("next_role_index", 0) + 1
    committed_trace = append_trace(
        state,
        {
            "event": "role_committed",
            "role": role,
            "summary": "output committed to shared memory",
        },
    )

    final_report = state.get("final_report", "")
    if role == demo.role_order[-1]:
        final_report = build_final_report(
            demo,
            {**state, "action_trace": committed_trace},
            updated_outputs,
        )

    return {
        "role_outputs": updated_outputs,
        "role_artifacts": updated_artifacts,
        "shared_memory": shared_memory,
        "next_role_index": next_role_index,
        "final_report": final_report,
        "test_run_result": state.get("test_run_result", {}),
        "tool_events": state.get("tool_events", []),
        "action_trace": committed_trace,
        "execution_log": append_log(
            state,
            f"coordination: committed output for `{role}`",
        ),
    }


def build_graph(demo: Any):
    graph = StateGraph(FiveLayerState)
    graph.add_node("perception", demo.perception_node)
    graph.add_node("coordination_prepare", demo.coordination_prepare_node)
    graph.add_node("behavior_route", demo.behavior_route_node)
    graph.add_node("communication_brief", demo.communication_brief_node)
    graph.add_node("inference_execute", demo.inference_execute_node)
    graph.add_node("coordination_commit", demo.coordination_commit_node)

    graph.add_edge(START, "perception")
    graph.add_edge("perception", "coordination_prepare")
    graph.add_edge("coordination_prepare", "behavior_route")
    graph.add_conditional_edges(
        "behavior_route",
        demo.behavior_route_decision,
        {
            "continue": "communication_brief",
            "end": END,
        },
    )
    graph.add_edge("communication_brief", "inference_execute")
    graph.add_edge("inference_execute", "coordination_commit")
    graph.add_edge("coordination_commit", "behavior_route")

    return graph.compile(checkpointer=MemorySaver())


def scenario_to_initial_state(
    demo: Any,
    scenario: Scenario,
    invoke_model: bool,
    model_name: str | None,
    repo_path: str | None = None,
    test_command: str | None = None,
    test_timeout_sec: int = 120,
    seed_payload: dict[str, Any] | None = None,
    start_role: str | None = None,
) -> FiveLayerState:
    effective_test_command = test_command or scenario.test_command
    merged_seed_payload = demo.build_seed_payload(
        scenario=scenario,
        seed_payload=seed_payload,
        start_role=start_role,
    )
    repo_access_mode: Literal["synthetic", "read_only"] = demo.resolve_access_mode(
        scenario=scenario,
        repo_path=repo_path,
        effective_test_command=effective_test_command,
    )
    available_tools = demo.resolve_available_tools(
        scenario=scenario,
        repo_access_mode=repo_access_mode,
        repo_path=repo_path,
        effective_test_command=effective_test_command,
    )
    return {
        "scenario_id": scenario.id,
        "title": scenario.title,
        "task": scenario.user_task,
        "repository_context": scenario.repository_context,
        "acceptance_criteria": scenario.acceptance_criteria,
        "available_tools": available_tools,
        "risk_notes": scenario.risk_notes,
        "start_role": merged_seed_payload.get("start_role"),
        "repo_path": repo_path,
        "repo_access_mode": repo_access_mode,
        "test_command": effective_test_command,
        "test_timeout_sec": test_timeout_sec,
        "seed_context": deepcopy(merged_seed_payload.get("seed_context", {})),
        "seed_role_outputs": deepcopy(
            merged_seed_payload.get("seed_role_outputs", {})
        ),
        "seed_role_artifacts": deepcopy(
            merged_seed_payload.get("seed_role_artifacts", {})
        ),
        "seed_test_run_result": deepcopy(
            merged_seed_payload.get("seed_test_run_result", {})
        ),
        "seed_tool_events": deepcopy(
            merged_seed_payload.get("seed_tool_events", [])
        ),
        "seed_action_trace": deepcopy(
            merged_seed_payload.get("seed_action_trace", [])
        ),
        "execution_log": [],
        "tool_events": [],
        "invoke_model": invoke_model,
        "model_name": model_name,
    }


def run_scenario(
    demo: Any,
    scenario: Scenario,
    invoke_model: bool,
    model_name: str | None,
    repo_path: str | None = None,
    test_command: str | None = None,
    test_timeout_sec: int = 120,
    seed_payload: dict[str, Any] | None = None,
    start_role: str | None = None,
) -> FiveLayerState:
    graph = build_graph(demo)
    initial_state = scenario_to_initial_state(
        demo,
        scenario=scenario,
        invoke_model=invoke_model,
        model_name=model_name,
        repo_path=repo_path,
        test_command=test_command,
        test_timeout_sec=test_timeout_sec,
        seed_payload=seed_payload,
        start_role=start_role,
    )
    return graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": f"{demo.name}:{scenario.id}"}},
    )


def summarize_state(demo: Any, state: FiveLayerState) -> dict[str, Any]:
    return {
        "scenario_id": state["scenario_id"],
        "title": state["title"],
        "workflow_status": state.get("workflow_status"),
        "active_role": state.get("active_role"),
        "repo_access_mode": state.get("repo_access_mode"),
        "repo_path": state.get("repo_path"),
        "start_role": state.get("start_role"),
        "test_command": state.get("test_command"),
        "role_outputs": state.get("role_outputs", {}),
        "role_artifacts": state.get("role_artifacts", {}),
        "tool_events": state.get("tool_events", []),
        "action_trace": state.get("action_trace", []),
        "action_trace_text": demo.format_action_trace(
            state.get("action_trace", [])
        ),
        "repo_snapshot": state.get("repo_snapshot", {}),
        "live_file_context": state.get("live_file_context", ""),
        "read_only_files": state.get("read_only_files", []),
        "seed_context": state.get("seed_context", {}),
        "test_run_result": state.get("test_run_result", {}),
        "execution_log": state.get("execution_log", []),
        "final_report": state.get("final_report", ""),
    }
