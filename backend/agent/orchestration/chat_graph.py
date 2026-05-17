from __future__ import annotations

import json
import uuid
from typing import Any

from ...config import OPENAI_CHAT_MODEL
from ...errors import ApiError
from ..common import append_fault_trace, logger, normalize_message_content, strip_think_blocks
from .router_state import FaultChatState
try:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command
except Exception:
    InMemorySaver = None
    Command = None
from .live_playbook_state import (
    build_matched_playbook_payload_by_id,
    build_playbook_execution_payload,
)
from .router_nodes import (
    build_messages_node,
    call_chat_model_node,
    call_tools_node,
    execute_playbook_node,
    interpret_model_output_node,
    load_catalog_node,
    route_after_playbook_node,
    route_after_interpret_node,
    route_playbook_node,
    wait_for_playbook_render_node,
)

try:
    from langgraph.graph import END, StateGraph
except Exception:
    END = None
    StateGraph = None


def _build_chat_graph() -> Any:
    if StateGraph is None or END is None:
        return None
    graph = StateGraph(FaultChatState)
    graph.add_node("load_catalog", load_catalog_node)
    graph.add_node("route_playbook", route_playbook_node)
    graph.add_node("wait_playbook_render", wait_for_playbook_render_node)
    graph.add_node("build_messages", build_messages_node)
    graph.add_node("execute_playbook", execute_playbook_node)
    graph.add_node("call_model", call_chat_model_node)
    graph.add_node("interpret_output", interpret_model_output_node)
    graph.add_node("call_tools", call_tools_node)
    graph.set_entry_point("load_catalog")
    graph.add_edge("load_catalog", "route_playbook")
    graph.add_edge("route_playbook", "wait_playbook_render")
    graph.add_edge("wait_playbook_render", "build_messages")
    graph.add_edge("build_messages", "execute_playbook")
    graph.add_conditional_edges(
        "execute_playbook",
        route_after_playbook_node,
        {
            "finish": END,
            "call_model": "call_model",
        },
    )
    graph.add_edge("call_model", "interpret_output")
    graph.add_conditional_edges(
        "interpret_output",
        route_after_interpret_node,
        {
            "finish": END,
            "loop_exit": END,
            "retry": "call_model",
            "tool_call": "call_tools",
        },
    )
    graph.add_edge("call_tools", "call_model")
    compile_kwargs: dict[str, Any] = {}
    if InMemorySaver is not None:
        compile_kwargs["checkpointer"] = InMemorySaver()
    return graph.compile(**compile_kwargs)


CHAT_GRAPH = _build_chat_graph()


def _format_loop_exit_message(result: dict[str, Any], fallback_message: str) -> str:
    parsed = result.get("parsed_response")
    if isinstance(parsed, dict):
        commands = parsed.get("commands")
        if isinstance(commands, list) and commands:
            first = commands[0] if isinstance(commands[0], dict) else {}
            tool_name = normalize_message_content(first.get("name") or first.get("tool_name") or "")
            tool_args = first.get("arguments") if isinstance(first.get("arguments"), dict) else {}
            lines = ["当前还在按恢复流程继续排查，但本轮自动执行已达到上限。"]
            if tool_name:
                lines.append(f"建议下一步工具：{tool_name}")
            if tool_args:
                arg_text = ", ".join(f"{key}={value}" for key, value in tool_args.items())
                if arg_text:
                    lines.append(f"建议参数：{arg_text}")
            return "\n".join(lines).strip()
    return fallback_message


