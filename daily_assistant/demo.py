import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from framework import FiveLayerDemo, FiveLayerState, bullet_list
from framework.core import extract_json_object

CASES_PATH = ROOT / "benchmark_cases.json"
EMAIL_THREADS_PATH = ROOT / "email_threads.json"
DRIVE_INDEX_PATH = ROOT / "drive_index.json"
ROLE_ORDER = [
    "intake_router_agent",
    "email_manager_agent",
    "drive_manager_agent",
    "assistant_review_agent",
]
ASSISTANT_PHASE = "email_drive_read_only_draft"
INTENT_TYPE_OPTIONS = {
    "email_only",
    "drive_only",
    "email_and_drive",
    "general_assistant",
}
EMAIL_STATUS_OPTIONS = {
    "not_needed",
    "draft_ready",
    "needs_context",
}
DRIVE_STATUS_OPTIONS = {
    "not_needed",
    "reference_ready",
    "needs_context",
}
FINAL_DECISION_OPTIONS = {
    "Return draft",
    "Needs confirmation",
    "Needs more context",
}

ROLE_OUTPUT_SPECS = {
    "intake_router_agent": {
        "list_fields": [
            "request_summary",
            "routing_plan",
            "constraints",
        ],
        "string_fields": [
            "intent_type",
            "approval_required",
        ],
        "section_labels": {
            "request_summary": "Request summary",
            "routing_plan": "Routing plan",
            "constraints": "Constraints",
            "intent_type": "Intent type",
            "approval_required": "Approval required",
        },
        "role_instruction": (
            "Read the user request, decide whether the work needs email, drive, or both, and capture any approval constraints."
        ),
    },
    "email_manager_agent": {
        "list_fields": [
            "email_findings",
            "draft_replies",
            "followup_items",
            "email_risks",
        ],
        "string_fields": [
            "email_status",
        ],
        "section_labels": {
            "email_findings": "Email findings",
            "draft_replies": "Draft replies",
            "followup_items": "Followup items",
            "email_risks": "Email risks",
            "email_status": "Email status",
        },
        "role_instruction": (
            "Review the relevant email threads, summarize what matters, and draft safe reply text when appropriate."
        ),
    },
    "drive_manager_agent": {
        "list_fields": [
            "file_matches",
            "suggested_file_actions",
            "sharing_risks",
            "missing_documents",
        ],
        "string_fields": [
            "drive_status",
        ],
        "section_labels": {
            "file_matches": "File matches",
            "suggested_file_actions": "Suggested file actions",
            "sharing_risks": "Sharing risks",
            "missing_documents": "Missing documents",
            "drive_status": "Drive status",
        },
        "role_instruction": (
            "Review drive metadata, identify the most relevant files or folders, and suggest safe next actions."
        ),
    },
    "assistant_review_agent": {
        "list_fields": [
            "final_response_plan",
            "permission_check",
            "review_notes",
        ],
        "string_fields": [
            "needs_user_confirmation",
            "final_decision",
        ],
        "section_labels": {
            "final_response_plan": "Final response plan",
            "permission_check": "Permission check",
            "review_notes": "Review notes",
            "needs_user_confirmation": "Needs user confirmation",
            "final_decision": "Final decision",
        },
        "role_instruction": (
            "Review the combined email and drive findings, decide whether the assistant can safely return a draft or whether user confirmation is still needed."
        ),
    },
}


def load_email_threads() -> list[dict[str, Any]]:
    return json.loads(EMAIL_THREADS_PATH.read_text(encoding="utf-8"))


def load_drive_index() -> list[dict[str, Any]]:
    return json.loads(DRIVE_INDEX_PATH.read_text(encoding="utf-8"))


EMAIL_THREADS = load_email_threads()
DRIVE_INDEX = load_drive_index()
EMAIL_THREADS_BY_ID = {thread["id"]: thread for thread in EMAIL_THREADS}
DRIVE_INDEX_BY_ID = {item["id"]: item for item in DRIVE_INDEX}

