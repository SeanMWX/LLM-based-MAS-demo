import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_daily_assistant_phase_status_declares_phase3b_current():
    payload = json.loads(
        (REPO_ROOT / "daily_assistant" / "phase_status.json").read_text(
            encoding="utf-8"
        )
    )

    assert payload["demo"] == "daily_assistant"
    assert payload["current_phase"] == "phase3b"
    phases = {phase["id"]: phase for phase in payload["phases"]}
    assert phases["phase1"]["status"] == "implemented"
    assert phases["phase2"]["status"] == "implemented"
    assert phases["phase3a"]["status"] == "implemented"
    assert phases["phase3b"]["status"] == "implemented"
