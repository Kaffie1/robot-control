import posixpath
import re
import shlex
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import paramiko

from .config import PROJECT_ROOT_CANDIDATES, UPLOAD_CHUNK_SIZE
from .models import ApiError, ConnectionConfig
from .utils import build_backup_path, is_dir, short_error


class RobotClient:
    def __init__(self) -> None:
        self.ssh: paramiko.SSHClient | None = None
        self.sftp: paramiko.SFTPClient | None = None
        self.lock = threading.RLock()
        self.home_dir = ""

    @property
    def connected(self) -> bool:
        return self.ssh is not None and self.sftp is not None

    def connect(self, config: ConnectionConfig) -> None:
        with self.lock:
            self.close()
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            connect_kwargs: dict[str, Any] = {
                "hostname": config.host,
                "port": config.port,
                "username": config.username,
                "timeout": config.timeout,
                "password": config.password,
                "allow_agent": False,
                "look_for_keys": False,
            }
            try:
                ssh.connect(**connect_kwargs)
                sftp = ssh.open_sftp()
                home_dir = sftp.normalize(".")
            except paramiko.AuthenticationException as exc:
                ssh.close()
                raise ApiError("SSH 认证失败，请检查用户名或密码") from exc
            except paramiko.BadHostKeyException as exc:
                ssh.close()
                raise ApiError("SSH 主机指纹校验失败") from exc
            except paramiko.SSHException as exc:
                ssh.close()
                raise ApiError(f"SSH 连接失败: {exc}") from exc
            except OSError as exc:
                ssh.close()
                raise ApiError(f"无法连接到主机 {config.host}:{config.port}: {exc}") from exc
            self.ssh = ssh
            self.sftp = sftp
            self.home_dir = home_dir

    def connect_via_jump(self, jump_client: "RobotClient", config: ConnectionConfig) -> None:
        with self.lock:
            self.close()
            jump_client.ensure_connected()
            assert jump_client.ssh is not None
            transport = jump_client.ssh.get_transport()
            if transport is None or not transport.is_active():
                raise ApiError("跳板连接不可用，无法连接目标处理器")
            try:
                channel = transport.open_channel(
                    "direct-tcpip",
                    (config.host, int(config.port)),
                    ("127.0.0.1", 0),
                )
            except Exception as exc:  # noqa: BLE001
                raise ApiError(f"无法通过跳板连接目标处理器 {config.host}:{config.port}: {exc}") from exc

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            connect_kwargs: dict[str, Any] = {
                "hostname": config.host,
                "port": config.port,
                "username": config.username,
                "timeout": config.timeout,
                "password": config.password,
                "allow_agent": False,
                "look_for_keys": False,
                "sock": channel,
            }
            try:
                ssh.connect(**connect_kwargs)
                sftp = ssh.open_sftp()
                home_dir = sftp.normalize(".")
            except paramiko.AuthenticationException as exc:
                ssh.close()
                raise ApiError("目标处理器 SSH 认证失败，请检查用户名或密码") from exc
            except paramiko.BadHostKeyException as exc:
                ssh.close()
                raise ApiError("目标处理器主机指纹校验失败") from exc
            except paramiko.SSHException as exc:
                ssh.close()
                raise ApiError(f"目标处理器 SSH 连接失败: {exc}") from exc
            except OSError as exc:
                ssh.close()
                raise ApiError(f"无法连接到目标处理器 {config.host}:{config.port}: {exc}") from exc
            self.ssh = ssh
            self.sftp = sftp
            self.home_dir = home_dir

    def close(self) -> None:
        with self.lock:
            if self.sftp is not None:
                self.sftp.close()
                self.sftp = None
            if self.ssh is not None:
                self.ssh.close()
                self.ssh = None
            self.home_dir = ""

    def ensure_connected(self) -> None:
        if not self.connected:
            raise ApiError("请先连接机器人")

    def get_sftp(self, *, refresh: bool = False) -> paramiko.SFTPClient:
        with self.lock:
            self.ensure_connected()
            assert self.ssh is not None
            if self.sftp is not None:
                try:
                    channel = self.sftp.get_channel()
                    if refresh or channel.closed or not channel.active:
                        self.sftp.close()
                        self.sftp = None
                except Exception:  # noqa: BLE001
                    try:
                        self.sftp.close()
                    except Exception:  # noqa: BLE001
                        pass
                    self.sftp = None
            if self.sftp is None:
                self.sftp = self.ssh.open_sftp()
                if not self.home_dir:
                    self.home_dir = self.sftp.normalize(".")
            return self.sftp

    def exec_command(self, command: str, *, timeout: float | None = None) -> dict[str, Any]:
        with self.lock:
            self.ensure_connected()
            assert self.ssh is not None
            _, stdout, stderr = self.ssh.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            return {
                "exit_code": exit_code,
                "stdout": stdout.read().decode("utf-8", errors="replace"),
                "stderr": stderr.read().decode("utf-8", errors="replace"),
            }

    def exec_sudo_command(self, command: str, password: str, *, timeout: float | None = None) -> dict[str, Any]:
        with self.lock:
            self.ensure_connected()
            assert self.ssh is not None
            wrapped = f"sudo -S -p '' bash -lc {shlex.quote(command)}"
            stdin, stdout, stderr = self.ssh.exec_command(wrapped, timeout=timeout)
            stdin.write(f"{password}\n")
            stdin.flush()
            exit_code = stdout.channel.recv_exit_status()
            return {
                "exit_code": exit_code,
                "stdout": stdout.read().decode("utf-8", errors="replace"),
                "stderr": stderr.read().decode("utf-8", errors="replace"),
            }

    def exec_interactive_command(self, command: str, *, timeout: float = 20.0) -> dict[str, Any]:
        with self.lock:
            self.ensure_connected()
            assert self.ssh is not None
            channel = self.ssh.invoke_shell(width=160, height=48)
            channel.settimeout(0.2)
            marker = f"__CODEx_DONE_{uuid.uuid4().hex}__"
            marker_pattern = re.compile(rf"{re.escape(marker)}:(\d+)")
            output_chunks: list[str] = []

            def drain_channel(idle_seconds: float) -> str:
                deadline = time.monotonic() + idle_seconds
                buffer: list[str] = []
                while time.monotonic() < deadline:
                    if channel.recv_ready():
                        chunk = channel.recv(4096).decode("utf-8", errors="replace")
                        if not chunk:
                            break
                        buffer.append(chunk)
                        deadline = time.monotonic() + idle_seconds
                        continue
                    time.sleep(0.05)
                return "".join(buffer)

            try:
                drain_channel(0.4)
                wrapped_command = (
                    f"{command}\n"
                    f"printf '\\n{marker}:%s\\n' $?\n"
                )
                channel.send(wrapped_command)
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    chunk = drain_channel(0.3)
                    if chunk:
                        output_chunks.append(chunk)
                        combined_output = "".join(output_chunks)
                        marker_match = marker_pattern.search(combined_output)
                        if marker_match:
                            exit_code = int(marker_match.group(1))
                            cleaned_output = marker_pattern.sub("", combined_output)
                            cleaned_output = cleaned_output.replace(wrapped_command, "", 1).strip()
                            return {
                                "exit_code": exit_code,
                                "stdout": cleaned_output,
                                "stderr": "",
                            }
                    time.sleep(0.05)
                raise ApiError(f"交互式命令执行超时（>{timeout:.0f}s）")
            finally:
                channel.close()

    def exec_compose_service_command(self, project_root: str, service_name: str, command: str, *, timeout: float = 20.0) -> dict[str, Any]:
        normalized_project_root = str(project_root or "").strip()
        normalized_service_name = str(service_name or "").strip()
        normalized_command = str(command or "").strip()
        if not normalized_project_root:
            raise ApiError("docker compose 项目目录不能为空")
        if not normalized_service_name:
            raise ApiError("docker compose 服务名不能为空")
        if not normalized_command:
            raise ApiError("容器命令不能为空")
        setup_script = (
            "for file in "
            "/opt/ros/noetic/setup.bash "
            "/opt/ros/humble/setup.bash "
            "/workspace/devel/setup.bash "
            "/workspace/install/setup.bash "
            "/root/catkin_ws/devel/setup.bash "
            "/catkin_ws/devel/setup.bash "
            "/app/catkin_ws/devel/setup.bash; "
            "do if [ -f \"$file\" ]; then . \"$file\" >/dev/null 2>&1; fi; done"
        )
        wrapped_command = (
            f"cd {shlex.quote(normalized_project_root)} && "
            f"docker compose exec -T {shlex.quote(normalized_service_name)} "
            f"bash -lc {shlex.quote(f'{setup_script}; {normalized_command}')}"
        )
        return self.exec_command(wrapped_command, timeout=timeout + 5.0)

    def get_interactive_env(self, name: str, *, timeout: float = 10.0) -> str:
        variable_name = str(name or "").strip()
        if not variable_name:
            raise ApiError("环境变量名不能为空")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable_name):
            raise ApiError(f"非法环境变量名: {variable_name}")
        result = self.exec_command(f"bash -ic 'printf %s \"${variable_name}\"'")
        if int(result.get("exit_code", 0) or 0) != 0:
            raise ApiError(f"读取环境变量失败: {variable_name}")
        return str(result.get("stdout") or "").strip()

    def get_home_dir(self) -> str:
        with self.lock:
            self.ensure_connected()
            if not self.home_dir:
                self.home_dir = self.get_sftp().normalize(".")
            return self.home_dir

    def resolve_remote_path(self, remote_path: str) -> str:
        normalized = str(remote_path or "").strip()
        if not normalized:
            return ""
        if normalized == "~":
            return self.get_home_dir()
        if normalized.startswith("~/"):
            return posixpath.join(self.get_home_dir(), normalized[2:])
        return normalized

    def ensure_remote_dir(self, remote_dir: str) -> None:
        if not remote_dir:
            return
        with self.lock:
            self.ensure_connected()
            sftp = self.get_sftp()
            remote_dir = self.resolve_remote_path(remote_dir)
            current = "/"
            for part in [piece for piece in remote_dir.split("/") if piece]:
                current = posixpath.join(current, part)
                try:
                    sftp.stat(current)
                except FileNotFoundError:
                    sftp.mkdir(current)

    def _upload_reader(self, reader, total_bytes: int, remote_path: str, progress_callback=None) -> str:
        with self.lock:
            self.ensure_connected()
            remote_path = self.resolve_remote_path(remote_path)
            sftp = self.get_sftp(refresh=True)
            self.ensure_remote_dir(posixpath.dirname(remote_path))
            transferred_bytes = 0
            with sftp.file(remote_path, "wb") as remote_stream:
                remote_stream.set_pipelined(True)
                while True:
                    chunk = reader(UPLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    remote_stream.write(chunk)
                    transferred_bytes += len(chunk)
                    if progress_callback:
                        progress_callback(transferred_bytes, total_bytes)
                remote_stream.flush()
            try:
                remote_size = int(sftp.stat(remote_path).st_size)
            except Exception:  # noqa: BLE001
                remote_size = total_bytes
            if remote_size != total_bytes:
                raise ApiError(f"远程上传大小异常: 预期 {total_bytes} 字节, 实际 {remote_size} 字节")
            return remote_path

    def upload_bytes(self, data: bytes, remote_path: str, progress_callback=None) -> str:
        total_bytes = len(data)
        view = memoryview(data)
        offset = 0

        def reader(chunk_size: int) -> bytes:
            nonlocal offset
            if offset >= total_bytes:
                return b""
            chunk = bytes(view[offset : offset + chunk_size])
            offset += len(chunk)
            return chunk

        return self._upload_reader(reader, total_bytes, remote_path, progress_callback=progress_callback)

    def upload_local_file(self, local_path: str | Path, remote_path: str, progress_callback=None) -> str:
        source_path = Path(local_path)
        try:
            source_stat = source_path.stat()
            total_bytes = int(source_stat.st_size)
        except OSError as exc:
            raise ApiError(f"读取本地待上传文件失败: {source_path}") from exc
        with source_path.open("rb") as local_stream:
            uploaded_path = self._upload_reader(local_stream.read, total_bytes, remote_path, progress_callback=progress_callback)
        try:
            self.get_sftp(refresh=True).chmod(uploaded_path, source_stat.st_mode & 0o777)
        except OSError as exc:
            raise ApiError(f"同步远端文件权限失败: {uploaded_path}") from exc
        return uploaded_path

    def upload_local_tree(self, local_dir: str | Path, remote_dir: str) -> list[str]:
        source_dir = Path(local_dir)
        if not source_dir.exists():
            raise ApiError(f"本地目录不存在: {source_dir}")
        if not source_dir.is_dir():
            raise ApiError(f"本地路径不是目录: {source_dir}")
        remote_dir = self.resolve_remote_path(remote_dir)
        uploaded_paths: list[str] = []
        self.ensure_remote_dir(remote_dir)
        for path in sorted(source_dir.rglob("*")):
            relative_path = path.relative_to(source_dir).as_posix()
            target_path = posixpath.join(remote_dir, relative_path)
            if path.is_dir():
                self.ensure_remote_dir(target_path)
                continue
            self.upload_local_file(path, target_path)
            uploaded_paths.append(target_path)
        return uploaded_paths

    def list_dir(self, remote_dir: str) -> list[dict[str, Any]]:
        with self.lock:
            self.ensure_connected()
            sftp = self.get_sftp()
            remote_dir = self.resolve_remote_path(remote_dir)
            entries = []
            for item in sftp.listdir_attr(remote_dir):
                path = posixpath.join(remote_dir, item.filename)
                entries.append(
                    {
                        "name": item.filename,
                        "path": path,
                        "is_dir": is_dir(item.st_mode),
                        "size": item.st_size,
                        "mtime": int(getattr(item, "st_mtime", 0) or 0),
                    }
                )
            entries.sort(key=lambda entry: (not entry["is_dir"], entry["name"].lower()))
            return entries

    def read_file_bytes(self, remote_path: str) -> bytes:
        with self.lock:
            self.ensure_connected()
            sftp = self.get_sftp()
            remote_path = self.resolve_remote_path(remote_path)
            with sftp.file(remote_path, "rb") as remote_stream:
                return remote_stream.read()

    def path_exists(self, remote_path: str) -> bool:
        with self.lock:
            self.ensure_connected()
            sftp = self.get_sftp()
            remote_path = self.resolve_remote_path(remote_path)
            try:
                sftp.stat(remote_path)
                return True
            except FileNotFoundError:
                return False

    def get_remote_file_owner(self, remote_path: str) -> str:
        remote_path = self.resolve_remote_path(remote_path)
        result = self.exec_command(f"stat -c '%U' -- {shlex.quote(remote_path)}")
        if result["exit_code"] != 0:
            raise ApiError(f"读取远端文件所有者失败: {short_error(result)}")
        return str(result.get("stdout") or "").strip()

    def ensure_remote_executable(self, remote_path: str, *, sudo_password: str = "") -> dict[str, Any]:
        remote_path = self.resolve_remote_path(remote_path)
        command = f"chmod +x -- {shlex.quote(remote_path)}"
        if sudo_password:
            result = self.exec_sudo_command(command, sudo_password)
        else:
            result = self.exec_command(command)
        if result["exit_code"] != 0:
            raise ApiError(f"设置远端文件可执行权限失败: {short_error(result)}")
        return result

    def is_dir_path(self, remote_path: str) -> bool:
        with self.lock:
            self.ensure_connected()
            sftp = self.get_sftp()
            remote_path = self.resolve_remote_path(remote_path)
            try:
                return is_dir(sftp.stat(remote_path).st_mode)
            except FileNotFoundError:
                return False

    def backup_remote_path(self, remote_path: str, *, sudo_password: str = "") -> str | None:
        remote_path = self.resolve_remote_path(remote_path)
        if not self.path_exists(remote_path):
            return None
        backup_path = build_backup_path(remote_path)
        command = f"cp -a -- {shlex.quote(remote_path)} {shlex.quote(backup_path)}"
        if sudo_password:
            result = self.exec_sudo_command(command, sudo_password)
        else:
            result = self.exec_command(command)
        if result["exit_code"] != 0:
            raise ApiError(f"远程备份失败: {short_error(result)}")
        return backup_path

    def restore_backup(self, backup_path: str, remote_path: str) -> dict[str, Any]:
        backup_path = self.resolve_remote_path(backup_path)
        remote_path = self.resolve_remote_path(remote_path)
        result = self.exec_command(f"cp -a -- {shlex.quote(backup_path)} {shlex.quote(remote_path)}")
        if result["exit_code"] != 0:
            raise ApiError(f"恢复备份失败: {short_error(result)}")
        return result

    def move_remote_path(self, source_path: str, target_path: str, *, sudo_password: str = "") -> dict[str, Any]:
        source_path = self.resolve_remote_path(source_path)
        target_path = self.resolve_remote_path(target_path)
        self.ensure_remote_dir(posixpath.dirname(target_path))
        command = f"mv -f -- {shlex.quote(source_path)} {shlex.quote(target_path)}"
        if sudo_password:
            result = self.exec_sudo_command(command, sudo_password)
        else:
            result = self.exec_command(command)
        if result["exit_code"] != 0:
            raise ApiError(f"移动远端文件失败: {short_error(result)}")
        return result

    def remove_remote_path(self, remote_path: str, *, recursive: bool = False, sudo_password: str = "") -> None:
        target_path = self.resolve_remote_path(remote_path)
        if not self.path_exists(target_path):
            return
        command = "rm -rf --" if recursive else "rm -f --"
        raw_command = f"{command} {shlex.quote(target_path)}"
        if sudo_password:
            result = self.exec_sudo_command(raw_command, sudo_password)
        else:
            result = self.exec_command(raw_command)
        if result["exit_code"] != 0:
            raise ApiError(f"删除远端路径失败: {short_error(result)}")

    def remove_files_by_prefix(self, remote_dir: str, prefix: str, *, sudo_password: str = "") -> list[str]:
        target_dir = self.resolve_remote_path(remote_dir)
        if not self.path_exists(target_dir):
            return []
        removed_files: list[str] = []
        for entry in self.list_dir(target_dir):
            if entry.get("is_dir"):
                continue
            entry_name = str(entry.get("name") or "")
            entry_path = str(entry.get("path") or "")
            if not entry_name.startswith(prefix):
                continue
            command = f"rm -f -- {shlex.quote(entry_path)}"
            if sudo_password:
                result = self.exec_sudo_command(command, sudo_password)
            else:
                result = self.exec_command(command)
            if result["exit_code"] != 0:
                raise ApiError(f"删除旧文件失败: {short_error(result)}")
            removed_files.append(entry_path)
        return removed_files

    def walk_entries(self, root_path: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        self._walk(self.resolve_remote_path(root_path), results)
        return results

    def list_files_recursive(self, root_path: str, *, require_birth_time: bool = False) -> list[dict[str, Any]]:
        resolved_root = self.resolve_remote_path(root_path)
        command = (
            f"find {shlex.quote(resolved_root)} -type f "
            "-exec stat -c '%W\t%Z\t%Y\t%s\t%n' {} +"
        )
        result = self.exec_command(command)
        if result["exit_code"] != 0:
            raise ApiError(f"递归扫描日志目录失败: {short_error(result)}")

        entries: list[dict[str, Any]] = []
        for raw_line in result["stdout"].splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split("\t", 4)
            if len(parts) != 5:
                continue
            birth_time_raw, change_time_raw, modified_time_raw, size_raw, path = parts
            try:
                birth_time = int(float(birth_time_raw or 0))
            except ValueError:
                birth_time = 0
            try:
                change_time = int(float(change_time_raw or 0))
            except ValueError:
                change_time = 0
            try:
                modified_time = int(float(modified_time_raw or 0))
            except ValueError:
                modified_time = 0
            try:
                size = int(float(size_raw or 0))
            except ValueError:
                size = 0
            normalized_path = str(path or "").strip()
            if not normalized_path:
                continue
            if require_birth_time and birth_time <= 0:
                raise ApiError(f"文件系统不支持按创建时间筛选，缺少 birth time: {normalized_path}")
            relative_path = posixpath.relpath(normalized_path, resolved_root)
            entries.append(
                {
                    "name": posixpath.basename(normalized_path),
                    "path": normalized_path,
                    "relative_path": relative_path,
                    "is_dir": False,
                    "size": size,
                    "mtime": modified_time,
                    "ctime": change_time,
                    "birth_time": birth_time,
                    "created_at": birth_time,
                }
            )
        entries.sort(
            key=lambda entry: (
                posixpath.dirname(str(entry.get("relative_path") or "")),
                str(entry.get("name") or "").lower(),
                str(entry.get("relative_path") or "").lower(),
            )
        )
        return entries

    def directory_shortcuts(self) -> dict[str, Any]:
        home_dir = self.get_home_dir()
        shortcuts: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        preferred_root = ""
        for candidate_path, label in PROJECT_ROOT_CANDIDATES:
            resolved_path = self.resolve_remote_path(candidate_path)
            if resolved_path in seen_paths:
                continue
            seen_paths.add(resolved_path)
            exists = self.path_exists(resolved_path)
            if exists and not preferred_root:
                preferred_root = resolved_path
            shortcuts.append(
                {
                    "label": label,
                    "path": resolved_path,
                    "display_path": candidate_path,
                    "exists": exists,
                }
            )
        base_shortcuts = [
            {"label": "机器人 Home", "path": home_dir, "display_path": "~", "exists": True},
            {"label": "临时目录 /tmp", "path": "/tmp", "display_path": "/tmp", "exists": self.path_exists("/tmp")},
            {"label": "根目录 /", "path": "/", "display_path": "/", "exists": True},
        ]
        for shortcut in base_shortcuts:
            if shortcut["path"] in seen_paths:
                continue
            seen_paths.add(shortcut["path"])
            shortcuts.append(shortcut)
        if not preferred_root:
            preferred_root = home_dir
        return {"shortcuts": shortcuts, "preferred_root": preferred_root}

    def _walk(self, current: str, output: list[dict[str, Any]]) -> None:
        for entry in self.list_dir(current):
            output.append(entry)
            if entry["is_dir"]:
                try:
                    self._walk(entry["path"], output)
                except OSError:
                    continue
