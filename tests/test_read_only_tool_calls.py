import json
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

from coding_agent.demo import APP


def create_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "repo"
    package_dir = repo_path / "demo_pkg"
    tests_dir = repo_path / "tests"
    package_dir.mkdir(parents=True)
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
    (tests_dir / "test_math_utils.py").write_text(
        dedent(
            """
            from demo_pkg.math_utils import add


            def test_add():
                assert add(1, 2) == 3
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return repo_path


def build_live_planner_state(repo_path: Path):
    scenario = APP.load_scenarios()["simple_feature_python"]
    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=True,
        model_name=None,
        repo_path=str(repo_path),
    )
    state.update(APP.perception_node(state))
    state["active_role"] = "planner"
    state.update(APP.communication_brief_node(state))
    return state


def test_search_repo_returns_path_and_content_matches(tmp_path):
    repo_path = create_repo(tmp_path)

    result = APP.search_repo(repo_path.resolve(), "math_utils", top_k=5)

    assert result["tool"] == "search"
    assert result["matches"]
    assert any(item["kind"] == "path" for item in result["matches"])
    assert any(item["kind"] == "content" for item in result["matches"])


def test_parse_tool_request_accepts_wrapped_shapes():
    request = APP.parse_tool_request(
        '{"tool_request":{"tool":"search","query":"normalize_slug","top_k":"3"}}',
        ["search", "read_file", "run_tests"],
    )

    assert request == {"tool": "search", "query": "normalize_slug", "top_k": 3}


def test_parse_tool_request_rejects_unsupported_or_malformed_shapes():
    assert APP.parse_tool_request("not json", ["search", "read_file"]) is None
    assert (
        APP.parse_tool_request('{"tool":"run_tests"}', ["search", "read_file", "run_tests"])
        is None
    )
    assert APP.parse_tool_request('{"tool_request":{"tool":"read_file"}}', ["read_file"]) is None


def test_inference_execute_node_runs_tool_rounds_before_final_output(
    monkeypatch,
    tmp_path,
):
    repo_path = create_repo(tmp_path)
    state = build_live_planner_state(repo_path)
    prompts: list[str] = []

    class FakeModel:
        def __init__(self):
            self.responses = [
                '{"tool_request":{"tool":"search","query":"add","top_k":2}}',
                '{"tool_request":{"tool":"read_file","path":"demo_pkg/math_utils.py"}}',
                json.dumps(
                    {
                        "plan": ["Inspect math helper implementation."],
                        "success_criteria": ["Tests pass"],
                        "risks": ["Keep patch minimal"],
                        "handoff_to_coder": ["Touch math_utils.py only if needed"],
                    }
                ),
            ]

        def invoke(self, messages):
            prompts.append(messages[-1].content)
            return SimpleNamespace(content=self.responses.pop(0))

    model = FakeModel()
    monkeypatch.setattr(APP, "build_model", lambda _model_name: model)

    updated = APP.inference_execute_node(state)

    assert updated["latest_artifact"]["plan"] == ["Inspect math helper implementation."]
    assert len(updated["tool_events"]) == 2
    assert updated["tool_events"][0]["request"]["tool"] == "search"
    assert updated["tool_events"][1]["request"]["tool"] == "read_file"
    tool_trace_events = [
        event["event"] for event in updated["action_trace"] if event.get("role") == "planner"
    ]
    assert "tool_request" in tool_trace_events
    assert "tool_result" in tool_trace_events
    assert "role_completed" in tool_trace_events
    assert "Tool result:" in updated["agent_brief"]
    assert "demo_pkg/math_utils.py" in updated["agent_brief"]
    assert "def add(left: int, right: int) -> int:" in updated["agent_brief"]
    assert any("Search query: add" in prompt for prompt in prompts[1:])


def test_read_file_tool_returns_not_found_for_missing_path(tmp_path):
    repo_path = create_repo(tmp_path)

    result = APP.execute_read_only_tool(
        repo_path.resolve(),
        {"tool": "read_file", "path": "missing.py"},
    )

    assert result["tool"] == "read_file"
    assert result["found"] is False
