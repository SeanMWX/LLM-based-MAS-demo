from ict_pipeline.demo import (
    APPROVAL_ROUTE_OPTIONS,
    APPROVAL_WAIT_STATE_OPTIONS,
    AUDIT_VERDICT_OPTIONS,
    CATEGORY_OPTIONS,
    CLOSURE_ELIGIBILITY_OPTIONS,
    DB_STATE_CONSISTENCY_OPTIONS,
    EXECUTION_VERDICT_OPTIONS,
    KB_CONFIDENCE_OPTIONS,
    PRIORITY_OPTIONS,
    QUEUE_OPTIONS,
    RECEIPT_CONSISTENCY_OPTIONS,
    STATUS_OPTIONS,
    normalize_role_output,
)


def test_intake_agent_normalizes_category_from_sectioned_text():
    raw = """
    Ticket summary:
    Remote user cannot access VPN.

    Extracted fields:
    requester = sales manager
    service = vpn

    Missing fields:
    identity verification

    Category: Access Request
    """

    artifact, _normalized = normalize_role_output("intake_agent", raw, {})

    assert artifact["category"] == "access_request"
    assert artifact["category"] in CATEGORY_OPTIONS


def test_triage_agent_normalizes_priority_queue_kb_confidence_and_approval_route():
    raw = """
    Routing rationale:
    Business impact is immediate.

    Required checks:
    Confirm identity first.

    KB matches:
    kb_vpn_locked_account_reset

    Approval reason:
    Manager confirmation is required.

    Priority: Urgent
    Target queue: VPN approvals
    KB confidence: strong match
    Approval required: TRUE
    Approval route: Identity Verification
    """

    artifact, _normalized = normalize_role_output("triage_agent", raw, {})

    assert artifact["priority"] == "high"
    assert artifact["target_queue"] == "access_management"
    assert artifact["kb_confidence"] == "high"
    assert artifact["approval_required"] == "yes"
    assert artifact["approval_route"] == "identity_verification"
    assert artifact["priority"] in PRIORITY_OPTIONS
    assert artifact["target_queue"] in QUEUE_OPTIONS
    assert artifact["kb_confidence"] in KB_CONFIDENCE_OPTIONS
    assert artifact["approval_route"] in APPROVAL_ROUTE_OPTIONS


def test_executor_agent_normalizes_status_action_log_yes_no_and_approval_wait_state():
    raw = """
    Actions taken:
    Queue manual review.

    Execution notes:
    Approval is required.

    KB actions used:
    hold privileged access until the approval record is attached

    Action log entries:
    step=1 | action=request finance drive approval | tool=record action log | receipt=Finance Approval 1 | outcome=approval requested

    Receipt IDs:
    Finance Approval 1

    DB updates:
    set approval route to finance manager approval

    Execution blockers:
    waiting for manager approval

    Status update: waiting for human approval
    Needs human: TRUE
    Execution verdict: pending on human approval
    Approval wait state: pending approval
    """

    artifact, _normalized = normalize_role_output("executor_agent", raw, {})

    assert artifact["status_update"] == "waiting_human"
    assert artifact["needs_human"] == "yes"
    assert artifact["execution_verdict"] == "pending_human"
    assert artifact["approval_wait_state"] == "pending"
    assert artifact["action_log_entries"] == [
        "step=1 | action=request_finance_drive_approval | tool=record_action_log | receipt=finance_approval_1 | outcome=approval_requested"
    ]
    assert artifact["receipt_ids"] == ["finance_approval_1"]
    assert artifact["status_update"] in STATUS_OPTIONS
    assert artifact["execution_verdict"] in EXECUTION_VERDICT_OPTIONS
    assert artifact["approval_wait_state"] in APPROVAL_WAIT_STATE_OPTIONS


def test_audit_agent_normalizes_final_decision_evidence_db_and_closure_fields():
    raw = """
    Completeness check:
    Ticket has enough routing detail.

    Risks:
    Access reset still needs a person.

    KB evidence review:
    kb_vpn_locked_account_reset requires identity verification

    Action log review:
    receipt mismatch detected

    Approval chain review:
    approval is still pending

    Final decision: please escalate
    Receipt consistency: receipts missing
    Audit verdict: reject this evidence
    DB state consistency: missing update
    Closure eligibility: blocked by approval
    """

    artifact, _normalized = normalize_role_output("audit_agent", raw, {})

    assert artifact["final_decision"] == "Escalate"
    assert artifact["receipt_consistency"] == "missing"
    assert artifact["audit_verdict"] == "reject"
    assert artifact["db_state_consistency"] == "missing_update"
    assert artifact["closure_eligibility"] == "blocked_by_approval"
    assert artifact["receipt_consistency"] in RECEIPT_CONSISTENCY_OPTIONS
    assert artifact["audit_verdict"] in AUDIT_VERDICT_OPTIONS
    assert artifact["db_state_consistency"] in DB_STATE_CONSISTENCY_OPTIONS
    assert artifact["closure_eligibility"] in CLOSURE_ELIGIBILITY_OPTIONS
