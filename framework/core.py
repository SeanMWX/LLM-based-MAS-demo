from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"


@dataclass
class Scenario:
    id: str
    title: str
    user_task: str
    repository_context: str
    acceptance_criteria: list[str]
    available_tools: list[str]
    risk_notes: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scenario":
        return cls(**data)


class FiveLayerState(TypedDict, total=False):
    scenario_id: str
    title: str
    task: str
    repository_context: str
    acceptance_criteria: list[str]
    available_tools: list[str]
    risk_notes: list[str]
    observations: list[str]
    shared_memory: dict[str, Any]
    next_role_index: int
    active_role: str
    agent_brief: str
    latest_output: str
    latest_artifact: dict[str, Any]
    role_outputs: dict[str, str]
    role_artifacts: dict[str, dict[str, Any]]
    execution_log: list[str]
    workflow_status: Literal["running", "completed"]
    final_report: str
    invoke_model: bool
    model_name: str | None


RoleSimulator = Callable[[str, FiveLayerState], str]
RoleOutputNormalizer = Callable[[str, str, FiveLayerState], tuple[dict[str, Any], str]]


def bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def format_role_label(role: str) -> str:
    return role.replace("_", " ").title()


def append_log(state: FiveLayerState, message: str) -> list[str]:
    return [*state.get("execution_log", []), message]


def parse_env_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        return None

    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()

    if not key:
        return None

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]

    return key, value


def load_repo_env(env_path: Path = ENV_PATH) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = parse_env_line(raw_line)
        if parsed is None:
            continue

        key, value = parsed
        os.environ.setdefault(key, value)


def first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def coerce_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(content)


load_repo_env()


class MiniMaxAnthropicAdapter:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0,
        max_tokens: int = 2048,
    ) -> None:
        import anthropic

        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def invoke(self, messages: list[Any]):
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, str]] = []

        for message in messages:
            text = coerce_message_text(message.content)

            if isinstance(message, SystemMessage):
                system_parts.append(text)
            elif isinstance(message, HumanMessage):
                anthropic_messages.append({"role": "user", "content": text})
            elif isinstance(message, AIMessage):
                anthropic_messages.append({"role": "assistant", "content": text})
            else:
                anthropic_messages.append({"role": "user", "content": text})

        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": anthropic_messages,
        }
        if system_parts:
            request_kwargs["system"] = "\n\n".join(system_parts)

        response = self.client.messages.create(**request_kwargs)

        text_parts: list[str] = []
        thinking_parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(str(block.text))
            elif hasattr(block, "text"):
                text_parts.append(str(block.text))
            elif hasattr(block, "thinking"):
                thinking_parts.append(str(block.thinking))

        parts = text_parts if text_parts else thinking_parts
        return SimpleNamespace(content="\n".join(part for part in parts if part).strip())


