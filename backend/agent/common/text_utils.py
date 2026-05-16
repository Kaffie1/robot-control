import json
import re
from typing import Any


def normalize_message_content(value: Any) -> str:
    return str(value or "").strip()


def strip_think_blocks(text: str) -> str:
    normalized = str(text or "")
    cleaned = re.sub(r"<think>.*?</think>", "", normalized, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"^\s*思考过程[:：].*$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_json_payload(text: str) -> dict[str, Any] | None:
    normalized = strip_think_blocks(str(text or ""))
    if not normalized:
        return None
    fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", normalized, flags=re.IGNORECASE | re.DOTALL)
    if fenced_match:
        normalized = fenced_match.group(1).strip()

    first_brace = normalized.find("{")
    if first_brace < 0:
        return None
    depth = 0
    end_index = -1
    for index, char in enumerate(normalized[first_brace:], start=first_brace):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end_index = index
                break
    if end_index < 0:
        return None
    try:
        payload = json.loads(normalized[first_brace : end_index + 1].strip())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
