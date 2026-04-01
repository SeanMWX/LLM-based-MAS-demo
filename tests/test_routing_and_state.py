from coding_agent.demo import APP, ROLE_ORDER


def test_behavior_route_selects_expected_next_role():
    state = {
        "next_role_index": 1,
        "execution_log": [],
    }

    updated = APP.behavior_route_node(state)

    assert updated["active_role"] == "coder"
    assert updated["workflow_status"] == "running"
    assert "behavior: selected next role `coder`" in updated["execution_log"][-1]


def test_behavior_route_marks_workflow_complete_when_roles_are_exhausted():
    state = {
        "next_role_index": len(ROLE_ORDER),
        "execution_log": [],
    }

    updated = APP.behavior_route_node(state)

    assert updated["active_role"] == ""
    assert updated["workflow_status"] == "completed"
    assert "behavior: workflow marked complete" in updated["execution_log"][-1]


def test_build_agent_brief_marks_missing_prior_outputs():
    state = {
        "task": "Implement the feature",
        "repository_context": "Small Python package",
        "acceptance_criteria": ["Add feature", "Add tests"],
        "risk_notes": ["Keep patch minimal"],
        "role_outputs": {
            "planner": '{"plan":["inspect module"]}',
        },
    }

    brief = APP.build_agent_brief("reviewer", state)

    assert "Planner output" in brief
    assert "Coder output:\n(missing)" in brief
    assert "Tester output:\n(missing)" in brief


def test_coordination_commit_persists_output_and_artifact():
    state = {
        "active_role": "coder",
        "latest_output": '{"patch_summary":["minimal patch"]}',
        "latest_artifact": {
            "patch_summary": ["minimal patch"],
            "likely_files": ["utils/helpers.py"],
            "constraints": ["Keep patch minimal"],
        },
        "role_outputs": {
            "planner": '{"plan":["inspect module"]}',
        },
        "role_artifacts": {
            "planner": {
                "plan": ["inspect module"],
                "success_criteria": ["tests pass"],
                "risks": ["none"],
                "handoff_to_coder": ["keep patch minimal"],
            }
        },
        "shared_memory": {
            "role_outputs": {
                "planner": '{"plan":["inspect module"]}',
            },
            "role_artifacts": {
                "planner": {
                    "plan": ["inspect module"],
                    "success_criteria": ["tests pass"],
                    "risks": ["none"],
                    "handoff_to_coder": ["keep patch minimal"],
                }
            },
        },
        "next_role_index": 1,
        "execution_log": [],
    }

    updated = APP.coordination_commit_node(state)

    assert updated["next_role_index"] == 2
    assert updated["role_outputs"]["coder"] == state["latest_output"]
    assert updated["role_artifacts"]["coder"] == state["latest_artifact"]
    assert updated["shared_memory"]["role_outputs"]["coder"] == state["latest_output"]
    assert (
        updated["shared_memory"]["role_artifacts"]["coder"]
        == state["latest_artifact"]
    )
    assert "coordination: committed output for `coder`" in updated["execution_log"][-1]
