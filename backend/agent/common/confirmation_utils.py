from __future__ import annotations

import re
from typing import Any

from ...errors import ApiError


_CONTEXT_REF_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")
_TRUE_TEXTS = {"1", "true", "yes", "y", "ok", "confirm", "是", "确认", "同意", "允许", "可以", "继续", "好"}
_FALSE_TEXTS = {"0", "false", "no", "n", "cancel", "否", "拒绝", "不同意", "不允许", "不可以", "停止"}


def get_context_value(tool_context: dict[str, Any] | None, key: str) -> Any:
    if not isinstance(tool_context, dict):
        return None
    return tool_context.get(str(key or "").strip())


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


def has_context_value(tool_context: dict[str, Any] | None, key: str) -> bool:
    value = get_context_value(tool_context, key)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def get_confirmation_request(
    node_spec: dict[str, Any],
    tool_context: dict[str, Any] | None,
    *,
    playbook_id: str,
    playbook_title: str,
    node_path: str,
) -> dict[str, Any] | None:
    if not bool(node_spec.get("require_confirmation")):
        return None
    confirmation = node_spec.get("confirmation")
    if not isinstance(confirmation, dict):
        raise ApiError(f"确认节点缺少 confirmation 配置: {playbook_id}.{node_path}")
    when = str(confirmation.get("when") or "before").strip().lower()
    if when != "before":
        raise ApiError(f"当前仅支持 before 确认: {playbook_id}.{node_path}")
    mode = str(confirmation.get("mode") or "input").strip().lower()
    output = confirmation.get("output") if isinstance(confirmation.get("output"), dict) else {}
    store_as = str(output.get("store_as") or "").strip()
    if store_as and has_context_value(tool_context, store_as):
        return None
    raw_message = str(
        confirmation.get("message")
        or node_spec.get("failure_message")
        or f"请确认步骤 {node_spec.get('name') or node_spec.get('tool_name') or node_path} 所需信息"
    ).strip()
    if not raw_message:
        raise ApiError(f"确认节点缺少提示语: {playbook_id}.{node_path}")
    message = _build_confirmation_message(raw_message, mode, confirmation)
    return {
        "type": "playbook_confirmation",
        "playbook_id": playbook_id,
        "playbook_title": playbook_title,
        "node_path": node_path,
        "node_name": str(node_spec.get("name") or node_spec.get("tool_name") or "").strip(),
        "tool_name": str(node_spec.get("tool_name") or "").strip(),
        "message": message,
        "mode": mode,
        "input": confirmation.get("input") if isinstance(confirmation.get("input"), dict) else {},
        "output": output,
    }


def _build_confirmation_message(base_message: str, mode: str, confirmation: dict[str, Any]) -> str:
    normalized_base = base_message.strip()
    if mode == "approve":
        return f"{normalized_base}\n可直接回复：允许 / 拒绝"
    if mode == "input":
        input_spec = confirmation.get("input") if isinstance(confirmation.get("input"), dict) else {}
        label = str(input_spec.get("label") or "").strip()
        placeholder = str(input_spec.get("placeholder") or "").strip()
        parts = [normalized_base]
        if label:
            parts.append(f"请输入：{label}")
        if placeholder:
            parts.append(f"示例：{placeholder}")
        return "\n".join(parts)
    if mode == "select":
        input_spec = confirmation.get("input") if isinstance(confirmation.get("input"), dict) else {}
        options = _normalize_select_options(input_spec.get("options"))
        if not options:
            return normalized_base
        option_lines = [f"{option['index'] + 1}. {option['label']}" for option in options]
        return "\n".join([normalized_base, "可回复序号或选项文本：", *option_lines])
    return normalized_base


def _coerce_boolean(text: str) -> bool:
    normalized = text.strip().lower()
    if normalized in _TRUE_TEXTS:
        return True
    if normalized in _FALSE_TEXTS:
        return False
    raise ApiError("无法识别你的确认结果。请直接回复：允许 / 拒绝")


def _normalize_select_options(raw_options: Any) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    if not isinstance(raw_options, list):
        return options
    for index, item in enumerate(raw_options):
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or item.get("value") or "").strip()
            value = item.get("value", label)
        else:
            label = str(item or "").strip()
            value = label
        if not label:
            continue
        options.append({"label": label, "value": value, "index": index})
    return options


def resolve_confirmation_value(request: dict[str, Any], response_text: str) -> Any:
    mode = str(request.get("mode") or "input").strip().lower()
    input_spec = request.get("input") if isinstance(request.get("input"), dict) else {}
    output_spec = request.get("output") if isinstance(request.get("output"), dict) else {}
    response = str(response_text or "").strip()

    if mode == "approve":
        approved = _coerce_boolean(response)
        output_type = str(output_spec.get("type") or "boolean").strip().lower()
        if output_type in {"", "boolean", "raw_input"}:
            return approved
        raise ApiError(f"暂不支持的 approve 输出类型: {output_type}")

    if mode == "input":
        allow_empty = bool(input_spec.get("allow_empty"))
        if not response and not allow_empty:
            raise ApiError("确认输入不能为空")
        input_type = str(input_spec.get("type") or "text").strip().lower()
        if input_type in {"text", "string"}:
            value: Any = response
        elif input_type == "number":
            try:
                value = float(response)
            except ValueError as exc:
                raise ApiError("请输入数字") from exc
        elif input_type == "integer":
            try:
                value = int(response)
            except ValueError as exc:
                raise ApiError("请输入整数") from exc
        elif input_type == "boolean":
            value = _coerce_boolean(response)
        elif input_type == "index":
            try:
                value = int(response)
            except ValueError as exc:
                raise ApiError("请输入索引数字") from exc
        else:
            raise ApiError(f"暂不支持的确认输入类型: {input_type}")
        return value

    if mode == "select":
        options = _normalize_select_options(input_spec.get("options"))
        if not options:
            raise ApiError("select 确认缺少 options")
        if not response and bool(input_spec.get("auto_select_if_single")) and len(options) == 1:
            selected = options[0]
        else:
            selected = None
            if response.isdigit():
                selected_index = int(response)
                for option in options:
                    if option["index"] == selected_index or option["index"] + 1 == selected_index:
                        selected = option
                        break
            if selected is None:
                for option in options:
                    if response in {str(option["label"]).strip(), str(option["value"]).strip()}:
                        selected = option
                        break
            if selected is None:
                raise ApiError("未匹配到可选项，请按编号或选项文本回复")
        output_type = str(output_spec.get("type") or "selected_option_value").strip().lower()
        if output_type == "selected_option_value":
            return selected["value"]
        if output_type == "selected_option_label":
            return selected["label"]
        if output_type == "selected_option_index":
            return selected["index"]
        raise ApiError(f"暂不支持的 select 输出类型: {output_type}")

    raise ApiError(f"暂不支持的确认模式: {mode}")


def apply_confirmation_response(
    tool_context: dict[str, Any] | None,
    request: dict[str, Any] | None,
    response_text: str,
) -> dict[str, Any]:
    updated = dict(tool_context or {})
    if not isinstance(request, dict):
        return updated
    output_spec = request.get("output") if isinstance(request.get("output"), dict) else {}
    store_as = str(output_spec.get("store_as") or "").strip()
    if not store_as:
        return updated
    updated[store_as] = resolve_confirmation_value(request, response_text)
    return updated
