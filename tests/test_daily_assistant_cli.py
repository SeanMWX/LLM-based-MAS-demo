import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )


def test_daily_assistant_list_command_outputs_case_ids():
    result = run_cli("daily_assistant/demo.py", "list")

    assert "reply_with_latest_quarterly_deck" in result.stdout
    assert "morning_followup_triage" in result.stdout
    assert "expense_receipt_archive" in result.stdout


def test_daily_assistant_render_command_outputs_json():
    result = run_cli(
        "daily_assistant/demo.py",
        "render",
        "--case",
        "reply_with_latest_quarterly_deck",
    )

    payload = json.loads(result.stdout)

    assert payload["id"] == "reply_with_latest_quarterly_deck"
    assert payload["title"] == "Draft a reply with the latest quarterly deck"
    assert "search_email" in payload["available_tools"]
    assert "search_drive" in payload["available_tools"]
    assert "search_policy" in payload["available_tools"]
    assert "read_policy_rule" in payload["available_tools"]
    assert "stage_mail_adapter_action" in payload["available_tools"]
    assert "read_drive_adapter_receipts" in payload["available_tools"]
    assert payload["role_order"] == [
        "intake_router_agent",
        "email_manager_agent",
        "drive_manager_agent",
        "assistant_review_agent",
    ]


def test_daily_assistant_run_command_outputs_structured_summary():
    result = run_cli(
        "daily_assistant/demo.py",
        "run",
        "--case",
        "reply_with_latest_quarterly_deck",
    )

    payload = json.loads(result.stdout)

    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["scenario_id"] == "reply_with_latest_quarterly_deck"
    assert payload[0]["workflow_status"] == "completed"
    assert payload[0]["assistant_phase"] == "email_drive_policy_confirmation_queue_action_log_sandbox_adapters"
    assert payload[0]["policy_phase"] == "policy_kb_confirmation_gating"
    assert payload[0]["queue_phase"] == "confirmation_queue_action_log"
    assert payload[0]["adapter_phase"] == "sandboxed_mail_drive_adapters"
    assert payload[0]["email_matches"]
    assert payload[0]["drive_matches"]
    assert payload[0]["policy_matches"]
    assert payload[0]["assistant_action_log"]
    assert payload[0]["confirmation_queue"]
    assert payload[0]["assistant_receipts"]
    assert payload[0]["sandbox_mail_records"]
    assert payload[0]["sandbox_drive_records"]
    assert payload[0]["sandbox_adapter_receipts"]
    assert payload[0]["assistant_execution_evidence"]["queue_status"] == "pending_confirmation"
    assert payload[0]["sandbox_execution_summary"]["adapter_verdict"] == "awaiting_confirmation"
    assert payload[0]["role_artifacts"]["intake_router_agent"]["request_summary"]
    assert payload[0]["role_artifacts"]["email_manager_agent"]["draft_replies"]
    assert payload[0]["role_artifacts"]["email_manager_agent"]["policy_flags"]
    assert payload[0]["role_artifacts"]["email_manager_agent"]["proposed_email_actions"]
    assert payload[0]["role_artifacts"]["email_manager_agent"]["email_receipt_ids"]
    assert payload[0]["role_artifacts"]["email_manager_agent"]["sandbox_email_receipts"]
    assert payload[0]["role_artifacts"]["drive_manager_agent"]["file_matches"]
    assert payload[0]["role_artifacts"]["drive_manager_agent"]["sharing_requirements"]
    assert payload[0]["role_artifacts"]["drive_manager_agent"]["proposed_drive_actions"]
    assert payload[0]["role_artifacts"]["drive_manager_agent"]["drive_receipt_ids"]
    assert payload[0]["role_artifacts"]["drive_manager_agent"]["sandbox_drive_receipts"]
    assert payload[0]["role_artifacts"]["assistant_review_agent"]["final_decision"]
    assert payload[0]["role_artifacts"]["assistant_review_agent"]["policy_evidence_review"]
    assert payload[0]["role_artifacts"]["assistant_review_agent"]["confirmation_queue_review"]
    assert payload[0]["role_artifacts"]["assistant_review_agent"]["action_log_review"]
    assert payload[0]["role_artifacts"]["assistant_review_agent"]["adapter_evidence_review"]
    assert payload[0]["role_artifacts"]["assistant_review_agent"]["adapter_verdict"] == "awaiting_confirmation"
