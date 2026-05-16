from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ...config import FAULT_PLAYBOOKS_PATH


def read_text_file(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def load_playbooks() -> list[dict[str, Any]]:
    playbooks_root = FAULT_PLAYBOOKS_PATH
    if playbooks_root.is_file():
        playbook_files = [playbooks_root]
    elif playbooks_root.is_dir():
        playbook_files = sorted(playbooks_root.rglob("playbook.yaml"))
    else:
        return []

    playbooks: list[dict[str, Any]] = []
    for playbook_file in playbook_files:
        playbook_text = read_text_file(playbook_file)
        if not playbook_text:
            continue
        try:
            payload = yaml.safe_load(playbook_text)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(payload, dict):
            continue
        if isinstance(payload.get("playbooks"), list):
            for item in payload.get("playbooks") or []:
                if isinstance(item, dict):
                    playbook = dict(item)
                    playbook.setdefault("source_path", str(playbook_file))
                    playbook.setdefault("rules_source_path", str(playbook_file.with_name("rules.yaml")))
                    playbooks.append(playbook)
            continue
        payload.setdefault("source_path", str(playbook_file))
        payload.setdefault("rules_source_path", str(playbook_file.with_name("rules.yaml")))
        playbooks.append(payload)
    return playbooks


def find_playbook_by_id(playbook_id: str) -> dict[str, Any] | None:
    normalized_id = str(playbook_id or "").strip()
    if not normalized_id:
        return None
    for playbook in load_playbooks():
        if str(playbook.get("id") or "").strip() == normalized_id:
            return playbook
    return None


def get_playbook_catalog() -> list[dict[str, str]]:
    catalog: list[dict[str, str]] = []
    for playbook in load_playbooks():
        catalog.append(
            {
                "id": str(playbook.get("id") or "").strip(),
                "title": str(playbook.get("title") or "").strip(),
            }
        )
    return [item for item in catalog if item["id"] and item["title"]]
