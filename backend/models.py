from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass
class ConnectionConfig:
    host: str
    port: int
    username: str
    password: str = ""
    timeout: int = 10


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 400, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}


class TaskFailure(Exception):
    def __init__(self, message: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


class ConnectPayload(BaseModel):
    host: str
    port: int
    username: str
    password: str = ""
    pico_host: str = ""
    pico_port: int = 22
    pico_username: str = ""
    pico_password: str = ""


class InstallDebPayload(BaseModel):
    remote_path: str
    command_template: str = "dpkg -i {deb_path}"


class ExecutePayload(BaseModel):
    command: str
    interactive: bool = False


class RosTopicPublishPayload(BaseModel):
    name: str
    message_type: str
    message: str = ""


class RosServiceCallPayload(BaseModel):
    name: str
    request: str = ""
class AudioMonitorConfigEntryPayload(BaseModel):
    module: str
    enable: bool


class AudioMonitorConfigSavePayload(BaseModel):
    entries: list[AudioMonitorConfigEntryPayload]
