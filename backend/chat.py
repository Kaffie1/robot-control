import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .agent_tools import agent_tool_registry
from .config import (
    FAULT_TRACE_LOG_PATH,
    FAULT_PLAYBOOKS_PATH,
    FAULT_PROMPT_TEMPLATE_PATH,
    FAULT_TOOLS_PATH,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_CHAT_MODEL,
    OPENAI_CHAT_TEMPERATURE,
    OPENAI_ENABLE_REASONING_SPLIT,
    OPENAI_THINK,
)
from .models import ApiError
from .prompts import build_fault_chat_system_prompt


def _normalize_message_content(value: Any) -> str:
    return str(value or "").strip()


def _normalize_message_role(value: Any) -> str:
    role = str(value or "").strip().lower()
    if role not in {"system", "user", "assistant"}:
        raise ApiError(f"不支持的消息角色: {value}")
    return role


def _strip_think_blocks(text: str) -> str:
    normalized = str(text or "")
    cleaned = re.sub(r"<think>.*?</think>", "", normalized, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"^\s*思考过程[:：].*$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _read_text_file(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _truncate_trace_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= 4:
        return "…"
    if isinstance(value, dict):
        items: dict[str, Any] = {}
        for key, item in list(value.items())[:60]:
            items[str(key)] = _truncate_trace_value(item, depth=depth + 1)
        return items
    if isinstance(value, list):
        return [_truncate_trace_value(item, depth=depth + 1) for item in value[:60]]
    if isinstance(value, str):
        if len(value) <= 2000:
            return value
        return f"{value[:2000]}…(truncated,{len(value)} chars)"
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


def _append_fault_trace(event: str, payload: dict[str, Any]) -> None:
    FAULT_TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": event,
        "payload": _truncate_trace_value(payload),
    }
    with FAULT_TRACE_LOG_PATH.open("a", encoding="utf-8") as file_obj:
        file_obj.write(json.dumps(record, ensure_ascii=False) + "\n")


