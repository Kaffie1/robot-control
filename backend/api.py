import json
import io
import os
import posixpath
import re
import shlex
import threading
import traceback
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import (
    DEPLOY_CONFIG_PATH,
    MAX_TASK_ITEMS,
    MODULE_DEPLOY_ROOT,
    ROSBRIDGE_SERVICE_NAME,
    ROS_COMPOSE_PROJECT_ROOT,
    SESSION_CLEANUP_INTERVAL_SECONDS,
    SESSION_COOKIE,
    SESSION_IDLE_TIMEOUT_SECONDS,
    STATIC_DIR,
)
from .models import ApiError, ConnectPayload, ConnectionConfig, ExecutePayload, InstallDebPayload, RosServiceCallPayload, RosTopicPublishPayload
from .runtime import connection_cache_store, deploy_config_store, history_store, session_store, task_manager, templates, upload_progress_manager
from .services import (
    build_file_replace_history,
    create_package_target_client,
    create_deploy_runner,
    create_history_rollback_runner,
    create_module_deploy_runner,
    ensure_client_connected,
    refresh_remote_shortcuts,
    resolve_deploy_target,
)
from .utils import get_asset_version, parse_bool, prepare_package_bytes, render_remote_command, require_text, require_upload, resolve_download_source_path


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop_event = threading.Event()

    def cleanup_loop() -> None:
        while not stop_event.wait(SESSION_CLEANUP_INTERVAL_SECONDS):
            session_store.cleanup_expired(SESSION_IDLE_TIMEOUT_SECONDS)

    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()
    try:
        yield
    finally:
        stop_event.set()
        cleanup_thread.join(timeout=1)
        session_store.close_all()


