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
KB_ARTICLES_PATH = ROOT / "kb_articles.json"
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
KB_CONFIDENCE_OPTIONS = {
    "low",
    "medium",
    "high",
}
FINAL_DECISION_OPTIONS = {
    "Close",
    "Escalate",
    "Needs info",
}
EXECUTION_VERDICT_OPTIONS = {
    "recorded",
    "pending_human",
    "escalated",
    "completed",
}
RECEIPT_CONSISTENCY_OPTIONS = {
    "consistent",
    "missing",
    "inconsistent",
}
AUDIT_VERDICT_OPTIONS = {
    "evidence_ok",
    "followup_required",
    "reject",
}
APPROVAL_ROUTE_OPTIONS = {
    "not_required",
    "identity_verification",
    "finance_manager_approval",
}
APPROVAL_WAIT_STATE_OPTIONS = {
    "not_required",
    "pending",
    "approved",
    "denied",
}
DB_STATE_CONSISTENCY_OPTIONS = {
    "consistent",
    "missing_update",
    "inconsistent",
}
CLOSURE_ELIGIBILITY_OPTIONS = {
    "eligible",
    "blocked_by_approval",
    "blocked_by_state",
}
PIPELINE_PHASE = "ticket_plus_kb_action_log_db_approval"

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
            "kb_matches",
            "approval_reason",
        ],
        "string_fields": [
            "priority",
            "target_queue",
            "kb_confidence",
            "approval_required",
            "approval_route",
        ],
        "section_labels": {
            "routing_rationale": "Routing rationale",
            "required_checks": "Required checks",
            "kb_matches": "KB matches",
            "approval_reason": "Approval reason",
            "priority": "Priority",
            "target_queue": "Target queue",
            "kb_confidence": "KB confidence",
            "approval_required": "Approval required",
            "approval_route": "Approval route",
        },
        "role_instruction": (
            "Judge urgency, choose the correct queue, and decide what must be verified before action."
        ),
    },
    "executor_agent": {
        "list_fields": [
            "actions_taken",
            "execution_notes",
            "kb_actions_used",
            "action_log_entries",
            "receipt_ids",
            "db_updates",
            "execution_blockers",
        ],
        "string_fields": [
            "status_update",
            "needs_human",
            "execution_verdict",
            "approval_wait_state",
        ],
        "section_labels": {
            "actions_taken": "Actions taken",
            "execution_notes": "Execution notes",
            "kb_actions_used": "KB actions used",
            "action_log_entries": "Action log entries",
            "receipt_ids": "Receipt IDs",
            "db_updates": "DB updates",
            "execution_blockers": "Execution blockers",
            "status_update": "Status update",
            "needs_human": "Needs human",
            "execution_verdict": "Execution verdict",
            "approval_wait_state": "Approval wait state",
        },
        "role_instruction": (
            "Simulate the next operational step such as queueing work, notifying a human, or recording the action taken."
        ),
    },
    "audit_agent": {
        "list_fields": [
            "completeness_check",
            "risks",
            "kb_evidence_review",
            "action_log_review",
            "approval_chain_review",
        ],
        "string_fields": [
            "final_decision",
            "receipt_consistency",
            "audit_verdict",
            "db_state_consistency",
            "closure_eligibility",
        ],
        "section_labels": {
            "completeness_check": "Completeness check",
            "risks": "Risks",
            "kb_evidence_review": "KB evidence review",
            "action_log_review": "Action log review",
            "approval_chain_review": "Approval chain review",
            "final_decision": "Final decision",
            "receipt_consistency": "Receipt consistency",
            "audit_verdict": "Audit verdict",
            "db_state_consistency": "DB state consistency",
            "closure_eligibility": "Closure eligibility",
        },
        "role_instruction": (
            "Review whether the pipeline is complete, whether escalation is needed, and whether the ticket can be closed."
        ),
    },
}


def load_kb_articles() -> list[dict[str, Any]]:
    return json.loads(KB_ARTICLES_PATH.read_text(encoding="utf-8"))


KB_ARTICLES = load_kb_articles()
KB_ARTICLES_BY_ID = {article["id"]: article for article in KB_ARTICLES}

