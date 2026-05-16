from __future__ import annotations

from typing import Any

from ...config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_CHAT_MODEL,
    OPENAI_CHAT_TEMPERATURE,
    OPENAI_ENABLE_REASONING_SPLIT,
    OPENAI_THINK,
)
from ...models import ApiError


def load_chat_message_classes() -> tuple[Any, Any, Any]:
    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    except Exception as exc:  # noqa: BLE001
        raise ApiError("聊天依赖未安装，请先安装 langchain-openai 和 openai") from exc
    return AIMessage, HumanMessage, SystemMessage


def _build_extra_body() -> dict[str, Any]:
    return {
        "reasoning_split": OPENAI_ENABLE_REASONING_SPLIT,
        "think": OPENAI_THINK,
    }


def _create_chat_openai(*, temperature: float):
    if not OPENAI_API_KEY:
        raise ApiError("未配置 OPENAI_API_KEY，无法调用聊天模型")
    try:
        from langchain_openai import ChatOpenAI
    except Exception as exc:  # noqa: BLE001
        raise ApiError("聊天依赖未安装，请先安装 langchain-openai 和 openai") from exc
    return ChatOpenAI(
        model=OPENAI_CHAT_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=temperature,
        base_url=OPENAI_BASE_URL,
        extra_body=_build_extra_body(),
    )


def build_chat_model():
    return _create_chat_openai(temperature=OPENAI_CHAT_TEMPERATURE)


def build_router_model():
    return _create_chat_openai(temperature=0)
