import json
from pathlib import Path

from coding_agent.demo import APP, ROLE_ORDER

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"


def test_simple_feature_role_artifacts_match_snapshot():
    scenario = APP.load_scenarios()["simple_feature_python"]
    state = APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
    )

    expected = json.loads(
        (SNAPSHOT_DIR / "simple_feature_python.role_artifacts.json").read_text(
            encoding="utf-8"
        )
    )

    assert state["role_artifacts"] == expected


def test_role_outputs_round_trip_to_snapshot():
    scenario = APP.load_scenarios()["simple_feature_python"]
    state = APP.run_scenario(
        scenario=scenario,
        invoke_model=False,
        model_name=None,
    )

    expected = json.loads(
        (SNAPSHOT_DIR / "simple_feature_python.role_artifacts.json").read_text(
            encoding="utf-8"
        )
    )

    for role in ROLE_ORDER:
        assert json.loads(state["role_outputs"][role]) == expected[role]
