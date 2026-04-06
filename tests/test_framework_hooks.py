from pathlib import Path

from framework import FiveLayerDemo
from framework.models import Scenario


def simulate_role_output(_role: str, _state):
    return "{}"


APP = FiveLayerDemo(
    name="dummy_demo",
    description="Dummy demo for framework hook defaults.",
    cases_path=Path(__file__),
    role_order=["agent_a"],
    role_system_prompts={"agent_a": "Return JSON."},
    simulate_role_output=simulate_role_output,
)


def test_default_resolve_access_mode_is_synthetic_without_repo_path():
    scenario = Scenario(
        id="dummy",
        title="Dummy",
        user_task="Do work",
        repository_context="Synthetic context",
        acceptance_criteria=["One"],
        available_tools=["read_ticket"],
        risk_notes=["Keep it small"],
        test_command="echo should_not_enable_read_only",
    )

    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
    )

    assert state["repo_access_mode"] == "synthetic"
    assert state["available_tools"] == ["read_ticket"]
    assert state["test_command"] == "echo should_not_enable_read_only"


def test_default_resolve_available_tools_only_adds_read_only_tools_when_repo_path_exists():
    scenario = Scenario(
        id="dummy",
        title="Dummy",
        user_task="Do work",
        repository_context="Synthetic context",
        acceptance_criteria=["One"],
        available_tools=["read_ticket"],
        risk_notes=["Keep it small"],
    )

    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        repo_path=".",
    )

    assert state["repo_access_mode"] == "read_only"
    assert state["available_tools"] == ["read_ticket", "search", "read_file"]


def test_default_framework_hooks_are_neutral():
    state = {
        "task": "Do work",
        "repository_context": "Context",
        "acceptance_criteria": ["One"],
    }

    assert APP.extend_perception_observations(state, {}, []) == []
    assert APP.extend_shared_memory(state) == {}
    assert APP.extend_brief_sections("agent_a", state) == []
    artifact, normalized, updates, trace = APP.postprocess_role_execution(
        role="agent_a",
        state=state,
        artifact={"raw_output": "{}"},
        normalized_output="{}",
    )
    assert artifact == {"raw_output": "{}"}
    assert normalized == "{}"
    assert updates == {}
    assert trace == []
