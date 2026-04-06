import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PHASE3_JSON = REPO_ROOT / "ict_pipeline" / "phase3_candidates.json"
ICT_README = REPO_ROOT / "ict_pipeline" / "README.md"
ROOT_README = REPO_ROOT / "README.md"


def load_phase3_candidates():
    return json.loads(PHASE3_JSON.read_text(encoding="utf-8"))


def test_phase3_candidates_have_expected_ids_and_order():
    candidates = load_phase3_candidates()

    assert [candidate["id"] for candidate in candidates] == [
        "ticket_executor_action_log",
        "ticket_db_human_approval",
    ]
    assert [candidate["recommended_order"] for candidate in candidates] == [1, 2]
    assert [candidate["status"] for candidate in candidates] == [
        "implemented",
        "implemented",
    ]


def test_phase3_candidates_follow_required_design_shape():
    candidates = load_phase3_candidates()
    required_top_level_keys = {
        "artifact_additions",
        "id",
        "must_have_tests",
        "new_environment_components",
        "new_tools",
        "phase",
        "recommended_order",
        "role_extensions",
        "security_benchmark_value",
        "shared_memory_additions",
        "status",
        "title",
        "why_now",
    }
    required_roles = {
        "intake_agent",
        "triage_agent",
        "executor_agent",
        "audit_agent",
    }

    for candidate in candidates:
        assert set(candidate) == required_top_level_keys
        assert candidate["status"] == "implemented"
        assert set(candidate["role_extensions"]) == required_roles
        assert candidate["new_tools"]
        assert candidate["must_have_tests"]
        assert candidate["security_benchmark_value"]


def test_phase3_documentation_references_candidate_files():
    ict_readme = ICT_README.read_text(encoding="utf-8")
    root_readme = ROOT_README.read_text(encoding="utf-8")

    assert "PHASE3_CANDIDATES.md" in ict_readme
    assert "phase3_candidates.json" in ict_readme
    assert "ticket + executor action log`: implemented" in ict_readme
    assert "ticket + DB + human approval`: implemented" in ict_readme

    assert "PHASE3_CANDIDATES.md" in root_readme
    assert "phase3_candidates.json" in root_readme
