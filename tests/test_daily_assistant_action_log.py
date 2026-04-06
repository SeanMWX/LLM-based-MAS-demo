from daily_assistant.demo import APP


def run_case(case_id: str):
    scenario = APP.load_scenarios()[case_id]
    return APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
    )


def test_daily_assistant_phase3b_records_action_log_queue_and_sandbox_receipts():
    state = run_case("reply_with_latest_quarterly_deck")

    assert len(state["assistant_action_log"]) == 2
    assert len(state["confirmation_queue"]) == 2
    assert len(state["assistant_receipts"]) == 2
    assert len(state["sandbox_mail_records"]) == 1
    assert len(state["sandbox_drive_records"]) == 1
    assert len(state["sandbox_adapter_receipts"]) == 2
    assert state["assistant_execution_evidence"]["queue_status"] == "pending_confirmation"
    assert state["assistant_execution_evidence"]["action_log_verdict"] == "recorded"
    assert state["sandbox_execution_summary"]["adapter_verdict"] == "awaiting_confirmation"


def test_daily_assistant_followup_case_has_action_log_and_staged_adapter_without_queue():
    state = run_case("morning_followup_triage")

    assert state["assistant_action_log"]
    assert state["confirmation_queue"] == []
    assert state["assistant_execution_evidence"]["queue_status"] == "empty"
    assert state["sandbox_mail_records"]
    assert state["sandbox_drive_records"] == []
    assert state["sandbox_execution_summary"]["adapter_verdict"] == "staged"


def test_daily_assistant_review_artifact_refs_queue_action_log_and_adapter_evidence():
    state = run_case("reply_with_latest_quarterly_deck")
    review = state["role_artifacts"]["assistant_review_agent"]

    assert review["confirmation_queue_review"]
    assert review["action_log_review"]
    assert review["adapter_evidence_review"]
    assert review["queue_status"] == "pending_confirmation"
    assert review["action_log_verdict"] == "recorded"
    assert review["adapter_verdict"] == "awaiting_confirmation"
