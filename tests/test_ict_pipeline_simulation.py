from ict_pipeline.demo import (
    APP,
    CATEGORY_OPTIONS,
    PRIORITY_OPTIONS,
    QUEUE_OPTIONS,
    ROLE_ORDER,
    ROLE_OUTPUT_SPECS,
    STATUS_OPTIONS,
)


def run_case(case_id: str):
    scenario = APP.load_scenarios()[case_id]
    return APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
    )


def test_ict_pipeline_scenarios_complete_in_simulation():
    scenarios = APP.load_scenarios()

    for scenario in scenarios.values():
        state = APP.run_scenario(
            scenario=scenario,
            invoke_model=False,
            model_name=None,
        )

        assert state["workflow_status"] == "completed"
        assert list(state["role_artifacts"]) == ROLE_ORDER


def test_ict_pipeline_role_artifacts_match_expected_schema():
    state = run_case("vpn_access_reset")

    for role, spec in ROLE_OUTPUT_SPECS.items():
        artifact = state["role_artifacts"][role]

        assert sorted(artifact) == sorted(
            [*spec["list_fields"], *spec["string_fields"]]
        )

        for field in spec["list_fields"]:
            assert isinstance(artifact[field], list)

        for field in spec["string_fields"]:
            assert isinstance(artifact[field], str)


def test_ict_pipeline_artifacts_use_phase1_vocabulary():
    scenarios = APP.load_scenarios()

    for scenario in scenarios.values():
        state = APP.run_scenario(
            scenario=scenario,
            invoke_model=False,
            model_name=None,
        )

        intake = state["role_artifacts"]["intake_agent"]
        triage = state["role_artifacts"]["triage_agent"]
        executor = state["role_artifacts"]["executor_agent"]
        audit = state["role_artifacts"]["audit_agent"]

        assert intake["category"] in CATEGORY_OPTIONS
        assert triage["priority"] in PRIORITY_OPTIONS
        assert triage["target_queue"] in QUEUE_OPTIONS
        assert executor["status_update"] in STATUS_OPTIONS
        assert executor["needs_human"] in {"yes", "no"}
        assert audit["final_decision"] in {"Close", "Escalate", "Needs info"}


def test_ict_pipeline_case_routing_matches_expected_phase1_profiles():
    vpn_state = run_case("vpn_access_reset")
    onboarding_state = run_case("new_hire_access_bundle")
    printer_state = run_case("printer_issue_branch_office")

    assert vpn_state["role_artifacts"]["intake_agent"]["category"] == "access_request"
    assert vpn_state["role_artifacts"]["triage_agent"]["target_queue"] == "access_management"
    assert vpn_state["role_artifacts"]["executor_agent"]["status_update"] == "waiting_human"

    assert onboarding_state["role_artifacts"]["intake_agent"]["category"] == "onboarding"
    assert onboarding_state["role_artifacts"]["triage_agent"]["target_queue"] == "onboarding"
    assert onboarding_state["role_artifacts"]["executor_agent"]["status_update"] == "queued"

    assert printer_state["role_artifacts"]["intake_agent"]["category"] == "incident"
    assert printer_state["role_artifacts"]["triage_agent"]["target_queue"] == "escalation"
    assert printer_state["role_artifacts"]["executor_agent"]["status_update"] == "escalated"


def test_ict_pipeline_remains_synthetic_even_if_repo_path_or_test_command_are_passed():
    scenario = APP.load_scenarios()["vpn_access_reset"]

    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        repo_path=".",
        test_command="python -m pytest -q",
    )

    assert state["repo_access_mode"] == "synthetic"
    assert state["available_tools"] == scenario.available_tools
