from __future__ import annotations

import json
from typing import Any
import time

from ...config import OPENAI_CHAT_MODEL
from ...errors import ApiError
from ..common import (
    append_fault_trace,
    apply_confirmation_response,
    extract_json_payload,
    logger,
    normalize_message_content,
)
from ..common import strip_think_blocks
from ..playbooks import build_fault_doc_context_from_playbook, list_playbooks, run_scripted_fault_playbook_by_id
from ..playbooks.loader import find_playbook_by_id
from ..tools import agent_tool_registry
from .live_playbook_state import build_matched_playbook_payload, publish_live_playbook_state
from .model import build_chat_model, load_chat_message_classes
from .model import build_router_model
from ..playbooks.loader import get_playbook_catalog
from .prompts import build_fault_chat_system_prompt, build_fault_route_prompt
from .router_state import FaultChatState, FaultRouteState
try:
    from langgraph.types import interrupt
except Exception:
    interrupt = None


def load_catalog_node(_: FaultRouteState) -> FaultRouteState:
    playbooks = get_playbook_catalog()
    append_fault_trace(
        "route_catalog_loaded",
        {
            "count": len(playbooks),
            "playbooks": playbooks,
        },
    )
    return {"playbooks": playbooks}


def _publish_selected_playbook(playbooks: list[dict[str, Any]] | None, selected_playbook_id: str) -> None:
    normalized_playbook_id = normalize_message_content(selected_playbook_id)
    if not normalized_playbook_id:
        return
    selected_playbook = find_playbook_by_id(normalized_playbook_id)
    if not isinstance(selected_playbook, dict):
        selected_playbook = next(
            (
                playbook
                for playbook in (playbooks or [])
                if normalize_message_content(playbook.get("id", "")) == normalized_playbook_id
            ),
            None,
        )
    logger.info(
        "已向前端发布路由命中的流程图 | playbook_id=%s | has_root=%s",
        normalized_playbook_id,
        bool(isinstance(selected_playbook, dict) and isinstance(selected_playbook.get("root"), dict)),
    )
    publish_live_playbook_state(playbook=build_matched_playbook_payload(selected_playbook))


def resolve_playbook_route(state: FaultRouteState, *, publish: bool = True) -> FaultRouteState:
    continuation = state.get("resume_continuation")
    if isinstance(continuation, dict):
        selected_playbook_id = normalize_message_content(continuation.get("playbook_id", ""))
        selected_playbook_title = normalize_message_content(continuation.get("playbook_title", ""))
        reason = normalize_message_content(continuation.get("reason", "")) or "继续执行人工确认后的 playbook"
        if selected_playbook_id and not selected_playbook_title:
            for item in state.get("playbooks") or []:
                if item.get("id") == selected_playbook_id:
                    selected_playbook_title = normalize_message_content(item.get("title", ""))
                    break
        if publish:
            _publish_selected_playbook(state.get("playbooks"), selected_playbook_id)
        return {
            "selected_playbook_id": selected_playbook_id,
            "selected_playbook_title": selected_playbook_title,
            "reason": reason,
        }
    prefetched_playbook_id = normalize_message_content(state.get("prefetched_playbook_id", ""))
    if prefetched_playbook_id:
        prefetched_playbook_title = normalize_message_content(state.get("prefetched_playbook_title", ""))
        prefetched_reason = normalize_message_content(state.get("prefetched_reason", ""))
        if publish:
            _publish_selected_playbook(state.get("playbooks"), prefetched_playbook_id)
        return {
            "selected_playbook_id": prefetched_playbook_id,
            "selected_playbook_title": prefetched_playbook_title,
            "reason": prefetched_reason,
        }
    user_message = normalize_message_content(state.get("user_message", ""))
    playbooks = state.get("playbooks") or []
    if not user_message or not playbooks:
        return {
            "selected_playbook_id": "",
            "selected_playbook_title": "",
            "reason": "",
        }

    llm = build_router_model()
    prompt = build_fault_route_prompt(user_message, playbooks)
    logger.info("LLM 路由模型开始调用 | model=%s | candidate_count=%d", OPENAI_CHAT_MODEL, len(playbooks))
    append_fault_trace(
        "route_model_input",
        {
            "model": OPENAI_CHAT_MODEL,
            "user_message": user_message,
            "candidate_count": len(playbooks),
            "prompt": prompt,
        },
    )
    response = llm.invoke(prompt)
    raw_content = getattr(response, "content", "")
    logger.info("LLM 路由模型返回 | model=%s", OPENAI_CHAT_MODEL)
    append_fault_trace(
        "route_model_output",
        {
            "model": OPENAI_CHAT_MODEL,
            "response": raw_content,
        },
    )
    parsed = extract_json_payload(raw_content)
    selected_playbook_id = normalize_message_content(parsed.get("playbook_id", "")) if parsed else ""
    reason = normalize_message_content(parsed.get("reason", "")) if parsed else ""
    selected_title = ""
    for item in playbooks:
        if item.get("id") == selected_playbook_id:
            selected_title = normalize_message_content(item.get("title", ""))
            break
    if not selected_title:
        selected_playbook_id = ""
    append_fault_trace(
        "route_model_decision",
        {
            "selected_playbook_id": selected_playbook_id,
            "selected_playbook_title": selected_title,
            "reason": reason,
            "parsed": parsed,
        },
    )
    if publish:
        _publish_selected_playbook(playbooks, selected_playbook_id)
    return {
        "selected_playbook_id": selected_playbook_id,
        "selected_playbook_title": selected_title,
        "reason": reason,
    }


