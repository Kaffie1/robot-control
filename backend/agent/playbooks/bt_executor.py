from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import py_trees

from ...models import ApiError
from ..common import store_pending_confirmation
from ..rules import build_playbook_rule_context
from .loader import find_playbook_by_id


def _normalize_status(value: str) -> py_trees.common.Status:
    normalized = str(value or "").strip().lower()
    if normalized == "success":
        return py_trees.common.Status.SUCCESS
    if normalized == "running":
        return py_trees.common.Status.RUNNING
    return py_trees.common.Status.FAILURE


def _short_text(value: Any, *, limit: int = 320) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…"


@dataclass
class BehaviourTreeState:
    playbook: dict[str, Any]
    tool_context: dict[str, Any]
    visited_ids: set[str]
    depth: int
    max_depth: int
    steps: list[dict[str, Any]] = field(default_factory=list)
    observations: dict[str, bool | None] = field(default_factory=dict)
    recent_tasks: list[dict[str, Any]] = field(default_factory=list)
    sub_playbooks: list[dict[str, Any]] = field(default_factory=list)
    pending_confirmation: bool = False
    confirmation: dict[str, Any] | None = None
    conclusion: str = ""
    next_action: str = ""


def _update_observations(state: BehaviourTreeState, step: dict[str, Any]) -> None:
    from .executor import update_observations

    update_observations(state.observations, step)


def _run_leaf_step(node_spec: dict[str, Any], tool_context: dict[str, Any]) -> dict[str, Any]:
    from .executor import run_script_step, step_passed

    wait_seconds = max(int(node_spec.get("wait_seconds") or 0), 0)
    confirm_times = max(int(node_spec.get("confirm_times") or 1), 1)
    spec_without_wait = dict(node_spec)
    spec_without_wait.pop("wait_seconds", None)
    spec_without_wait.pop("confirm_times", None)
    attempts: list[dict[str, Any]] = []
    if wait_seconds:
        time.sleep(wait_seconds)
    passed = True
    pending_confirmation = False
    for _ in range(confirm_times):
        attempt = run_script_step(spec_without_wait, tool_context)
        attempts.append(attempt)
        if bool(attempt.get("pending_confirmation")):
            pending_confirmation = True
            passed = False
            break
        if not step_passed(attempt):
            passed = False
            break
    last_attempt = attempts[-1] if attempts else {}
    result = {
        "name": str(node_spec.get("name") or node_spec.get("tool_name") or "").strip(),
        "tool_name": str(node_spec.get("tool_name") or "").strip(),
        "arguments": node_spec.get("arguments") if isinstance(node_spec.get("arguments"), dict) else {},
        "output": last_attempt.get("output", ""),
        "passed": passed,
        "pending_confirmation": pending_confirmation,
        "assert_ref": str(node_spec.get("assert_ref") or node_spec.get("expect") or "").strip(),
        "wait_seconds": wait_seconds,
        "confirm_times": confirm_times,
        "attempts": attempts,
        "confirmation": last_attempt.get("confirmation"),
    }
    if len(attempts) == 1:
        result.update(last_attempt)
        result["wait_seconds"] = wait_seconds
        result["confirm_times"] = confirm_times
        result["attempts"] = attempts
    return result


class ToolBehaviour(py_trees.behaviour.Behaviour):
    def __init__(self, node_spec: dict[str, Any], state: BehaviourTreeState, *, node_kind: str) -> None:
        super().__init__(name=str(node_spec.get("name") or node_spec.get("tool_name") or node_kind))
        self.node_spec = dict(node_spec)
        self.state = state
        self.node_kind = node_kind

    def update(self) -> py_trees.common.Status:
        result = _run_leaf_step(self.node_spec, self.state.tool_context)
        result["node_type"] = self.node_kind
        self.state.steps.append(result)
        _update_observations(self.state, result)
        if bool(result.get("pending_confirmation")):
            self.state.pending_confirmation = True
            self.state.confirmation = result.get("confirmation") if isinstance(result.get("confirmation"), dict) else {}
            self.state.conclusion = str((self.state.confirmation or {}).get("message") or "等待人工确认")
            self.state.next_action = "请根据提示补充输入后继续"
            raw_confirmation = self.node_spec.get("confirmation") if isinstance(self.node_spec.get("confirmation"), dict) else {}
            if self.state.confirmation:
                store_pending_confirmation(self.state.tool_context, self.state.confirmation)
            pending_payload = {
                **(self.state.confirmation or {}),
                "playbook_id": str(self.state.tool_context.get("playbook_id") or ""),
                "playbook_title": str(self.state.tool_context.get("playbook_title") or ""),
                "step_name": self.name,
                "tool_name": str(self.node_spec.get("tool_name") or ""),
                "confirmation": raw_confirmation,
                "store_as": str(((raw_confirmation.get("output") or {}) if isinstance(raw_confirmation, dict) else {}).get("store_as") or ""),
            }
            store_pending_confirmation(self.state.tool_context, pending_payload)
            return py_trees.common.Status.RUNNING
        if bool(result.get("passed")):
            success_message = str(self.node_spec.get("success_message") or "").strip()
            if success_message:
                self.state.conclusion = success_message
            return py_trees.common.Status.SUCCESS
        failure_message = str(self.node_spec.get("failure_message") or result.get("failure_message") or "").strip()
        if failure_message:
            self.state.conclusion = failure_message
            self.state.next_action = failure_message
        return py_trees.common.Status.FAILURE


