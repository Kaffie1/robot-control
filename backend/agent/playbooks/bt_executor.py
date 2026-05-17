from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import py_trees

from ...errors import ApiError
from ..rules import build_playbook_rule_context
from .executor import (
    PlaybookConfirmationRequired,
    execute_playbook,
    run_leaf_step,
    short_text,
    update_observations,
)
from .loader import find_playbook_by_id


def _normalize_status(value: str) -> py_trees.common.Status:
    normalized = str(value or "").strip().lower()
    if normalized == "success":
        return py_trees.common.Status.SUCCESS
    if normalized == "running":
        return py_trees.common.Status.RUNNING
    return py_trees.common.Status.FAILURE


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
    conclusion: str = ""
    next_action: str = ""
    completed_nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    pending_child_resumes: dict[str, dict[str, Any]] = field(default_factory=dict)
    active_node_path: str = ""
    active_node_message: str = ""
    status_reporter: Callable[[dict[str, Any], dict[str, Any] | None, str, str], None] | None = None

    def to_resume_state(self) -> dict[str, Any]:
        return {
            "steps": list(self.steps),
            "observations": dict(self.observations),
            "recent_tasks": list(self.recent_tasks),
            "sub_playbooks": list(self.sub_playbooks),
            "conclusion": self.conclusion,
            "next_action": self.next_action,
            "completed_nodes": dict(self.completed_nodes),
            "pending_child_resumes": dict(self.pending_child_resumes),
        }

    def to_execution_snapshot(self, *, executed: bool = False, passed: bool | None = None) -> dict[str, Any]:
        payload = {
            "playbook_id": str(self.playbook.get("id") or "").strip(),
            "playbook_title": str(self.playbook.get("title") or "").strip(),
            "executed": executed,
            "steps": list(self.steps),
            "observations": dict(self.observations),
            "conclusion": self.conclusion,
            "next_action": self.next_action,
            "recent_tasks": list(self.recent_tasks),
            "sub_playbooks": list(self.sub_playbooks),
            "sub_playbook": self.sub_playbooks[-1] if self.sub_playbooks else None,
            "matched_context": self.playbook,
        }
        if passed is not None:
            payload["passed"] = passed
        return payload

    def emit_status_update(self, *, pending_confirmation: dict[str, Any] | None = None, executed: bool = False, passed: bool | None = None) -> None:
        if not callable(self.status_reporter):
            return
        self.status_reporter(
            self.to_execution_snapshot(executed=executed, passed=passed),
            pending_confirmation,
            self.active_node_path,
            self.active_node_message,
        )

class ToolBehaviour(py_trees.behaviour.Behaviour):
    def __init__(self, node_spec: dict[str, Any], state: BehaviourTreeState, *, node_kind: str, node_path: str) -> None:
        super().__init__(name=str(node_spec.get("name") or node_spec.get("tool_name") or node_kind))
        self.node_spec = dict(node_spec)
        self.state = state
        self.node_kind = node_kind
        self.node_path = node_path

    def update(self) -> py_trees.common.Status:
        cached = self.state.completed_nodes.get(self.node_path)
        if isinstance(cached, dict):
            return py_trees.common.Status.SUCCESS if bool(cached.get("passed")) else py_trees.common.Status.FAILURE
        self.state.active_node_path = self.node_path
        self.state.active_node_message = str(self.node_spec.get("display_name") or self.node_spec.get("name") or self.node_spec.get("tool_name") or "").strip()
        self.state.emit_status_update()
        try:
            result = run_leaf_step(
                self.node_spec,
                self.state.tool_context,
                playbook_id=str(self.state.playbook.get("id") or "").strip(),
                playbook_title=str(self.state.playbook.get("title") or "").strip(),
                node_path=self.node_path,
            )
        except PlaybookConfirmationRequired as interrupt:
            self.state.active_node_message = str(interrupt.request.get("message") or self.state.active_node_message).strip()
            self.state.emit_status_update(pending_confirmation=interrupt.request)
            raise
        result["node_type"] = self.node_kind
        self.state.steps.append(result)
        update_observations(self.state.observations, result)
        self.state.completed_nodes[self.node_path] = dict(result)
        self.state.active_node_path = ""
        self.state.active_node_message = ""
        self.state.emit_status_update()
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
    def __init__(self, node_spec: dict[str, Any], state: BehaviourTreeState, *, node_path: str) -> None:
        super().__init__(name=str(node_spec.get("name") or "result"))
        self.node_spec = dict(node_spec)
        self.state = state
        self.node_path = node_path

    def update(self) -> py_trees.common.Status:
        cached = self.state.completed_nodes.get(self.node_path)
        if isinstance(cached, dict):
            return py_trees.common.Status.SUCCESS if bool(cached.get("passed")) else py_trees.common.Status.FAILURE
        self.state.active_node_path = self.node_path
        self.state.active_node_message = str(self.node_spec.get("message") or self.name).strip()
        self.state.emit_status_update()
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
            "node_path": self.node_path,
        }
        self.state.steps.append(step)
        self.state.completed_nodes[self.node_path] = dict(step)
        self.state.active_node_path = ""
        self.state.active_node_message = ""
        self.state.emit_status_update()
        if message:
            self.state.conclusion = message
            self.state.next_action = message
        return status


