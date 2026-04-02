from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .text_utils import (
    compact_output,
    extract_json_object,
    format_kv_section,
    format_numbered_snippet,
    truncate_text,
)

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


def resolve_repo_path(repo_path: str | None) -> Path | None:
    if not repo_path:
        return None
    resolved = Path(repo_path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Repo path does not exist: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Repo path is not a directory: {resolved}")
    return resolved


def collect_repo_snapshot(repo_path: Path) -> dict[str, Any]:
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
    snapshot: dict[str, Any],
    task: str,
    repository_context: str,
    acceptance_criteria: list[str],
    max_files: int = 4,
) -> list[str]:
    keywords = extract_query_keywords(
        task,
        repository_context,
        *acceptance_criteria,
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

    for path in [
        *non_test_python[:2],
        *test_files[:2],
        *python_files,
        *snapshot.get("file_sample", []),
    ]:
        normalized = str(path).replace("\\", "/")
        if normalized not in fallback:
            fallback.append(normalized)
        if len(fallback) >= max_files:
            return fallback
    return fallback


def collect_read_only_files(
    repo_path: Path,
    snapshot: dict[str, Any],
    task: str,
    repository_context: str,
    acceptance_criteria: list[str],
    max_files: int = 4,
) -> list[dict[str, str]]:
    selected_paths = select_files_for_context(
        snapshot=snapshot,
        task=task,
        repository_context=repository_context,
        acceptance_criteria=acceptance_criteria,
        max_files=max_files,
    )
    read_only_files: list[dict[str, str]] = []

    for relative_path in selected_paths:
        content = read_repo_text_file(repo_path, relative_path)
        if not content:
            continue
        read_only_files.append(
            {
                "path": relative_path,
                "snippet": format_numbered_snippet(content),
            }
        )
    return read_only_files


def format_read_only_files(files: list[dict[str, str]]) -> str:
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


def parse_tool_request(
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
        content = read_repo_text_file(repo_path, path, max_chars=10_000)
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
    repo_path: Path,
    request: dict[str, Any],
) -> dict[str, Any]:
    tool = request["tool"]
    if tool == "search":
        return search_repo(
            repo_path=repo_path,
            query=request["query"],
            top_k=request.get("top_k", 8),
        )

    if tool == "read_file":
        content = read_repo_text_file(repo_path, request["path"], max_chars=4000)
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


def format_tool_result(result: dict[str, Any]) -> str:
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
    brief: str,
    request: dict[str, Any],
    result: dict[str, Any],
    round_index: int,
) -> str:
    section = "\n\n".join(
        [
            f"Tool round {round_index}",
            f"Tool request:\n{json.dumps(request, indent=2, ensure_ascii=False)}",
            f"Tool result:\n{format_tool_result(result)}",
            "If you have enough context now, return the final role JSON only. "
            "If you still need more repo context, you may issue one more tool_request JSON.",
        ]
    )
    return brief + "\n\n" + section


def format_repo_snapshot(snapshot: dict[str, Any]) -> str:
    sections = [
        f"Repo path: {snapshot.get('repo_path', '')}",
        f"Git root: {snapshot.get('git_root', '(not available)')}",
        f"File count: {snapshot.get('file_count', 0)}",
    ]

    if snapshot.get("git_status"):
        sections.append(format_kv_section("Git status", snapshot["git_status"]))
    if snapshot.get("file_sample"):
        sections.append(
            format_kv_section(
                "File sample",
                "\n".join(f"- {item}" for item in snapshot["file_sample"]),
            )
        )
    if snapshot.get("test_files_sample"):
        sections.append(
            format_kv_section(
                "Test file sample",
                "\n".join(f"- {item}" for item in snapshot["test_files_sample"]),
            )
        )

    return "\n\n".join(section for section in sections if section)


def execute_test_command(
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


def format_test_run_result(result: dict[str, Any]) -> str:
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
