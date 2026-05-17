"""Shared application exceptions."""

from typing import Any


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 400, payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}
