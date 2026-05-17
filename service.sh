#!/bin/bash
# Agent Console service management script

APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/Caskroom/miniforge/base/envs/langchain/bin/python}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_DIR="${SCRIPT_DIR}/.runtime"
LOG_FILE="${RUNTIME_DIR}/app.log"
PID_FILE="${RUNTIME_DIR}/app.pid"
STARTUP_TIMEOUT="${STARTUP_TIMEOUT:-12}"

mkdir -p "${RUNTIME_DIR}"

get_port_pid() {
    lsof -tiTCP:"${APP_PORT}" -sTCP:LISTEN 2>/dev/null | head -n 1
}

get_recorded_pid() {
    if [ -f "${PID_FILE}" ]; then
        cat "${PID_FILE}"
    fi
}

is_pid_running() {
    local pid="$1"
    [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null
}

write_pid_file() {
    local pid="$1"
    if [ -n "${pid}" ]; then
        echo "${pid}" > "${PID_FILE}"
    fi
}

remove_pid_file() {
    rm -f "${PID_FILE}"
}

sync_pid_file() {
    local port_pid
    port_pid="$(get_port_pid)"

    if [ -n "${port_pid}" ]; then
        write_pid_file "${port_pid}"
        return 0
    fi

    local recorded_pid
    recorded_pid="$(get_recorded_pid)"
    if ! is_pid_running "${recorded_pid}"; then
        remove_pid_file
    fi
}

wait_for_startup() {
    local expected_pid="$1"
    local elapsed=0

    while [ "${elapsed}" -lt "${STARTUP_TIMEOUT}" ]; do
        local port_pid
        port_pid="$(get_port_pid)"

        if [ -n "${port_pid}" ]; then
            write_pid_file "${port_pid}"
            return 0
        fi

        if ! is_pid_running "${expected_pid}"; then
            break
        fi

        sleep 1
        elapsed=$((elapsed + 1))
    done

    return 1
}

start() {
    sync_pid_file

    local current_pid
    current_pid="$(get_port_pid)"
    if [ -n "${current_pid}" ]; then
        write_pid_file "${current_pid}"
        echo "Agent Console is already running on ${APP_HOST}:${APP_PORT} with PID ${current_pid}"
        echo "Log: ${LOG_FILE}"
        return 0
    fi

    echo "Starting Agent Console on ${APP_HOST}:${APP_PORT}..."
    cd "${SCRIPT_DIR}" || exit 1
    nohup "${PYTHON_BIN}" -m backend.main > "${LOG_FILE}" 2>&1 &
    local spawned_pid=$!

    if wait_for_startup "${spawned_pid}"; then
        local running_pid
        running_pid="$(get_port_pid)"
        echo "Started with PID ${running_pid}"
        echo "Log: ${LOG_FILE}"
        return 0
    fi

    echo "Failed to start Agent Console on port ${APP_PORT}" >&2
    if [ -f "${LOG_FILE}" ]; then
        echo "--- recent log ---" >&2
        tail -n 20 "${LOG_FILE}" >&2
    fi
    remove_pid_file
    return 1
}

stop() {
    sync_pid_file

    local port_pid
    port_pid="$(get_port_pid)"
    local recorded_pid
    recorded_pid="$(get_recorded_pid)"

    if [ -z "${port_pid}" ] && ! is_pid_running "${recorded_pid}"; then
        echo "Process not running"
        remove_pid_file
        return 0
    fi

    local target_pid="${port_pid:-${recorded_pid}}"
    kill "${target_pid}" 2>/dev/null || true

    local elapsed=0
    while [ "${elapsed}" -lt 10 ]; do
        if ! is_pid_running "${target_pid}" && [ -z "$(get_port_pid)" ]; then
            echo "Stopped PID ${target_pid}"
            remove_pid_file
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    kill -9 "${target_pid}" 2>/dev/null || true
    sleep 1

    if [ -z "$(get_port_pid)" ]; then
        echo "Stopped PID ${target_pid}"
        remove_pid_file
        return 0
    fi

    echo "Failed to stop Agent Console on port ${APP_PORT}" >&2
    return 1
}

status() {
    sync_pid_file

    local port_pid
    port_pid="$(get_port_pid)"
    if [ -n "${port_pid}" ]; then
        echo "Running with PID ${port_pid}"
        return 0
    fi

    echo "Not running"
    return 1
}

restart() {
    stop || return 1
    sleep 1
    start
}

case "$1" in
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    status)  status ;;
    *)       echo "Usage: $0 {start|stop|restart|status}" ;;
esac
