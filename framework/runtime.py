from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Literal

from . import cli as cli_helpers
from .models import FiveLayerState, RoleOutputNormalizer, RoleSimulator, Scenario
from .providers import build_model as build_provider_model
from .repo_tools import (
    append_tool_result_to_brief,
    collect_read_only_files,
    collect_repo_snapshot,
    execute_read_only_tool,
    execute_test_command,
    format_read_only_files,
    format_repo_snapshot,
    format_test_run_result,
    parse_tool_request,
    read_repo_text_file,
    resolve_repo_path,
    search_repo,
    select_files_for_context,
)
from .seeding import (
    build_seed_payload,
    format_seed_context,
    normalize_seed_role_outputs,
    resolve_start_role_index,
    validate_seed_payload,
)
from .tracing import (
    format_action_trace,
    summarize_artifact,
    summarize_tool_request,
    summarize_tool_result,
)
from .workflow import (
    behavior_route_decision,
    behavior_route_node,
    build_agent_brief,
    build_final_report,
    build_graph,
    communication_brief_node,
    coordination_commit_node,
    coordination_prepare_node,
    inference_execute_node,
    invoke_role_model,
    invoke_role_with_read_only_tools,
    normalize_role_response,
    perception_node,
    run_scenario,
    scenario_to_initial_state,
    summarize_state,
)


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

    def load_seed_payload(self, seed_file: str | None) -> dict[str, Any]:
        if not seed_file:
            return {}
        seed_path = Path(seed_file).expanduser().resolve()
        if not seed_path.exists():
            raise FileNotFoundError(f"Seed file does not exist: {seed_path}")
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("Seed file must contain a top-level JSON object.")
        return payload

    def validate_seed_payload(self, seed_payload: dict[str, Any]) -> None:
        validate_seed_payload(seed_payload)

    def build_seed_payload(
        self,
        scenario: Scenario,
        seed_payload: dict[str, Any] | None = None,
        start_role: str | None = None,
    ) -> dict[str, Any]:
        return build_seed_payload(
            scenario=scenario,
            seed_payload=seed_payload,
            start_role=start_role,
        )

    def normalize_seed_role_outputs(
        self,
        seed_role_outputs: dict[str, str],
        seed_role_artifacts: dict[str, dict[str, Any]],
    ) -> dict[str, str]:
        return normalize_seed_role_outputs(
            seed_role_outputs=seed_role_outputs,
            seed_role_artifacts=seed_role_artifacts,
            role_order=self.role_order,
        )

    def resolve_start_role_index(
        self,
        start_role: str | None,
        seeded_roles: set[str],
    ) -> int:
        return resolve_start_role_index(
            start_role=start_role,
            seeded_roles=seeded_roles,
            role_order=self.role_order,
        )

    def format_seed_context(self, seed_context: dict[str, Any]) -> str:
        return format_seed_context(seed_context)

    def resolve_repo_path(self, repo_path: str | None) -> Path | None:
        return resolve_repo_path(repo_path)

    def collect_repo_snapshot(self, repo_path: Path) -> dict[str, Any]:
        return collect_repo_snapshot(repo_path)

    def read_repo_text_file(
        self,
        repo_path: Path,
        relative_path: str,
        max_chars: int = 2400,
    ) -> str | None:
        return read_repo_text_file(repo_path, relative_path, max_chars=max_chars)

    def select_files_for_context(
        self,
        snapshot: dict[str, Any],
        state: FiveLayerState,
        max_files: int = 4,
    ) -> list[str]:
        return select_files_for_context(
            snapshot=snapshot,
            task=state.get("task", ""),
            repository_context=state.get("repository_context", ""),
            acceptance_criteria=state.get("acceptance_criteria", []),
            max_files=max_files,
        )

    def collect_read_only_files(
        self,
        repo_path: Path,
        snapshot: dict[str, Any],
        state: FiveLayerState,
        max_files: int = 4,
    ) -> list[dict[str, str]]:
        return collect_read_only_files(
            repo_path=repo_path,
            snapshot=snapshot,
            task=state.get("task", ""),
            repository_context=state.get("repository_context", ""),
            acceptance_criteria=state.get("acceptance_criteria", []),
            max_files=max_files,
        )

    def format_read_only_files(self, files: list[dict[str, str]]) -> str:
        return format_read_only_files(files)

    def summarize_artifact(self, role: str, artifact: dict[str, Any]) -> str:
        return summarize_artifact(role, artifact)

    def summarize_tool_request(self, request: dict[str, Any]) -> str:
        return summarize_tool_request(request)

    def summarize_tool_result(self, result: dict[str, Any]) -> str:
        return summarize_tool_result(result)

    def format_action_trace(self, action_trace: list[dict[str, Any]]) -> str:
        return format_action_trace(action_trace)

    def parse_tool_request(
        self,
        raw_output: str,
        available_tools: list[str],
    ) -> dict[str, Any] | None:
        return parse_tool_request(raw_output, available_tools)

    def search_repo(
        self,
        repo_path: Path,
        query: str,
        top_k: int = 8,
    ) -> dict[str, Any]:
        return search_repo(repo_path, query, top_k=top_k)

    def execute_read_only_tool(
        self,
        repo_path: Path,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        return execute_read_only_tool(repo_path, request)

    def format_tool_result(self, result: dict[str, Any]) -> str:
        from .repo_tools import format_tool_result

        return format_tool_result(result)

    def append_tool_result_to_brief(
        self,
        brief: str,
        request: dict[str, Any],
        result: dict[str, Any],
        round_index: int,
    ) -> str:
        return append_tool_result_to_brief(
            brief=brief,
            request=request,
            result=result,
            round_index=round_index,
        )

    def format_repo_snapshot(self, snapshot: dict[str, Any]) -> str:
        return format_repo_snapshot(snapshot)

    def execute_test_command(
        self,
        repo_path: Path,
        test_command: str,
        timeout_sec: int,
    ) -> dict[str, Any]:
        return execute_test_command(repo_path, test_command, timeout_sec)

    def format_test_run_result(self, result: dict[str, Any]) -> str:
        return format_test_run_result(result)

    def build_model(self, model_name: str | None):
        return build_provider_model(model_name)

    def resolve_access_mode(
        self,
        scenario: Scenario,
        repo_path: str | None,
        effective_test_command: str | None,
    ) -> Literal["synthetic", "read_only"]:
        del scenario, effective_test_command
        return "read_only" if repo_path else "synthetic"

    def resolve_available_tools(
        self,
        scenario: Scenario,
        repo_access_mode: Literal["synthetic", "read_only"],
        repo_path: str | None,
        effective_test_command: str | None,
    ) -> list[str]:
        del repo_path, effective_test_command
        tools = list(scenario.available_tools)
        if repo_access_mode == "read_only":
            for tool in ["search", "read_file"]:
                if tool not in tools:
                    tools.append(tool)
        return tools

    def extend_perception_observations(
        self,
        state: FiveLayerState,
        repo_snapshot: dict[str, Any],
        read_only_files: list[dict[str, str]],
    ) -> list[str]:
        del state, repo_snapshot, read_only_files
        return []

    def extend_shared_memory(
        self,
        state: FiveLayerState,
    ) -> dict[str, Any]:
        del state
        return {}

    def extend_brief_sections(
        self,
        role: str,
        state: FiveLayerState,
    ) -> list[str]:
        del role, state
        return []

    def postprocess_role_execution(
        self,
        role: str,
        state: FiveLayerState,
        artifact: dict[str, Any],
        normalized_output: str,
    ) -> tuple[dict[str, Any], str, dict[str, Any], list[dict[str, Any]]]:
        del role, state
        return artifact, normalized_output, {}, []

    def invoke_role_with_read_only_tools(
        self,
        role: str,
        state: FiveLayerState,
    ) -> tuple[str, str, list[dict[str, Any]], list[dict[str, Any]]]:
        return invoke_role_with_read_only_tools(self, role, state)

    def perception_node(self, state: FiveLayerState) -> FiveLayerState:
        return perception_node(self, state)

    def coordination_prepare_node(self, state: FiveLayerState) -> FiveLayerState:
        return coordination_prepare_node(self, state)

    def behavior_route_node(self, state: FiveLayerState) -> FiveLayerState:
        return behavior_route_node(self, state)

    def behavior_route_decision(self, state: FiveLayerState) -> str:
        return behavior_route_decision(state)

    def build_agent_brief(self, role: str, state: FiveLayerState) -> str:
        return build_agent_brief(self, role, state)

    def communication_brief_node(self, state: FiveLayerState) -> FiveLayerState:
        return communication_brief_node(self, state)

    def invoke_role_model(
        self,
        role: str,
        state: FiveLayerState,
        agent_brief: str | None = None,
    ) -> str:
        return invoke_role_model(self, role, state, agent_brief=agent_brief)

    def normalize_role_response(
        self,
        role: str,
        raw_output: str,
        state: FiveLayerState,
    ) -> tuple[dict[str, Any], str]:
        return normalize_role_response(self, role, raw_output, state)

    def inference_execute_node(self, state: FiveLayerState) -> FiveLayerState:
        return inference_execute_node(self, state)

    def build_final_report(
        self,
        state: FiveLayerState,
        updated_outputs: dict[str, str],
    ) -> str:
        return build_final_report(self, state, updated_outputs)

    def coordination_commit_node(self, state: FiveLayerState) -> FiveLayerState:
        return coordination_commit_node(self, state)

    def build_graph(self):
        return build_graph(self)

    def scenario_to_initial_state(
        self,
        scenario: Scenario,
        invoke_model: bool,
        model_name: str | None,
        repo_path: str | None = None,
        test_command: str | None = None,
        test_timeout_sec: int = 120,
        seed_payload: dict[str, Any] | None = None,
        start_role: str | None = None,
    ) -> FiveLayerState:
        return scenario_to_initial_state(
            self,
            scenario,
            invoke_model,
            model_name,
            repo_path=repo_path,
            test_command=test_command,
            test_timeout_sec=test_timeout_sec,
            seed_payload=seed_payload,
            start_role=start_role,
        )

    def run_scenario(
        self,
        scenario: Scenario,
        invoke_model: bool,
        model_name: str | None,
        repo_path: str | None = None,
        test_command: str | None = None,
        test_timeout_sec: int = 120,
        seed_payload: dict[str, Any] | None = None,
        start_role: str | None = None,
    ) -> FiveLayerState:
        return run_scenario(
            self,
            scenario,
            invoke_model,
            model_name,
            repo_path=repo_path,
            test_command=test_command,
            test_timeout_sec=test_timeout_sec,
            seed_payload=seed_payload,
            start_role=start_role,
        )

    def summarize_state(self, state: FiveLayerState) -> dict[str, Any]:
        return summarize_state(self, state)

    def print_scenarios(self, scenarios: dict[str, Scenario]) -> None:
        cli_helpers.print_scenarios(self, scenarios)

    def render_scenario(self, scenario: Scenario) -> None:
        cli_helpers.render_scenario(self, scenario)

    def parse_args(self):
        return cli_helpers.parse_args(self.description)

    def resolve_requested_scenarios(
        self,
        requested: str,
        scenarios: dict[str, Scenario],
    ) -> list[Scenario]:
        return cli_helpers.resolve_requested_scenarios(requested, scenarios)

    def main(self) -> None:
        cli_helpers.main(self)
