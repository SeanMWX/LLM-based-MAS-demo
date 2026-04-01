import os

import pytest

from coding_agent.demo import APP


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_MODEL_TESTS") != "1",
    reason="Set RUN_LIVE_MODEL_TESTS=1 to run live MiniMax smoke tests.",
)


def test_live_minimax_smoke():
    scenario = APP.load_scenarios()["simple_feature_python"]

    state = APP.run_scenario(
        scenario=scenario,
        invoke_model=True,
        model_name=None,
    )

    assert state["workflow_status"] == "completed"
    assert state["role_artifacts"]["planner"]["plan"]
    assert state["role_artifacts"]["coder"]["likely_files"]
    assert state["role_artifacts"]["tester"]["verdict"]
    assert state["role_artifacts"]["reviewer"]["decision"] in {
        "Approve",
        "Request changes",
        "Needs verification",
    }