def route_playbook_node(state: FaultRouteState) -> FaultRouteState:
    return resolve_playbook_route(state, publish=True)


def wait_for_playbook_render_node(state: FaultChatState) -> FaultChatState:
    # time.sleep(5)  # 等待前端流程图加载的缓冲时间，实际等待时长由前端通过 interrupt 机制控制
    selected_playbook_id = normalize_message_content(state.get("selected_playbook_id", ""))
    if not selected_playbook_id:
        return {"playbook_render_ready": True}

    playbook = find_playbook_by_id(selected_playbook_id)
    pending_playbook_render = {
        "type": "playbook_render_ready",
        "playbook_id": selected_playbook_id,
        "playbook_title": normalize_message_content(state.get("selected_playbook_title", "")),
        "reason": normalize_message_content(state.get("reason", "")),
        "message": "流程图已准备好，等待前端确认加载完成后继续执行。",
        "playbook": build_matched_playbook_payload(playbook),
    }
    if interrupt is None:
        logger.info("langgraph interrupt 不可用，跳过前端渲染等待 | playbook_id=%s", selected_playbook_id)
        return {"playbook_render_ready": True}
    logger.info("等待前端流程图加载完成（interrupt） | playbook_id=%s", selected_playbook_id)
    resume_value = interrupt(pending_playbook_render)
    logger.info("前端流程图已加载完成，继续执行 | playbook_id=%s | resume_value=%s", selected_playbook_id, bool(resume_value))
    return {"playbook_render_ready": True}


def _coerce_structured_text(value: Any) -> Any:
    import ast

    if isinstance(value, (dict, list)):
        return value
    text = normalize_message_content(value)
    if not text:
        return text
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except Exception:
            continue
        if isinstance(parsed, (dict, list)):
            return parsed
    return text


def _format_section_block(title: str, value: Any) -> str:
    lines = [title]
    if isinstance(value, list):
        for item in value:
            item_text = normalize_message_content(item)
            if item_text:
                lines.append(f"- {item_text}")
    else:
        item_text = normalize_message_content(value)
        if item_text:
            lines.append(item_text)
    return "\n".join(lines).strip()


