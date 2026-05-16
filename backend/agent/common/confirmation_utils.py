from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .text_utils import normalize_message_content

MAX_CHAT_HISTORY_TURNS = 3


def get_session(tool_context: dict[str, Any] | None) -> dict[str, Any] | None:
    session = (tool_context or {}).get("session")
    return session if isinstance(session, dict) else None


def get_chat_state(tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = get_session(tool_context)
    if session is None:
        return {}
    chat_state = session.get("chat_state")
    if not isinstance(chat_state, dict):
        chat_state = {}
        session["chat_state"] = chat_state
    return chat_state


def _get_chat_history_path(tool_context: dict[str, Any] | None) -> Path | None:
    session = get_session(tool_context)
    if session is None:
        return None
    raw_path = str(session.get("chat_history_path") or "").strip()
    if not raw_path:
        return None
    return Path(raw_path)


def _read_chat_history_file(tool_context: dict[str, Any] | None) -> list[dict[str, str]]:
    path = _get_chat_history_path(tool_context)
    if path is None:
        return []
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw or "[]")
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    normalized_history: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        role = normalize_message_content(item.get("role") or "").lower()
        content = normalize_message_content(item.get("content") or "")
        if role not in {"user", "assistant"} or not content:
            continue
        normalized_history.append({"role": role, "content": content})
    return normalized_history


