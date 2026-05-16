from __future__ import annotations

from typing import Any

from ...models import ApiError

ALLOWED_SCRIPT_FAILURE_ACTIONS = {"stop", "escalate", "call_playbook"}
ALLOWED_SUCCESS_FAILURE_ACTIONS = {"stop", "escalate"}
ALLOWED_CONFIRMATION_MODES = {"approve", "input", "select"}
ALLOWED_CONFIRMATION_INPUT_TYPES = {"text", "number", "integer", "boolean", "index"}
ALLOWED_CONFIRMATION_OUTPUT_TYPES = {
    "raw_input",
    "boolean",
    "selected_option_value",
    "selected_option_label",
    "selected_option_index",
}
ALLOWED_CONFIRMATION_TIMINGS = {"before", "after"}
ALLOWED_CONFIRMATION_OPTION_PARSERS = {"string_list"}
ALLOWED_BT_NODE_TYPES = {"sequence", "selector", "condition", "action", "call_playbook", "result"}


def validate_confirmation_spec(
    confirmation: Any,
    *,
    playbook_id: str,
    step_index: int,
    location: str,
) -> None:
    if not isinstance(confirmation, dict):
        raise ApiError(f"{location} confirmation 必须是对象: {playbook_id}[{step_index}]")
    mode = str(confirmation.get("mode") or "").strip().lower()
    if not mode:
        raise ApiError(f"{location} confirmation 缺少 mode: {playbook_id}[{step_index}]")
    if mode not in ALLOWED_CONFIRMATION_MODES:
        raise ApiError(f"{location} confirmation.mode 不支持: {mode}")
    timing = str(confirmation.get("when") or "").strip().lower()
    if timing and timing not in ALLOWED_CONFIRMATION_TIMINGS:
        raise ApiError(f"{location} confirmation.when 不支持: {timing}")

    message = confirmation.get("message")
    if message is not None and not isinstance(message, str):
        raise ApiError(f"{location} confirmation.message 必须是字符串: {playbook_id}[{step_index}]")

    input_spec = confirmation.get("input")
    if input_spec is not None:
        if not isinstance(input_spec, dict):
            raise ApiError(f"{location} confirmation.input 必须是对象: {playbook_id}[{step_index}]")
        input_type = str(input_spec.get("type") or "").strip().lower()
        if input_type and input_type not in ALLOWED_CONFIRMATION_INPUT_TYPES:
            raise ApiError(f"{location} confirmation.input.type 不支持: {input_type}")
        for string_field in ("placeholder", "label", "help_text"):
            field_value = input_spec.get(string_field)
            if field_value is not None and not isinstance(field_value, str):
                raise ApiError(f"{location} confirmation.input.{string_field} 必须是字符串: {playbook_id}[{step_index}]")
        allow_empty = input_spec.get("allow_empty")
        if allow_empty is not None and not isinstance(allow_empty, bool):
            raise ApiError(f"{location} confirmation.input.allow_empty 必须是布尔值: {playbook_id}[{step_index}]")
        auto_select_if_single = input_spec.get("auto_select_if_single")
        if auto_select_if_single is not None and not isinstance(auto_select_if_single, bool):
            raise ApiError(f"{location} confirmation.input.auto_select_if_single 必须是布尔值: {playbook_id}[{step_index}]")
        options = input_spec.get("options")
        if options is not None and not isinstance(options, list):
            raise ApiError(f"{location} confirmation.input.options 必须是列表: {playbook_id}[{step_index}]")
        if isinstance(options, list):
            for option_index, option in enumerate(options):
                if isinstance(option, str):
                    continue
                if not isinstance(option, dict):
                    raise ApiError(f"{location} confirmation.input.options[{option_index}] 必须是字符串或对象: {playbook_id}[{step_index}]")
                for option_field in ("label", "value"):
                    option_value = option.get(option_field)
                    if option_value is not None and not isinstance(option_value, (str, int, float, bool)):
                        raise ApiError(
                            f"{location} confirmation.input.options[{option_index}].{option_field} 类型不支持: {playbook_id}[{step_index}]"
                        )
        options_source = input_spec.get("options_source")
        if options_source is not None:
            if not isinstance(options_source, dict):
                raise ApiError(f"{location} confirmation.input.options_source 必须是对象: {playbook_id}[{step_index}]")
            field_name = str(options_source.get("field") or "").strip()
            if not field_name:
                raise ApiError(f"{location} confirmation.input.options_source 缺少 field: {playbook_id}[{step_index}]")
            parser_name = str(options_source.get("parser") or "").strip().lower()
            if parser_name and parser_name not in ALLOWED_CONFIRMATION_OPTION_PARSERS:
                raise ApiError(f"{location} confirmation.input.options_source.parser 不支持: {parser_name}")
            list_key = options_source.get("list_key")
            if list_key is not None and not isinstance(list_key, str):
                raise ApiError(f"{location} confirmation.input.options_source.list_key 必须是字符串: {playbook_id}[{step_index}]")

    output_spec = confirmation.get("output")
    if output_spec is not None:
        if not isinstance(output_spec, dict):
            raise ApiError(f"{location} confirmation.output 必须是对象: {playbook_id}[{step_index}]")
        store_as = str(output_spec.get("store_as") or "").strip()
        if not store_as:
            raise ApiError(f"{location} confirmation.output 缺少 store_as: {playbook_id}[{step_index}]")
        output_type = str(output_spec.get("type") or "").strip().lower()
        if output_type and output_type not in ALLOWED_CONFIRMATION_OUTPUT_TYPES:
            raise ApiError(f"{location} confirmation.output.type 不支持: {output_type}")
    elif mode in {"input", "select"}:
        raise ApiError(f"{location} confirmation.output 缺少 store_as 配置: {playbook_id}[{step_index}]")