class CallPlaybookBehaviour(py_trees.behaviour.Behaviour):
    def __init__(self, node_spec: dict[str, Any], state: BehaviourTreeState, *, node_path: str) -> None:
        super().__init__(name=str(node_spec.get("name") or node_spec.get("playbook_id") or "call_playbook"))
        self.node_spec = dict(node_spec)
        self.state = state
        self.node_path = node_path

    def update(self) -> py_trees.common.Status:
        cached = self.state.completed_nodes.get(self.node_path)
        if isinstance(cached, dict):
            return py_trees.common.Status.SUCCESS if bool(cached.get("passed")) else py_trees.common.Status.FAILURE
        self.state.active_node_path = self.node_path
        self.state.active_node_message = str(self.node_spec.get("name") or self.node_spec.get("playbook_id") or "call_playbook").strip()
        self.state.emit_status_update()
        playbook_id = str(self.node_spec.get("playbook_id") or self.node_spec.get("target_playbook_id") or "").strip()
        if not playbook_id:
            raise ApiError(f"行为树节点缺少 playbook_id: {self.name}")
        child_playbook = find_playbook_by_id(playbook_id)
        if child_playbook is None:
            raise ApiError(f"未找到子 playbook: {playbook_id}")
        child_resume_state = self.state.pending_child_resumes.get(self.node_path)
        child_result = execute_playbook(
            child_playbook,
            self.state.tool_context,
            visited_ids=set(self.state.visited_ids),
            depth=self.state.depth + 1,
            max_depth=self.state.max_depth,
            resume_state=child_resume_state,
            status_reporter=None,
        )
        if isinstance(child_result.get("pending_confirmation"), dict):
            resume_state = child_result.get("resume_state")
            if isinstance(resume_state, dict):
                self.state.pending_child_resumes[self.node_path] = resume_state
            self.state.active_node_message = str(child_result.get("pending_confirmation", {}).get("message") or self.state.active_node_message).strip()
            self.state.emit_status_update(pending_confirmation=child_result.get("pending_confirmation"))
            raise PlaybookConfirmationRequired(child_result.get("pending_confirmation"))
        self.state.pending_child_resumes.pop(self.node_path, None)
        self.state.sub_playbooks.append(child_result)
        step = {
            "name": self.name,
            "tool_name": "call_playbook",
            "arguments": {"playbook_id": playbook_id},
            "output": short_text(child_result.get("conclusion") or child_result.get("next_action") or ""),
            "passed": bool(child_result.get("passed")),
            "node_type": "call_playbook",
            "sub_playbook": child_result,
            "called_playbook_id": playbook_id,
            "node_path": self.node_path,
        }
        self.state.steps.append(step)
        self.state.completed_nodes[self.node_path] = dict(step)
        self.state.active_node_path = ""
        self.state.active_node_message = ""
        self.state.emit_status_update()
        self.state.observations.update(
            {
                key: value
                for key, value in (child_result.get("observations") or {}).items()
                if key not in self.state.observations or value is not None
            }
        )
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


