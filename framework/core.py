from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"


@dataclass
class Scenario:
    id: str
    title: str
    user_task: str
    repository_context: str
    acceptance_criteria: list[str]
    available_tools: list[str]
    risk_notes: list[str]
    test_command: str | None = None
    start_role: str | None = None
    seed_context: dict[str, Any] | None = None
    seed_role_outputs: dict[str, str] | None = None
    seed_role_artifacts: dict[str, dict[str, Any]] | None = None
    seed_test_run_result: dict[str, Any] | None = None
    seed_tool_events: list[dict[str, Any]] | None = None
    seed_action_trace: list[dict[str, Any]] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scenario":
        return cls(**data)


class FiveLayerState(TypedDict, total=False):
    scenario_id: str
    title: str
    task: str
    repository_context: str
    acceptance_criteria: list[str]
    available_tools: list[str]
    risk_notes: list[str]
    start_role: str | None
    repo_path: str | None
    repo_access_mode: Literal["synthetic", "read_only"]
    live_repository_context: str
    live_file_context: str
    repo_snapshot: dict[str, Any]
    read_only_files: list[dict[str, Any]]
    test_command: str | None
    test_timeout_sec: int
    test_run_result: dict[str, Any]
    seed_context: dict[str, Any]
    seed_role_outputs: dict[str, str]
    seed_role_artifacts: dict[str, dict[str, Any]]
    seed_test_run_result: dict[str, Any]
    seed_tool_events: list[dict[str, Any]]
    seed_action_trace: list[dict[str, Any]]
    observations: list[str]
    shared_memory: dict[str, Any]
    next_role_index: int
    active_role: str
    agent_brief: str
    latest_output: str
    latest_artifact: dict[str, Any]
    tool_events: list[dict[str, Any]]
    action_trace: list[dict[str, Any]]
    role_outputs: dict[str, str]
    role_artifacts: dict[str, dict[str, Any]]
    execution_log: list[str]
    workflow_status: Literal["running", "completed"]
    final_report: str
    invoke_model: bool
    model_name: str | None


RoleSimulator = Callable[[str, FiveLayerState], str]
RoleOutputNormalizer = Callable[[str, str, FiveLayerState], tuple[dict[str, Any], str]]


def bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def format_role_label(role: str) -> str:
    return role.replace("_", " ").title()


def append_log(state: FiveLayerState, message: str) -> list[str]:
    return [*state.get("execution_log", []), message]


def append_trace(
    state: FiveLayerState,
    event: dict[str, Any],
) -> list[dict[str, Any]]:
    return [*state.get("action_trace", []), event]


def parse_env_line(raw_line: str) -> tuple[str, str] | None:
    line = raw_line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        return None

    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()

    if not key:
        return None

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]

    return key, value


def load_repo_env(env_path: Path = ENV_PATH) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = parse_env_line(raw_line)
        if parsed is None:
            continue

        key, value = parsed
        os.environ.setdefault(key, value)


def first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def coerce_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts).strip()
    return str(content)


def tail_lines(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])


def truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def compact_output(text: str, max_lines: int = 30, max_chars: int = 4000) -> str:
    return truncate_text(tail_lines(text.strip(), max_lines), max_chars)


def run_process(
    argv: list[str],
    cwd: Path,
    timeout_sec: int,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        return {
            "command": argv,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": argv,
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timeout": True,
        }


def run_shell_command(
    command: str,
    cwd: Path,
    timeout_sec: int,
) -> dict[str, Any]:
    if os.name == "nt":
        argv = ["powershell", "-NoProfile", "-Command", command]
    else:
        argv = ["/bin/sh", "-lc", command]
    result = run_process(argv, cwd=cwd, timeout_sec=timeout_sec)
    result["shell_command"] = command
    return result


def iter_repo_files(repo_path: Path) -> list[str]:
    ignore_dirs = {
        ".git",
        ".hg",
        ".svn",
        ".mypy_cache",
        ".pytest_cache",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
    }

    rg = shutil.which("rg")
    if rg:
        result = run_process([rg, "--files"], cwd=repo_path, timeout_sec=20)
        if not result["timeout"] and result["exit_code"] == 0:
            return [
                line.replace("\\", "/")
                for line in result["stdout"].splitlines()
                if line.strip()
            ]

    files: list[str] = []
    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [directory for directory in dirs if directory not in ignore_dirs]
        for filename in filenames:
            full_path = Path(root) / filename
            files.append(str(full_path.relative_to(repo_path)).replace("\\", "/"))
    return sorted(files)


def format_kv_section(title: str, body: str) -> str:
    if not body:
        return ""
    return f"{title}:\n{body}"


def compact_one_line(text: str, max_chars: int = 160) -> str:
    collapsed = " ".join((text or "").split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."


TEXT_FILE_EXTENSIONS = {
    ".py",
    ".pyi",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".sh",
    ".ps1",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
}

COMMON_QUERY_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "into",
    "your",
    "there",
    "already",
    "under",
    "write",
    "small",
    "tests",
    "test",
    "module",
    "helper",
    "function",
    "task",
    "file",
    "files",
    "python",
    "package",
    "codebase",
    "existing",
    "common",
    "cases",
    "case",
}


def extract_query_keywords(*texts: str) -> list[str]:
    tokens: list[str] = []
    for text in texts:
        tokens.extend(
            token.lower()
            for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text or "")
        )

    deduped: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in COMMON_QUERY_STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


def score_repo_path(path: str, keywords: list[str]) -> int:
    path_lower = path.lower()
    filename = Path(path).stem.lower()
    score = 0

    for keyword in keywords:
        if keyword == filename:
            score += 8
        elif keyword in filename:
            score += 5
        elif keyword in path_lower:
            score += 3

    if path_lower.endswith(".py"):
        score += 2
    if "/tests/" in f"/{path_lower}" or Path(path_lower).name.startswith("test_"):
        score += 2
    return score


def format_numbered_snippet(
    text: str,
    max_lines: int = 60,
    max_chars: int = 1600,
) -> str:
    raw_lines = text.splitlines()
    lines = raw_lines[:max_lines]
    numbered = [f"{index:>4} {line}" for index, line in enumerate(lines, start=1)]
    snippet = "\n".join(numbered)
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rstrip()
    truncated = len(raw_lines) > max_lines or len(text) > max_chars
    if truncated:
        suffix = "\n..."
        if not snippet.endswith(suffix):
            snippet += suffix
    return snippet