def _write_chat_history_file(tool_context: dict[str, Any] | None, history: list[dict[str, str]]) -> None:
    path = _get_chat_history_path(tool_context)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized_history: list[dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = normalize_message_content(item.get("role") or "").lower()
        content = normalize_message_content(item.get("content") or "")
        if role not in {"user", "assistant"} or not content:
            continue
        normalized_history.append({"role": role, "content": content})
    try:
        path.write_text(json.dumps(normalized_history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return


def delete_chat_history_file(tool_context: dict[str, Any] | None) -> None:
    path = _get_chat_history_path(tool_context)
    if path is None:
        return
    try:
        if path.exists():
            path.unlink()
    except OSError:
        return


def get_chat_history(tool_context: dict[str, Any] | None) -> list[dict[str, str]]:
    return _read_chat_history_file(tool_context)


def list_recent_chat_history(
    tool_context: dict[str, Any] | None,
    max_turns: int = MAX_CHAT_HISTORY_TURNS,
) -> list[dict[str, str]]:
    max_messages = max(int(max_turns or 0), 0) * 2
    history = get_chat_history(tool_context)
    if max_messages <= 0:
        return []
    return history[-max_messages:]


def append_chat_history_turn(
    tool_context: dict[str, Any] | None,
    *,
    user_message: str,
    assistant_message: str,
    max_turns: int = MAX_CHAT_HISTORY_TURNS,
) -> None:
    normalized_user_message = normalize_message_content(user_message)
    normalized_assistant_message = normalize_message_content(assistant_message)
    if not normalized_user_message and not normalized_assistant_message:
        return
    history = _read_chat_history_file(tool_context)
    if normalized_user_message:
        history.append({"role": "user", "content": normalized_user_message})
    if normalized_assistant_message:
        history.append({"role": "assistant", "content": normalized_assistant_message})
    max_messages = max(int(max_turns or 0), 0) * 2
    if max_messages > 0 and len(history) > max_messages:
        del history[:-max_messages]
    _write_chat_history_file(tool_context, history)


def clear_chat_history(tool_context: dict[str, Any] | None) -> None:
    _write_chat_history_file(tool_context, [])


def reset_chat_state(tool_context: dict[str, Any] | None) -> None:
    chat_state = get_chat_state(tool_context)
    if chat_state is not None:
        chat_state.clear()
    clear_chat_history(tool_context)


def get_playbook_inputs(tool_context: dict[str, Any] | None) -> dict[str, Any]:
    chat_state = get_chat_state(tool_context)
    playbook_inputs = chat_state.get("playbook_inputs")
    if not isinstance(playbook_inputs, dict):
        playbook_inputs = {}
        if chat_state:
            chat_state["playbook_inputs"] = playbook_inputs
    return playbook_inputs


def store_playbook_input(tool_context: dict[str, Any] | None, key: str, value: Any) -> None:
    normalized_key = normalize_message_content(key)
    if not normalized_key:
        return
    playbook_inputs = get_playbook_inputs(tool_context)
    if playbook_inputs is not None:
        playbook_inputs[normalized_key] = value
    if isinstance(tool_context, dict):
        tool_context[normalized_key] = value


def get_playbook_input(tool_context: dict[str, Any] | None, key: str) -> Any:
    normalized_key = normalize_message_content(key)
    if not normalized_key:
        return None
    if isinstance(tool_context, dict) and normalized_key in tool_context:
        return tool_context.get(normalized_key)
    return get_playbook_inputs(tool_context).get(normalized_key)


def get_context_value(tool_context: dict[str, Any] | None, key: str) -> Any:
    normalized_key = normalize_message_content(key)
    if not normalized_key:
        return None
    if normalized_key == "session":
        return get_session(tool_context)
    return get_playbook_input(tool_context, normalized_key)


_CONTEXT_REF_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")


def expand_context_references(value: Any, tool_context: dict[str, Any] | None) -> Any:
    if isinstance(value, dict):
        if "from_context" in value and len(value) == 1:
            return get_context_value(tool_context, str(value.get("from_context") or ""))
        return {key: expand_context_references(item, tool_context) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_context_references(item, tool_context) for item in value]
    if not isinstance(value, str):
        return value
    matches = list(_CONTEXT_REF_PATTERN.finditer(value))
    if not matches:
        return value
    if len(matches) == 1 and matches[0].span() == (0, len(value)):
        return get_context_value(tool_context, matches[0].group(1))

    def replace_match(match: re.Match[str]) -> str:
        resolved = get_context_value(tool_context, match.group(1))
        return "" if resolved is None else str(resolved)

    return _CONTEXT_REF_PATTERN.sub(replace_match, value)


def clear_playbook_input(tool_context: dict[str, Any] | None, key: str) -> None:
    normalized_key = normalize_message_content(key)
    if not normalized_key:
        return
    playbook_inputs = get_playbook_inputs(tool_context)
    if playbook_inputs:
        playbook_inputs.pop(normalized_key, None)
    if isinstance(tool_context, dict):
        tool_context.pop(normalized_key, None)


def build_confirmation_options(options: list[Any] | None) -> list[dict[str, Any]]:
    normalized_options: list[dict[str, Any]] = []
    for index, raw_option in enumerate(options or [], start=1):
        if isinstance(raw_option, dict):
            label = normalize_message_content(
                raw_option.get("display_label")
                or raw_option.get("label")
                or raw_option.get("text")
                or raw_option.get("value")
                or raw_option.get("name")
            )
            value = raw_option.get("value")
            if value is None:
                value = label
        else:
            label = normalize_message_content(raw_option)
            value = label
        if not label:
            continue
        normalized_options.append(
            {
                "index": index,
                "label": label,
                "display_label": f"{index}. {label}",
                "value": value,
            }
        )
    return normalized_options


def build_confirmation_payload(
    confirmation: dict[str, Any],
    *,
    options: list[Any] | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    normalized_options = build_confirmation_options(options)
    input_spec = confirmation.get("input") if isinstance(confirmation.get("input"), dict) else {}
    output_spec = confirmation.get("output") if isinstance(confirmation.get("output"), dict) else {}
    resolved_message = normalize_message_content(message or confirmation.get("message") or "")
    if not resolved_message:
        mode = normalize_message_content(confirmation.get("mode") or "").lower()
        if mode == "approve":
            resolved_message = "请确认是否继续"
        elif mode == "select":
            resolved_message = "请选择一个候选项"
        else:
            resolved_message = "请补充必要信息"
    return {
        "type": "clarify",
        "mode": normalize_message_content(confirmation.get("mode") or ""),
        "question": resolved_message,
        "message": resolved_message,
        "input": input_spec,
        "options": normalized_options,
        "count": len(normalized_options),
        "output": output_spec,
    }


def store_pending_confirmation(tool_context: dict[str, Any] | None, payload: dict[str, Any]) -> None:
    chat_state = get_chat_state(tool_context)
    if chat_state is not None:
        chat_state["pending_confirmation"] = payload


def get_pending_confirmation(tool_context: dict[str, Any] | None) -> dict[str, Any]:
    chat_state = get_chat_state(tool_context)
    pending = chat_state.get("pending_confirmation")
    return pending if isinstance(pending, dict) else {}


def clear_pending_confirmation(tool_context: dict[str, Any] | None) -> None:
    chat_state = get_chat_state(tool_context)
    if chat_state:
        chat_state.pop("pending_confirmation", None)


def _parse_boolean_reply(text: str) -> bool | None:
    normalized = normalize_message_content(text).lower()
    if normalized in {"1", "y", "yes", "true", "ok", "confirm", "continue", "是", "好", "确认", "继续"}:
        return True
    if normalized in {"0", "n", "no", "false", "cancel", "stop", "否", "不", "取消", "停止"}:
        return False
    return None


def resolve_pending_confirmation_reply(
    text: str,
    tool_context: dict[str, Any] | None,
) -> dict[str, Any]:
    pending = get_pending_confirmation(tool_context)
    if not pending:
        return {"matched": False, "resolved": False}

    normalized_text = normalize_message_content(text)
    confirmation = pending.get("confirmation") if isinstance(pending.get("confirmation"), dict) else {}
    input_spec = confirmation.get("input") if isinstance(confirmation.get("input"), dict) else {}
    output_spec = confirmation.get("output") if isinstance(confirmation.get("output"), dict) else {}
    mode = normalize_message_content(confirmation.get("mode") or pending.get("mode") or "").lower()
    input_type = normalize_message_content(input_spec.get("type") or "").lower()
    output_type = normalize_message_content(output_spec.get("type") or "").lower()
    store_as = normalize_message_content(output_spec.get("store_as") or pending.get("store_as") or "")
    options = build_confirmation_options(pending.get("options") if isinstance(pending.get("options"), list) else [])

    if mode == "approve" or input_type == "boolean":
        boolean_value = _parse_boolean_reply(normalized_text)
        if boolean_value is None:
            return {
                "matched": True,
                "resolved": False,
                "message": normalize_message_content(pending.get("message") or "请输入确认结果"),
                "clarify": build_confirmation_payload(confirmation, options=options, message=pending.get("message")),
            }
        resolved_value: Any = boolean_value
    elif mode == "select" or input_type == "index":
        if not normalized_text.isdigit():
            return {
                "matched": True,
                "resolved": False,
                "message": normalize_message_content(pending.get("message") or "请输入有效序号"),
                "clarify": build_confirmation_payload(confirmation, options=options, message=pending.get("message")),
            }
        index = int(normalized_text)
        if index < 1 or index > len(options):
            return {
                "matched": True,
                "resolved": False,
                "message": normalize_message_content(pending.get("message") or "序号无效，请重新输入"),
                "clarify": build_confirmation_payload(confirmation, options=options, message=pending.get("message")),
            }
        selected_option = options[index - 1]
        if output_type == "selected_option_index":
            resolved_value = selected_option.get("index")
        elif output_type == "selected_option_label":
            resolved_value = selected_option.get("label")
        else:
            resolved_value = selected_option.get("value")
    else:
        allow_empty = bool(input_spec.get("allow_empty"))
        if not normalized_text and not allow_empty:
            return {
                "matched": True,
                "resolved": False,
                "message": normalize_message_content(pending.get("message") or "输入不能为空"),
                "clarify": build_confirmation_payload(confirmation, options=options, message=pending.get("message")),
            }
        if input_type == "number":
            try:
                resolved_value = float(normalized_text)
            except ValueError:
                return {
                    "matched": True,
                    "resolved": False,
                    "message": normalize_message_content(pending.get("message") or "请输入数字"),
                    "clarify": build_confirmation_payload(confirmation, options=options, message=pending.get("message")),
                }
        elif input_type == "integer":
            try:
                resolved_value = int(normalized_text)
            except ValueError:
                return {
                    "matched": True,
                    "resolved": False,
                    "message": normalize_message_content(pending.get("message") or "请输入整数"),
                    "clarify": build_confirmation_payload(confirmation, options=options, message=pending.get("message")),
                }
        elif input_type == "boolean":
            boolean_value = _parse_boolean_reply(normalized_text)
            if boolean_value is None:
                return {
                    "matched": True,
                    "resolved": False,
                    "message": normalize_message_content(pending.get("message") or "请输入是或否"),
                    "clarify": build_confirmation_payload(confirmation, options=options, message=pending.get("message")),
                }
            resolved_value = boolean_value
        else:
            resolved_value = normalized_text

    if store_as:
        store_playbook_input(tool_context, store_as, resolved_value)
    clear_pending_confirmation(tool_context)
    return {
        "matched": True,
        "resolved": True,
        "store_as": store_as,
        "value": resolved_value,
    }
