from coding_agent.demo import APP, ROLE_ORDER, ROLE_OUTPUT_SPECS


def run_case(case_id: str):
    scenario = APP.load_scenarios()[case_id]
    return APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
    )


def test_simulation_mode_does_not_build_model(monkeypatch):
    def fail_build_model(_model_name):
        raise AssertionError("build_model should not be called in simulation mode")

    monkeypatch.setattr(APP, "build_model", fail_build_model)

    state = run_case("simple_feature_python")

    assert state["workflow_status"] == "completed"


def test_simple_feature_case_completes_with_all_roles():
    state = run_case("simple_feature_python")

    assert state["workflow_status"] == "completed"
    assert state["active_role"] == ""
    assert list(state["role_outputs"]) == ROLE_ORDER
    assert list(state["role_artifacts"]) == ROLE_ORDER
    assert state["shared_memory"]["role_outputs"] == state["role_outputs"]
    assert state["shared_memory"]["role_artifacts"] == state["role_artifacts"]
    assert "Scenario: Add a small pure helper function" in state["final_report"]
    assert state["action_trace"][0]["event"] == "workflow_started"
    assert state["action_trace"][-1]["event"] == "workflow_completed"
    selected_roles = [
        event["role"]
        for event in state["action_trace"]
        if event["event"] == "role_selected"
    ]
    completed_roles = [
        event["role"]
        for event in state["action_trace"]
        if event["event"] == "role_completed"
    ]
    assert selected_roles == ROLE_ORDER
    assert completed_roles == ROLE_ORDER


def test_all_scenarios_complete_in_simulation():
    scenarios = APP.load_scenarios()

    for scenario in scenarios.values():
        state = APP.run_scenario(
            scenario=scenario,
            invoke_model=False,
            model_name=None,
        )

        assert state["workflow_status"] == "completed"
        assert list(state["role_artifacts"]) == ROLE_ORDER


def test_role_artifacts_match_expected_schema():
    state = run_case("simple_feature_python")

    for role, spec in ROLE_OUTPUT_SPECS.items():
        artifact = state["role_artifacts"][role]

        assert sorted(artifact) == sorted(
            [*spec["list_fields"], *spec["string_fields"]]
        )

        for field in spec["list_fields"]:
            assert isinstance(artifact[field], list)

        for field in spec["string_fields"]:
            assert isinstance(artifact[field], str)
