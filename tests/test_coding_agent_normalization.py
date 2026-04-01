import json

from coding_agent.demo import normalize_role_output


def test_planner_normalization_parses_prefixed_json():
    raw = (
        "Let me create a compact JSON plan.\n"
        '{"plan":["inspect module"],'
        '"success_criteria":["tests pass"],'
        '"risks":["none"],'
        '"handoff_to_coder":["keep patch minimal"]}'
    )

    artifact, normalized = normalize_role_output("planner", raw, {})

    assert artifact["plan"] == ["inspect module"]
    assert artifact["success_criteria"] == ["tests pass"]
    assert artifact["risks"] == ["none"]
    assert artifact["handoff_to_coder"] == ["keep patch minimal"]
    assert json.loads(normalized) == artifact


def test_tester_normalization_falls_back_to_sectioned_text():
    raw = """
    Verification plan:
    - Run pytest
    - Re-check the touched module

    Failure checks:
    - Missing regression test
    - Unexpected output format

    Verdict: Pass
    """

    artifact, _normalized = normalize_role_output("tester", raw, {})

    assert artifact["verification_plan"] == [
        "Run pytest",
        "Re-check the touched module",
    ]
    assert artifact["failure_checks"] == [
        "Missing regression test",
        "Unexpected output format",
    ]
    assert artifact["verdict"] == "Pass"


def test_reviewer_decision_is_normalized():
    raw = """
    Review summary:
    - Patch is small
    - Tests are proportionate

    Risks:
    - Real repo verification still missing

    Decision: approve
    """

    artifact, _normalized = normalize_role_output("reviewer", raw, {})

    assert artifact["decision"] == "Approve"


def test_missing_tester_verdict_defaults_to_needs_verification():
    raw = """
    Verification plan:
    - Run pytest
    Failure checks:
    - Missing tests
    """

    artifact, _normalized = normalize_role_output("tester", raw, {})

    assert artifact["verdict"] == "Needs verification"


def test_invalid_json_produces_empty_schema_shape():
    raw = "This is not valid JSON and has no expected sections."

    artifact, normalized = normalize_role_output("coder", raw, {})

    assert artifact == {
        "patch_summary": [],
        "likely_files": [],
        "constraints": [],
    }
    assert json.loads(normalized) == artifact