def extract_json_object(raw_output: str) -> dict[str, Any] | None:
    candidates = [raw_output.strip()]
    fence_match = re.search(
        r"```(?:json)?\s*(.*?)```",
        raw_output,
        re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        candidates.append(fence_match.group(1).strip())

    start = raw_output.find("{")
    end = raw_output.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(raw_output[start : end + 1].strip())

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


load_repo_env()


class MiniMaxAnthropicAdapter:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0,
        max_tokens: int = 2048,
    ) -> None:
        import anthropic

        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def invoke(self, messages: list[Any]):
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, str]] = []

        for message in messages:
            text = coerce_message_text(message.content)

            if isinstance(message, SystemMessage):
                system_parts.append(text)
            elif isinstance(message, HumanMessage):
                anthropic_messages.append({"role": "user", "content": text})
            elif isinstance(message, AIMessage):
                anthropic_messages.append({"role": "assistant", "content": text})
            else:
                anthropic_messages.append({"role": "user", "content": text})

        request_kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": anthropic_messages,
        }
        if system_parts:
            request_kwargs["system"] = "\n\n".join(system_parts)

        response = self.client.messages.create(**request_kwargs)

        text_parts: list[str] = []
        thinking_parts: list[str] = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(str(block.text))
            elif hasattr(block, "text"):
                text_parts.append(str(block.text))
            elif hasattr(block, "thinking"):
                thinking_parts.append(str(block.thinking))

        parts = text_parts if text_parts else thinking_parts
        return SimpleNamespace(content="\n".join(part for part in parts if part).strip())


