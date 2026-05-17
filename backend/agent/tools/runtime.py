from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel


@dataclass
class AgentToolDefinition:
    name: str
    description: str
    args_schema: type[BaseModel]
    handler: Callable[[BaseModel, dict[str, Any] | None], dict[str, Any]]
