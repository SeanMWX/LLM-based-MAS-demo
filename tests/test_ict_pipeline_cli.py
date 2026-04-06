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


def test_ict_pipeline_list_command_outputs_case_ids():
    result = run_cli("ict_pipeline/demo.py", "list")

    assert "vpn_access_reset" in result.stdout
    assert "new_hire_access_bundle" in result.stdout
    assert "printer_issue_branch_office" in result.stdout


def test_ict_pipeline_render_command_outputs_json():
    result = run_cli(
        "ict_pipeline/demo.py",
        "render",
        "--case",
        "vpn_access_reset",
    )

    payload = json.loads(result.stdout)

    assert payload["id"] == "vpn_access_reset"
    assert payload["title"] == "Reset a locked VPN account"
    assert "search_kb" in payload["available_tools"]
    assert "read_kb_article" in payload["available_tools"]
    assert "record_action_log" in payload["available_tools"]
    assert "read_action_log" in payload["available_tools"]
    assert "read_executor_receipt" in payload["available_tools"]
    assert "read_ticket_db" in payload["available_tools"]
    assert "update_ticket_db" in payload["available_tools"]
    assert "request_human_approval" in payload["available_tools"]
    assert "read_approval_status" in payload["available_tools"]
    assert payload["role_order"] == [
        "intake_agent",
        "triage_agent",
        "executor_agent",
        "audit_agent",
    ]


def test_ict_pipeline_run_command_outputs_structured_summary():
    result = run_cli(
        "ict_pipeline/demo.py",
        "run",
        "--case",
        "vpn_access_reset",
    )

    payload = json.loads(result.stdout)

    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["scenario_id"] == "vpn_access_reset"
    assert payload[0]["workflow_status"] == "completed"
    assert payload[0]["role_artifacts"]["intake_agent"]["ticket_summary"]
    assert payload[0]["role_artifacts"]["triage_agent"]["kb_matches"]
    assert payload[0]["role_artifacts"]["executor_agent"]["action_log_entries"]
    assert payload[0]["execution_evidence"]["receipt_consistency"] == "consistent"
    assert payload[0]["ticket_db_record"]["ticket_id"].startswith("TCK-")
    assert "approval_wait_state" in payload[0]["approval_state"]
    assert payload[0]["approval_history"]
