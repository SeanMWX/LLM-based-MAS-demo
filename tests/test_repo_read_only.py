import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from coding_agent.demo import APP

REPO_ROOT = Path(__file__).resolve().parents[1]


def python_module_command(*args: str) -> str:
    if os.name == "nt":
        quoted = [f'"{str(Path(sys.executable).resolve())}"', *[f'"{arg}"' for arg in args]]
        return "& " + " ".join(quoted)
    return " ".join(shlex.quote(arg) for arg in [str(Path(sys.executable).resolve()), *args])


def create_demo_repo(tmp_path: Path, failing: bool = False) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    package_dir = tmp_path / "demo_pkg"
    tests_dir = tmp_path / "tests"
    package_dir.mkdir()
    tests_dir.mkdir()

    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "math_utils.py").write_text(
        dedent(
            """
            def add(left: int, right: int) -> int:
                return left + right
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    expected = "4" if failing else "3"
    (tests_dir / "test_math_utils.py").write_text(
        dedent(
            f"""
            from demo_pkg.math_utils import add


            def test_add():
                assert add(1, 2) == {expected}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return tmp_path


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )


def python_script_command(script_path: Path, *args: str) -> str:
    return python_module_command(str(script_path), *args)


def test_scenario_initial_state_switches_to_read_only_mode_with_real_tools():
    scenario = APP.load_scenarios()["simple_feature_python"]

    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        repo_path=".",
        test_command="python -m pytest -q",
    )

    assert state["repo_access_mode"] == "read_only"
    assert state["available_tools"] == ["search", "read_file", "run_tests"]
    assert state["test_command"] == "python -m pytest -q"


def test_resolve_repo_path_raises_for_missing_directory(tmp_path):
    missing = tmp_path / "does-not-exist"

    with pytest.raises(FileNotFoundError):
        APP.resolve_repo_path(str(missing))


def test_resolve_repo_path_raises_for_file_path(tmp_path):
    file_path = tmp_path / "not-a-directory.txt"
    file_path.write_text("hello", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        APP.resolve_repo_path(str(file_path))


def test_perception_node_collects_live_repo_snapshot(tmp_path):
    repo_path = create_demo_repo(tmp_path)
    scenario = APP.load_scenarios()["simple_feature_python"]
    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        repo_path=str(repo_path),
    )

    updated = APP.perception_node(state)

    assert updated["repo_snapshot"]["repo_path"] == str(repo_path.resolve())
    assert updated["repo_snapshot"]["file_count"] >= 3
    assert "demo_pkg/math_utils.py" in updated["repo_snapshot"]["python_files_sample"]
    assert "tests/test_math_utils.py" in updated["repo_snapshot"]["test_files_sample"]
    assert updated["read_only_files"]
    assert any(
        item["path"] == "demo_pkg/math_utils.py" for item in updated["read_only_files"]
    )
    assert "def add(left: int, right: int) -> int:" in updated["live_file_context"]
    assert "assert add(1, 2) ==" in updated["live_file_context"]
    assert f"Live repo path: {repo_path.resolve()}" in updated["observations"]
    assert "Read-only file excerpts collected:" in updated["observations"][-1]


def test_read_repo_text_file_rejects_outside_repo_path(tmp_path):
    repo_path = create_demo_repo(tmp_path / "repo")
    outside_file = tmp_path / "outside.py"
    outside_file.write_text("print('outside')\n", encoding="utf-8")

    content = APP.read_repo_text_file(repo_path.resolve(), "../outside.py")

    assert content is None


def test_read_repo_text_file_skips_large_and_non_text_files(tmp_path):
    repo_path = create_demo_repo(tmp_path / "repo")
    large_file = repo_path / "large.py"
    binary_file = repo_path / "image.png"
    large_file.write_text("x" * 210_000, encoding="utf-8")
    binary_file.write_bytes(b"\x89PNG\r\n\x1a\n" + (b"\x00" * 32))

    assert APP.read_repo_text_file(repo_path.resolve(), "large.py") is None
    assert APP.read_repo_text_file(repo_path.resolve(), "image.png") is None


def test_collect_read_only_files_respects_max_files_limit(tmp_path):
    repo_path = create_demo_repo(tmp_path)
    snapshot = APP.collect_repo_snapshot(repo_path.resolve())
    state = {
        "task": "Inspect helpers and tests",
        "repository_context": "Small Python package",
        "acceptance_criteria": ["Add feature", "Add tests"],
    }

    files = APP.collect_read_only_files(
        repo_path=repo_path.resolve(),
        snapshot=snapshot,
        state=state,
        max_files=2,
    )

    assert len(files) <= 2


def test_run_scenario_executes_real_pytest_and_records_pass_result(tmp_path):
    repo_path = create_demo_repo(tmp_path, failing=False)
    scenario = APP.load_scenarios()["simple_feature_python"]

    state = APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        repo_path=str(repo_path),
        test_command=python_module_command("-m", "pytest", "-q"),
        test_timeout_sec=60,
    )

    assert state["workflow_status"] == "completed"
    assert state["repo_access_mode"] == "read_only"
    assert state["test_run_result"]["passed"] is True
    assert state["test_run_result"]["cwd"] == str(repo_path.resolve())
    assert "1 passed" in state["test_run_result"]["stdout_tail"]
    assert state["role_artifacts"]["tester"]["verdict"] == "Pass"
    assert any(
        line.startswith("Run real test command:")
        for line in state["role_artifacts"]["tester"]["verification_plan"]
    )
    assert any(
        event["event"] == "test_command_executed" and event.get("role") == "tester"
        for event in state["action_trace"]
    )


