import json
import logging
import os
import posixpath
import re
import shlex
import sys
import tempfile
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from fastapi import Request, UploadFile

from .config import (
    CHFS_HOST,
    CHFS_PASSWORD,
    CHFS_PORT,
    CHFS_USER,
    CONNECTION_CACHE_PATH,
    DATA_DIR,
    DB_PATH,
    DOWNLOAD_TMP_DIR,
    FAULT_TRACE_LOG_PATH,
    LEGACY_CONNECTION_CACHE_PATH,
    LEGACY_DB_PATH,
    MODULE_DEPLOY_NAMES,
    STATIC_DIR,
    TEMPLATE_DIR,
)
from .models import ApiError


def setup_fault_logger() -> logging.Logger:
    logger = logging.getLogger("fault_diagnosis")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    log_path = Path(FAULT_TRACE_LOG_PATH).parent / "fault_diagnosis.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_path, encoding="utf-8", mode="a")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


class PrettyTraceFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        raw_message = super().format(record)
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            return raw_message
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def setup_fault_trace_logger() -> logging.Logger:
    logger = logging.getLogger("fault_diagnosis.trace")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    log_path = Path(FAULT_TRACE_LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_path, encoding="utf-8", mode="a")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(PrettyTraceFormatter("%(message)s"))

    logger.addHandler(file_handler)
    return logger


_fault_logger: logging.Logger | None = None


def get_fault_logger() -> logging.Logger:
    global _fault_logger
    if _fault_logger is None:
        _fault_logger = setup_fault_logger()
    return _fault_logger


_fault_trace_logger: logging.Logger | None = None


def get_fault_trace_logger() -> logging.Logger:
    global _fault_trace_logger
    if _fault_trace_logger is None:
        _fault_trace_logger = setup_fault_trace_logger()
    return _fault_trace_logger


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def migrate_legacy_runtime_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    migrations = [
        (LEGACY_DB_PATH, DB_PATH),
        (LEGACY_CONNECTION_CACHE_PATH, CONNECTION_CACHE_PATH),
    ]
    for legacy_path, target_path in migrations:
        if legacy_path == target_path:
            continue
        if not legacy_path.exists() or target_path.exists():
            continue
        legacy_path.replace(target_path)


def is_dir(st_mode: int) -> bool:
    return (st_mode & 0o170000) == 0o040000


