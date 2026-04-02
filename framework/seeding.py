from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from .models import Scenario
from .text_utils import format_kv_section


def validate_seed_payload(seed_payload: dict[str, Any]) -> None:
    validators: dict[str, type | tuple[type, ...]] = {
        "start_role": str,
        "seed_context": dict,
        "seed_role_outputs": dict,
        "seed_role_artifacts": dict,
        "seed_test_run_result": dict,
        "seed_tool_events": list,
        "seed_action_trace": list,
    }
    for key, expected_type in validators.items():
        value = seed_payload.get(key)
        if value is None:
            continue
        if not isinstance(value, expected_type):
            expected_name = (
                expected_type.__name__
                if isinstance(expected_type, type)
                else "/".join(t.__name__ for t in expected_type)
            )
            raise TypeError(f"{key} must be a {expected_name}.")


def build_seed_payload(
    scenario: Scenario,
    seed_payload: dict[str, Any] | None = None,
    start_role: str | None = None,
) -> dict[str, Any]:
    if seed_payload is not None:
        validate_seed_payload(seed_payload)
    merged: dict[str, Any] = {}
    scenario_seed = {
        "start_role": scenario.start_role,
        "seed_context": scenario.seed_context,
        "seed_role_outputs": scenario.seed_role_outputs,
        "seed_role_artifacts": scenario.seed_role_artifacts,
        "seed_test_run_result": scenario.seed_test_run_result,
        "seed_tool_events": scenario.seed_tool_events,
        "seed_action_trace": scenario.seed_action_trace,
    }
    for key, value in scenario_seed.items():
        if value is not None:
            merged[key] = deepcopy(value)

    for key, value in (seed_payload or {}).items():
        if value is not None:
            merged[key] = deepcopy(value)

    if start_role is not None:
        merged["start_role"] = start_role
    return merged


def normalize_seed_role_outputs(
    seed_role_outputs: dict[str, str],
    seed_role_artifacts: dict[str, dict[str, Any]],
    role_order: list[str],
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for role, output in seed_role_outputs.items():
        if role in role_order:
            normalized[role] = str(output)
    for role, artifact in seed_role_artifacts.items():
        if role in role_order and role not in normalized:
            normalized[role] = json.dumps(artifact, indent=2, ensure_ascii=False)
    return normalized


def resolve_start_role_index(
    start_role: str | None,
    seeded_roles: set[str],
    role_order: list[str],
) -> int:
    if start_role is not None:
        if start_role not in role_order:
            raise KeyError(f"Unknown start role: {start_role}")
        return role_order.index(start_role)

    for index, role in enumerate(role_order):
        if role not in seeded_roles:
            return index
    return len(role_order)


def format_seed_context(seed_context: dict[str, Any]) -> str:
    sections: list[str] = []
    for key, value in seed_context.items():
        label = key.replace("_", " ").title()
        if isinstance(value, str):
            body = value
        else:
            body = json.dumps(value, indent=2, ensure_ascii=False)
        sections.append(format_kv_section(label, body))
    return "\n\n".join(section for section in sections if section)
