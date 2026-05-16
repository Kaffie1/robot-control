from __future__ import annotations

import ast
import json
import re
import time
from typing import Any

from ...models import ApiError
from ..common import (
    append_fault_trace,
    build_confirmation_options,
    build_confirmation_payload,
    expand_context_references,
    get_playbook_input,
    logger,
    store_pending_confirmation,
    store_playbook_input,
)
from ..rules import build_playbook_rule_context, evaluate_step_assertion
from ..tools import agent_tool_registry
from .loader import find_playbook_by_id
from .schema import validate_playbook_spec


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


def _extract_value_by_path(payload: Any, field_path: str) -> Any:
    normalized_path = str(field_path or "").strip()
    if not normalized_path or normalized_path == ".":
        return payload
    current = payload
    for part in normalized_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current.get(part)
            continue
        return None
    return current


def _parse_string_list_options(value: Any, *, list_key: str = "") -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        if list_key:
            candidate = value.get(list_key)
            if isinstance(candidate, list):
                return [str(item).strip() for item in candidate if str(item).strip()]
        for candidate in value.values():
            if isinstance(candidate, list):
                return [str(item).strip() for item in candidate if str(item).strip()]
        return []
    text = str(value or "").strip()
    if not text:
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except Exception:
            continue
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
        if isinstance(parsed, dict):
            if list_key and isinstance(parsed.get(list_key), list):
                return [str(item).strip() for item in parsed.get(list_key) if str(item).strip()]
    lines = text.splitlines()
    options: list[str] = []
    inside_target_section = not bool(list_key)
    list_key_pattern = re.compile(rf"^{re.escape(list_key)}\s*:\s*$") if list_key else None
    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            continue
        if list_key_pattern and list_key_pattern.match(stripped):
            inside_target_section = True
            continue
        if inside_target_section:
            bullet_match = re.match(r"^(?:-\s*|\d+[.)]\s*)(.+)$", stripped)
            if bullet_match:
                option = bullet_match.group(1).strip()
                if option:
                    options.append(option)
                continue
            if list_key and ":" in stripped:
                break
    if not options and not list_key:
        return [line.strip() for line in lines if line.strip()]
    return options


def _resolve_confirmation_spec(step: dict[str, Any]) -> dict[str, Any]:
    confirmation = step.get("confirmation") if isinstance(step.get("confirmation"), dict) else {}
    if confirmation:
        return confirmation
    if not bool(step.get("require_confirmation")):
        return {}
    step_name = str(step.get("name") or step.get("tool_name") or "step").strip().replace(" ", "_")
    return {
        "mode": "approve",
        "when": "before",
        "message": f"即将执行步骤 {step_name}，是否继续？",
        "output": {
            "store_as": f"{step_name}_approved",
            "type": "boolean",
        },
    }


