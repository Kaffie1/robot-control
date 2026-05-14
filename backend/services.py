import os
import posixpath
import shlex
import tempfile
from pathlib import Path
from typing import Any

from .config import LOCAL_MODULE_DIR, MODULE_DEPLOY_PROJECT_ROOT, PACKAGE_DEPLOY_DIR
from .models import ApiError, ConnectionConfig, TaskFailure
from .robot import RobotClient
from .runtime import history_store, upload_progress_manager
from .stores import TaskContext
from .utils import (
    detect_ignored_package_install_error,
    extract_critical_command_warnings,
    extract_package_prefix,
    log_command_result,
    now_text,
    render_remote_command,
    require_text,
)


def ensure_client_connected(session: dict[str, Any]):
    client = session["client"]
    client.ensure_connected()
    return client


def robot_identity(session: dict[str, Any]) -> dict[str, Any]:
    config = session["last_config"]
    return {
        "robot_host": config.get("host", ""),
        "robot_port": config.get("port"),
        "robot_username": config.get("username", ""),
    }


def current_robot_password(session: dict[str, Any]) -> str:
    processor_auth = session.get("processor_auth") or {}
    orin_auth = processor_auth.get("ORIN") if isinstance(processor_auth, dict) else {}
    if isinstance(orin_auth, dict) and str(orin_auth.get("password") or ""):
        return str(orin_auth.get("password") or "")
    ssh_auth = session.get("ssh_auth") or {}
    if isinstance(ssh_auth, dict):
        return str(ssh_auth.get("password") or "")
    return ""


def ensure_connected_to_history_target(session: dict[str, Any], entry: dict[str, Any]):
    client = ensure_client_connected(session)
    config = session["last_config"]
    if (
        str(config.get("host", "")) != str(entry.get("robot_host", ""))
        or int(config.get("port", 0)) != int(entry.get("robot_port", 0) or 0)
        or str(config.get("username", "")) != str(entry.get("robot_username", ""))
    ):
        raise ApiError("请先连接到该历史记录对应的机器人，再执行回滚")
    return client


def refresh_remote_shortcuts(session: dict[str, Any]) -> dict[str, Any]:
    client = ensure_client_connected(session)
    shortcut_payload = client.directory_shortcuts()
    session["remote_shortcuts"] = shortcut_payload["shortcuts"]
    session["preferred_root"] = shortcut_payload["preferred_root"]
    return shortcut_payload


def build_upload_callback(token: str, remote_path: str):
    def callback(transferred_bytes: int, total_bytes: int) -> None:
        upload_progress_manager.update(
            token,
            transferred_bytes=transferred_bytes,
            total_bytes=total_bytes,
            phase="uploading_to_robot",
            message=f"正在上传到机器人: {remote_path}",
        )

    return callback


def resolve_package_target_credentials(
    session: dict[str, Any],
    device_type: str,
) -> dict[str, Any]:
    normalized_device_type = str(device_type or "ORIN").strip().upper() or "ORIN"
    processor_auth = session.get("processor_auth") or {}
    target_auth = processor_auth.get(normalized_device_type) if isinstance(processor_auth, dict) else {}
    identity = robot_identity(session)
    if not isinstance(target_auth, dict):
        target_auth = {}
    configured_host = str(target_auth.get("host") or "").strip()
    configured_username = str(target_auth.get("username") or "").strip()
    configured_password = str(target_auth.get("password") or "")
    try:
        configured_port = int(target_auth.get("port") or 22)
    except (TypeError, ValueError):
        configured_port = 22
    if normalized_device_type == "ORIN":
        return {
            "device_type": "ORIN",
            "host": configured_host or identity.get("robot_host", ""),
            "port": configured_port or int(identity.get("robot_port") or 22),
            "username": configured_username or str(identity.get("robot_username") or "").strip(),
            "password": configured_password,
            "requires_jump": False,
        }
    if normalized_device_type != "PICO":
        raise ApiError(f"不支持的设备类型: {normalized_device_type}")
    return {
        "device_type": "PICO",
        "host": require_text(configured_host, "请先在 SSH 连接中填写 PICO 主机"),
        "port": configured_port,
        "username": require_text(configured_username, "请先在 SSH 连接中填写 PICO 用户名"),
        "password": configured_password,
        "requires_jump": True,
    }


