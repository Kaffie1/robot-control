from __future__ import annotations

from typing import Any

from ..common import get_playbook_inputs, normalize_message_content, strip_think_blocks


def coerce_structured_text(value: Any) -> Any:
    import ast
    import json

    if isinstance(value, (dict, list)):
        return value
    text = normalize_message_content(value)
    if not text:
        return text
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except Exception:
            continue
        if isinstance(parsed, (dict, list)):
            return parsed
    return text


def format_section_block(title: str, value: Any) -> str:
    lines = [title]
    if isinstance(value, list):
        for item in value:
            item_text = normalize_message_content(item)
            if item_text:
                lines.append(f"- {item_text}")
    else:
        item_text = normalize_message_content(value)
        if item_text:
            lines.append(item_text)
    return "\n".join(lines).strip()


def render_final_message(value: Any) -> str:
    structured = coerce_structured_text(value)
    if isinstance(structured, dict):
        ordered_sections = ("问题：", "排查过程：", "结论：")
        if all(section in structured for section in ordered_sections):
            return "\n\n".join(
                format_section_block(section, structured.get(section))
                for section in ordered_sections
            ).strip()
        import json

        return json.dumps(structured, ensure_ascii=False, indent=2)
    if isinstance(structured, list):
        return "\n".join(
            f"- {normalize_message_content(item)}"
            for item in structured
            if normalize_message_content(item)
        ).strip()
    return strip_think_blocks(normalize_message_content(structured))


def extract_final_message(payload: dict[str, Any], fallback_text: str) -> str:
    candidates = [
        payload.get("answer"),
        payload.get("content"),
        payload.get("summary"),
        payload.get("message"),
        fallback_text,
    ]
    for candidate in candidates:
        text = render_final_message(candidate)
        if text:
            return text
    return ""


def final_message_has_required_sections(message: str) -> bool:
    text = normalize_message_content(message)
    if not text:
        return False
    required_sections = ("问题：", "排查过程：", "结论：")
    return all(section in text for section in required_sections)


def merge_tool_context(tool_context: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(tool_context or {})
    for key, value in get_playbook_inputs(tool_context).items():
        merged[str(key)] = value
    return merged
