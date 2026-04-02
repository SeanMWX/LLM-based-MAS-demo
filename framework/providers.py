from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .env import env_int, first_env
from .text_utils import coerce_message_text


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


def build_model(model_name: str | None):
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
