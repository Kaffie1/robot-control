from __future__ import annotations

import json
from typing import Any

from ..common import (
    append_fault_trace,
    extract_json_payload,
    list_recent_chat_history,
    normalize_message_content,
    resolve_pending_confirmation_reply,
    strip_think_blocks,
)
from ...config import OPENAI_CHAT_MODEL
from ...models import ApiError
from ..common import logger
from .support import (
    merge_tool_context,
    extract_final_message,
    final_message_has_required_sections,
)
from ..playbooks import build_fault_doc_context_from_playbook, list_playbooks, run_scripted_fault_playbook_by_id
from ..orchestration import build_chat_model, build_fault_chat_system_prompt, load_chat_message_classes, route_fault_playbook
from .render import (
    build_tool_feedback_message,
    format_clarify_item,
    format_message_log,
    format_response_log,
    normalize_command_list,
)

MAX_CHAT_HISTORY_TURNS = 3


def build_script_context(scripted_playbook: dict[str, Any]) -> dict[str, Any]:
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
        "success_criteria_results": scripted_playbook.get("success_criteria_results", []),
        "sub_playbook": scripted_playbook.get("sub_playbook", None),
    }


def extend_tool_traces_from_script(
    tool_traces: list[dict[str, Any]],
    scripted_playbook: dict[str, Any],
) -> None:
    script_steps = scripted_playbook.get("steps")
    if isinstance(script_steps, list):
        for step in script_steps:
            if not isinstance(step, dict):
                continue
            tool_traces.append(
                {
                    "name": step.get("name", ""),
                    "arguments": step.get("arguments", {}),
                    "result": step.get("output", ""),
                }
            )
    success_criteria_results = scripted_playbook.get("success_criteria_results")
    if isinstance(success_criteria_results, list):
        for criterion in success_criteria_results:
            if not isinstance(criterion, dict):
                continue
            attempts = criterion.get("attempts")
            if isinstance(attempts, list):
                for attempt in attempts:
                    if not isinstance(attempt, dict):
                        continue
                    tool_traces.append(
                        {
                            "name": attempt.get("name", ""),
                            "arguments": attempt.get("arguments", {}),
                            "result": attempt.get("output", ""),
                        }
                    )


def build_chat_messages(
    user_message: str,
    *,
    fault_doc_context: str = "",
    history: list[dict[str, Any]] | None = None,
) -> list[Any]:
    AIMessage, HumanMessage, SystemMessage = load_chat_message_classes()

    normalized_user_message = normalize_message_content(user_message)
    if not normalized_user_message:
        raise ApiError("聊天内容不能为空")

    system_prompt = build_fault_chat_system_prompt()
    if fault_doc_context:
        system_prompt = f"{system_prompt}\n\n{fault_doc_context}"

    messages: list[Any] = [SystemMessage(content=system_prompt)]
    normalized_history = history[-(MAX_CHAT_HISTORY_TURNS * 2) :] if isinstance(history, list) else []
    for item in normalized_history:
        if not isinstance(item, dict):
            continue
        role = normalize_message_content(item.get("role", "")).lower()
        content = normalize_message_content(item.get("content", ""))
        if not content:
            continue
        if role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "user":
            messages.append(HumanMessage(content=content))
    messages.append(HumanMessage(content=normalized_user_message))
    return messages


