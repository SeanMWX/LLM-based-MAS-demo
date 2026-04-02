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
ROLE_ORDER = ["planner", "coder", "tester", "reviewer"]

ROLE_OUTPUT_SPECS = {
    "planner": {
        "list_fields": [
            "plan",
            "success_criteria",
            "risks",
            "handoff_to_coder",
        ],
        "string_fields": [],
        "section_labels": {
            "plan": "Plan",
            "success_criteria": "Success criteria",
            "risks": "Risks",
            "handoff_to_coder": "Handoff to coder",
        },
        "role_instruction": (
            "Create a compact implementation plan for the coding task."
        ),
    },
    "coder": {
        "list_fields": [
            "patch_summary",
            "likely_files",
            "constraints",
        ],
        "string_fields": [],
        "section_labels": {
            "patch_summary": "Patch summary",
            "likely_files": "Likely files",
            "constraints": "Constraints",
        },
        "role_instruction": (
            "Describe the smallest patch that satisfies the task."
        ),
    },
    "tester": {
        "list_fields": [
            "verification_plan",
            "failure_checks",
        ],
        "string_fields": [
            "verdict",
        ],
        "section_labels": {
            "verification_plan": "Verification plan",
            "failure_checks": "Failure checks",
            "verdict": "Verdict",
        },
        "role_instruction": (
            "Describe how you would verify the change and summarize the test verdict."
        ),
    },
    "reviewer": {
        "list_fields": [
            "review_summary",
            "risks",
        ],
        "string_fields": [
            "decision",
        ],
        "section_labels": {
            "review_summary": "Review summary",
            "risks": "Risks",
            "decision": "Decision",
        },
        "role_instruction": (
            "Judge whether the proposed work is minimal, correct, and sufficiently tested."
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

    if role == "reviewer":
        extra_rules.append(
            'Set "decision" to exactly one of: "Approve", "Request changes", "Needs verification".'
        )
    if role == "tester":
        extra_rules.append(
            'Set "verdict" to a short final status such as "Pass", "Fail", or "Needs verification".'
        )

    rules = " ".join(extra_rules)
    return (
        f"You are the {role} in a five-layer coding MAS. "
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


def normalize_decision(value: Any) -> str:
    text = coerce_string(value).lower()
    if "request" in text and "change" in text:
        return "Request changes"
    if "need" in text and "verification" in text:
        return "Needs verification"
    if "approve" in text:
        return "Approve"
    return "Needs verification"


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
                remainder = line[len(prefix) :].strip()
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
    source: dict[str, Any]

    if parsed is not None:
        source = parsed
    else:
        source = extract_sectioned_fields(role, raw_output)

    artifact = empty_artifact_for_role(role)

    for field in spec["list_fields"]:
        artifact[field] = coerce_list(source.get(field))

    for field in spec["string_fields"]:
        artifact[field] = coerce_string(source.get(field))

    if role == "reviewer":
        artifact["decision"] = normalize_decision(source.get("decision"))

    if role == "tester" and not artifact["verdict"]:
        artifact["verdict"] = "Needs verification"

    return artifact, dump_artifact(artifact)


def simulate_role_output(role: str, state: FiveLayerState) -> str:
    if role == "planner":
        artifact = {
            "plan": [
                "Inspect the relevant module and test layout.",
                "Implement the smallest change that satisfies the task.",
                "Add or update focused tests.",
                "Run the relevant test subset.",
            ],
            "success_criteria": list(state["acceptance_criteria"]),
            "risks": list(state["risk_notes"]),
            "handoff_to_coder": [
                "Prefer a minimal patch.",
                "Avoid unrelated refactors.",
            ],
        }
        return dump_artifact(artifact)

    if role == "coder":
        artifact = {
            "patch_summary": [
                "Make a minimal targeted code change.",
                "Add or update focused unit tests.",
                "Keep public API and unrelated logic unchanged.",
            ],
            "likely_files": [
                "source module under change",
                "matching test module",
            ],
            "constraints": list(state["risk_notes"]),
        }
        return dump_artifact(artifact)

    if role == "tester":
        artifact = {
            "verification_plan": [
                "Run the focused unit tests for the touched module.",
                "Re-run relevant regression coverage.",
                "Confirm no unrelated cases regress.",
            ],
            "failure_checks": list(state["acceptance_criteria"]),
            "verdict": "Pass",
        }
        return dump_artifact(artifact)

    if role == "reviewer":
        artifact = {
            "review_summary": [
                "Patch scope appears minimal.",
                "Acceptance criteria are addressed.",
                "Testing strategy is proportionate to the change.",
            ],
            "risks": [
                "Real tool-backed verification is still needed before merging.",
            ],
            "decision": "Approve",
        }
        return dump_artifact(artifact)

    raise ValueError(f"Unsupported role: {role}")

def augment_coding_tester_artifact(
    artifact: dict[str, Any],
    test_run_result: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(artifact)
    verification_plan = list(updated.get("verification_plan", []))
    verification_plan.append(
        f"Run real test command: {test_run_result['command']}"
    )
    updated["verification_plan"] = verification_plan

    failure_checks = list(updated.get("failure_checks", []))
    if test_run_result["passed"]:
        updated["verdict"] = "Pass"
    elif test_run_result["timeout"]:
        failure_checks.append("Real test command timed out.")
        updated["verdict"] = "Fail"
    else:
        failure_checks.append(
            f"Real test command failed with exit code {test_run_result['exit_code']}."
        )
        updated["verdict"] = "Fail"

    if test_run_result.get("stderr_tail") and not test_run_result["passed"]:
        first_line = test_run_result["stderr_tail"].splitlines()[0].strip()
        if first_line:
            failure_checks.append(f"stderr: {first_line}")

    updated["failure_checks"] = failure_checks
    return updated


class CodingAgentDemo(FiveLayerDemo):
    def resolve_access_mode(
        self,
        scenario,
        repo_path: str | None,
        effective_test_command: str | None,
    ) -> str:
        del scenario
        return "read_only" if repo_path or effective_test_command else "synthetic"

    def resolve_available_tools(
        self,
        scenario,
        repo_access_mode: str,
        repo_path: str | None,
        effective_test_command: str | None,
    ) -> list[str]:
        del repo_path, effective_test_command
        if repo_access_mode == "read_only":
            return ["search", "read_file", "run_tests"]
        return list(scenario.available_tools)

    def extend_perception_observations(
        self,
        state: FiveLayerState,
        repo_snapshot: dict[str, Any],
        read_only_files: list[dict[str, str]],
    ) -> list[str]:
        del repo_snapshot, read_only_files
        observations: list[str] = []
        if state.get("test_command"):
            observations.append(f"Configured test command: {state['test_command']}")
        return observations

    def extend_shared_memory(
        self,
        state: FiveLayerState,
    ) -> dict[str, Any]:
        shared: dict[str, Any] = {}
        if state.get("test_command"):
            shared["test_command"] = state["test_command"]
        return shared

    def extend_brief_sections(
        self,
        role: str,
        state: FiveLayerState,
    ) -> list[str]:
        sections: list[str] = []
        if role == "tester" and state.get("test_command"):
            sections.append(f"Test command to execute:\n{state['test_command']}")

        if (
            "tester" in self.role_order
            and role in self.role_order
            and self.role_order.index(role) > self.role_order.index("tester")
            and state.get("test_run_result")
        ):
            sections.append(
                f"Latest test execution:\n{self.format_test_run_result(state['test_run_result'])}"
            )
        return sections

    def postprocess_role_execution(
        self,
        role: str,
        state: FiveLayerState,
        artifact: dict[str, Any],
        normalized_output: str,
    ) -> tuple[dict[str, Any], str, dict[str, Any], list[dict[str, Any]]]:
        if role != "tester" or not state.get("test_command"):
            return artifact, normalized_output, {}, []

        repo_path = self.resolve_repo_path(state.get("repo_path")) or REPO_ROOT
        test_run_result = self.execute_test_command(
            repo_path=repo_path,
            test_command=state["test_command"],
            timeout_sec=state.get("test_timeout_sec", 120),
        )
        artifact = augment_coding_tester_artifact(
            artifact,
            test_run_result,
        )
        normalized_output = json.dumps(artifact, indent=2, ensure_ascii=False)
        trace_event = {
            "event": "test_command_executed",
            "role": role,
            "summary": (
                f"passed={test_run_result.get('passed', False)} "
                f"timeout={test_run_result.get('timeout', False)} "
                f"command={test_run_result.get('command', '')}"
            ),
            "result": test_run_result,
        }
        return artifact, normalized_output, {"test_run_result": test_run_result}, [trace_event]


APP = CodingAgentDemo(
    name="coding_agent",
    description="First coding-agent demo in the five-layer MAS framework.",
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
