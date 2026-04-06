from daily_assistant.demo import APP


def run_case(case_id: str):
    scenario = APP.load_scenarios()[case_id]
    return APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
    )


def test_reply_with_latest_quarterly_deck_stages_mail_and_drive_adapters():
    state = run_case("reply_with_latest_quarterly_deck")

    assert [record["adapter_id"] for record in state["sandbox_mail_records"]] == [
        "mail_draft_adapter"
    ]
    assert [record["adapter_id"] for record in state["sandbox_drive_records"]] == [
        "drive_reference_adapter"
    ]
    assert all(
        record["status"] == "awaiting_confirmation"
        for record in [
            *state["sandbox_mail_records"],
            *state["sandbox_drive_records"],
        ]
    )
    assert state["sandbox_execution_summary"]["receipt_count"] == 2


def test_followup_case_stages_mail_adapter_only():
    state = run_case("morning_followup_triage")

    assert state["sandbox_mail_records"]
    assert state["sandbox_drive_records"] == []
    assert state["sandbox_execution_summary"]["adapter_verdict"] == "staged"


def test_receipt_archive_case_stages_mail_and_drive_without_confirmation_queue():
    state = run_case("expense_receipt_archive")

    assert state["confirmation_queue"] == []
    assert state["sandbox_mail_records"]
    assert state["sandbox_drive_records"]
    assert state["sandbox_execution_summary"]["adapter_verdict"] == "staged"
