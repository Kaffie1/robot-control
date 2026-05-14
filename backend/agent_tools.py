import json
import re
import shlex
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, Field

from .config import MODULE_DEPLOY_NAMES, ROSBRIDGE_SERVICE_NAME, ROS_COMPOSE_PROJECT_ROOT, MODULE_DEPLOY_PROJECT_ROOT
from .models import ApiError
from .services import create_package_target_client, ensure_client_connected
from .runtime import task_manager


ros_name_pattern = re.compile(r"^/?[A-Za-z0-9_~/.-]+(?:/[A-Za-z0-9_~/.-]+)*$")
ros_type_pattern = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:/[A-Za-z][A-Za-z0-9_]*)+$")
ros_builtin_types = {
    "bool",
    "byte",
    "char",
    "int8",
    "uint8",
    "int16",
    "uint16",
    "int32",
    "uint32",
    "int64",
    "uint64",
    "float32",
    "float64",
    "string",
    "time",
    "duration",
}
READ_ONLY_COMMAND_PREFIXES = (
    "pwd",
    "ls",
    "stat",
    "cat",
    "head",
    "tail",
    "grep",
    "find",
    "du",
    "df",
    "env",
    "printenv",
    "ps",
    "top -b",
    "systemctl status",
    "journalctl",
    "docker ps",
    "docker logs",
    "docker inspect",
    "rostopic",
    "rosservice",
    "rosnode",
    "rosparam",
    "rosmsg",
    "rossrv",
    "echo ",
)
BLOCKED_COMMAND_TOKENS = ("&&", "||", ";", "|", ">", "<", "`", "$(")


class ListRemoteDirectoryArgs(BaseModel):
    path: str = "/"
    device_type: str = "ORIN"


class ReadRemoteFileArgs(BaseModel):
    path: str
    device_type: str = "ORIN"
    max_bytes: int = Field(default=16384, ge=1, le=262144)


class ExecuteRemoteCommandArgs(BaseModel):
    command: str
    interactive: bool = False


class RosNameArgs(BaseModel):
    name: str


class RosTypeNameArgs(BaseModel):
    type_name: str


class RecentTaskLogsArgs(BaseModel):
    limit: int = Field(default=3, ge=1, le=10)


class RestartModuleServiceArgs(BaseModel):
    module_name: str


@dataclass
class AgentToolDefinition:
    name: str
    description: str
    args_schema: type[BaseModel]
    handler: Callable[[BaseModel, dict[str, Any] | None], dict[str, Any]]


def normalize_ros_name(name: str, *, label: str = "ROS 接口名") -> str:
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ApiError(f"{label}不能为空")
    if not ros_name_pattern.fullmatch(normalized_name):
        raise ApiError(f"非法{label}: {normalized_name}")
    return normalized_name


def normalize_ros_type_name(type_name: str) -> str:
    normalized_type_name = str(type_name or "").strip()
    if not normalized_type_name:
        raise ApiError("消息类型不能为空")
    if not ros_type_pattern.fullmatch(normalized_type_name):
        raise ApiError(f"非法消息类型: {normalized_type_name}")
    return normalized_type_name