def require_text(value: Any, message: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ApiError(message)
    return text


def parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_json_config(path: Path, default_payload: Any, *, label: str = "配置") -> Any:
    if not path.exists():
        return json.loads(json.dumps(default_payload, ensure_ascii=False))
    try:
        return json.loads(path.read_text(encoding="utf-8") or "null")
    except json.JSONDecodeError as exc:
        raise ApiError(f"{label}格式错误: {exc}") from exc
    except OSError as exc:
        raise ApiError(f"读取{label}失败: {exc}") from exc


def require_upload(upload: UploadFile | None, message: str) -> UploadFile:
    if upload is None or not str(upload.filename or "").strip():
        raise ApiError(message)
    return upload


def render_remote_command(
    template: str,
    remote_path: str,
    template_vars: dict[str, Any] | None = None,
    *,
    append_remote_path_if_missing: bool = True,
) -> str:
    normalized = template.strip()
    if not normalized:
        raise ApiError("命令模板不能为空")
    quoted_path = shlex.quote(remote_path)
    replacements: dict[str, str] = {
        "deb_path": quoted_path,
        "remote_path": quoted_path,
    }
    if template_vars:
        for key, value in template_vars.items():
            normalized_key = str(key or "").strip()
            if not normalized_key:
                continue
            replacements[normalized_key] = shlex.quote(str(value))

    path_placeholder_used = False
    for key, value in replacements.items():
        placeholder = f"{{{key}}}"
        if placeholder in normalized:
            normalized = normalized.replace(placeholder, value)
            if key in {"deb_path", "remote_path"} or key.endswith("_path"):
                path_placeholder_used = True

    if append_remote_path_if_missing and not path_placeholder_used:
        normalized = f"{normalized} {quoted_path}"
    return normalized


def build_backup_path(remote_path: str) -> str:
    remote_dir = posixpath.dirname(remote_path) or "/"
    file_name = posixpath.basename(remote_path)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return posixpath.join(remote_dir, f".{file_name}.bak.{timestamp}")


def extract_package_prefix(file_name: str) -> str:
    normalized = os.path.basename(require_text(file_name, "文件名不能为空"))
    prefix = normalized.split("_", 1)[0].strip()
    if not prefix:
        raise ApiError(f"无法从文件名解析模块前缀: {normalized}")
    return prefix


def resolve_module_path(module_name: str) -> str:
    normalized = require_text(module_name, "请选择要部署的模块")
    if normalized not in MODULE_DEPLOY_NAMES:
        raise ApiError(f"不支持的模块: {normalized}")
    return posixpath.join("/home/naviai/navi_project/.dists", normalized)


def resolve_download_source_path(raw_path: Any) -> str:
    text = require_text(raw_path, "文件服务器包路径不能为空").replace("\\", "/").strip()
    parsed = urllib.parse.urlparse(text)
    candidate = parsed.path if parsed.scheme else text
    slash_index = candidate.find("/")
    if slash_index >= 0:
        candidate = candidate[slash_index:]
    candidate = candidate.strip()
    if not candidate:
        raise ApiError("无法从输入内容中裁剪出可下载路径")
    if not candidate.startswith("/"):
        candidate = f"/{candidate}"
    return urllib.parse.unquote(candidate)


def download_file_from_chfs(remote_file: str, local_file: Path) -> Path:
    local_file.parent.mkdir(parents=True, exist_ok=True)
    base_url = f"http://{CHFS_HOST}:{CHFS_PORT}"
    session = requests.Session()
    try:
        login_url = f"{base_url.rstrip('/')}/chfs/session"
        login_response = session.post(login_url, data={"user": CHFS_USER, "pwd": CHFS_PASSWORD}, timeout=30)
        login_response.raise_for_status()

        attempts = [
            (f"{base_url.rstrip('/')}/chfs/download", {"filepath": remote_file}),
            (f"{base_url.rstrip('/')}{remote_file}", None),
        ]
        last_error: Exception | None = None
        for url, params in attempts:
            try:
                with session.get(url, params=params, timeout=300, stream=True) as response:
                    response.raise_for_status()
                    with local_file.open("wb") as file_obj:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                file_obj.write(chunk)
                    return local_file
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if last_error is not None:
            raise last_error
        raise ApiError(f"下载失败: {remote_file}")
    finally:
        try:
            session.delete(f"{base_url}/chfs/session", timeout=10)
        except Exception:  # noqa: BLE001
            pass


def short_error(result: dict[str, Any]) -> str:
    return str(result.get("stderr") or result.get("stdout") or "未知错误").strip()


CRITICAL_STDERR_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\):"),
    re.compile(r"\b[A-Za-z_]+Error:\s"),
    re.compile(r"\bException:\s"),
    re.compile(r"An error has been caught in function"),
]


def extract_critical_command_warnings(label: str, result: dict[str, Any]) -> list[str]:
    if int(result.get("exit_code", 0) or 0) != 0:
        return []
    stderr_text = str(result.get("stderr") or "")
    if not stderr_text.strip():
        return []
    for pattern in CRITICAL_STDERR_PATTERNS:
        match = pattern.search(stderr_text)
        if not match:
            continue
        snippet_start = max(match.start() - 80, 0)
        snippet_end = min(match.end() + 220, len(stderr_text))
        snippet = " ".join(stderr_text[snippet_start:snippet_end].split())
        return [f"{label}存在关键异常输出: {snippet}"]
    return []


