from __future__ import annotations

# 规则引擎负责把 playbook / success_criteria 里的断言配置统一转成可执行判断。
# 这里尽量只做“字段取值 + 条件计算 + 规则引用解析”，避免把具体业务逻辑
# 写死在 playbook 执行器里。外层的 config/fault_rules.yaml 只作为规则模板，
# 实际规则实现放在每个 playbook 自己的 rules.yaml 里。
from functools import lru_cache
from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Any

import yaml

from ...config import FAULT_PLAYBOOK_RULES_FILENAME
from ...models import ApiError
from ..common import expand_context_references
from .schema import validate_rule_catalog, validate_rule_spec


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not raw_text.strip():
        return {}
    try:
        payload = yaml.safe_load(raw_text)
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


@lru_cache(maxsize=32)
def _load_rule_catalog_cached(path_text: str) -> dict[str, dict[str, Any]]:
    payload = _read_yaml(Path(path_text))
    rules = payload.get("rules")
    catalog: dict[str, dict[str, Any]] = {}
    if isinstance(rules, dict):
        for name, spec in rules.items():
            normalized_name = str(name or "").strip()
            if normalized_name and isinstance(spec, dict):
                catalog[normalized_name] = dict(spec)
    elif isinstance(rules, list):
        for item in rules:
            if not isinstance(item, dict):
                continue
            normalized_name = str(item.get("name") or item.get("id") or "").strip()
            if not normalized_name:
                continue
            spec = item.get("assert") if isinstance(item.get("assert"), dict) else item.get("rule")
            if isinstance(spec, dict):
                catalog[normalized_name] = dict(spec)
            else:
                catalog[normalized_name] = {
                    key: value
                    for key, value in item.items()
                    if key not in {"name", "id"}
                }
    return catalog


def load_rule_catalog(rules_source_path: str | Path | None) -> dict[str, dict[str, Any]]:
    if not rules_source_path:
        return {}
    resolved_path = Path(rules_source_path).expanduser().resolve(strict=False)
    return _load_rule_catalog_cached(str(resolved_path))


def get_playbook_rules_path(playbook_source_path: str | Path | None) -> Path | None:
    if not playbook_source_path:
        return None
    playbook_path = Path(playbook_source_path)
    if not playbook_path.name:
        return None
    return playbook_path.with_name(FAULT_PLAYBOOK_RULES_FILENAME)