def _build_confirmation_options_from_tool_result(
    confirmation: dict[str, Any],
    tool_result: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    input_spec = confirmation.get("input") if isinstance(confirmation.get("input"), dict) else {}
    static_options = input_spec.get("options")
    if isinstance(static_options, list) and static_options:
        return build_confirmation_options(static_options)
    options_source = input_spec.get("options_source") if isinstance(input_spec.get("options_source"), dict) else {}
    if not options_source:
        return []
    source_field = str(options_source.get("field") or "").strip()
    parser_name = str(options_source.get("parser") or "string_list").strip().lower()
    list_key = str(options_source.get("list_key") or "").strip()
    source_value = _extract_value_by_path(tool_result or {}, source_field)
    if parser_name == "string_list":
        return build_confirmation_options(_parse_string_list_options(source_value, list_key=list_key))
    return []


def _build_pending_confirmation_result(
    *,
    step_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    result_output: Any,
    confirmation: dict[str, Any],
    options: list[dict[str, Any]],
    playbook_id: str,
    playbook_title: str,
) -> dict[str, Any]:
    payload = build_confirmation_payload(confirmation, options=options)
    return {
        "name": step_name or tool_name,
        "tool_name": tool_name,
        "arguments": arguments,
        "output": short_text(result_output),
        "passed": False,
        "pending_confirmation": True,
        "confirmation": payload,
        "playbook_id": playbook_id,
        "playbook_title": playbook_title,
    }


def run_script_step(step: dict[str, Any], tool_context: dict[str, Any] | None) -> dict[str, Any]:
    name = str(step.get("name") or step.get("tool_name") or "").strip()
    tool_name = str(step.get("tool_name") or "").strip()
    raw_arguments = step.get("arguments") if isinstance(step.get("arguments"), dict) else {}
    arguments = expand_context_references(raw_arguments, tool_context)
    assert_ref = str(step.get("assert_ref") or step.get("expect") or "").strip()
    confirmation = _resolve_confirmation_spec(step)
    confirmation_mode = str(confirmation.get("mode") or "").strip().lower()
    confirmation_when = str(confirmation.get("when") or "").strip().lower() or "before"
    confirmation_output = confirmation.get("output") if isinstance(confirmation.get("output"), dict) else {}
    confirmation_store_as = str(confirmation_output.get("store_as") or "").strip()
    existing_confirmation_value = get_playbook_input(tool_context, confirmation_store_as) if confirmation_store_as else None
    if confirmation and confirmation_when == "before" and existing_confirmation_value is None:
        payload = build_confirmation_payload(confirmation)
        step_result = {
            "name": name or tool_name,
            "tool_name": tool_name,
            "arguments": arguments,
            "output": "",
            "expect": assert_ref,
            "assert_ref": assert_ref,
            "assert_spec": None,
            "wait_seconds": 0,
            "passed": False,
            "require_confirmation": True,
            "pending_confirmation": True,
            "confirmation": payload,
            "failure_action": "",
            "failure_message": "",
            "failure_playbook_id": "",
        }
        append_fault_trace("playbook_step_result", step_result)
        return step_result
    if confirmation and confirmation_when == "before" and confirmation_mode == "approve" and existing_confirmation_value is False:
        step_result = {
            "name": name or tool_name,
            "tool_name": tool_name,
            "arguments": arguments,
            "output": "",
            "expect": assert_ref,
            "assert_ref": assert_ref,
            "assert_spec": None,
            "wait_seconds": 0,
            "passed": False,
            "require_confirmation": True,
            "failure_action": "stop",
            "failure_message": "人工未确认，当前步骤未执行",
            "failure_playbook_id": "",
        }
        append_fault_trace("playbook_step_result", step_result)
        return step_result
    wait_seconds = max(int(step.get("wait_seconds") or 0), 0)
    if wait_seconds:
        logger.info("Playbook 步骤等待 | seconds=%d | step=%s | tool=%s", wait_seconds, name, tool_name)
        time.sleep(wait_seconds)
    result = tool_call(tool_name, arguments, tool_context)
    if confirmation and confirmation_when == "after" and existing_confirmation_value is None:
        input_spec = confirmation.get("input") if isinstance(confirmation.get("input"), dict) else {}
        options = _build_confirmation_options_from_tool_result(confirmation, result.get("result"))
        if options and bool(input_spec.get("auto_select_if_single")) and len(options) == 1 and confirmation_store_as:
            selected_option = options[0]
            output_type = str(confirmation_output.get("type") or "").strip().lower()
            if output_type == "selected_option_index":
                auto_value = selected_option.get("index")
            elif output_type == "selected_option_label":
                auto_value = selected_option.get("label")
            else:
                auto_value = selected_option.get("value")
            store_playbook_input(tool_context, confirmation_store_as, auto_value)
        else:
            step_result = _build_pending_confirmation_result(
                step_name=name,
                tool_name=tool_name,
                arguments=arguments,
                result_output=result.get("result"),
                confirmation=confirmation,
                options=options,
                playbook_id=str(tool_context.get("playbook_id") or "") if isinstance(tool_context, dict) else "",
                playbook_title=str(tool_context.get("playbook_title") or "") if isinstance(tool_context, dict) else "",
            )
            append_fault_trace("playbook_step_result", step_result)
            return step_result
    assertion = evaluate_step_assertion(step, result.get("result", {}), tool_context=tool_context)
    passed = bool(assertion.get("passed"))
    failure = step.get("on_fail") if isinstance(step.get("on_fail"), dict) else {}
    require_confirmation = bool(step.get("require_confirmation") or confirmation)
    step_result = {
        "name": name or tool_name,
        "tool_name": tool_name,
        "arguments": arguments,
        "output": short_text(result.get("result")),
        "expect": assertion.get("rule_name") or assert_ref,
        "assert_ref": assertion.get("rule_name") or assert_ref,
        "assert_spec": assertion.get("rule_spec"),
        "wait_seconds": wait_seconds,
        "passed": passed,
        "require_confirmation": require_confirmation,
        "confirmation": build_confirmation_payload(confirmation) if confirmation else None,
        "failure_action": str(failure.get("action") or "").strip(),
        "failure_message": str(failure.get("message") or "").strip(),
        "failure_playbook_id": str(failure.get("playbook_id") or failure.get("target_playbook_id") or "").strip(),
    }
    append_fault_trace("playbook_step_result", step_result)
    return step_result


def step_passed(step: dict[str, Any]) -> bool:
    return bool(step.get("passed"))


def summarize_step_output(step: dict[str, Any]) -> str:
    if not isinstance(step, dict):
        return ""
    output = step.get("output")
    if output is None:
        output = step.get("result")
    return short_text(output)


def update_observations(observations: dict[str, bool | None], step: dict[str, Any]) -> None:
    key = str(step.get("assert_ref") or step.get("expect") or step.get("name") or "").strip()
    if not key:
        return
    observations[key] = step_passed(step)


def merge_observations(
    base_observations: dict[str, bool | None],
    new_observations: dict[str, Any] | None,
) -> dict[str, bool | None]:
    merged = dict(base_observations)
    if not isinstance(new_observations, dict):
        return merged
    for key, value in new_observations.items():
        if key not in merged:
            continue
        if value is None:
            continue
        merged[key] = bool(value)
    return merged


def summarize_recent_tasks(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        items = result
    elif isinstance(result, dict):
        items = result.get("items")
    else:
        items = None
    if not isinstance(items, list):
        return []
    summary: list[dict[str, Any]] = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        summary.append(
            {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "type": item.get("type", ""),
                "status": item.get("status", ""),
                "error": short_text(item.get("error", ""), limit=160),
            }
        )
    return summary


def run_success_criteria_item(item: dict[str, Any], tool_context: dict[str, Any] | None) -> dict[str, Any]:
    name = str(item.get("name") or item.get("tool_name") or "").strip()
    tool_name = str(item.get("tool_name") or "").strip()
    arguments = item.get("arguments") if isinstance(item.get("arguments"), dict) else {}
    assert_ref = str(item.get("assert_ref") or item.get("expect") or "").strip()
    wait_seconds = max(int(item.get("wait_seconds") or 0), 0)
    confirm_times = max(int(item.get("confirm_times") or 1), 1)
    on_fail = item.get("on_fail") if isinstance(item.get("on_fail"), dict) else {}
    attempts: list[dict[str, Any]] = []
    all_passed = True
    if wait_seconds:
        logger.info("Success criteria 等待 | seconds=%d | tool=%s", wait_seconds, tool_name)
        time.sleep(wait_seconds)
    for _ in range(confirm_times):
        attempt = run_script_step(
            {
                "name": name,
                "tool_name": tool_name,
                "arguments": arguments,
                "expect": assert_ref,
                "assert_ref": assert_ref,
                "confirmation": item.get("confirmation"),
                "require_confirmation": item.get("require_confirmation"),
                "on_fail": on_fail,
            },
            tool_context,
        )
        attempts.append(attempt)
        if bool(attempt.get("pending_confirmation")) or not step_passed(attempt):
            all_passed = False
            break
    criterion_result = {
        "name": name or tool_name,
        "tool_name": tool_name,
        "arguments": arguments,
        "expect": assert_ref,
        "assert_ref": assert_ref,
        "assert_spec": attempts[-1].get("assert_spec") if attempts else None,
        "wait_seconds": wait_seconds,
        "confirm_times": confirm_times,
        "passed": all_passed,
        "require_confirmation": bool(item.get("require_confirmation")),
        "attempts": attempts,
        "pending_confirmation": bool(attempts[-1].get("pending_confirmation")) if attempts else False,
        "confirmation": attempts[-1].get("confirmation") if attempts else None,
        "failure_message": attempts[-1].get("failure_message", "") if attempts else "",
        "failure_action": attempts[-1].get("failure_action", "") if attempts else "",
    }
    append_fault_trace("playbook_success_criteria_result", criterion_result)
    return criterion_result


def execute_playbook(
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
    validate_playbook_spec(playbook)
    playbook_context = build_playbook_rule_context(
        {
            **dict(tool_context or {}),
            "playbook_id": playbook_id,
            "playbook_title": playbook_title,
            "playbook_source_path": playbook_source_path,
            "playbook_rules_source_path": playbook_rules_source_path,
        }
    )
    normalized_visited_ids = set(visited_ids or set())
    logger.info("Playbook 执行开始 | id=%s | title=%s | depth=%d", playbook_id, playbook_title, depth)
    append_fault_trace(
        "playbook_execute_start",
        {
            "playbook_id": playbook_id,
            "playbook_title": playbook_title,
            "depth": depth,
            "playbook": playbook,
        },
    )

    if not playbook_id:
        return {"playbook_id": "", "playbook_title": playbook_title, "executed": False, "reason": "playbook 缺少 id", "matched_context": playbook}
    if depth > max_depth:
        return {"playbook_id": playbook_id, "playbook_title": playbook_title, "executed": False, "reason": "playbook 嵌套层级超过上限", "matched_context": playbook}
    if playbook_id in normalized_visited_ids:
        return {"playbook_id": playbook_id, "playbook_title": playbook_title, "executed": False, "reason": "检测到 playbook 循环引用", "matched_context": playbook}
    normalized_visited_ids.add(playbook_id)

    script_steps = playbook.get("script")
    if not isinstance(script_steps, list) or not script_steps:
        return {"playbook_id": playbook_id, "playbook_title": playbook_title, "executed": False, "reason": "playbook 中没有可执行脚本", "matched_context": playbook}

    steps: list[dict[str, Any]] = []
    observations: dict[str, bool | None] = {}
    recent_tasks: list[dict[str, Any]] = []

    for raw_step in script_steps:
        if not isinstance(raw_step, dict):
            continue
        step = run_script_step(raw_step, playbook_context)
        steps.append(step)
        if bool(step.get("pending_confirmation")):
            confirmation_payload = step.get("confirmation") if isinstance(step.get("confirmation"), dict) else {}
            pending_payload = {
                **confirmation_payload,
                "playbook_id": playbook_id,
                "playbook_title": playbook_title,
                "step_name": str(step.get("name") or ""),
                "tool_name": str(step.get("tool_name") or ""),
                "confirmation": raw_step.get("confirmation") if isinstance(raw_step.get("confirmation"), dict) else _resolve_confirmation_spec(raw_step),
                "store_as": str((((raw_step.get("confirmation") or {}) if isinstance(raw_step.get("confirmation"), dict) else {}).get("output") or {}).get("store_as") or ""),
            }
            store_pending_confirmation(playbook_context, pending_payload)
            return {
                "playbook_id": playbook_id,
                "playbook_title": playbook_title,
                "executed": True,
                "steps": steps,
                "observations": observations,
                "pending_confirmation": True,
                "confirmation": confirmation_payload,
                "conclusion": str(confirmation_payload.get("message") or "等待人工确认"),
                "next_action": "请根据提示补充输入后继续",
                "recent_tasks": recent_tasks,
                "matched_context": playbook,
            }
        update_observations(observations, step)
        if step_passed(step):
            continue

        failure_action = str(step.get("failure_action") or "").strip()
        failure_message = str(step.get("failure_message") or "").strip()
        failure_playbook_id = str(step.get("failure_playbook_id") or "").strip()

        if failure_action == "call_playbook":
            if not failure_playbook_id:
                return {
                    "playbook_id": playbook_id,
                    "playbook_title": playbook_title,
                    "executed": True,
                    "steps": steps,
                    "observations": observations,
                    "conclusion": failure_message or "子 playbook 缺少目标 id",
                    "next_action": "补充 on_fail.playbook_id 后重试",
                    "recent_tasks": recent_tasks,
                    "matched_context": playbook,
                }
            child_playbook = find_playbook_by_id(failure_playbook_id)
            if not child_playbook:
                return {
                    "playbook_id": playbook_id,
                    "playbook_title": playbook_title,
                    "executed": True,
                    "steps": steps,
                    "observations": observations,
                    "conclusion": failure_message or f"未找到子 playbook: {failure_playbook_id}",
                    "next_action": f"创建或修正 {failure_playbook_id} 对应的 playbook",
                    "recent_tasks": recent_tasks,
                    "matched_context": playbook,
                }
            child_result = execute_playbook(
                child_playbook,
                playbook_context,
                visited_ids=normalized_visited_ids,
                depth=depth + 1,
                max_depth=max_depth,
            )
            merged_observations = merge_observations(observations, child_result.get("observations"))
            return {
                "playbook_id": playbook_id,
                "playbook_title": playbook_title,
                "executed": True,
                "steps": steps,
                "observations": merged_observations,
                "conclusion": child_result.get("conclusion") or failure_message or f"已转入子 playbook: {failure_playbook_id}",
                "next_action": child_result.get("next_action") or failure_message or f"请查看子 playbook: {failure_playbook_id}",
                "sub_playbook": child_result,
                "recent_tasks": recent_tasks,
                "matched_context": playbook,
            }

        next_action = failure_message or "请按升级说明继续处理"
        if failure_action == "stop":
            next_action = failure_message or "停止脚本并转人工"
        elif failure_action == "escalate":
            next_action = failure_message or "转人工或算法同事继续分析"
        return {
            "playbook_id": playbook_id,
            "playbook_title": playbook_title,
            "executed": True,
            "steps": steps,
            "observations": observations,
            "conclusion": failure_message or "脚本在当前步骤失败",
            "next_action": next_action,
            "recent_tasks": recent_tasks,
            "matched_context": playbook,
        }

    success_criteria = playbook.get("success_criteria")
    success_criteria_results: list[dict[str, Any]] = []
    if isinstance(success_criteria, list) and success_criteria:
        for raw_item in success_criteria:
            if not isinstance(raw_item, dict):
                continue
            criterion = run_success_criteria_item(raw_item, playbook_context)
            success_criteria_results.append(criterion)
            if bool(criterion.get("pending_confirmation")):
                confirmation_payload = criterion.get("confirmation") if isinstance(criterion.get("confirmation"), dict) else {}
                store_pending_confirmation(
                    playbook_context,
                    {
                        **confirmation_payload,
                        "playbook_id": playbook_id,
                        "playbook_title": playbook_title,
                        "step_name": str(criterion.get("name") or ""),
                        "tool_name": str(criterion.get("tool_name") or ""),
                        "confirmation": raw_item.get("confirmation") if isinstance(raw_item.get("confirmation"), dict) else _resolve_confirmation_spec(raw_item),
                        "store_as": str((((raw_item.get("confirmation") or {}) if isinstance(raw_item.get("confirmation"), dict) else {}).get("output") or {}).get("store_as") or ""),
                    },
                )
                return {
                    "playbook_id": playbook_id,
                    "playbook_title": playbook_title,
                    "executed": True,
                    "steps": [{"name": str(item.get("name") or ""), "arguments": item.get("arguments") or {}, "output": summarize_step_output(item)} for item in steps],
                    "observations": observations,
                    "success_criteria_results": success_criteria_results,
                    "pending_confirmation": True,
                    "confirmation": confirmation_payload,
                    "conclusion": str(confirmation_payload.get("message") or "等待人工确认"),
                    "next_action": "请根据提示补充输入后继续",
                    "recent_tasks": recent_tasks,
                    "matched_context": playbook,
                }
            if step_passed(criterion):
                continue
            failure_message = str(criterion.get("failure_message") or "").strip()
            next_action = failure_message or "问题还没有真正解决，继续排查或转人工"
            failure_action = str(criterion.get("failure_action") or "").strip()
            if failure_action == "stop":
                next_action = failure_message or "停止自动判定并转人工"
            elif failure_action == "escalate":
                next_action = failure_message or "转算法同事继续分析"
            elif failure_action == "call_playbook":
                raise ApiError("success_criteria 不支持 call_playbook")
            return {
                "playbook_id": playbook_id,
                "playbook_title": playbook_title,
                "executed": True,
                "steps": [{"name": str(item.get("name") or ""), "arguments": item.get("arguments") or {}, "output": summarize_step_output(item)} for item in steps],
                "observations": observations,
                "success_criteria_results": success_criteria_results,
                "conclusion": failure_message or "脚本步骤已完成，但整体成功条件未满足",
                "next_action": next_action,
                "recent_tasks": recent_tasks,
                "matched_context": playbook,
            }

    final_passed = all(step_passed(item) for item in steps) if steps else False
    if success_criteria_results:
        final_passed = final_passed and all(step_passed(item) for item in success_criteria_results)
    return {
        "playbook_id": playbook_id,
        "playbook_title": playbook_title,
        "executed": True,
        "steps": [{"name": str(item.get("name") or ""), "arguments": item.get("arguments") or {}, "output": summarize_step_output(item)} for item in steps],
        "observations": observations,
        "success_criteria_results": success_criteria_results,
        "passed": final_passed,
        "conclusion": "playbook 执行完成" if final_passed else "playbook 执行完成，但仍有未通过的判定",
        "next_action": "继续观察当前状态" if final_passed else "查看未通过的步骤并继续处理",
        "recent_tasks": summarize_recent_tasks(recent_tasks),
        "matched_context": playbook,
    }