def validate_playbook_spec(playbook: dict[str, Any]) -> None:
    if not isinstance(playbook, dict):
        raise ApiError("playbook 格式错误")
    playbook_id = str(playbook.get("id") or "").strip()
    if not playbook_id:
        raise ApiError("playbook 缺少 id")

    root = playbook.get("root")
    script = playbook.get("script")
    if isinstance(root, dict):
        validate_bt_node_spec(root, playbook_id=playbook_id, path="root")
    else:
        if not isinstance(script, list) or not script:
            raise ApiError(f"playbook 缺少 script: {playbook_id}")
        for index, raw_step in enumerate(script):
            if not isinstance(raw_step, dict):
                raise ApiError(f"脚本步骤格式错误: {playbook_id}[{index}]")
            tool_name = str(raw_step.get("tool_name") or "").strip()
            if not tool_name:
                raise ApiError(f"脚本步骤缺少 tool_name: {playbook_id}[{index}]")
            arguments = raw_step.get("arguments")
            if arguments is not None and not isinstance(arguments, dict):
                raise ApiError(f"脚本步骤 arguments 必须是对象: {playbook_id}[{index}]")
            require_confirmation = raw_step.get("require_confirmation")
            if require_confirmation is not None and not isinstance(require_confirmation, bool):
                raise ApiError(f"脚本步骤 require_confirmation 必须是布尔值: {playbook_id}[{index}]")
            confirmation = raw_step.get("confirmation")
            if confirmation is not None:
                validate_confirmation_spec(
                    confirmation,
                    playbook_id=playbook_id,
                    step_index=index,
                    location="脚本步骤",
                )
            on_fail = raw_step.get("on_fail")
            if on_fail is not None:
                if not isinstance(on_fail, dict):
                    raise ApiError(f"脚本步骤 on_fail 必须是对象: {playbook_id}[{index}]")
                action = str(on_fail.get("action") or "").strip().lower()
                if action and action not in ALLOWED_SCRIPT_FAILURE_ACTIONS:
                    raise ApiError(f"脚本步骤不支持的 on_fail.action: {action}")
                if action == "call_playbook":
                    failure_playbook_id = str(on_fail.get("playbook_id") or on_fail.get("target_playbook_id") or "").strip()
                    if not failure_playbook_id:
                        raise ApiError(f"脚本步骤 call_playbook 缺少 playbook_id: {playbook_id}[{index}]")

    success_criteria = playbook.get("success_criteria")
    if success_criteria is not None and not isinstance(success_criteria, list):
        raise ApiError(f"success_criteria 必须是列表: {playbook_id}")
    if isinstance(success_criteria, list):
        for index, raw_item in enumerate(success_criteria):
            if not isinstance(raw_item, dict):
                raise ApiError(f"success_criteria 格式错误: {playbook_id}[{index}]")
            tool_name = str(raw_item.get("tool_name") or "").strip()
            if not tool_name:
                raise ApiError(f"success_criteria 缺少 tool_name: {playbook_id}[{index}]")
            arguments = raw_item.get("arguments")
            if arguments is not None and not isinstance(arguments, dict):
                raise ApiError(f"success_criteria arguments 必须是对象: {playbook_id}[{index}]")
            confirmation = raw_item.get("confirmation")
            if confirmation is not None:
                validate_confirmation_spec(
                    confirmation,
                    playbook_id=playbook_id,
                    step_index=index,
                    location="success_criteria",
                )
            on_fail = raw_item.get("on_fail")
            if on_fail is not None:
                if not isinstance(on_fail, dict):
                    raise ApiError(f"success_criteria on_fail 必须是对象: {playbook_id}[{index}]")
                action = str(on_fail.get("action") or "").strip().lower()
                if action and action not in ALLOWED_SUCCESS_FAILURE_ACTIONS:
                    raise ApiError(f"success_criteria 不支持的 on_fail.action: {action}")

    for list_field in ("escalation_notes", "execution_notes", "global_rules"):
        if list_field in playbook and not isinstance(playbook.get(list_field), list):
            raise ApiError(f"{list_field} 必须是列表: {playbook_id}")