def _format_tool_catalog(items: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in items:
        name = str(item.get("name") or "").strip()
        description = str(item.get("description") or "").strip()
        if not name:
            continue
        input_schema = item.get("input_schema") or {}
        lines.append(
            f"- {name}: {description}\n"
            f"  input_schema: {json.dumps(input_schema, ensure_ascii=False)}"
        )
    return "\n".join(lines).strip()


def _extract_json_payload(text: str) -> dict[str, Any] | None:
    normalized = _strip_think_blocks(str(text or ""))
    if not normalized:
        return None
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", normalized, flags=re.IGNORECASE | re.DOTALL)
    if fenced_match:
        normalized = fenced_match.group(1).strip()

    first_brace = normalized.find("{")
    if first_brace < 0:
        return None
    depth = 0
    end_index = -1
    for index, char in enumerate(normalized[first_brace:], start=first_brace):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end_index = index
                break
    if end_index < 0:
        return None
    normalized = normalized[first_brace : end_index + 1].strip()
    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    return None


def build_chat_messages(
    user_message: str,
    history: list[dict[str, Any]] | None = None,
    runtime_context: dict[str, Any] | None = None,
) -> list[Any]:
    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    except Exception as exc:  # noqa: BLE001
        raise ApiError("聊天依赖未安装，请先安装 langchain-openai 和 openai") from exc

    normalized_user_message = _normalize_message_content(user_message)
    if not normalized_user_message:
        raise ApiError("聊天内容不能为空")

    fault_documents = "\n\n".join(
        section
        for section in (
            "### 故障诊断提示词\n" + _read_text_file(FAULT_PROMPT_TEMPLATE_PATH),
            "### 故障诊断策略\n" + _read_text_file(FAULT_PLAYBOOKS_PATH),
            "### 故障工具文档\n" + _read_text_file(FAULT_TOOLS_PATH),
        )
        if section.strip()
    )
    tool_catalog = _format_tool_catalog(agent_tool_registry.list_definitions())

    messages: list[Any] = [
        SystemMessage(
            content=build_fault_chat_system_prompt(
                runtime_context,
                fault_documents=fault_documents,
                tool_catalog=tool_catalog,
            )
        )
    ]
    for item in history or []:
        role = _normalize_message_role(item.get("role"))
        content = _normalize_message_content(item.get("content"))
        if not content:
            continue
        if role == "system":
            messages.append(SystemMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    messages.append(HumanMessage(content=normalized_user_message))
    return messages


def _build_tool_feedback_message(tool_name: str, tool_args: dict[str, Any], tool_result: dict[str, Any]) -> str:
    return (
        "【工具执行结果】\n"
        f"工具: {tool_name}\n"
        f"参数: {json.dumps(tool_args, ensure_ascii=False)}\n"
        f"结果: {json.dumps(tool_result, ensure_ascii=False)}"
    )


def _normalize_command_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
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


def _extract_final_message(payload: dict[str, Any], fallback_text: str) -> str:
    candidates = [
        payload.get("answer"),
        payload.get("content"),
        payload.get("summary"),
        payload.get("message"),
        fallback_text,
    ]
    for candidate in candidates:
        text = _normalize_message_content(candidate)
        if text:
            return _strip_think_blocks(text)
    return ""

def _build_chat_model():
    if not OPENAI_API_KEY:
        raise ApiError("未配置 OPENAI_API_KEY，无法调用聊天模型")

    try:
        from langchain_openai import ChatOpenAI
    except Exception as exc:  # noqa: BLE001
        raise ApiError("聊天依赖未安装，请先安装 langchain-openai 和 openai") from exc

    llm_kwargs: dict[str, Any] = {
        "model": OPENAI_CHAT_MODEL,
        "api_key": OPENAI_API_KEY,
        "temperature": OPENAI_CHAT_TEMPERATURE,
        "base_url": OPENAI_BASE_URL,
    }

    extra_body: dict[str, Any] = {}
    extra_body["reasoning_split"] = OPENAI_ENABLE_REASONING_SPLIT
    extra_body["think"] = OPENAI_THINK
    llm_kwargs["extra_body"] = extra_body

    return ChatOpenAI(**llm_kwargs)

def invoke_chat_model(
    user_message: str,
    *,
    history: list[dict[str, Any]] | None = None,
    runtime_context: dict[str, Any] | None = None,
    tool_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    messages = build_chat_messages(user_message, history=history, runtime_context=runtime_context)
    _append_fault_trace(
        "chat_start",
        {
            "user_message": user_message,
            "history_count": len(history or []),
            "runtime_context": runtime_context or {},
            "tool_count": len(agent_tool_registry.list_definitions()),
        },
    )

    llm = _build_chat_model()
    tool_traces: list[dict[str, Any]] = []

    response = None
    for _ in range(6):
        response = llm.invoke(messages)
        content = _normalize_message_content(getattr(response, "content", ""))
        visible_content = _normalize_message_content(_strip_think_blocks(content))
        parsed = _extract_json_payload(content)
        _append_fault_trace(
            "model_response",
            {
                "visible_content": visible_content,
                "parsed": parsed,
                "reasoning_removed": visible_content != _normalize_message_content(content),
            },
        )
        if parsed is None:
            normalized_content = visible_content
            if not normalized_content:
                raise ApiError("模型未返回有效内容")
            _append_fault_trace(
                "chat_final",
                {
                    "type": "text",
                    "message": normalized_content,
                    "tool_traces": tool_traces,
                },
            )
            return {
                "model": OPENAI_CHAT_MODEL,
                "message": normalized_content,
                "tool_traces": tool_traces,
            }

        response_type = str(parsed.get("type") or parsed.get("mode") or "").strip().lower()
        if response_type in {"final", "answer", "summary"}:
            final_message = _extract_final_message(parsed, content)
            if not final_message:
                raise ApiError("模型未返回有效内容")
            _append_fault_trace(
                "chat_final",
                {
                    "type": response_type or "final",
                    "message": final_message,
                    "tool_traces": tool_traces,
                },
            )
            return {
                "model": OPENAI_CHAT_MODEL,
                "message": final_message,
                "tool_traces": tool_traces,
            }

        if response_type == "clarify":
            questions = parsed.get("questions")
            if isinstance(questions, list):
                question_text = "\n".join(_normalize_message_content(item) for item in questions if _normalize_message_content(item))
            else:
                question_text = _extract_final_message(parsed, content)
            final_message = _normalize_message_content(question_text)
            if not final_message:
                raise ApiError("模型未返回有效内容")
            _append_fault_trace(
                "chat_clarify",
                {
                    "questions": questions if isinstance(questions, list) else final_message,
                    "tool_traces": tool_traces,
                },
            )
            return {
                "model": OPENAI_CHAT_MODEL,
                "message": final_message,
                "tool_traces": tool_traces,
            }

        commands = _normalize_command_list(parsed)
        if not commands:
            final_message = _extract_final_message(parsed, content)
            if not final_message:
                raise ApiError("模型未返回有效内容")
            _append_fault_trace(
                "chat_final",
                {
                    "type": "fallback",
                    "message": final_message,
                    "tool_traces": tool_traces,
                },
            )
            return {
                "model": OPENAI_CHAT_MODEL,
                "message": final_message,
                "tool_traces": tool_traces,
            }

        messages.append(AIMessage(content=content))
        for command in commands:
            tool_name = str(command.get("name") or command.get("tool_name") or "").strip()
            if not tool_name:
                raise ApiError("模型输出的命令缺少工具名")
            tool_args = command.get("arguments")
            if not isinstance(tool_args, dict):
                tool_args = command.get("args") if isinstance(command.get("args"), dict) else {}
            _append_fault_trace(
                "tool_call_start",
                {
                    "name": tool_name,
                    "arguments": tool_args,
                },
            )
            try:
                tool_result = agent_tool_registry.call_tool(tool_name, tool_args, tool_context)
                tool_traces.append({"name": tool_name, "arguments": tool_args, "result": tool_result})
                _append_fault_trace(
                    "tool_call",
                    {
                        "name": tool_name,
                        "arguments": tool_args,
                        "result": tool_result,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                error_message = exc.message if isinstance(exc, ApiError) else str(exc)
                tool_result = {"ok": False, "error": error_message}
                tool_traces.append({"name": tool_name, "arguments": tool_args, "error": error_message})
                _append_fault_trace(
                    "tool_call_error",
                    {
                        "name": tool_name,
                        "arguments": tool_args,
                        "error": error_message,
                    },
                )
            _append_fault_trace(
                "tool_call_end",
                {
                    "name": tool_name,
                    "arguments": tool_args,
                    "ok": bool(tool_result.get("ok", True)) if isinstance(tool_result, dict) else True,
                },
            )
            messages.append(HumanMessage(content=_build_tool_feedback_message(tool_name, tool_args, tool_result)))

    if response is None:
        raise ApiError("模型未返回有效内容")

    content = getattr(response, "content", "")
    normalized_content = _normalize_message_content(_strip_think_blocks(str(content)))
    if not normalized_content:
        raise ApiError("模型未返回有效内容")
    _append_fault_trace(
        "chat_final",
        {
            "type": "loop_exit",
            "message": normalized_content,
            "tool_traces": tool_traces,
        },
    )
    return {
        "model": OPENAI_CHAT_MODEL,
        "message": normalized_content,
        "tool_traces": tool_traces,
    }
