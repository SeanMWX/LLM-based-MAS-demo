from ict_pipeline.demo import (
    build_execution_evidence,
    build_executor_receipts,
    canonicalize_action_log_entry,
    derive_audit_verdict,
    parse_action_log_entry,
)


def test_canonicalize_action_log_entry_normalizes_tokens():
    entry = canonicalize_action_log_entry(
        "step=1 | action=Request Finance Drive Approval | tool=Record Action Log | receipt=Finance Receipt 1 | outcome=Approval Requested",
        step_index=1,
    )

    assert entry == (
        "step=1 | action=request_finance_drive_approval | tool=record_action_log | "
        "receipt=finance_receipt_1 | outcome=approval_requested"
    )


def test_build_execution_evidence_marks_missing_receipts():
    action_log_entries = [
        canonicalize_action_log_entry(
            "step=1 | action=queue_standard_access_bundle | tool=record_action_log | receipt=rcpt_bundle | outcome=queued_onboarding",
            step_index=1,
        )
    ]

    evidence = build_execution_evidence(
        action_log_entries=action_log_entries,
        receipt_ids=["rcpt_bundle"],
        expected_receipts=["rcpt_bundle", "rcpt_approval"],
    )

    assert evidence["receipt_consistency"] == "missing"
    assert evidence["missing_receipts"] == ["rcpt_approval"]


def test_build_executor_receipts_marks_unlogged_receipts():
    receipts = build_executor_receipts(
        action_log_entries=[
            canonicalize_action_log_entry(
                "step=1 | action=notify_local_support | tool=record_action_log | receipt=rcpt_local_support | outcome=queued_local_support",
                step_index=1,
            )
        ],
        receipt_ids=["rcpt_local_support", "rcpt_missing"],
    )

    assert receipts["rcpt_local_support"]["recorded"] is True
    assert receipts["rcpt_missing"]["recorded"] is False


def test_parse_action_log_entry_and_audit_verdict_helpers():
    parsed = parse_action_log_entry(
        "step=2 | action=hold_privileged_access | tool=record_action_log | receipt=rcpt_hold | outcome=waiting_for_approval"
    )

    assert parsed["step"] == "2"
    assert parsed["action"] == "hold_privileged_access"
    assert derive_audit_verdict("consistent", "Escalate") == "followup_required"
    assert derive_audit_verdict("missing", "Escalate") == "reject"
