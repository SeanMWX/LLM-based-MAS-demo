from __future__ import annotations

import json
from typing import Any

from .text_utils import compact_one_line


def append_log(state: dict[str, Any], message: str) -> list[str]:
    return [*state.get("execution_log", []), message]


def append_trace(
    state: dict[str, Any],
    event: dict[str, Any],
) -> list[dict[str, Any]]:
    return [*state.get("action_trace", []), event]


def summarize_artifact(role: str, artifact: dict[str, Any]) -> str:
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


def summarize_tool_request(request: dict[str, Any]) -> str:
    tool = request.get("tool", "")
    if tool == "search":
        return f"search query={request.get('query', '')}"
    if tool == "read_file":
        return f"read_file path={request.get('path', '')}"
    return compact_one_line(json.dumps(request, ensure_ascii=False))


def summarize_tool_result(result: dict[str, Any]) -> str:
    tool = result.get("tool", "")
    if tool == "search":
        return f"search returned {len(result.get('matches', []))} matches"
    if tool == "read_file":
        if result.get("found"):
            return f"read_file returned snippet for {result.get('path', '')}"
        return f"read_file could not read {result.get('path', '')}"
    return compact_one_line(json.dumps(result, ensure_ascii=False))


def format_action_trace(action_trace: list[dict[str, Any]]) -> str:
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