def validate_bt_node_spec(
    node: Any,
    *,
    playbook_id: str,
    path: str,
) -> None:
    if not isinstance(node, dict):
        raise ApiError(f"行为树节点必须是对象: {playbook_id}.{path}")
    node_type = str(node.get("type") or "").strip().lower()
    if not node_type:
        raise ApiError(f"行为树节点缺少 type: {playbook_id}.{path}")
    if node_type not in ALLOWED_BT_NODE_TYPES:
        raise ApiError(f"行为树节点类型不支持: {node_type}")
    if node_type in {"sequence", "selector"}:
        children = node.get("children")
        if not isinstance(children, list) or not children:
            raise ApiError(f"组合节点缺少 children: {playbook_id}.{path}")
        for index, child in enumerate(children):
            validate_bt_node_spec(child, playbook_id=playbook_id, path=f"{path}.children[{index}]")
        return
    if node_type in {"condition", "action"}:
        tool_name = str(node.get("tool_name") or "").strip()
        if not tool_name:
            raise ApiError(f"行为树叶子节点缺少 tool_name: {playbook_id}.{path}")
        arguments = node.get("arguments")
        if arguments is not None and not isinstance(arguments, dict):
            raise ApiError(f"行为树叶子节点 arguments 必须是对象: {playbook_id}.{path}")
        require_confirmation = node.get("require_confirmation")
        if require_confirmation is not None and not isinstance(require_confirmation, bool):
            raise ApiError(f"行为树叶子节点 require_confirmation 必须是布尔值: {playbook_id}.{path}")
        confirmation = node.get("confirmation")
        if confirmation is not None:
            validate_confirmation_spec(
                confirmation,
                playbook_id=playbook_id,
                step_index=0,
                location=f"行为树节点 {path}",
            )
        return
    if node_type == "call_playbook":
        failure_playbook_id = str(node.get("playbook_id") or node.get("target_playbook_id") or "").strip()
        if not failure_playbook_id:
            raise ApiError(f"行为树 call_playbook 节点缺少 playbook_id: {playbook_id}.{path}")
        return
    if node_type == "result":
        status = str(node.get("status") or "").strip().lower()
        if status not in {"success", "failure", "running"}:
            raise ApiError(f"行为树 result 节点缺少有效 status: {playbook_id}.{path}")
