import json
import secrets
import sqlite3
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import CHAT_SESSION_DIR, MAX_CONNECTION_CACHE_ITEMS, MAX_TASK_ITEMS
from .models import TaskFailure
from .robot import RobotClient
from .utils import now_text


def normalize_connection_cache_entry(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    host = str(entry.get("host") or "").strip()
    username = str(entry.get("username") or "").strip()
    port_text = str(entry.get("port") or "").strip() or "22"
    password = str(entry.get("password") or "")
    pico_host = str(entry.get("pico_host") or "").strip()
    pico_username = str(entry.get("pico_username") or "").strip()
    pico_password = str(entry.get("pico_password") or "")
    if not host or not username:
        return None
    try:
        port = int(port_text)
    except ValueError:
        port = 22
    try:
        pico_port = int(entry.get("pico_port") or 22)
    except ValueError:
        pico_port = 22
    saved_at = str(entry.get("saved_at") or "")
    return {
        "id": f"{host}|{port}|{username}",
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "pico_host": pico_host,
        "pico_port": pico_port,
        "pico_username": pico_username,
        "pico_password": pico_password,
        "saved_at": saved_at,
    }


def normalize_machine_option(option: Any) -> dict[str, str] | None:
    if isinstance(option, dict):
        value = str(option.get("value") or option.get("id") or option.get("name") or "").strip()
        label = str(option.get("label") or option.get("title") or value).strip()
    else:
        value = str(option or "").strip()
        label = value
    if not value:
        return None
    return {"value": value, "label": label or value}


def normalize_doc_link(entry: Any) -> dict[str, str] | None:
    if not isinstance(entry, dict):
        return None
    title = str(entry.get("title") or "").strip()
    url = str(entry.get("url") or "").strip()
    if not title or not url:
        return None
    return {"title": title, "url": url}


def normalize_deploy_profile(profile: Any, defaults: dict[str, Any]) -> dict[str, Any]:
    item = profile if isinstance(profile, dict) else {}
    probe_command_template = str(item.get("probe_command_template") or defaults.get("probe_command_template", "")).strip()
    install_template = str(item.get("install_template") or defaults["install_template"]).strip()
    if not install_template:
        install_template = defaults["install_template"]
    normalized = {
        "probe_command_template": probe_command_template,
        "up_wait_seconds": max(int(item.get("up_wait_seconds", defaults.get("up_wait_seconds", 0)) or 0), 0),
        "install_template": install_template,
        "start_command": str(item.get("start_command", defaults["start_command"])).strip(),
        "health_command": str(item.get("health_command", defaults["health_command"])).strip(),
        "rollback_template": str(item.get("rollback_template", defaults["rollback_template"])).strip(),
        "auto_rollback": bool(item.get("auto_rollback", defaults["auto_rollback"])),
    }
    raw_machine_options = item.get("machine_options", defaults.get("machine_options", []))
    machine_options: list[dict[str, str]] = []
    if isinstance(raw_machine_options, list):
        for option in raw_machine_options:
            normalized_option = normalize_machine_option(option)
            if normalized_option:
                machine_options.append(normalized_option)
    if machine_options:
        normalized["machine_options"] = machine_options
    raw_machine_profiles = item.get("machine_profiles", defaults.get("machine_profiles", {}))
    machine_profiles: dict[str, dict[str, Any]] = {}
    if isinstance(raw_machine_profiles, dict):
        for machine_key, machine_profile in raw_machine_profiles.items():
            normalized_key = str(machine_key or "").strip()
            machine_item = machine_profile if isinstance(machine_profile, dict) else {}
            if not normalized_key:
                continue
            machine_profiles[normalized_key] = {
                "probe_command_template": str(machine_item.get("probe_command_template", normalized["probe_command_template"])).strip(),
                "up_wait_seconds": max(int(machine_item.get("up_wait_seconds", normalized["up_wait_seconds"]) or 0), 0),
                "install_template": str(machine_item.get("install_template", normalized["install_template"])).strip()
                or normalized["install_template"],
                "start_command": str(machine_item.get("start_command", normalized["start_command"])).strip(),
                "health_command": str(machine_item.get("health_command", normalized["health_command"])).strip(),
                "rollback_template": str(machine_item.get("rollback_template", normalized["rollback_template"])).strip(),
                "auto_rollback": bool(machine_item.get("auto_rollback", normalized["auto_rollback"])),
            }
    if machine_profiles:
        normalized["machine_profiles"] = machine_profiles
    return normalized


class ConnectionCacheStore:
    def __init__(self, cache_path: Path, max_items: int = MAX_CONNECTION_CACHE_ITEMS) -> None:
        self.cache_path = cache_path
        self.max_items = max_items
        self.lock = threading.Lock()

    def list_entries(self) -> list[dict[str, Any]]:
        with self.lock:
            return self._read_entries()

    def remember(self, connection: dict[str, Any]) -> list[dict[str, Any]]:
        normalized = normalize_connection_cache_entry({**connection, "saved_at": datetime.now().isoformat(timespec="seconds")})
        if normalized is None:
            return self.list_entries()
        with self.lock:
            entries = [normalized, *[item for item in self._read_entries() if item["id"] != normalized["id"]]]
            entries = entries[: self.max_items]
            self._write_entries(entries)
            return entries

    def clear(self) -> list[dict[str, Any]]:
        with self.lock:
            self._write_entries([])
            return []

    def _read_entries(self) -> list[dict[str, Any]]:
        if not self.cache_path.exists():
            return []
        try:
            raw = self.cache_path.read_text(encoding="utf-8")
            parsed = json.loads(raw or "[]")
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(parsed, list):
            return []
        items = [normalize_connection_cache_entry(entry) for entry in parsed]
        return [item for item in items if item]

    def _write_entries(self, entries: list[dict[str, Any]]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.cache_path.with_suffix(f"{self.cache_path.suffix}.tmp")
        temp_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.cache_path)


class DeployConfigStore:
    def __init__(self, config_path: Path, defaults: dict[str, dict[str, Any]]) -> None:
        self.config_path = config_path
        self.defaults = defaults
        self.lock = threading.Lock()

    def ensure_exists(self) -> None:
        with self.lock:
            if not self.config_path.exists():
                self._write(self.defaults)

    def get_profile(self, deploy_mode: str = "package", machine_type: str = "") -> dict[str, Any]:
        from .models import ApiError

        mode = str(deploy_mode or "package").strip().lower()
        config = self.load()
        if mode not in config:
            raise ApiError(f"当前不支持的部署模式: {mode}")
        profile = config.get(mode)
        if profile is None:
            raise ApiError(f"部署配置中缺少 {mode} 配置")
        machine_options = profile.get("machine_options", [])
        option_values = [str(option.get("value") or "").strip() for option in machine_options if isinstance(option, dict)]
        resolved_machine_type = str(machine_type or "").strip()
        if not resolved_machine_type and option_values:
            resolved_machine_type = option_values[0]
        if resolved_machine_type and option_values and resolved_machine_type not in option_values:
            raise ApiError(f"未配置的机型: {resolved_machine_type}")
        resolved_profile = dict(profile)
        machine_profiles = profile.get("machine_profiles", {})
        if resolved_machine_type and isinstance(machine_profiles, dict):
            resolved_profile.update(machine_profiles.get(resolved_machine_type, {}))
        resolved_profile["machine_type"] = resolved_machine_type
        resolved_profile["deploy_mode"] = mode
        return resolved_profile

    def get_machine_options(self, deploy_mode: str = "package") -> list[dict[str, str]]:
        mode = str(deploy_mode or "package").strip().lower()
        profile = self.load().get(mode, {})
        options = profile.get("machine_options", [])
        return [option for option in options if isinstance(option, dict) and str(option.get("value") or "").strip()]

    def load(self) -> dict[str, dict[str, Any]]:
        from .models import ApiError

        with self.lock:
            if not self.config_path.exists():
                self._write(self.defaults)
                return {key: dict(value) for key, value in self.defaults.items()}
            try:
                raw = self.config_path.read_text(encoding="utf-8")
                parsed = json.loads(raw or "{}")
            except json.JSONDecodeError as exc:
                raise ApiError(f"{self.config_path.name} 格式错误: {exc}") from exc
            except OSError as exc:
                raise ApiError(f"读取 {self.config_path.name} 失败: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ApiError(f"{self.config_path.name} 顶层必须是对象")
            return {key: normalize_deploy_profile(parsed.get(key), defaults) for key, defaults in self.defaults.items()}

    def _write(self, payload: dict[str, dict[str, Any]]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.config_path.with_suffix(f"{self.config_path.suffix}.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.config_path)


class HistoryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id TEXT,
                    task_id TEXT,
                    operation_type TEXT NOT NULL,
                    robot_host TEXT,
                    robot_port INTEGER,
                    robot_username TEXT,
                    title TEXT,
                    target_path TEXT,
                    remote_deb_path TEXT,
                    install_command TEXT,
                    start_command TEXT,
                    health_command TEXT,
                    rollback_command TEXT,
                    backup_path TEXT,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    logs TEXT,
                    created_at TEXT,
                    finished_at TEXT
                )
                """
            )
            columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(operation_history)").fetchall()}
            if "owner_id" not in columns:
                conn.execute("ALTER TABLE operation_history ADD COLUMN owner_id TEXT DEFAULT ''")

    def insert_entry(self, entry: dict[str, Any]) -> int:
        payload = {
            "owner_id": entry.get("owner_id", ""),
            "task_id": entry.get("task_id", ""),
            "operation_type": entry.get("operation_type", ""),
            "robot_host": entry.get("robot_host", ""),
            "robot_port": entry.get("robot_port"),
            "robot_username": entry.get("robot_username", ""),
            "title": entry.get("title", ""),
            "target_path": entry.get("target_path", ""),
            "remote_deb_path": entry.get("remote_deb_path", ""),
            "install_command": entry.get("install_command", ""),
            "start_command": entry.get("start_command", ""),
            "health_command": entry.get("health_command", ""),
            "rollback_command": entry.get("rollback_command", ""),
            "backup_path": entry.get("backup_path", ""),
            "status": entry.get("status", "succeeded"),
            "result_json": json.dumps(entry.get("result") or {}, ensure_ascii=False),
            "logs": "\n".join(entry.get("logs") or []),
            "created_at": entry.get("created_at", now_text()),
            "finished_at": entry.get("finished_at", now_text()),
        }
        with self.lock, self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO operation_history (
                    owner_id, task_id, operation_type, robot_host, robot_port, robot_username, title,
                    target_path, remote_deb_path, install_command, start_command, health_command,
                    rollback_command, backup_path, status, result_json, logs, created_at, finished_at
                )
                VALUES (
                    :owner_id, :task_id, :operation_type, :robot_host, :robot_port, :robot_username, :title,
                    :target_path, :remote_deb_path, :install_command, :start_command, :health_command,
                    :rollback_command, :backup_path, :status, :result_json, :logs, :created_at, :finished_at
                )
                """,
                payload,
            )
            return int(cursor.lastrowid)

    def get_entry(self, entry_id: int, owner_id: str = "") -> dict[str, Any] | None:
        normalized_owner_id = str(owner_id or "")
        with self.lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM operation_history WHERE id = ? AND owner_id = ?", (entry_id, normalized_owner_id)).fetchone()
        return self._serialize(row) if row else None

    def list_entries(self, limit: int = 20, owner_id: str = "") -> list[dict[str, Any]]:
        normalized_owner_id = str(owner_id or "")
        with self.lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM operation_history WHERE owner_id = ? ORDER BY id DESC LIMIT ?", (normalized_owner_id, limit)).fetchall()
        return [self._serialize(row) for row in rows]

    def _serialize(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["result"] = json.loads(item.pop("result_json") or "{}")
        item["logs"] = item["logs"].splitlines() if item.get("logs") else []
        item["rollback_available"] = bool(
            (item["operation_type"] == "deployment" and item.get("rollback_command"))
            or (item["operation_type"] == "file_replace" and item.get("backup_path"))
        )
        return item


class TaskContext:
    def __init__(self, manager: "TaskManager", task_id: str) -> None:
        self.manager = manager
        self.task_id = task_id

    def log(self, text: str) -> None:
        self.manager.append_log(self.task_id, text)


class TaskManager:
    def __init__(self, history_store: HistoryStore, max_items: int = MAX_TASK_ITEMS) -> None:
        self.history_store = history_store
        self.max_items = max(1, int(max_items or MAX_TASK_ITEMS))
        self.tasks: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    def create_task(self, task_type: str, title: str, metadata: dict[str, Any], runner, *, owner_id: str = "") -> dict[str, Any]:
        task_id = secrets.token_hex(8)
        task = {
            "id": task_id,
            "owner_id": str(owner_id or ""),
            "type": task_type,
            "title": title,
            "status": "pending",
            "metadata": metadata,
            "created_at": now_text(),
            "started_at": "",
            "finished_at": "",
            "logs": [],
            "result": {},
            "error": "",
            "history_id": None,
        }
        with self.lock:
            self.tasks[task_id] = task
            self._prune_tasks_locked()
        self.append_log(task_id, "任务已创建，等待后台执行")
        thread = threading.Thread(target=self._run_task, args=(task_id, runner), daemon=True)
        thread.start()
        return self.get_task(task_id) or {}

    def append_log(self, task_id: str, text: str) -> None:
        line = f"[{now_text()}] {text}"
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return
            task["logs"].append(line)
            task["logs"] = task["logs"][-300:]

    def _run_task(self, task_id: str, runner) -> None:
        self._update_task(task_id, {"status": "running", "started_at": now_text()})
        context = TaskContext(self, task_id)
        context.log("任务开始执行")
        payload: dict[str, Any] = {}
        status = "succeeded"
        error = ""
        try:
            result = runner(context)
            payload = result if isinstance(result, dict) else {"summary": result}
            summary = payload.get("summary", payload) if isinstance(payload, dict) else {}
            if isinstance(summary, dict) and summary.get("warnings"):
                status = "warning"
                context.log(f"任务完成，但存在 {len(summary.get('warnings') or [])} 条告警")
        except TaskFailure as exc:
            status = "failed"
            error = str(exc)
            payload = exc.payload
            context.log(f"任务失败: {error}")
        except Exception as exc:  # noqa: BLE001
            status = "failed"
            error = str(exc)
            context.log(f"任务异常: {error}")
            context.log(traceback.format_exc())
        self._finish_task(task_id, status, payload, error)

    def _finish_task(self, task_id: str, status: str, payload: dict[str, Any], error: str) -> None:
        result = payload.get("summary", payload) if isinstance(payload, dict) else {}
        history_payload = payload.get("history") if isinstance(payload, dict) else None
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return
            task["status"] = status
            task["finished_at"] = now_text()
            task["result"] = result
            task["error"] = error
            logs = list(task["logs"])
            task_snapshot = dict(task)
        if history_payload:
            history_entry = {
                **history_payload,
                "owner_id": str(task_snapshot.get("owner_id") or ""),
                "task_id": task_id,
                "status": status,
                "result": result,
                "logs": logs,
                "created_at": task_snapshot["created_at"],
                "finished_at": task_snapshot["finished_at"],
            }
            history_id = self.history_store.insert_entry(history_entry)
            with self.lock:
                if task_id in self.tasks:
                    self.tasks[task_id]["history_id"] = history_id
                self._prune_tasks_locked()

    def _update_task(self, task_id: str, values: dict[str, Any]) -> None:
        with self.lock:
            task = self.tasks.get(task_id)
            if task:
                task.update(values)

    def list_tasks(self, limit: int = MAX_TASK_ITEMS) -> list[dict[str, Any]]:
        with self.lock:
            items = sorted(self.tasks.values(), key=lambda item: (item["created_at"], item["id"]), reverse=True)
        return [self._serialize_task(task, include_logs=False) for task in items[:limit]]

    def list_tasks_for_owner(self, owner_id: str, limit: int = MAX_TASK_ITEMS) -> list[dict[str, Any]]:
        normalized_owner_id = str(owner_id or "")
        with self.lock:
            items = [
                item
                for item in sorted(self.tasks.values(), key=lambda item: (item["created_at"], item["id"]), reverse=True)
                if str(item.get("owner_id") or "") == normalized_owner_id
            ]
        return [self._serialize_task(task, include_logs=False) for task in items[:limit]]

    def _prune_tasks_locked(self) -> None:
        if len(self.tasks) <= self.max_items:
            return
        ordered_ids = [item["id"] for item in sorted(self.tasks.values(), key=lambda item: (item["created_at"], item["id"]))]
        for task_id in ordered_ids[: len(self.tasks) - self.max_items]:
            self.tasks.pop(task_id, None)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return None
            return self._serialize_task(task, include_logs=True)

    def get_task_for_owner(self, task_id: str, owner_id: str) -> dict[str, Any] | None:
        normalized_owner_id = str(owner_id or "")
        with self.lock:
            task = self.tasks.get(task_id)
            if not task or str(task.get("owner_id") or "") != normalized_owner_id:
                return None
            return self._serialize_task(task, include_logs=True)

    def _serialize_task(self, task: dict[str, Any], include_logs: bool) -> dict[str, Any]:
        return {
            "id": task["id"],
            "type": task["type"],
            "title": task["title"],
            "status": task["status"],
            "metadata": task["metadata"],
            "created_at": task["created_at"],
            "started_at": task["started_at"],
            "finished_at": task["finished_at"],
            "result": task["result"],
            "error": task["error"],
            "history_id": task["history_id"],
            "logs": list(task["logs"]) if include_logs else [],
        }


class SessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    def _build_chat_history_path(self, sid: str) -> Path:
        normalized_sid = str(sid or "").strip()
        if not normalized_sid:
            normalized_sid = "anonymous"
        return CHAT_SESSION_DIR / f"{normalized_sid}.json"

    def _initialize_chat_history_file(self, sid: str) -> Path:
        path = self._build_chat_history_path(sid)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("[]\n", encoding="utf-8")
        return path

    def _delete_chat_history_file(self, session: dict[str, Any]) -> None:
        raw_path = str(session.get("chat_history_path") or "").strip()
        path = Path(raw_path) if raw_path else self._build_chat_history_path(str(session.get("session_id") or ""))
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

    def _release_session_resources(self, session: dict[str, Any], *, remove_history_file: bool = True) -> None:
        client = session.get("client")
        if isinstance(client, RobotClient):
            client.close()
        session["chat_state"] = {}
        if remove_history_file:
            self._delete_chat_history_file(session)

    def get_or_create(self, sid: str | None) -> tuple[str, dict[str, Any], bool]:
        with self.lock:
            if sid and sid in self.sessions:
                self.sessions[sid]["last_seen_ts"] = time.time()
                return sid, self.sessions[sid], False
            new_sid = secrets.token_hex(16)
            chat_history_path = self._initialize_chat_history_file(new_sid)
            self.sessions[new_sid] = {
                "session_id": new_sid,
                "client": RobotClient(),
                "chat_history_path": str(chat_history_path),
                "last_seen_ts": time.time(),
                "path_cache": [],
                "last_remote_deb_path": "",
                "remote_shortcuts": [],
                "preferred_root": "/",
                "chat_state": {},
                "last_config": {
                    "host": "",
                    "port": 22,
                    "username": "",
                    "pico_host": "192.168.217.66",
                    "pico_port": 22,
                    "pico_username": "nav01",
                },
                "ssh_auth": {"username": "", "password": ""},
                "processor_auth": {
                    "ORIN": {"host": "", "port": 22, "username": "", "password": ""},
                    "PICO": {"host": "192.168.217.66", "port": 22, "username": "nav01", "password": ""},
                },
            }
            return new_sid, self.sessions[new_sid], True

    def touch(self, sid: str) -> None:
        if not sid:
            return
        with self.lock:
            session = self.sessions.get(sid)
            if session is not None:
                session["last_seen_ts"] = time.time()

    def cleanup_expired(self, idle_timeout_seconds: int) -> int:
        timeout = max(1, int(idle_timeout_seconds or 0))
        now_ts = time.time()
        expired_sessions: list[dict[str, Any]] = []
        with self.lock:
            expired_ids = [
                sid
                for sid, session in self.sessions.items()
                if now_ts - float(session.get("last_seen_ts") or 0) >= timeout
            ]
            for sid in expired_ids:
                expired_sessions.append(self.sessions.pop(sid))
        for session in expired_sessions:
            self._release_session_resources(session)
        return len(expired_sessions)

    def close_all(self) -> None:
        with self.lock:
            sessions = list(self.sessions.values())
            self.sessions.clear()
        for session in sessions:
            self._release_session_resources(session)


class UploadProgressManager:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}
        self.lock = threading.RLock()

    def start(self, token: str, *, file_name: str = "", total_bytes: int = 0, phase: str = "pending", message: str = "", owner_id: str = "") -> None:
        if not token:
            return
        with self.lock:
            self.items[token] = {
                "token": token,
                "owner_id": str(owner_id or ""),
                "file_name": file_name,
                "phase": phase,
                "message": message,
                "total_bytes": total_bytes,
                "transferred_bytes": 0,
                "percent": 0,
                "done": False,
                "error": "",
                "updated_at": now_text(),
            }

    def update(self, token: str, *, transferred_bytes: int | None = None, total_bytes: int | None = None, phase: str | None = None, message: str | None = None, done: bool | None = None, error: str | None = None, owner_id: str = "") -> None:
        if not token:
            return
        with self.lock:
            item = self.items.get(token)
            if item is None:
                self.start(token, owner_id=owner_id)
                item = self.items[token]
            if transferred_bytes is not None:
                item["transferred_bytes"] = transferred_bytes
            if total_bytes is not None:
                item["total_bytes"] = total_bytes
            if phase is not None:
                item["phase"] = phase
            if message is not None:
                item["message"] = message
            if done is not None:
                item["done"] = done
            if error is not None:
                item["error"] = error
            total = int(item.get("total_bytes") or 0)
            transferred = int(item.get("transferred_bytes") or 0)
            item["percent"] = round((transferred / total) * 100, 2) if total > 0 else 0
            item["updated_at"] = now_text()

    def fail(self, token: str, message: str, owner_id: str = "") -> None:
        self.update(token, phase="failed", message=message, error=message, done=True, owner_id=owner_id)

    def get(self, token: str, owner_id: str = "") -> dict[str, Any] | None:
        if not token:
            return None
        normalized_owner_id = str(owner_id or "")
        with self.lock:
            item = self.items.get(token)
            if not item or str(item.get("owner_id") or "") != normalized_owner_id:
                return None
            return dict(item)
