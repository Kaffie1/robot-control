from __future__ import annotations

import json
from typing import Any

from ..common import normalize_message_content


def build_tool_feedback_message(tool_name: str, tool_args: dict[str, Any], tool_result: dict[str, Any]) -> str:
    return (
        "【工具执行结果】\n"
        f"工具: {tool_name}\n"
        f"参数: {json.dumps(tool_args, ensure_ascii=False)}\n"
        f"结果: {json.dumps(tool_result, ensure_ascii=False)}"
    )


def format_message_log(messages: list[Any]) -> str:
    lines: list[str] = []
    for index, message in enumerate(messages, start=1):
        role = str(getattr(message, "type", "") or message.__class__.__name__).replace("Message", "").lower()
        content = normalize_message_content(getattr(message, "content", ""))
        lines.append(f"[{index}] {role}")
        lines.append(content or "-")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_response_log(response: Any) -> str:
    content = normalize_message_content(getattr(response, "content", ""))
    response_type = str(getattr(response, "type", "") or response.__class__.__name__).strip()
    lines = [f"type: {response_type}"]
    if content:
        lines.append("content:")
        lines.append(content)
    else:
        lines.append("content: -")
    return "\n".join(lines)


def normalize_command_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    raw_commands = payload.get("commands")
    if isinstance(raw_commands, list):
        for item in raw_commands:
            if isinstance(item, dict):
                commands.append(item)
    elif isinstance(raw_commands, dict):
        commands.append(raw_commands)
    elif payload.get("name") or payload.get("tool_name"):
        commands.append(payload)
    return commands


def format_clarify_item(item: Any) -> str:
    if isinstance(item, str):
        return normalize_message_content(item)
    if isinstance(item, dict):
        question = normalize_message_content(
            item.get("question")
            or item.get("content")
            or item.get("title")
            or item.get("message")
        )
        options = item.get("options")
        lines: list[str] = []
        if question:
            lines.append(question)
        if isinstance(options, list) and options:
            for option in options:
                if isinstance(option, dict):
                    option_text = normalize_message_content(
                        option.get("display_label")
                        or option.get("label")
                        or option.get("text")
                        or option.get("value")
                        or option.get("name")
                    )
                else:
                    option_text = normalize_message_content(option)
                if option_text:
                    lines.append(f"- {option_text}")
        return "\n".join(lines).strip()
    return normalize_message_content(item)