def create_package_target_client(
    session: dict[str, Any],
    device_type: str,
) -> tuple[RobotClient, bool, dict[str, Any]]:
    base_client = ensure_client_connected(session)
    target = resolve_package_target_credentials(session, device_type)
    if not target["requires_jump"]:
        return base_client, False, target

    jump_client = RobotClient()
    jump_client.connect_via_jump(
        base_client,
        ConnectionConfig(
            host=str(target["host"]),
            port=int(target["port"]),
            username=str(target["username"]),
            password=str(target["password"]),
        ),
    )
    return jump_client, True, target


def create_deploy_runner(
    session: dict[str, Any],
    *,
    remote_dir: str,
    machine_type: str,
    device_type: str,
    install_template: str,
    start_command: str,
    health_command: str,
    rollback_template: str,
    auto_rollback: bool,
    file_name: str,
    file_bytes: bytes,
    source_metadata: dict[str, Any] | None = None,
    skip_upload: bool = False,
    upload_token: str = "",
    owner_id: str = "",
):
    identity = robot_identity(session)
    preview_remote_path = posixpath.join(remote_dir, file_name)
    title = f"整包部署 {file_name}"
    if machine_type:
        title = f"整包部署 [{machine_type}/{device_type}] {file_name}"
    else:
        title = f"整包部署 [{device_type}] {file_name}"

    def runner(ctx: TaskContext) -> dict[str, Any]:
        client, should_close_target_client, target = create_package_target_client(
            session,
            device_type,
        )
        package_prefix = extract_package_prefix(file_name)
        remote_path = client.resolve_remote_path(posixpath.join(remote_dir, file_name))
        warnings: list[str] = []
        summary: dict[str, Any] = {
            "remote_deb_path": remote_path,
            "temp_remote_path": remote_path,
            "package_prefix": package_prefix,
            "removed_files": [],
            "install_command": "",
            "start_command": start_command,
            "health_command": health_command,
            "rollback_command": "",
            "machine_type": machine_type,
            "device_type": str(target.get("device_type") or device_type),
            "target_host": str(target.get("host") or ""),
            "target_port": int(target.get("port") or 22),
            "target_username": str(target.get("username") or ""),
            "upload_skipped": skip_upload,
            "source_metadata": source_metadata or {},
            "warnings": warnings,
        }
        history = {
            **identity,
            "operation_type": "deployment",
            "title": title,
            "remote_deb_path": remote_path,
            "target_path": remote_path,
            "install_command": "",
            "start_command": start_command,
            "health_command": health_command,
            "rollback_command": "",
            "machine_type": machine_type,
            "device_type": str(target.get("device_type") or device_type),
            "upload_skipped": skip_upload,
        }
        ctx.log(f"目标机器人: {identity['robot_username']}@{identity['robot_host']}:{identity['robot_port']}")
        if machine_type:
            ctx.log(f"目标机型: {machine_type}")
        ctx.log(f"目标处理器: {target.get('device_type')} {target.get('username')}@{target.get('host')}:{target.get('port')}")
        upload_progress_manager.start(
            upload_token,
            file_name=file_name,
            total_bytes=len(file_bytes),
            phase="queued",
            message="部署任务已创建，准备处理安装包",
            owner_id=owner_id,
        )
        try:
            try:
                if skip_upload:
                    ctx.log(f"检测到远端同名安装包，跳过上传并直接复用: {remote_path}")
                    if not client.path_exists(remote_path):
                        raise ApiError(f"远端安装包不存在，无法直接安装: {remote_path}")
                    upload_progress_manager.update(upload_token, transferred_bytes=0, total_bytes=0, phase="completed", message=f"已复用远端安装包: {remote_path}", done=True)
                else:
                    if source_metadata and source_metadata.get("source_kind") == "file_server":
                        ctx.log(f"文件服务器路径: {source_metadata.get('source_path')}")
                        ctx.log(f"裁剪后的下载路径: {source_metadata.get('download_path')}")
                        ctx.log(f"已下载到本机临时目录: {source_metadata.get('local_tmp_path')}")
                    ctx.log(f"清理目标目录同前缀旧包: {package_prefix}")
                    removed_files = client.remove_files_by_prefix(remote_dir, package_prefix)
                    summary["removed_files"] = removed_files
                    for removed_file in removed_files:
                        ctx.log(f"已删除旧包: {removed_file}")
                    ctx.log(f"上传安装包到 {remote_path}")
                    upload_progress_manager.update(
                        upload_token,
                        transferred_bytes=0,
                        total_bytes=len(file_bytes),
                        phase="uploading_to_robot",
                        message=f"正在上传到目标处理器: {remote_path}",
                    )
                    client.upload_bytes(file_bytes, remote_path, progress_callback=build_upload_callback(upload_token, remote_path))
                    upload_progress_manager.update(upload_token, transferred_bytes=len(file_bytes), total_bytes=len(file_bytes), phase="completed", message=f"安装包已上传到机器人: {remote_path}", done=True)
                session["last_remote_deb_path"] = remote_path
                if not skip_upload:
                    ctx.log("安装包上传完成")
            except Exception as exc:  # noqa: BLE001
                upload_progress_manager.fail(upload_token, f"上传失败: {exc}")
                raise

            install_command = render_remote_command(
                install_template,
                remote_path,
                {
                    "machine_type": machine_type,
                    "device_type": str(target.get("device_type") or device_type),
                    "target_username": str(target.get("username") or ""),
                    "target_password": str(target.get("password") or ""),
                },
            )
            summary["install_command"] = install_command
            history["install_command"] = install_command
            ctx.log(f"执行安装命令: {install_command}")
            install_result = client.exec_command(install_command)
            summary["install_result"] = install_result
            log_command_result(ctx, "安装命令", install_result)
            if install_result["exit_code"] != 0:
                ignored_error = detect_ignored_package_install_error(install_result)
                if ignored_error:
                    warnings.append(ignored_error)
                    ctx.log(f"告警: {ignored_error}")
                else:
                    raise TaskFailure("安装命令执行失败", {"summary": summary, "history": history})
            install_warnings = extract_critical_command_warnings("安装命令", install_result)
            warnings.extend(install_warnings)
            for warning in install_warnings:
                ctx.log(f"告警: {warning}")
            if start_command:
                ctx.log(f"执行启动命令: {start_command}")
                start_result = client.exec_command(start_command)
                summary["start_result"] = start_result
                log_command_result(ctx, "启动命令", start_result)
                if start_result["exit_code"] != 0:
                    raise TaskFailure("启动命令执行失败", {"summary": summary, "history": history})
            resolved_rollback_command = ""
            if rollback_template:
                resolved_rollback_command = render_remote_command(
                    rollback_template,
                    remote_path,
                    {
                        "machine_type": machine_type,
                        "device_type": str(target.get("device_type") or device_type),
                        "target_username": str(target.get("username") or ""),
                        "target_password": str(target.get("password") or ""),
                    },
                )
                summary["rollback_command"] = resolved_rollback_command
                history["rollback_command"] = resolved_rollback_command
            if health_command:
                ctx.log(f"执行健康检查: {health_command}")
                health_result = client.exec_command(health_command)
                summary["health_result"] = health_result
                log_command_result(ctx, "健康检查", health_result)
                if health_result["exit_code"] != 0:
                    if auto_rollback and resolved_rollback_command:
                        ctx.log(f"健康检查失败，开始自动回滚: {resolved_rollback_command}")
                        rollback_result = client.exec_command(resolved_rollback_command)
                        summary["rollback_result"] = rollback_result
                        log_command_result(ctx, "自动回滚", rollback_result)
                        if rollback_result["exit_code"] != 0:
                            raise TaskFailure("健康检查失败，自动回滚也失败", {"summary": summary, "history": history})
                        ctx.log("执行回滚后的健康检查")
                        rollback_health_result = client.exec_command(health_command)
                        summary["rollback_health_result"] = rollback_health_result
                        log_command_result(ctx, "回滚后健康检查", rollback_health_result)
                        if rollback_health_result["exit_code"] != 0:
                            raise TaskFailure("健康检查失败，自动回滚后健康检查仍失败", {"summary": summary, "history": history})
                        raise TaskFailure("健康检查失败，已自动回滚到可用状态", {"summary": summary, "history": history})
                    raise TaskFailure("健康检查失败", {"summary": summary, "history": history})
            ctx.log("部署任务执行完成")
            return {"summary": summary, "history": history}
        finally:
            if should_close_target_client:
                client.close()

    return title, {"remote_deb_path": preview_remote_path, "file_name": file_name}, runner


