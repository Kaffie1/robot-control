from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from ..common import (
    append_fault_trace,
    expand_context_references,
    get_confirmation_request,
    logger,
)
from ..rules import evaluate_step_assertion
from ..tools import agent_tool_registry
from .schema import validate_playbook_spec


class PlaybookConfirmationRequired(Exception):
    def __init__(self, request: dict[str, Any]):
        super().__init__(str(request.get("message") or "需要人工确认"))
        self.request = request


def short_text(value: Any, *, limit: int = 320) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…"


def tool_call(tool_name: str, arguments: dict[str, Any], tool_context: dict[str, Any] | None) -> dict[str, Any]:
    logger.info("Playbook 工具调用开始 | tool=%s", tool_name)
    append_fault_trace(
        "playbook_tool_call_start",
        {
            "tool_name": tool_name,
            "arguments": arguments,
        },
    )
    result = agent_tool_registry.call_tool(tool_name, arguments, tool_context)
    append_fault_trace(
        "playbook_tool_call_end",
        {
            "tool_name": tool_name,
            "arguments": arguments,
            "result": result,
        },
    )
    return {
        "name": tool_name,
        "arguments": arguments,
        "result": result,
    }


def run_script_step(step: dict[str, Any], tool_context: dict[str, Any] | None) -> dict[str, Any]:
    name = str(step.get("name") or step.get("tool_name") or "").strip()
    tool_name = str(step.get("tool_name") or "").strip()
    raw_arguments = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
    arguments = expand_context_references(raw_arguments, tool_context)
    assert_ref = str(step.get("assert_ref") or step.get("expect") or "").strip()
    wait_seconds = max(int(step.get("wait_seconds") or 0), 0)
    if wait_seconds:
        logger.info("Playbook 步骤等待 | seconds=%d | step=%s | tool=%s", wait_seconds, name, tool_name)
        time.sleep(wait_seconds)
    result = tool_call(tool_name, arguments, tool_context)
    raw_result = result.get("result", {})
    assertion_payload = {
        "result": raw_result,
        "arguments": arguments,
        "tool_name": tool_name,
    }
    assertion = evaluate_step_assertion(step, assertion_payload, tool_context=tool_context)
    passed = bool(assertion.get("passed"))
    step_result = {
        "name": name or tool_name,
        "tool_name": tool_name,
        "arguments": arguments,
        "output": short_text(raw_result),
        "expect": assertion.get("rule_name") or assert_ref,
        "assert_ref": assertion.get("rule_name") or assert_ref,
        "assert_spec": assertion.get("rule_spec"),
        "wait_seconds": wait_seconds,
        "passed": passed,
        "failure_message": str(step.get("failure_message") or "").strip(),
    }
    append_fault_trace("playbook_step_result", step_result)
    return step_result


def step_passed(step: dict[str, Any]) -> bool:
    return bool(step.get("passed"))


def update_observations(observations: dict[str, bool | None], step: dict[str, Any]) -> None:
    key = str(step.get("assert_ref") or step.get("expect") or step.get("name") or "").strip()
    if not key:
        return
    observations[key] = step_passed(step)


def run_leaf_step(
    node_spec: dict[str, Any],
    tool_context: dict[str, Any] | None,
    *,
    playbook_id: str,
    playbook_title: str,
    node_path: str,
) -> dict[str, Any]:
    wait_seconds = max(int(node_spec.get("wait_seconds") or 0), 0)
    confirm_times = max(int(node_spec.get("confirm_times") or 1), 1)
    spec_without_control = dict(node_spec)
    spec_without_control.pop("wait_seconds", None)
    spec_without_control.pop("confirm_times", None)
    request = get_confirmation_request(
        node_spec,
        tool_context,
        playbook_id=playbook_id,
        playbook_title=playbook_title,
        node_path=node_path,
    )
    if request is not None:
        raise PlaybookConfirmationRequired(request)
    attempts: list[dict[str, Any]] = []
    if wait_seconds:
        time.sleep(wait_seconds)
    passed = True
    for _ in range(confirm_times):
        attempt = run_script_step(spec_without_control, tool_context)
        attempts.append(attempt)
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
        "assert_ref": str(node_spec.get("assert_ref") or node_spec.get("expect") or "").strip(),
        "node_path": node_path,
        "wait_seconds": wait_seconds,
        "confirm_times": confirm_times,
        "attempts": attempts,
    }
    if len(attempts) == 1:
        result.update(last_attempt)
        result["wait_seconds"] = wait_seconds
        result["confirm_times"] = confirm_times
        result["attempts"] = attempts
    return result


def execute_playbook(
    playbook: dict[str, Any],
    tool_context: dict[str, Any] | None,
    *,
    visited_ids: set[str] | None = None,
    depth: int = 0,
    max_depth: int = 4,
    resume_state: dict[str, Any] | None = None,
    status_reporter: Callable[[dict[str, Any], dict[str, Any] | None, str, str], None] | None = None,
) -> dict[str, Any]:
    from .bt_executor import execute_tree_playbook

    validate_playbook_spec(playbook)
    return execute_tree_playbook(
        playbook,
        tool_context,
        visited_ids=visited_ids,
        depth=depth,
        max_depth=max_depth,
        resume_state=resume_state,
        status_reporter=status_reporter,
    )