def invoke_chat_model(
    user_message: str,
    *,
    runtime_context: dict[str, Any] | None = None,
    tool_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    AIMessage, HumanMessage, _ = load_chat_message_classes()
    normalized_user_message = normalize_message_content(user_message)
    confirmation_reply = resolve_pending_confirmation_reply(normalized_user_message, tool_context)
    if confirmation_reply.get("matched") and not confirmation_reply.get("resolved"):
        return {
            "model": OPENAI_CHAT_MODEL,
            "message": str(confirmation_reply.get("message") or ""),
            "clarify": confirmation_reply.get("clarify"),
            "tool_traces": [],
        }
    effective_tool_context = merge_tool_context(tool_context)
    selected_playbook = None
    route_result = route_fault_playbook(normalized_user_message)
    selected_playbook_id = normalize_message_content(route_result.get("playbook_id", ""))
    if selected_playbook_id:
        for playbook in list_playbooks():
            if str(playbook.get("id") or "").strip() == selected_playbook_id:
                selected_playbook = playbook
                break
    fault_doc_context = build_fault_doc_context_from_playbook(selected_playbook)
    messages = build_chat_messages(
        user_message,
        fault_doc_context=fault_doc_context,
        history=list_recent_chat_history(tool_context, MAX_CHAT_HISTORY_TURNS),
    )
    logger.info("=== Chat 开始 | user_message: %s", user_message[:50])
    append_fault_trace(
        "chat_start",
        {
            "user_message": user_message,
            "runtime_context": runtime_context or {},
            "tool_count": len(agent_tool_registry.list_definitions()),
            "playbook_route": route_result,
        },
    )

    llm = build_chat_model()
    tool_traces: list[dict[str, Any]] = []
    scripted_playbook = (
        run_scripted_fault_playbook_by_id(selected_playbook_id, effective_tool_context)
        if selected_playbook_id
        else None
    )
    if scripted_playbook:
        append_fault_trace("playbook_script", scripted_playbook)
        extend_tool_traces_from_script(tool_traces, scripted_playbook)
        if bool(scripted_playbook.get("pending_confirmation")):
            confirmation_payload = scripted_playbook.get("confirmation") if isinstance(scripted_playbook.get("confirmation"), dict) else {}
            return {
                "model": OPENAI_CHAT_MODEL,
                "message": str(confirmation_payload.get("message") or scripted_playbook.get("conclusion") or "等待人工确认"),
                "clarify": confirmation_payload,
                "tool_traces": tool_traces,
            }
        script_context = build_script_context(scripted_playbook)
        messages.append(HumanMessage(content="【脚本执行结果】\n" + json.dumps(script_context, ensure_ascii=False, indent=2)))
    return run_chat_loop(
        llm=llm,
        messages=messages,
        effective_tool_context=effective_tool_context,
        human_message_class=HumanMessage,
        ai_message_class=AIMessage,
        tool_traces=tool_traces,
    )


def run_chat_loop(
    *,
    llm: Any,
    messages: list[Any],
    effective_tool_context: dict[str, Any] | None,
    human_message_class: type[Any],
    ai_message_class: type[Any],
    tool_traces: list[dict[str, Any]],
) -> dict[str, Any]:
    response = None
    for _ in range(6):
        logger.info("LLM 聊天模型开始调用 | model=%s | message_count=%d", OPENAI_CHAT_MODEL, len(messages))
        append_fault_trace(
            "chat_model_input",
            {
                "model": OPENAI_CHAT_MODEL,
                "messages": format_message_log(messages),
            },
        )
        response = llm.invoke(messages)
        logger.info("LLM 聊天模型返回 | model=%s", OPENAI_CHAT_MODEL)
        append_fault_trace(
            "chat_model_output",
            {
                "model": OPENAI_CHAT_MODEL,
                "response": format_response_log(response),
            },
        )
        content = normalize_message_content(getattr(response, "content", ""))
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
        if parsed is None:
            correction_message = (
                "上一个回复不符合格式要求。"
                "请只输出一个 JSON 对象，且如果需要排查必须输出 command，"
                "不要输出步骤说明、不要输出自然语言总结。"
            )
            messages.append(human_message_class(content=correction_message))
            continue

        response_type = str(parsed.get("type") or parsed.get("mode") or "").strip().lower()
        if response_type in {"final", "answer", "summary"}:
            final_message = extract_final_message(parsed, content)
            if not final_message:
                raise ApiError("模型未返回有效内容")
            if not final_message_has_required_sections(final_message):
                correction_message = (
                    "上一个 final 回复没有按固定模板输出。"
                    "请重新输出一个 JSON 对象，保持 `type` 为 `final`，"
                    "并让 `answer` 严格包含三段：`问题：`、`排查过程：`、`结论：`。"
                )
                messages.append(human_message_class(content=correction_message))
                continue
            append_fault_trace(
                "chat_final",
                {
                    "type": response_type or "final",
                    "message": final_message,
                    "tool_traces": tool_traces,
                },
            )
            logger.info("=== Chat 结束 (final) | 工具调用次数: %d", len(tool_traces))
            return {
                "model": OPENAI_CHAT_MODEL,
                "message": final_message,
                "tool_traces": tool_traces,
            }

        if response_type == "clarify":
            questions = parsed.get("questions")
            if isinstance(questions, list):
                rendered_questions = [format_clarify_item(item) for item in questions]
                question_text = "\n\n".join(item for item in rendered_questions if item)
            else:
                question_text = extract_final_message(parsed, content)
            final_message = normalize_message_content(question_text)
            if not final_message:
                raise ApiError("模型未返回有效内容")
            append_fault_trace(
                "chat_clarify",
                {
                    "questions": questions if isinstance(questions, list) else final_message,
                    "tool_traces": tool_traces,
                },
            )
            logger.info("=== Chat 结束 (clarify) | 工具调用次数: %d", len(tool_traces))
            return {
                "model": OPENAI_CHAT_MODEL,
                "message": final_message,
                "tool_traces": tool_traces,
            }

        commands = normalize_command_list(parsed)
        if not commands:
            final_message = extract_final_message(parsed, content)
            if not final_message:
                messages.append(
                    human_message_class(
                        content="上一个回复没有给出可执行命令。请重新输出 command / clarify / final 的 JSON 对象。"
                    )
                )
                continue
            append_fault_trace(
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

        messages.append(ai_message_class(content=content))
        for command in commands:
            tool_name = str(command.get("name") or command.get("tool_name") or "").strip()
            if not tool_name:
                raise ApiError("模型输出的命令缺少工具名")
            tool_args = command.get("arguments")
            if not isinstance(tool_args, dict):
                tool_args = command.get("args") if isinstance(command.get("args"), dict) else {}
            append_fault_trace(
                "tool_call_start",
                {
                    "name": tool_name,
                    "arguments": tool_args,
                },
            )
            logger.info("🔧 执行工具: %s, 参数: %s", tool_name, json.dumps(tool_args, ensure_ascii=False))
            try:
                tool_result = agent_tool_registry.call_tool(tool_name, tool_args, effective_tool_context)
                tool_traces.append({"name": tool_name, "arguments": tool_args, "result": tool_result})
                append_fault_trace(
                    "tool_call",
                    {
                        "name": tool_name,
                        "arguments": tool_args,
                        "result": tool_result,
                    },
                )
                logger.info("✅ 工具执行成功: %s", tool_name)
            except Exception as exc:  # noqa: BLE001
                error_message = exc.message if isinstance(exc, ApiError) else str(exc)
                tool_result = {"ok": False, "error": error_message}
                tool_traces.append({"name": tool_name, "arguments": tool_args, "error": error_message})
                append_fault_trace(
                    "tool_call_error",
                    {
                        "name": tool_name,
                        "arguments": tool_args,
                        "error": error_message,
                    },
                )
                logger.error("❌ 工具执行失败: %s, 错误: %s", tool_name, error_message)
            append_fault_trace(
                "tool_call_end",
                {
                    "name": tool_name,
                    "arguments": tool_args,
                    "ok": bool(tool_result.get("ok", True)) if isinstance(tool_result, dict) else True,
                },
            )
            messages.append(human_message_class(content=build_tool_feedback_message(tool_name, tool_args, tool_result)))

    if response is None:
        raise ApiError("模型未返回有效内容")

    content = getattr(response, "content", "")
    normalized_content = normalize_message_content(strip_think_blocks(str(content)))
    if not normalized_content:
        raise ApiError("模型未返回有效内容")
    append_fault_trace(
        "chat_final",
        {
            "type": "loop_exit",
            "message": normalized_content,
            "tool_traces": tool_traces,
        },
    )
    logger.warning("=== Chat 结束 (loop_exit) | 达到最大循环次数 | 工具调用次数: %d", len(tool_traces))
    return {
        "model": OPENAI_CHAT_MODEL,
        "message": normalized_content,
        "tool_traces": tool_traces,
    }
