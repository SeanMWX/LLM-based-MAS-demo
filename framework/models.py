from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from typing_extensions import TypedDict


@dataclass
class Scenario:
    id: str
    title: str
    user_task: str
    repository_context: str
    acceptance_criteria: list[str]
    available_tools: list[str]
    risk_notes: list[str]
    test_command: str | None = None
    start_role: str | None = None
    seed_context: dict[str, Any] | None = None
    seed_role_outputs: dict[str, str] | None = None
    seed_role_artifacts: dict[str, dict[str, Any]] | None = None
    seed_test_run_result: dict[str, Any] | None = None
    seed_tool_events: list[dict[str, Any]] | None = None
    seed_action_trace: list[dict[str, Any]] | None = None

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
    start_role: str | None
    repo_path: str | None
    repo_access_mode: Literal["synthetic", "read_only"]
    live_repository_context: str
    live_file_context: str
    repo_snapshot: dict[str, Any]
    read_only_files: list[dict[str, Any]]
    test_command: str | None
    test_timeout_sec: int
    test_run_result: dict[str, Any]
    seed_context: dict[str, Any]
    seed_role_outputs: dict[str, str]
    seed_role_artifacts: dict[str, dict[str, Any]]
    seed_test_run_result: dict[str, Any]
    seed_tool_events: list[dict[str, Any]]
    seed_action_trace: list[dict[str, Any]]
    observations: list[str]
    shared_memory: dict[str, Any]
    next_role_index: int
    active_role: str
    agent_brief: str
    latest_output: str
    latest_artifact: dict[str, Any]
    tool_events: list[dict[str, Any]]
    action_trace: list[dict[str, Any]]
    role_outputs: dict[str, str]
    role_artifacts: dict[str, dict[str, Any]]
    execution_log: list[str]
    workflow_status: Literal["running", "completed"]
    final_report: str
    invoke_model: bool
    model_name: str | None


RoleSimulator = Callable[[str, FiveLayerState], str]
RoleOutputNormalizer = Callable[
    [str, str, FiveLayerState],
    tuple[dict[str, Any], str],
]
