from __future__ import annotations

from typing import Any

from ...models import ApiError

ALLOWED_COMPARE_OPERATORS = {
    "equals",
    "not_equals",
    "greater_than",
    "greater_or_equal",
    "less_than",
    "less_or_equal",
    "contains",
    "not_contains",
    "regex_match",
    "list_contains",
    "exists",
    "not_exists",
    "empty",
    "not_empty",
    "between",
    "boolean_true",
    "boolean_false",
    "timestamp_recent",
    "length_gt",
    "fields_equal",
    "equal_fields",
}

ALLOWED_COMPOUND_OPERATORS = {"and", "or"}


def validate_condition_spec(condition_name: str, condition: dict[str, Any]) -> None:
    normalized_name = str(condition_name or "").strip()
    if not normalized_name:
        raise ApiError("规则条件名称不能为空")
    if not isinstance(condition, dict):
        raise ApiError(f"规则条件格式错误: {normalized_name}")

    condition_type = str(condition.get("type") or "").strip().lower()
    if condition_type and condition_type != "compare":
        raise ApiError(f"不支持的规则条件类型: {condition_type}")

    op = str(condition.get("op") or "").strip().lower()
    if not op:
        raise ApiError(f"规则缺少 op: {normalized_name}")
    if not condition_type and isinstance(condition.get("conditions"), list) and op in ALLOWED_COMPOUND_OPERATORS:
        nested_conditions = condition.get("conditions")
        if not nested_conditions:
            raise ApiError(f"组合规则缺少 conditions: {normalized_name}")
        for index, nested_condition in enumerate(nested_conditions):
            if not isinstance(nested_condition, dict):
                raise ApiError(f"组合规则条件格式错误: {normalized_name}[{index}]")
            validate_condition_spec(f"{normalized_name}[{index}]", nested_condition)
        return
    if op not in ALLOWED_COMPARE_OPERATORS:
        raise ApiError(f"不支持的规则比较运算: {op}")

    field = str(condition.get("field") or "").strip()
    if not field and op not in {"and", "or"}:
        raise ApiError(f"规则缺少 field: {normalized_name}")

    if op == "between":
        if "min" not in condition or "max" not in condition:
            raise ApiError(f"between 规则缺少 min 或 max: {normalized_name}")
    if op == "timestamp_recent" and "within_seconds" not in condition:
        raise ApiError(f"timestamp_recent 规则缺少 within_seconds: {normalized_name}")

    extract_spec = condition.get("extract")
    if extract_spec is not None:
        if not isinstance(extract_spec, dict):
            raise ApiError(f"extract 格式错误: {normalized_name}")
        extract_type = str(extract_spec.get("type") or "regex").strip().lower()
        if extract_type != "regex":
            raise ApiError(f"不支持的提取类型: {extract_type}")
        if not str(extract_spec.get("pattern") or "").strip():
            raise ApiError(f"regex 提取缺少 pattern: {normalized_name}")


def validate_rule_spec(rule_name: str, rule_spec: dict[str, Any]) -> None:
    normalized_rule_name = str(rule_name or "").strip()
    if not normalized_rule_name:
        raise ApiError("规则名称不能为空")
    if not isinstance(rule_spec, dict):
        raise ApiError(f"规则定义格式错误: {normalized_rule_name}")

    if isinstance(rule_spec.get("conditions"), list):
        op = str(rule_spec.get("op") or "").strip().lower()
        if op not in ALLOWED_COMPOUND_OPERATORS:
            raise ApiError(f"组合规则 {normalized_rule_name} 的 op 必须是 and 或 or")
        if not rule_spec["conditions"]:
            raise ApiError(f"组合规则缺少 conditions: {normalized_rule_name}")
        for index, condition in enumerate(rule_spec["conditions"]):
            if not isinstance(condition, dict):
                raise ApiError(f"组合规则条件格式错误: {normalized_rule_name}[{index}]")
            validate_condition_spec(f"{normalized_rule_name}[{index}]", condition)
        return

    validate_condition_spec(normalized_rule_name, rule_spec)


def validate_rule_catalog(catalog: dict[str, dict[str, Any]]) -> None:
    if not isinstance(catalog, dict):
        raise ApiError("规则目录格式错误")
    for rule_name, rule_spec in catalog.items():
        validate_rule_spec(rule_name, rule_spec)
