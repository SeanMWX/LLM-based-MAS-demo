import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from framework import FiveLayerDemo, FiveLayerState
from framework.core import extract_json_object

CASES_PATH = ROOT / "benchmark_cases.json"
ROLE_ORDER = [
    "intake_agent",
    "triage_agent",
    "executor_agent",
    "audit_agent",
]
CATEGORY_OPTIONS = {
    "access_request",
    "onboarding",
    "incident",
    "service_request",
}
PRIORITY_OPTIONS = {
    "low",
    "medium",
    "high",
    "critical",
}
QUEUE_OPTIONS = {
    "service_desk",
    "access_management",
    "onboarding",
    "local_support",
    "escalation",
}
STATUS_OPTIONS = {
    "new",
    "triaged",
    "queued",
    "waiting_human",
    "resolved",
    "escalated",
    "closed",
}

ROLE_OUTPUT_SPECS = {
    "intake_agent": {
        "list_fields": [
            "ticket_summary",
            "extracted_fields",
            "missing_fields",
        ],
        "string_fields": [
            "category",
        ],
        "section_labels": {
            "ticket_summary": "Ticket summary",
            "extracted_fields": "Extracted fields",
            "missing_fields": "Missing fields",
            "category": "Category",
        },
        "role_instruction": (
            "Receive the incoming ICT request, extract key fields, and make an initial classification."
        ),
    },
    "triage_agent": {
        "list_fields": [
            "routing_rationale",
            "required_checks",
        ],
        "string_fields": [
            "priority",
            "target_queue",
        ],
        "section_labels": {
            "routing_rationale": "Routing rationale",
            "required_checks": "Required checks",
            "priority": "Priority",
            "target_queue": "Target queue",
        },
        "role_instruction": (
            "Judge urgency, choose the correct queue, and decide what must be verified before action."
        ),
    },
    "executor_agent": {
        "list_fields": [
            "actions_taken",
            "execution_notes",
        ],
        "string_fields": [
            "status_update",
            "needs_human",
        ],
        "section_labels": {
            "actions_taken": "Actions taken",
            "execution_notes": "Execution notes",
            "status_update": "Status update",
            "needs_human": "Needs human",
        },
        "role_instruction": (
            "Simulate the next operational step such as queueing work, notifying a human, or recording the action taken."
        ),
    },
    "audit_agent": {
        "list_fields": [
            "completeness_check",
            "risks",
        ],
        "string_fields": [
            "final_decision",
        ],
        "section_labels": {
            "completeness_check": "Completeness check",
            "risks": "Risks",
            "final_decision": "Final decision",
        },
        "role_instruction": (
            "Review whether the pipeline is complete, whether escalation is needed, and whether the ticket can be closed."
        ),
    },
}


def empty_artifact_for_role(role: str) -> dict[str, Any]:
    spec = ROLE_OUTPUT_SPECS[role]
    artifact: dict[str, Any] = {}
    for field in spec["list_fields"]:
        artifact[field] = []
    for field in spec["string_fields"]:
        artifact[field] = ""
    return artifact


def dump_artifact(artifact: dict[str, Any]) -> str:
    return json.dumps(artifact, indent=2, ensure_ascii=False)


def build_role_system_prompt(role: str) -> str:
    spec = ROLE_OUTPUT_SPECS[role]
    schema = empty_artifact_for_role(role)
    extra_rules = [
        "Return valid JSON only.",
        "Do not include markdown, code fences, or explanatory text.",
        "Do not add keys outside the schema.",
    ]

    if role == "executor_agent":
        extra_rules.append(
            'Set "needs_human" to exactly one of: "yes", "no".'
        )
        extra_rules.append(
            'Set "status_update" to exactly one of: "new", "triaged", "queued", "waiting_human", "resolved", "escalated", "closed".'
        )
    if role == "audit_agent":
        extra_rules.append(
            'Set "final_decision" to exactly one of: "Close", "Escalate", "Needs info".'
        )
    if role == "intake_agent":
        extra_rules.append(
            'Set "category" to exactly one of: "access_request", "onboarding", "incident", "service_request".'
        )
    if role == "triage_agent":
        extra_rules.append(
            'Set "priority" to exactly one of: "low", "medium", "high", "critical".'
        )
        extra_rules.append(
            'Set "target_queue" to exactly one of: "service_desk", "access_management", "onboarding", "local_support", "escalation".'
        )

    rules = " ".join(extra_rules)
    return (
        f"You are the {role} in a five-layer ICT pipeline MAS. "
        f"{spec['role_instruction']} "
        f"{rules} "
        f"Use exactly this JSON schema:\n{json.dumps(schema, ensure_ascii=False)}"
    )


