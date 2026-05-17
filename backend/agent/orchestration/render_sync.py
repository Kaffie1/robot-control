from __future__ import annotations

import threading
import time
import uuid

_LOCK = threading.RLock()
_PENDING: dict[str, dict[str, float | bool | str]] = {}
_WAITERS: dict[str, threading.Event] = {}
_TOKEN_TTL_SECONDS = 300.0


def _now() -> float:
    return time.time()


def _cleanup_expired() -> None:
    threshold = _now() - _TOKEN_TTL_SECONDS
    expired = [
        token
        for token, payload in _PENDING.items()
        if float(payload.get("created_at") or 0.0) < threshold
    ]
    for token in expired:
        _PENDING.pop(token, None)
        _WAITERS.pop(token, None)


def create_render_token(*, playbook_id: str) -> str:
    with _LOCK:
        _cleanup_expired()
        token = uuid.uuid4().hex
        _PENDING[token] = {
            "playbook_id": playbook_id,
            "created_at": _now(),
            "ready": False,
        }
        _WAITERS[token] = threading.Event()
        return token


def mark_render_ready(token: str) -> bool:
    normalized = str(token or "").strip()
    if not normalized:
        return False
    with _LOCK:
        _cleanup_expired()
        payload = _PENDING.get(normalized)
        waiter = _WAITERS.get(normalized)
        if not isinstance(payload, dict) or waiter is None:
            return False
        payload["ready"] = True
        waiter.set()
        return True


def wait_for_render_ready(token: str, *, timeout_seconds: float = 1.2) -> bool:
    normalized = str(token or "").strip()
    if not normalized:
        return True
    with _LOCK:
        _cleanup_expired()
        payload = _PENDING.get(normalized)
        waiter = _WAITERS.get(normalized)
        if not isinstance(payload, dict) or waiter is None:
            return True
        if bool(payload.get("ready")):
            return True
    return waiter.wait(timeout=max(float(timeout_seconds), 0.0))


def consume_render_token(token: str) -> None:
    normalized = str(token or "").strip()
    if not normalized:
        return
    with _LOCK:
        _PENDING.pop(normalized, None)
        _WAITERS.pop(normalized, None)