def create_module_deploy_runner(
    session: dict[str, Any],
    *,
    module_name: str,
    module_path: str,
    package_files: list[dict[str, Any]],
    auto_deploy_version: str = "",
    upload_token: str,
    install_template: str,
    start_command: str,
    health_command: str,
    rollback_template: str,
    auto_rollback: bool,
    auto_deploy: bool = False,
    owner_id: str = "",
):
    client = ensure_client_connected(session)
    identity = robot_identity(session)
    sudo_password = current_robot_password(session)
    package_file_names = [
        str(item.get("package_file_name") or "").strip()
        for item in package_files
        if str(item.get("package_file_name") or "").strip()
    ]
    package_title = package_file_names[0] if len(package_file_names) == 1 else f"{len(package_file_names)} 个包"
    title = f"模块部署 [{module_name}] {package_title}"

    def extract_compose_service_block(compose_text: str, service_name: str) -> str:
        lines = str(compose_text or "").splitlines()
        in_services = False
        service_start = -1
        service_end = -1
        target_prefix = f"  {service_name}:"
        for index, line in enumerate(lines):
            if not in_services:
                if line.strip() == "services:":
                    in_services = True
                continue
            if line and not line.startswith(" "):
                break
            if service_start < 0:
                if line.startswith(target_prefix):
                    service_start = index
                continue
            if line.startswith("  ") and not line.startswith("    ") and line.strip():
                service_end = index
                break
        if service_start < 0:
            raise ApiError(f"版本 docker-compose.yaml 中未找到模块服务: {service_name}")
        if service_end < 0:
            service_end = len(lines)
        return "\n".join(lines[service_start:service_end]).rstrip() + "\n"

    def merge_compose_service_block(current_text: str, service_name: str, replacement_block: str) -> str:
        lines = str(current_text or "").splitlines()
        if not lines:
            raise ApiError("远端 docker-compose.yaml 为空，无法替换模块片段")
        in_services = False
        services_line = -1
        service_start = -1
        service_end = -1
        target_prefix = f"  {service_name}:"
        for index, line in enumerate(lines):
            if not in_services:
                if line.strip() == "services:":
                    in_services = True
                    services_line = index
                continue
            if line and not line.startswith(" "):
                if service_start >= 0 and service_end < 0:
                    service_end = index
                break
            if service_start < 0:
                if line.startswith(target_prefix):
                    service_start = index
                continue
            if line.startswith("  ") and not line.startswith("    ") and line.strip():
                service_end = index
                break
        if services_line < 0:
            raise ApiError("远端 docker-compose.yaml 缺少 services 段")
        replacement_lines = replacement_block.rstrip("\n").splitlines()
        if service_start >= 0:
            if service_end < 0:
                service_end = len(lines)
            merged_lines = [*lines[:service_start], *replacement_lines, *lines[service_end:]]
            return "\n".join(merged_lines).rstrip() + "\n"
        insert_at = len(lines)
        for index in range(services_line + 1, len(lines)):
            line = lines[index]
            if line and not line.startswith(" "):
                insert_at = index
                break
        merged_lines = [*lines[:insert_at], *replacement_lines, *lines[insert_at:]]
        return "\n".join(merged_lines).rstrip() + "\n"

    def resolve_local_module_assets(version: str) -> dict[str, Path]:
        normalized_version = str(version or "").strip()
        if not normalized_version:
            raise ApiError("自动模块部署缺少版本号")
        version_dir = LOCAL_MODULE_DIR / normalized_version
        if not version_dir.exists() or not version_dir.is_dir():
            raise ApiError(f"本地模块版本目录不存在: {version_dir}")
        module_dir_name = module_name.strip().lower()
        config_dir = version_dir / "config" / module_dir_name
        containers_dir = version_dir / "containers" / module_dir_name
        compose_file = version_dir / "docker-compose.yaml"
        if not compose_file.exists() or not compose_file.is_file():
            raise ApiError(f"版本目录缺少 docker-compose.yaml: {compose_file}")
        if not config_dir.exists() and not containers_dir.exists():
            raise ApiError(f"版本目录中未找到模块 {module_dir_name} 的 config 或 containers 资源")
        return {
            "version_dir": version_dir,
            "config_dir": config_dir,
            "containers_dir": containers_dir,
            "compose_file": compose_file,
            "module_dir_name": Path(module_dir_name),
        }

    def replace_remote_module_assets(ctx: TaskContext, version: str, summary: dict[str, Any]) -> None:
        assets = resolve_local_module_assets(version)
        module_dir_name = str(assets["module_dir_name"])
        project_root = client.resolve_remote_path(MODULE_DEPLOY_PROJECT_ROOT)
        remote_config_root = client.resolve_remote_path(posixpath.join(project_root, "config"))
        remote_containers_root = client.resolve_remote_path(posixpath.join(project_root, "containers"))
        remote_compose_path = client.resolve_remote_path(posixpath.join(project_root, "docker-compose.yaml"))
        remote_config_target = client.resolve_remote_path(posixpath.join(remote_config_root, str(assets["module_dir_name"])))
        remote_containers_target = client.resolve_remote_path(posixpath.join(remote_containers_root, str(assets["module_dir_name"])))
        summary["auto_deploy_version"] = version
        summary["project_root"] = project_root
        summary["replaced_paths"] = []
        summary["local_module_assets"] = {
            "version_dir": str(assets["version_dir"]),
            "config_dir": str(assets["config_dir"]) if assets["config_dir"].exists() else "",
            "containers_dir": str(assets["containers_dir"]) if assets["containers_dir"].exists() else "",
            "compose_file": str(assets["compose_file"]),
        }
        ctx.log(f"自动模块部署版本: {version}")
        ctx.log(f"项目目录: {project_root}")

        if not client.path_exists(project_root) or not client.is_dir_path(project_root):
            raise ApiError(f"机器人项目目录不存在: {project_root}")

        if assets["config_dir"].exists():
            ctx.log(f"替换远端 config 目录: {remote_config_target}")
            client.remove_remote_path(remote_config_target, recursive=True, sudo_password=sudo_password)
            client.upload_local_tree(assets["config_dir"], remote_config_target)
            summary["replaced_paths"].append(remote_config_target)

        if assets["containers_dir"].exists():
            ctx.log(f"替换远端 containers 目录: {remote_containers_target}")
            client.remove_remote_path(remote_containers_target, recursive=True, sudo_password=sudo_password)
            client.upload_local_tree(assets["containers_dir"], remote_containers_target)
            summary["replaced_paths"].append(remote_containers_target)

        with tempfile.NamedTemporaryFile(prefix="docker-compose-", suffix=".yaml", delete=False) as temp_file:
            temp_local_compose = Path(temp_file.name)
        try:
            local_compose_text = assets["compose_file"].read_text(encoding="utf-8")
            local_service_block = extract_compose_service_block(local_compose_text, module_dir_name)
            remote_compose_text = client.read_file_bytes(remote_compose_path).decode("utf-8", errors="replace")
            merged_compose_text = merge_compose_service_block(remote_compose_text, module_dir_name, local_service_block)
            temp_local_compose.write_text(merged_compose_text, encoding="utf-8")
            remote_temp_compose = client.resolve_remote_path(posixpath.join(PACKAGE_DEPLOY_DIR, f"docker-compose.{module_name.lower()}.yaml"))
            ctx.log(f"替换远端 docker-compose 模块片段: {module_dir_name}")
            client.upload_local_file(temp_local_compose, remote_temp_compose)
            client.remove_remote_path(remote_compose_path, sudo_password=sudo_password)
            move_result = client.move_remote_path(remote_temp_compose, remote_compose_path, sudo_password=sudo_password)
            log_command_result(ctx, "替换 docker-compose.yaml", move_result)
            summary["replaced_paths"].append(remote_compose_path)
        finally:
            try:
                temp_local_compose.unlink(missing_ok=True)
            except OSError:
                pass

    def runner(ctx: TaskContext) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "module_name": module_name,
            "module_path": module_path,
            "compose_profiles": "",
            "package_file_name": package_file_names[0] if package_file_names else "",
            "package_files": [],
            "removed_files": [],
            "uploaded_file_paths": [],
            "uploaded_file_path": "",
            "skipped_existing_files": [],
            "install_command": "",
            "start_command": start_command,
            "health_command": health_command,
            "rollback_command": "",
            "auto_deploy_version": auto_deploy_version,
        }
        history = {
            **identity,
            "operation_type": "deployment",
            "title": title,
            "target_path": module_path,
            "remote_deb_path": "",
            "remote_deb_paths": [],
            "install_command": "",
            "start_command": start_command,
            "health_command": health_command,
            "rollback_command": "",
            "module_name": module_name,
            "module_path": module_path,
            "compose_profiles": "",
        }
        ctx.log(f"目标机器人: {identity['robot_username']}@{identity['robot_host']}:{identity['robot_port']}")
        ctx.log(f"目标模块: {module_name}")
        ctx.log(f"模块目录: {module_path}")
        if not client.path_exists(module_path):
            raise ApiError(f"模块目录不存在: {module_path}")
        if not client.is_dir_path(module_path):
            raise ApiError(f"模块路径不是目录: {module_path}")
        compose_profiles = client.get_interactive_env("COMPOSE_PROFILES")
        summary["compose_profiles"] = compose_profiles
        history["compose_profiles"] = compose_profiles
        ctx.log(f"自动读取 COMPOSE_PROFILES: {compose_profiles or '(空)'}")
        if auto_deploy:
            replace_remote_module_assets(ctx, auto_deploy_version, summary)
        total_bytes = sum(len(item.get("package_file_bytes") or b"") for item in package_files)
        upload_progress_manager.start(
            upload_token,
            file_name=package_title,
            total_bytes=total_bytes,
            phase="preparing",
            message="模块部署任务已创建，准备清理旧包",
            owner_id=owner_id,
        )
        transferred_total = 0
        try:
            for package_index, package_item in enumerate(package_files, start=1):
                package_file_name = str(package_item.get("package_file_name") or "").strip()
                package_file_bytes = bytes(package_item.get("package_file_bytes") or b"")
                source_metadata = package_item.get("source_metadata") if isinstance(package_item.get("source_metadata"), dict) else {}
                package_prefix = extract_package_prefix(package_file_name)
                temp_remote_path = client.resolve_remote_path(posixpath.join(PACKAGE_DEPLOY_DIR, package_file_name))
                remote_package_path = client.resolve_remote_path(posixpath.join(module_path, package_file_name))
                if auto_deploy and client.path_exists(remote_package_path):
                    package_summary = {
                        "package_file_name": package_file_name,
                        "package_prefix": package_prefix,
                        "uploaded_file_path": remote_package_path,
                        "removed_files": [],
                        "source_kind": str(source_metadata.get("source_kind") or ""),
                        "source_path": str(source_metadata.get("source_path") or ""),
                        "download_path": str(source_metadata.get("download_path") or ""),
                        "skipped_existing": True,
                    }
                    summary["package_files"].append(package_summary)
                    summary["uploaded_file_paths"].append(remote_package_path)
                    summary["skipped_existing_files"].append(remote_package_path)
                    if not summary["uploaded_file_path"]:
                        summary["uploaded_file_path"] = remote_package_path
                    if not history["remote_deb_path"]:
                        history["remote_deb_path"] = remote_package_path
                    history["remote_deb_paths"].append(remote_package_path)
                    ctx.log(f"[{package_index}/{len(package_files)}] 自动部署检测到同名文件，跳过替换: {remote_package_path}")
                    upload_progress_manager.update(
                        upload_token,
                        transferred_bytes=transferred_total,
                        total_bytes=total_bytes,
                        phase="preparing",
                        message=f"[{package_index}/{len(package_files)}] 检测到同名文件，已跳过替换: {package_file_name}",
                    )
                    continue
                package_summary = {
                    "package_file_name": package_file_name,
                    "package_prefix": package_prefix,
                    "uploaded_file_path": remote_package_path,
                    "removed_files": [],
                    "source_kind": str(source_metadata.get("source_kind") or ""),
                    "source_path": str(source_metadata.get("source_path") or ""),
                    "download_path": str(source_metadata.get("download_path") or ""),
                    "skipped_existing": False,
                }
                summary["package_files"].append(package_summary)
                summary["uploaded_file_paths"].append(remote_package_path)
                if not summary["uploaded_file_path"]:
                    summary["uploaded_file_path"] = remote_package_path
                if not history["remote_deb_path"]:
                    history["remote_deb_path"] = remote_package_path
                history["remote_deb_paths"].append(remote_package_path)
                if source_metadata.get("source_kind") == "file_server":
                    ctx.log(f"[{package_index}/{len(package_files)}] 文件服务器路径: {source_metadata.get('source_path')}")
                    ctx.log(f"[{package_index}/{len(package_files)}] 裁剪后的下载路径: {source_metadata.get('download_path')}")
                    ctx.log(f"[{package_index}/{len(package_files)}] 已下载到本机临时目录: {source_metadata.get('local_tmp_path')}")
                existing_entries = client.list_dir(module_path)
                for entry in existing_entries:
                    if not entry.get("is_dir") and str(entry.get("name") or "").startswith(package_prefix):
                        upload_progress_manager.update(
                            upload_token,
                            transferred_bytes=transferred_total,
                            total_bytes=total_bytes,
                            phase="preparing",
                            message=f"[{package_index}/{len(package_files)}] 正在清理旧包: {entry.get('name')}",
                        )
                removed_files = client.remove_files_by_prefix(module_path, package_prefix)
                package_summary["removed_files"] = removed_files
                summary["removed_files"].extend(removed_files)
                for removed_file in removed_files:
                    ctx.log(f"[{package_index}/{len(package_files)}] 已删除旧包: {removed_file}")
                ctx.log(f"[{package_index}/{len(package_files)}] 上传模块安装包到临时目录: {temp_remote_path}")
                upload_progress_manager.update(
                    upload_token,
                    transferred_bytes=transferred_total,
                    total_bytes=total_bytes,
                    phase="uploading_to_robot",
                    message=f"[{package_index}/{len(package_files)}] 正在上传到机器人: {temp_remote_path}",
                )

                def progress_callback(transferred_bytes: int, _: int) -> None:
                    upload_progress_manager.update(
                        upload_token,
                        transferred_bytes=transferred_total + transferred_bytes,
                        total_bytes=total_bytes,
                        phase="uploading_to_robot",
                        message=f"[{package_index}/{len(package_files)}] 正在上传到机器人: {temp_remote_path}",
                    )

                client.upload_bytes(package_file_bytes, temp_remote_path, progress_callback=progress_callback)
                ctx.log(f"[{package_index}/{len(package_files)}] 移动模块安装包到目标目录: {temp_remote_path} -> {remote_package_path}")
                move_result = client.move_remote_path(temp_remote_path, remote_package_path)
                log_command_result(ctx, f"移动安装包命令 [{package_file_name}]", move_result)
                transferred_total += len(package_file_bytes)
            upload_progress_manager.update(
                upload_token,
                transferred_bytes=transferred_total,
                total_bytes=total_bytes,
                phase="completed",
                message=f"模块安装包已全部上传到机器人，共 {len(package_files)} 个",
                done=True,
            )
        except Exception as exc:  # noqa: BLE001
            upload_progress_manager.fail(upload_token, f"上传失败: {exc}")
            raise
        last_package_file_name = package_file_names[-1]
        last_package_prefix = extract_package_prefix(last_package_file_name)
        install_command = render_remote_command(
            install_template,
            module_path,
            {
                "module_name": module_name,
                "module_path": module_path,
                "compose_profiles": compose_profiles,
                "package_file_name": last_package_file_name,
                "package_prefix": last_package_prefix,
                "package_path": summary["uploaded_file_paths"][-1] if summary["uploaded_file_paths"] else "",
            },
            append_remote_path_if_missing=False,
        )
        summary["install_command"] = install_command
        history["install_command"] = install_command
        ctx.log(f"执行模块安装命令: {install_command}")
        install_result = client.exec_command(install_command)
        summary["install_result"] = install_result
        log_command_result(ctx, "模块安装命令", install_result)
        if install_result["exit_code"] != 0:
            raise TaskFailure("模块安装命令执行失败", {"summary": summary, "history": history})
        if start_command:
            ctx.log(f"执行启动命令: {start_command}")
            start_result = client.exec_command(start_command)
            summary["start_result"] = start_result
            log_command_result(ctx, "启动命令", start_result)
            if start_result["exit_code"] != 0:
                raise TaskFailure("启动命令执行失败", {"summary": summary, "history": history})
        resolved_rollback_command = ""
        if rollback_template:
            resolved_rollback_command = render_remote_command(
                rollback_template,
                module_path,
                {"module_name": module_name, "module_path": module_path},
                append_remote_path_if_missing=False,
            )
            summary["rollback_command"] = resolved_rollback_command
            history["rollback_command"] = resolved_rollback_command
        if health_command:
            ctx.log(f"执行健康检查: {health_command}")
            health_result = client.exec_command(health_command)
            summary["health_result"] = health_result
            log_command_result(ctx, "健康检查", health_result)
            if health_result["exit_code"] != 0:
                if auto_rollback and resolved_rollback_command:
                    ctx.log(f"健康检查失败，开始自动回滚: {resolved_rollback_command}")
                    rollback_result = client.exec_command(resolved_rollback_command)
                    summary["rollback_result"] = rollback_result
                    log_command_result(ctx, "自动回滚", rollback_result)
                    if rollback_result["exit_code"] != 0:
                        raise TaskFailure("健康检查失败，自动回滚也失败", {"summary": summary, "history": history})
                    raise TaskFailure("健康检查失败，已自动回滚到可用状态", {"summary": summary, "history": history})
                raise TaskFailure("健康检查失败", {"summary": summary, "history": history})
        ctx.log("模块部署任务执行完成")
        return {"summary": summary, "history": history}

    return title, {"module_name": module_name, "module_path": module_path}, runner
