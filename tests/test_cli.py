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


def test_coding_agent_list_command_outputs_case_ids():
    result = run_cli("coding_agent/demo.py", "list")

    assert "simple_feature_python" in result.stdout
    assert "bugfix_validation" in result.stdout
    assert "test_gap_regression" in result.stdout


def test_coding_agent_render_command_outputs_json():
    result = run_cli(
        "coding_agent/demo.py",
        "render",
        "--case",
        "simple_feature_python",
    )

    payload = json.loads(result.stdout)

    assert payload["id"] == "simple_feature_python"
    assert payload["title"] == "Add a small pure helper function"
    assert payload["role_order"] == ["planner", "coder", "tester", "reviewer"]


def test_coding_agent_run_command_outputs_structured_summary():
    result = run_cli(
        "coding_agent/demo.py",
        "run",
        "--case",
        "simple_feature_python",
    )

    payload = json.loads(result.stdout)

    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["scenario_id"] == "simple_feature_python"
    assert payload[0]["workflow_status"] == "completed"
    assert payload[0]["role_artifacts"]["planner"]["plan"]


def test_compatibility_entrypoint_still_lists_cases():
    result = run_cli("mas_benchmark_demo.py", "list")

    assert "simple_feature_python" in result.stdout
    assert "bugfix_validation" in result.stdout


def test_coding_agent_run_supports_seed_file_for_reviewer_start():
    result = run_cli(
        "coding_agent/demo.py",
        "run",
        "--case",
        "simple_feature_python",
        "--seed-file",
        "coding_agent/seeds/reviewer_hypothesis.json",
    )

    payload = json.loads(result.stdout)

    assert payload[0]["start_role"] == "reviewer"
    assert payload[0]["role_artifacts"]["tester"]["verdict"] == "Needs verification"
    assert payload[0]["role_artifacts"]["reviewer"]["decision"] == "Approve"
    assert payload[0]["seed_context"]["candidate_diff"]


def test_coding_agent_run_with_missing_seed_file_returns_nonzero():
    result = subprocess.run(
        [
            sys.executable,
            "coding_agent/demo.py",
            "run",
            "--case",
            "simple_feature_python",
            "--seed-file",
            "coding_agent/seeds/does_not_exist.json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Seed file does not exist" in result.stderr