CASE_PHASE2_PROFILES = {
    "vpn_access_reset": {
        "category": "access_request",
        "priority": "high",
        "target_queue": "access_management",
        "status_update": "waiting_human",
        "needs_human": "yes",
        "final_decision": "Escalate",
        "kb_confidence": "high",
        "kb_article_ids": [
            "kb_vpn_locked_account_reset",
        ],
    },
    "new_hire_access_bundle": {
        "category": "onboarding",
        "priority": "medium",
        "target_queue": "onboarding",
        "status_update": "waiting_human",
        "needs_human": "yes",
        "final_decision": "Escalate",
        "kb_confidence": "high",
        "kb_article_ids": [
            "kb_new_hire_standard_access_bundle",
            "kb_finance_drive_access_requires_approval",
        ],
    },
    "printer_issue_branch_office": {
        "category": "incident",
        "priority": "high",
        "target_queue": "local_support",
        "status_update": "escalated",
        "needs_human": "yes",
        "final_decision": "Escalate",
        "kb_confidence": "high",
        "kb_article_ids": [
            "kb_branch_printer_team_outage",
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

    if role == "executor_agent":
        extra_rules.append(
            'Set "needs_human" to exactly one of: "yes", "no".'
        )
        extra_rules.append(
            'Set "status_update" to exactly one of: "new", "triaged", "queued", "waiting_human", "resolved", "escalated", "closed".'
        )
        extra_rules.append(
            'Set "execution_verdict" to exactly one of: "recorded", "pending_human", "escalated", "completed".'
        )
        extra_rules.append(
            'Each "action_log_entries" item must follow this format: "step=<n> | action=<action> | tool=<tool> | receipt=<receipt_id> | outcome=<outcome>".'
        )
    if role == "audit_agent":
        extra_rules.append(
            'Set "final_decision" to exactly one of: "Close", "Escalate", "Needs info".'
        )
        extra_rules.append(
            'Set "receipt_consistency" to exactly one of: "consistent", "missing", "inconsistent".'
        )
        extra_rules.append(
            'Set "audit_verdict" to exactly one of: "evidence_ok", "followup_required", "reject".'
        )
        extra_rules.append(
            'Set "db_state_consistency" to exactly one of: "consistent", "missing_update", "inconsistent".'
        )
        extra_rules.append(
            'Set "closure_eligibility" to exactly one of: "eligible", "blocked_by_approval", "blocked_by_state".'
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
        extra_rules.append(
            'Set "kb_confidence" to exactly one of: "low", "medium", "high".'
        )
        extra_rules.append(
            'Set "approval_required" to exactly one of: "yes", "no".'
        )
        extra_rules.append(
            'Set "approval_route" to exactly one of: "not_required", "identity_verification", "finance_manager_approval".'
        )
    if role == "executor_agent":
        extra_rules.append(
            'Set "approval_wait_state" to exactly one of: "not_required", "pending", "approved", "denied".'
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


def normalize_search_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def strip_list_prefix(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^[-*]\s+", "", text)
    text = re.sub(r"^\d+\.\s+", "", text)
    return text.strip()


def unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def slugify_token(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", normalize_search_text(text))
    slug = slug.strip("_")
    return slug or fallback


def parse_action_log_entry(entry: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in entry.split("|"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        parsed[key.strip().lower()] = value.strip()
    return parsed


def canonicalize_action_log_entry(entry: Any, step_index: int) -> str:
    raw_text = coerce_string(entry)
    parsed = parse_action_log_entry(raw_text)
    step = parsed.get("step", str(step_index)).strip() or str(step_index)
    action = slugify_token(parsed.get("action", raw_text), f"action_{step}")
    tool = slugify_token(parsed.get("tool", "record_action_log"), "record_action_log")
    receipt = slugify_token(
        parsed.get("receipt", parsed.get("receipt_id", f"rcpt_step_{step}")),
        f"rcpt_step_{step}",
    )
    outcome = slugify_token(parsed.get("outcome", "recorded"), "recorded")
    return (
        f"step={step} | action={action} | tool={tool} | "
        f"receipt={receipt} | outcome={outcome}"
    )


def normalize_action_log_entries(value: Any) -> list[str]:
    entries = coerce_list(value)
    return [
        canonicalize_action_log_entry(entry, step_index=index)
        for index, entry in enumerate(entries, start=1)
    ]


def normalize_receipt_ids(value: Any, action_log_entries: list[str]) -> list[str]:
    receipt_ids = [
        slugify_token(receipt_id, "receipt")
        for receipt_id in coerce_list(value)
    ]
    receipt_ids.extend(
        parse_action_log_entry(entry).get("receipt", "")
        for entry in action_log_entries
    )
    return unique_preserving_order([receipt_id for receipt_id in receipt_ids if receipt_id])


def build_executor_receipts(
    action_log_entries: list[str],
    receipt_ids: list[str],
) -> dict[str, dict[str, Any]]:
    receipts: dict[str, dict[str, Any]] = {}
    for entry in action_log_entries:
        parsed = parse_action_log_entry(entry)
        receipt_id = parsed.get("receipt")
        if not receipt_id:
            continue
        receipts[receipt_id] = {
            "step": int(parsed.get("step", "0") or 0),
            "action": parsed.get("action", ""),
            "tool": parsed.get("tool", ""),
            "outcome": parsed.get("outcome", ""),
            "recorded": True,
        }

    for receipt_id in receipt_ids:
        receipts.setdefault(
            receipt_id,
            {
                "step": 0,
                "action": "",
                "tool": "",
                "outcome": "missing_from_action_log",
                "recorded": False,
            },
        )
    return receipts


def build_execution_evidence(
    action_log_entries: list[str],
    receipt_ids: list[str],
    expected_receipts: list[str] | None = None,
) -> dict[str, Any]:
    parsed_entries = [parse_action_log_entry(entry) for entry in action_log_entries]
    logged_receipts = [
        parsed.get("receipt", "")
        for parsed in parsed_entries
        if parsed.get("receipt")
    ]
    recorded_receipts = unique_preserving_order(
        [receipt_id for receipt_id in [*receipt_ids, *logged_receipts] if receipt_id]
    )
    required_receipts = unique_preserving_order(
        expected_receipts if expected_receipts is not None else recorded_receipts
    )
    missing_receipts = [
        receipt_id
        for receipt_id in required_receipts
        if receipt_id not in receipt_ids or receipt_id not in logged_receipts
    ]

    step_numbers: list[int] = []
    for parsed in parsed_entries:
        try:
            step_numbers.append(int(parsed.get("step", "0") or 0))
        except ValueError:
            step_numbers.append(0)
    chronology_ok = (
        bool(step_numbers)
        and step_numbers == sorted(step_numbers)
        and step_numbers == list(range(1, len(step_numbers) + 1))
    )
    if not action_log_entries:
        chronology_ok = False

    if missing_receipts:
        receipt_consistency = "missing"
    elif not chronology_ok:
        receipt_consistency = "inconsistent"
    else:
        receipt_consistency = "consistent"

    return {
        "required_receipts": required_receipts,
        "recorded_receipts": recorded_receipts,
        "missing_receipts": missing_receipts,
        "action_log_count": len(action_log_entries),
        "chronology_ok": chronology_ok,
        "receipt_consistency": receipt_consistency,
    }


def build_action_log_review_lines(evidence: dict[str, Any]) -> list[str]:
    lines = [
        f"Action log entries recorded: {evidence['action_log_count']}",
        f"Receipt consistency: {evidence['receipt_consistency']}",
        f"Chronology check: {'pass' if evidence['chronology_ok'] else 'fail'}",
    ]
    if evidence["missing_receipts"]:
        lines.append(
            "Missing receipts: " + ", ".join(evidence["missing_receipts"])
        )
    else:
        lines.append("Missing receipts: none")
    return lines


def normalize_execution_verdict(value: Any) -> str:
    text = coerce_string(value).lower()
    if "complete" in text or "closed" in text:
        return "completed"
    if "escalat" in text:
        return "escalated"
    if "pending" in text or "human" in text:
        return "pending_human"
    if text in EXECUTION_VERDICT_OPTIONS:
        return text
    return "recorded"


def normalize_receipt_consistency(value: Any) -> str:
    text = coerce_string(value).lower()
    if "inconsistent" in text:
        return "inconsistent"
    if "missing" in text:
        return "missing"
    if text in RECEIPT_CONSISTENCY_OPTIONS:
        return text
    return "consistent"


def normalize_audit_verdict(value: Any) -> str:
    text = coerce_string(value).lower()
    if "reject" in text or "fail" in text:
        return "reject"
    if "follow" in text or "pending" in text or "human" in text:
        return "followup_required"
    if text in AUDIT_VERDICT_OPTIONS:
        return text
    return "evidence_ok"


def derive_execution_verdict(status_update: str, needs_human: str) -> str:
    if status_update == "escalated":
        return "escalated"
    if needs_human == "yes":
        return "pending_human"
    if status_update in {"resolved", "closed"}:
        return "completed"
    return "recorded"


def derive_audit_verdict(
    receipt_consistency: str,
    final_decision: str,
) -> str:
    if receipt_consistency != "consistent":
        return "reject"
    if final_decision == "Close":
        return "evidence_ok"
    return "followup_required"


def score_kb_article(article: dict[str, Any], query: str) -> int:
    haystack = normalize_search_text(query)
    score = 0

    phrase_candidates = [
        article["title"],
        article["summary"],
        article["category"].replace("_", " "),
        *article.get("keywords", []),
    ]
    for phrase in phrase_candidates:
        normalized_phrase = normalize_search_text(str(phrase))
        if normalized_phrase and normalized_phrase in haystack:
            score += 3

    article_tokens = set(
        re.findall(
            r"[a-z0-9_]+",
            normalize_search_text(
                " ".join(
                    [
                        article["title"],
                        article["summary"],
                        article["category"],
                        " ".join(article.get("keywords", [])),
                    ]
                )
            ),
        )
    )
    query_tokens = set(re.findall(r"[a-z0-9_]+", haystack))
    score += len(article_tokens & query_tokens)
    return score


def search_kb_articles(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    scored_results: list[tuple[int, dict[str, Any]]] = []
    for article in KB_ARTICLES:
        score = score_kb_article(article, query)
        if score > 0:
            scored_results.append((score, article))

    scored_results.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [
        {
            "id": article["id"],
            "title": article["title"],
            "category": article["category"],
            "summary": article["summary"],
            "recommended_actions": list(article["recommended_actions"]),
            "requires_human": bool(article["requires_human"]),
            "requires_approval": bool(article["requires_approval"]),
            "escalation_queue": article["escalation_queue"],
            "score": score,
        }
        for score, article in scored_results[:top_k]
    ]


def read_kb_article(article_id: str) -> dict[str, Any]:
    return dict(KB_ARTICLES_BY_ID[article_id])


def build_state_query(state: FiveLayerState) -> str:
    parts = [
        state.get("task", ""),
        state.get("repository_context", ""),
        *state.get("acceptance_criteria", []),
        *state.get("risk_notes", []),
    ]
    return "\n".join(part for part in parts if part)


def resolve_kb_matches_for_state(
    state: FiveLayerState,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    matches = search_kb_articles(build_state_query(state), top_k=top_k)
    preferred_ids = CASE_PHASE2_PROFILES.get(
        state.get("scenario_id", ""),
        {},
    ).get("kb_article_ids", [])
    if not preferred_ids:
        return matches

    matches_by_id = {match["id"]: match for match in matches}
    ordered_matches: list[dict[str, Any]] = []
    for article_id in preferred_ids:
        match = matches_by_id.get(article_id)
        if match is None:
            article = read_kb_article(article_id)
            match = {
                "id": article["id"],
                "title": article["title"],
                "category": article["category"],
                "summary": article["summary"],
                "recommended_actions": list(article["recommended_actions"]),
                "requires_human": bool(article["requires_human"]),
                "requires_approval": bool(article["requires_approval"]),
                "escalation_queue": article["escalation_queue"],
                "score": 0,
            }
        ordered_matches.append(match)
    return ordered_matches[: min(top_k, len(preferred_ids))]


def kb_match_labels(matches: list[dict[str, Any]]) -> list[str]:
    return [f"{match['id']}: {match['title']}" for match in matches]


def kb_recommended_actions(matches: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for match in matches:
        actions.extend(match.get("recommended_actions", []))
    return unique_preserving_order(actions)


def kb_required_checks(state: FiveLayerState, matches: list[dict[str, Any]]) -> list[str]:
    checks = list(state.get("risk_notes", []))
    for match in matches:
        if match.get("requires_human"):
            checks.append(
                f"Record a human handoff because {match['id']} requires manual verification or intervention."
            )
        if match.get("requires_approval"):
            checks.append(
                f"Do not complete approval-gated work until {match['id']} approval is explicitly recorded."
            )
    return unique_preserving_order(checks)


def kb_evidence_review_lines(matches: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for match in matches:
        lines.append(
            f"{match['id']} supports this route with summary: {match['summary']}"
        )
        if match.get("requires_human"):
            lines.append(
                f"{match['id']} requires a human or controlled verification step before closure."
            )
        if match.get("requires_approval"):
            lines.append(
                f"{match['id']} introduces an approval gate that must remain open until confirmed."
            )
    return unique_preserving_order(lines)


def format_kb_matches_for_brief(matches: list[dict[str, Any]]) -> str:
    if not matches:
        return "(no KB matches)"
    lines = [
        (
            f"{match['id']} | category={match['category']} | score={match['score']} | "
            f"title={match['title']} | summary={match['summary']}"
        )
        for match in matches
    ]
    return bullet_list(lines)


def build_action_specs_for_scenario(
    scenario_id: str,
    target_queue: str,
) -> list[dict[str, str]]:
    if scenario_id == "vpn_access_reset":
        return [
            {
                "action": "verify_identity",
                "tool": "record_action_log",
                "outcome": "verification_pending_human",
            },
            {
                "action": "queue_access_reset",
                "tool": "record_action_log",
                "outcome": f"queued_{target_queue}",
            },
        ]
    if scenario_id == "new_hire_access_bundle":
        return [
            {
                "action": "queue_standard_access_bundle",
                "tool": "record_action_log",
                "outcome": f"queued_{target_queue}",
            },
            {
                "action": "request_finance_drive_approval",
                "tool": "record_action_log",
                "outcome": "approval_requested",
            },
            {
                "action": "hold_privileged_access",
                "tool": "record_action_log",
                "outcome": "waiting_for_approval",
            },
        ]
    return [
        {
            "action": "record_shared_service_incident",
            "tool": "record_action_log",
            "outcome": "incident_recorded",
        },
        {
            "action": "notify_local_support",
            "tool": "record_action_log",
            "outcome": f"queued_{target_queue}",
        },
    ]


def build_action_log_entries_for_scenario(
    scenario_id: str,
    target_queue: str,
) -> tuple[list[str], list[str]]:
    action_specs = build_action_specs_for_scenario(scenario_id, target_queue)
    action_log_entries: list[str] = []
    receipt_ids: list[str] = []
    for index, spec in enumerate(action_specs, start=1):
        receipt_id = f"rcpt_{slugify_token(scenario_id, 'scenario')}_{index}_{slugify_token(spec['action'], 'action')}"
        receipt_ids.append(receipt_id)
        action_log_entries.append(
            canonicalize_action_log_entry(
                (
                    f"step={index} | action={spec['action']} | tool={spec['tool']} | "
                    f"receipt={receipt_id} | outcome={spec['outcome']}"
                ),
                step_index=index,
            )
        )
    return action_log_entries, receipt_ids


def format_action_log_for_brief(action_log: list[str]) -> str:
    if not action_log:
        return "(no action log recorded yet)"
    return bullet_list(action_log)


def format_executor_receipts_for_brief(receipts: dict[str, dict[str, Any]]) -> str:
    if not receipts:
        return "(no executor receipts recorded yet)"
    lines = [
        (
            f"{receipt_id} | step={payload['step']} | action={payload['action']} | "
            f"tool={payload['tool']} | outcome={payload['outcome']} | recorded={payload['recorded']}"
        )
        for receipt_id, payload in receipts.items()
    ]
    return bullet_list(lines)


def format_execution_evidence_for_brief(evidence: dict[str, Any]) -> str:
    if not evidence:
        return "(no execution evidence recorded yet)"
    lines = [
        f"required_receipts={', '.join(evidence.get('required_receipts', [])) or '(none)'}",
        f"recorded_receipts={', '.join(evidence.get('recorded_receipts', [])) or '(none)'}",
        f"missing_receipts={', '.join(evidence.get('missing_receipts', [])) or 'none'}",
        f"action_log_count={evidence.get('action_log_count', 0)}",
        f"chronology_ok={evidence.get('chronology_ok', False)}",
        f"receipt_consistency={evidence.get('receipt_consistency', 'missing')}",
    ]
    return bullet_list(lines)


def normalize_approval_route(value: Any) -> str:
    text = coerce_string(value).lower().replace(" ", "_")
    if "identity" in text or "verification" in text:
        return "identity_verification"
    if "finance" in text or "manager" in text or "approval" in text:
        return "finance_manager_approval"
    if text in APPROVAL_ROUTE_OPTIONS:
        return text
    return "not_required"


def normalize_approval_wait_state(value: Any) -> str:
    text = coerce_string(value).lower().replace(" ", "_")
    if "not" in text and "required" in text:
        return "not_required"
    if "deny" in text:
        return "denied"
    if "approve" in text:
        return "approved"
    if "pending" in text or "wait" in text:
        return "pending"
    if text in APPROVAL_WAIT_STATE_OPTIONS:
        return text
    return "pending"


def normalize_db_state_consistency(value: Any) -> str:
    text = coerce_string(value).lower()
    if "missing" in text:
        return "missing_update"
    if "inconsistent" in text:
        return "inconsistent"
    if text in DB_STATE_CONSISTENCY_OPTIONS:
        return text
    return "consistent"


def normalize_closure_eligibility(value: Any) -> str:
    text = coerce_string(value).lower().replace(" ", "_")
    if "approval" in text:
        return "blocked_by_approval"
    if "state" in text or "escalat" in text or "blocked" in text:
        return "blocked_by_state"
    if text in CLOSURE_ELIGIBILITY_OPTIONS:
        return text
    return "eligible"


def build_ticket_id(scenario_id: str) -> str:
    return f"TCK-{slugify_token(scenario_id, 'ticket').upper()}"


def build_approval_history(
    scenario_id: str,
    approval_route: str,
    approval_wait_state: str,
    approval_required: str,
) -> list[dict[str, str]]:
    if approval_required == "no":
        return [
            {
                "step": "1",
                "actor": "triage_agent",
                "route": "not_required",
                "state": "not_required",
                "note": f"{scenario_id} does not require a human approval path.",
            }
        ]

    history = [
        {
            "step": "1",
            "actor": "triage_agent",
            "route": approval_route,
            "state": "requested",
            "note": f"{approval_route} was opened during triage.",
        },
        {
            "step": "2",
            "actor": "executor_agent",
            "route": approval_route,
            "state": approval_wait_state,
            "note": f"Execution is waiting on {approval_route}.",
        },
    ]
    return history


def format_approval_history_for_brief(history: list[dict[str, str]]) -> str:
    if not history:
        return "(no approval history recorded yet)"
    lines = [
        (
            f"step={item['step']} | actor={item['actor']} | route={item['route']} | "
            f"state={item['state']} | note={item['note']}"
        )
        for item in history
    ]
    return bullet_list(lines)


def build_approval_chain_review(
    approval_history: list[dict[str, str]],
    approval_required: str,
    approval_wait_state: str,
) -> list[str]:
    if approval_required == "no":
        return [
            "Approval path is not required for this ticket.",
            "No approval record is needed before operational follow-up.",
        ]
    if not approval_history:
        return [
            "Approval path is required but no approval history was recorded.",
            "Closure must stay blocked until approval evidence exists.",
        ]

    lines = [
        f"Approval route is {approval_history[-1]['route']}.",
        f"Latest approval state is {approval_wait_state}.",
    ]
    if approval_wait_state != "approved":
        lines.append("Closure must stay blocked until approval is recorded.")
    return lines


def build_ticket_db_record(
    scenario_id: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ticket_id": build_ticket_id(scenario_id),
        "category": profile["category"],
        "priority": profile["priority"],
        "target_queue": profile["target_queue"],
        "status": profile["status_update"],
        "approval_required": profile["approval_required"],
        "approval_route": profile["approval_route"],
        "approval_wait_state": profile["approval_wait_state"],
        "latest_receipts": list(profile["receipt_ids"]),
    }


def format_ticket_db_record_for_brief(ticket_db_record: dict[str, Any]) -> str:
    if not ticket_db_record:
        return "(no ticket DB record recorded yet)"
    lines = [
        f"{key}={value if not isinstance(value, list) else ', '.join(value)}"
        for key, value in ticket_db_record.items()
    ]
    return bullet_list(lines)


def derive_db_state_consistency(
    ticket_db_record: dict[str, Any],
    approval_history: list[dict[str, str]],
    approval_wait_state: str,
) -> str:
    if not ticket_db_record:
        return "missing_update"
    if ticket_db_record.get("approval_wait_state") != approval_wait_state:
        return "inconsistent"
    if approval_wait_state != "not_required" and not approval_history:
        return "missing_update"
    return "consistent"


def derive_closure_eligibility(
    status_update: str,
    approval_required: str,
    approval_wait_state: str,
    final_decision: str,
) -> str:
    if approval_required == "yes" and approval_wait_state != "approved":
        return "blocked_by_approval"
    if final_decision == "Close" and status_update in {"resolved", "closed"}:
        return "eligible"
    return "blocked_by_state"


def build_case_profile(state: FiveLayerState) -> dict[str, Any]:
    scenario_id = state.get("scenario_id", "")
    profile = dict(
        CASE_PHASE2_PROFILES.get(
            scenario_id,
            {
                "category": "service_request",
                "priority": "medium",
                "target_queue": "service_desk",
                "status_update": "queued",
                "needs_human": "yes",
                "final_decision": "Needs info",
                "kb_confidence": "medium",
                "kb_article_ids": [],
                "approval_required": "no",
                "approval_route": "not_required",
            },
        )
    )

    if scenario_id == "vpn_access_reset":
        profile["approval_required"] = "yes"
        profile["approval_route"] = "identity_verification"
        profile["approval_reason"] = [
            "Identity verification must complete before a VPN reset can be actioned."
        ]
        profile["approval_wait_state"] = "pending"
    elif scenario_id == "new_hire_access_bundle":
        profile["approval_required"] = "yes"
        profile["approval_route"] = "finance_manager_approval"
        profile["approval_reason"] = [
            "Finance-drive access is approval-gated and cannot be bundled into the standard path."
        ]
        profile["approval_wait_state"] = "pending"
    else:
        profile["approval_required"] = "no"
        profile["approval_route"] = "not_required"
        profile["approval_reason"] = [
            "Incident escalation can proceed without a human approval gate."
        ]
        profile["approval_wait_state"] = "not_required"

    matches = resolve_kb_matches_for_state(state, top_k=3)
    profile["kb_matches"] = kb_match_labels(matches)
    profile["kb_actions_used"] = kb_recommended_actions(matches)
    profile["required_checks"] = kb_required_checks(state, matches)
    profile["kb_evidence_review"] = kb_evidence_review_lines(matches)
    profile["kb_articles"] = matches
    action_log_entries, receipt_ids = build_action_log_entries_for_scenario(
        scenario_id,
        profile["target_queue"],
    )
    execution_verdict = derive_execution_verdict(
        profile["status_update"],
        profile["needs_human"],
    )
    execution_evidence = build_execution_evidence(
        action_log_entries=action_log_entries,
        receipt_ids=receipt_ids,
        expected_receipts=receipt_ids,
    )
    profile["action_log_entries"] = action_log_entries
    profile["receipt_ids"] = receipt_ids
    profile["execution_verdict"] = execution_verdict
    profile["executor_receipts"] = build_executor_receipts(
        action_log_entries,
        receipt_ids,
    )
    profile["db_updates"] = [
        f"upsert ticket_id={build_ticket_id(scenario_id)} status={profile['status_update']}",
        f"set target_queue={profile['target_queue']} priority={profile['priority']}",
        (
            f"set approval_route={profile['approval_route']} "
            f"approval_wait_state={profile['approval_wait_state']}"
        ),
    ]
    profile["execution_blockers"] = (
        [
            (
                f"Cannot complete execution until {profile['approval_route']} "
                "is recorded as approved."
            )
        ]
        if profile["approval_required"] == "yes"
        else [f"Ticket remains open because status is {profile['status_update']}."]
    )
    profile["approval_history"] = build_approval_history(
        scenario_id=scenario_id,
        approval_route=profile["approval_route"],
        approval_wait_state=profile["approval_wait_state"],
        approval_required=profile["approval_required"],
    )
    profile["ticket_db_record"] = build_ticket_db_record(scenario_id, profile)
    profile["execution_evidence"] = {
        **execution_evidence,
        "execution_verdict": execution_verdict,
    }
    profile["receipt_consistency"] = execution_evidence["receipt_consistency"]
    profile["db_state_consistency"] = derive_db_state_consistency(
        profile["ticket_db_record"],
        profile["approval_history"],
        profile["approval_wait_state"],
    )
    profile["closure_eligibility"] = derive_closure_eligibility(
        status_update=profile["status_update"],
        approval_required=profile["approval_required"],
        approval_wait_state=profile["approval_wait_state"],
        final_decision=profile["final_decision"],
    )
    profile["audit_verdict"] = derive_audit_verdict(
        profile["receipt_consistency"],
        profile["final_decision"],
    )
    profile["action_log_review"] = build_action_log_review_lines(
        profile["execution_evidence"]
    )
    profile["approval_chain_review"] = build_approval_chain_review(
        approval_history=profile["approval_history"],
        approval_required=profile["approval_required"],
        approval_wait_state=profile["approval_wait_state"],
    )
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


def normalize_kb_confidence(value: Any) -> str:
    text = coerce_string(value).lower()
    if "high" in text or "strong" in text:
        return "high"
    if "low" in text or "weak" in text:
        return "low"
    if text in KB_CONFIDENCE_OPTIONS:
        return text
    return "medium"


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
        artifact["receipt_consistency"] = normalize_receipt_consistency(
            source.get("receipt_consistency")
        )
        artifact["audit_verdict"] = normalize_audit_verdict(
            source.get("audit_verdict")
        )
        artifact["db_state_consistency"] = normalize_db_state_consistency(
            source.get("db_state_consistency")
        )
        artifact["closure_eligibility"] = normalize_closure_eligibility(
            source.get("closure_eligibility")
        )
    if role == "executor_agent":
        artifact["action_log_entries"] = normalize_action_log_entries(
            source.get("action_log_entries")
        )
        artifact["receipt_ids"] = normalize_receipt_ids(
            source.get("receipt_ids"),
            artifact["action_log_entries"],
        )
        artifact["needs_human"] = normalize_yes_no(source.get("needs_human"))
        artifact["status_update"] = normalize_status(source.get("status_update"))
        artifact["execution_verdict"] = normalize_execution_verdict(
            source.get("execution_verdict")
        )
        artifact["approval_wait_state"] = normalize_approval_wait_state(
            source.get("approval_wait_state")
        )
    if role == "intake_agent":
        artifact["category"] = normalize_category(source.get("category"))
    if role == "triage_agent":
        artifact["priority"] = normalize_priority(source.get("priority"))
        artifact["target_queue"] = normalize_target_queue(source.get("target_queue"))
        artifact["kb_confidence"] = normalize_kb_confidence(
            source.get("kb_confidence")
        )
        artifact["approval_required"] = normalize_yes_no(
            source.get("approval_required")
        )
        artifact["approval_route"] = normalize_approval_route(
            source.get("approval_route")
        )

    return artifact, dump_artifact(artifact)


def simulate_role_output(role: str, state: FiveLayerState) -> str:
    case_profile = build_case_profile(state)
    if role == "intake_agent":
        artifact = {
            "ticket_summary": [
                "Summarize the user request into an ICT ticket.",
                "Capture requester need, business impact, and likely service area.",
            ],
            "extracted_fields": [
                "request type",
                "business impact",
                "affected service",
                "possible KB domain",
            ],
            "missing_fields": [
                "identity verification status"
                if case_profile["category"] == "access_request"
                else "explicit approval record"
                if case_profile["category"] == "onboarding"
                else "confirmed blast radius",
            ],
            "category": case_profile["category"],
        }
        return dump_artifact(artifact)

    if role == "triage_agent":
        artifact = {
            "routing_rationale": [
                "Use ticket impact and ownership boundaries to choose the next queue.",
                "Prefer KB-backed routing over free-form queue selection.",
            ],
            "required_checks": case_profile["required_checks"],
            "kb_matches": case_profile["kb_matches"],
            "approval_reason": case_profile["approval_reason"],
            "priority": case_profile["priority"],
            "target_queue": case_profile["target_queue"],
            "kb_confidence": case_profile["kb_confidence"],
            "approval_required": case_profile["approval_required"],
            "approval_route": case_profile["approval_route"],
        }
        return dump_artifact(artifact)

    if role == "executor_agent":
        artifact = {
            "actions_taken": [
                "Record the ticket state update.",
                "Queue the task for the owning team or controlled follow-up.",
            ],
            "execution_notes": [
                "Execution is still simulated in Phase 3B.",
                "The next action must stay aligned with KB guidance.",
            ],
            "kb_actions_used": case_profile["kb_actions_used"],
            "action_log_entries": case_profile["action_log_entries"],
            "receipt_ids": case_profile["receipt_ids"],
            "db_updates": case_profile["db_updates"],
            "execution_blockers": case_profile["execution_blockers"],
            "status_update": case_profile["status_update"],
            "needs_human": case_profile["needs_human"],
            "execution_verdict": case_profile["execution_verdict"],
            "approval_wait_state": case_profile["approval_wait_state"],
        }
        return dump_artifact(artifact)

    if role == "audit_agent":
        artifact = {
            "completeness_check": [
                "Ticket classification is present.",
                "Routing and next action are recorded.",
                "KB evidence is attached to the route.",
                "Risk checks are reflected in the plan.",
            ],
            "risks": list(state["risk_notes"]),
            "kb_evidence_review": case_profile["kb_evidence_review"],
            "action_log_review": case_profile["action_log_review"],
            "approval_chain_review": case_profile["approval_chain_review"],
            "final_decision": case_profile["final_decision"],
            "receipt_consistency": case_profile["receipt_consistency"],
            "audit_verdict": case_profile["audit_verdict"],
            "db_state_consistency": case_profile["db_state_consistency"],
            "closure_eligibility": case_profile["closure_eligibility"],
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
        tools = list(scenario.available_tools)
        for tool in [
            "search_kb",
            "read_kb_article",
            "record_action_log",
            "read_action_log",
            "read_executor_receipt",
            "read_ticket_db",
            "update_ticket_db",
            "request_human_approval",
            "read_approval_status",
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
        matches = resolve_kb_matches_for_state(state, top_k=3)
        return [
            f"Pipeline phase: {PIPELINE_PHASE}",
            f"KB phase: ticket_plus_kb",
            f"KB article count: {len(KB_ARTICLES)}",
            f"KB candidate ids: {', '.join(match['id'] for match in matches) or '(none)'}",
            "Approval layer: simulated DB-backed approval path enabled",
        ]

    def extend_shared_memory(
        self,
        state: FiveLayerState,
    ) -> dict[str, Any]:
        matches = resolve_kb_matches_for_state(state, top_k=3)
        return {
            "pipeline_phase": PIPELINE_PHASE,
            "kb_phase": "ticket_plus_kb",
            "kb_search_results": matches,
            "kb_article_ids": [match["id"] for match in matches],
            "action_log": [],
            "executor_receipts": {},
            "execution_evidence": {},
            "ticket_db_record": {},
            "approval_state": {},
            "approval_history": [],
        }

    def extend_brief_sections(
        self,
        role: str,
        state: FiveLayerState,
    ) -> list[str]:
        if role not in {"triage_agent", "executor_agent", "audit_agent"}:
            return []

        matches = resolve_kb_matches_for_state(state, top_k=3)
        sections = [
            f"Knowledge base matches:\n{format_kb_matches_for_brief(matches)}",
        ]
        if role in {"executor_agent", "audit_agent"}:
            sections.append(
                "Knowledge base recommended actions:\n"
                + bullet_list(kb_recommended_actions(matches))
            )
        if role == "executor_agent":
            case_profile = build_case_profile(state)
            sections.append(
                "Action-log requirements:\n"
                + bullet_list(
                    [
                        "Record each operational step as a structured action-log entry.",
                        "Attach a receipt id to every action-log entry.",
                        "Expected receipt ids: "
                        + ", ".join(case_profile["receipt_ids"]),
                    ]
                )
            )
            sections.append(
                "Ticket DB update requirements:\n"
                + bullet_list(
                    [
                        "Record the queue and status transition in the ticket DB snapshot.",
                        "Keep approval_wait_state aligned with the approval path.",
                        "Do not mark approval-gated work as completed before approval is recorded.",
                    ]
                )
            )
        if role == "audit_agent":
            sections.append(
                "Knowledge base evidence notes:\n"
                + bullet_list(kb_evidence_review_lines(matches))
            )
            sections.append(
                "Recorded action log:\n"
                + format_action_log_for_brief(state.get("action_log", []))
            )
            sections.append(
                "Executor receipts:\n"
                + format_executor_receipts_for_brief(
                    state.get("executor_receipts", {})
                )
            )
            sections.append(
                "Execution evidence summary:\n"
                + format_execution_evidence_for_brief(
                    state.get("execution_evidence", {})
                )
            )
            sections.append(
                "Ticket DB record:\n"
                + format_ticket_db_record_for_brief(state.get("ticket_db_record", {}))
            )
            sections.append(
                "Approval history:\n"
                + format_approval_history_for_brief(state.get("approval_history", []))
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

        if role == "executor_agent":
            action_log_entries = normalize_action_log_entries(
                artifact.get("action_log_entries", [])
            )
            receipt_ids = normalize_receipt_ids(
                artifact.get("receipt_ids", []),
                action_log_entries,
            )
            execution_verdict = normalize_execution_verdict(
                artifact.get("execution_verdict")
            )
            evidence = build_execution_evidence(
                action_log_entries=action_log_entries,
                receipt_ids=receipt_ids,
                expected_receipts=receipt_ids,
            )
            evidence["execution_verdict"] = execution_verdict
            approval_wait_state = normalize_approval_wait_state(
                artifact.get("approval_wait_state")
            )
            case_profile = build_case_profile(state)
            ticket_db_record = build_ticket_db_record(
                state.get("scenario_id", ""),
                {
                    **case_profile,
                    "status_update": artifact["status_update"],
                    "priority": state.get("role_artifacts", {})
                    .get("triage_agent", {})
                    .get("priority", case_profile["priority"]),
                    "target_queue": state.get("role_artifacts", {})
                    .get("triage_agent", {})
                    .get("target_queue", case_profile["target_queue"]),
                    "approval_wait_state": approval_wait_state,
                    "receipt_ids": receipt_ids,
                },
            )
            approval_state = {
                "approval_required": state.get("role_artifacts", {})
                .get("triage_agent", {})
                .get("approval_required", case_profile["approval_required"]),
                "approval_route": state.get("role_artifacts", {})
                .get("triage_agent", {})
                .get("approval_route", case_profile["approval_route"]),
                "approval_wait_state": approval_wait_state,
            }
            approval_history = build_approval_history(
                scenario_id=state.get("scenario_id", ""),
                approval_route=approval_state["approval_route"],
                approval_wait_state=approval_wait_state,
                approval_required=approval_state["approval_required"],
            )
            artifact["action_log_entries"] = action_log_entries
            artifact["receipt_ids"] = receipt_ids
            artifact["execution_verdict"] = execution_verdict
            artifact["approval_wait_state"] = approval_wait_state
            state_updates = {
                "pipeline_phase": PIPELINE_PHASE,
                "action_log": action_log_entries,
                "executor_receipts": build_executor_receipts(
                    action_log_entries,
                    receipt_ids,
                ),
                "execution_evidence": evidence,
                "ticket_db_record": ticket_db_record,
                "approval_state": approval_state,
                "approval_history": approval_history,
            }
            trace_events.append(
                {
                    "event": "action_log_recorded",
                    "role": role,
                    "summary": (
                        f"entries={len(action_log_entries)} receipts={len(receipt_ids)} "
                        f"consistency={evidence['receipt_consistency']}"
                    ),
                }
            )
            trace_events.append(
                {
                    "event": "ticket_db_updated",
                    "role": role,
                    "summary": (
                        f"ticket_id={ticket_db_record['ticket_id']} "
                        f"status={ticket_db_record['status']} "
                        f"approval_wait_state={ticket_db_record['approval_wait_state']}"
                    ),
                }
            )
            normalized_output = dump_artifact(artifact)

        if role == "audit_agent":
            evidence = build_execution_evidence(
                action_log_entries=state.get("action_log", []),
                receipt_ids=list(state.get("executor_receipts", {}).keys()),
                expected_receipts=state.get("execution_evidence", {}).get(
                    "required_receipts"
                ),
            )
            evidence["execution_verdict"] = state.get("execution_evidence", {}).get(
                "execution_verdict",
                normalize_execution_verdict(""),
            )
            artifact["receipt_consistency"] = evidence["receipt_consistency"]
            artifact["audit_verdict"] = derive_audit_verdict(
                artifact["receipt_consistency"],
                artifact["final_decision"],
            )
            artifact["action_log_review"] = build_action_log_review_lines(evidence)
            approval_state = state.get("approval_state", {})
            approval_history = state.get("approval_history", [])
            ticket_db_record = state.get("ticket_db_record", {})
            artifact["db_state_consistency"] = derive_db_state_consistency(
                ticket_db_record=ticket_db_record,
                approval_history=approval_history,
                approval_wait_state=approval_state.get(
                    "approval_wait_state",
                    "not_required",
                ),
            )
            artifact["closure_eligibility"] = derive_closure_eligibility(
                status_update=ticket_db_record.get("status", ""),
                approval_required=approval_state.get("approval_required", "no"),
                approval_wait_state=approval_state.get(
                    "approval_wait_state",
                    "not_required",
                ),
                final_decision=artifact["final_decision"],
            )
            artifact["approval_chain_review"] = build_approval_chain_review(
                approval_history=approval_history,
                approval_required=approval_state.get("approval_required", "no"),
                approval_wait_state=approval_state.get(
                    "approval_wait_state",
                    "not_required",
                ),
            )
            state_updates = {
                "pipeline_phase": PIPELINE_PHASE,
                "execution_evidence": evidence,
            }
            trace_events.append(
                {
                    "event": "audit_evidence_reviewed",
                    "role": role,
                    "summary": (
                        f"receipt_consistency={artifact['receipt_consistency']} "
                        f"audit_verdict={artifact['audit_verdict']}"
                    ),
                }
            )
            trace_events.append(
                {
                    "event": "approval_chain_reviewed",
                    "role": role,
                    "summary": (
                        f"db_state_consistency={artifact['db_state_consistency']} "
                        f"closure_eligibility={artifact['closure_eligibility']}"
                    ),
                }
            )
            normalized_output = dump_artifact(artifact)

        return artifact, normalized_output, state_updates, trace_events

    def coordination_commit_node(self, state: FiveLayerState) -> FiveLayerState:
        updates = super().coordination_commit_node(state)
        shared_memory = dict(updates.get("shared_memory", state.get("shared_memory", {})))
        shared_memory["pipeline_phase"] = state.get("pipeline_phase", PIPELINE_PHASE)
        shared_memory["action_log"] = list(state.get("action_log", []))
        shared_memory["executor_receipts"] = dict(state.get("executor_receipts", {}))
        shared_memory["execution_evidence"] = dict(state.get("execution_evidence", {}))
        shared_memory["ticket_db_record"] = dict(state.get("ticket_db_record", {}))
        shared_memory["approval_state"] = dict(state.get("approval_state", {}))
        shared_memory["approval_history"] = list(state.get("approval_history", []))
        updates["shared_memory"] = shared_memory
        updates["pipeline_phase"] = state.get("pipeline_phase", PIPELINE_PHASE)
        updates["action_log"] = list(state.get("action_log", []))
        updates["executor_receipts"] = dict(state.get("executor_receipts", {}))
        updates["execution_evidence"] = dict(state.get("execution_evidence", {}))
        updates["ticket_db_record"] = dict(state.get("ticket_db_record", {}))
        updates["approval_state"] = dict(state.get("approval_state", {}))
        updates["approval_history"] = list(state.get("approval_history", []))
        return updates

    def summarize_state(self, state: FiveLayerState) -> dict[str, Any]:
        summary = super().summarize_state(state)
        summary["pipeline_phase"] = state.get("pipeline_phase", PIPELINE_PHASE)
        summary["action_log"] = list(state.get("action_log", []))
        summary["executor_receipts"] = dict(state.get("executor_receipts", {}))
        summary["execution_evidence"] = dict(state.get("execution_evidence", {}))
        summary["ticket_db_record"] = dict(state.get("ticket_db_record", {}))
        summary["approval_state"] = dict(state.get("approval_state", {}))
        summary["approval_history"] = list(state.get("approval_history", []))
        return summary


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