def _normalize_final_answer(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    normalized: dict[str, Any] = {}
    for raw_key, raw_value in value.items():
        key = normalize_message_content(raw_key)
        compact_key = key.replace("：", "").replace(":", "").replace(" ", "")
        if compact_key == "问题":
            normalized["问题："] = raw_value
        elif compact_key in {"排查过程", "分析过程", "处理过程"}:
            normalized["排查过程："] = raw_value
        elif compact_key in {"结论", "结果", "建议"}:
            normalized["结论："] = raw_value
    return normalized if all(section in normalized for section in ("问题：", "排查过程：", "结论：")) else None


def _render_polished_final_answer(answer: dict[str, Any]) -> str:
    problem = normalize_message_content(answer.get("问题：", ""))
    conclusion = normalize_message_content(answer.get("结论：", ""))
    process = answer.get("排查过程：", "")

    lines: list[str] = ["问题："]
    if problem:
        lines.append(f"当前现象：{problem}")

    lines.append("")
    lines.append("排查过程：")
    if isinstance(process, list):
        for index, item in enumerate(process, start=1):
            item_text = normalize_message_content(item)
            if item_text:
                lines.append(f"{index}. {item_text}")
    else:
        process_text = normalize_message_content(process)
        if process_text:
            lines.append(process_text)

    lines.append("")
    lines.append("结论：")
    if conclusion:
        lines.append(f"综合判断：{conclusion}")

    return "\n".join(lines).strip()


def _render_final_message(value: Any) -> str:
    structured = _coerce_structured_text(value)
    if isinstance(structured, dict):
        ordered_sections = ("问题：", "排查过程：", "结论：")
        normalized_answer = _normalize_final_answer(structured)
        if normalized_answer is not None:
            return _render_polished_final_answer(normalized_answer)
        return json.dumps(structured, ensure_ascii=False, indent=2)
    if isinstance(structured, list):
        return "\n".join(
            f"- {normalize_message_content(item)}"
            for item in structured
            if normalize_message_content(item)
        ).strip()
    return strip_think_blocks(normalize_message_content(structured))


def _extract_final_message(payload: dict[str, Any], fallback_text: str) -> str:
    for candidate in (
        payload.get("answer"),
        payload.get("content"),
        payload.get("summary"),
        payload.get("message"),
        fallback_text,
    ):
        text = _render_final_message(candidate)
        if text:
            return text
    return ""


def _final_message_has_required_sections(message: str) -> bool:
    text = normalize_message_content(message)
    if not text:
        return False
    normalized_text = text.replace(":", "：")
    return all(section in normalized_text for section in ("问题：", "排查过程：", "结论："))


def _build_tool_feedback_message(tool_name: str, tool_args: dict[str, Any], tool_result: dict[str, Any]) -> str:
    return (
        "【工具执行结果】\n"
        f"工具: {tool_name}\n"
        f"参数: {json.dumps(tool_args, ensure_ascii=False)}\n"
        f"结果: {json.dumps(tool_result, ensure_ascii=False)}"
    )


def _format_message_log(messages: list[Any]) -> str:
    lines: list[str] = []
    for index, message in enumerate(messages, start=1):
        role = str(getattr(message, "type", "") or message.__class__.__name__).replace("Message", "").lower()
        content = normalize_message_content(getattr(message, "content", ""))
        lines.append(f"[{index}] {role}")
        lines.append(content or "-")
        lines.append("")
    return "\n".join(lines).rstrip()


def _format_response_log(response: Any) -> str:
    content = normalize_message_content(getattr(response, "content", ""))
    response_type = str(getattr(response, "type", "") or response.__class__.__name__).strip()
    lines = [f"type: {response_type}"]
    if content:
        lines.append("content:")
        lines.append(content)
    else:
        lines.append("content: -")
    return "\n".join(lines)


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


def _format_clarify_item(item: Any) -> str:
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
        if isinstance(options, list):
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


def _build_script_context(scripted_playbook: dict[str, Any]) -> dict[str, Any]:
    return {
        "playbook_id": scripted_playbook.get("playbook_id", ""),
        "playbook_title": scripted_playbook.get("playbook_title", ""),
        "executed": scripted_playbook.get("executed", False),
        "reason": scripted_playbook.get("reason", ""),
        "observations": scripted_playbook.get("observations", {}),
        "conclusion": scripted_playbook.get("conclusion", ""),
        "next_action": scripted_playbook.get("next_action", ""),
        "recent_tasks": scripted_playbook.get("recent_tasks", []),
        "steps": scripted_playbook.get("steps", []),
        "sub_playbook": scripted_playbook.get("sub_playbook", None),
        "sub_playbooks": scripted_playbook.get("sub_playbooks", []),
        "matched_root": (scripted_playbook.get("matched_context") or {}).get("root", {}),
    }


def _extend_tool_traces_from_script(tool_traces: list[dict[str, Any]], scripted_playbook: dict[str, Any]) -> None:
    if not isinstance(scripted_playbook, dict):
        return
    for step in scripted_playbook.get("steps") or []:
        if isinstance(step, dict):
            tool_traces.append(
                {
                    "name": step.get("name", ""),
                    "arguments": step.get("arguments", {}),
                    "result": step.get("output", ""),
                }
            )
    for nested_playbook in scripted_playbook.get("sub_playbooks") or []:
        _extend_tool_traces_from_script(tool_traces, nested_playbook)
    nested_playbook = scripted_playbook.get("sub_playbook")
    if isinstance(nested_playbook, dict):
        _extend_tool_traces_from_script(tool_traces, nested_playbook)


def _build_chat_messages(user_message: str, *, fault_doc_context: str = "") -> list[Any]:
    AIMessage, HumanMessage, SystemMessage = load_chat_message_classes()
    normalized_user_message = normalize_message_content(user_message)
    if not normalized_user_message:
        raise ApiError("聊天内容不能为空")
    system_prompt = build_fault_chat_system_prompt(agent_tool_registry.list_tool_names())
    if fault_doc_context:
        system_prompt = f"{system_prompt}\n\n{fault_doc_context}"
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=normalized_user_message),
    ]


