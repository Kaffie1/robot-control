from __future__ import annotations

from typing import Any

from ..common import append_fault_trace, logger, normalize_message_content
from ..playbooks.matcher import match_playbook_by_title
from .router_nodes import load_catalog_node, route_playbook_node
from .router_state import FaultRouteState

try:
    from langgraph.graph import END, StateGraph
except Exception:
    END = None
    StateGraph = None


def _build_route_graph() -> Any:
    if StateGraph is None or END is None:
        return None
    graph = StateGraph(FaultRouteState)
    graph.add_node("load_catalog", load_catalog_node)
    graph.add_node("route_playbook", route_playbook_node)
    graph.set_entry_point("load_catalog")
    graph.add_edge("load_catalog", "route_playbook")
    graph.add_edge("route_playbook", END)
    return graph.compile()


ROUTE_GRAPH = _build_route_graph()


def route_fault_playbook(user_message: str) -> dict[str, str]:
    normalized_user_message = normalize_message_content(user_message)
    logger.info("开始故障路由 | user_message=%s", normalized_user_message[:120])
    append_fault_trace(
        "route_start",
        {
            "user_message": normalized_user_message,
        },
    )
    if ROUTE_GRAPH is None:
        fallback = match_playbook_by_title(user_message)
        result = {
            "playbook_id": normalize_message_content(fallback.get("id", "")) if isinstance(fallback, dict) else "",
            "playbook_title": normalize_message_content(fallback.get("title", "")) if isinstance(fallback, dict) else "",
            "reason": "langgraph 不可用，已回退到标题匹配" if isinstance(fallback, dict) else "",
        }
        append_fault_trace("route_fallback", result)
        return result

    result = ROUTE_GRAPH.invoke({"user_message": normalized_user_message})
    playbook_id = normalize_message_content(result.get("selected_playbook_id", ""))
    playbook_title = normalize_message_content(result.get("selected_playbook_title", ""))
    reason = normalize_message_content(result.get("reason", ""))
    if playbook_id and playbook_title:
        route_result = {
            "playbook_id": playbook_id,
            "playbook_title": playbook_title,
            "reason": reason,
        }
        append_fault_trace("route_finish", route_result)
        return route_result
    fallback = match_playbook_by_title(user_message)
    route_result = {
        "playbook_id": normalize_message_content(fallback.get("id", "")) if isinstance(fallback, dict) else "",
        "playbook_title": normalize_message_content(fallback.get("title", "")) if isinstance(fallback, dict) else "",
        "reason": reason or ("LLM 未命中，已回退到标题匹配" if isinstance(fallback, dict) else ""),
    }
    append_fault_trace("route_finish", route_result)
    return route_result
