from ict_pipeline.demo import (
    build_approval_chain_review,
    build_approval_history,
    build_ticket_db_record,
    derive_closure_eligibility,
    derive_db_state_consistency,
    normalize_approval_route,
    normalize_approval_wait_state,
)


def test_normalize_approval_route_and_wait_state():
    assert normalize_approval_route("Identity Verification") == "identity_verification"
    assert normalize_approval_route("Finance manager sign-off") == "finance_manager_approval"
    assert normalize_approval_wait_state("pending approval") == "pending"
    assert normalize_approval_wait_state("not required") == "not_required"


def test_build_approval_history_for_required_and_non_required_paths():
    required_history = build_approval_history(
        scenario_id="new_hire_access_bundle",
        approval_route="finance_manager_approval",
        approval_wait_state="pending",
        approval_required="yes",
    )
    no_approval_history = build_approval_history(
        scenario_id="printer_issue_branch_office",
        approval_route="not_required",
        approval_wait_state="not_required",
        approval_required="no",
    )

    assert len(required_history) == 2
    assert required_history[-1]["state"] == "pending"
    assert no_approval_history[0]["route"] == "not_required"


def test_build_ticket_db_record_and_consistency_helpers():
    profile = {
        "category": "onboarding",
        "priority": "medium",
        "target_queue": "onboarding",
        "status_update": "waiting_human",
        "approval_required": "yes",
        "approval_route": "finance_manager_approval",
        "approval_wait_state": "pending",
        "receipt_ids": ["rcpt_bundle"],
    }
    ticket_db_record = build_ticket_db_record("new_hire_access_bundle", profile)
    approval_history = build_approval_history(
        scenario_id="new_hire_access_bundle",
        approval_route="finance_manager_approval",
        approval_wait_state="pending",
        approval_required="yes",
    )

    assert ticket_db_record["ticket_id"].startswith("TCK-")
    assert (
        derive_db_state_consistency(
            ticket_db_record=ticket_db_record,
            approval_history=approval_history,
            approval_wait_state="pending",
        )
        == "consistent"
    )
    assert (
        derive_closure_eligibility(
            status_update="waiting_human",
            approval_required="yes",
            approval_wait_state="pending",
            final_decision="Escalate",
        )
        == "blocked_by_approval"
    )


def test_build_approval_chain_review_for_pending_and_not_required():
    pending_review = build_approval_chain_review(
        approval_history=[
            {
                "step": "1",
                "actor": "triage_agent",
                "route": "identity_verification",
                "state": "requested",
                "note": "identity verification was opened during triage",
            }
        ],
        approval_required="yes",
        approval_wait_state="pending",
    )
    no_approval_review = build_approval_chain_review(
        approval_history=[],
        approval_required="no",
        approval_wait_state="not_required",
    )

    assert pending_review[-1] == "Closure must stay blocked until approval is recorded."
    assert no_approval_review[0] == "Approval path is not required for this ticket."
