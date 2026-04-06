from ict_pipeline.demo import (
    APPROVAL_ROUTE_OPTIONS,
    APPROVAL_WAIT_STATE_OPTIONS,
    APP,
    AUDIT_VERDICT_OPTIONS,
    CATEGORY_OPTIONS,
    CLOSURE_ELIGIBILITY_OPTIONS,
    DB_STATE_CONSISTENCY_OPTIONS,
    EXECUTION_VERDICT_OPTIONS,
    FINAL_DECISION_OPTIONS,
    KB_CONFIDENCE_OPTIONS,
    PRIORITY_OPTIONS,
    QUEUE_OPTIONS,
    RECEIPT_CONSISTENCY_OPTIONS,
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


def test_ict_pipeline_artifacts_use_phase3b_vocabulary():
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
        assert triage["kb_confidence"] in KB_CONFIDENCE_OPTIONS
        assert triage["approval_required"] in {"yes", "no"}
        assert triage["approval_route"] in APPROVAL_ROUTE_OPTIONS
        assert executor["status_update"] in STATUS_OPTIONS
        assert executor["needs_human"] in {"yes", "no"}
        assert executor["execution_verdict"] in EXECUTION_VERDICT_OPTIONS
        assert executor["approval_wait_state"] in APPROVAL_WAIT_STATE_OPTIONS
        assert audit["final_decision"] in FINAL_DECISION_OPTIONS
        assert audit["receipt_consistency"] in RECEIPT_CONSISTENCY_OPTIONS
        assert audit["audit_verdict"] in AUDIT_VERDICT_OPTIONS
        assert audit["db_state_consistency"] in DB_STATE_CONSISTENCY_OPTIONS
        assert audit["closure_eligibility"] in CLOSURE_ELIGIBILITY_OPTIONS


def test_ict_pipeline_case_routing_matches_expected_phase3b_profiles():
    vpn_state = run_case("vpn_access_reset")
    onboarding_state = run_case("new_hire_access_bundle")
    printer_state = run_case("printer_issue_branch_office")

    assert vpn_state["role_artifacts"]["intake_agent"]["category"] == "access_request"
    assert (
        vpn_state["role_artifacts"]["triage_agent"]["target_queue"]
        == "access_management"
    )
    assert (
        vpn_state["role_artifacts"]["executor_agent"]["status_update"]
        == "waiting_human"
    )
    assert (
        vpn_state["role_artifacts"]["executor_agent"]["execution_verdict"]
        == "pending_human"
    )
    assert (
        vpn_state["role_artifacts"]["triage_agent"]["approval_required"]
        == "yes"
    )
    assert (
        vpn_state["role_artifacts"]["triage_agent"]["approval_route"]
        == "identity_verification"
    )
    assert (
        vpn_state["role_artifacts"]["executor_agent"]["approval_wait_state"]
        == "pending"
    )
    assert vpn_state["role_artifacts"]["triage_agent"]["kb_matches"] == [
        "kb_vpn_locked_account_reset: Locked VPN account reset after failed sign-in attempts"
    ]

    assert onboarding_state["role_artifacts"]["intake_agent"]["category"] == "onboarding"
    assert (
        onboarding_state["role_artifacts"]["triage_agent"]["target_queue"]
        == "onboarding"
    )
    assert (
        onboarding_state["role_artifacts"]["executor_agent"]["status_update"]
        == "waiting_human"
    )
    assert (
        onboarding_state["role_artifacts"]["executor_agent"]["execution_verdict"]
        == "pending_human"
    )
    assert (
        onboarding_state["role_artifacts"]["triage_agent"]["approval_required"]
        == "yes"
    )
    assert (
        onboarding_state["role_artifacts"]["triage_agent"]["approval_route"]
        == "finance_manager_approval"
    )
    assert (
        onboarding_state["role_artifacts"]["executor_agent"]["approval_wait_state"]
        == "pending"
    )
    assert onboarding_state["role_artifacts"]["triage_agent"]["kb_matches"] == [
        "kb_new_hire_standard_access_bundle: Standard onboarding bundle for a new hire",
        "kb_finance_drive_access_requires_approval: Finance shared-drive access requires explicit approval",
    ]

    assert printer_state["role_artifacts"]["intake_agent"]["category"] == "incident"
    assert (
        printer_state["role_artifacts"]["triage_agent"]["target_queue"]
        == "local_support"
    )
    assert (
        printer_state["role_artifacts"]["executor_agent"]["status_update"]
        == "escalated"
    )
    assert (
        printer_state["role_artifacts"]["executor_agent"]["execution_verdict"]
        == "escalated"
    )
    assert (
        printer_state["role_artifacts"]["triage_agent"]["approval_required"]
        == "no"
    )
    assert (
        printer_state["role_artifacts"]["triage_agent"]["approval_route"]
        == "not_required"
    )
    assert (
        printer_state["role_artifacts"]["executor_agent"]["approval_wait_state"]
        == "not_required"
    )
    assert printer_state["role_artifacts"]["triage_agent"]["kb_matches"] == [
        "kb_branch_printer_team_outage: Branch-office shared printer outage affecting multiple users"
    ]


def test_ict_pipeline_shared_memory_contains_kb_action_log_and_db_approval_context():
    state = run_case("new_hire_access_bundle")

    assert state["shared_memory"]["kb_phase"] == "ticket_plus_kb"
    assert (
        state["shared_memory"]["pipeline_phase"]
        == "ticket_plus_kb_action_log_db_approval"
    )
    assert state["shared_memory"]["kb_article_ids"] == [
        "kb_new_hire_standard_access_bundle",
        "kb_finance_drive_access_requires_approval",
    ]
    assert len(state["shared_memory"]["kb_search_results"]) >= 2
    assert len(state["shared_memory"]["action_log"]) == 3
    assert len(state["shared_memory"]["executor_receipts"]) == 3
    assert state["shared_memory"]["execution_evidence"]["receipt_consistency"] == "consistent"
    assert state["shared_memory"]["ticket_db_record"]["approval_route"] == "finance_manager_approval"
    assert state["shared_memory"]["approval_state"]["approval_wait_state"] == "pending"
    assert len(state["shared_memory"]["approval_history"]) == 2


def test_ict_pipeline_brief_includes_kb_action_log_and_db_sections_for_downstream_roles():
    scenario = APP.load_scenarios()["vpn_access_reset"]
    state = APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
    )

    triage_brief = APP.build_agent_brief("triage_agent", state)
    executor_brief = APP.build_agent_brief("executor_agent", state)
    audit_brief = APP.build_agent_brief("audit_agent", state)

    assert "Knowledge base matches:" in triage_brief
    assert "kb_vpn_locked_account_reset" in triage_brief
    assert "Knowledge base recommended actions:" in executor_brief
    assert "verify caller identity with an approved factor" in executor_brief
    assert "Action-log requirements:" in executor_brief
    assert "Knowledge base evidence notes:" in audit_brief
    assert "Recorded action log:" in audit_brief
    assert "Executor receipts:" in audit_brief
    assert "Execution evidence summary:" in audit_brief
    assert "Ticket DB record:" in audit_brief
    assert "Approval history:" in audit_brief
    assert "Ticket DB update requirements:" in executor_brief


def test_ict_pipeline_executor_outputs_structured_action_log_and_receipts():
    state = run_case("vpn_access_reset")
    executor = state["role_artifacts"]["executor_agent"]

    assert executor["action_log_entries"]
    assert executor["receipt_ids"]
    assert len(executor["action_log_entries"]) == len(executor["receipt_ids"])
    assert executor["action_log_entries"][0].startswith("step=1 | action=")
    assert executor["receipt_ids"][0].startswith("rcpt_")
    assert executor["db_updates"]
    assert executor["execution_blockers"]


def test_ict_pipeline_audit_reviews_recorded_execution_evidence_and_db_state():
    state = run_case("printer_issue_branch_office")
    audit = state["role_artifacts"]["audit_agent"]

    assert audit["action_log_review"]
    assert audit["receipt_consistency"] == "consistent"
    assert audit["audit_verdict"] == "followup_required"
    assert audit["db_state_consistency"] == "consistent"
    assert audit["closure_eligibility"] == "blocked_by_state"
    assert audit["approval_chain_review"]


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
