import sys
from types import SimpleNamespace

from langchain_core.messages import HumanMessage

from coding_agent.demo import APP
from framework.core import MiniMaxAnthropicAdapter


def build_planner_state():
    scenario = APP.load_scenarios()["simple_feature_python"]
    state = APP.scenario_to_initial_state(
        scenario=scenario,
        invoke_model=True,
        model_name=None,
    )
    state["active_role"] = "planner"
    state["agent_brief"] = "Planner brief"
    return state


def test_minimax_adapter_prefers_text_blocks_over_thinking(monkeypatch):
    class FakeClient:
        def __init__(self, **_kwargs):
            self.messages = SimpleNamespace(create=self.create)

        def create(self, **_kwargs):
            return SimpleNamespace(
                content=[
                    SimpleNamespace(type="thinking", thinking="internal reasoning"),
                    SimpleNamespace(type="text", text='{"ok": true}'),
                ]
            )

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=FakeClient))

    adapter = MiniMaxAnthropicAdapter(
        api_key="fake-key",
        base_url="https://api.minimaxi.com/anthropic",
        model="MiniMax-M2.5",
        max_tokens=64,
    )
    response = adapter.invoke([HumanMessage(content="reply with json")])

    assert response.content == '{"ok": true}'


def test_minimax_adapter_falls_back_to_thinking_when_text_is_missing(monkeypatch):
    class FakeClient:
        def __init__(self, **_kwargs):
            self.messages = SimpleNamespace(create=self.create)

        def create(self, **_kwargs):
            return SimpleNamespace(
                content=[
                    SimpleNamespace(type="thinking", thinking="internal reasoning only"),
                ]
            )

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=FakeClient))

    adapter = MiniMaxAnthropicAdapter(
        api_key="fake-key",
        base_url="https://api.minimaxi.com/anthropic",
        model="MiniMax-M2.5",
        max_tokens=64,
    )
    response = adapter.invoke([HumanMessage(content="reply with reasoning")])

    assert response.content == "internal reasoning only"


def test_inference_execute_node_normalizes_prefixed_json_from_mock_provider(monkeypatch):
    class FakeModel:
        def invoke(self, _messages):
            return SimpleNamespace(
                content=(
                    "Let me create a compact JSON plan.\n"
                    '{"plan":["inspect module"],'
                    '"success_criteria":["tests pass"],'
                    '"risks":["none"],'
                    '"handoff_to_coder":["keep patch minimal"]}'
                )
            )

    monkeypatch.setattr(APP, "build_model", lambda _model_name: FakeModel())

    updated = APP.inference_execute_node(build_planner_state())

    assert updated["latest_artifact"]["plan"] == ["inspect module"]
    assert updated["latest_artifact"]["success_criteria"] == ["tests pass"]
    assert updated["latest_artifact"]["risks"] == ["none"]
    assert updated["latest_artifact"]["handoff_to_coder"] == ["keep patch minimal"]


def test_inference_execute_node_handles_invalid_json_from_mock_provider(monkeypatch):
    class FakeModel:
        def invoke(self, _messages):
            return SimpleNamespace(content="not valid json at all")

    monkeypatch.setattr(APP, "build_model", lambda _model_name: FakeModel())

    updated = APP.inference_execute_node(build_planner_state())

    assert updated["latest_artifact"] == {
        "plan": [],
        "success_criteria": [],
        "risks": [],
        "handoff_to_coder": [],
    }


def test_inference_execute_node_normalizes_json_inside_code_fence(monkeypatch):
    class FakeModel:
        def invoke(self, _messages):
            return SimpleNamespace(
                content=(
                    "```json\n"
                    '{"plan":["inspect module"],'
                    '"success_criteria":["tests pass"],'
                    '"risks":["none"],'
                    '"handoff_to_coder":["keep patch minimal"]}'
                    "\n```"
                )
            )

    monkeypatch.setattr(APP, "build_model", lambda _model_name: FakeModel())

    updated = APP.inference_execute_node(build_planner_state())

    assert updated["latest_artifact"]["plan"] == ["inspect module"]
    assert updated["latest_artifact"]["success_criteria"] == ["tests pass"]


def test_inference_execute_node_handles_truncated_json_from_mock_provider(monkeypatch):
    class FakeModel:
        def invoke(self, _messages):
            return SimpleNamespace(
                content=(
                    '{"plan":["inspect module"],'
                    '"success_criteria":["tests pass"]'
                )
            )

    monkeypatch.setattr(APP, "build_model", lambda _model_name: FakeModel())

    updated = APP.inference_execute_node(build_planner_state())

    assert updated["latest_artifact"] == {
        "plan": [],
        "success_criteria": [],
        "risks": [],
        "handoff_to_coder": [],
    }