def create_app() -> FastAPI:
    app = FastAPI(title="Robot Upgrade Console", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    gz_log_name_pattern = re.compile(
        r"^(?P<stamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:-\d{1,6})?)\..*\.gz$",
        re.IGNORECASE,
    )

    def resolve_log_filter_timestamp(entry: dict[str, Any]) -> int:
        name = str(entry.get("name") or "").strip()
        if name.lower().endswith(".gz"):
            match = gz_log_name_pattern.match(name)
            if match:
                stamp = match.group("stamp")
                for fmt in ("%Y-%m-%d_%H-%M-%S-%f", "%Y-%m-%d_%H-%M-%S"):
                    try:
                        return int(datetime.strptime(stamp, fmt).timestamp())
                    except ValueError:
                        continue
        created_at = int(entry.get("created_at") or 0)
        if created_at <= 0:
            raise ApiError(f"日志文件缺少可用创建时间，无法筛选: {str(entry.get('path') or name).strip()}")
        return created_at

    def collect_log_files(
        *,
        client,
        root: str,
        module_names: str,
        start_at: str,
        end_at: str,
    ) -> tuple[str, set[str], list[dict[str, Any]]]:
        resolved_root = client.resolve_remote_path(root)
        files = client.list_files_recursive(resolved_root, require_birth_time=False)
        selected_modules = {
            item.strip()
            for item in str(module_names or "").split(",")
            if item.strip()
        }
        if selected_modules:
            files = [
                entry
                for entry in files
                if str(entry.get("relative_path") or "").split("/", 1)[0] in selected_modules
            ]
        start_ts = None
        end_ts = None
        if str(start_at or "").strip():
            start_ts = int(datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S").timestamp())
        if str(end_at or "").strip():
            end_ts = int(datetime.strptime(end_at, "%Y-%m-%d %H:%M:%S").timestamp())
        for entry in files:
            entry["filter_timestamp"] = resolve_log_filter_timestamp(entry)
        if start_ts is not None:
            files = [entry for entry in files if int(entry.get("filter_timestamp") or 0) >= start_ts]
        if end_ts is not None:
            files = [entry for entry in files if int(entry.get("filter_timestamp") or 0) <= end_ts]
        return resolved_root, selected_modules, files

    def build_log_archive_name(device_type: str, start_at: str, end_at: str) -> str:
        prefix = str(device_type or "log").strip().lower() or "log"
        start_label = datetime.strptime(start_at, "%Y-%m-%d %H:%M:%S").strftime("%m%d%H%M")
        end_label = datetime.strptime(end_at, "%Y-%m-%d %H:%M:%S").strftime("%m%d%H%M")
        return f"{prefix}-{start_label}-{end_label}.zip"

    def parse_machine_options_from_output(output: str) -> list[dict[str, str]]:
        normalized = str(output or "").replace("\r", "\n")
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            candidates = [str(item or "").strip() for item in parsed if str(item or "").strip()]
        else:
            candidates = [
                item.strip().strip("[]\"'")
                for chunk in normalized.splitlines()
                for item in chunk.split(",")
                if item.strip().strip("[]\"'")
            ]
        seen: set[str] = set()
        options: list[dict[str, str]] = []
        for item in candidates:
            if item in seen:
                continue
            seen.add(item)
            options.append({"value": item, "label": item})
        if options:
            return options
        return [
            {"value": "WA1", "label": "WA1"},
            {"value": "WA2", "label": "WA2"},
            {"value": "I2", "label": "I2"},
        ]

    ros_name_pattern = re.compile(r"^/?[A-Za-z0-9_~/.-]+(?:/[A-Za-z0-9_~/.-]+)*$")
    ros_type_pattern = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:/[A-Za-z][A-Za-z0-9_]*)+$")

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

    def list_ros_names(output: str) -> list[str]:
        return [line.strip() for line in str(output or "").splitlines() if line.strip()]

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

    @app.middleware("http")
    async def attach_session(request: Request, call_next):
        sid = request.cookies.get(SESSION_COOKIE)
        sid, session, is_new = session_store.get_or_create(sid)
        session_store.touch(sid)
        request.state.session_id = sid
        request.state.session = session
        response = await call_next(request)
        if is_new:
            response.set_cookie(SESSION_COOKIE, sid, path="/", httponly=True, samesite="lax")
        return response

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError):
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.message, **exc.payload})
        return PlainTextResponse(exc.message, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        message = errors[0].get("msg", "请求参数无效") if errors else "请求参数无效"
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=400, content={"ok": False, "error": message})
        return PlainTextResponse(message, status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": str(exc.detail)})
        return PlainTextResponse(str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        traceback.print_exc()
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
        return PlainTextResponse(str(exc), status_code=500)

    def get_session(request: Request) -> dict[str, Any]:
        return request.state.session

    def get_session_id(request: Request) -> str:
        return str(request.state.session_id or "")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        session = get_session(request)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "request": request,
                "defaults": session["last_config"],
                "connected": session["client"].connected,
                "saved_connections": connection_cache_store.list_entries(),
                "package_machine_options": deploy_config_store.get_machine_options("package"),
                "module_machine_options": deploy_config_store.get_machine_options("module"),
                "asset_version": get_asset_version(),
            },
        )

    @app.get("/api/status")
    def api_status(request: Request):
        session = get_session(request)
        if session["client"].connected and not session.get("remote_shortcuts"):
            refresh_remote_shortcuts(session)
        return {
            "ok": True,
            "connected": session["client"].connected,
            "last_config": session["last_config"],
            "last_remote_deb_path": session["last_remote_deb_path"],
            "remote_shortcuts": session.get("remote_shortcuts", []),
            "preferred_root": session.get("preferred_root", "/"),
            "saved_connections": connection_cache_store.list_entries(),
            "package_machine_options": deploy_config_store.get_machine_options("package"),
            "module_machine_options": deploy_config_store.get_machine_options("module"),
        }

    @app.post("/api/connect")
    def api_connect(payload: ConnectPayload, request: Request):
        session = get_session(request)
        host = require_text(payload.host, "主机不能为空")
        username = require_text(payload.username, "用户名不能为空")
        password = str(payload.password or "")
        pico_host = str(payload.pico_host or "").strip()
        pico_username = str(payload.pico_username or "").strip()
        pico_password = str(payload.pico_password or "")
        if not password:
            raise ApiError("请填写密码")
        config = ConnectionConfig(host=host, port=int(payload.port), username=username, password=password)
        session["client"].connect(config)
        session["last_config"] = {
            "host": host,
            "port": int(payload.port),
            "username": username,
            "pico_host": pico_host,
            "pico_port": int(payload.pico_port),
            "pico_username": pico_username,
        }
        session["ssh_auth"] = {"username": username, "password": password}
        session["processor_auth"] = {
            "ORIN": {"host": host, "port": int(payload.port), "username": username, "password": password},
            "PICO": {"host": pico_host, "port": int(payload.pico_port), "username": pico_username, "password": pico_password},
        }
        saved_connections = connection_cache_store.remember(
            {
                "host": host,
                "port": int(payload.port),
                "username": username,
                "password": password,
                "pico_host": pico_host,
                "pico_port": int(payload.pico_port),
                "pico_username": pico_username,
                "pico_password": pico_password,
            }
        )
        shortcut_payload = refresh_remote_shortcuts(session)
        return {"ok": True, "message": "连接成功", "remote_shortcuts": shortcut_payload["shortcuts"], "preferred_root": shortcut_payload["preferred_root"], "saved_connections": saved_connections}

    @app.post("/api/disconnect")
    def api_disconnect(request: Request):
        session = get_session(request)
        session["client"].close()
        session["remote_shortcuts"] = []
        session["preferred_root"] = "/"
        session["ssh_auth"] = {"username": str(session["last_config"].get("username") or ""), "password": ""}
        session["processor_auth"] = {
            "ORIN": {
                "host": str(session["last_config"].get("host") or ""),
                "port": int(session["last_config"].get("port") or 22),
                "username": str(session["last_config"].get("username") or ""),
                "password": "",
            },
            "PICO": {
                "host": str(session["last_config"].get("pico_host") or ""),
                "port": int(session["last_config"].get("pico_port") or 22),
                "username": str(session["last_config"].get("pico_username") or ""),
                "password": "",
            },
        }
        return {"ok": True, "message": "已断开连接"}

    @app.get("/api/connection-cache")
    def api_connection_cache():
        return {"ok": True, "saved_connections": connection_cache_store.list_entries()}

    @app.post("/api/connection-cache/clear")
    def api_clear_connection_cache():
        return {"ok": True, "message": "连接缓存已清空", "saved_connections": connection_cache_store.clear()}

    @app.get("/api/remote-shortcuts")
    def api_remote_shortcuts(request: Request):
        shortcut_payload = refresh_remote_shortcuts(get_session(request))
        return {"ok": True, "shortcuts": shortcut_payload["shortcuts"], "preferred_root": shortcut_payload["preferred_root"]}

    @app.get("/api/upload-progress/{upload_token}")
    def api_upload_progress(upload_token: str, request: Request):
        return {"ok": True, "progress": upload_progress_manager.get(upload_token, get_session_id(request))}

    @app.get("/api/ping")
    def api_ping(request: Request):
        return {"ok": True, "session_id": get_session_id(request)}

    @app.get("/api/ros/topics")
    def api_ros_topics(request: Request):
        client = ensure_client_connected(get_session(request))
        result = run_rosbridge_command(client, "rostopic list")
        return {"ok": True, "items": list_ros_names(result.get("stdout", ""))}

    @app.get("/api/ros/services")
    def api_ros_services(request: Request):
        client = ensure_client_connected(get_session(request))
        result = run_rosbridge_command(client, "rosservice list")
        return {"ok": True, "items": list_ros_names(result.get("stdout", ""))}

    @app.get("/api/ros/topic-info")
    def api_ros_topic_info(request: Request, name: str = ""):
        client = ensure_client_connected(get_session(request))
        topic_name = normalize_ros_name(name, label="topic 名称")
        result = run_rosbridge_command(client, f"rostopic info {shlex.quote(topic_name)}")
        return {"ok": True, "name": topic_name, "output": build_command_output_text(result)}

    @app.get("/api/ros/topic-type")
    def api_ros_topic_type(request: Request, name: str = ""):
        client = ensure_client_connected(get_session(request))
        topic_name = normalize_ros_name(name, label="topic 名称")
        result = run_rosbridge_command(client, f"rostopic type {shlex.quote(topic_name)}")
        return {"ok": True, "name": topic_name, "output": build_command_output_text(result)}

    @app.get("/api/ros/message-definition")
    def api_ros_message_definition(request: Request, type_name: str = ""):
        client = ensure_client_connected(get_session(request))
        normalized_type_name = normalize_ros_type_name(type_name)
        try:
            source_payload = read_ros_interface_source(client, normalized_type_name, interface_kind="msg")
            return {
                "ok": True,
                "type_name": str(source_payload.get("type_name") or normalized_type_name),
                "source_path": str(source_payload.get("source_path") or ""),
                "output": str(source_payload.get("output") or ""),
            }
        except Exception:
            result = run_rosbridge_command(client, f"rosmsg show {shlex.quote(normalized_type_name)}")
            return {"ok": True, "type_name": normalized_type_name, "source_path": "", "output": build_command_output_text(result)}

    @app.get("/api/ros/topic-echo")
    def api_ros_topic_echo(request: Request, name: str = ""):
        client = ensure_client_connected(get_session(request))
        topic_name = normalize_ros_name(name, label="topic 名称")
        result = run_rosbridge_command(client, f"timeout 5s rostopic echo -n 1 {shlex.quote(topic_name)}", timeout=8.0)
        return {"ok": True, "name": topic_name, "output": build_command_output_text(result)}

    @app.post("/api/ros/topic-pub")
    def api_ros_topic_pub(payload: RosTopicPublishPayload, request: Request):
        client = ensure_client_connected(get_session(request))
        topic_name = normalize_ros_name(payload.name, label="topic 名称")
        message_type = normalize_ros_type_name(payload.message_type)
        message = str(payload.message or "").strip()
        command = f"rostopic pub -1 {shlex.quote(topic_name)} {shlex.quote(message_type)}"
        if message:
            command = f"{command} {shlex.quote(message)}"
        result = run_rosbridge_command(client, command, timeout=12.0)
        return {"ok": True, "name": topic_name, "output": build_command_output_text(result)}

    @app.get("/api/ros/service-info")
    def api_ros_service_info(request: Request, name: str = ""):
        client = ensure_client_connected(get_session(request))
        service_name = normalize_ros_name(name, label="service 名称")
        result = run_rosbridge_command(client, f"rosservice info {shlex.quote(service_name)}")
        return {"ok": True, "name": service_name, "output": build_command_output_text(result)}

    @app.get("/api/ros/service-type")
    def api_ros_service_type(request: Request, name: str = ""):
        client = ensure_client_connected(get_session(request))
        service_name = normalize_ros_name(name, label="service 名称")
        result = run_rosbridge_command(client, f"rosservice type {shlex.quote(service_name)}")
        return {"ok": True, "name": service_name, "output": build_command_output_text(result)}

    @app.get("/api/ros/service-definition")
    def api_ros_service_definition(request: Request, name: str = ""):
        client = ensure_client_connected(get_session(request))
        service_name = normalize_ros_name(name, label="service 名称")
        type_result = run_rosbridge_command(client, f"rosservice type {shlex.quote(service_name)}")
        normalized_type_name = normalize_ros_type_name(build_command_output_text(type_result).splitlines()[0] if build_command_output_text(type_result) else "")
        try:
            source_payload = read_ros_interface_source(client, normalized_type_name, interface_kind="srv")
            return {
                "ok": True,
                "name": service_name,
                "type_name": str(source_payload.get("type_name") or normalized_type_name),
                "source_path": str(source_payload.get("source_path") or ""),
                "output": str(source_payload.get("output") or ""),
            }
        except Exception:
            definition_result = run_rosbridge_command(client, f"rossrv show {shlex.quote(normalized_type_name)}")
            return {
                "ok": True,
                "name": service_name,
                "type_name": normalized_type_name,
                "source_path": "",
                "output": build_command_output_text(definition_result),
            }

    @app.post("/api/ros/service-call")
    def api_ros_service_call(payload: RosServiceCallPayload, request: Request):
        client = ensure_client_connected(get_session(request))
        service_name = normalize_ros_name(payload.name, label="service 名称")
        request_text = str(payload.request or "").strip()
        command = f"rosservice call {shlex.quote(service_name)}"
        if request_text:
            command = f"{command} {shlex.quote(request_text)}"
        result = run_rosbridge_command(client, command, timeout=12.0)
        return {"ok": True, "name": service_name, "output": build_command_output_text(result)}

    @app.get("/api/deploy-target")
    def api_deploy_target(request: Request, file_name: str = "", machine_type: str = "", device_type: str = "ORIN"):
        session = get_session(request)
        client, should_close_target_client, _ = create_package_target_client(
            session,
            device_type,
        )
        try:
            resolved_remote_dir, normalized_file_name, remote_path = resolve_deploy_target(client, file_name)
            return {"ok": True, "remote_dir": resolved_remote_dir, "file_name": normalized_file_name, "remote_path": remote_path, "exists": client.path_exists(remote_path)}
        finally:
            if should_close_target_client:
                client.close()

    @app.post("/api/deploy")
    def api_deploy(request: Request, machine_type: str = Form(""), device_type: str = Form("ORIN"), file_name: str = Form(""), server_file_path: str = Form(""), replace_existing: str = Form(""), use_existing_remote: str = Form(""), auto_deploy: str = Form(""), upload_token: str = Form(""), deb_file: UploadFile | None = File(None)):
        session = get_session(request)
        session_id = get_session_id(request)
        client, should_close_target_client, target = create_package_target_client(
            session,
            device_type,
        )
        replace_existing_flag = parse_bool(replace_existing)
        use_existing_remote_flag = parse_bool(use_existing_remote)
        auto_deploy_flag = parse_bool(auto_deploy)
        if replace_existing_flag and use_existing_remote_flag:
            raise ApiError("同名文件处理参数冲突")
        try:
            deploy_profile = deploy_config_store.get_profile("package")
            selected_file_name = os.path.basename(file_name or "")
            if str(server_file_path or "").strip():
                selected_file_name = os.path.basename(resolve_download_source_path(server_file_path))
            elif deb_file is not None:
                selected_file_name = os.path.basename(deb_file.filename or "") or selected_file_name
            resolved_remote_dir, selected_file_name, remote_path = resolve_deploy_target(client, selected_file_name)
            remote_exists = client.path_exists(remote_path)
            if auto_deploy_flag and remote_exists and not replace_existing_flag:
                use_existing_remote_flag = True
            if remote_exists and not replace_existing_flag and not use_existing_remote_flag:
                raise ApiError(f"远程已存在同名文件: {remote_path}", status_code=409, payload={"conflict": {"remote_path": remote_path, "file_name": selected_file_name, "remote_dir": resolved_remote_dir}})
            if use_existing_remote_flag and not remote_exists:
                raise ApiError(f"远端不存在可直接安装的文件: {remote_path}")
            if use_existing_remote_flag:
                file_bytes = b""
                source_metadata = {"source_kind": "existing_remote", "source_path": "", "download_path": "", "local_tmp_path": ""}
            else:
                if str(server_file_path or "").strip():
                    download_path = resolve_download_source_path(server_file_path)
                    upload_progress_manager.start(str(upload_token or "").strip(), file_name=os.path.basename(download_path), phase="downloading_from_server", message=f"正在从文件服务器下载: {download_path}", owner_id=session_id)
                selected_file_name, file_bytes, source_metadata = prepare_package_bytes(deb_file, server_file_path, local_error_message="请选择要部署的安装包文件或填写文件服务器包路径")
                if str(server_file_path or "").strip():
                    upload_progress_manager.update(str(upload_token or "").strip(), transferred_bytes=len(file_bytes), total_bytes=len(file_bytes), phase="queued", message="文件已从服务器下载，准备创建部署任务")
                resolved_remote_dir, selected_file_name, remote_path = resolve_deploy_target(client, selected_file_name)
            deploy_profile = deploy_config_store.get_profile("package", machine_type)
            title, metadata, runner = create_deploy_runner(
                session,
                remote_dir=resolved_remote_dir,
                machine_type=str(deploy_profile.get("machine_type") or ""),
                device_type=str(target.get("device_type") or device_type).upper(),
                install_template=deploy_profile["install_template"],
                start_command=deploy_profile["start_command"],
                health_command=deploy_profile["health_command"],
                rollback_template=deploy_profile["rollback_template"],
                auto_rollback=bool(deploy_profile["auto_rollback"]),
                file_name=selected_file_name,
                file_bytes=file_bytes,
                source_metadata=source_metadata,
                skip_upload=use_existing_remote_flag,
                upload_token=str(upload_token or "").strip(),
                owner_id=session_id,
            )
            metadata.update({"deploy_mode": "package", "remote_dir": resolved_remote_dir, "remote_path": remote_path, "deploy_config_path": str(DEPLOY_CONFIG_PATH), "machine_type": str(deploy_profile.get("machine_type") or ""), "device_type": str(target.get("device_type") or device_type).upper(), "target_host": str(target.get("host") or ""), "target_port": int(target.get("port") or 22), "target_username": str(target.get("username") or ""), "used_existing_remote": use_existing_remote_flag, "replaced_existing_remote": bool(remote_exists and replace_existing_flag), "source_kind": str(source_metadata.get("source_kind") or ""), "source_path": str(source_metadata.get("source_path") or ""), "download_path": str(source_metadata.get("download_path") or "")})
            return {"ok": True, "task": task_manager.create_task("deployment", title, metadata, runner, owner_id=session_id)}
        finally:
            if should_close_target_client:
                client.close()

    @app.post("/api/package-upload-probe")
    def api_package_upload_probe(
        request: Request,
        device_type: str = Form("ORIN"),
        file_name: str = Form(""),
        server_file_path: str = Form(""),
        replace_existing: str = Form(""),
        use_existing_remote: str = Form(""),
        upload_token: str = Form(""),
        deb_file: UploadFile | None = File(None),
    ):
        session = get_session(request)
        session_id = get_session_id(request)
        client, should_close_target_client, target = create_package_target_client(
            session,
            device_type,
        )
        replace_existing_flag = parse_bool(replace_existing)
        use_existing_remote_flag = parse_bool(use_existing_remote)
        if replace_existing_flag and use_existing_remote_flag:
            raise ApiError("同名文件处理参数冲突")
        deploy_profile = deploy_config_store.get_profile("package")
        fallback_machine_options = deploy_config_store.get_machine_options("package") or parse_machine_options_from_output("")
        try:
            selected_file_name = os.path.basename(file_name or "")
            if str(server_file_path or "").strip():
                selected_file_name = os.path.basename(resolve_download_source_path(server_file_path))
            elif deb_file is not None:
                selected_file_name = os.path.basename(deb_file.filename or "") or selected_file_name
            resolved_remote_dir, selected_file_name, remote_path = resolve_deploy_target(client, selected_file_name)
            remote_exists = client.path_exists(remote_path)
            if remote_exists and not replace_existing_flag and not use_existing_remote_flag:
                raise ApiError(
                    f"远程已存在同名文件: {remote_path}",
                    status_code=409,
                    payload={"conflict": {"remote_path": remote_path, "file_name": selected_file_name, "remote_dir": resolved_remote_dir}},
                )
            if use_existing_remote_flag and not remote_exists:
                raise ApiError(f"远端不存在可直接识别的文件: {remote_path}")

            if use_existing_remote_flag:
                upload_progress_manager.start(
                    str(upload_token or "").strip(),
                    file_name=selected_file_name,
                    total_bytes=0,
                    phase="completed",
                    message=f"已复用远端安装包: {remote_path}",
                    owner_id=session_id,
                )
                upload_progress_manager.update(
                    str(upload_token or "").strip(),
                    transferred_bytes=0,
                    total_bytes=0,
                    phase="completed",
                    message=f"已复用远端安装包: {remote_path}",
                    done=True,
                    owner_id=session_id,
                )
            else:
                if str(server_file_path or "").strip():
                    download_path = resolve_download_source_path(server_file_path)
                    upload_progress_manager.start(
                        str(upload_token or "").strip(),
                        file_name=os.path.basename(download_path),
                        phase="downloading_from_server",
                        message=f"正在从文件服务器下载: {download_path}",
                        owner_id=session_id,
                    )
                selected_file_name, file_bytes, _ = prepare_package_bytes(
                    deb_file,
                    server_file_path,
                    local_error_message="请选择 firmware 文件或填写文件服务器包路径",
                )
                if str(server_file_path or "").strip():
                    upload_progress_manager.update(
                        str(upload_token or "").strip(),
                        transferred_bytes=len(file_bytes),
                        total_bytes=len(file_bytes),
                        phase="preparing",
                        message="文件已从服务器下载，准备上传并识别机型",
                        owner_id=session_id,
                    )
                resolved_remote_dir, selected_file_name, remote_path = resolve_deploy_target(client, selected_file_name)
                package_prefix = selected_file_name.split("_", 1)[0].strip() or selected_file_name
                removed_files = client.remove_files_by_prefix(resolved_remote_dir, package_prefix)
                for removed_file in removed_files:
                    if removed_file != remote_path:
                        pass
                upload_progress_manager.update(
                    str(upload_token or "").strip(),
                    transferred_bytes=0,
                    total_bytes=len(file_bytes),
                    phase="uploading_to_robot",
                    message=f"正在上传到目标处理器: {remote_path}",
                    owner_id=session_id,
                )
                client.upload_bytes(file_bytes, remote_path, progress_callback=lambda transferred, total: upload_progress_manager.update(
                    str(upload_token or "").strip(),
                    transferred_bytes=transferred,
                    total_bytes=total,
                    phase="uploading_to_robot",
                    message=f"正在上传到目标处理器: {remote_path}",
                    owner_id=session_id,
                ))
                upload_progress_manager.update(
                    str(upload_token or "").strip(),
                    transferred_bytes=len(file_bytes),
                    total_bytes=len(file_bytes),
                    phase="installing",
                    message=f"安装包已上传到机器人，正在识别机型: {remote_path}",
                    done=False,
                    owner_id=session_id,
                )
                session["last_remote_deb_path"] = remote_path

            allowed_values_map = {
                str(option.get("value") or "").strip().upper(): str(option.get("value") or "").strip()
                for option in fallback_machine_options
                if isinstance(option, dict) and str(option.get("value") or "").strip()
            }
            try:
                robot_type_value = str(client.get_interactive_env("ROBOT_TYPE") or "").strip()
            except Exception:
                robot_type_value = ""
            selected_machine_type = ""
            probe_command = render_remote_command(
                str(deploy_profile.get("probe_command_template") or "chmod +x {deb_path} && {deb_path} --get_robot_type"),
                remote_path,
                {
                    "device_type": str(target.get("device_type") or device_type).upper(),
                    "target_username": str(target.get("username") or ""),
                    "target_password": str(target.get("password") or ""),
                },
            )
            probe_result = {"exit_code": 0, "stdout": "", "stderr": ""}
            probe_output = ""
            probe_warning = ""
            if robot_type_value:
                normalized_robot_type = allowed_values_map.get(robot_type_value.upper(), robot_type_value)
                if allowed_values_map and normalized_robot_type.upper() not in allowed_values_map:
                    machine_options = fallback_machine_options
                    probe_warning = f"检测到 ROBOT_TYPE={robot_type_value}，但不在可配置机型范围内，请手动选择机型"
                else:
                    selected_machine_type = normalized_robot_type
                    machine_options = [
                        {
                            "value": normalized_robot_type,
                            "label": normalized_robot_type,
                        }
                    ]
            else:
                probe_result = client.exec_command(probe_command)
                probe_output = "\n".join(
                    part for part in [str(probe_result.get("stdout") or "").strip(), str(probe_result.get("stderr") or "").strip()] if part
                )
                if int(probe_result.get("exit_code") or 0) != 0:
                    machine_options = fallback_machine_options
                    probe_warning = "未读取到 ROBOT_TYPE，且机型识别命令执行失败，请手动选择机型"
                else:
                    parsed_options = parse_machine_options_from_output(probe_output)
                    if allowed_values_map:
                        parsed_options = [
                            option
                            for option in parsed_options
                            if str(option.get("value") or "").strip().upper() in allowed_values_map
                        ]
                    machine_options = parsed_options or fallback_machine_options
                    if not parsed_options:
                        probe_warning = "未读取到 ROBOT_TYPE，请手动选择机型"
            upload_progress_manager.update(
                str(upload_token or "").strip(),
                transferred_bytes=0,
                total_bytes=0,
                phase="completed",
                message="机型识别完成",
                done=True,
                owner_id=session_id,
            )
            return {
                "ok": True,
                "remote_dir": resolved_remote_dir,
                "file_name": selected_file_name,
                "remote_path": remote_path,
                "device_type": str(target.get("device_type") or device_type).upper(),
                "probe_command": probe_command,
                "probe_result": probe_result,
                "machine_options": machine_options,
                "selected_machine_type": selected_machine_type,
                "robot_type": robot_type_value,
                "probe_warning": probe_warning,
            }
        except Exception as exc:
            upload_progress_manager.fail(str(upload_token or "").strip(), f"机型识别失败: {exc}", owner_id=session_id)
            raise
        finally:
            if should_close_target_client:
                client.close()

    @app.post("/api/deploy-module")
    def api_deploy_module(
        request: Request,
        module_name: str = Form(""),
        server_file_path: str = Form(""),
        server_file_paths_json: str = Form(""),
        auto_module_version: str = Form(""),
        auto_deploy: str = Form(""),
        upload_token: str = Form(""),
        deb_file: UploadFile | None = File(None),
    ):
        session = get_session(request)
        session_id = get_session_id(request)
        client = ensure_client_connected(session)
        auto_deploy_flag = parse_bool(auto_deploy)
        selected_module_name = require_text(module_name, "请选择要部署的模块")
        selected_module_path = client.resolve_remote_path(posixpath.join(MODULE_DEPLOY_ROOT, selected_module_name))
        if not client.path_exists(selected_module_path):
            raise ApiError(f"模块目录不存在: {selected_module_path}")
        if not client.is_dir_path(selected_module_path):
            raise ApiError(f"模块路径不是目录: {selected_module_path}")
        package_files: list[dict[str, Any]] = []
        batch_server_paths: list[str] = []
        if str(server_file_paths_json or "").strip():
            try:
                raw_paths = json.loads(server_file_paths_json)
            except json.JSONDecodeError as exc:
                raise ApiError(f"自动部署包路径配置解析失败: {exc}") from exc
            if not isinstance(raw_paths, list):
                raise ApiError("自动部署包路径格式错误，应为数组")
            batch_server_paths = [str(item or "").strip() for item in raw_paths if str(item or "").strip()]
        if batch_server_paths:
            total_download_bytes = 0
            for index, path in enumerate(batch_server_paths, start=1):
                download_path = resolve_download_source_path(path)
                upload_progress_manager.start(
                    str(upload_token or "").strip(),
                    file_name=os.path.basename(download_path),
                    phase="downloading_from_server",
                    message=f"[{index}/{len(batch_server_paths)}] 正在从文件服务器下载: {download_path}",
                    owner_id=session_id,
                )
                package_file_name, package_file_bytes, source_metadata = prepare_package_bytes(
                    None,
                    path,
                    local_error_message="请选择要部署的模块 deb 文件或填写文件服务器包路径",
                )
                total_download_bytes += len(package_file_bytes)
                upload_progress_manager.update(
                    str(upload_token or "").strip(),
                    transferred_bytes=total_download_bytes,
                    total_bytes=total_download_bytes,
                    phase="queued",
                    message=f"[{index}/{len(batch_server_paths)}] 文件已从服务器下载，准备创建模块部署任务",
                )
                package_files.append(
                    {
                        "package_file_name": package_file_name,
                        "package_file_bytes": package_file_bytes,
                        "source_metadata": source_metadata,
                    }
                )
        else:
            if str(server_file_path or "").strip():
                download_path = resolve_download_source_path(server_file_path)
                upload_progress_manager.start(str(upload_token or "").strip(), file_name=os.path.basename(download_path), phase="downloading_from_server", message=f"正在从文件服务器下载: {download_path}", owner_id=session_id)
            package_file_name, package_file_bytes, source_metadata = prepare_package_bytes(deb_file, server_file_path, local_error_message="请选择要部署的模块 deb 文件或填写文件服务器包路径")
            if str(server_file_path or "").strip():
                upload_progress_manager.update(str(upload_token or "").strip(), transferred_bytes=len(package_file_bytes), total_bytes=len(package_file_bytes), phase="queued", message="文件已从服务器下载，准备创建模块部署任务")
            package_files.append(
                {
                    "package_file_name": package_file_name,
                    "package_file_bytes": package_file_bytes,
                    "source_metadata": source_metadata,
                }
            )
        deploy_profile = deploy_config_store.get_profile("module", selected_module_name)
        title, metadata, runner = create_module_deploy_runner(
            session,
            module_name=selected_module_name,
            module_path=selected_module_path,
            package_files=package_files,
            auto_deploy_version=str(auto_module_version or "").strip(),
            upload_token=str(upload_token or "").strip(),
            install_template=deploy_profile["install_template"],
            start_command=deploy_profile["start_command"],
            health_command=deploy_profile["health_command"],
            rollback_template=deploy_profile["rollback_template"],
            auto_rollback=bool(deploy_profile["auto_rollback"]),
            auto_deploy=auto_deploy_flag,
            owner_id=session_id,
        )
        first_package_name = str(package_files[0].get("package_file_name") or "")
        first_source_metadata = package_files[0].get("source_metadata") if isinstance(package_files[0].get("source_metadata"), dict) else {}
        metadata.update(
            {
                "deploy_mode": "module",
                "module_name": selected_module_name,
                "module_path": selected_module_path,
                "package_file_name": first_package_name,
                "package_file_names": [str(item.get("package_file_name") or "") for item in package_files],
                "package_count": len(package_files),
                "auto_deploy": auto_deploy_flag,
                "auto_deploy_version": str(auto_module_version or "").strip(),
                "package_prefix": first_package_name.split("_", 1)[0].strip() if first_package_name else "",
                "remote_path": client.resolve_remote_path(posixpath.join(selected_module_path, first_package_name)) if first_package_name else selected_module_path,
                "remote_paths": [
                    client.resolve_remote_path(posixpath.join(selected_module_path, str(item.get("package_file_name") or "")))
                    for item in package_files
                    if str(item.get("package_file_name") or "").strip()
                ],
                "deploy_config_path": str(DEPLOY_CONFIG_PATH),
                "source_kind": str(first_source_metadata.get("source_kind") or ""),
                "source_path": str(first_source_metadata.get("source_path") or ""),
                "download_path": str(first_source_metadata.get("download_path") or ""),
            }
        )
        return {"ok": True, "task": task_manager.create_task("deployment", title, metadata, runner, owner_id=session_id)}

    @app.get("/api/tasks")
    def api_tasks(request: Request, limit: int = MAX_TASK_ITEMS):
        return {"ok": True, "tasks": task_manager.list_tasks_for_owner(get_session_id(request), limit=limit)}

    @app.get("/api/tasks/{task_id}")
    def api_task_detail(task_id: str, request: Request):
        task = task_manager.get_task_for_owner(task_id, get_session_id(request))
        if not task:
            raise ApiError("任务不存在", status_code=404)
        return {"ok": True, "task": task}

    @app.get("/api/history")
    def api_history(request: Request, limit: int = 20):
        return {"ok": True, "history": history_store.list_entries(limit=limit, owner_id=get_session_id(request))}

    @app.post("/api/history/{entry_id}/rollback")
    def api_history_rollback(entry_id: int, request: Request):
        entry = history_store.get_entry(entry_id, owner_id=get_session_id(request))
        if not entry:
            raise ApiError("历史记录不存在", status_code=404)
        title, runner = create_history_rollback_runner(get_session(request), entry)
        return {"ok": True, "task": task_manager.create_task("rollback", title, {"source_history_id": entry_id, "operation_type": entry["operation_type"]}, runner, owner_id=get_session_id(request))}

    @app.post("/api/upload-deb")
    def api_upload_deb(request: Request, remote_dir: str = Form(...), command_template: str = Form("dpkg -i {deb_path}"), install_after_upload: str | None = Form(None), upload_token: str = Form(""), deb_file: UploadFile | None = File(None)):
        session = get_session(request)
        session_id = get_session_id(request)
        client = ensure_client_connected(session)
        upload = require_upload(deb_file, "请上传 deb 文件")
        remote_dir = require_text(remote_dir, "远程目录不能为空")
        filename = os.path.basename(upload.filename or "package.deb")
        raw_bytes = upload.file.read()
        try:
            upload_progress_manager.start(upload_token, file_name=filename, total_bytes=len(raw_bytes), phase="uploading_to_robot", message="正在上传到机器人", owner_id=session_id)
            remote_path = client.resolve_remote_path(posixpath.join(remote_dir, filename))
            client.upload_bytes(raw_bytes, remote_path, progress_callback=lambda transferred, total: upload_progress_manager.update(upload_token, transferred_bytes=transferred, total_bytes=total, phase="uploading_to_robot", message=f"正在上传到机器人: {remote_path}"))
            session["last_remote_deb_path"] = remote_path
            install_result = None
            install_command = None
            if parse_bool(install_after_upload):
                upload_progress_manager.update(upload_token, transferred_bytes=len(raw_bytes), total_bytes=len(raw_bytes), phase="installing", message="安装包上传完成，正在执行安装命令")
                install_command = render_remote_command(str(command_template or "dpkg -i {deb_path}"), remote_path)
                install_result = client.exec_command(install_command)
            upload_progress_manager.update(upload_token, transferred_bytes=len(raw_bytes), total_bytes=len(raw_bytes), phase="completed", message=f"安装包处理完成: {remote_path}", done=True)
            return {"ok": True, "message": f"deb 已上传到 {remote_path}", "remote_path": remote_path, "install_command": install_command, "install_result": install_result}
        except Exception as exc:  # noqa: BLE001
            upload_progress_manager.fail(upload_token, f"上传失败: {exc}")
            raise

    @app.post("/api/install-deb")
    def api_install_deb(payload: InstallDebPayload, request: Request):
        session = get_session(request)
        remote_path = require_text(payload.remote_path, "远程 deb 路径不能为空")
        command = render_remote_command(str(payload.command_template or "dpkg -i {deb_path}"), remote_path)
        result = ensure_client_connected(session).exec_command(command)
        session["last_remote_deb_path"] = remote_path
        return {"ok": True, "command": command, "result": result}

    @app.post("/api/execute")
    def api_execute(payload: ExecutePayload, request: Request):
        client = ensure_client_connected(get_session(request))
        command = require_text(payload.command, "命令不能为空")
        if payload.interactive:
            result = client.exec_interactive_command(command)
        else:
            result = client.exec_command(command)
        return {"ok": True, "result": result}

    @app.get("/api/list-dir")
    def api_list_dir(request: Request, path: str = "/", device_type: str = "ORIN"):
        session = get_session(request)
        client, should_close_target_client, target = create_package_target_client(session, device_type)
        try:
            resolved_path = client.resolve_remote_path(path)
            return {
                "ok": True,
                "entries": client.list_dir(resolved_path),
                "resolved_path": resolved_path,
                "device_type": str(target.get("device_type") or device_type).upper(),
            }
        finally:
            if should_close_target_client:
                client.close()

    @app.get("/api/download-log-archive")
    def api_download_log_archive(
        request: Request,
        device_type: str = "ORIN",
        module_names: str = "",
        start_at: str = "",
        end_at: str = "",
        root: str = "/home/naviai/navi_project/logs",
    ):
        session = get_session(request)
        client, should_close_target_client, target = create_package_target_client(session, device_type)
        try:
            resolved_root, selected_modules, files = collect_log_files(
                client=client,
                root=root,
                module_names=module_names,
                start_at=start_at,
                end_at=end_at,
            )
            if not files:
                raise ApiError("当前筛选条件下没有可打包的日志文件", status_code=404)

            archive_name = build_log_archive_name(str(target.get("device_type") or device_type).upper(), start_at, end_at)
            archive_stream = io.BytesIO()
            with zipfile.ZipFile(archive_stream, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                for entry in files:
                    remote_path = str(entry.get("path") or "").strip()
                    relative_path = str(entry.get("relative_path") or os.path.basename(remote_path) or "log.txt").strip()
                    if not remote_path or not relative_path:
                        continue
                    archive.writestr(relative_path, client.read_file_bytes(remote_path))

                manifest_lines = [
                    f"device_type: {str(target.get('device_type') or device_type).upper()}",
                    f"resolved_root: {resolved_root}",
                    f"module_names: {', '.join(sorted(selected_modules)) if selected_modules else 'ALL'}",
                    f"start_at: {str(start_at or '').strip() or '-'}",
                    f"end_at: {str(end_at or '').strip() or '-'}",
                    f"file_count: {len(files)}",
                    "",
                    "files:",
                ]
                manifest_lines.extend(f"- {str(entry.get('relative_path') or entry.get('path') or '').strip()}" for entry in files)
                archive.writestr("_manifest.txt", "\n".join(manifest_lines).strip() + "\n")

            archive_stream.seek(0)
            headers = {"Content-Disposition": f'attachment; filename="{archive_name}"'}
            return StreamingResponse(archive_stream, media_type="application/zip", headers=headers)
        finally:
            if should_close_target_client:
                client.close()

    @app.get("/api/scan-paths")
    def api_scan_paths(request: Request, root: str = "/", keyword: str = ""):
        session = get_session(request)
        client = ensure_client_connected(session)
        resolved_root = client.resolve_remote_path(root)
        entries = client.walk_entries(resolved_root)
        all_paths = [resolved_root, *[entry["path"] for entry in entries]]
        all_directories = [resolved_root, *[entry["path"] for entry in entries if entry["is_dir"]]]
        session["path_cache"] = all_paths
        normalized_keyword = keyword.strip().lower()
        if normalized_keyword:
            paths = [item for item in all_paths if normalized_keyword in item.lower()]
            directories = [item for item in all_directories if normalized_keyword in item.lower()]
        else:
            paths = all_paths
            directories = all_directories
        return {"ok": True, "count": len(paths), "paths": paths, "directories": directories, "resolved_root": resolved_root}

    @app.post("/api/replace-file")
    def api_replace_file(request: Request, remote_path: str = Form(...), backup_before_replace: str | None = Form(None), upload_token: str = Form(""), replace_file: UploadFile | None = File(None)):
        session = get_session(request)
        session_id = get_session_id(request)
        client = ensure_client_connected(session)
        upload = require_upload(replace_file, "请上传要替换的本地文件")
        target_path = client.resolve_remote_path(require_text(remote_path, "目标远程文件不能为空"))
        raw_bytes = upload.file.read()
        try:
            upload_progress_manager.start(upload_token, file_name=os.path.basename(upload.filename or target_path), total_bytes=len(raw_bytes), phase="preparing", message="正在准备替换远程文件", owner_id=session_id)
            backup_path = None
            if parse_bool(backup_before_replace):
                upload_progress_manager.update(upload_token, phase="backing_up", message="正在备份远端文件")
                backup_path = client.backup_remote_path(target_path)
            client.upload_bytes(raw_bytes, target_path, progress_callback=lambda transferred, total: upload_progress_manager.update(upload_token, transferred_bytes=transferred, total_bytes=total, phase="uploading_to_robot", message=f"正在上传到机器人: {target_path}"))
            upload_progress_manager.update(upload_token, transferred_bytes=len(raw_bytes), total_bytes=len(raw_bytes), phase="completed", message=f"文件已上传并替换: {target_path}", done=True)
            history_id = build_file_replace_history(session, target_path, backup_path, {"remote_path": target_path, "backup_path": backup_path or ""})
            return {"ok": True, "message": f"已替换远程文件 {target_path}", "backup_path": backup_path, "history_id": history_id}
        except Exception as exc:  # noqa: BLE001
            upload_progress_manager.fail(upload_token, f"替换失败: {exc}")
            raise

    return app
