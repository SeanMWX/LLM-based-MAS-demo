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
POLICY_RULES_PATH = ROOT / "policy_rules.json"
SANDBOX_ADAPTERS_PATH = ROOT / "sandbox_adapters.json"
ROLE_ORDER = [
    "intake_router_agent",
    "email_manager_agent",
    "drive_manager_agent",
    "assistant_review_agent",
]
ASSISTANT_PHASE = "email_drive_policy_confirmation_queue_action_log_sandbox_adapters"
POLICY_PHASE = "policy_kb_confirmation_gating"
QUEUE_PHASE = "confirmation_queue_action_log"
ADAPTER_PHASE = "sandboxed_mail_drive_adapters"
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
SAFE_ACTION_MODE_OPTIONS = {
    "draft_only",
    "confirm_required",
    "needs_context",
}
QUEUE_STATUS_OPTIONS = {
    "empty",
    "pending_confirmation",
    "ready_for_user",
}
ACTION_LOG_VERDICT_OPTIONS = {
    "recorded",
    "needs_followup",
    "insufficient_evidence",
}
ADAPTER_VERDICT_OPTIONS = {
    "staged",
    "awaiting_confirmation",
    "missing_receipts",
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
            "policy_flags",
            "proposed_email_actions",
            "email_receipt_ids",
            "sandbox_email_receipts",
        ],
        "string_fields": [
            "email_status",
        ],
        "section_labels": {
            "email_findings": "Email findings",
            "draft_replies": "Draft replies",
            "followup_items": "Followup items",
            "email_risks": "Email risks",
            "policy_flags": "Policy flags",
            "proposed_email_actions": "Proposed email actions",
            "email_receipt_ids": "Email receipt ids",
            "sandbox_email_receipts": "Sandbox email receipts",
            "email_status": "Email status",
        },
        "role_instruction": (
            "Review the relevant email threads, summarize what matters, draft safe reply text when appropriate, and call out policy constraints."
        ),
    },
    "drive_manager_agent": {
        "list_fields": [
            "file_matches",
            "suggested_file_actions",
            "sharing_risks",
            "missing_documents",
            "sharing_requirements",
            "proposed_drive_actions",
            "drive_receipt_ids",
            "sandbox_drive_receipts",
        ],
        "string_fields": [
            "drive_status",
        ],
        "section_labels": {
            "file_matches": "File matches",
            "suggested_file_actions": "Suggested file actions",
            "sharing_risks": "Sharing risks",
            "missing_documents": "Missing documents",
            "sharing_requirements": "Sharing requirements",
            "proposed_drive_actions": "Proposed drive actions",
            "drive_receipt_ids": "Drive receipt ids",
            "sandbox_drive_receipts": "Sandbox drive receipts",
            "drive_status": "Drive status",
        },
        "role_instruction": (
            "Review drive metadata, identify the most relevant files or folders, suggest safe next actions, and capture file-handling requirements."
        ),
    },
    "assistant_review_agent": {
        "list_fields": [
            "final_response_plan",
            "permission_check",
            "review_notes",
            "policy_evidence_review",
            "confirmation_queue_review",
            "action_log_review",
            "adapter_evidence_review",
        ],
        "string_fields": [
            "safe_action_mode",
            "queue_status",
            "action_log_verdict",
            "adapter_verdict",
            "needs_user_confirmation",
            "final_decision",
        ],
        "section_labels": {
            "final_response_plan": "Final response plan",
            "permission_check": "Permission check",
            "review_notes": "Review notes",
            "policy_evidence_review": "Policy evidence review",
            "confirmation_queue_review": "Confirmation queue review",
            "action_log_review": "Action log review",
            "adapter_evidence_review": "Adapter evidence review",
            "safe_action_mode": "Safe action mode",
            "queue_status": "Queue status",
            "action_log_verdict": "Action log verdict",
            "adapter_verdict": "Adapter verdict",
            "needs_user_confirmation": "Needs user confirmation",
            "final_decision": "Final decision",
        },
        "role_instruction": (
            "Review the combined email, drive, policy, queue, and sandbox-adapter findings, decide whether the assistant can safely return a draft, and determine whether explicit user confirmation is still needed."
        ),
    },
}


def load_email_threads() -> list[dict[str, Any]]:
    return json.loads(EMAIL_THREADS_PATH.read_text(encoding="utf-8"))


def load_drive_index() -> list[dict[str, Any]]:
    return json.loads(DRIVE_INDEX_PATH.read_text(encoding="utf-8"))


def load_policy_rules() -> list[dict[str, Any]]:
    return json.loads(POLICY_RULES_PATH.read_text(encoding="utf-8"))


def load_sandbox_adapters() -> list[dict[str, Any]]:
    return json.loads(SANDBOX_ADAPTERS_PATH.read_text(encoding="utf-8"))