def run_fault_chat_graph(
    user_message: str,
    *,
    runtime_context: dict[str, Any] | None = None,
    tool_context: dict[str, Any] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
    resume_continuation: dict[str, Any] | None = None,
    confirmation_response: str = "",
    prefetched_playbook_id: str = "",
    prefetched_playbook_title: str = "",
    prefetched_reason: str = "",
) -> dict[str, Any]:
    if CHAT_GRAPH is None:
        raise ApiError("聊天图依赖未安装，请先安装 langgraph")
    continuation_kind = normalize_message_content((resume_continuation or {}).get("kind", "")) if isinstance(resume_continuation, dict) else ""
    thread_id = normalize_message_content((resume_continuation or {}).get("thread_id", "")) if isinstance(resume_continuation, dict) else ""
    if not thread_id:
        thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}
    invoke_input: Any
    if continuation_kind == "playbook_render_ready" and Command is not None:
        invoke_input = Command(resume=True)
    else:
        invoke_input = {
            "user_message": normalize_message_content(user_message),
            "conversation_history": list(conversation_history or [])[:10],
            "runtime_context": runtime_context or {},
            "tool_context": dict(tool_context or {}),
            "effective_tool_context": dict(tool_context or {}),
            "tool_traces": [],
            "model_loop_count": 0,
            "resume_continuation": dict(resume_continuation or {}) if isinstance(resume_continuation, dict) else None,
            "confirmation_response": normalize_message_content(confirmation_response),
            "prefetched_playbook_id": normalize_message_content(prefetched_playbook_id),
            "prefetched_playbook_title": normalize_message_content(prefetched_playbook_title),
            "prefetched_reason": normalize_message_content(prefetched_reason),
        }
    result = CHAT_GRAPH.invoke(invoke_input, config=config)
    matched_playbook = build_matched_playbook_payload_by_id(result.get("selected_playbook_id", ""))
    playbook_execution = build_playbook_execution_payload(
        result.get("scripted_playbook"),
        pending_confirmation=result.get("pending_confirmation"),
    )
    interrupts = result.get("__interrupt__")
    if isinstance(interrupts, (list, tuple)) and interrupts:
        interrupt_item = interrupts[0]
        pending_playbook_render = getattr(interrupt_item, "value", None)
        continuation = {
            "kind": "playbook_render_ready",
            "user_message": normalize_message_content(user_message),
            "playbook_id": normalize_message_content(result.get("selected_playbook_id", "")),
            "playbook_title": normalize_message_content(result.get("selected_playbook_title", "")),
            "reason": normalize_message_content(result.get("reason", "")),
            "thread_id": thread_id,
        }
        logger.info(
            "=== Chat 中断 (playbook_render_wait) | playbook=%s",
            continuation["playbook_id"] or "-",
        )
        return {
            "model": OPENAI_CHAT_MODEL,
            "message": normalize_message_content(pending_playbook_render.get("message", "")) or "等待前端流程图加载完成",
            "tool_traces": result.get("tool_traces") or [],
            "continuation": continuation,
            "playbook": pending_playbook_render.get("playbook"),
            "playbook_execution": playbook_execution,
        }
    pending_confirmation = result.get("pending_confirmation")
    if isinstance(pending_confirmation, dict):
        continuation = {
            "kind": "playbook_confirmation",
            "user_message": normalize_message_content(user_message),
            "playbook_id": normalize_message_content(result.get("selected_playbook_id", "")),
            "playbook_title": normalize_message_content(result.get("selected_playbook_title", "")),
            "reason": normalize_message_content(result.get("reason", "")),
            "tool_context": dict(result.get("effective_tool_context") or {}),
            "resume_state": result.get("playbook_resume_state") if isinstance(result.get("playbook_resume_state"), dict) else {},
            "pending_confirmation": pending_confirmation,
        }
        logger.info(
            "=== Chat 中断 (confirmation) | playbook=%s | 工具调用次数: %d",
            continuation["playbook_id"] or "-",
            len(result.get("tool_traces") or []),
        )
        return {
            "model": OPENAI_CHAT_MODEL,
            "message": normalize_message_content(pending_confirmation.get("message", "")) or "需要人工确认后继续",
            "tool_traces": result.get("tool_traces") or [],
            "pending_confirmation": pending_confirmation,
            "continuation": continuation,
            "playbook": matched_playbook,
            "playbook_execution": playbook_execution,
        }
    final_message = normalize_message_content(result.get("final_message", ""))
    if final_message:
        logger.info("=== Chat 结束 (%s) | 工具调用次数: %d", result.get("result_kind") or "final", len(result.get("tool_traces") or []))
        return {
            "model": OPENAI_CHAT_MODEL,
            "message": final_message,
            "tool_traces": result.get("tool_traces") or [],
            "playbook": matched_playbook,
            "playbook_execution": playbook_execution,
        }
    response = result.get("response")
    content = getattr(response, "content", "")
    normalized_content = normalize_message_content(strip_think_blocks(str(content)))
    if not normalized_content:
        raise ApiError("模型未返回有效内容")
    append_fault_trace(
        "chat_final",
        {
            "type": "loop_exit",
            "message": normalized_content,
            "tool_traces": result.get("tool_traces") or [],
        },
    )
    logger.warning("=== Chat 结束 (loop_exit) | 达到最大循环次数 | 工具调用次数: %d", len(result.get("tool_traces") or []))
    user_facing_message = _format_loop_exit_message(result, normalized_content)
    return {
        "model": OPENAI_CHAT_MODEL,
        "message": user_facing_message,
        "tool_traces": result.get("tool_traces") or [],
        "playbook": matched_playbook,
        "playbook_execution": playbook_execution,
    }