def build_playbook_rule_context(tool_context: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(tool_context or {})
    playbook_source_path = merged.get("playbook_source_path")
    explicit_rules_source_path = str(merged.get("playbook_rules_source_path") or "").strip()
    resolved_rules_source_path = explicit_rules_source_path
    if playbook_source_path:
        rules_path = get_playbook_rules_path(playbook_source_path)
        if rules_path is not None:
            resolved_rules_source_path = str(rules_path)
    elif not resolved_rules_source_path:
        resolved_rules_source_path = ""
    existing_rules_source_path = str(merged.get("playbook_rule_catalog_source_path") or "")
    existing_catalog = merged.get("playbook_rule_catalog")
    if (
        isinstance(existing_catalog, dict)
        and resolved_rules_source_path
        and existing_rules_source_path == resolved_rules_source_path
    ):
        merged["playbook_rules_source_path"] = resolved_rules_source_path
        return merged
    merged["playbook_rules_source_path"] = resolved_rules_source_path
    merged["playbook_rule_catalog_source_path"] = resolved_rules_source_path
    merged["playbook_rule_catalog"] = load_rule_catalog(resolved_rules_source_path) if resolved_rules_source_path else {}
    return merged


def _get_value_by_path(payload: Any, field: str) -> tuple[bool, Any]:
    normalized_field = str(field or "").strip()
    if not normalized_field:
        return False, None
    current = payload
    if normalized_field == ".":
        return True, current
    for segment in normalized_field.split("."):
        if isinstance(current, dict):
            if segment not in current:
                return False, None
            current = current[segment]
            continue
        if isinstance(current, list) and segment.isdigit():
            index = int(segment)
            if index < 0 or index >= len(current):
                return False, None
            current = current[index]
            continue
        return False, None
    return True, current


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    return None


def _to_timestamp(value: Any) -> float | None:
    numeric_value = _to_number(value)
    if numeric_value is not None:
        return numeric_value
    text = str(value or "").strip()
    if not text:
        return None
    for parser in (
        lambda raw: datetime.fromisoformat(raw.replace("Z", "+00:00")),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d %H:%M:%S"),
    ):
        try:
            parsed = parser(text)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    return None


def _is_not_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _normalize_comparable(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _normalize_condition(condition: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(condition)
    condition_type = str(normalized.get("type") or "").strip().lower()
    if condition_type == "compare":
        normalized["type"] = "compare"
        return normalized
    return normalized


def _cast_condition_value(value: Any, cast: Any) -> Any:
    normalized_cast = str(cast or "auto").strip().lower()
    if normalized_cast in {"", "auto", "raw"}:
        return value
    if normalized_cast in {"number", "float", "int"}:
        return _to_number(value)
    if normalized_cast in {"bool", "boolean"}:
        return _to_bool(value)
    if normalized_cast == "timestamp":
        return _to_timestamp(value)
    if normalized_cast in {"string", "str", "text"}:
        return "" if value is None else str(value)
    return value


def _extract_condition_value(condition: dict[str, Any], value: Any) -> tuple[bool, Any]:
    extract_spec = condition.get("extract")
    if not isinstance(extract_spec, dict):
        return True, value
    extract_type = str(extract_spec.get("type") or "regex").strip().lower()
    if extract_type != "regex":
        raise ApiError(f"不支持的提取类型: {extract_type}")
    pattern = str(extract_spec.get("pattern") or "").strip()
    if not pattern:
        raise ApiError("regex 提取缺少 pattern")
    group = int(_to_number(extract_spec.get("group")) or 1)
    flags = 0
    if _to_bool(extract_spec.get("ignore_case")):
        flags |= re.IGNORECASE
    match = re.search(pattern, str(value or ""), flags)
    if not match:
        return False, None
    try:
        if group == 0:
            extracted = match.group(0)
        else:
            extracted = match.group(group)
    except IndexError as exc:
        raise ApiError(f"regex 提取组不存在: {group}") from exc
    return True, extracted


def _compare_ordered_values(op: str, actual: Any, expected: Any) -> bool:
    normalized_op = op.strip().lower()
    if normalized_op == "equals":
        return _normalize_comparable(actual) == _normalize_comparable(expected)
    if normalized_op == "not_equals":
        return _normalize_comparable(actual) != _normalize_comparable(expected)

    actual_number = _to_number(actual)
    expected_number = _to_number(expected)
    if normalized_op == "greater_than":
        return actual_number is not None and expected_number is not None and actual_number > expected_number
    if normalized_op == "greater_or_equal":
        return actual_number is not None and expected_number is not None and actual_number >= expected_number
    if normalized_op == "less_than":
        return actual_number is not None and expected_number is not None and actual_number < expected_number
    if normalized_op == "less_or_equal":
        return actual_number is not None and expected_number is not None and actual_number <= expected_number

    if normalized_op == "contains":
        if isinstance(actual, list):
            normalized_expected = _normalize_comparable(expected)
            return normalized_expected in actual or str(normalized_expected) in [str(item) for item in actual]
        return str(expected) in str(actual or "")
    if normalized_op == "not_contains":
        if isinstance(actual, list):
            normalized_expected = _normalize_comparable(expected)
            return normalized_expected not in actual and str(normalized_expected) not in [str(item) for item in actual]
        return str(expected) not in str(actual or "")
    if normalized_op == "regex_match":
        pattern = str(expected or "").strip()
        if not pattern:
            return False
        return bool(re.search(pattern, str(actual or "")))
    if normalized_op == "list_contains":
        if isinstance(actual, list):
            normalized_expected = _normalize_comparable(expected)
            return normalized_expected in actual or str(normalized_expected) in [str(item) for item in actual]
        return False
    if normalized_op == "length_gt":
        compare_value = max(int(expected_number or 0), 0)
        if actual is None:
            return False
        try:
            return len(actual) > compare_value
        except TypeError:
            return len(str(actual)) > compare_value
    raise ApiError(f"不支持的规则比较运算: {op}")


def _evaluate_compare_condition(condition: dict[str, Any], payload: Any, tool_context: dict[str, Any] | None) -> bool:
    field = str(condition.get("field") or "").strip()
    exists, raw_value = _get_value_by_path(payload, field)
    op = str(condition.get("op") or "").strip().lower()
    if op == "exists":
        return exists
    if op == "not_exists":
        return not exists
    if not exists:
        return False

    value_exists, extracted_value = _extract_condition_value(condition, raw_value)
    if not value_exists:
        return False

    if op == "not_empty":
        return _is_not_empty(extracted_value)
    if op == "empty":
        return not _is_not_empty(extracted_value)
    if op == "boolean_true":
        return _to_bool(extracted_value) is True
    if op == "boolean_false":
        return _to_bool(extracted_value) is False
    if op == "timestamp_recent":
        within_seconds = max(int(_to_number(condition.get("within_seconds")) or 0), 0)
        actual_timestamp = _to_timestamp(extracted_value)
        if actual_timestamp is None:
            return False
        return abs(datetime.now(tz=timezone.utc).timestamp() - actual_timestamp) <= within_seconds

    expected_value = condition.get("value")
    value_field = str(condition.get("value_field") or "").strip()
    if value_field:
        expected_exists, expected_raw_value = _get_value_by_path(payload, value_field)
        if not expected_exists:
            return False
        expected_value = expected_raw_value

    expected_value = expand_context_references(expected_value, tool_context)
    cast_name = condition.get("cast")
    if cast_name:
        extracted_value = _cast_condition_value(extracted_value, cast_name)
        expected_value = _cast_condition_value(expected_value, cast_name)

    if op == "between":
        actual_number = _to_number(extracted_value)
        min_value = _to_number(condition.get("min"))
        max_value = _to_number(condition.get("max"))
        if actual_number is None:
            return False
        if min_value is not None and actual_number < min_value:
            return False
        if max_value is not None and actual_number > max_value:
            return False
        return True
    if op in {"fields_equal", "equal_fields"}:
        return _normalize_comparable(extracted_value) == _normalize_comparable(expected_value)
    return _compare_ordered_values(op, extracted_value, expected_value)


def evaluate_condition(condition: dict[str, Any], payload: Any, tool_context: dict[str, Any] | None = None) -> bool:
    normalized_condition = _normalize_condition(expand_context_references(condition, tool_context))
    condition_type = str(normalized_condition.get("type") or "").strip().lower()
    if not condition_type and "op" in normalized_condition and "conditions" in normalized_condition:
        return evaluate_assert_spec(normalized_condition, payload, tool_context=tool_context)
    if condition_type == "compare":
        return _evaluate_compare_condition(normalized_condition, payload, tool_context)
    raise ApiError(f"不支持的规则条件类型: {condition_type}")


def evaluate_assert_spec(
    assert_spec: dict[str, Any],
    payload: Any,
    *,
    tool_context: dict[str, Any] | None = None,
) -> bool:
    normalized_spec = expand_context_references(assert_spec, tool_context)
    normalized_spec = _normalize_condition(normalized_spec)
    if isinstance(normalized_spec.get("type"), str) and normalized_spec.get("type"):
        return evaluate_condition(normalized_spec, payload, tool_context)
    op = str(normalized_spec.get("op") or "and").strip().lower()
    conditions = normalized_spec.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ApiError("规则引擎缺少 conditions")

    results: list[bool] = []
    for raw_condition in conditions:
        if not isinstance(raw_condition, dict):
            continue
        results.append(evaluate_condition(raw_condition, payload, tool_context))

    if op == "and":
        return all(results) if results else False
    if op == "or":
        return any(results) if results else False
    raise ApiError(f"不支持的规则逻辑运算: {op}")


def resolve_assert_spec(step: dict[str, Any], tool_context: dict[str, Any] | None = None) -> tuple[str, dict[str, Any] | None]:
    inline_assert = step.get("assert") if isinstance(step.get("assert"), dict) else None
    if inline_assert:
        return "inline_assert", dict(inline_assert)

    assert_ref = str(step.get("assert_ref") or step.get("expect") or "").strip()
    if not assert_ref:
        return "", None

    merged_tool_context = build_playbook_rule_context(tool_context)
    catalog = merged_tool_context.get("playbook_rule_catalog")
    if not isinstance(catalog, dict):
        catalog = {}
    rule_spec = catalog.get(assert_ref)
    if rule_spec is None:
        raise ApiError(f"未找到规则定义: {assert_ref}")
    return assert_ref, dict(rule_spec)


def evaluate_step_assertion(
    step: dict[str, Any],
    payload: Any,
    *,
    tool_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rule_name, rule_spec = resolve_assert_spec(step, tool_context)
    if not rule_spec:
        return {
            "rule_name": "",
            "rule_spec": None,
            "passed": bool(payload),
        }
    if isinstance(rule_spec.get("type"), str) and rule_spec.get("type"):
        passed = evaluate_condition(rule_spec, payload, tool_context)
    else:
        passed = evaluate_assert_spec(rule_spec, payload, tool_context=tool_context)
    return {
        "rule_name": rule_name,
        "rule_spec": rule_spec,
        "passed": passed,
    }
