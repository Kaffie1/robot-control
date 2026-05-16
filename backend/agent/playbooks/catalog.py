from __future__ import annotations

from typing import Any

import yaml

from .executor import execute_playbook
from .loader import find_playbook_by_id, get_playbook_catalog, load_playbooks
from .matcher import match_playbook_by_title


def list_playbooks() -> list[dict[str, Any]]:
    return load_playbooks()


def build_fault_doc_context_from_playbook(playbook: dict[str, Any] | None) -> str:
    if not isinstance(playbook, dict):
        return ""
    summary = {
        "id": playbook.get("id", ""),
        "title": playbook.get("title", ""),
        "source_path": playbook.get("source_path", ""),
        "rules_source_path": playbook.get("rules_source_path", ""),
        "script": playbook.get("script", []),
        "root": playbook.get("root", {}),
        "success_criteria": playbook.get("success_criteria", []),
        "escalation_notes": playbook.get("escalation_notes", []),
        "execution_notes": playbook.get("execution_notes", []),
    }
    return "相关 playbook：\n" + yaml.safe_dump(summary, allow_unicode=True, sort_keys=False).strip()


def build_fault_doc_context(user_message: str) -> str:
    matched = match_playbook_by_title(user_message)
    return build_fault_doc_context_from_playbook(matched)


def run_scripted_fault_playbook(
    user_message: str,
    tool_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    matched = match_playbook_by_title(user_message)
    if not matched:
        return None
    return execute_playbook(matched, tool_context)


def run_scripted_fault_playbook_by_id(
    playbook_id: str,
    tool_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    matched = find_playbook_by_id(playbook_id)
    if not matched:
        return None
    return execute_playbook(matched, tool_context)
