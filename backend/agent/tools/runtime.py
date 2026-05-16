from __future__ import annotations

import shlex
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

from pydantic import BaseModel

from ...config import DOCKER_COMPOSE_UP_WAIT_SECONDS, MODULE_DEPLOY_NAMES, MODULE_DEPLOY_PROJECT_ROOT
from ...models import ApiError
from ...ros_ops import (
    build_command_output_text,
    ros_list_services,
    ros_list_topics,
    ros_message_definition,
    ros_service_call,
    ros_service_definition_by_type,
    ros_service_info,
    ros_service_type,
    ros_topic_echo,
    ros_topic_info,
    ros_topic_type,
)
from ...services import ensure_client_connected
from ...utils import short_error
from ..common import logger


class RosNameArgs(BaseModel):
    name: str


class RosTypeNameArgs(BaseModel):
    type_name: str


class RosServiceCallArgs(BaseModel):
    name: str
    request: Any | None = None


class PingHostArgs(BaseModel):
    host: str
    count: int = 1
    timeout_seconds: int = 2


class DockerComposeModuleArgs(BaseModel):
    module_name: str
    wait_seconds: int = DOCKER_COMPOSE_UP_WAIT_SECONDS


@dataclass(frozen=True)
class ToolRuntime:
    session: dict[str, Any]
    client: Any
    tool_context: dict[str, Any] | None


@dataclass
class AgentToolDefinition:
    name: str
    description: str
    args_schema: type[BaseModel]
    handler: Callable[[BaseModel, dict[str, Any] | None], dict[str, Any]]


def ensure_tool_session(tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = (tool_context or {}).get("session")
    if not isinstance(session, dict):
        raise ApiError("当前工具调用缺少会话上下文")
    return session


def build_tool_runtime(tool_context: dict[str, Any] | None) -> ToolRuntime:
    session = ensure_tool_session(tool_context)
    client = ensure_client_connected(session)
    return ToolRuntime(session=session, client=client, tool_context=tool_context)


def connected_tool(handler: Callable[[BaseModel, ToolRuntime], dict[str, Any]]) -> Callable[[BaseModel, dict[str, Any] | None], dict[str, Any]]:
    @wraps(handler)
    def wrapper(args: BaseModel, tool_context: dict[str, Any] | None) -> dict[str, Any]:
        runtime = build_tool_runtime(tool_context)
        return handler(args, runtime)

    return wrapper


@connected_tool
def handle_ros_list_topics(_: BaseModel, runtime: ToolRuntime) -> dict[str, Any]:
    return ros_list_topics(runtime.client)


@connected_tool
def handle_ros_list_services(_: BaseModel, runtime: ToolRuntime) -> dict[str, Any]:
    return ros_list_services(runtime.client)


@connected_tool
def handle_ros_topic_info(args: RosNameArgs, runtime: ToolRuntime) -> dict[str, Any]:
    return ros_topic_info(runtime.client, args.name)


@connected_tool
def handle_ros_topic_type(args: RosNameArgs, runtime: ToolRuntime) -> dict[str, Any]:
    return ros_topic_type(runtime.client, args.name)


@connected_tool
def handle_ros_message_definition(args: RosTypeNameArgs, runtime: ToolRuntime) -> dict[str, Any]:
    return ros_message_definition(runtime.client, args.type_name)


@connected_tool
def handle_ros_topic_echo(args: RosNameArgs, runtime: ToolRuntime) -> dict[str, Any]:
    return ros_topic_echo(runtime.client, args.name, timeout=15.0, line_limit=120)


@connected_tool
def handle_ros_service_info(args: RosNameArgs, runtime: ToolRuntime) -> dict[str, Any]:
    return ros_service_info(runtime.client, args.name)


@connected_tool
def handle_ros_service_type(args: RosNameArgs, runtime: ToolRuntime) -> dict[str, Any]:
    return ros_service_type(runtime.client, args.name)


@connected_tool
def handle_ros_service_definition(args: RosTypeNameArgs, runtime: ToolRuntime) -> dict[str, Any]:
    return ros_service_definition_by_type(runtime.client, args.type_name)


@connected_tool
def handle_ros_service_call(args: RosServiceCallArgs, runtime: ToolRuntime) -> dict[str, Any]:
    return ros_service_call(runtime.client, args.name, args.request)


@connected_tool
def handle_ping_host(args: PingHostArgs, runtime: ToolRuntime) -> dict[str, Any]:
    host = str(args.host or "").strip()
    if not host:
        raise ApiError("ping 主机不能为空")
    count = max(int(args.count or 1), 1)
    timeout_seconds = max(int(args.timeout_seconds or 2), 1)
    command = f"ping -c {count} -W {timeout_seconds} {shlex.quote(host)}"
    result = runtime.client.exec_interactive_command(command, timeout=float(timeout_seconds) + 5.0)
    return {
        "host": host,
        "command": command,
        "result": result,
        "output": build_command_output_text(result),
    }


def _resolve_module_project_root(runtime: ToolRuntime, module_name: str) -> tuple[Any, str, str]:
    client = runtime.client
    normalized_module_name = str(module_name or "").strip()
    if normalized_module_name not in MODULE_DEPLOY_NAMES:
        raise ApiError(f"不支持的模块: {normalized_module_name}")
    project_root = client.resolve_remote_path(MODULE_DEPLOY_PROJECT_ROOT)
    if not client.path_exists(project_root) or not client.is_dir_path(project_root):
        raise ApiError(f"机器人项目目录不存在: {project_root}")
    return client, normalized_module_name, project_root


@connected_tool
def handle_docker_compose_down_module(args: DockerComposeModuleArgs, runtime: ToolRuntime) -> dict[str, Any]:
    client, normalized_module_name, project_root = _resolve_module_project_root(runtime, args.module_name)
    command = f"cd {shlex.quote(project_root)} && docker compose down {shlex.quote(normalized_module_name)}"
    result = client.exec_interactive_command(command, timeout=20.0)
    if int(result.get("exit_code") or 0) != 0:
        raise ApiError(f"停止模块服务失败: {short_error(result)}")
    return {
        "module_name": normalized_module_name,
        "project_root": project_root,
        "command": command,
        "result": result,
        "output": build_command_output_text(result),
    }


@connected_tool
def handle_docker_compose_up_module(args: DockerComposeModuleArgs, runtime: ToolRuntime) -> dict[str, Any]:
    client, normalized_module_name, project_root = _resolve_module_project_root(runtime, args.module_name)
    wait_seconds = max(int(args.wait_seconds or 0), 0)
    command = f"cd {shlex.quote(project_root)} && docker compose up -d {shlex.quote(normalized_module_name)}"
    result = client.exec_interactive_command(command, timeout=20.0)
    if int(result.get("exit_code") or 0) != 0:
        raise ApiError(f"启动模块服务失败: {short_error(result)}")
    if wait_seconds:
        logger.info(
            "docker_compose_up_module 等待容器稳定 | module=%s | seconds=%d",
            normalized_module_name,
            wait_seconds,
        )
        time.sleep(wait_seconds)
    return {
        "module_name": normalized_module_name,
        "project_root": project_root,
        "command": command,
        "result": result,
        "output": build_command_output_text(result),
        "wait_seconds": wait_seconds,
    }