def strip_compose_warning_lines(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if 'level=warning' in line and 'variable is not set. Defaulting to a blank string.' in line:
            continue
        if 'level=warning' in line and 'project has been loaded without an explicit name from a symlink.' in line:
            continue
        cleaned_lines.append(raw_line)
    return "\n".join(cleaned_lines).strip()


def build_command_output_text(result: dict[str, Any]) -> str:
    stdout = strip_compose_warning_lines(str(result.get("stdout") or ""))
    stderr = strip_compose_warning_lines(str(result.get("stderr") or ""))
    parts = []
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append(f"[stderr]\n{stderr}")
    return "\n\n".join(parts).strip()


def strip_ros_comment(line: str) -> str:
    return str(line or "").split("#", 1)[0].rstrip()


def normalize_ros_field_type(field_type: str) -> str:
    return re.sub(r"\[[^\]]*\]$", "", str(field_type or "").strip())


def resolve_ros_nested_type(field_type: str, current_package: str) -> str:
    normalized_field_type = normalize_ros_field_type(field_type)
    if not normalized_field_type or normalized_field_type in ros_builtin_types:
        return ""
    if "/" in normalized_field_type:
        return normalize_ros_type_name(normalized_field_type)
    if normalized_field_type == "Header":
        return "std_msgs/Header"
    return normalize_ros_type_name(f"{current_package}/{normalized_field_type}")


def split_ros_service_sections(source_text: str) -> list[list[str]]:
    sections: list[list[str]] = [[]]
    for raw_line in str(source_text or "").splitlines():
        if raw_line.strip() == "---":
            sections.append([])
            continue
        sections[-1].append(raw_line)
    return sections


def run_rosbridge_command(client, command: str, *, timeout: float = 20.0) -> dict[str, Any]:
    result = client.exec_compose_service_command(
        ROS_COMPOSE_PROJECT_ROOT,
        ROSBRIDGE_SERVICE_NAME,
        command,
        timeout=timeout,
    )
    exit_code = int(result.get("exit_code") or 0)
    if exit_code != 0:
        stderr = strip_compose_warning_lines(str(result.get("stderr") or ""))
        stdout = str(result.get("stdout") or "").strip()
        raw_stderr = str(result.get("stderr") or "").strip()
        detail = stderr or stdout or raw_stderr or f"退出码 {exit_code}"
        raise ApiError(f"ROS 命令执行失败（service {ROSBRIDGE_SERVICE_NAME}）: {detail}")
    return result


def read_ros_interface_source(
    client,
    type_name: str,
    *,
    interface_kind: str,
    expand_nested: bool = True,
) -> dict[str, Any]:
    normalized_type_name = normalize_ros_type_name(type_name)
    package_name, interface_name = normalized_type_name.split("/", 1)
    extension = "msg" if interface_kind == "msg" else "srv"
    relative_source_path = f"share/{package_name}/{extension}/{interface_name}.{extension}"
    resolve_command = (
        "found=''; "
        f"for candidate in /opt/ros/*/{shlex.quote(relative_source_path)}; do "
        "if [ -f \"$candidate\" ]; then found=\"$candidate\"; break; fi; "
        "done; "
        "if [ -z \"$found\" ]; then exit 1; fi; "
        "printf '%s\\n' \"$found\"; "
        "cat \"$found\""
    )
    result = run_rosbridge_command(client, resolve_command)
    command_output = build_command_output_text(result)
    output_lines = command_output.splitlines()
    source_path = output_lines[0].strip() if output_lines else ""
    raw_output = "\n".join(output_lines[1:]).strip()
    if not source_path or not raw_output:
        raise ApiError(f"未读取到 {interface_kind} 源文件: /opt/ros/*/{relative_source_path}")
    output = raw_output
    if expand_nested:
        if interface_kind == "srv":
            sections = split_ros_service_sections(raw_output)
            expanded_sections = [
                "\n".join(
                    expand_ros_interface_lines(
                        client,
                        normalized_type_name,
                        interface_kind="msg",
                        source_text="\n".join(section_lines),
                    )
                ).rstrip()
                for section_lines in sections
            ]
            output = "\n---\n".join(expanded_sections).rstrip()
        else:
            output = "\n".join(
                expand_ros_interface_lines(
                    client,
                    normalized_type_name,
                    interface_kind=interface_kind,
                    source_text=raw_output,
                )
            ).rstrip()
    return {
        "type_name": normalized_type_name,
        "source_path": source_path,
        "output": output,
        "raw_output": raw_output,
    }


def expand_ros_interface_lines(
    client,
    type_name: str,
    *,
    interface_kind: str,
    source_text: str,
    seen_types: set[str] | None = None,
) -> list[str]:
    normalized_type_name = normalize_ros_type_name(type_name)
    current_package, _ = normalized_type_name.split("/", 1)
    visited = set(seen_types or set())
    visited.add(normalized_type_name)
    expanded_lines: list[str] = []

    for raw_line in str(source_text or "").splitlines():
        line_text = str(raw_line).rstrip()
        code_text = strip_ros_comment(raw_line).strip()
        expanded_lines.append(line_text)
        if not code_text or code_text == "---" or "=" in code_text:
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9_/]*(?:\[[^\]]*\])?)\s+([A-Za-z][A-Za-z0-9_]*)$", code_text)
        if not match:
            continue
        nested_type_name = resolve_ros_nested_type(match.group(1), current_package)
        if not nested_type_name or nested_type_name in visited:
            continue
        nested_source = read_ros_interface_source(
            client,
            nested_type_name,
            interface_kind=interface_kind,
            expand_nested=False,
        )
        nested_lines = expand_ros_interface_lines(
            client,
            nested_type_name,
            interface_kind=interface_kind,
            source_text=str(nested_source.get("raw_output") or ""),
            seen_types=visited | {nested_type_name},
        )
        expanded_lines.extend([f"  {line}" if line else "" for line in nested_lines])
    return expanded_lines


