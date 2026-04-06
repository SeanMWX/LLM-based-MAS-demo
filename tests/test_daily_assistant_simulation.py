from daily_assistant.demo import (
    ADAPTER_PHASE,
    ADAPTER_VERDICT_OPTIONS,
    APP,
    ASSISTANT_PHASE,
    ACTION_LOG_VERDICT_OPTIONS,
    POLICY_PHASE,
    QUEUE_PHASE,
    QUEUE_STATUS_OPTIONS,
    DRIVE_STATUS_OPTIONS,
    EMAIL_STATUS_OPTIONS,
    FINAL_DECISION_OPTIONS,
    INTENT_TYPE_OPTIONS,
    ROLE_ORDER,
    ROLE_OUTPUT_SPECS,
    SAFE_ACTION_MODE_OPTIONS,
)


def run_case(case_id: str):
    scenario = APP.load_scenarios()[case_id]
    return APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
    )


def test_daily_assistant_scenarios_complete_in_simulation():
    scenarios = APP.load_scenarios()

    for scenario in scenarios.values():
        state = APP.run_scenario(
            scenario=scenario,
            invoke_model=False,
            model_name=None,
        )

        assert state["workflow_status"] == "completed"
        assert list(state["role_artifacts"]) == ROLE_ORDER


def test_daily_assistant_role_artifacts_match_expected_schema():
    state = run_case("reply_with_latest_quarterly_deck")

    for role, spec in ROLE_OUTPUT_SPECS.items():
        artifact = state["role_artifacts"][role]

        assert sorted(artifact) == sorted(
            [*spec["list_fields"], *spec["string_fields"]]
        )

        for field in spec["list_fields"]:
            assert isinstance(artifact[field], list)

        for field in spec["string_fields"]:
            assert isinstance(artifact[field], str)


def test_daily_assistant_artifacts_use_phase3b_vocabulary():
    for scenario in APP.load_scenarios().values():
        state = APP.run_scenario(
            scenario=scenario,
            invoke_model=False,
            model_name=None,
        )

        intake = state["role_artifacts"]["intake_router_agent"]
        email = state["role_artifacts"]["email_manager_agent"]
        drive = state["role_artifacts"]["drive_manager_agent"]
        review = state["role_artifacts"]["assistant_review_agent"]

        assert intake["intent_type"] in INTENT_TYPE_OPTIONS
        assert intake["approval_required"] in {"yes", "no"}
        assert email["email_status"] in EMAIL_STATUS_OPTIONS
        assert drive["drive_status"] in DRIVE_STATUS_OPTIONS
        assert review["safe_action_mode"] in SAFE_ACTION_MODE_OPTIONS
        assert review["queue_status"] in QUEUE_STATUS_OPTIONS
        assert review["action_log_verdict"] in ACTION_LOG_VERDICT_OPTIONS
        assert review["adapter_verdict"] in ADAPTER_VERDICT_OPTIONS
        assert review["needs_user_confirmation"] in {"yes", "no"}
        assert review["final_decision"] in FINAL_DECISION_OPTIONS


def test_daily_assistant_case_profiles_match_expected_outputs():
    deck_state = run_case("reply_with_latest_quarterly_deck")
    followup_state = run_case("morning_followup_triage")
    receipt_state = run_case("expense_receipt_archive")

    assert (
        deck_state["role_artifacts"]["intake_router_agent"]["intent_type"]
        == "email_and_drive"
    )
    assert (
        deck_state["role_artifacts"]["assistant_review_agent"]["final_decision"]
        == "Needs confirmation"
    )
    assert (
        deck_state["role_artifacts"]["assistant_review_agent"]["queue_status"]
        == "pending_confirmation"
    )
    assert (
        deck_state["role_artifacts"]["assistant_review_agent"]["action_log_verdict"]
        == "recorded"
    )
    assert (
        deck_state["role_artifacts"]["assistant_review_agent"]["adapter_verdict"]
        == "awaiting_confirmation"
    )
    assert (
        deck_state["role_artifacts"]["assistant_review_agent"]["safe_action_mode"]
        == "confirm_required"
    )
    assert (
        deck_state["role_artifacts"]["assistant_review_agent"][
            "needs_user_confirmation"
        ]
        == "yes"
    )
    assert "Q2 Sales Deck v5" in deck_state["role_artifacts"]["drive_manager_agent"][
        "file_matches"
    ][0]

    assert (
        followup_state["role_artifacts"]["intake_router_agent"]["intent_type"]
        == "email_only"
    )
    assert (
        followup_state["role_artifacts"]["drive_manager_agent"]["drive_status"]
        == "not_needed"
    )
    assert (
        followup_state["role_artifacts"]["assistant_review_agent"]["final_decision"]
        == "Return draft"
    )
    assert (
        followup_state["role_artifacts"]["assistant_review_agent"]["queue_status"]
        == "empty"
    )
    assert (
        followup_state["role_artifacts"]["assistant_review_agent"]["adapter_verdict"]
        == "staged"
    )
    assert (
        followup_state["role_artifacts"]["assistant_review_agent"][
            "safe_action_mode"
        ]
        == "draft_only"
    )
    assert len(
        followup_state["role_artifacts"]["email_manager_agent"]["email_findings"]
    ) == 2
    assert followup_state["role_artifacts"]["drive_manager_agent"]["file_matches"] == []

    assert (
        receipt_state["role_artifacts"]["assistant_review_agent"]["final_decision"]
        == "Return draft"
    )
    assert "Suggest archiving into" in receipt_state["role_artifacts"][
        "drive_manager_agent"
    ]["suggested_file_actions"][0]