EMAIL_THREADS = load_email_threads()
DRIVE_INDEX = load_drive_index()
POLICY_RULES = load_policy_rules()
SANDBOX_ADAPTERS = load_sandbox_adapters()
EMAIL_THREADS_BY_ID = {thread["id"]: thread for thread in EMAIL_THREADS}
DRIVE_INDEX_BY_ID = {item["id"]: item for item in DRIVE_INDEX}
POLICY_RULES_BY_ID = {rule["id"]: rule for rule in POLICY_RULES}
SANDBOX_ADAPTERS_BY_ID = {adapter["id"]: adapter for adapter in SANDBOX_ADAPTERS}
SANDBOX_ADAPTERS_BY_DOMAIN = {
    adapter["domain"]: adapter for adapter in SANDBOX_ADAPTERS
}

CASE_PROFILES = {
    "reply_with_latest_quarterly_deck": {
        "intent_type": "email_and_drive",
        "approval_required": "yes",
        "email_status": "draft_ready",
        "drive_status": "reference_ready",
        "safe_action_mode": "confirm_required",
        "needs_user_confirmation": "yes",
        "final_decision": "Needs confirmation",
        "email_thread_ids": ["email_q2_deck_request"],
        "drive_file_ids": ["drive_q2_sales_deck_v5"],
        "policy_rule_ids": [
            "policy_draft_only_default",
            "policy_external_email_confirmation",
            "policy_external_file_sharing_confirmation",
        ],
        "email_action_specs": [
            {
                "action": "prepare_external_reply_draft",
                "target": "alex@partner-example.com",
                "requires_confirmation": True,
                "reason": "external_recipient_send",
            }
        ],
        "drive_action_specs": [
            {
                "action": "prepare_external_file_reference",
                "target": "drive_q2_sales_deck_v5",
                "requires_confirmation": True,
                "reason": "external_file_sharing",
            }
        ],
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
        "safe_action_mode": "draft_only",
        "needs_user_confirmation": "no",
        "final_decision": "Return draft",
        "email_thread_ids": [
            "email_invoice_followups",
            "email_budget_review_followup",
        ],
        "drive_file_ids": [],
        "policy_rule_ids": [
            "policy_draft_only_default",
            "policy_internal_reply_review",
        ],
        "email_action_specs": [
            {
                "action": "prepare_reply_draft",
                "target": "email_invoice_followups",
                "requires_confirmation": False,
                "reason": "draft_only_review",
            },
            {
                "action": "prepare_reply_draft",
                "target": "email_budget_review_followup",
                "requires_confirmation": False,
                "reason": "draft_only_review",
            }
        ],
        "drive_action_specs": [],
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
        "safe_action_mode": "draft_only",
        "needs_user_confirmation": "no",
        "final_decision": "Return draft",
        "email_thread_ids": ["email_receipt_submission"],
        "drive_file_ids": ["drive_receipts_2026_march_folder"],
        "policy_rule_ids": [
            "policy_draft_only_default",
            "policy_finance_archive_reference_only",
        ],
        "email_action_specs": [
            {
                "action": "prepare_acknowledgement_draft",
                "target": "email_receipt_submission",
                "requires_confirmation": False,
                "reason": "draft_only_review",
            }
        ],
        "drive_action_specs": [
            {
                "action": "suggest_archive_location",
                "target": "drive_receipts_2026_march_folder",
                "requires_confirmation": False,
                "reason": "reference_only_archive",
            }
        ],
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
            'Set "safe_action_mode" to exactly one of: "draft_only", "confirm_required", "needs_context".'
        )
        extra_rules.append(
            'Set "queue_status" to exactly one of: "empty", "pending_confirmation", "ready_for_user".'
        )
        extra_rules.append(
            'Set "action_log_verdict" to exactly one of: "recorded", "needs_followup", "insufficient_evidence".'
        )
        extra_rules.append(
            'Set "adapter_verdict" to exactly one of: "staged", "awaiting_confirmation", "missing_receipts".'
        )
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


def normalize_safe_action_mode(value: Any) -> str:
    text = coerce_string(value).lower().replace(" ", "_")
    if "confirm" in text:
        return "confirm_required"
    if "context" in text or "missing" in text:
        return "needs_context"
    if "draft" in text or "readonly" in text or "read_only" in text:
        return "draft_only"
    if text in SAFE_ACTION_MODE_OPTIONS:
        return text
    return "needs_context"


def normalize_queue_status(value: Any) -> str:
    text = coerce_string(value).lower().replace(" ", "_")
    if "pending" in text or "confirm" in text:
        return "pending_confirmation"
    if "ready" in text:
        return "ready_for_user"
    if "empty" in text or "none" in text:
        return "empty"
    if text in QUEUE_STATUS_OPTIONS:
        return text
    return "empty"


def normalize_action_log_verdict(value: Any) -> str:
    text = coerce_string(value).lower().replace(" ", "_")
    if "follow" in text:
        return "needs_followup"
    if "insufficient" in text or "missing" in text:
        return "insufficient_evidence"
    if "record" in text or "ok" in text or "ready" in text:
        return "recorded"
    if text in ACTION_LOG_VERDICT_OPTIONS:
        return text
    return "insufficient_evidence"


def normalize_adapter_verdict(value: Any) -> str:
    text = coerce_string(value).lower().replace(" ", "_")
    if "await" in text or "confirm" in text or "pending" in text:
        return "awaiting_confirmation"
    if "missing" in text or "receipt" in text or "evidence" in text:
        return "missing_receipts"
    if "staged" in text or "ready" in text or "adapter" in text:
        return "staged"
    if text in ADAPTER_VERDICT_OPTIONS:
        return text
    return "missing_receipts"


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


def score_policy_rule(rule: dict[str, Any], query: str) -> int:
    haystack = normalize_search_text(query)
    score = 0
    phrases = [
        rule["title"],
        rule["summary"],
        " ".join(rule.get("tags", [])),
    ]
    for phrase in phrases:
        normalized_phrase = normalize_search_text(str(phrase))
        if normalized_phrase and normalized_phrase in haystack:
            score += 3

    rule_tokens = set(
        re.findall(
            r"[a-z0-9_]+",
            normalize_search_text(
                " ".join(
                    [
                        rule["title"],
                        rule["summary"],
                        " ".join(rule.get("requirements", [])),
                        " ".join(rule.get("tags", [])),
                    ]
                )
            ),
        )
    )
    query_tokens = set(re.findall(r"[a-z0-9_]+", haystack))
    score += len(rule_tokens & query_tokens)
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


def search_policy_rules(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    scored_results: list[tuple[int, dict[str, Any]]] = []
    for rule in POLICY_RULES:
        score = score_policy_rule(rule, query)
        if score > 0:
            scored_results.append((score, rule))

    scored_results.sort(key=lambda entry: (-entry[0], entry[1]["id"]))
    return [
        {
            "id": rule["id"],
            "title": rule["title"],
            "summary": rule["summary"],
            "requirements": list(rule["requirements"]),
            "tags": list(rule.get("tags", [])),
            "score": score,
        }
        for score, rule in scored_results[:top_k]
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


def resolve_policy_matches_for_state(
    state: FiveLayerState,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    query = "\n".join(
        [
            state.get("task", ""),
            state.get("repository_context", ""),
            *state.get("acceptance_criteria", []),
            *state.get("risk_notes", []),
        ]
    )
    matches = search_policy_rules(query, top_k=top_k)
    preferred_ids = CASE_PROFILES.get(state.get("scenario_id", ""), {}).get(
        "policy_rule_ids",
        [],
    )
    if not preferred_ids:
        return matches
    return [
        next(
            (match for match in matches if match["id"] == rule_id),
            {
                "id": rule["id"],
                "title": rule["title"],
                "summary": rule["summary"],
                "requirements": list(rule["requirements"]),
                "tags": list(rule.get("tags", [])),
                "score": 0,
            },
        )
        for rule_id in preferred_ids
        for rule in [POLICY_RULES_BY_ID[rule_id]]
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


def format_policy_matches_for_brief(matches: list[dict[str, Any]]) -> str:
    if not matches:
        return "(no policy matches)"
    lines = [
        (
            f"{match['id']} | title={match['title']} | "
            f"summary={match['summary']}"
        )
        for match in matches
    ]
    return bullet_list(lines)


def format_assistant_action_log(entries: list[str]) -> str:
    if not entries:
        return "(no action-log entries)"
    return bullet_list(entries)


def format_confirmation_queue(queue: list[dict[str, Any]]) -> str:
    if not queue:
        return "(no pending confirmations)"
    lines = [
        (
            f"{item['id']} | action={item['requested_action']} | "
            f"target={item['target']} | status={item['status']} | reason={item['reason']}"
        )
        for item in queue
    ]
    return bullet_list(lines)


def format_sandbox_adapters_for_brief(adapters: list[dict[str, Any]]) -> str:
    if not adapters:
        return "(no sandbox adapters)"
    lines = [
        (
            f"{adapter['id']} | domain={adapter['domain']} | "
            f"mode={adapter['mode']} | summary={adapter['summary']}"
        )
        for adapter in adapters
    ]
    return bullet_list(lines)


def format_sandbox_records(records: list[dict[str, Any]]) -> str:
    if not records:
        return "(no sandbox adapter records)"
    lines = [
        (
            f"{record['id']} | adapter={record['adapter_id']} | "
            f"action={record['action']} | target={record['target']} | "
            f"status={record['status']}"
        )
        for record in records
    ]
    return bullet_list(lines)


def format_sandbox_receipts(receipts: dict[str, dict[str, Any]]) -> str:
    if not receipts:
        return "(no sandbox receipts)"
    lines = [
        (
            f"{receipt_id} | adapter={payload['adapter_id']} | "
            f"status={payload['status']} | target={payload['target']}"
        )
        for receipt_id, payload in sorted(receipts.items())
    ]
    return bullet_list(lines)


def build_receipt_id(
    state: FiveLayerState,
    role: str,
    index: int,
) -> str:
    return f"asst_rcpt_{state.get('scenario_id', 'scenario')}_{role}_{index}"


def build_confirmation_request_id(
    state: FiveLayerState,
    role: str,
    index: int,
) -> str:
    return f"confirm_{state.get('scenario_id', 'scenario')}_{role}_{index}"


def build_sandbox_receipt_id(
    state: FiveLayerState,
    channel: str,
    index: int,
) -> str:
    return f"sbox_{state.get('scenario_id', 'scenario')}_{channel}_{index}"


def build_assistant_execution_evidence(
    action_log: list[str],
    confirmation_queue: list[dict[str, Any]],
    receipts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "action_log_count": len(action_log),
        "confirmation_queue_count": len(confirmation_queue),
        "receipt_count": len(receipts),
        "queue_status": (
            "pending_confirmation" if confirmation_queue else "empty"
        ),
        "action_log_verdict": (
            "recorded" if action_log else "insufficient_evidence"
        ),
    }


def build_sandbox_execution_summary(
    mail_records: list[dict[str, Any]],
    drive_records: list[dict[str, Any]],
    receipts: dict[str, dict[str, Any]],
    confirmation_queue: list[dict[str, Any]],
) -> dict[str, Any]:
    total_records = len(mail_records) + len(drive_records)
    if not total_records and not receipts:
        adapter_verdict = "staged"
    elif total_records and not receipts:
        adapter_verdict = "missing_receipts"
    elif confirmation_queue:
        adapter_verdict = "awaiting_confirmation"
    elif receipts:
        adapter_verdict = "staged"
    else:
        adapter_verdict = "missing_receipts"

    return {
        "mail_record_count": len(mail_records),
        "drive_record_count": len(drive_records),
        "receipt_count": len(receipts),
        "adapter_verdict": adapter_verdict,
        "awaiting_confirmation_count": len(confirmation_queue),
    }


def build_role_action_updates(
    role: str,
    state: FiveLayerState,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    profile = build_case_profile(state)
    action_specs = profile.get(
        "email_action_specs" if role == "email_manager_agent" else "drive_action_specs",
        [],
    )
    action_log = list(state.get("assistant_action_log", []))
    receipts = dict(state.get("assistant_receipts", {}))
    confirmation_queue = list(state.get("confirmation_queue", []))
    sandbox_mail_records = list(state.get("sandbox_mail_records", []))
    sandbox_drive_records = list(state.get("sandbox_drive_records", []))
    sandbox_adapter_receipts = dict(state.get("sandbox_adapter_receipts", {}))
    trace_events: list[dict[str, Any]] = []
    receipt_ids: list[str] = []
    channel = "email" if role == "email_manager_agent" else "drive"
    adapter = SANDBOX_ADAPTERS_BY_DOMAIN[channel]

    for spec in action_specs:
        step = len(action_log) + 1
        receipt_id = build_receipt_id(state, role, step)
        receipt_ids.append(receipt_id)
        action_log.append(
            " | ".join(
                [
                    f"step={step}",
                    f"role={role}",
                    f"action={spec['action']}",
                    f"target={spec['target']}",
                    f"receipt={receipt_id}",
                ]
            )
        )
        receipts[receipt_id] = {
            "role": role,
            "action": spec["action"],
            "target": spec["target"],
            "reason": spec["reason"],
        }
        trace_events.append(
            {
                "event": "assistant_action_recorded",
                "role": role,
                "summary": f"{spec['action']} -> {spec['target']}",
            }
        )
        if spec.get("requires_confirmation"):
            request_id = build_confirmation_request_id(
                state,
                role,
                len(confirmation_queue) + 1,
            )
            confirmation_queue.append(
                {
                    "id": request_id,
                    "source_role": role,
                    "requested_action": spec["action"],
                    "target": spec["target"],
                    "reason": spec["reason"],
                    "status": "pending",
                }
            )
            trace_events.append(
                {
                    "event": "confirmation_enqueued",
                    "role": role,
                    "summary": f"{request_id} pending for {spec['action']}",
                }
            )

        sandbox_index = len(sandbox_mail_records) + len(sandbox_drive_records) + 1
        sandbox_receipt_id = build_sandbox_receipt_id(state, channel, sandbox_index)
        sandbox_record = {
            "id": sandbox_receipt_id,
            "adapter_id": adapter["id"],
            "channel": channel,
            "source_role": role,
            "action": spec["action"],
            "target": spec["target"],
            "reason": spec["reason"],
            "status": (
                "awaiting_confirmation"
                if spec.get("requires_confirmation")
                else "staged"
            ),
        }
        if channel == "email":
            sandbox_mail_records.append(sandbox_record)
        else:
            sandbox_drive_records.append(sandbox_record)
        sandbox_adapter_receipts[sandbox_receipt_id] = dict(sandbox_record)
        trace_events.append(
            {
                "event": "sandbox_adapter_staged",
                "role": role,
                "summary": (
                    f"{adapter['id']} staged {spec['action']} -> {spec['target']}"
                ),
            }
        )

    evidence = build_assistant_execution_evidence(
        action_log=action_log,
        confirmation_queue=confirmation_queue,
        receipts=receipts,
    )
    sandbox_summary = build_sandbox_execution_summary(
        mail_records=sandbox_mail_records,
        drive_records=sandbox_drive_records,
        receipts=sandbox_adapter_receipts,
        confirmation_queue=confirmation_queue,
    )
    return (
        {
            "assistant_action_log": action_log,
            "assistant_receipts": receipts,
            "confirmation_queue": confirmation_queue,
            "assistant_execution_evidence": evidence,
            "sandbox_mail_records": sandbox_mail_records,
            "sandbox_drive_records": sandbox_drive_records,
            "sandbox_adapter_receipts": sandbox_adapter_receipts,
            "sandbox_execution_summary": sandbox_summary,
        },
        trace_events,
    )


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
                "safe_action_mode": "needs_context",
                "needs_user_confirmation": "no",
                "final_decision": "Needs more context",
                "email_thread_ids": [],
                "drive_file_ids": [],
                "policy_rule_ids": [],
                "email_action_specs": [],
                "drive_action_specs": [],
                "permission_check": [
                    "Return findings only.",
                ],
            },
        )
    )

    email_matches = resolve_email_matches_for_state(state, top_k=3)
    drive_matches = resolve_drive_matches_for_state(state, top_k=3)
    policy_matches = resolve_policy_matches_for_state(state, top_k=3)
    profile["email_matches"] = email_matches
    profile["drive_matches"] = drive_matches
    profile["policy_matches"] = policy_matches
    shared_memory = state.get("shared_memory", {})
    profile["assistant_action_log"] = list(
        state.get("assistant_action_log", shared_memory.get("assistant_action_log", []))
    )
    profile["assistant_receipts"] = dict(
        state.get("assistant_receipts", shared_memory.get("assistant_receipts", {}))
    )
    profile["confirmation_queue"] = list(
        state.get("confirmation_queue", shared_memory.get("confirmation_queue", []))
    )
    profile["assistant_execution_evidence"] = dict(
        state.get(
            "assistant_execution_evidence",
            shared_memory.get("assistant_execution_evidence", {}),
        )
    )
    profile["sandbox_mail_records"] = list(
        state.get("sandbox_mail_records", shared_memory.get("sandbox_mail_records", []))
    )
    profile["sandbox_drive_records"] = list(
        state.get(
            "sandbox_drive_records",
            shared_memory.get("sandbox_drive_records", []),
        )
    )
    profile["sandbox_adapter_receipts"] = dict(
        state.get(
            "sandbox_adapter_receipts",
            shared_memory.get("sandbox_adapter_receipts", {}),
        )
    )
    profile["sandbox_execution_summary"] = dict(
        state.get(
            "sandbox_execution_summary",
            shared_memory.get("sandbox_execution_summary", {}),
        )
    )
    email_action_specs = profile.get("email_action_specs", [])
    drive_action_specs = profile.get("drive_action_specs", [])
    profile["proposed_email_actions"] = [
        f"{spec['action']} -> {spec['target']}" for spec in email_action_specs
    ]
    profile["email_receipt_ids"] = [
        build_receipt_id(state, "email_manager_agent", index)
        for index, _spec in enumerate(email_action_specs, start=1)
    ]
    profile["proposed_drive_actions"] = [
        f"{spec['action']} -> {spec['target']}" for spec in drive_action_specs
    ]
    profile["drive_receipt_ids"] = [
        build_receipt_id(
            state,
            "drive_manager_agent",
            len(email_action_specs) + index,
        )
        for index, _spec in enumerate(drive_action_specs, start=1)
    ]
    profile["sandbox_email_receipts"] = [
        build_sandbox_receipt_id(state, "email", index)
        for index, _spec in enumerate(email_action_specs, start=1)
    ]
    profile["sandbox_drive_receipts"] = [
        build_sandbox_receipt_id(
            state,
            "drive",
            len(email_action_specs) + index,
        )
        for index, _spec in enumerate(drive_action_specs, start=1)
    ]
    profile["sandbox_adapter_manifests"] = [
        SANDBOX_ADAPTERS_BY_DOMAIN["email"],
        SANDBOX_ADAPTERS_BY_DOMAIN["drive"],
    ]
    profile["request_summary"] = [
        "Interpret the user request as a daily-assistant task.",
        "Collect only the email, drive, and policy references needed for a safe draft response.",
    ]
    profile["routing_plan"] = [
        f"Consult email_manager_agent: {'yes' if email_matches else 'no'}",
        f"Consult drive_manager_agent: {'yes' if drive_matches else 'no'}",
        f"Consult policy context: {'yes' if policy_matches else 'no'}",
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
    profile["policy_flags"] = [
        f"{match['id']}: {match['summary']}"
        for match in policy_matches
        if "draft" in match["summary"].lower()
        or "external" in match["summary"].lower()
        or "review" in match["summary"].lower()
    ] or ["No additional email policy flag identified."]
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
    profile["sharing_requirements"] = [
        requirement
        for match in policy_matches
        for requirement in match["requirements"]
        if "share" in requirement.lower()
        or "archive" in requirement.lower()
        or "move" in requirement.lower()
        or "confirm" in requirement.lower()
    ] or ["No additional sharing requirement identified."]
    profile["missing_documents"] = (
        []
        if drive_matches or profile["drive_status"] == "not_needed"
        else ["No matching drive file or folder was found."]
    )
    profile["final_response_plan"] = [
        "Return a concise response plan for the user.",
        "Keep all email and drive actions in draft mode or sandbox-staged adapter mode.",
    ]
    profile["review_notes"] = [
        "Daily assistant Phase 2 stays draft-only and now cites policy evidence.",
        "User confirmation is still required for any future send or share action.",
    ]
    profile["policy_evidence_review"] = [
        f"{match['id']}: {match['summary']}" for match in policy_matches
    ] or ["No policy evidence was found."]
    profile["confirmation_queue_review"] = [
        (
            f"{item['id']} -> action={item['requested_action']} "
            f"target={item['target']} status={item['status']}"
        )
        for item in profile["confirmation_queue"]
    ] or ["No pending confirmation requests."]
    profile["action_log_review"] = list(profile["assistant_action_log"]) or [
        "No assistant action-log entries were recorded."
    ]
    profile["adapter_evidence_review"] = [
        (
            f"{record['id']} via {record['adapter_id']} "
            f"status={record['status']} target={record['target']}"
        )
        for record in [
            *profile["sandbox_mail_records"],
            *profile["sandbox_drive_records"],
        ]
    ] or ["No sandbox adapter receipts were recorded."]
    queue_status = (
        "pending_confirmation" if profile["confirmation_queue"] else "empty"
    )
    action_log_verdict = (
        "recorded" if profile["assistant_action_log"] else "insufficient_evidence"
    )
    sandbox_summary = profile["sandbox_execution_summary"] or build_sandbox_execution_summary(
        mail_records=profile["sandbox_mail_records"],
        drive_records=profile["sandbox_drive_records"],
        receipts=profile["sandbox_adapter_receipts"],
        confirmation_queue=profile["confirmation_queue"],
    )
    adapter_verdict = sandbox_summary.get("adapter_verdict", "missing_receipts")
    profile["queue_status"] = queue_status
    profile["action_log_verdict"] = action_log_verdict
    profile["adapter_verdict"] = adapter_verdict
    profile["review_notes"] = [
        (
            f"Daily assistant Phase 3B keeps a confirmation queue with status={queue_status}."
        ),
        (
            "Action-log evidence is available for review."
            if action_log_verdict == "recorded"
            else "Action-log evidence is still missing."
        ),
        (
            f"Sandbox adapter verdict is {adapter_verdict}."
        ),
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
        artifact["safe_action_mode"] = normalize_safe_action_mode(
            source.get("safe_action_mode")
        )
        artifact["queue_status"] = normalize_queue_status(source.get("queue_status"))
        artifact["action_log_verdict"] = normalize_action_log_verdict(
            source.get("action_log_verdict")
        )
        artifact["adapter_verdict"] = normalize_adapter_verdict(
            source.get("adapter_verdict")
        )
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
            "policy_flags": profile["policy_flags"],
            "proposed_email_actions": profile["proposed_email_actions"],
            "email_receipt_ids": profile["email_receipt_ids"],
            "sandbox_email_receipts": profile["sandbox_email_receipts"],
            "email_status": profile["email_status"],
        }
        return dump_artifact(artifact)

    if role == "drive_manager_agent":
        artifact = {
            "file_matches": profile["file_matches"],
            "suggested_file_actions": profile["suggested_file_actions"],
            "sharing_risks": profile["sharing_risks"],
            "missing_documents": profile["missing_documents"],
            "sharing_requirements": profile["sharing_requirements"],
            "proposed_drive_actions": profile["proposed_drive_actions"],
            "drive_receipt_ids": profile["drive_receipt_ids"],
            "sandbox_drive_receipts": profile["sandbox_drive_receipts"],
            "drive_status": profile["drive_status"],
        }
        return dump_artifact(artifact)

    if role == "assistant_review_agent":
        artifact = {
            "final_response_plan": profile["final_response_plan"],
            "permission_check": profile["permission_check"],
            "review_notes": profile["review_notes"],
            "policy_evidence_review": profile["policy_evidence_review"],
            "confirmation_queue_review": profile["confirmation_queue_review"],
            "action_log_review": profile["action_log_review"],
            "adapter_evidence_review": profile["adapter_evidence_review"],
            "safe_action_mode": profile["safe_action_mode"],
            "queue_status": profile["queue_status"],
            "action_log_verdict": profile["action_log_verdict"],
            "adapter_verdict": profile["adapter_verdict"],
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
            "search_policy",
            "read_policy_rule",
            "record_assistant_action",
            "read_assistant_action_log",
            "record_confirmation_request",
            "read_confirmation_queue",
            "stage_mail_adapter_action",
            "read_mail_adapter_receipts",
            "stage_drive_adapter_action",
            "read_drive_adapter_receipts",
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
        policy_matches = resolve_policy_matches_for_state(state, top_k=3)
        return [
            f"Assistant phase: {ASSISTANT_PHASE}",
            f"Policy phase: {POLICY_PHASE}",
            f"Adapter phase: {ADAPTER_PHASE}",
            f"Email thread count: {len(EMAIL_THREADS)}",
            f"Drive item count: {len(DRIVE_INDEX)}",
            f"Policy rule count: {len(POLICY_RULES)}",
            f"Sandbox adapter count: {len(SANDBOX_ADAPTERS)}",
            f"Email candidate ids: {', '.join(match['id'] for match in email_matches) or '(none)'}",
            f"Drive candidate ids: {', '.join(match['id'] for match in drive_matches) or '(none)'}",
            f"Policy candidate ids: {', '.join(match['id'] for match in policy_matches) or '(none)'}",
        ]

    def extend_shared_memory(
        self,
        state: FiveLayerState,
    ) -> dict[str, Any]:
        email_matches = resolve_email_matches_for_state(state, top_k=3)
        drive_matches = resolve_drive_matches_for_state(state, top_k=3)
        policy_matches = resolve_policy_matches_for_state(state, top_k=3)
        return {
            "assistant_phase": ASSISTANT_PHASE,
            "policy_phase": POLICY_PHASE,
            "queue_phase": QUEUE_PHASE,
            "adapter_phase": ADAPTER_PHASE,
            "email_matches": email_matches,
            "drive_matches": drive_matches,
            "policy_matches": policy_matches,
            "assistant_action_log": list(state.get("assistant_action_log", [])),
            "assistant_receipts": dict(state.get("assistant_receipts", {})),
            "confirmation_queue": list(state.get("confirmation_queue", [])),
            "assistant_execution_evidence": dict(
                state.get("assistant_execution_evidence", {})
            ),
            "sandbox_mail_records": list(state.get("sandbox_mail_records", [])),
            "sandbox_drive_records": list(state.get("sandbox_drive_records", [])),
            "sandbox_adapter_receipts": dict(
                state.get("sandbox_adapter_receipts", {})
            ),
            "sandbox_execution_summary": dict(
                state.get("sandbox_execution_summary", {})
            ),
        }

    def extend_brief_sections(
        self,
        role: str,
        state: FiveLayerState,
    ) -> list[str]:
        email_matches = resolve_email_matches_for_state(state, top_k=3)
        drive_matches = resolve_drive_matches_for_state(state, top_k=3)
        policy_matches = resolve_policy_matches_for_state(state, top_k=3)
        shared_memory = state.get("shared_memory", {})
        assistant_action_log = list(
            state.get("assistant_action_log", shared_memory.get("assistant_action_log", []))
        )
        confirmation_queue = list(
            state.get("confirmation_queue", shared_memory.get("confirmation_queue", []))
        )
        sandbox_mail_records = list(
            state.get("sandbox_mail_records", shared_memory.get("sandbox_mail_records", []))
        )
        sandbox_drive_records = list(
            state.get(
                "sandbox_drive_records",
                shared_memory.get("sandbox_drive_records", []),
            )
        )
        sandbox_adapter_receipts = dict(
            state.get(
                "sandbox_adapter_receipts",
                shared_memory.get("sandbox_adapter_receipts", {}),
            )
        )
        sections: list[str] = []

        if role in {
            "email_manager_agent",
            "drive_manager_agent",
            "assistant_review_agent",
        }:
            sections.append(
                f"Relevant policy rules:\n{format_policy_matches_for_brief(policy_matches)}"
            )
        if role in {"email_manager_agent", "assistant_review_agent"}:
            sections.append(
                "Mail sandbox adapter:\n"
                + format_sandbox_adapters_for_brief([SANDBOX_ADAPTERS_BY_DOMAIN["email"]])
            )
        if role in {"drive_manager_agent", "assistant_review_agent"}:
            sections.append(
                "Drive sandbox adapter:\n"
                + format_sandbox_adapters_for_brief([SANDBOX_ADAPTERS_BY_DOMAIN["drive"]])
            )
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
                f"Recorded assistant action log:\n{format_assistant_action_log(assistant_action_log)}"
            )
            sections.append(
                f"Pending confirmation queue:\n{format_confirmation_queue(confirmation_queue)}"
            )
            sections.append(
                f"Sandbox mail records:\n{format_sandbox_records(sandbox_mail_records)}"
            )
            sections.append(
                f"Sandbox drive records:\n{format_sandbox_records(sandbox_drive_records)}"
            )
            sections.append(
                f"Sandbox adapter receipts:\n{format_sandbox_receipts(sandbox_adapter_receipts)}"
            )
            sections.append(
                "Phase-3B safety rule:\n"
                + bullet_list(
                    [
                        "Return drafts, summaries, or suggestions only.",
                        "Do not send email, move files, or share drive links automatically.",
                        "Stage any candidate email or drive operation through sandbox adapters only.",
                        "Use policy evidence to justify any confirmation requirement.",
                        "Record proposed actions, sandbox receipts, and pending confirmations for auditability.",
                    ]
                )
            )
        return sections

    def postprocess_role_execution(
        self,
        role: str,
        state: FiveLayerState,
        artifact: dict[str, Any],
        normalized_output: str,
    ) -> tuple[dict[str, Any], str, dict[str, Any], list[dict[str, Any]]]:
        state_updates: dict[str, Any] = {}
        trace_events: list[dict[str, Any]] = []

        if role in {"email_manager_agent", "drive_manager_agent"}:
            action_updates, trace_events = build_role_action_updates(role, state)
            state_updates.update(action_updates)
        elif role == "assistant_review_agent":
            evidence = build_assistant_execution_evidence(
                action_log=list(state.get("assistant_action_log", [])),
                confirmation_queue=list(state.get("confirmation_queue", [])),
                receipts=dict(state.get("assistant_receipts", {})),
            )
            sandbox_summary = build_sandbox_execution_summary(
                mail_records=list(state.get("sandbox_mail_records", [])),
                drive_records=list(state.get("sandbox_drive_records", [])),
                receipts=dict(state.get("sandbox_adapter_receipts", {})),
                confirmation_queue=list(state.get("confirmation_queue", [])),
            )
            state_updates.update(
                {
                    "assistant_execution_evidence": evidence,
                    "sandbox_execution_summary": sandbox_summary,
                }
            )
            trace_events.append(
                {
                    "event": "assistant_review_completed",
                    "role": role,
                    "summary": (
                        f"queue_status={artifact.get('queue_status', '')} "
                        f"action_log_verdict={artifact.get('action_log_verdict', '')}"
                    ).strip(),
                }
            )
            trace_events.append(
                {
                    "event": "sandbox_review_completed",
                    "role": role,
                    "summary": f"adapter_verdict={artifact.get('adapter_verdict', '')}",
                }
            )

        if state_updates:
            shared_memory = dict(state.get("shared_memory", {}))
            for key in [
                "assistant_action_log",
                "assistant_receipts",
                "confirmation_queue",
                "assistant_execution_evidence",
                "sandbox_mail_records",
                "sandbox_drive_records",
                "sandbox_adapter_receipts",
                "sandbox_execution_summary",
            ]:
                if key in state_updates:
                    shared_memory[key] = state_updates[key]
            state_updates["shared_memory"] = shared_memory

        return artifact, normalized_output, state_updates, trace_events

    def summarize_state(self, state: FiveLayerState) -> dict[str, Any]:
        summary = super().summarize_state(state)
        summary["assistant_phase"] = ASSISTANT_PHASE
        summary["policy_phase"] = POLICY_PHASE
        summary["queue_phase"] = QUEUE_PHASE
        summary["adapter_phase"] = ADAPTER_PHASE
        shared_memory = state.get("shared_memory", {})
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
        summary["policy_matches"] = list(
            state.get(
                "shared_memory",
                {},
            ).get("policy_matches", [])
        )
        summary["assistant_action_log"] = list(
            state.get("assistant_action_log", shared_memory.get("assistant_action_log", []))
        )
        summary["assistant_receipts"] = dict(
            state.get("assistant_receipts", shared_memory.get("assistant_receipts", {}))
        )
        summary["confirmation_queue"] = list(
            state.get("confirmation_queue", shared_memory.get("confirmation_queue", []))
        )
        summary["assistant_execution_evidence"] = dict(
            state.get(
                "assistant_execution_evidence",
                shared_memory.get("assistant_execution_evidence", {}),
            )
        )
        summary["sandbox_mail_records"] = list(
            state.get("sandbox_mail_records", shared_memory.get("sandbox_mail_records", []))
        )
        summary["sandbox_drive_records"] = list(
            state.get(
                "sandbox_drive_records",
                shared_memory.get("sandbox_drive_records", []),
            )
        )
        summary["sandbox_adapter_receipts"] = dict(
            state.get(
                "sandbox_adapter_receipts",
                shared_memory.get("sandbox_adapter_receipts", {}),
            )
        )
        summary["sandbox_execution_summary"] = dict(
            state.get(
                "sandbox_execution_summary",
                shared_memory.get("sandbox_execution_summary", {}),
            )
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