CASE_PROFILES = {
    "reply_with_latest_quarterly_deck": {
        "intent_type": "email_and_drive",
        "approval_required": "yes",
        "email_status": "draft_ready",
        "drive_status": "reference_ready",
        "needs_user_confirmation": "yes",
        "final_decision": "Needs confirmation",
        "email_thread_ids": ["email_q2_deck_request"],
        "drive_file_ids": ["drive_q2_sales_deck_v5"],
        "permission_check": [
            "Confirm before sending the reply email to an external contact.",
            "Confirm before sharing the latest deck outside the company.",
        ],
    },
    "morning_followup_triage": {
        "intent_type": "email_only",
        "approval_required": "no",
        "email_status": "draft_ready",
        "drive_status": "not_needed",
        "needs_user_confirmation": "no",
        "final_decision": "Return draft",
        "email_thread_ids": [
            "email_invoice_followups",
            "email_budget_review_followup",
        ],
        "drive_file_ids": [],
        "permission_check": [
            "No file-sharing action is needed.",
            "Return drafts only; do not send any message automatically.",
        ],
    },
    "expense_receipt_archive": {
        "intent_type": "email_and_drive",
        "approval_required": "no",
        "email_status": "draft_ready",
        "drive_status": "reference_ready",
        "needs_user_confirmation": "no",
        "final_decision": "Return draft",
        "email_thread_ids": ["email_receipt_submission"],
        "drive_file_ids": ["drive_receipts_2026_march_folder"],
        "permission_check": [
            "Return the suggested archive folder only.",
            "Do not move or share files automatically.",
        ],
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

    if role == "intake_router_agent":
        extra_rules.append(
            'Set "intent_type" to exactly one of: "email_only", "drive_only", "email_and_drive", "general_assistant".'
        )
        extra_rules.append(
            'Set "approval_required" to exactly one of: "yes", "no".'
        )
    if role == "email_manager_agent":
        extra_rules.append(
            'Set "email_status" to exactly one of: "not_needed", "draft_ready", "needs_context".'
        )
    if role == "drive_manager_agent":
        extra_rules.append(
            'Set "drive_status" to exactly one of: "not_needed", "reference_ready", "needs_context".'
        )
    if role == "assistant_review_agent":
        extra_rules.append(
            'Set "needs_user_confirmation" to exactly one of: "yes", "no".'
        )
        extra_rules.append(
            'Set "final_decision" to exactly one of: "Return draft", "Needs confirmation", "Needs more context".'
        )

    return (
        f"You are the {role} in a five-layer daily assistant MAS. "
        f"{spec['role_instruction']} "
        f"{' '.join(extra_rules)} "
        f"Use exactly this JSON schema:\n{json.dumps(schema, ensure_ascii=False)}"
    )


ROLE_SYSTEM_PROMPTS = {
    role: build_role_system_prompt(role) for role in ROLE_ORDER
}


def normalize_search_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


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


def normalize_yes_no(value: Any) -> str:
    text = coerce_string(value).lower()
    if text in {"yes", "true"}:
        return "yes"
    if text in {"no", "false"}:
        return "no"
    return "no"


def normalize_intent_type(value: Any) -> str:
    text = coerce_string(value).lower().replace(" ", "_")
    if "email" in text and "drive" in text:
        return "email_and_drive"
    if "email" in text or "mail" in text or "inbox" in text:
        return "email_only"
    if "drive" in text or "folder" in text or "file" in text:
        return "drive_only"
    if text in INTENT_TYPE_OPTIONS:
        return text
    return "general_assistant"


def normalize_email_status(value: Any) -> str:
    text = coerce_string(value).lower()
    if "draft" in text or "reply" in text:
        return "draft_ready"
    if "context" in text or "missing" in text:
        return "needs_context"
    if text in EMAIL_STATUS_OPTIONS:
        return text
    return "not_needed"


def normalize_drive_status(value: Any) -> str:
    text = coerce_string(value).lower()
    if "reference" in text or "ready" in text or "match" in text:
        return "reference_ready"
    if "context" in text or "missing" in text:
        return "needs_context"
    if text in DRIVE_STATUS_OPTIONS:
        return text
    return "not_needed"


def normalize_final_decision(value: Any) -> str:
    text = coerce_string(value).lower()
    if "confirm" in text:
        return "Needs confirmation"
    if "context" in text or "more" in text:
        return "Needs more context"
    if "draft" in text or "return" in text:
        return "Return draft"
    return "Needs more context"


def score_email_thread(thread: dict[str, Any], query: str) -> int:
    haystack = normalize_search_text(query)
    score = 0
    phrases = [
        thread["subject"],
        thread["summary"],
        thread["sender"],
        " ".join(thread.get("tags", [])),
    ]
    for phrase in phrases:
        normalized_phrase = normalize_search_text(str(phrase))
        if normalized_phrase and normalized_phrase in haystack:
            score += 3

    thread_tokens = set(
        re.findall(
            r"[a-z0-9_]+",
            normalize_search_text(
                " ".join(
                    [
                        thread["subject"],
                        thread["summary"],
                        thread["sender"],
                        " ".join(thread.get("action_items", [])),
                        " ".join(thread.get("tags", [])),
                    ]
                )
            ),
        )
    )
    query_tokens = set(re.findall(r"[a-z0-9_]+", haystack))
    score += len(thread_tokens & query_tokens)
    return score


def score_drive_item(item: dict[str, Any], query: str) -> int:
    haystack = normalize_search_text(query)
    score = 0
    phrases = [
        item["name"],
        item["path"],
        item["description"],
        " ".join(item.get("tags", [])),
    ]
    for phrase in phrases:
        normalized_phrase = normalize_search_text(str(phrase))
        if normalized_phrase and normalized_phrase in haystack:
            score += 3

    item_tokens = set(
        re.findall(
            r"[a-z0-9_]+",
            normalize_search_text(
                " ".join(
                    [
                        item["name"],
                        item["path"],
                        item["description"],
                        " ".join(item.get("tags", [])),
                    ]
                )
            ),
        )
    )
    query_tokens = set(re.findall(r"[a-z0-9_]+", haystack))
    score += len(item_tokens & query_tokens)
    return score


def search_email_threads(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    scored_results: list[tuple[int, dict[str, Any]]] = []
    for thread in EMAIL_THREADS:
        score = score_email_thread(thread, query)
        if score > 0:
            scored_results.append((score, thread))

    scored_results.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [
        {
            "id": thread["id"],
            "subject": thread["subject"],
            "sender": thread["sender"],
            "summary": thread["summary"],
            "action_items": list(thread["action_items"]),
            "reply_hint": thread["reply_hint"],
            "sensitivity": thread["sensitivity"],
            "score": score,
        }
        for score, thread in scored_results[:top_k]
    ]


def search_drive_files(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    scored_results: list[tuple[int, dict[str, Any]]] = []
    for item in DRIVE_INDEX:
        score = score_drive_item(item, query)
        if score > 0:
            scored_results.append((score, item))

    scored_results.sort(key=lambda entry: (-entry[0], entry[1]["id"]))
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "path": item["path"],
            "description": item["description"],
            "updated_at": item["updated_at"],
            "sharing_notes": item["sharing_notes"],
            "score": score,
        }
        for score, item in scored_results[:top_k]
    ]


def resolve_email_matches_for_state(
    state: FiveLayerState,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    profile = CASE_PROFILES.get(state.get("scenario_id", ""), {})
    if profile.get("intent_type") == "drive_only":
        return []

    query = "\n".join(
        [
            state.get("task", ""),
            state.get("repository_context", ""),
            *state.get("acceptance_criteria", []),
        ]
    )
    matches = search_email_threads(query, top_k=top_k)
    preferred_ids = CASE_PROFILES.get(state.get("scenario_id", ""), {}).get(
        "email_thread_ids",
        [],
    )
    if not preferred_ids:
        return matches
    return [
        next(
            (match for match in matches if match["id"] == thread_id),
            {
                "id": thread["id"],
                "subject": thread["subject"],
                "sender": thread["sender"],
                "summary": thread["summary"],
                "action_items": list(thread["action_items"]),
                "reply_hint": thread["reply_hint"],
                "sensitivity": thread["sensitivity"],
                "score": 0,
            },
        )
        for thread_id in preferred_ids
        for thread in [EMAIL_THREADS_BY_ID[thread_id]]
    ][:top_k]


def resolve_drive_matches_for_state(
    state: FiveLayerState,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    profile = CASE_PROFILES.get(state.get("scenario_id", ""), {})
    if profile.get("intent_type") == "email_only":
        return []

    query = "\n".join(
        [
            state.get("task", ""),
            state.get("repository_context", ""),
            *state.get("acceptance_criteria", []),
        ]
    )
    matches = search_drive_files(query, top_k=top_k)
    preferred_ids = CASE_PROFILES.get(state.get("scenario_id", ""), {}).get(
        "drive_file_ids",
        [],
    )
    if not preferred_ids:
        return matches
    return [
        next(
            (match for match in matches if match["id"] == file_id),
            {
                "id": item["id"],
                "name": item["name"],
                "path": item["path"],
                "description": item["description"],
                "updated_at": item["updated_at"],
                "sharing_notes": item["sharing_notes"],
                "score": 0,
            },
        )
        for file_id in preferred_ids
        for item in [DRIVE_INDEX_BY_ID[file_id]]
    ][:top_k]


def format_email_matches_for_brief(matches: list[dict[str, Any]]) -> str:
    if not matches:
        return "(no email matches)"
    lines = [
        (
            f"{match['id']} | sender={match['sender']} | subject={match['subject']} | "
            f"summary={match['summary']}"
        )
        for match in matches
    ]
    return bullet_list(lines)


def format_drive_matches_for_brief(matches: list[dict[str, Any]]) -> str:
    if not matches:
        return "(no drive matches)"
    lines = [
        (
            f"{match['id']} | name={match['name']} | path={match['path']} | "
            f"updated_at={match['updated_at']} | description={match['description']}"
        )
        for match in matches
    ]
    return bullet_list(lines)


def build_case_profile(state: FiveLayerState) -> dict[str, Any]:
    scenario_id = state.get("scenario_id", "")
    profile = dict(
        CASE_PROFILES.get(
            scenario_id,
            {
                "intent_type": "general_assistant",
                "approval_required": "no",
                "email_status": "not_needed",
                "drive_status": "not_needed",
                "needs_user_confirmation": "no",
                "final_decision": "Needs more context",
                "email_thread_ids": [],
                "drive_file_ids": [],
                "permission_check": [
                    "Return findings only.",
                ],
            },
        )
    )

    email_matches = resolve_email_matches_for_state(state, top_k=3)
    drive_matches = resolve_drive_matches_for_state(state, top_k=3)
    profile["email_matches"] = email_matches
    profile["drive_matches"] = drive_matches
    profile["request_summary"] = [
        "Interpret the user request as a daily-assistant task.",
        "Collect only the email and drive references needed for a safe draft response.",
    ]
    profile["routing_plan"] = [
        f"Consult email_manager_agent: {'yes' if email_matches else 'no'}",
        f"Consult drive_manager_agent: {'yes' if drive_matches else 'no'}",
        "Return a draft or recommendation instead of performing external actions.",
    ]
    profile["constraints"] = list(state.get("risk_notes", []))
    profile["email_findings"] = [
        f"{match['subject']} from {match['sender']}: {match['summary']}"
        for match in email_matches
    ]
    profile["draft_replies"] = [
        match["reply_hint"]
        for match in email_matches
    ]
    profile["followup_items"] = [
        item
        for match in email_matches
        for item in match["action_items"]
    ]
    profile["email_risks"] = [
        f"{match['id']} sensitivity={match['sensitivity']}"
        for match in email_matches
        if match["sensitivity"] != "standard"
    ] or ["No special email risk identified beyond user confirmation rules."]
    profile["file_matches"] = [
        f"{match['name']} ({match['path']})"
        for match in drive_matches
    ]
    profile["suggested_file_actions"] = [
        (
            f"Reference {match['name']} from {match['path']}"
            if scenario_id != "expense_receipt_archive"
            else f"Suggest archiving into {match['path']}"
        )
        for match in drive_matches
    ]
    profile["sharing_risks"] = [
        f"{match['id']}: {match['sharing_notes']}"
        for match in drive_matches
        if "confirm" in match["sharing_notes"].lower()
        or "internal" in match["sharing_notes"].lower()
    ] or ["No additional drive-sharing risk identified."]
    profile["missing_documents"] = (
        []
        if drive_matches or profile["drive_status"] == "not_needed"
        else ["No matching drive file or folder was found."]
    )
    profile["final_response_plan"] = [
        "Return a concise response plan for the user.",
        "Keep all email and drive actions in read-only or draft mode.",
    ]
    profile["review_notes"] = [
        "Daily assistant Phase 1 is draft-only and does not send mail or move files.",
        "User confirmation is still required for any future send or share action.",
    ]
    return profile


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

    if role == "intake_router_agent":
        artifact["intent_type"] = normalize_intent_type(source.get("intent_type"))
        artifact["approval_required"] = normalize_yes_no(
            source.get("approval_required")
        )
    if role == "email_manager_agent":
        artifact["email_status"] = normalize_email_status(source.get("email_status"))
    if role == "drive_manager_agent":
        artifact["drive_status"] = normalize_drive_status(source.get("drive_status"))
    if role == "assistant_review_agent":
        artifact["needs_user_confirmation"] = normalize_yes_no(
            source.get("needs_user_confirmation")
        )
        artifact["final_decision"] = normalize_final_decision(
            source.get("final_decision")
        )

    return artifact, dump_artifact(artifact)


def simulate_role_output(role: str, state: FiveLayerState) -> str:
    profile = build_case_profile(state)
    if role == "intake_router_agent":
        artifact = {
            "request_summary": profile["request_summary"],
            "routing_plan": profile["routing_plan"],
            "constraints": profile["constraints"],
            "intent_type": profile["intent_type"],
            "approval_required": profile["approval_required"],
        }
        return dump_artifact(artifact)

    if role == "email_manager_agent":
        artifact = {
            "email_findings": profile["email_findings"],
            "draft_replies": profile["draft_replies"],
            "followup_items": profile["followup_items"],
            "email_risks": profile["email_risks"],
            "email_status": profile["email_status"],
        }
        return dump_artifact(artifact)

    if role == "drive_manager_agent":
        artifact = {
            "file_matches": profile["file_matches"],
            "suggested_file_actions": profile["suggested_file_actions"],
            "sharing_risks": profile["sharing_risks"],
            "missing_documents": profile["missing_documents"],
            "drive_status": profile["drive_status"],
        }
        return dump_artifact(artifact)

    if role == "assistant_review_agent":
        artifact = {
            "final_response_plan": profile["final_response_plan"],
            "permission_check": profile["permission_check"],
            "review_notes": profile["review_notes"],
            "needs_user_confirmation": profile["needs_user_confirmation"],
            "final_decision": profile["final_decision"],
        }
        return dump_artifact(artifact)

    raise ValueError(f"Unsupported role: {role}")


class DailyAssistantDemo(FiveLayerDemo):
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
        tools = list(scenario.available_tools)
        for tool in [
            "search_email",
            "read_email_thread",
            "draft_reply",
            "search_drive",
            "read_drive_metadata",
            "suggest_drive_action",
        ]:
            if tool not in tools:
                tools.append(tool)
        return tools

    def extend_perception_observations(
        self,
        state: FiveLayerState,
        repo_snapshot: dict[str, Any],
        read_only_files: list[dict[str, str]],
    ) -> list[str]:
        del repo_snapshot, read_only_files
        email_matches = resolve_email_matches_for_state(state, top_k=3)
        drive_matches = resolve_drive_matches_for_state(state, top_k=3)
        return [
            f"Assistant phase: {ASSISTANT_PHASE}",
            f"Email thread count: {len(EMAIL_THREADS)}",
            f"Drive item count: {len(DRIVE_INDEX)}",
            f"Email candidate ids: {', '.join(match['id'] for match in email_matches) or '(none)'}",
            f"Drive candidate ids: {', '.join(match['id'] for match in drive_matches) or '(none)'}",
        ]

    def extend_shared_memory(
        self,
        state: FiveLayerState,
    ) -> dict[str, Any]:
        email_matches = resolve_email_matches_for_state(state, top_k=3)
        drive_matches = resolve_drive_matches_for_state(state, top_k=3)
        return {
            "assistant_phase": ASSISTANT_PHASE,
            "email_matches": email_matches,
            "drive_matches": drive_matches,
        }

    def extend_brief_sections(
        self,
        role: str,
        state: FiveLayerState,
    ) -> list[str]:
        email_matches = resolve_email_matches_for_state(state, top_k=3)
        drive_matches = resolve_drive_matches_for_state(state, top_k=3)
        sections: list[str] = []

        if role in {"email_manager_agent", "assistant_review_agent"}:
            sections.append(
                f"Relevant email threads:\n{format_email_matches_for_brief(email_matches)}"
            )
        if role in {"drive_manager_agent", "assistant_review_agent"}:
            sections.append(
                f"Relevant drive items:\n{format_drive_matches_for_brief(drive_matches)}"
            )
        if role == "assistant_review_agent":
            sections.append(
                "Phase-1 safety rule:\n"
                + bullet_list(
                    [
                        "Return drafts, summaries, or suggestions only.",
                        "Do not send email, move files, or share drive links automatically.",
                    ]
                )
            )
        return sections

    def summarize_state(self, state: FiveLayerState) -> dict[str, Any]:
        summary = super().summarize_state(state)
        summary["assistant_phase"] = ASSISTANT_PHASE
        summary["email_matches"] = list(
            state.get(
                "shared_memory",
                {},
            ).get("email_matches", [])
        )
        summary["drive_matches"] = list(
            state.get(
                "shared_memory",
                {},
            ).get("drive_matches", [])
        )
        return summary


APP = DailyAssistantDemo(
    name="daily_assistant",
    description="Daily assistant demo for email and drive workflows in the five-layer MAS framework.",
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
