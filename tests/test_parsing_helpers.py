import json

from coding_agent.demo import (
    coerce_list,
    coerce_string,
    dump_artifact,
    empty_artifact_for_role,
    extract_json_object,
    normalize_decision,
)


def test_empty_artifact_for_role_returns_expected_schema_shape():
    assert empty_artifact_for_role("planner") == {
        "plan": [],
        "success_criteria": [],
        "risks": [],
        "handoff_to_coder": [],
    }
    assert empty_artifact_for_role("tester") == {
        "verification_plan": [],
        "failure_checks": [],
        "verdict": "",
    }


def test_dump_artifact_round_trips_to_json():
    artifact = {
        "plan": ["inspect module"],
        "success_criteria": ["tests pass"],
        "risks": ["none"],
        "handoff_to_coder": ["keep patch minimal"],
    }

    dumped = dump_artifact(artifact)

    assert json.loads(dumped) == artifact


def test_coerce_list_handles_bullets_strings_and_scalars():
    assert coerce_list(["- first", "2. second", "third"]) == [
        "first",
        "second",
        "third",
    ]
    assert coerce_list("line one\n- line two\n3. line three") == [
        "line one",
        "line two",
        "line three",
    ]
    assert coerce_list(None) == []
    assert coerce_list(42) == ["42"]


def test_coerce_string_handles_strings_lists_and_none():
    assert coerce_string("  hello  ") == "hello"
    assert coerce_string(["- alpha", "2. beta", "gamma"]) == "alpha; beta; gamma"
    assert coerce_string(None) == ""
    assert coerce_string(99) == "99"


def test_normalize_decision_maps_common_variants():
    assert normalize_decision("approve") == "Approve"
    assert normalize_decision("Request Changes please") == "Request changes"
    assert normalize_decision("Needs Verification before merge") == "Needs verification"
    assert normalize_decision("unknown") == "Needs verification"


def test_extract_json_object_handles_fenced_and_prefixed_json():
    fenced = """```json
    {"plan": ["inspect module"]}
    ```"""
    prefixed = 'Here is the result: {"plan": ["inspect module"], "risks": ["none"]}'

    assert extract_json_object(fenced) == {"plan": ["inspect module"]}
    assert extract_json_object(prefixed) == {
        "plan": ["inspect module"],
        "risks": ["none"],
    }


def test_extract_json_object_returns_none_for_invalid_input():
    assert extract_json_object("not json") is None
    assert extract_json_object('{"plan": ["inspect module"]') is None
