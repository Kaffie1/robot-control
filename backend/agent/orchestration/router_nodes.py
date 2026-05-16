from __future__ import annotations

from ..common import append_fault_trace, extract_json_payload, logger, normalize_message_content
from .model import build_router_model
from ..playbooks.loader import get_playbook_catalog
from .prompts import build_fault_route_prompt
from .router_state import FaultRouteState
from ...config import OPENAI_CHAT_MODEL


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


def route_playbook_node(state: FaultRouteState) -> FaultRouteState:
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
    return {
        "selected_playbook_id": selected_playbook_id,
        "selected_playbook_title": selected_title,
        "reason": reason,
    }
