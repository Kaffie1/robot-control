from fastapi.templating import Jinja2Templates

from .config import CONNECTION_CACHE_PATH, DB_PATH, DEFAULT_DEPLOY_CONFIG, DEPLOY_CONFIG_PATH, TEMPLATE_DIR
from .stores import ConnectionCacheStore, DeployConfigStore, HistoryStore, SessionStore, TaskManager, UploadProgressManager
from .utils import migrate_legacy_runtime_files


migrate_legacy_runtime_files()
history_store = HistoryStore(DB_PATH)
task_manager = TaskManager(history_store)
session_store = SessionStore()
upload_progress_manager = UploadProgressManager()
connection_cache_store = ConnectionCacheStore(CONNECTION_CACHE_PATH)
deploy_config_store = DeployConfigStore(DEPLOY_CONFIG_PATH, DEFAULT_DEPLOY_CONFIG)
deploy_config_store.ensure_exists()
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