class ResultBehaviour(py_trees.behaviour.Behaviour):
    def __init__(self, node_spec: dict[str, Any], state: BehaviourTreeState) -> None:
        super().__init__(name=str(node_spec.get("name") or "result"))
        self.node_spec = dict(node_spec)
        self.state = state

    def update(self) -> py_trees.common.Status:
        status = _normalize_status(self.node_spec.get("status") or "failure")
        message = str(self.node_spec.get("message") or "").strip()
        step = {
            "name": self.name,
            "tool_name": "",
            "arguments": {},
            "output": message,
            "passed": status == py_trees.common.Status.SUCCESS,
            "node_type": "result",
            "result_status": status.value,
        }
        self.state.steps.append(step)
        if message:
            self.state.conclusion = message
            self.state.next_action = message
        return status


class CallPlaybookBehaviour(py_trees.behaviour.Behaviour):
    def __init__(self, node_spec: dict[str, Any], state: BehaviourTreeState) -> None:
        super().__init__(name=str(node_spec.get("name") or node_spec.get("playbook_id") or "call_playbook"))
        self.node_spec = dict(node_spec)
        self.state = state

    def update(self) -> py_trees.common.Status:
        from .executor import execute_playbook

        playbook_id = str(self.node_spec.get("playbook_id") or self.node_spec.get("target_playbook_id") or "").strip()
        if not playbook_id:
            raise ApiError(f"行为树节点缺少 playbook_id: {self.name}")
        child_playbook = find_playbook_by_id(playbook_id)
        if child_playbook is None:
            raise ApiError(f"未找到子 playbook: {playbook_id}")
        child_result = execute_playbook(
            child_playbook,
            self.state.tool_context,
            visited_ids=set(self.state.visited_ids),
            depth=self.state.depth + 1,
            max_depth=self.state.max_depth,
        )
        self.state.sub_playbooks.append(child_result)
        step = {
            "name": self.name,
            "tool_name": "call_playbook",
            "arguments": {"playbook_id": playbook_id},
            "output": _short_text(child_result.get("conclusion") or child_result.get("next_action") or ""),
            "passed": bool(child_result.get("passed")),
            "pending_confirmation": bool(child_result.get("pending_confirmation")),
            "node_type": "call_playbook",
            "sub_playbook": child_result,
            "called_playbook_id": playbook_id,
        }
        self.state.steps.append(step)
        self.state.observations.update(
            {
                key: value
                for key, value in (child_result.get("observations") or {}).items()
                if key not in self.state.observations or value is not None
            }
        )
        if bool(child_result.get("pending_confirmation")):
            self.state.pending_confirmation = True
            self.state.confirmation = child_result.get("confirmation") if isinstance(child_result.get("confirmation"), dict) else {}
            self.state.conclusion = str(child_result.get("conclusion") or "等待人工确认")
            self.state.next_action = str(child_result.get("next_action") or "请根据提示补充输入后继续")
            return py_trees.common.Status.RUNNING
        if bool(child_result.get("passed")):
            success_message = str(self.node_spec.get("success_message") or "").strip()
            if success_message:
                self.state.conclusion = success_message
            return py_trees.common.Status.SUCCESS
        failure_message = str(child_result.get("conclusion") or child_result.get("next_action") or self.node_spec.get("failure_message") or "").strip()
        if failure_message:
            self.state.conclusion = failure_message
            self.state.next_action = failure_message
        return py_trees.common.Status.FAILURE


