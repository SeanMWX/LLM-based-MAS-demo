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
    assert payload[0]["assistant_phase"] == "email_drive_read_only_draft"
    assert payload[0]["email_matches"]
    assert payload[0]["drive_matches"]
    assert payload[0]["role_artifacts"]["intake_router_agent"]["request_summary"]
    assert payload[0]["role_artifacts"]["email_manager_agent"]["draft_replies"]
    assert payload[0]["role_artifacts"]["drive_manager_agent"]["file_matches"]
    assert payload[0]["role_artifacts"]["assistant_review_agent"]["final_decision"]