def test_daily_assistant_shared_memory_contains_phase_and_matches():
    state = run_case("reply_with_latest_quarterly_deck")

    assert state["shared_memory"]["assistant_phase"] == ASSISTANT_PHASE
    assert state["shared_memory"]["policy_phase"] == POLICY_PHASE
    assert state["shared_memory"]["adapter_phase"] == ADAPTER_PHASE
    assert state["shared_memory"]["assistant_action_log"]
    assert state["shared_memory"]["confirmation_queue"]
    assert state["shared_memory"]["assistant_receipts"]
    assert state["shared_memory"]["sandbox_mail_records"]
    assert state["shared_memory"]["sandbox_drive_records"]
    assert state["shared_memory"]["sandbox_adapter_receipts"]
    assert state["shared_memory"]["email_matches"]
    assert state["shared_memory"]["drive_matches"]
    assert state["shared_memory"]["policy_matches"]


def test_daily_assistant_summary_includes_queue_phase_and_execution_evidence():
    state = run_case("reply_with_latest_quarterly_deck")
    summary = APP.summarize_state(state)

    assert summary["queue_phase"] == QUEUE_PHASE
    assert summary["adapter_phase"] == ADAPTER_PHASE
    assert summary["assistant_action_log"]
    assert summary["confirmation_queue"]
    assert summary["assistant_receipts"]
    assert summary["assistant_execution_evidence"]["queue_status"] == "pending_confirmation"
    assert summary["sandbox_mail_records"]
    assert summary["sandbox_drive_records"]
    assert summary["sandbox_adapter_receipts"]
    assert summary["sandbox_execution_summary"]["adapter_verdict"] == "awaiting_confirmation"


def test_daily_assistant_brief_includes_email_drive_policy_and_safety_sections():
    state = run_case("reply_with_latest_quarterly_deck")

    email_brief = APP.build_agent_brief("email_manager_agent", state)
    drive_brief = APP.build_agent_brief("drive_manager_agent", state)
    review_brief = APP.build_agent_brief("assistant_review_agent", state)

    assert "Relevant policy rules:" in email_brief
    assert "Mail sandbox adapter:" in email_brief
    assert "mail_draft_adapter" in email_brief
    assert "policy_external_email_confirmation" in email_brief
    assert "Relevant email threads:" in email_brief
    assert "email_q2_deck_request" in email_brief
    assert "Relevant policy rules:" in drive_brief
    assert "Drive sandbox adapter:" in drive_brief
    assert "drive_reference_adapter" in drive_brief
    assert "policy_external_file_sharing_confirmation" in drive_brief
    assert "Relevant drive items:" in drive_brief
    assert "drive_q2_sales_deck_v5" in drive_brief
    assert "Recorded assistant action log:" in review_brief
    assert "Pending confirmation queue:" in review_brief
    assert "Sandbox adapter receipts:" in review_brief
    assert "Phase-3B safety rule:" in review_brief
    assert "Do not send email" in review_brief
    assert "Use policy evidence" in review_brief
    assert "sandbox adapters only" in review_brief


def test_daily_assistant_remains_synthetic_with_repo_path_or_test_command():
    scenario = APP.load_scenarios()["reply_with_latest_quarterly_deck"]

    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        repo_path=".",
        test_command="python -m pytest -q",
    )

    assert state["repo_access_mode"] == "synthetic"
    assert state["available_tools"] == scenario.available_tools
