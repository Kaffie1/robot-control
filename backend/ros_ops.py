import json
import re
import shlex
from typing import Any

from .config import ROSBRIDGE_SERVICE_NAME, ROS_COMPOSE_PROJECT_ROOT
from .models import ApiError


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
        if "level=warning" in line and "variable is not set. Defaulting to a blank string." in line:
            continue
        if "level=warning" in line and "project has been loaded without an explicit name from a symlink." in line:
            continue
        cleaned_lines.append(raw_line)
    return "\n".join(cleaned_lines).strip()


def build_command_output_text(result: dict[str, Any]) -> str:
    stdout = strip_compose_warning_lines(str(result.get("stdout") or ""))
    stderr = strip_compose_warning_lines(str(result.get("stderr") or ""))
    parts: list[str] = []
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append(f"[stderr]\n{stderr}")
    return "\n\n".join(parts).strip()


def list_ros_names(output: str) -> list[str]:
    return [line.strip() for line in str(output or "").splitlines() if line.strip()]


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


def format_rosservice_request(request: Any) -> str:
    if request is None:
        return ""
    if isinstance(request, str):
        return request.strip()
    if isinstance(request, (int, float, bool)):
        return str(request).lower() if isinstance(request, bool) else str(request)
    if isinstance(request, dict):
        lines: list[str] = []
        for key, value in request.items():
            if isinstance(value, str):
                rendered_value = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, bool):
                rendered_value = "true" if value else "false"
            else:
                rendered_value = str(value)
            lines.append(f"{key}: {rendered_value}")
        return "\n".join(lines).strip()
    if isinstance(request, list):
        return "\n".join(f"- {item}" for item in request).strip()
    return str(request).strip()


def ros_list_topics(client) -> dict[str, Any]:
    result = run_rosbridge_command(client, "rostopic list")
    return {"items": list_ros_names(result.get("stdout", ""))}


def ros_list_services(client) -> dict[str, Any]:
    result = run_rosbridge_command(client, "rosservice list")
    return {"items": list_ros_names(result.get("stdout", ""))}


def ros_topic_info(client, name: str) -> dict[str, Any]:
    topic_name = normalize_ros_name(name, label="topic 名称")
    result = run_rosbridge_command(client, f"rostopic info {shlex.quote(topic_name)}")
    return {"name": topic_name, "output": build_command_output_text(result)}


def ros_topic_type(client, name: str) -> dict[str, Any]:
    topic_name = normalize_ros_name(name, label="topic 名称")
    result = run_rosbridge_command(client, f"rostopic type {shlex.quote(topic_name)}")
    return {"name": topic_name, "output": build_command_output_text(result)}


def ros_message_definition(client, type_name: str) -> dict[str, Any]:
    normalized_type_name = normalize_ros_type_name(type_name)
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


def ros_topic_echo(client, name: str, *, timeout: float = 15.0, line_limit: int = 120) -> dict[str, Any]:
    topic_name = normalize_ros_name(name, label="topic 名称")
    command = f"timeout 3s rostopic echo -n 1 {shlex.quote(topic_name)} | head -n {max(int(line_limit), 1)}"
    result = run_rosbridge_command(client, command, timeout=timeout)
    raw_output = build_command_output_text(result)
    return {
        "name": topic_name,
        "output": raw_output,
        "raw_output": raw_output,
    }


def ros_topic_publish(client, name: str, message_type: str, message: str = "") -> dict[str, Any]:
    topic_name = normalize_ros_name(name, label="topic 名称")
    normalized_message_type = normalize_ros_type_name(message_type)
    normalized_message = str(message or "").strip()
    command = f"rostopic pub -1 {shlex.quote(topic_name)} {shlex.quote(normalized_message_type)}"
    if normalized_message:
        command = f"{command} {shlex.quote(normalized_message)}"
    result = run_rosbridge_command(client, command, timeout=12.0)
    return {"name": topic_name, "output": build_command_output_text(result)}


def ros_service_info(client, name: str) -> dict[str, Any]:
    service_name = normalize_ros_name(name, label="service 名称")
    result = run_rosbridge_command(client, f"rosservice info {shlex.quote(service_name)}")
    return {"name": service_name, "output": build_command_output_text(result)}


def ros_service_type(client, name: str) -> dict[str, Any]:
    service_name = normalize_ros_name(name, label="service 名称")
    result = run_rosbridge_command(client, f"rosservice type {shlex.quote(service_name)}")
    return {"name": service_name, "output": build_command_output_text(result)}


def ros_service_definition_by_type(client, type_name: str) -> dict[str, Any]:
    normalized_type_name = normalize_ros_type_name(type_name)
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


def ros_service_definition_by_name(client, name: str) -> dict[str, Any]:
    service_name = normalize_ros_name(name, label="service 名称")
    type_payload = ros_service_type(client, service_name)
    normalized_type_name = normalize_ros_type_name(
        str(type_payload.get("output") or "").splitlines()[0] if str(type_payload.get("output") or "").strip() else ""
    )
    definition_payload = ros_service_definition_by_type(client, normalized_type_name)
    return {
        "name": service_name,
        "type_name": str(definition_payload.get("type_name") or normalized_type_name),
        "source_path": str(definition_payload.get("source_path") or ""),
        "output": str(definition_payload.get("output") or ""),
    }


def ros_service_call(client, name: str, request: Any | None = None) -> dict[str, Any]:
    service_name = normalize_ros_name(name, label="service 名称")
    request_text = format_rosservice_request(request)
    command = f"rosservice call {shlex.quote(service_name)}"
    if request_text:
        command = f"{command} {shlex.quote(request_text)}"
    result = run_rosbridge_command(client, command, timeout=12.0)
    return {
        "name": service_name,
        "request": request_text,
        "output": build_command_output_text(result),
    }
