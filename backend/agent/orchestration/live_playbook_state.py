from __future__ import annotations

import copy
import json
import threading
import time
from collections import deque
from collections.abc import Iterator
from typing import Any

from ..common import normalize_message_content
from ..playbooks.loader import find_playbook_by_id

_state_lock = threading.RLock()
_live_state: dict[str, Any] = {
    "playbook": None,
    "playbook_execution": None,
    "pending_confirmation": None,
    "updated_at": 0.0,
    "version": 0,
}
_live_events: deque[dict[str, Any]] = deque(maxlen=512)
_state_changed = threading.Condition(_state_lock)


def _now() -> float:
    return time.time()


def _clone_payload(value: Any) -> Any:
    return copy.deepcopy(value)


def build_matched_playbook_payload(playbook: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(playbook, dict):
        return None
    return {
        "id": normalize_message_content(playbook.get("id", "")),
        "title": normalize_message_content(playbook.get("title", "")),
        "playbook_id": normalize_message_content(playbook.get("id", "")),
        "playbook_title": normalize_message_content(playbook.get("title", "")),
        "root": playbook.get("root") if isinstance(playbook.get("root"), dict) else {},
        "source_path": normalize_message_content(playbook.get("source_path", "")),
        "rules_source_path": normalize_message_content(playbook.get("rules_source_path", "")),
    }


def build_matched_playbook_payload_by_id(playbook_id: str) -> dict[str, Any] | None:
    if not playbook_id:
        return None
    return build_matched_playbook_payload(find_playbook_by_id(playbook_id))


def build_playbook_execution_payload(
    scripted_playbook: dict[str, Any] | None,
    *,
    pending_confirmation: dict[str, Any] | None = None,
    active_node_path: str = "",
    active_node_message: str = "",
) -> dict[str, Any] | None:
    if not isinstance(scripted_playbook, dict) and not isinstance(pending_confirmation, dict) and not active_node_path:
        return None

    matched_context = scripted_playbook.get("matched_context") if isinstance(scripted_playbook, dict) else {}
    root = matched_context.get("root") if isinstance(matched_context, dict) else {}
    steps = scripted_playbook.get("steps") if isinstance(scripted_playbook, dict) else []
    leaf_statuses: dict[str, dict[str, Any]] = {}
    script_passed = bool(scripted_playbook.get("passed")) if isinstance(scripted_playbook, dict) else False
    confirmation_node_path = normalize_message_content((pending_confirmation or {}).get("node_path", ""))
    current_active_node_path = normalize_message_content(active_node_path) or confirmation_node_path
    final_conclusion = normalize_message_content((scripted_playbook or {}).get("conclusion", ""))

    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            node_path = normalize_message_content(step.get("node_path", ""))
            if not node_path:
                continue
            passed = step.get("passed")
            if passed:
                status = "success"
            elif node_path == current_active_node_path:
                status = "pending"
            else:
                status = "failed"
            leaf_statuses[node_path] = {
                "status": status,
                "passed": bool(passed),
                "message": normalize_message_content(step.get("success_message") or step.get("failure_message") or step.get("output") or ""),
            }

    if current_active_node_path:
        leaf_statuses[current_active_node_path] = {
            "status": "pending",
            "passed": False,
            "message": normalize_message_content(active_node_message or (pending_confirmation or {}).get("message", "")),
        }

    node_statuses: dict[str, dict[str, Any]] = {}

    def mark_skipped(node: Any, path: str) -> None:
        if not isinstance(node, dict):
            return
        current = node_statuses.get(path)
        if current and current.get("status") != "unstarted":
            return
        node_statuses[path] = {
            "status": "skipped",
            "message": normalize_message_content(node.get("message") or node.get("success_message") or node.get("failure_message") or ""),
        }
        children = node.get("children") if isinstance(node.get("children"), list) else []
        for index, child in enumerate(children):
            mark_skipped(child, f"{path}.children[{index}]")

    def walk(node: Any, path: str = "root") -> str:
        if not isinstance(node, dict):
            return "unstarted"

        explicit = leaf_statuses.get(path)
        children = node.get("children") if isinstance(node.get("children"), list) else []
        node_type = normalize_message_content(node.get("type", "")).lower()

        if not children:
            status = normalize_message_content((explicit or {}).get("status", "")) or "unstarted"
            node_statuses[path] = {
                "status": status,
                "message": normalize_message_content((explicit or {}).get("message", "")),
            }
            return status

        child_statuses = []
        for index, child in enumerate(children):
            child_statuses.append(walk(child, f"{path}.children[{index}]"))

        def set_child_status(index: int, status: str) -> None:
            child_path = f"{path}.children[{index}]"
            current = normalize_message_content((node_statuses.get(child_path) or {}).get("status", ""))
            if current and current != "unstarted":
                return
            child_statuses[index] = status
            node_statuses[child_path] = {
                "status": status,
                "message": normalize_message_content(children[index].get("message") or children[index].get("success_message") or children[index].get("failure_message") or ""),
            }

        if current_active_node_path and any(
            current_active_node_path == f"{path}.children[{index}]"
            or current_active_node_path.startswith(f"{path}.children[{index}].")
            for index in range(len(children))
        ):
            status = "pending"
        elif node_type == "sequence":
            first_progress_index = next((index for index, item in enumerate(child_statuses) if item in {"pending", "success", "failed"}), None)
            if first_progress_index is not None:
                for index in range(first_progress_index):
                    if child_statuses[index] == "unstarted":
                        set_child_status(index, "success")
            if any(item == "failed" for item in child_statuses):
                first_failed = next(index for index, item in enumerate(child_statuses) if item == "failed")
                for index in range(first_failed + 1, len(children)):
                    mark_skipped(children[index], f"{path}.children[{index}]")
                status = "failed"
            elif any(item == "pending" for item in child_statuses):
                status = "pending"
            elif all(item == "success" for item in child_statuses):
                status = "success"
            elif any(item == "success" for item in child_statuses):
                status = "pending"
            else:
                status = "unstarted"
        elif node_type == "selector":
            first_progress_index = next((index for index, item in enumerate(child_statuses) if item in {"pending", "success", "failed"}), None)
            if first_progress_index is not None:
                for index in range(first_progress_index):
                    if child_statuses[index] == "unstarted":
                        set_child_status(index, "failed")
            if any(item == "success" for item in child_statuses):
                first_success = next(index for index, item in enumerate(child_statuses) if item == "success")
                for index in range(first_success + 1, len(children)):
                    mark_skipped(children[index], f"{path}.children[{index}]")
                status = "success"
            elif any(item == "pending" for item in child_statuses):
                status = "pending"
            elif all(item == "failed" for item in child_statuses):
                status = "failed"
            elif any(item == "failed" for item in child_statuses):
                status = "pending"
            else:
                status = "unstarted"
        else:
            if any(item == "failed" for item in child_statuses):
                status = "failed"
            elif any(item == "pending" for item in child_statuses):
                status = "pending"
            elif all(item == "success" for item in child_statuses):
                status = "success"
            elif any(item == "success" for item in child_statuses):
                status = "pending"
            else:
                status = "unstarted"

        node_statuses[path] = {
            "status": status,
            "message": normalize_message_content(node.get("message") or node.get("success_message") or node.get("failure_message") or ""),
        }
        return status

    root_status = walk(root, "root") if isinstance(root, dict) else ("pending" if current_active_node_path else ("success" if script_passed else "failed"))

    return {
        "overall_status": root_status,
        "active_node_path": current_active_node_path,
        "node_statuses": node_statuses,
        "conclusion": final_conclusion,
    }


def clear_live_playbook_state() -> None:
    “”"清空当前的 playbook 执行状态，通常在执行完成后调用，或者在需要强制重置状态时调用。"""
    with _state_lock:
        _live_state["playbook"] = None
        _live_state["playbook_execution"] = None
        _live_state["pending_confirmation"] = None
        _live_state["updated_at"] = _now()
        _live_state["version"] = int(_live_state.get("version") or 0) + 1
        _live_events.clear()
        _live_events.append(
            {
                "version": _live_state["version"],
                "updated_at": _live_state["updated_at"],
                "playbook": None,
                "playbook_execution": None,
                "pending_confirmation": None,
            }
        )
        _state_changed.notify_all()


def reset_live_playbook_execution(*, playbook: dict[str, Any] | None = None) -> None:
    """重置当前的 playbook 执行状态，通常在开始新的 playbook 执行时调用。可以选择性地提供一个新的 playbook 来替换当前状态中的 playbook。"""
    with _state_lock:
        if playbook is not None:
            _live_state["playbook"] = _clone_payload(playbook)
        _live_state["playbook_execution"] = None
        _live_state["pending_confirmation"] = None
        _live_state["updated_at"] = _now()
        _live_state["version"] = int(_live_state.get("version") or 0) + 1
        _live_events.append(
            {
                "version": _live_state["version"],
                "updated_at": _live_state["updated_at"],
                "playbook": _clone_payload(_live_state.get("playbook")),
                "playbook_execution": None,
                "pending_confirmation": None,
            }
        )
        _state_changed.notify_all()


def publish_live_playbook_state(
    *,
    playbook: dict[str, Any] | None = None,
    scripted_playbook: dict[str, Any] | None = None,
    pending_confirmation: dict[str, Any] | None = None,
    active_node_path: str = "",
    active_node_message: str = "",
) -> None:
    with _state_lock:
        _live_state["playbook"] = _clone_payload(playbook)
        _live_state["playbook_execution"] = build_playbook_execution_payload(
            scripted_playbook,
            pending_confirmation=pending_confirmation,
            active_node_path=active_node_path,
            active_node_message=active_node_message,
        )
        _live_state["pending_confirmation"] = _clone_payload(pending_confirmation) if isinstance(pending_confirmation, dict) else None
        _live_state["updated_at"] = _now()
        _live_state["version"] = int(_live_state.get("version") or 0) + 1
        _live_events.append(
            {
                "version": _live_state["version"],
                "updated_at": _live_state["updated_at"],
                "playbook": _clone_payload(_live_state["playbook"]),
                "playbook_execution": _clone_payload(_live_state["playbook_execution"]),
                "pending_confirmation": _clone_payload(_live_state["pending_confirmation"]),
            }
        )
        _state_changed.notify_all()


def get_live_playbook_state(*, since_version: int = 0) -> dict[str, Any]:
    with _state_lock:
        latest_version = int(_live_state.get("version") or 0)
        events = [
            _clone_payload(event)
            for event in _live_events
            if int(event.get("version") or 0) > since_version
        ]
        return {
            "playbook": _clone_payload(_live_state.get("playbook")),
            "playbook_execution": _clone_payload(_live_state.get("playbook_execution")),
            "pending_confirmation": _clone_payload(_live_state.get("pending_confirmation")),
            "updated_at": _live_state.get("updated_at") or 0.0,
            "version": latest_version,
            "events": events,
        }


def stream_live_playbook_events(*, since_version: int = 0, heartbeat_seconds: float = 60.0) -> Iterator[str]:
    current_version = max(int(since_version), 0)
    while True:
        payload: dict[str, Any] | None = None
        with _state_changed:
            latest_version = int(_live_state.get("version") or 0)
            if latest_version <= current_version:
                _state_changed.wait(timeout=heartbeat_seconds)
                latest_version = int(_live_state.get("version") or 0)
            if latest_version > current_version:
                payload = get_live_playbook_state(since_version=current_version)
                current_version = int(payload.get("version") or current_version)
        if payload is not None:
            yield "event: playbook_state\n"
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            continue
        yield "event: heartbeat\n"
        yield "data: {}\n\n"