def _build_bt_node(node_spec: dict[str, Any], state: BehaviourTreeState, *, node_path: str) -> py_trees.behaviour.Behaviour:
    node_type = str(node_spec.get("type") or "").strip().lower()
    name = str(node_spec.get("name") or node_type or "node").strip()
    if node_type == "sequence":
        node = py_trees.composites.Sequence(
            name=name,
            memory=bool(node_spec.get("memory", False)),
        )
        children = node_spec.get("children") if isinstance(node_spec.get("children"), list) else []
        for index, child in enumerate(children):
            if isinstance(child, dict):
                node.add_child(_build_bt_node(child, state, node_path=f"{node_path}.children[{index}]"))
        return node
    if node_type == "selector":
        node = py_trees.composites.Selector(
            name=name,
            memory=bool(node_spec.get("memory", False)),
        )
        children = node_spec.get("children") if isinstance(node_spec.get("children"), list) else []
        for index, child in enumerate(children):
            if isinstance(child, dict):
                node.add_child(_build_bt_node(child, state, node_path=f"{node_path}.children[{index}]"))
        return node
    if node_type == "condition":
        return ToolBehaviour(node_spec, state, node_kind="condition", node_path=node_path)
    if node_type == "action":
        return ToolBehaviour(node_spec, state, node_kind="action", node_path=node_path)
    if node_type == "call_playbook":
        return CallPlaybookBehaviour(node_spec, state, node_path=node_path)
    if node_type == "result":
        return ResultBehaviour(node_spec, state, node_path=node_path)
    raise ApiError(f"不支持的行为树节点类型: {node_type}")


def execute_tree_playbook(
    playbook: dict[str, Any],
    tool_context: dict[str, Any] | None,
    *,
    visited_ids: set[str] | None = None,
    depth: int = 0,
    max_depth: int = 4,
    resume_state: dict[str, Any] | None = None,
    status_reporter: Callable[[dict[str, Any], dict[str, Any] | None, str, str], None] | None = None,
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
        steps=list(resume_state.get("steps") or []) if isinstance(resume_state, dict) else [],
        observations=dict(resume_state.get("observations") or {}) if isinstance(resume_state, dict) else {},
        recent_tasks=list(resume_state.get("recent_tasks") or []) if isinstance(resume_state, dict) else [],
        sub_playbooks=list(resume_state.get("sub_playbooks") or []) if isinstance(resume_state, dict) else [],
        conclusion=str(resume_state.get("conclusion") or "") if isinstance(resume_state, dict) else "",
        next_action=str(resume_state.get("next_action") or "") if isinstance(resume_state, dict) else "",
        completed_nodes=dict(resume_state.get("completed_nodes") or {}) if isinstance(resume_state, dict) else {},
        pending_child_resumes=dict(resume_state.get("pending_child_resumes") or {}) if isinstance(resume_state, dict) else {},
        status_reporter=status_reporter,
    )
    root_spec = playbook.get("root")
    if not isinstance(root_spec, dict):
        return {"playbook_id": playbook_id, "playbook_title": playbook_title, "executed": False, "reason": "行为树 playbook 缺少 root", "matched_context": playbook}
    root = _build_bt_node(root_spec, state, node_path="root")
    tree = py_trees.trees.BehaviourTree(root)
    state.emit_status_update()
    try:
        tree.tick()
    except PlaybookConfirmationRequired as interrupt:
        state.emit_status_update(pending_confirmation=interrupt.request)
        return {
            "playbook_id": playbook_id,
            "playbook_title": playbook_title,
            "executed": False,
            "interrupted": True,
            "pending_confirmation": interrupt.request,
            "resume_state": state.to_resume_state(),
            "steps": state.steps,
            "observations": state.observations,
            "conclusion": state.conclusion,
            "next_action": state.next_action,
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
    state.emit_status_update(executed=True, passed=passed)
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
