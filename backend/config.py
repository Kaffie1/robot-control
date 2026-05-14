import os
from pathlib import Path


def load_env_file(env_path: str | Path) -> None:
    path = Path(env_path)
    if not path.exists() or not path.is_file():
        return
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        if not normalized_key:
            continue
        normalized_value = value.strip()
        if len(normalized_value) >= 2 and normalized_value[0] == normalized_value[-1] and normalized_value[0] in {"'", '"'}:
            normalized_value = normalized_value[1:-1]
        os.environ.setdefault(normalized_key, normalized_value)


BASE_DIR = Path(__file__).resolve().parent.parent
load_env_file(BASE_DIR / ".env")

APP_HOST = str(os.getenv("APP_HOST") or "0.0.0.0").strip() or "127.0.0.1"
APP_PORT = int(str(os.getenv("APP_PORT") or "8000").strip() or "8000")
OPENAI_API_KEY = str(os.getenv("OPENAI_API_KEY") or "").strip()
OPENAI_BASE_URL = str(os.getenv("OPENAI_BASE_URL") or "").strip()
OPENAI_CHAT_MODEL = str(os.getenv("OPENAI_CHAT_MODEL") or "gpt-4.1-mini").strip() or "gpt-4.1-mini"
OPENAI_CHAT_TEMPERATURE = float(str(os.getenv("OPENAI_CHAT_TEMPERATURE") or "0.2").strip() or "0.2")
OPENAI_ENABLE_REASONING_SPLIT = str(os.getenv("OPENAI_ENABLE_REASONING_SPLIT") or "").strip().lower() in {"1", "true", "yes", "on"}
OPENAI_THINK = str(os.getenv("OPENAI_THINK") or "").strip()

STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
FAULT_CONFIG_DIR = BASE_DIR / "config"
LOCAL_MODULE_DIR = BASE_DIR / "module"
DATA_DIR = BASE_DIR / "data"
RUNTIME_DIR = BASE_DIR / ".runtime"
DB_PATH = DATA_DIR / "operations.db"
CONNECTION_CACHE_PATH = DATA_DIR / "connection_cache.json"
DEPLOY_CONFIG_PATH = STATIC_DIR / "page_configs" / "deploy.json"
FAULT_PLAYBOOKS_PATH = FAULT_CONFIG_DIR / "fault_playbooks.yaml"
FAULT_PROMPT_TEMPLATE_PATH = FAULT_CONFIG_DIR / "fault_prompt_template.yaml"
FAULT_REPORT_TEMPLATE_PATH = FAULT_CONFIG_DIR / "fault_report_template.yaml"
FAULT_TOOLS_PATH = FAULT_CONFIG_DIR / "fault_tools.yaml"
FAULT_TRACE_LOG_PATH = RUNTIME_DIR / "fault_diagnosis.log"
SESSION_COOKIE = "robot_upgrade_sid"
MAX_CONNECTION_CACHE_ITEMS = 8
MAX_TASK_ITEMS = 5
SESSION_IDLE_TIMEOUT_SECONDS = 30 * 60
SESSION_CLEANUP_INTERVAL_SECONDS = 60

PACKAGE_DEPLOY_DIR = "/tmp"
MODULE_DEPLOY_ROOT = "/home/naviai/navi_project/.dists"
MODULE_DEPLOY_PROJECT_ROOT = "/home/naviai/navi_project"
ROS_COMPOSE_PROJECT_ROOT = "/home/naviai/navi_project"
ROSBRIDGE_SERVICE_NAME = "rosbridge"
MODULE_DEPLOY_NAMES = [
    "chassis",
    "perception",
    "sensor_lidar",
    "navigation",
    "map_server",
    "nviz",
]
DOWNLOAD_TMP_DIR = Path("/tmp")
CHFS_HOST = "10.51.33.211"
CHFS_PORT = 10000
CHFS_USER = "admin"
CHFS_PASSWORD = "admin"
UPLOAD_CHUNK_SIZE = 1024 * 1024
DEFAULT_DEPLOY_CONFIG = {
    "package": {
        "probe_command_template": "chmod +x {deb_path} && {deb_path} --get_robot_type",
        "install_template": "chmod +x {deb_path} && {deb_path} -- --device_type={device_type} --force --robot_type={machine_type} --user={target_username} --password={target_password}",
        "start_command": "",
        "health_command": (
            "test -s ~/.zj_humanoid/version.json && ("
            "(command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet zj_humanoid) || "
            "(command -v sudo >/dev/null 2>&1 && sudo -n systemctl is-active --quiet zj_humanoid) || "
            "test -L ~/navi_project || "
            "test -L ~/zj_humanoid || "
            "(command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -q .)"
            ")"
        ),
        "rollback_template": "",
        "auto_rollback": False,
        "machine_options": [
            {
                "value": "H1",
                "label": "H1",
            },
            {
                "value": "U1",
                "label": "U1",
            },
            {
                "value": "U2_WA1",
                "label": "U2_WA1",
            },
            {
                "value": "I2",
                "label": "I2",
            },
            {
                "value": "WA1",
                "label": "WA1",
            },
            {
                "value": "WA1_400L",
                "label": "WA1_400L",
            },
            {
                "value": "WA1_400K",
                "label": "WA1_400K",
            },
            {
                "value": "WA2",
                "label": "WA2",
            },
            {
                "value": "WA2_LS",
                "label": "WA2_LS",
            },
            {
                "value": "WA2_TY20",
                "label": "WA2_TY20",
            },
            {
                "value": "WA2_L",
                "label": "WA2_L",
            },
            {
                "value": "U1_WA1",
                "label": "U1_WA1",
            },
        ],
    },
    "module": {
        "probe_command_template": "",
        "install_template": (
            'bash -ic "export COMPOSE_PROFILES={compose_profiles}; '
            'export DISPLAY=\\${DISPLAY:-127.0.0.1:99.0}; '
            'export ROBOT_MODEL=\\$COMPOSE_PROFILES; '
            'if [ \\"\\$COMPOSE_PROFILES\\" = \\"rx\\" ]; then '
            'export ROS_MASTER_URI=http://192.168.217.100:11311; '
            'else export ROS_MASTER_URI=http://192.168.217.1:11311; fi; '
            'export ROS_IP=192.168.217.100; '
            'echo ROS_MASTER_URI=\\$ROS_MASTER_URI; '
            'echo ROS_IP=\\$ROS_IP; '
            'echo COMPOSE_PROFILES=\\$COMPOSE_PROFILES; '
            f"cd {MODULE_DEPLOY_PROJECT_ROOT} && "
            'docker compose down {module_name} && '
            'docker compose up -d {module_name}"'
        ),
        "start_command": "",
        "health_command": "",
        "rollback_template": "",
        "auto_rollback": False,
        "machine_options": [
            {
                "value": module_name,
                "label": module_name,
            }
            for module_name in MODULE_DEPLOY_NAMES
        ],
    },
}
PROJECT_ROOT_CANDIDATES = [
    ("/home/naviai/navi_project", "项目目录 /home/naviai/navi_project"),
    ("~/navi_project", "机器人 ~/navi_project"),
]
LEGACY_DB_PATH = BASE_DIR / "operations.db"
LEGACY_CONNECTION_CACHE_PATH = BASE_DIR / "connection_cache.json"
