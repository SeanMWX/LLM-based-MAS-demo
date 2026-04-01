import json
from pathlib import Path

import pytest

from coding_agent.demo import APP, ROLE_ORDER

REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_FILE = REPO_ROOT / "coding_agent" / "seeds" / "reviewer_hypothesis.json"


def test_coordination_prepare_initializes_seeded_roles_and_start_role():
    scenario = APP.load_scenarios()["simple_feature_python"]
    seed_payload = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        seed_payload=seed_payload,
    )
    state.update(APP.perception_node(state))

    prepared = APP.coordination_prepare_node(state)

    assert list(prepared["role_outputs"]) == ["planner", "coder", "tester"]
    assert list(prepared["role_artifacts"]) == ["planner", "coder", "tester"]
    assert prepared["next_role_index"] == ROLE_ORDER.index("reviewer")
    assert prepared["test_run_result"]["passed"] is True
    assert any(
        event["event"] == "seed_loaded" for event in prepared["action_trace"]
    )


def test_reviewer_brief_includes_seeded_context_and_seeded_test_result():
    scenario = APP.load_scenarios()["simple_feature_python"]
    seed_payload = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        seed_payload=seed_payload,
    )
    state.update(APP.perception_node(state))
    state.update(APP.coordination_prepare_node(state))
    state["active_role"] = "reviewer"

    updated = APP.communication_brief_node(state)

    assert "Seeded evaluation context:" in updated["agent_brief"]
    assert "Candidate Diff:" in updated["agent_brief"]
    assert "Latest test execution:" in updated["agent_brief"]
    assert "Needs verification" in updated["agent_brief"]


def test_run_scenario_with_seed_payload_starts_from_reviewer_and_completes():
    scenario = APP.load_scenarios()["simple_feature_python"]
    seed_payload = json.loads(SEED_FILE.read_text(encoding="utf-8"))

    state = APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        seed_payload=seed_payload,
    )

    assert state["workflow_status"] == "completed"
    assert list(state["role_artifacts"]) == ROLE_ORDER
    assert state["role_artifacts"]["tester"]["verdict"] == "Needs verification"
    assert state["role_artifacts"]["reviewer"]["decision"] == "Approve"
    assert any(event["event"] == "seed_loaded" for event in state["action_trace"])
    assert "Seed Loaded" in APP.summarize_state(state)["action_trace_text"]


def test_start_role_override_takes_precedence_over_seed_file():
    scenario = APP.load_scenarios()["simple_feature_python"]
    seed_payload = json.loads(SEED_FILE.read_text(encoding="utf-8"))

    state = APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        seed_payload=seed_payload,
        start_role="tester",
    )

    selected_roles = [
        event["role"]
        for event in state["action_trace"]
        if event["event"] == "role_selected"
    ]

    assert selected_roles[0] == "tester"
    assert state["start_role"] == "tester"


def test_all_roles_seeded_can_complete_without_executing_new_role():
    scenario = APP.load_scenarios()["simple_feature_python"]
    seed_payload = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    seed_payload["start_role"] = None
    seed_payload["seed_role_artifacts"]["reviewer"] = {
        "review_summary": ["Pre-seeded reviewer conclusion."],
        "risks": ["No live review executed."],
        "decision": "Needs verification",
    }

    state = APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        seed_payload=seed_payload,
    )

    assert state["workflow_status"] == "completed"
    assert state["active_role"] == ""
    assert list(state["role_artifacts"]) == ROLE_ORDER
    assert [
        event["event"] for event in state["action_trace"] if event["event"] == "role_completed"
    ] == []
    assert state["role_artifacts"]["reviewer"]["decision"] == "Needs verification"


def test_load_seed_payload_rejects_non_object_json(tmp_path):
    seed_file = tmp_path / "bad_seed.json"
    seed_file.write_text('["not", "an", "object"]', encoding="utf-8")

    with pytest.raises(TypeError):
        APP.load_seed_payload(str(seed_file))


def test_build_seed_payload_rejects_invalid_field_types():
    scenario = APP.load_scenarios()["simple_feature_python"]

    with pytest.raises(TypeError):
        APP.build_seed_payload(
            scenario=scenario,
            seed_payload={"seed_role_artifacts": ["not", "a", "dict"]},
        )