def iter_command_output_lines(text: str) -> list[str]:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        return []
    return [line.rstrip() for line in normalized.splitlines()]


def detect_ignored_package_install_error(result: dict[str, Any]) -> str | None:
    exit_code = int(result.get("exit_code", 0) or 0)
    if exit_code == 0:
        return None

    stderr_text = str(result.get("stderr") or "")
    stdout_text = str(result.get("stdout") or "")
    combined_text = f"{stdout_text}\n{stderr_text}"
    success_markers = [
        "Deployment finished successfully",
        "Update Version Success",
    ]
    if not any(marker in combined_text for marker in success_markers):
        return None

    tolerated_arg_patterns = [
        re.compile(r"Could not consume arg:\s+--user="),
        re.compile(r"Could not consume arg:\s+--password="),
    ]
    matched_patterns = [pattern for pattern in tolerated_arg_patterns if pattern.search(combined_text)]
    if not matched_patterns:
        return None

    normalized_lines = [
        line.strip()
        for line in iter_command_output_lines(combined_text)
        if line.strip()
    ]
    unexpected_error_lines: list[str] = []
    for line in normalized_lines:
        if "Could not consume arg:" in line and ("--user=" in line or "--password=" in line):
            continue
        if any(marker in line for marker in success_markers):
            continue
        if "For detailed information on this command" in line:
            continue
        if line.startswith("Usage: zjh_deploy "):
            continue
        if re.search(r"\b(ERROR|Error|Exception|Traceback)\b", line):
            unexpected_error_lines.append(line)

    if unexpected_error_lines:
        return None
    return "安装包主体已成功部署，尾部仅出现新版本兼容参数告警，已忽略退出码"


def prepare_package_bytes(upload: UploadFile | None, server_file_path: str, *, local_error_message: str) -> tuple[str, bytes, dict[str, Any]]:
    source_path = str(server_file_path or "").strip()
    if source_path:
        remote_file = resolve_download_source_path(source_path)
        file_name = os.path.basename(remote_file)
        if not file_name:
            raise ApiError(f"无法从文件服务器路径解析文件名: {remote_file}")
        local_file = DOWNLOAD_TMP_DIR / file_name
        download_file_from_chfs(remote_file, local_file)
        return file_name, local_file.read_bytes(), {
            "source_kind": "file_server",
            "source_path": source_path,
            "download_path": remote_file,
            "local_tmp_path": str(local_file),
        }

    resolved_upload = require_upload(upload, local_error_message)
    file_name = os.path.basename(resolved_upload.filename or "")
    return file_name, resolved_upload.file.read(), {
        "source_kind": "local_upload",
        "source_path": "",
        "download_path": "",
        "local_tmp_path": "",
    }

def log_command_result(ctx, label: str, result: dict[str, Any]) -> None:
    ctx.log(f"{label}退出码: {result.get('exit_code', '')}")
    for stream_name, stream_label in (("stdout", "标准输出"), ("stderr", "错误输出")):
        output_lines = iter_command_output_lines(result.get(stream_name) or "")
        if not output_lines:
            continue
        ctx.log(f"{label}{stream_label}:")
        for line in output_lines:
            ctx.log(f"[{stream_name}] {line}")


def is_api_request(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def get_asset_version() -> str:
    candidates = [TEMPLATE_DIR / "index.html", *sorted((STATIC_DIR / "css").glob("*.css")), *sorted((STATIC_DIR / "js").glob("*.js"))]
    latest_mtime = 0.0
    for path in candidates:
        try:
            latest_mtime = max(latest_mtime, path.stat().st_mtime)
        except OSError:
            continue
    return str(int(latest_mtime))


def is_remote_subpath(parent_path: str, child_path: str) -> bool:
    normalized_parent = (parent_path or "/").rstrip("/") or "/"
    normalized_child = (child_path or "/").rstrip("/") or "/"
    return normalized_child == normalized_parent or normalized_child.startswith(f"{normalized_parent}/")