def _append_history_messages(messages: list[Any], history: list[dict[str, str]] | None) -> list[Any]:
    if not isinstance(history, list) or not history:
        return messages
    AIMessage, HumanMessage, _ = load_chat_message_classes()
    normalized_history: list[Any] = []
    for item in history[-10:]:
        if not isinstance(item, dict):
            continue
        role = normalize_message_content(item.get("role", "")).lower()
        content = normalize_message_content(item.get("content", ""))
        if not content:
            continue
        if role == "assistant":
            normalized_history.append(AIMessage(content=content))
        elif role == "user":
            normalized_history.append(HumanMessage(content=content))
    if len(messages) < 2:
        return messages + normalized_history
    return [messages[0], *normalized_history, messages[-1]]


def _find_selected_playbook(selected_playbook_id: str) -> dict[str, Any] | None:
    if not selected_playbook_id:
        return None
    for playbook in list_playbooks():
        if str(playbook.get("id") or "").strip() == selected_playbook_id:
            return playbook
    return None


def build_messages_node(state: FaultChatState) -> FaultChatState:
    user_message = normalize_message_content(state.get("user_message", ""))
    selected_playbook_id = normalize_message_content(state.get("selected_playbook_id", ""))
    selected_playbook_title = normalize_message_content(state.get("selected_playbook_title", ""))
    reason = normalize_message_content(state.get("reason", ""))
    route_trace = {
        "playbook_id": selected_playbook_id,
        "playbook_title": selected_playbook_title,
        "reason": reason,
    }
    logger.info("开始故障路由 | user_message=%s", user_message[:120])
    append_fault_trace(
        "route_start",
        {
            "user_message": user_message,
        },
    )
    append_fault_trace("route_finish", route_trace)
    selected_playbook = _find_selected_playbook(selected_playbook_id)
    messages = _build_chat_messages(
        user_message,
        fault_doc_context=build_fault_doc_context_from_playbook(selected_playbook),
    )
    messages = _append_history_messages(messages, state.get("conversation_history"))
    confirmation_response = normalize_message_content(state.get("confirmation_response", ""))
    if confirmation_response:
        _, HumanMessage, _ = load_chat_message_classes()
        messages.append(HumanMessage(content="【用户补充信息】\n" + confirmation_response))
    logger.info("=== Chat 开始 | user_message: %s", user_message[:50])
    append_fault_trace(
        "chat_start",
        {
            "user_message": user_message,
            "runtime_context": state.get("runtime_context") or {},
            "tool_count": agent_tool_registry.count(),
            "playbook_route": {
                "playbook_id": selected_playbook_id,
                "playbook_title": selected_playbook_title,
                "reason": reason,
            },
        },
    )
    return {"messages": messages}