@dataclass
class FiveLayerDemo:
    name: str
    description: str
    cases_path: Path
    role_order: list[str]
    role_system_prompts: dict[str, str]
    simulate_role_output: RoleSimulator
    normalize_role_output: RoleOutputNormalizer | None = None

    def load_scenarios(self) -> dict[str, Scenario]:
        data = json.loads(self.cases_path.read_text(encoding="utf-8"))
        scenarios = [Scenario.from_dict(item) for item in data]
        return {scenario.id: scenario for scenario in scenarios}

    def build_model(self, model_name: str | None):
        minimax_base_url = first_env("MINIMAX_BASE_URL", "ANTHROPIC_BASE_URL")
        minimax_api_key = first_env(
            "MINIMAX_API_KEY",
            "MINIMAX_AUTH_TOKEN",
        )
        minimax_base_url_is_selected = bool(
            minimax_base_url and "minimax" in minimax_base_url.lower()
        )

        if minimax_api_key or minimax_base_url_is_selected:
            resolved_api_key = minimax_api_key or first_env(
                "ANTHROPIC_API_KEY",
                "ANTHROPIC_AUTH_TOKEN",
            )
            if resolved_api_key:
                return MiniMaxAnthropicAdapter(
                    api_key=resolved_api_key,
                    base_url=minimax_base_url or "https://api.minimax.io/anthropic",
                    model=model_name
                    or first_env("MINIMAX_MODEL", "ANTHROPIC_MODEL")
                    or "MiniMax-M2.5",
                    temperature=0,
                    max_tokens=env_int("MINIMAX_MAX_TOKENS", 2048),
                )

        if os.getenv("ANTHROPIC_API_KEY"):
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=model_name or "claude-3-5-sonnet-latest",
                temperature=0,
            )

        if os.getenv("OPENAI_API_KEY"):
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model_name or "gpt-4o-mini",
                temperature=0,
            )

        return None

    def perception_node(self, state: FiveLayerState) -> FiveLayerState:
        observations = [
            f"Task: {state['task']}",
            f"Repository context: {state['repository_context']}",
            f"Available tools: {', '.join(state['available_tools'])}",
            f"Acceptance criteria count: {len(state['acceptance_criteria'])}",
        ]
        return {
            "observations": observations,
            "execution_log": append_log(
                state,
                "perception: normalized task and repository context",
            ),
        }

    def coordination_prepare_node(self, state: FiveLayerState) -> FiveLayerState:
        shared_memory = {
            "task": state["task"],
            "acceptance_criteria": state["acceptance_criteria"],
            "role_outputs": {},
            "role_artifacts": {},
        }
        return {
            "shared_memory": shared_memory,
            "role_outputs": {},
            "role_artifacts": {},
            "next_role_index": 0,
            "workflow_status": "running",
            "execution_log": append_log(
                state,
                "coordination: initialized shared memory",
            ),
        }

    def behavior_route_node(self, state: FiveLayerState) -> FiveLayerState:
        index = state.get("next_role_index", 0)
        if index >= len(self.role_order):
            return {
                "active_role": "",
                "workflow_status": "completed",
                "execution_log": append_log(
                    state,
                    "behavior: workflow marked complete",
                ),
            }

        role = self.role_order[index]
        return {
            "active_role": role,
            "workflow_status": "running",
            "execution_log": append_log(
                state,
                f"behavior: selected next role `{role}`",
            ),
        }

    def behavior_route_decision(self, state: FiveLayerState) -> str:
        return "end" if state.get("workflow_status") == "completed" else "continue"

    def build_agent_brief(self, role: str, state: FiveLayerState) -> str:
        prior_outputs = state.get("role_outputs", {})
        role_index = self.role_order.index(role)

        sections = [
            f"Role: {role}",
            f"User task:\n{state['task']}",
            f"Repository context:\n{state['repository_context']}",
            f"Acceptance criteria:\n{bullet_list(state['acceptance_criteria'])}",
            f"Risk notes:\n{bullet_list(state['risk_notes'])}",
        ]

        prior_roles = self.role_order[:role_index]
        if not prior_roles:
            sections.append("No prior role outputs yet.")
        else:
            for prior_role in prior_roles:
                label = format_role_label(prior_role)
                sections.append(
                    f"{label} output:\n{prior_outputs.get(prior_role, '(missing)')}"
                )

        return "\n\n".join(sections)

    def communication_brief_node(self, state: FiveLayerState) -> FiveLayerState:
        role = state["active_role"]
        return {
            "agent_brief": self.build_agent_brief(role, state),
            "execution_log": append_log(
                state,
                f"communication: built handoff brief for `{role}`",
            ),
        }

    def invoke_role_model(self, role: str, state: FiveLayerState) -> str:
        model = self.build_model(state.get("model_name"))
        if model is None:
            return self.simulate_role_output(role, state)

        messages = [
            SystemMessage(content=self.role_system_prompts[role]),
            HumanMessage(content=state["agent_brief"]),
        ]
        response = model.invoke(messages)
        content = response.content

        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return coerce_message_text(content)
        return str(content)

    def normalize_role_response(
        self,
        role: str,
        raw_output: str,
        state: FiveLayerState,
    ) -> tuple[dict[str, Any], str]:
        if self.normalize_role_output is None:
            return {"raw_output": raw_output}, raw_output
        return self.normalize_role_output(role, raw_output, state)

    def inference_execute_node(self, state: FiveLayerState) -> FiveLayerState:
        role = state["active_role"]
        raw_output = (
            self.invoke_role_model(role, state)
            if state.get("invoke_model")
            else self.simulate_role_output(role, state)
        )
        artifact, normalized_output = self.normalize_role_response(
            role,
            raw_output,
            state,
        )
        return {
            "latest_output": normalized_output,
            "latest_artifact": artifact,
            "execution_log": append_log(state, f"inference: executed role `{role}`"),
        }

    def build_final_report(
        self,
        state: FiveLayerState,
        updated_outputs: dict[str, str],
    ) -> str:
        sections = [f"Scenario: {state['title']}"]
        for role in self.role_order:
            label = format_role_label(role)
            sections.append(f"{label}:\n{updated_outputs.get(role, '')}")
        return "\n\n".join(sections) + "\n"

    def coordination_commit_node(self, state: FiveLayerState) -> FiveLayerState:
        role = state["active_role"]
        updated_outputs = dict(state.get("role_outputs", {}))
        updated_outputs[role] = state["latest_output"]
        updated_artifacts = dict(state.get("role_artifacts", {}))
        updated_artifacts[role] = dict(state.get("latest_artifact", {}))

        shared_memory = dict(state.get("shared_memory", {}))
        shared_memory["role_outputs"] = updated_outputs
        shared_memory["role_artifacts"] = updated_artifacts
        shared_memory[f"{role}_done"] = True

        next_role_index = state.get("next_role_index", 0) + 1

        final_report = state.get("final_report", "")
        if role == self.role_order[-1]:
            final_report = self.build_final_report(state, updated_outputs)

        return {
            "role_outputs": updated_outputs,
            "role_artifacts": updated_artifacts,
            "shared_memory": shared_memory,
            "next_role_index": next_role_index,
            "final_report": final_report,
            "execution_log": append_log(
                state,
                f"coordination: committed output for `{role}`",
            ),
        }

    def build_graph(self):
        graph = StateGraph(FiveLayerState)
        graph.add_node("perception", self.perception_node)
        graph.add_node("coordination_prepare", self.coordination_prepare_node)
        graph.add_node("behavior_route", self.behavior_route_node)
        graph.add_node("communication_brief", self.communication_brief_node)
        graph.add_node("inference_execute", self.inference_execute_node)
        graph.add_node("coordination_commit", self.coordination_commit_node)

        graph.add_edge(START, "perception")
        graph.add_edge("perception", "coordination_prepare")
        graph.add_edge("coordination_prepare", "behavior_route")
        graph.add_conditional_edges(
            "behavior_route",
            self.behavior_route_decision,
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
        self,
        scenario: Scenario,
        invoke_model: bool,
        model_name: str | None,
    ) -> FiveLayerState:
        return {
            "scenario_id": scenario.id,
            "title": scenario.title,
            "task": scenario.user_task,
            "repository_context": scenario.repository_context,
            "acceptance_criteria": scenario.acceptance_criteria,
            "available_tools": scenario.available_tools,
            "risk_notes": scenario.risk_notes,
            "execution_log": [],
            "invoke_model": invoke_model,
            "model_name": model_name,
        }

    def run_scenario(
        self,
        scenario: Scenario,
        invoke_model: bool,
        model_name: str | None,
    ) -> FiveLayerState:
        graph = self.build_graph()
        initial_state = self.scenario_to_initial_state(
            scenario=scenario,
            invoke_model=invoke_model,
            model_name=model_name,
        )
        return graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": f"{self.name}:{scenario.id}"}},
        )

    def summarize_state(self, state: FiveLayerState) -> dict[str, Any]:
        return {
            "scenario_id": state["scenario_id"],
            "title": state["title"],
            "workflow_status": state.get("workflow_status"),
            "active_role": state.get("active_role"),
            "role_outputs": state.get("role_outputs", {}),
            "role_artifacts": state.get("role_artifacts", {}),
            "execution_log": state.get("execution_log", []),
            "final_report": state.get("final_report", ""),
        }

    def print_scenarios(self, scenarios: dict[str, Scenario]) -> None:
        for scenario in scenarios.values():
            print(f"{scenario.id:<24} {scenario.title}")

    def render_scenario(self, scenario: Scenario) -> None:
        print(
            json.dumps(
                {
                    "id": scenario.id,
                    "title": scenario.title,
                    "user_task": scenario.user_task,
                    "repository_context": scenario.repository_context,
                    "acceptance_criteria": scenario.acceptance_criteria,
                    "available_tools": scenario.available_tools,
                    "risk_notes": scenario.risk_notes,
                    "role_order": self.role_order,
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    def parse_args(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description=self.description)
        subparsers = parser.add_subparsers(dest="command", required=True)

        subparsers.add_parser("list", help="List scenarios.")

        render_parser = subparsers.add_parser("render", help="Render one scenario.")
        render_parser.add_argument("--case", required=True, help="Scenario id.")

        run_parser = subparsers.add_parser("run", help="Run one or all scenarios.")
        run_parser.add_argument("--case", default="all", help="Scenario id or 'all'.")
        run_parser.add_argument(
            "--invoke",
            action="store_true",
            help="Invoke a real model if API keys are configured.",
        )
        run_parser.add_argument(
            "--model",
            default=None,
            help="Optional model override.",
        )

        return parser.parse_args()

    def resolve_requested_scenarios(
        self,
        requested: str,
        scenarios: dict[str, Scenario],
    ) -> list[Scenario]:
        if requested == "all":
            return list(scenarios.values())
        if requested not in scenarios:
            raise KeyError(f"Unknown scenario id: {requested}")
        return [scenarios[requested]]

    def main(self) -> None:
        args = self.parse_args()
        scenarios = self.load_scenarios()

        if args.command == "list":
            self.print_scenarios(scenarios)
            return

        if args.command == "render":
            self.render_scenario(scenarios[args.case])
            return

        requested = self.resolve_requested_scenarios(args.case, scenarios)
        results = [
            self.summarize_state(
                self.run_scenario(
                    scenario,
                    invoke_model=args.invoke,
                    model_name=args.model,
                )
            )
            for scenario in requested
        ]
        print(json.dumps(results, indent=2, ensure_ascii=False))