def test_run_scenario_with_test_command_only_uses_repo_root_fallback():
    scenario = APP.load_scenarios()["simple_feature_python"]

    state = APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        test_command=python_module_command("-m", "pytest", "tests/test_parsing_helpers.py", "-q"),
        test_timeout_sec=60,
    )

    assert state["workflow_status"] == "completed"
    assert state["repo_access_mode"] == "read_only"
    assert state["repo_path"] is None
    assert state["test_run_result"]["passed"] is True
    assert state["test_run_result"]["cwd"] == str(REPO_ROOT)
    assert "7 passed" in state["test_run_result"]["stdout_tail"]


def test_run_scenario_executes_real_pytest_and_records_fail_result(tmp_path):
    repo_path = create_demo_repo(tmp_path, failing=True)
    scenario = APP.load_scenarios()["simple_feature_python"]

    state = APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        repo_path=str(repo_path),
        test_command=python_module_command("-m", "pytest", "-q"),
        test_timeout_sec=60,
    )

    assert state["workflow_status"] == "completed"
    assert state["test_run_result"]["passed"] is False
    assert state["test_run_result"]["exit_code"] == 1
    assert state["role_artifacts"]["tester"]["verdict"] == "Fail"
    assert "Real test command failed with exit code 1." in state["role_artifacts"][
        "tester"
    ]["failure_checks"]


def test_run_scenario_records_timeout_result(tmp_path):
    repo_path = create_demo_repo(tmp_path / "repo")
    sleep_script = tmp_path / "repo" / "sleep_for_timeout.py"
    sleep_script.write_text(
        dedent(
            """
            import time

            time.sleep(2.5)
            print("finished")
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    scenario = APP.load_scenarios()["simple_feature_python"]

    state = APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
        repo_path=str(repo_path),
        test_command=python_script_command(sleep_script),
        test_timeout_sec=1,
    )

    assert state["workflow_status"] == "completed"
    assert state["test_run_result"]["timeout"] is True
    assert state["test_run_result"]["passed"] is False
    assert state["test_run_result"]["exit_code"] is None
    assert state["role_artifacts"]["tester"]["verdict"] == "Fail"
    assert "Real test command timed out." in state["role_artifacts"]["tester"][
        "failure_checks"
    ]


def test_reviewer_brief_includes_latest_test_execution():
    brief = APP.build_agent_brief(
        "reviewer",
        {
            "task": "Implement the feature",
            "repository_context": "Small Python package",
            "acceptance_criteria": ["Add feature", "Add tests"],
            "risk_notes": ["Keep patch minimal"],
            "available_tools": ["search", "read_file", "run_tests"],
            "repo_access_mode": "read_only",
            "live_file_context": (
                "Path: demo_pkg/math_utils.py\n"
                "Snippet:\n"
                "   1 def add(left: int, right: int) -> int:\n"
                "   2     return left + right"
            ),
            "role_outputs": {
                "planner": '{"plan":["inspect module"]}',
                "coder": '{"patch_summary":["minimal patch"]}',
                'tester': '{"verification_plan":["run pytest"],"failure_checks":[],"verdict":"Pass"}',
            },
            "test_run_result": {
                "command": "python -m pytest -q",
                "cwd": str(REPO_ROOT),
                "passed": True,
                "exit_code": 0,
                "timeout": False,
                "stdout_tail": "1 passed in 0.01s",
                "stderr_tail": "",
            },
        },
    )

    assert "Read-only file excerpts:" in brief
    assert "Path: demo_pkg/math_utils.py" in brief
    assert "Latest test execution:" in brief
    assert "Command: python -m pytest -q" in brief
    assert "Passed: True" in brief


def test_reviewer_brief_omits_test_execution_before_tester():
    brief = APP.build_agent_brief(
        "coder",
        {
            "task": "Implement the feature",
            "repository_context": "Small Python package",
            "acceptance_criteria": ["Add feature", "Add tests"],
            "risk_notes": ["Keep patch minimal"],
            "available_tools": ["search", "read_file", "run_tests"],
            "repo_access_mode": "read_only",
            "role_outputs": {
                "planner": '{"plan":["inspect module"]}',
            },
            "test_run_result": {
                "command": "python -m pytest -q",
                "cwd": str(REPO_ROOT),
                "passed": True,
                "exit_code": 0,
                "timeout": False,
                "stdout_tail": "1 passed in 0.01s",
                "stderr_tail": "",
            },
        },
    )

    assert "Latest test execution:" not in brief


def test_cli_run_supports_real_repo_snapshot_and_test_execution(tmp_path):
    repo_path = create_demo_repo(tmp_path, failing=False)
    result = run_cli(
        "coding_agent/demo.py",
        "run",
        "--case",
        "simple_feature_python",
        "--repo-path",
        str(repo_path),
        "--test-command",
        python_module_command("-m", "pytest", "-q"),
        "--test-timeout",
        "60",
    )

    payload = json.loads(result.stdout)

    assert payload[0]["repo_access_mode"] == "read_only"
    assert payload[0]["repo_snapshot"]["repo_path"] == str(repo_path.resolve())
    assert payload[0]["read_only_files"]
    assert "def add(left: int, right: int) -> int:" in payload[0]["live_file_context"]
    assert payload[0]["test_run_result"]["passed"] is True
    assert payload[0]["action_trace"]
    assert "Workflow Started" in payload[0]["action_trace_text"]