def execute_playbook_node(state: FaultChatState) -> FaultChatState:
    selected_playbook_id = normalize_message_content(state.get("selected_playbook_id", ""))
    if not selected_playbook_id:
        return {"scripted_playbook": None}
    selected_playbook = _find_selected_playbook(selected_playbook_id)
    matched_playbook_payload = build_matched_playbook_payload(selected_playbook)
    publish_live_playbook_state(playbook=matched_playbook_payload)
    effective_tool_context = dict(state.get("effective_tool_context") or {})
    resume_continuation = state.get("resume_continuation")
    resume_state = None
    if isinstance(resume_continuation, dict):
        effective_tool_context = apply_confirmation_response(
            effective_tool_context,
            resume_continuation.get("pending_confirmation"),
            normalize_message_content(state.get("confirmation_response", "")),
        )
        raw_resume_state = resume_continuation.get("resume_state")
        resume_state = raw_resume_state if isinstance(raw_resume_state, dict) else None
    scripted_playbook = run_scripted_fault_playbook_by_id(
        selected_playbook_id,
        effective_tool_context,
        resume_state=resume_state,
        status_reporter=lambda payload, pending, active_path, active_message: publish_live_playbook_state(
            playbook=matched_playbook_payload,
            scripted_playbook=payload,
            pending_confirmation=pending,
            active_node_path=active_path,
            active_node_message=active_message,
        ),
    )
    if not scripted_playbook:
        return {"scripted_playbook": None}
    append_fault_trace("playbook_script", scripted_playbook)
    tool_traces = list(state.get("tool_traces") or [])
    _extend_tool_traces_from_script(tool_traces, scripted_playbook)
    if isinstance(scripted_playbook.get("pending_confirmation"), dict):
        pending_confirmation = scripted_playbook.get("pending_confirmation")
        publish_live_playbook_state(
            playbook=matched_playbook_payload,
            scripted_playbook=scripted_playbook,
            pending_confirmation=pending_confirmation,
            active_node_path=normalize_message_content(pending_confirmation.get("node_path", "")),
            active_node_message=normalize_message_content(pending_confirmation.get("message", "")),
        )
        append_fault_trace("playbook_confirmation", pending_confirmation)
        return {
            "scripted_playbook": scripted_playbook,
            "tool_traces": tool_traces,
            "effective_tool_context": effective_tool_context,
            "pending_confirmation": pending_confirmation,
            "playbook_resume_state": scripted_playbook.get("resume_state"),
            "final_message": normalize_message_content(pending_confirmation.get("message", "")),
            "result_kind": "confirmation",
        }
    messages = list(state.get("messages") or [])
    _, HumanMessage, _ = load_chat_message_classes()
    script_context = _build_script_context(scripted_playbook)
    publish_live_playbook_state(
        playbook=matched_playbook_payload,
        scripted_playbook=scripted_playbook,
    )
    messages.append(HumanMessage(content="【脚本执行结果】\n" + json.dumps(script_context, ensure_ascii=False, indent=2)))
    return {
        "scripted_playbook": scripted_playbook,
        "tool_traces": tool_traces,
        "effective_tool_context": effective_tool_context,
        "messages": messages,
    }


def route_after_playbook_node(state: FaultChatState) -> str:
    if isinstance(state.get("pending_confirmation"), dict):
        return "finish"
    return "call_model"


def call_chat_model_node(state: FaultChatState) -> FaultChatState:
    messages = list(state.get("messages") or [])
    logger.info("LLM 聊天模型开始调用 | model=%s | message_count=%d", OPENAI_CHAT_MODEL, len(messages))
    append_fault_trace(
        "chat_model_input",
        {
            "model": OPENAI_CHAT_MODEL,
            "messages": _format_message_log(messages),
        },
    )
    llm = build_chat_model()
    response = llm.invoke(messages)
    logger.info("LLM 聊天模型返回 | model=%s", OPENAI_CHAT_MODEL)
    append_fault_trace(
        "chat_model_output",
        {
            "model": OPENAI_CHAT_MODEL,
            "response": _format_response_log(response),
        },
    )
    return {
        "response": response,
        "response_content": normalize_message_content(getattr(response, "content", "")),
        "model_loop_count": int(state.get("model_loop_count") or 0) + 1,
    }


