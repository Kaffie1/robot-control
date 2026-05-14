#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_DIR="$BASE_DIR/.runtime"
PID_FILE="$RUNTIME_DIR/app.pid"
LOG_FILE="$RUNTIME_DIR/app.log"
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"
STOP_TIMEOUT=30

mkdir -p "$RUNTIME_DIR"

usage() {
  cat <<'EOF'
用法:
  ./service.sh start
  ./service.sh stop
  ./service.sh restart
  ./service.sh status

说明:
  start   后台启动 Web 服务
  stop    停止后台 Web 服务
  restart 重启后台 Web 服务
  status  查看服务状态
EOF
}

is_running() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null
}

can_import_backend() {
  local py="$1"
  (
    cd "$BASE_DIR"
    PYTHONPATH="$BASE_DIR:${PYTHONPATH:-}" "$py" -c "import backend.main"
  ) >/dev/null 2>&1
}

resolve_python_bin() {
  local -a candidates=()
  local py

  if [[ -n "${PYTHON_BIN:-}" ]]; then
    candidates+=("$PYTHON_BIN")
  fi

  if [[ -n "${CONDA_EXE:-}" ]]; then
    local conda_root
    conda_root="$(cd "$(dirname "$CONDA_EXE")/.." && pwd)"
    candidates+=(
      "$conda_root/envs/py311/bin/python"
      "$conda_root/envs/py310/bin/python"
    )
  fi

  if [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/python" ]]; then
    candidates+=("${CONDA_PREFIX}/bin/python")
  fi

  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    candidates+=("${VIRTUAL_ENV}/bin/python")
  fi

  candidates+=("python3" "python")

  for py in "${candidates[@]}"; do
    [[ -n "$py" ]] || continue
    if ! command -v "$py" >/dev/null 2>&1; then
      continue
    fi
    py="$(command -v "$py")"
    if can_import_backend "$py"; then
      printf '%s\n' "$py"
      return 0
    fi
  done

  for py in "${candidates[@]}"; do
    [[ -n "$py" ]] || continue
    if command -v "$py" >/dev/null 2>&1; then
      command -v "$py"
      return 0
    fi
  done

  return 1
}

if ! PYTHON_BIN="$(resolve_python_bin)"; then
  echo "未找到可用的 Python 可执行文件" >&2
  exit 1
fi

START_CMD=("$PYTHON_BIN" -m backend.main)

port_in_use() {
  "$PYTHON_BIN" - "$APP_HOST" "$APP_PORT" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
except PermissionError:
    raise SystemExit(2)

try:
    sock.bind((host, port))
except OSError:
    raise SystemExit(0)
finally:
    sock.close()
raise SystemExit(1)
PY
}

warn_unmanaged_instance() {
  local context="$1"
  local port_state=1
  if port_in_use; then
    port_state=0
  else
    port_state=$?
  fi

  if [[ "$port_state" -eq 0 ]]; then
    echo "${context}端口 ${APP_HOST}:${APP_PORT} 当前被占用，可能有其他实例在运行。" >&2
  fi
}

check_runtime() {
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "未找到 Python 可执行文件: $PYTHON_BIN" >&2
    return 1
  fi

  if ! can_import_backend "$PYTHON_BIN"; then
    echo "当前 Python 环境无法导入 backend.main: $PYTHON_BIN" >&2
    echo "项目目录: $BASE_DIR" >&2
    echo "可先安装依赖，或通过 PYTHON_BIN 指定可用环境，例如:" >&2
    echo "  PYTHON_BIN=/path/to/python ./scripts/service.sh start" >&2
    return 1
  fi
}

read_pid() {
  if [[ -f "$PID_FILE" ]]; then
    tr -d '[:space:]' <"$PID_FILE"
  fi
}

clear_stale_pid() {
  local pid
  pid="$(read_pid)"

  if [[ -n "${pid:-}" ]] && ! is_running "$pid"; then
    rm -f "$PID_FILE"
  fi
}

start_service() {
  local pid
  clear_stale_pid
  pid="$(read_pid)"

  check_runtime

  if [[ -n "${pid:-}" ]] && is_running "$pid"; then
    echo "服务已在运行中，PID: $pid"
    echo "日志文件: $LOG_FILE"
    return 0
  fi

  if port_in_use; then
    echo "端口 ${APP_HOST}:${APP_PORT} 已被占用，可能已有其他实例在运行。" >&2
    echo "当前 PID 文件: $PID_FILE" >&2
    echo "如果页面仍可访问，通常表示服务是由其他进程启动的，而不是当前 PID 文件管理的实例。" >&2
    return 1
  fi

  (
    cd "$BASE_DIR"
    export APP_HOST APP_PORT
    nohup "${START_CMD[@]}" >>"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
  )

  sleep 1
  pid="$(read_pid)"

  if [[ -n "${pid:-}" ]] && is_running "$pid"; then
    echo "服务启动成功，PID: $pid"
    echo "日志文件: $LOG_FILE"
    return 0
  fi

  rm -f "$PID_FILE"
  echo "服务启动失败，请检查日志: $LOG_FILE" >&2
  return 1
}

stop_service() {
  local pid
  local waited=0

  clear_stale_pid
  pid="$(read_pid)"

  if [[ -z "${pid:-}" ]]; then
    echo "服务未运行"
    warn_unmanaged_instance ""
    return 0
  fi

  echo "正在停止服务，PID: $pid"
  kill "$pid"

  while is_running "$pid"; do
    if (( waited >= STOP_TIMEOUT )); then
      echo "服务在 ${STOP_TIMEOUT}s 内未退出，请手动检查 PID: $pid" >&2
      return 1
    fi
    sleep 1
    waited=$((waited + 1))
  done

  rm -f "$PID_FILE"
  echo "服务已停止"
}

status_service() {
  local pid
  clear_stale_pid
  pid="$(read_pid)"

  if [[ -n "${pid:-}" ]] && is_running "$pid"; then
    echo "服务运行中"
    echo "PID: $pid"
    echo "PID 文件: $PID_FILE"
    echo "日志文件: $LOG_FILE"
    return 0
  fi

  echo "服务未运行"
  echo "PID 文件: $PID_FILE"
  echo "日志文件: $LOG_FILE"
  warn_unmanaged_instance "注意: "
}

main() {
  local action="${1:-}"

  case "$action" in
    start)
      start_service
      ;;
    stop)
      stop_service
      ;;
    restart)
      stop_service || true
      start_service
      ;;
    status)
      status_service
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
