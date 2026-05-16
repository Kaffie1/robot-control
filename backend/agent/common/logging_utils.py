import json
from datetime import datetime
from typing import Any

from ...utils import get_fault_logger, get_fault_trace_logger

logger = get_fault_logger()
trace_logger = get_fault_trace_logger()


def truncate_trace_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= 4:
        return "…"
    if isinstance(value, dict):
        items: dict[str, Any] = {}
        for key, item in list(value.items())[:60]:
            items[str(key)] = truncate_trace_value(item, depth=depth + 1)
        return items
    if isinstance(value, list):
        return [truncate_trace_value(item, depth=depth + 1) for item in value[:60]]
    if isinstance(value, str):
        if len(value) <= 4000:
            return value
        return f"{value[:4000]}…(truncated,{len(value)} chars)"
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


def append_fault_trace(event: str, payload: dict[str, Any]) -> None:
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": event,
        "payload": truncate_trace_value(payload),
    }
    trace_logger.info(json.dumps(record, ensure_ascii=False))