def interpret_model_output_node(state: FaultChatState) -> FaultChatState:
    content = normalize_message_content(state.get("response_content", ""))
    visible_content = normalize_message_content(strip_think_blocks(content))
    parsed = extract_json_payload(content)
    append_fault_trace(
        "model_response",
        {
            "visible_content": visible_content,
            "parsed": parsed,
            "reasoning_removed": visible_content != normalize_message_content(content),
        },
    )
    messages = list(state.get("messages") or [])
    AIMessage, HumanMessage, _ = load_chat_message_classes()
    if parsed is None:
        messages.append(
            HumanMessage(
                content=(
                    "上一个回复不符合格式要求。"
                    "请只输出一个 JSON 对象，且如果需要排查必须输出 command，"
                    "不要输出步骤说明、不要输出自然语言总结。"
                )
            )
        )
        return {"messages": messages, "parsed_response": None, "result_kind": "retry"}
    response_type = str(parsed.get("type") or parsed.get("mode") or "").strip().lower()
    if response_type in {"final", "answer", "summary"}:
        final_message = _extract_final_message(parsed, content)
        if not final_message:
            raise ApiError("模型未返回有效内容")
        if not _final_message_has_required_sections(final_message):
            messages.append(
                HumanMessage(
                    content=(
                        "上一个 final 回复没有按固定模板输出。"
                        "请重新输出一个 JSON 对象，保持 `type` 为 `final`，"
                        "并让 `answer` 严格包含三段：`问题：`、`排查过程：`、`结论：`。"
                    )
                )
            )
            return {"messages": messages, "parsed_response": parsed, "result_kind": "retry"}
        append_fault_trace(
            "chat_final",
            {
                "type": response_type or "final",
                "message": final_message,
                "tool_traces": state.get("tool_traces") or [],
            },
        )
        return {"parsed_response": parsed, "final_message": final_message, "result_kind": "final"}
    if response_type == "clarify":
        questions = parsed.get("questions")
        if isinstance(questions, list):
            question_text = "\n\n".join(item for item in (_format_clarify_item(item) for item in questions) if item)
        else:
            question_text = _extract_final_message(parsed, content)
        final_message = normalize_message_content(question_text)
        if not final_message:
            raise ApiError("模型未返回有效内容")
        append_fault_trace(
            "chat_clarify",
            {
                "questions": questions if isinstance(questions, list) else final_message,
                "tool_traces": state.get("tool_traces") or [],
            },
        )
        return {"parsed_response": parsed, "final_message": final_message, "result_kind": "clarify"}
    commands = _normalize_command_list(parsed)
    if not commands:
        final_message = _extract_final_message(parsed, content)
        if not final_message:
            messages.append(
                HumanMessage(
                    content="上一个回复没有给出可执行命令。请重新输出 command / clarify / final 的 JSON 对象。"
                )
            )
            return {"messages": messages, "parsed_response": parsed, "result_kind": "retry"}
        append_fault_trace(
            "chat_final",
            {
                "type": "fallback",
                "message": final_message,
                "tool_traces": state.get("tool_traces") or [],
            },
        )
        return {"parsed_response": parsed, "final_message": final_message, "result_kind": "final"}
    messages.append(AIMessage(content=content))
    return {"parsed_response": parsed, "pending_commands": commands, "messages": messages, "result_kind": "tool_call"}


def call_tools_node(state: FaultChatState) -> FaultChatState:
    messages = list(state.get("messages") or [])
    tool_traces = list(state.get("tool_traces") or [])
    _, HumanMessage, _ = load_chat_message_classes()
    for command in state.get("pending_commands") or []:
        tool_name = str(command.get("name") or command.get("tool_name") or "").strip()
        if not tool_name:
            raise ApiError("模型输出的命令缺少工具名")
        tool_args = command.get("arguments")
        if not isinstance(tool_args, dict):
            tool_args = command.get("args") if isinstance(command.get("args"), dict) else {}
        append_fault_trace("tool_call_start", {"name": tool_name, "arguments": tool_args})
        logger.info("🔧 执行工具: %s, 参数: %s", tool_name, json.dumps(tool_args, ensure_ascii=False))
        try:
            tool_result = agent_tool_registry.call_tool(tool_name, tool_args, state.get("effective_tool_context"))
            tool_traces.append({"name": tool_name, "arguments": tool_args, "result": tool_result})
            append_fault_trace("tool_call", {"name": tool_name, "arguments": tool_args, "result": tool_result})
            logger.info("✅ 工具执行成功: %s", tool_name)
        except ApiError:
            raise
        except Exception as exc:  # noqa: BLE001
            error_message = exc.message if isinstance(exc, ApiError) else str(exc)
            tool_result = {"ok": False, "error": error_message}
            tool_traces.append({"name": tool_name, "arguments": tool_args, "error": error_message})
            append_fault_trace("tool_call_error", {"name": tool_name, "arguments": tool_args, "error": error_message})
            logger.error("❌ 工具执行失败: %s, 错误: %s", tool_name, error_message)
        append_fault_trace(
            "tool_call_end",
            {
                "name": tool_name,
                "arguments": tool_args,
                "ok": bool(tool_result.get("ok", True)) if isinstance(tool_result, dict) else True,
            },
        )
        messages.append(HumanMessage(content=_build_tool_feedback_message(tool_name, tool_args, tool_result)))
    return {"messages": messages, "tool_traces": tool_traces, "pending_commands": []}


def route_after_interpret_node(state: FaultChatState) -> str:
    result_kind = str(state.get("result_kind") or "")
    loop_count = int(state.get("model_loop_count") or 0)
    if result_kind in {"final", "clarify"}:
        return "finish"
    if loop_count >= 6:
        return "loop_exit"
    if result_kind == "tool_call":
        return "tool_call"
    return "retry"