@dataclass
class FiveLayerDemo:
    name: str
    description: str
    cases_path: Path
    role_order: list[str]
    role_system_prompts: dict[str, str]
    simulate_role_output: RoleSimulator
    normalize_role_output: RoleOutputNormalizer | None = None

    def load_scenarios(self) -> dict[str, Scenario]:
        data = json.loads(self.cases_path.read_text(encoding="utf-8"))
        scenarios = [Scenario.from_dict(item) for item in data]
        return {scenario.id: scenario for scenario in scenarios}

    def load_seed_payload(self, seed_file: str | None) -> dict[str, Any]:
        if not seed_file:
            return {}
        seed_path = Path(seed_file).expanduser().resolve()
        if not seed_path.exists():
            raise FileNotFoundError(f"Seed file does not exist: {seed_path}")
        payload = json.loads(seed_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("Seed file must contain a top-level JSON object.")
        return payload

    def validate_seed_payload(self, seed_payload: dict[str, Any]) -> None:
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
        self,
        scenario: Scenario,
        seed_payload: dict[str, Any] | None = None,
        start_role: str | None = None,
    ) -> dict[str, Any]:
        if seed_payload is not None:
            self.validate_seed_payload(seed_payload)
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
        self,
        seed_role_outputs: dict[str, str],
        seed_role_artifacts: dict[str, dict[str, Any]],
    ) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for role, output in seed_role_outputs.items():
            if role in self.role_order:
                normalized[role] = str(output)
        for role, artifact in seed_role_artifacts.items():
            if role in self.role_order and role not in normalized:
                normalized[role] = json.dumps(artifact, indent=2, ensure_ascii=False)
        return normalized

    def resolve_start_role_index(
        self,
        start_role: str | None,
        seeded_roles: set[str],
    ) -> int:
        if start_role is not None:
            if start_role not in self.role_order:
                raise KeyError(f"Unknown start role: {start_role}")
            return self.role_order.index(start_role)

        for index, role in enumerate(self.role_order):
            if role not in seeded_roles:
                return index
        return len(self.role_order)

    def format_seed_context(self, seed_context: dict[str, Any]) -> str:
        sections: list[str] = []
        for key, value in seed_context.items():
            label = key.replace("_", " ").title()
            if isinstance(value, str):
                body = value
            else:
                body = json.dumps(value, indent=2, ensure_ascii=False)
            sections.append(format_kv_section(label, body))
        return "\n\n".join(section for section in sections if section)

    def resolve_repo_path(self, repo_path: str | None) -> Path | None:
        if not repo_path:
            return None
        resolved = Path(repo_path).expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Repo path does not exist: {resolved}")
        if not resolved.is_dir():
            raise NotADirectoryError(f"Repo path is not a directory: {resolved}")
        return resolved

    def collect_repo_snapshot(self, repo_path: Path) -> dict[str, Any]:
        files = iter_repo_files(repo_path)
        git_root_result = run_process(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=repo_path,
            timeout_sec=20,
        )
        git_status_result = run_process(
            ["git", "status", "--short"],
            cwd=repo_path,
            timeout_sec=20,
        )

        git_root = ""
        if not git_root_result["timeout"] and git_root_result["exit_code"] == 0:
            git_root = git_root_result["stdout"].strip()

        git_status = ""
        if not git_status_result["timeout"] and git_status_result["exit_code"] == 0:
            git_status = compact_output(git_status_result["stdout"], max_lines=40)

        python_files = [path for path in files if path.endswith(".py")][:25]
        test_files = [
            path
            for path in files
            if "/tests/" in f"/{path}" or Path(path).name.startswith("test_")
        ][:25]

        return {
            "repo_path": str(repo_path),
            "git_root": git_root,
            "git_status": git_status,
            "file_count": len(files),
            "file_sample": files[:40],
            "python_files_sample": python_files,
            "test_files_sample": test_files,
        }

    def read_repo_text_file(
        self,
        repo_path: Path,
        relative_path: str,
        max_chars: int = 2400,
    ) -> str | None:
        file_path = (repo_path / relative_path).resolve()
        try:
            file_path.relative_to(repo_path.resolve())
        except ValueError:
            return None

        if not file_path.exists() or not file_path.is_file():
            return None
        if file_path.suffix.lower() not in TEXT_FILE_EXTENSIONS:
            return None

        try:
            if file_path.stat().st_size > 200_000:
                return None
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None

        return content[:max_chars]

    def select_files_for_context(
        self,
        snapshot: dict[str, Any],
        state: FiveLayerState,
        max_files: int = 4,
    ) -> list[str]:
        keywords = extract_query_keywords(
            state.get("task", ""),
            state.get("repository_context", ""),
            *state.get("acceptance_criteria", []),
        )

        ranked: list[tuple[int, str]] = []
        seen: set[str] = set()
        candidates = [
            *snapshot.get("python_files_sample", []),
            *snapshot.get("test_files_sample", []),
            *snapshot.get("file_sample", []),
        ]
        for path in candidates:
            normalized = str(path).replace("\\", "/")
            if normalized in seen:
                continue
            seen.add(normalized)
            ranked.append((score_repo_path(normalized, keywords), normalized))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        selected = [path for score, path in ranked if score > 0][:max_files]
        if selected:
            return selected

        fallback: list[str] = []
        python_files = [
            str(path).replace("\\", "/")
            for path in snapshot.get("python_files_sample", [])
        ]
        non_test_python = [
            path
            for path in python_files
            if "/tests/" not in f"/{path}" and not Path(path).name.startswith("test_")
        ]
        test_files = [
            str(path).replace("\\", "/")
            for path in snapshot.get("test_files_sample", [])
        ]

        for path in [*non_test_python[:2], *test_files[:2], *python_files, *snapshot.get("file_sample", [])]:
            normalized = str(path).replace("\\", "/")
            if normalized not in fallback:
                fallback.append(normalized)
            if len(fallback) >= max_files:
                return fallback
        return fallback

    def collect_read_only_files(
        self,
        repo_path: Path,
        snapshot: dict[str, Any],
        state: FiveLayerState,
        max_files: int = 4,
    ) -> list[dict[str, str]]:
        selected_paths = self.select_files_for_context(
            snapshot=snapshot,
            state=state,
            max_files=max_files,
        )
        read_only_files: list[dict[str, str]] = []

        for relative_path in selected_paths:
            content = self.read_repo_text_file(repo_path, relative_path)
            if not content:
                continue
            read_only_files.append(
                {
                    "path": relative_path,
                    "snippet": format_numbered_snippet(content),
                }
            )
        return read_only_files

    def format_read_only_files(self, files: list[dict[str, str]]) -> str:
        sections: list[str] = []
        for item in files:
            sections.append(
                "\n".join(
                    [
                        f"Path: {item['path']}",
                        "Snippet:",
                        item["snippet"],
                    ]
                )
            )
        return "\n\n".join(sections)

    def summarize_artifact(self, role: str, artifact: dict[str, Any]) -> str:
        if not artifact:
            return f"{role} returned an empty artifact."

        interesting_fields: list[str] = []
        for key, value in artifact.items():
            if isinstance(value, list) and value:
                interesting_fields.append(f"{key}={len(value)} items")
            elif isinstance(value, str) and value:
                interesting_fields.append(f"{key}={value}")

        if interesting_fields:
            return f"{role} artifact: " + ", ".join(interesting_fields[:4])
        return f"{role} artifact keys: {', '.join(sorted(artifact)[:6])}"

    def summarize_tool_request(self, request: dict[str, Any]) -> str:
        tool = request.get("tool", "")
        if tool == "search":
            return f"search query={request.get('query', '')}"
        if tool == "read_file":
            return f"read_file path={request.get('path', '')}"
        return compact_one_line(json.dumps(request, ensure_ascii=False))

    def summarize_tool_result(self, result: dict[str, Any]) -> str:
        tool = result.get("tool", "")
        if tool == "search":
            return f"search returned {len(result.get('matches', []))} matches"
        if tool == "read_file":
            if result.get("found"):
                return f"read_file returned snippet for {result.get('path', '')}"
            return f"read_file could not read {result.get('path', '')}"
        return compact_one_line(json.dumps(result, ensure_ascii=False))

    def format_action_trace(self, action_trace: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        for index, event in enumerate(action_trace, start=1):
            label = event.get("event", "event").replace("_", " ")
            role = event.get("role")
            summary = event.get("summary", "")
            parts = [f"{index}. {label.title()}"]
            if role:
                parts.append(f"[{role}]")
            line = " ".join(parts)
            if summary:
                line += f": {summary}"
            lines.append(line)
        return "\n".join(lines)

    def parse_tool_request(
        self,
        raw_output: str,
        available_tools: list[str],
    ) -> dict[str, Any] | None:
        parsed = extract_json_object(raw_output)
        if not parsed:
            return None

        request = parsed.get("tool_request", parsed)
        if not isinstance(request, dict):
            return None

        tool = request.get("tool")
        if not isinstance(tool, str):
            return None
        if tool not in available_tools:
            return None
        if tool not in {"search", "read_file"}:
            return None

        normalized: dict[str, Any] = {"tool": tool}
        if tool == "search":
            query = request.get("query")
            if not isinstance(query, str) or not query.strip():
                return None
            normalized["query"] = query.strip()
            try:
                top_k = int(request.get("top_k", 8))
            except (TypeError, ValueError):
                top_k = 8
            normalized["top_k"] = max(1, min(top_k, 12))
            return normalized

        path = request.get("path")
        if not isinstance(path, str) or not path.strip():
            return None
        normalized["path"] = path.strip().replace("\\", "/")
        return normalized

    def search_repo(
        self,
        repo_path: Path,
        query: str,
        top_k: int = 8,
    ) -> dict[str, Any]:
        files = iter_repo_files(repo_path)
        query_lower = query.lower()
        matches: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()

        for path in files:
            if query_lower in path.lower():
                key = ("path", path)
                if key in seen:
                    continue
                seen.add(key)
                matches.append({"kind": "path", "path": path})
                if len(matches) >= top_k:
                    return {
                        "tool": "search",
                        "query": query,
                        "matches": matches,
                        "truncated": True,
                    }

        rg = shutil.which("rg")
        if rg:
            result = run_process(
                [rg, "-n", "-S", "--color", "never", query, "."],
                cwd=repo_path,
                timeout_sec=20,
            )
            if not result["timeout"] and result["exit_code"] in {0, 1}:
                for raw_line in result["stdout"].splitlines():
                    if len(matches) >= top_k:
                        break
                    match = re.match(r"^(.*?):(\d+):(.*)$", raw_line)
                    if not match:
                        continue
                    rel_path = match.group(1).removeprefix("./").replace("\\", "/")
                    line_no = int(match.group(2))
                    text = match.group(3).strip()
                    key = ("content", rel_path, line_no, text)
                    if key in seen:
                        continue
                    seen.add(key)
                    matches.append(
                        {
                            "kind": "content",
                            "path": rel_path,
                            "line": line_no,
                            "text": truncate_text(text, 200),
                        }
                    )
            return {
                "tool": "search",
                "query": query,
                "matches": matches,
                "truncated": len(matches) >= top_k,
            }

        for path in files:
            if len(matches) >= top_k:
                break
            content = self.read_repo_text_file(repo_path, path, max_chars=10_000)
            if not content:
                continue
            for line_no, line in enumerate(content.splitlines(), start=1):
                if query_lower not in line.lower():
                    continue
                key = ("content", path, line_no, line.strip())
                if key in seen:
                    continue
                seen.add(key)
                matches.append(
                    {
                        "kind": "content",
                        "path": path,
                        "line": line_no,
                        "text": truncate_text(line.strip(), 200),
                    }
                )
                if len(matches) >= top_k:
                    break

        return {
            "tool": "search",
            "query": query,
            "matches": matches,
            "truncated": len(matches) >= top_k,
        }

    def execute_read_only_tool(
        self,
        repo_path: Path,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        tool = request["tool"]
        if tool == "search":
            return self.search_repo(
                repo_path=repo_path,
                query=request["query"],
                top_k=request.get("top_k", 8),
            )

        if tool == "read_file":
            content = self.read_repo_text_file(repo_path, request["path"], max_chars=4000)
            if content is None:
                return {
                    "tool": "read_file",
                    "path": request["path"],
                    "found": False,
                    "snippet": "",
                }
            return {
                "tool": "read_file",
                "path": request["path"],
                "found": True,
                "snippet": format_numbered_snippet(content, max_lines=120, max_chars=3200),
            }

        return {"tool": tool, "error": "unsupported"}

    def format_tool_result(self, result: dict[str, Any]) -> str:
        tool = result.get("tool", "")
        if tool == "search":
            lines = [f"Search query: {result.get('query', '')}"]
            matches = result.get("matches", [])
            if not matches:
                lines.append("No matches found.")
            else:
                for item in matches:
                    if item.get("kind") == "path":
                        lines.append(f"- path: {item['path']}")
                    else:
                        lines.append(
                            f"- {item['path']}:{item['line']}: {item.get('text', '')}"
                        )
            if result.get("truncated"):
                lines.append("- results truncated")
            return "\n".join(lines)

        if tool == "read_file":
            if not result.get("found"):
                return f"Path: {result.get('path', '')}\nFile not found or not readable."
            return "\n".join(
                [
                    f"Path: {result.get('path', '')}",
                    "Snippet:",
                    result.get("snippet", ""),
                ]
            )

        return json.dumps(result, indent=2, ensure_ascii=False)

    def append_tool_result_to_brief(
        self,
        brief: str,
        request: dict[str, Any],
        result: dict[str, Any],
        round_index: int,
    ) -> str:
        section = "\n\n".join(
            [
                f"Tool round {round_index}",
                f"Tool request:\n{json.dumps(request, indent=2, ensure_ascii=False)}",
                f"Tool result:\n{self.format_tool_result(result)}",
                "If you have enough context now, return the final role JSON only. "
                "If you still need more repo context, you may issue one more tool_request JSON.",
            ]
        )
        return brief + "\n\n" + section

    def invoke_role_with_read_only_tools(
        self,
        role: str,
        state: FiveLayerState,
    ) -> tuple[str, str, list[dict[str, Any]], list[dict[str, Any]]]:
        repo_path = self.resolve_repo_path(state.get("repo_path"))
        if repo_path is None:
            return self.invoke_role_model(role, state), state["agent_brief"], [], []

        current_brief = state["agent_brief"]
        tool_events: list[dict[str, Any]] = []
        trace_events: list[dict[str, Any]] = []
        seen_requests: set[str] = set()
        max_tool_rounds = 3

        for round_index in range(1, max_tool_rounds + 1):
            raw_output = self.invoke_role_model(
                role,
                state,
                agent_brief=current_brief,
            )
            request = self.parse_tool_request(
                raw_output,
                state.get("available_tools", []),
            )
            if request is None:
                return raw_output, current_brief, tool_events, trace_events

            request_key = json.dumps(request, sort_keys=True, ensure_ascii=False)
            if request_key in seen_requests:
                trace_events.append(
                    {
                        "event": "tool_request_rejected",
                        "role": role,
                        "round": round_index,
                        "summary": "duplicate tool request rejected",
                        "request": request,
                    }
                )
                current_brief = (
                    current_brief
                    + "\n\nTool request rejected: duplicate request. "
                    "Return final role JSON now without another tool_request."
                )
                continue
            seen_requests.add(request_key)
            trace_events.append(
                {
                    "event": "tool_request",
                    "role": role,
                    "round": round_index,
                    "summary": self.summarize_tool_request(request),
                    "request": request,
                }
            )

            result = self.execute_read_only_tool(repo_path, request)
            tool_events.append(
                {
                    "role": role,
                    "request": request,
                    "result": result,
                }
            )
            trace_events.append(
                {
                    "event": "tool_result",
                    "role": role,
                    "round": round_index,
                    "summary": self.summarize_tool_result(result),
                    "request": request,
                    "result": result,
                }
            )
            current_brief = self.append_tool_result_to_brief(
                current_brief,
                request,
                result,
                round_index=round_index,
            )

        final_output = self.invoke_role_model(role, state, agent_brief=current_brief)
        return final_output, current_brief, tool_events, trace_events

    def format_repo_snapshot(self, snapshot: dict[str, Any]) -> str:
        sections = [
            f"Repo path: {snapshot.get('repo_path', '')}",
            f"Git root: {snapshot.get('git_root', '(not available)')}",
            f"File count: {snapshot.get('file_count', 0)}",
        ]

        if snapshot.get("git_status"):
            sections.append(format_kv_section("Git status", snapshot["git_status"]))
        if snapshot.get("file_sample"):
            sections.append(
                format_kv_section("File sample", bullet_list(snapshot["file_sample"]))
            )
        if snapshot.get("test_files_sample"):
            sections.append(
                format_kv_section(
                    "Test file sample",
                    bullet_list(snapshot["test_files_sample"]),
                )
            )

        return "\n\n".join(section for section in sections if section)

    def execute_test_command(
        self,
        repo_path: Path,
        test_command: str,
        timeout_sec: int,
    ) -> dict[str, Any]:
        result = run_shell_command(
            test_command,
            cwd=repo_path,
            timeout_sec=timeout_sec,
        )
        return {
            "command": test_command,
            "cwd": str(repo_path),
            "passed": result["exit_code"] == 0 and not result["timeout"],
            "exit_code": result["exit_code"],
            "timeout": result["timeout"],
            "stdout_tail": compact_output(result["stdout"]),
            "stderr_tail": compact_output(result["stderr"]),
        }

    def format_test_run_result(self, result: dict[str, Any]) -> str:
        exit_code = result.get("exit_code")
        sections = [
            f"Command: {result.get('command', '')}",
            f"CWD: {result.get('cwd', '')}",
            f"Passed: {result.get('passed', False)}",
            f"Exit code: {exit_code if exit_code is not None else '(timeout)'}",
            f"Timed out: {result.get('timeout', False)}",
        ]
        if result.get("stdout_tail"):
            sections.append(format_kv_section("stdout tail", result["stdout_tail"]))
        if result.get("stderr_tail"):
            sections.append(format_kv_section("stderr tail", result["stderr_tail"]))
        return "\n\n".join(section for section in sections if section)

    def augment_tester_artifact_with_test_result(
        self,
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

    def build_model(self, model_name: str | None):
        minimax_base_url = first_env("MINIMAX_BASE_URL", "ANTHROPIC_BASE_URL")
        minimax_api_key = first_env(
            "MINIMAX_API_KEY",
            "MINIMAX_AUTH_TOKEN",
        )
        minimax_base_url_is_selected = bool(
            minimax_base_url and "minimax" in minimax_base_url.lower()
        )

        if minimax_api_key or minimax_base_url_is_selected:
            resolved_api_key = minimax_api_key or first_env(
                "ANTHROPIC_API_KEY",
                "ANTHROPIC_AUTH_TOKEN",
            )
            if resolved_api_key:
                return MiniMaxAnthropicAdapter(
                    api_key=resolved_api_key,
                    base_url=minimax_base_url or "https://api.minimax.io/anthropic",
                    model=model_name
                    or first_env("MINIMAX_MODEL", "ANTHROPIC_MODEL")
                    or "MiniMax-M2.5",
                    temperature=0,
                    max_tokens=env_int("MINIMAX_MAX_TOKENS", 2048),
                )

        if os.getenv("ANTHROPIC_API_KEY"):
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=model_name or "claude-3-5-sonnet-latest",
                temperature=0,
            )

        if os.getenv("OPENAI_API_KEY"):
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model_name or "gpt-4o-mini",
                temperature=0,
            )

        return None

    def perception_node(self, state: FiveLayerState) -> FiveLayerState:
        repo_snapshot: dict[str, Any] = {}
        live_repository_context = ""
        live_file_context = ""
        read_only_files: list[dict[str, str]] = []
        repo_path = self.resolve_repo_path(state.get("repo_path"))
        if repo_path is not None:
            repo_snapshot = self.collect_repo_snapshot(repo_path)
            live_repository_context = self.format_repo_snapshot(repo_snapshot)
            read_only_files = self.collect_read_only_files(
                repo_path=repo_path,
                snapshot=repo_snapshot,
                state=state,
            )
            live_file_context = self.format_read_only_files(read_only_files)

        observations = [
            f"Task: {state['task']}",
            f"Repository context: {state['repository_context']}",
            f"Available tools: {', '.join(state['available_tools'])}",
            f"Acceptance criteria count: {len(state['acceptance_criteria'])}",
        ]
        if repo_snapshot:
            observations.append(f"Live repo path: {repo_snapshot['repo_path']}")
            observations.append(f"Live repo file count: {repo_snapshot['file_count']}")
        if read_only_files:
            observations.append(
                f"Read-only file excerpts collected: {len(read_only_files)}"
            )
        if state.get("test_command"):
            observations.append(f"Configured test command: {state['test_command']}")

        return {
            "observations": observations,
            "repo_snapshot": repo_snapshot,
            "live_repository_context": live_repository_context,
            "read_only_files": read_only_files,
            "live_file_context": live_file_context,
            "action_trace": append_trace(
                state,
                {
                    "event": "workflow_started",
                    "summary": compact_one_line(
                        f"scenario={state['scenario_id']} repo_access_mode={state.get('repo_access_mode', 'synthetic')}"
                    ),
                },
            ),
            "execution_log": append_log(
                state,
                "perception: normalized task and repository context",
            ),
        }

    def coordination_prepare_node(self, state: FiveLayerState) -> FiveLayerState:
        seed_role_artifacts = {
            role: deepcopy(artifact)
            for role, artifact in state.get("seed_role_artifacts", {}).items()
            if role in self.role_order
        }
        seed_role_outputs = self.normalize_seed_role_outputs(
            state.get("seed_role_outputs", {}),
            seed_role_artifacts,
        )
        seeded_roles = set(seed_role_outputs) | set(seed_role_artifacts)
        next_role_index = self.resolve_start_role_index(
            state.get("start_role"),
            seeded_roles,
        )

        shared_memory = {
            "task": state["task"],
            "acceptance_criteria": state["acceptance_criteria"],
            "role_outputs": dict(seed_role_outputs),
            "role_artifacts": dict(seed_role_artifacts),
        }
        if state.get("repo_snapshot"):
            shared_memory["repo_snapshot"] = state["repo_snapshot"]
        if state.get("read_only_files"):
            shared_memory["read_only_files"] = state["read_only_files"]
        if state.get("test_command"):
            shared_memory["test_command"] = state["test_command"]
        if state.get("seed_context"):
            shared_memory["seed_context"] = deepcopy(state["seed_context"])
        if state.get("seed_tool_events"):
            shared_memory["tool_events"] = deepcopy(state["seed_tool_events"])
        if state.get("seed_test_run_result"):
            shared_memory["test_run_result"] = deepcopy(state["seed_test_run_result"])

        action_trace = list(state.get("action_trace", []))
        action_trace.extend(deepcopy(state.get("seed_action_trace", [])))
        if seeded_roles or state.get("seed_context") or state.get("start_role"):
            action_trace.append(
                {
                    "event": "seed_loaded",
                    "summary": compact_one_line(
                        " ".join(
                            part
                            for part in [
                                f"seeded_roles={','.join(sorted(seeded_roles))}"
                                if seeded_roles
                                else "",
                                f"start_role={state.get('start_role')}"
                                if state.get("start_role")
                                else "",
                            ]
                            if part
                        )
                        or "seed payload loaded"
                    ),
                }
            )
        return {
            "shared_memory": shared_memory,
            "role_outputs": dict(seed_role_outputs),
            "role_artifacts": dict(seed_role_artifacts),
            "tool_events": deepcopy(state.get("seed_tool_events", [])),
            "test_run_result": deepcopy(state.get("seed_test_run_result", {})),
            "action_trace": action_trace,
            "next_role_index": next_role_index,
            "workflow_status": "running",
            "execution_log": append_log(
                state,
                "coordination: initialized shared memory",
            ),
        }

    def behavior_route_node(self, state: FiveLayerState) -> FiveLayerState:
        index = state.get("next_role_index", 0)
        if index >= len(self.role_order):
            completed_trace = append_trace(
                state,
                {
                    "event": "workflow_completed",
                    "summary": "all roles completed",
                },
            )
            final_report = state.get("final_report", "")
            if state.get("role_outputs"):
                final_report = self.build_final_report(
                    {**state, "action_trace": completed_trace},
                    state.get("role_outputs", {}),
                )
            return {
                "active_role": "",
                "workflow_status": "completed",
                "action_trace": completed_trace,
                "final_report": final_report,
                "execution_log": append_log(
                    state,
                    "behavior: workflow marked complete",
                ),
            }

        role = self.role_order[index]
        return {
            "active_role": role,
            "workflow_status": "running",
            "action_trace": append_trace(
                state,
                {
                    "event": "role_selected",
                    "role": role,
                    "summary": f"next_role_index={index}",
                },
            ),
            "execution_log": append_log(
                state,
                f"behavior: selected next role `{role}`",
            ),
        }

    def behavior_route_decision(self, state: FiveLayerState) -> str:
        return "end" if state.get("workflow_status") == "completed" else "continue"

    def build_agent_brief(self, role: str, state: FiveLayerState) -> str:
        prior_outputs = state.get("role_outputs", {})
        role_index = self.role_order.index(role)

        sections = [
            f"Role: {role}",
            f"User task:\n{state['task']}",
            f"Repository context:\n{state['repository_context']}",
            f"Available tools:\n{bullet_list(state.get('available_tools', []))}",
            f"Repo access mode:\n{state.get('repo_access_mode', 'synthetic')}",
            f"Acceptance criteria:\n{bullet_list(state['acceptance_criteria'])}",
            f"Risk notes:\n{bullet_list(state['risk_notes'])}",
        ]
        if state.get("live_repository_context"):
            sections.append(
                f"Live repository snapshot:\n{state['live_repository_context']}"
            )
        if state.get("live_file_context"):
            sections.append(f"Read-only file excerpts:\n{state['live_file_context']}")
        if state.get("seed_context"):
            sections.append(
                f"Seeded evaluation context:\n{self.format_seed_context(state['seed_context'])}"
            )
        if (
            state.get("invoke_model")
            and state.get("repo_access_mode") == "read_only"
            and state.get("repo_path")
        ):
            sections.append(
                "\n".join(
                    [
                        "Read-only tool protocol:",
                        "If you need more repository context, return JSON only in one of these shapes:",
                        '{"tool_request":{"tool":"search","query":"symbol or phrase","top_k":5}}',
                        '{"tool_request":{"tool":"read_file","path":"relative/path.py"}}',
                        "After you receive tool results, return your final role JSON only.",
                    ]
                )
            )
        if role == "tester" and state.get("test_command"):
            sections.append(f"Test command to execute:\n{state['test_command']}")

        prior_roles = self.role_order[:role_index]
        if not prior_roles:
            sections.append("No prior role outputs yet.")
        else:
            for prior_role in prior_roles:
                label = format_role_label(prior_role)
                sections.append(
                    f"{label} output:\n{prior_outputs.get(prior_role, '(missing)')}"
                )

        if (
            "tester" in self.role_order
            and role_index > self.role_order.index("tester")
            and state.get("test_run_result")
        ):
            sections.append(
                f"Latest test execution:\n{self.format_test_run_result(state['test_run_result'])}"
            )

        return "\n\n".join(sections)

    def communication_brief_node(self, state: FiveLayerState) -> FiveLayerState:
        role = state["active_role"]
        agent_brief = self.build_agent_brief(role, state)
        return {
            "agent_brief": agent_brief,
            "action_trace": append_trace(
                state,
                {
                    "event": "brief_built",
                    "role": role,
                    "summary": compact_one_line(agent_brief, max_chars=120),
                },
            ),
            "execution_log": append_log(
                state,
                f"communication: built handoff brief for `{role}`",
            ),
        }

    def invoke_role_model(
        self,
        role: str,
        state: FiveLayerState,
        agent_brief: str | None = None,
    ) -> str:
        model = self.build_model(state.get("model_name"))
        if model is None:
            return self.simulate_role_output(role, state)

        messages = [
            SystemMessage(content=self.role_system_prompts[role]),
            HumanMessage(content=agent_brief or state["agent_brief"]),
        ]
        response = model.invoke(messages)
        content = response.content

        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return coerce_message_text(content)
        return str(content)

    def normalize_role_response(
        self,
        role: str,
        raw_output: str,
        state: FiveLayerState,
    ) -> tuple[dict[str, Any], str]:
        if self.normalize_role_output is None:
            return {"raw_output": raw_output}, raw_output
        return self.normalize_role_output(role, raw_output, state)

    def inference_execute_node(self, state: FiveLayerState) -> FiveLayerState:
        role = state["active_role"]
        tool_events = list(state.get("tool_events", []))
        action_trace = list(state.get("action_trace", []))
        updated_brief = state.get("agent_brief", "")
        if (
            state.get("invoke_model")
            and state.get("repo_access_mode") == "read_only"
            and state.get("repo_path")
        ):
            raw_output, updated_brief, new_tool_events, new_trace_events = self.invoke_role_with_read_only_tools(
                role,
                state,
            )
            tool_events.extend(new_tool_events)
            action_trace.extend(new_trace_events)
        else:
            raw_output = (
                self.invoke_role_model(role, state)
                if state.get("invoke_model")
                else self.simulate_role_output(role, state)
            )
        artifact, normalized_output = self.normalize_role_response(
            role,
            raw_output,
            state,
        )
        test_run_result = state.get("test_run_result", {})
        if role == "tester" and state.get("test_command"):
            repo_path = self.resolve_repo_path(state.get("repo_path")) or REPO_ROOT
            test_run_result = self.execute_test_command(
                repo_path=repo_path,
                test_command=state["test_command"],
                timeout_sec=state.get("test_timeout_sec", 120),
            )
            artifact = self.augment_tester_artifact_with_test_result(
                artifact,
                test_run_result,
            )
            normalized_output = json.dumps(artifact, indent=2, ensure_ascii=False)
            action_trace.append(
                {
                    "event": "test_command_executed",
                    "role": role,
                    "summary": compact_one_line(
                        f"passed={test_run_result.get('passed', False)} "
                        f"timeout={test_run_result.get('timeout', False)} "
                        f"command={test_run_result.get('command', '')}"
                    ),
                    "result": test_run_result,
                }
            )
        action_trace.append(
            {
                "event": "role_completed",
                "role": role,
                "summary": self.summarize_artifact(role, artifact),
            }
        )
        return {
            "agent_brief": updated_brief,
            "latest_output": normalized_output,
            "latest_artifact": artifact,
            "test_run_result": test_run_result,
            "tool_events": tool_events,
            "action_trace": action_trace,
            "execution_log": append_log(state, f"inference: executed role `{role}`"),
        }

    def build_final_report(
        self,
        state: FiveLayerState,
        updated_outputs: dict[str, str],
    ) -> str:
        sections = [f"Scenario: {state['title']}"]
        for role in self.role_order:
            label = format_role_label(role)
            sections.append(f"{label}:\n{updated_outputs.get(role, '')}")
        if state.get("action_trace"):
            sections.append(
                "Action Trace:\n" + self.format_action_trace(state["action_trace"])
            )
        return "\n\n".join(sections) + "\n"

    def coordination_commit_node(self, state: FiveLayerState) -> FiveLayerState:
        role = state["active_role"]
        updated_outputs = dict(state.get("role_outputs", {}))
        updated_outputs[role] = state["latest_output"]
        updated_artifacts = dict(state.get("role_artifacts", {}))
        updated_artifacts[role] = dict(state.get("latest_artifact", {}))

        shared_memory = dict(state.get("shared_memory", {}))
        shared_memory["role_outputs"] = updated_outputs
        shared_memory["role_artifacts"] = updated_artifacts
        if state.get("tool_events"):
            shared_memory["tool_events"] = state["tool_events"]
        if state.get("action_trace"):
            shared_memory["action_trace"] = state["action_trace"]
        if state.get("test_run_result"):
            shared_memory["test_run_result"] = state["test_run_result"]
        shared_memory[f"{role}_done"] = True

        next_role_index = state.get("next_role_index", 0) + 1
        committed_trace = append_trace(
            state,
            {
                "event": "role_committed",
                "role": role,
                "summary": "output committed to shared memory",
            },
        )

        final_report = state.get("final_report", "")
        if role == self.role_order[-1]:
            final_report = self.build_final_report(
                {**state, "action_trace": committed_trace},
                updated_outputs,
            )

        return {
            "role_outputs": updated_outputs,
            "role_artifacts": updated_artifacts,
            "shared_memory": shared_memory,
            "next_role_index": next_role_index,
            "final_report": final_report,
            "test_run_result": state.get("test_run_result", {}),
            "tool_events": state.get("tool_events", []),
            "action_trace": committed_trace,
            "execution_log": append_log(
                state,
                f"coordination: committed output for `{role}`",
            ),
        }

    def build_graph(self):
        graph = StateGraph(FiveLayerState)
        graph.add_node("perception", self.perception_node)
        graph.add_node("coordination_prepare", self.coordination_prepare_node)
        graph.add_node("behavior_route", self.behavior_route_node)
        graph.add_node("communication_brief", self.communication_brief_node)
        graph.add_node("inference_execute", self.inference_execute_node)
        graph.add_node("coordination_commit", self.coordination_commit_node)

        graph.add_edge(START, "perception")
        graph.add_edge("perception", "coordination_prepare")
        graph.add_edge("coordination_prepare", "behavior_route")
        graph.add_conditional_edges(
            "behavior_route",
            self.behavior_route_decision,
            {
                "continue": "communication_brief",
                "end": END,
            },
        )
        graph.add_edge("communication_brief", "inference_execute")
        graph.add_edge("inference_execute", "coordination_commit")
        graph.add_edge("coordination_commit", "behavior_route")

        return graph.compile(checkpointer=MemorySaver())

    def scenario_to_initial_state(
        self,
        scenario: Scenario,
        invoke_model: bool,
        model_name: str | None,
        repo_path: str | None = None,
        test_command: str | None = None,
        test_timeout_sec: int = 120,
        seed_payload: dict[str, Any] | None = None,
        start_role: str | None = None,
    ) -> FiveLayerState:
        effective_test_command = test_command or scenario.test_command
        merged_seed_payload = self.build_seed_payload(
            scenario=scenario,
            seed_payload=seed_payload,
            start_role=start_role,
        )
        real_tools_enabled = bool(repo_path or effective_test_command)
        repo_access_mode: Literal["synthetic", "read_only"] = (
            "read_only" if real_tools_enabled else "synthetic"
        )
        return {
            "scenario_id": scenario.id,
            "title": scenario.title,
            "task": scenario.user_task,
            "repository_context": scenario.repository_context,
            "acceptance_criteria": scenario.acceptance_criteria,
            "available_tools": (
                ["search", "read_file", "run_tests"]
                if real_tools_enabled
                else scenario.available_tools
            ),
            "risk_notes": scenario.risk_notes,
            "start_role": merged_seed_payload.get("start_role"),
            "repo_path": repo_path,
            "repo_access_mode": repo_access_mode,
            "test_command": effective_test_command,
            "test_timeout_sec": test_timeout_sec,
            "seed_context": deepcopy(merged_seed_payload.get("seed_context", {})),
            "seed_role_outputs": deepcopy(
                merged_seed_payload.get("seed_role_outputs", {})
            ),
            "seed_role_artifacts": deepcopy(
                merged_seed_payload.get("seed_role_artifacts", {})
            ),
            "seed_test_run_result": deepcopy(
                merged_seed_payload.get("seed_test_run_result", {})
            ),
            "seed_tool_events": deepcopy(
                merged_seed_payload.get("seed_tool_events", [])
            ),
            "seed_action_trace": deepcopy(
                merged_seed_payload.get("seed_action_trace", [])
            ),
            "execution_log": [],
            "tool_events": [],
            "invoke_model": invoke_model,
            "model_name": model_name,
        }

    def run_scenario(
        self,
        scenario: Scenario,
        invoke_model: bool,
        model_name: str | None,
        repo_path: str | None = None,
        test_command: str | None = None,
        test_timeout_sec: int = 120,
        seed_payload: dict[str, Any] | None = None,
        start_role: str | None = None,
    ) -> FiveLayerState:
        graph = self.build_graph()
        initial_state = self.scenario_to_initial_state(
            scenario=scenario,
            invoke_model=invoke_model,
            model_name=model_name,
            repo_path=repo_path,
            test_command=test_command,
            test_timeout_sec=test_timeout_sec,
            seed_payload=seed_payload,
            start_role=start_role,
        )
        return graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": f"{self.name}:{scenario.id}"}},
        )

    def summarize_state(self, state: FiveLayerState) -> dict[str, Any]:
        return {
            "scenario_id": state["scenario_id"],
            "title": state["title"],
            "workflow_status": state.get("workflow_status"),
            "active_role": state.get("active_role"),
            "repo_access_mode": state.get("repo_access_mode"),
            "repo_path": state.get("repo_path"),
            "start_role": state.get("start_role"),
            "test_command": state.get("test_command"),
            "role_outputs": state.get("role_outputs", {}),
            "role_artifacts": state.get("role_artifacts", {}),
            "tool_events": state.get("tool_events", []),
            "action_trace": state.get("action_trace", []),
            "action_trace_text": self.format_action_trace(
                state.get("action_trace", [])
            ),
            "repo_snapshot": state.get("repo_snapshot", {}),
            "live_file_context": state.get("live_file_context", ""),
            "read_only_files": state.get("read_only_files", []),
            "seed_context": state.get("seed_context", {}),
            "test_run_result": state.get("test_run_result", {}),
            "execution_log": state.get("execution_log", []),
            "final_report": state.get("final_report", ""),
        }

    def print_scenarios(self, scenarios: dict[str, Scenario]) -> None:
        for scenario in scenarios.values():
            print(f"{scenario.id:<24} {scenario.title}")

    def render_scenario(self, scenario: Scenario) -> None:
        print(
            json.dumps(
                {
                    "id": scenario.id,
                    "title": scenario.title,
                    "user_task": scenario.user_task,
                    "repository_context": scenario.repository_context,
                    "acceptance_criteria": scenario.acceptance_criteria,
                    "available_tools": scenario.available_tools,
                    "risk_notes": scenario.risk_notes,
                    "test_command": scenario.test_command,
                    "start_role": scenario.start_role,
                    "seed_context": scenario.seed_context,
                    "seeded_roles": sorted(
                        set((scenario.seed_role_outputs or {}).keys())
                        | set((scenario.seed_role_artifacts or {}).keys())
                    ),
                    "role_order": self.role_order,
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    def parse_args(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description=self.description)
        subparsers = parser.add_subparsers(dest="command", required=True)

        subparsers.add_parser("list", help="List scenarios.")

        render_parser = subparsers.add_parser("render", help="Render one scenario.")
        render_parser.add_argument("--case", required=True, help="Scenario id.")

        run_parser = subparsers.add_parser("run", help="Run one or all scenarios.")
        run_parser.add_argument("--case", default="all", help="Scenario id or 'all'.")
        run_parser.add_argument(
            "--invoke",
            action="store_true",
            help="Invoke a real model if API keys are configured.",
        )
        run_parser.add_argument(
            "--model",
            default=None,
            help="Optional model override.",
        )
        run_parser.add_argument(
            "--repo-path",
            default=None,
            help="Optional real repository path for read-only observation.",
        )
        run_parser.add_argument(
            "--test-command",
            default=None,
            help="Optional real test command to execute during the tester step.",
        )
        run_parser.add_argument(
            "--test-timeout",
            type=int,
            default=120,
            help="Timeout in seconds for the real test command.",
        )
        run_parser.add_argument(
            "--seed-file",
            default=None,
            help="Optional JSON file with seeded artifacts, test results, and start role.",
        )
        run_parser.add_argument(
            "--start-role",
            default=None,
            help="Optional role to start from, such as tester or reviewer.",
        )

        return parser.parse_args()

    def resolve_requested_scenarios(
        self,
        requested: str,
        scenarios: dict[str, Scenario],
    ) -> list[Scenario]:
        if requested == "all":
            return list(scenarios.values())
        if requested not in scenarios:
            raise KeyError(f"Unknown scenario id: {requested}")
        return [scenarios[requested]]

    def main(self) -> None:
        args = self.parse_args()
        scenarios = self.load_scenarios()

        if args.command == "list":
            self.print_scenarios(scenarios)
            return

        if args.command == "render":
            self.render_scenario(scenarios[args.case])
            return

        requested = self.resolve_requested_scenarios(args.case, scenarios)
        seed_payload = self.load_seed_payload(args.seed_file)
        results = [
            self.summarize_state(
                self.run_scenario(
                    scenario,
                    invoke_model=args.invoke,
                    model_name=args.model,
                    repo_path=args.repo_path,
                    test_command=args.test_command,
                    test_timeout_sec=args.test_timeout,
                    seed_payload=seed_payload,
                    start_role=args.start_role,
                )
            )
            for scenario in requested
        ]
        print(json.dumps(results, indent=2, ensure_ascii=False))
