import json

from daily_assistant.demo import normalize_role_output


def test_intake_router_normalizes_json_fields():
    raw_output = json.dumps(
        {
            "request_summary": ["Handle email and file lookup."],
            "routing_plan": ["Ask email manager", "Ask drive manager"],
            "constraints": ["Stay draft-only"],
            "intent_type": "Email and Drive",
            "approval_required": "true",
        }
    )

    artifact, normalized = normalize_role_output("intake_router_agent", raw_output, {})

    assert artifact["intent_type"] == "email_and_drive"
    assert artifact["approval_required"] == "yes"
    assert json.loads(normalized)["intent_type"] == "email_and_drive"


def test_email_manager_normalizes_sectioned_output():
    raw_output = """
Email findings:
- Need to reply to the partner about the deck
Draft replies:
- Draft: I found the latest deck reference and will confirm before sharing.
Followup items:
- Confirm the approved deck version
Email risks:
- External recipient
Email status: ready for draft
""".strip()

    artifact, normalized = normalize_role_output("email_manager_agent", raw_output, {})

    assert artifact["email_findings"] == [
        "Need to reply to the partner about the deck"
    ]
    assert artifact["email_status"] == "draft_ready"
    assert json.loads(normalized)["email_status"] == "draft_ready"


def test_drive_manager_normalizes_reference_status():
    raw_output = json.dumps(
        {
            "file_matches": ["Q2 Sales Deck v5"],
            "suggested_file_actions": ["Reference the deck only"],
            "sharing_risks": ["Confirm before external share"],
            "missing_documents": [],
            "drive_status": "ready reference",
        }
    )

    artifact, _ = normalize_role_output("drive_manager_agent", raw_output, {})

    assert artifact["drive_status"] == "reference_ready"


def test_assistant_review_normalizes_confirmation_decision():
    raw_output = """
Final response plan:
- Return a draft and the matching file reference
Permission check:
- External share still needs confirmation
Review notes:
- Stay in draft-only mode
Needs user confirmation: yes
Final decision: confirm before send
""".strip()

    artifact, normalized = normalize_role_output(
        "assistant_review_agent",
        raw_output,
        {},
    )

    assert artifact["needs_user_confirmation"] == "yes"
    assert artifact["final_decision"] == "Needs confirmation"
    assert json.loads(normalized)["final_decision"] == "Needs confirmation"