ROLE_SYSTEM_PROMPTS = {
    role: build_role_system_prompt(role) for role in ROLE_ORDER
}


def strip_list_prefix(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^[-*]\s+", "", text)
    text = re.sub(r"^\d+\.\s+", "", text)
    return text.strip()


def coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            item_text = strip_list_prefix(str(item))
            if item_text:
                items.append(item_text)
        return items

    if isinstance(value, str):
        lines = [strip_list_prefix(line) for line in value.splitlines()]
        lines = [line for line in lines if line]
        if lines:
            return lines
        value = value.strip()
        if not value:
            return []
        return [value]

    if value is None:
        return []

    return [str(value).strip()]


def coerce_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [strip_list_prefix(str(item)) for item in value]
        parts = [part for part in parts if part]
        return "; ".join(parts)
    if value is None:
        return ""
    return str(value).strip()


def normalize_final_decision(value: Any) -> str:
    text = coerce_string(value).lower()
    if "close" in text:
        return "Close"
    if "escalate" in text:
        return "Escalate"
    if "need" in text and "info" in text:
        return "Needs info"
    return "Needs info"


def normalize_yes_no(value: Any) -> str:
    text = coerce_string(value).lower()
    if text in {"yes", "true"}:
        return "yes"
    if text in {"no", "false"}:
        return "no"
    return "yes"


def normalize_category(value: Any) -> str:
    text = coerce_string(value).lower().replace(" ", "_")
    if "access" in text:
        return "access_request"
    if "onboard" in text or "new_hire" in text:
        return "onboarding"
    if "incident" in text or "outage" in text or "printer" in text:
        return "incident"
    if text in CATEGORY_OPTIONS:
        return text
    return "service_request"


def normalize_priority(value: Any) -> str:
    text = coerce_string(value).lower()
    if "critical" in text or "sev1" in text:
        return "critical"
    if "high" in text or "urgent" in text:
        return "high"
    if "low" in text:
        return "low"
    if text in PRIORITY_OPTIONS:
        return text
    return "medium"


def normalize_target_queue(value: Any) -> str:
    text = coerce_string(value).lower().replace(" ", "_")
    if "access" in text or "vpn" in text:
        return "access_management"
    if "onboard" in text:
        return "onboarding"
    if "local" in text or "printer" in text:
        return "local_support"
    if "escalat" in text:
        return "escalation"
    if text in QUEUE_OPTIONS:
        return text
    return "service_desk"


def normalize_status(value: Any) -> str:
    text = coerce_string(value).lower().replace(" ", "_")
    if "wait" in text or "human" in text or "approval" in text:
        return "waiting_human"
    if "escalat" in text:
        return "escalated"
    if "resolve" in text:
        return "resolved"
    if "close" in text:
        return "closed"
    if "queue" in text:
        return "queued"
    if "triage" in text:
        return "triaged"
    if text in STATUS_OPTIONS:
        return text
    return "queued"


def classify_case(state: FiveLayerState) -> dict[str, str]:
    scenario_id = state.get("scenario_id", "")
    if scenario_id == "vpn_access_reset":
        return {
            "category": "access_request",
            "priority": "high",
            "target_queue": "access_management",
            "status_update": "waiting_human",
            "needs_human": "yes",
            "final_decision": "Escalate",
        }
    if scenario_id == "new_hire_access_bundle":
        return {
            "category": "onboarding",
            "priority": "medium",
            "target_queue": "onboarding",
            "status_update": "queued",
            "needs_human": "yes",
            "final_decision": "Escalate",
        }
    return {
        "category": "incident",
        "priority": "high",
        "target_queue": "escalation",
        "status_update": "escalated",
        "needs_human": "yes",
        "final_decision": "Escalate",
    }


def extract_sectioned_fields(role: str, raw_output: str) -> dict[str, str]:
    labels = ROLE_OUTPUT_SPECS[role]["section_labels"]
    lowered_map = {label.lower(): field for field, label in labels.items()}
    sections: dict[str, list[str]] = {field: [] for field in labels}
    current_field: str | None = None

    for raw_line in raw_output.splitlines():
        line = raw_line.strip()
        if not line:
            if current_field is not None:
                sections[current_field].append("")
            continue

        matched_field = None
        for label_lower, field in lowered_map.items():
            prefix = f"{label_lower}:"
            if line.lower().startswith(prefix):
                matched_field = field
                current_field = field
                remainder = line[len(prefix):].strip()
                if remainder:
                    sections[field].append(remainder)
                break

        if matched_field is not None:
            continue

        if current_field is not None:
            sections[current_field].append(line)

    return {
        field: "\n".join(lines).strip()
        for field, lines in sections.items()
        if any(line.strip() for line in lines)
    }


def normalize_role_output(
    role: str,
    raw_output: str,
    _state: FiveLayerState,
) -> tuple[dict[str, Any], str]:
    spec = ROLE_OUTPUT_SPECS[role]
    parsed = extract_json_object(raw_output)
    source = parsed if parsed is not None else extract_sectioned_fields(role, raw_output)

    artifact = empty_artifact_for_role(role)

    for field in spec["list_fields"]:
        artifact[field] = coerce_list(source.get(field))

    for field in spec["string_fields"]:
        artifact[field] = coerce_string(source.get(field))

    if role == "audit_agent":
        artifact["final_decision"] = normalize_final_decision(
            source.get("final_decision")
        )
    if role == "executor_agent":
        artifact["needs_human"] = normalize_yes_no(source.get("needs_human"))
        artifact["status_update"] = normalize_status(source.get("status_update"))
    if role == "intake_agent":
        artifact["category"] = normalize_category(source.get("category"))
    if role == "triage_agent":
        artifact["priority"] = normalize_priority(source.get("priority"))
        artifact["target_queue"] = normalize_target_queue(source.get("target_queue"))

    return artifact, dump_artifact(artifact)


def simulate_role_output(role: str, state: FiveLayerState) -> str:
    case_profile = classify_case(state)
    if role == "intake_agent":
        artifact = {
            "ticket_summary": [
                "Summarize the user request into an ICT ticket.",
                "Capture requester need and likely service area.",
            ],
            "extracted_fields": [
                "request type",
                "business impact",
                "affected service",
            ],
            "missing_fields": [
                "identity verification status",
            ],
            "category": case_profile["category"],
        }
        return dump_artifact(artifact)

    if role == "triage_agent":
        artifact = {
            "routing_rationale": [
                "Assess urgency from business impact.",
                "Route to the queue that owns the requested service.",
            ],
            "required_checks": list(state["risk_notes"]),
            "priority": case_profile["priority"],
            "target_queue": case_profile["target_queue"],
        }
        return dump_artifact(artifact)

    if role == "executor_agent":
        artifact = {
            "actions_taken": [
                "Record the ticket state update.",
                "Queue the task for the owning team or automation.",
            ],
            "execution_notes": [
                "Keep an audit trail of the next operational step.",
            ],
            "status_update": case_profile["status_update"],
            "needs_human": case_profile["needs_human"],
        }
        return dump_artifact(artifact)

    if role == "audit_agent":
        artifact = {
            "completeness_check": [
                "Ticket classification is present.",
                "Routing and next action are recorded.",
                "Risk checks are reflected in the plan.",
            ],
            "risks": list(state["risk_notes"]),
            "final_decision": case_profile["final_decision"],
        }
        return dump_artifact(artifact)

    raise ValueError(f"Unsupported role: {role}")


class ICTPipelineDemo(FiveLayerDemo):
    def resolve_access_mode(
        self,
        scenario,
        repo_path: str | None,
        effective_test_command: str | None,
    ) -> str:
        del scenario, repo_path, effective_test_command
        return "synthetic"

    def resolve_available_tools(
        self,
        scenario,
        repo_access_mode: str,
        repo_path: str | None,
        effective_test_command: str | None,
    ) -> list[str]:
        del repo_access_mode, repo_path, effective_test_command
        return list(scenario.available_tools)


APP = ICTPipelineDemo(
    name="ict_pipeline",
    description="Enterprise ICT ticket-pipeline demo in the five-layer MAS framework.",
    cases_path=CASES_PATH,
    role_order=ROLE_ORDER,
    role_system_prompts=ROLE_SYSTEM_PROMPTS,
    simulate_role_output=simulate_role_output,
    normalize_role_output=normalize_role_output,
)


def main() -> None:
    APP.main()


if __name__ == "__main__":
    main()
