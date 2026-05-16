from __future__ import annotations

import re
from typing import Any

from .loader import load_playbooks


def normalize_match_text(value: str) -> str:
    return re.sub(r"[\s\W_]+", "", str(value or "").strip().lower())


def playbook_matches(user_message: str, playbook: dict[str, Any]) -> bool:
    normalized_message = normalize_match_text(user_message)
    if not normalized_message:
        return False
    title = normalize_match_text(str(playbook.get("title") or ""))
    return bool(title and (title in normalized_message or normalized_message in title))


def match_playbook_by_title(user_message: str) -> dict[str, Any] | None:
    for playbook in load_playbooks():
        if playbook_matches(user_message, playbook):
            return playbook
    return None