def create_history_rollback_runner(session: dict[str, Any], entry: dict[str, Any]):
    client = ensure_connected_to_history_target(session, entry)
    identity = {"robot_host": entry["robot_host"], "robot_port": entry["robot_port"], "robot_username": entry["robot_username"]}
    if entry["operation_type"] == "deployment":
        rollback_command = require_text(entry.get("rollback_command"), "该部署记录没有保存回滚命令")
        health_command = str(entry.get("health_command") or "").strip()
        title = f"回滚部署 #{entry['id']}"

        def runner(ctx: TaskContext) -> dict[str, Any]:
            summary = {"source_history_id": entry["id"], "rollback_command": rollback_command, "health_command": health_command}
            history = {**identity, "operation_type": "rollback", "title": title, "remote_deb_path": entry.get("remote_deb_path", ""), "target_path": entry.get("target_path", ""), "rollback_command": rollback_command, "health_command": health_command}
            ctx.log(f"执行部署回滚命令: {rollback_command}")
            command_result = client.exec_command(rollback_command)
            summary["command_result"] = command_result
            log_command_result(ctx, "部署回滚命令", command_result)
            if command_result["exit_code"] != 0:
                raise TaskFailure("部署回滚失败", {"summary": summary, "history": history})
            if health_command:
                ctx.log(f"执行回滚后的健康检查: {health_command}")
                health_result = client.exec_command(health_command)
                summary["health_result"] = health_result
                log_command_result(ctx, "回滚后健康检查", health_result)
                if health_result["exit_code"] != 0:
                    raise TaskFailure("回滚后的健康检查失败", {"summary": summary, "history": history})
            ctx.log("部署回滚完成")
            return {"summary": summary, "history": history}

        return title, runner
    if entry["operation_type"] == "file_replace":
        backup_path = require_text(entry.get("backup_path"), "该文件替换记录没有可用备份")
        target_path = require_text(entry.get("target_path"), "缺少文件目标路径")
        title = f"恢复文件 {posixpath.basename(target_path)}"

        def runner(ctx: TaskContext) -> dict[str, Any]:
            summary = {"source_history_id": entry["id"], "backup_path": backup_path, "target_path": target_path}
            history = {**identity, "operation_type": "rollback", "title": title, "target_path": target_path, "backup_path": backup_path}
            ctx.log(f"恢复远程文件: {backup_path} -> {target_path}")
            command_result = client.restore_backup(backup_path, target_path)
            summary["command_result"] = command_result
            log_command_result(ctx, "恢复文件命令", command_result)
            ctx.log("文件恢复完成")
            return {"summary": summary, "history": history}

        return title, runner
    raise ApiError("该操作类型暂不支持回滚")


def build_file_replace_history(session: dict[str, Any], remote_path: str, backup_path: str | None, result: dict[str, Any]) -> int:
    entry = {
        "owner_id": str(session.get("session_id") or ""),
        **robot_identity(session),
        "operation_type": "file_replace",
        "title": f"替换文件 {posixpath.basename(remote_path)}",
        "target_path": remote_path,
        "backup_path": backup_path or "",
        "status": "succeeded",
        "result": result,
        "logs": [f"目标文件: {remote_path}", f"备份路径: {backup_path or '无'}"],
        "created_at": now_text(),
        "finished_at": now_text(),
    }
    return history_store.insert_entry(entry)


def resolve_deploy_target(client: RobotClient, file_name: str) -> tuple[str, str, str]:
    resolved_remote_dir = client.resolve_remote_path(PACKAGE_DEPLOY_DIR)
    normalized_file_name = os.path.basename(require_text(file_name, "文件名不能为空"))
    if not normalized_file_name:
        raise ApiError("文件名不能为空")
    remote_path = client.resolve_remote_path(posixpath.join(resolved_remote_dir, normalized_file_name))
    return resolved_remote_dir, normalized_file_name, remote_path
