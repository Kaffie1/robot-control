"""Minimal config for agent-only mode."""

import os
from pathlib import Path

def load_env_file(env_path: str | Path) -> None:
    path = Path(env_path)
    if not path.exists() or not path.is_file():
        return
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            continue
        normalized_value = value.strip()
        if len(normalized_value) >= 2 and normalized_value[0] == normalized_value[-1] and normalized_value[0] in {"'", '"'}:
            normalized_value = normalized_value[1:-1]
        os.environ.setdefault(normalized_key, normalized_value)


BASE_DIR = Path(__file__).resolve().parent.parent
load_env_file(BASE_DIR / ".env")

# Agent/Playbook paths
FAULT_PLAYBOOKS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "fault_playbooks")
FAULT_PLAYBOOK_RULES_FILENAME = "rules.yaml"

# OpenAI model
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
OPENAI_CHAT_TEMPERATURE = float(os.getenv("OPENAI_CHAT_TEMPERATURE", "0.0"))
OPENAI_ENABLE_REASONING_SPLIT = os.getenv("OPENAI_ENABLE_REASONING_SPLIT", "false").lower() == "true"
OPENAI_THINK = os.getenv("OPENAI_THINK", "false").lower() == "true"

# App settings
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
