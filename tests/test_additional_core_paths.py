import json
import subprocess
import sys
from pathlib import Path

import pytest

from coding_agent.demo import APP
from framework.core import env_int, first_env

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_behavior_route_decision_returns_end_for_completed_state():
    assert APP.behavior_route_decision({"workflow_status": "completed"}) == "end"


def test_behavior_route_decision_returns_continue_for_running_state():
    assert APP.behavior_route_decision({"workflow_status": "running"}) == "continue"


def test_resolve_requested_scenarios_returns_all_cases():
    scenarios = APP.load_scenarios()

    resolved = APP.resolve_requested_scenarios("all", scenarios)

    assert len(resolved) == len(scenarios)
    assert {scenario.id for scenario in resolved} == set(scenarios)


def test_resolve_requested_scenarios_raises_for_unknown_case():
    scenarios = APP.load_scenarios()

    with pytest.raises(KeyError):
        APP.resolve_requested_scenarios("does_not_exist", scenarios)


def test_build_final_report_preserves_role_order():
    updated_outputs = {
        "planner": '{"plan":["a"]}',
        "coder": '{"patch_summary":["b"]}',
        "tester": '{"verdict":"Pass"}',
        "reviewer": '{"decision":"Approve"}',
    }
    state = {"title": "Demo title"}

    report = APP.build_final_report(state, updated_outputs)

    assert report.startswith("Scenario: Demo title")
    assert report.index("Planner:") < report.index("Coder:")
    assert report.index("Coder:") < report.index("Tester:")
    assert report.index("Tester:") < report.index("Reviewer:")


def test_communication_brief_node_adds_log_and_agent_brief():
    state = {
        "active_role": "planner",
        "task": "Implement the feature",
        "repository_context": "Small repo",
        "acceptance_criteria": ["Add feature", "Add tests"],
        "risk_notes": ["Keep patch minimal"],
        "role_outputs": {},
        "execution_log": [],
    }

    updated = APP.communication_brief_node(state)

    assert "Role: planner" in updated["agent_brief"]
    assert "No prior role outputs yet." in updated["agent_brief"]
    assert "communication: built handoff brief for `planner`" in updated["execution_log"][-1]


def test_first_env_prefers_first_populated_name(monkeypatch):
    monkeypatch.delenv("FIRST_NAME", raising=False)
    monkeypatch.setenv("SECOND_NAME", "value-2")
    monkeypatch.setenv("THIRD_NAME", "value-3")

    assert first_env("FIRST_NAME", "SECOND_NAME", "THIRD_NAME") == "value-2"


def test_env_int_returns_default_when_missing(monkeypatch):
    monkeypatch.delenv("MISSING_INT_ENV", raising=False)

    assert env_int("MISSING_INT_ENV", 123) == 123


def test_cli_render_unknown_case_returns_nonzero():
    result = subprocess.run(
        [sys.executable, "coding_agent/demo.py", "render", "--case", "does_not_exist"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "KeyError" in result.stderr or "Unknown" in result.stderr


def test_cli_run_all_returns_multiple_results():
    result = subprocess.run(
        [sys.executable, "coding_agent/demo.py", "run", "--case", "all"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)

    assert len(payload) == len(APP.load_scenarios())