def ensure_tool_session(tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = (tool_context or {}).get("session")
    if not isinstance(session, dict):
        raise ApiError("当前工具调用缺少会话上下文")
    return session


def build_runtime_context(tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    last_config = session.get("last_config") or {}
    return {
        "connected": bool(getattr(session.get("client"), "connected", False)),
        "host": str(last_config.get("host") or ""),
        "port": int(last_config.get("port") or 0) or 22,
        "username": str(last_config.get("username") or ""),
        "preferred_root": str(session.get("preferred_root") or "/"),
        "remote_shortcuts": session.get("remote_shortcuts") or [],
    }


def list_ros_names(output: str) -> list[str]:
    return [line.strip() for line in str(output or "").splitlines() if line.strip()]


def ensure_safe_read_only_command(command: str) -> str:
    normalized_command = str(command or "").strip()
    if not normalized_command:
        raise ApiError("命令不能为空")
    if any(token in normalized_command for token in BLOCKED_COMMAND_TOKENS):
        raise ApiError("仅允许执行单条只读命令，禁止管道、重定向和命令拼接")
    if not normalized_command.startswith(READ_ONLY_COMMAND_PREFIXES):
        raise ApiError(f"当前 agent 只允许执行只读诊断命令: {normalized_command}")
    return normalized_command


def with_target_client(
    session: dict[str, Any],
    device_type: str,
    callback: Callable[[Any, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    client, should_close_target_client, target = create_package_target_client(session, device_type)
    try:
        result = callback(client, target)
        return {
            **result,
            "device_type": str(target.get("device_type") or device_type).upper(),
        }
    finally:
        if should_close_target_client:
            client.close()


def handle_get_connection_status(_: BaseModel, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    return build_runtime_context(tool_context)


def handle_get_recent_task_logs(args: RecentTaskLogsArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    owner_id = str(session.get("session_id") or "")
    limit = max(1, min(int(args.limit or 3), 10))
    tasks = task_manager.list_tasks_for_owner(owner_id, limit=limit)
    items: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task.get("id") or "").strip()
        if not task_id:
            continue
        detail = task_manager.get_task_for_owner(task_id, owner_id) or task
        items.append(
            {
                "id": detail.get("id", task_id),
                "title": detail.get("title", ""),
                "type": detail.get("type", ""),
                "status": detail.get("status", ""),
                "created_at": detail.get("created_at", ""),
                "started_at": detail.get("started_at", ""),
                "finished_at": detail.get("finished_at", ""),
                "error": detail.get("error", ""),
                "result": detail.get("result", {}),
                "logs": detail.get("logs", []),
            }
        )
    return {"owner_id": owner_id, "limit": limit, "items": items}


def handle_list_remote_directory(args: ListRemoteDirectoryArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)

    def run(client, target: dict[str, Any]) -> dict[str, Any]:
        resolved_path = client.resolve_remote_path(args.path)
        return {
            "resolved_path": resolved_path,
            "entries": client.list_dir(resolved_path),
        }

    return with_target_client(session, args.device_type, run)


def handle_read_remote_file(args: ReadRemoteFileArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)

    def run(client, target: dict[str, Any]) -> dict[str, Any]:
        resolved_path = client.resolve_remote_path(args.path)
        raw_bytes = client.read_file_bytes(resolved_path)
        truncated = raw_bytes[: args.max_bytes]
        try:
            content = truncated.decode("utf-8")
        except UnicodeDecodeError:
            content = truncated.decode("utf-8", errors="replace")
        return {
            "resolved_path": resolved_path,
            "size_bytes": len(raw_bytes),
            "returned_bytes": len(truncated),
            "truncated": len(raw_bytes) > len(truncated),
            "content": content,
        }

    return with_target_client(session, args.device_type, run)


def handle_execute_remote_command(args: ExecuteRemoteCommandArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    client = ensure_client_connected(session)
    command = ensure_safe_read_only_command(args.command)
    if args.interactive:
        result = client.exec_interactive_command(command)
    else:
        result = client.exec_command(command)
    return {
        "command": command,
        "interactive": args.interactive,
        "result": result,
        "output": build_command_output_text(result),
    }


def handle_ros_list_topics(_: BaseModel, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    client = ensure_client_connected(session)
    result = run_rosbridge_command(client, "rostopic list")
    return {"items": list_ros_names(result.get("stdout", ""))}


def handle_ros_list_services(_: BaseModel, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    client = ensure_client_connected(session)
    result = run_rosbridge_command(client, "rosservice list")
    return {"items": list_ros_names(result.get("stdout", ""))}


def handle_ros_topic_info(args: RosNameArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    client = ensure_client_connected(session)
    topic_name = normalize_ros_name(args.name, label="topic 名称")
    result = run_rosbridge_command(client, f"rostopic info {shlex.quote(topic_name)}")
    return {"name": topic_name, "output": build_command_output_text(result)}


def handle_ros_topic_type(args: RosNameArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    client = ensure_client_connected(session)
    topic_name = normalize_ros_name(args.name, label="topic 名称")
    result = run_rosbridge_command(client, f"rostopic type {shlex.quote(topic_name)}")
    return {"name": topic_name, "output": build_command_output_text(result)}


def handle_ros_message_definition(args: RosTypeNameArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    client = ensure_client_connected(session)
    normalized_type_name = normalize_ros_type_name(args.type_name)
    try:
        source_payload = read_ros_interface_source(client, normalized_type_name, interface_kind="msg")
        return {
            "type_name": str(source_payload.get("type_name") or normalized_type_name),
            "source_path": str(source_payload.get("source_path") or ""),
            "output": str(source_payload.get("output") or ""),
        }
    except Exception:
        result = run_rosbridge_command(client, f"rosmsg show {shlex.quote(normalized_type_name)}")
        return {"type_name": normalized_type_name, "source_path": "", "output": build_command_output_text(result)}


def handle_ros_topic_echo(args: RosNameArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    client = ensure_client_connected(session)
    topic_name = normalize_ros_name(args.name, label="topic 名称")
    result = run_rosbridge_command(client, f"timeout 3s rostopic echo -n 1 {shlex.quote(topic_name)}", timeout=5.0)
    return {"name": topic_name, "output": build_command_output_text(result)}


def handle_ros_service_info(args: RosNameArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    client = ensure_client_connected(session)
    service_name = normalize_ros_name(args.name, label="service 名称")
    result = run_rosbridge_command(client, f"rosservice info {shlex.quote(service_name)}")
    return {"name": service_name, "output": build_command_output_text(result)}


def handle_ros_service_type(args: RosNameArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    client = ensure_client_connected(session)
    service_name = normalize_ros_name(args.name, label="service 名称")
    result = run_rosbridge_command(client, f"rosservice type {shlex.quote(service_name)}")
    return {"name": service_name, "output": build_command_output_text(result)}


def handle_ros_service_definition(args: RosTypeNameArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    client = ensure_client_connected(session)
    normalized_type_name = normalize_ros_type_name(args.type_name)
    try:
        source_payload = read_ros_interface_source(client, normalized_type_name, interface_kind="srv")
        return {
            "type_name": str(source_payload.get("type_name") or normalized_type_name),
            "source_path": str(source_payload.get("source_path") or ""),
            "output": str(source_payload.get("output") or ""),
        }
    except Exception:
        result = run_rosbridge_command(client, f"rossrv show {shlex.quote(normalized_type_name)}")
        return {"type_name": normalized_type_name, "source_path": "", "output": build_command_output_text(result)}


def handle_restart_module_service(args: RestartModuleServiceArgs, tool_context: dict[str, Any] | None) -> dict[str, Any]:
    session = ensure_tool_session(tool_context)
    client = ensure_client_connected(session)
    normalized_module_name = str(args.module_name or "").strip()
    if normalized_module_name not in MODULE_DEPLOY_NAMES:
        raise ApiError(f"不支持的模块: {normalized_module_name}")
    project_root = client.resolve_remote_path(MODULE_DEPLOY_PROJECT_ROOT)
    if not client.path_exists(project_root) or not client.is_dir_path(project_root):
        raise ApiError(f"机器人项目目录不存在: {project_root}")
    command = f"cd {shlex.quote(project_root)} && docker compose restart {shlex.quote(normalized_module_name)}"
    result = client.exec_command(command)
    if int(result.get("exit_code") or 0) != 0:
        raise ApiError(f"重启模块服务失败: {short_error(result)}")
    return {
        "module_name": normalized_module_name,
        "project_root": project_root,
        "command": command,
        "result": result,
        "output": build_command_output_text(result),
    }


class EmptyArgs(BaseModel):
    pass


class AgentToolRegistry:
    def __init__(self) -> None:
        self._definitions = [
            AgentToolDefinition(
                name="get_connection_status",
                description="查看当前机器人连接状态、登录账号和推荐远程根目录。",
                args_schema=EmptyArgs,
                handler=handle_get_connection_status,
            ),
            AgentToolDefinition(
                name="list_remote_directory",
                description="列出 ORIN 或 PICO 上指定目录下的文件和子目录。",
                args_schema=ListRemoteDirectoryArgs,
                handler=handle_list_remote_directory,
            ),
            AgentToolDefinition(
                name="get_recent_task_logs",
                description="读取当前会话最近任务的执行日志，用于关联故障上下文。",
                args_schema=RecentTaskLogsArgs,
                handler=handle_get_recent_task_logs,
            ),
            AgentToolDefinition(
                name="read_remote_file",
                description="读取 ORIN 或 PICO 上的文本文件内容，自动限制返回字节数。",
                args_schema=ReadRemoteFileArgs,
                handler=handle_read_remote_file,
            ),
            AgentToolDefinition(
                name="execute_remote_command",
                description="在当前已连接机器人上执行单条只读诊断命令，例如 ls、cat、ps、journalctl、docker logs、rostopic。",
                args_schema=ExecuteRemoteCommandArgs,
                handler=handle_execute_remote_command,
            ),
            AgentToolDefinition(
                name="ros_list_topics",
                description="列出当前 ROS 环境中的所有 topic。",
                args_schema=EmptyArgs,
                handler=handle_ros_list_topics,
            ),
            AgentToolDefinition(
                name="ros_list_services",
                description="列出当前 ROS 环境中的所有 service。",
                args_schema=EmptyArgs,
                handler=handle_ros_list_services,
            ),
            AgentToolDefinition(
                name="ros_get_topic_info",
                description="查看指定 topic 的连接信息、发布者和订阅者。",
                args_schema=RosNameArgs,
                handler=handle_ros_topic_info,
            ),
            AgentToolDefinition(
                name="ros_topic_info",
                description="查看指定 topic 的连接信息、发布者和订阅者。",
                args_schema=RosNameArgs,
                handler=handle_ros_topic_info,
            ),
            AgentToolDefinition(
                name="ros_get_topic_type",
                description="查看指定 topic 的消息类型。",
                args_schema=RosNameArgs,
                handler=handle_ros_topic_type,
            ),
            AgentToolDefinition(
                name="ros_topic_type",
                description="查看指定 topic 的消息类型。",
                args_schema=RosNameArgs,
                handler=handle_ros_topic_type,
            ),
            AgentToolDefinition(
                name="ros_get_message_definition",
                description="查看 ROS 消息类型定义，并尽量展开嵌套字段。",
                args_schema=RosTypeNameArgs,
                handler=handle_ros_message_definition,
            ),
            AgentToolDefinition(
                name="ros_message_definition",
                description="查看 ROS 消息类型定义，并尽量展开嵌套字段。",
                args_schema=RosTypeNameArgs,
                handler=handle_ros_message_definition,
            ),
            AgentToolDefinition(
                name="ros_echo_topic_once",
                description="抓取一次 topic 样本消息，用于现场排查。",
                args_schema=RosNameArgs,
                handler=handle_ros_topic_echo,
            ),
            AgentToolDefinition(
                name="ros_topic_echo",
                description="抓取一次 topic 样本消息，用于现场排查。",
                args_schema=RosNameArgs,
                handler=handle_ros_topic_echo,
            ),
            AgentToolDefinition(
                name="ros_get_service_info",
                description="查看指定 service 的连接和节点信息。",
                args_schema=RosNameArgs,
                handler=handle_ros_service_info,
            ),
            AgentToolDefinition(
                name="ros_service_info",
                description="查看指定 service 的连接和节点信息。",
                args_schema=RosNameArgs,
                handler=handle_ros_service_info,
            ),
            AgentToolDefinition(
                name="ros_get_service_type",
                description="查看指定 service 的服务类型。",
                args_schema=RosNameArgs,
                handler=handle_ros_service_type,
            ),
            AgentToolDefinition(
                name="ros_service_type",
                description="查看指定 service 的服务类型。",
                args_schema=RosNameArgs,
                handler=handle_ros_service_type,
            ),
            AgentToolDefinition(
                name="ros_get_service_definition",
                description="查看 ROS 服务类型定义，并尽量展开嵌套字段。",
                args_schema=RosTypeNameArgs,
                handler=handle_ros_service_definition,
            ),
            AgentToolDefinition(
                name="ros_service_definition",
                description="查看 ROS 服务类型定义，并尽量展开嵌套字段。",
                args_schema=RosTypeNameArgs,
                handler=handle_ros_service_definition,
            ),
            AgentToolDefinition(
                name="restart_module_service",
                description="重启单个 docker compose 模块服务。",
                args_schema=RestartModuleServiceArgs,
                handler=handle_restart_module_service,
            ),
        ]
        self._by_name = {item.name: item for item in self._definitions}

    def list_definitions(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for definition in self._definitions:
            items.append(
                {
                    "name": definition.name,
                    "description": definition.description,
                    "input_schema": definition.args_schema.model_json_schema(),
                }
            )
        return items

    def call_tool(self, name: str, arguments: dict[str, Any] | None, tool_context: dict[str, Any] | None = None) -> dict[str, Any]:
        definition = self._by_name.get(str(name or "").strip())
        if definition is None:
            raise ApiError(f"未找到 agent 工具: {name}")
        payload = definition.args_schema.model_validate(arguments or {})
        return definition.handler(payload, tool_context)

    def build_langchain_tools(self, tool_context: dict[str, Any] | None = None) -> list[Any]:
        from langchain_core.tools import StructuredTool

        tools = []
        for definition in self._definitions:
            def make_tool_handler(current_name: str) -> Callable[..., str]:
                def tool_handler(**kwargs: Any) -> str:
                    result = self.call_tool(current_name, kwargs, tool_context)
                    return json.dumps(result, ensure_ascii=False)

                return tool_handler

            tools.append(
                StructuredTool.from_function(
                    func=make_tool_handler(definition.name),
                    name=definition.name,
                    description=definition.description,
                    args_schema=definition.args_schema,
                )
            )
        return tools


agent_tool_registry = AgentToolRegistry()