def _build_bt_node(node_spec: dict[str, Any], state: BehaviourTreeState) -> py_trees.behaviour.Behaviour:
    node_type = str(node_spec.get("type") or "").strip().lower()
    name = str(node_spec.get("name") or node_type or "node").strip()
    if node_type == "sequence":
        node = py_trees.composites.Sequence(
            name=name,
            memory=bool(node_spec.get("memory", False)),
        )
        children = node_spec.get("children") if isinstance(node_spec.get("children"), list) else []
        for child in children:
            if isinstance(child, dict):
                node.add_child(_build_bt_node(child, state))
        return node
    if node_type == "selector":
        node = py_trees.composites.Selector(
            name=name,
            memory=bool(node_spec.get("memory", False)),
        )
        children = node_spec.get("children") if isinstance(node_spec.get("children"), list) else []
        for child in children:
            if isinstance(child, dict):
                node.add_child(_build_bt_node(child, state))
        return node
    if node_type == "condition":
        return ToolBehaviour(node_spec, state, node_kind="condition")
    if node_type == "action":
        return ToolBehaviour(node_spec, state, node_kind="action")
    if node_type == "call_playbook":
        return CallPlaybookBehaviour(node_spec, state)
    if node_type == "result":
        return ResultBehaviour(node_spec, state)
    raise ApiError(f"不支持的行为树节点类型: {node_type}")


def execute_tree_playbook(
    playbook: dict[str, Any],
    tool_context: dict[str, Any] | None,
    *,
    visited_ids: set[str] | None = None,
    depth: int = 0,
    max_depth: int = 4,
) -> dict[str, Any]:
    playbook_id = str(playbook.get("id") or "").strip()
    playbook_title = str(playbook.get("title") or "").strip()
    playbook_source_path = str(playbook.get("source_path") or "").strip()
    playbook_rules_source_path = str(playbook.get("rules_source_path") or "").strip()
    if not playbook_id:
        return {"playbook_id": "", "playbook_title": playbook_title, "executed": False, "reason": "playbook 缺少 id", "matched_context": playbook}
    if depth > max_depth:
        return {"playbook_id": playbook_id, "playbook_title": playbook_title, "executed": False, "reason": "playbook 嵌套层级超过上限", "matched_context": playbook}
    normalized_visited_ids = set(visited_ids or set())
    if playbook_id in normalized_visited_ids:
        return {"playbook_id": playbook_id, "playbook_title": playbook_title, "executed": False, "reason": "检测到 playbook 循环引用", "matched_context": playbook}
    normalized_visited_ids.add(playbook_id)
    playbook_context = build_playbook_rule_context(
        {
            **dict(tool_context or {}),
            "playbook_id": playbook_id,
            "playbook_title": playbook_title,
            "playbook_source_path": playbook_source_path,
            "playbook_rules_source_path": playbook_rules_source_path,
        }
    )
    state = BehaviourTreeState(
        playbook=playbook,
        tool_context=playbook_context,
        visited_ids=normalized_visited_ids,
        depth=depth,
        max_depth=max_depth,
    )
    root_spec = playbook.get("root")
    if not isinstance(root_spec, dict):
        return {"playbook_id": playbook_id, "playbook_title": playbook_title, "executed": False, "reason": "行为树 playbook 缺少 root", "matched_context": playbook}
    root = _build_bt_node(root_spec, state)
    tree = py_trees.trees.BehaviourTree(root)
    tree.tick()
    if state.pending_confirmation:
        return {
            "playbook_id": playbook_id,
            "playbook_title": playbook_title,
            "executed": True,
            "steps": state.steps,
            "observations": state.observations,
            "pending_confirmation": True,
            "confirmation": state.confirmation or {},
            "conclusion": state.conclusion or "等待人工确认",
            "next_action": state.next_action or "请根据提示补充输入后继续",
            "recent_tasks": state.recent_tasks,
            "sub_playbooks": state.sub_playbooks,
            "sub_playbook": state.sub_playbooks[-1] if state.sub_playbooks else None,
            "matched_context": playbook,
        }
    passed = root.status == py_trees.common.Status.SUCCESS
    if not state.conclusion:
        state.conclusion = "playbook 执行完成" if passed else "playbook 执行完成，但仍有未通过的判定"
    if not state.next_action:
        state.next_action = "继续观察当前状态" if passed else "查看未通过的节点并继续处理"
    return {
        "playbook_id": playbook_id,
        "playbook_title": playbook_title,
        "executed": True,
        "steps": state.steps,
        "observations": state.observations,
        "passed": passed,
        "conclusion": state.conclusion,
        "next_action": state.next_action,
        "recent_tasks": state.recent_tasks,
        "sub_playbooks": state.sub_playbooks,
        "sub_playbook": state.sub_playbooks[-1] if state.sub_playbooks else None,
        "matched_context": playbook,
    }
