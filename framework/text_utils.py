from __future__ import annotations

import json
import re
from typing import Any


def bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def format_role_label(role: str) -> str:
    return role.replace("_", " ").title()


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


def format_kv_section(title: str, body: str) -> str:
    if not body:
        return ""
    return f"{title}:\n{body}"


def compact_one_line(text: str, max_chars: int = 160) -> str:
    collapsed = " ".join((text or "").split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."


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
