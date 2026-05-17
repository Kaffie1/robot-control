"""Minimal API for agent-only mode."""

import asyncio
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

# Load .env file
_dotenv_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_dotenv_path)

from .agent.orchestration import run_fault_chat_graph
from .agent.orchestration.live_playbook_state import build_matched_playbook_payload_by_id
from .agent.orchestration.live_playbook_state import clear_live_playbook_state, get_live_playbook_state, reset_live_playbook_execution, stream_live_playbook_events
from .agent.orchestration.router_nodes import load_catalog_node, resolve_playbook_route
from .config import APP_HOST, APP_PORT, STATIC_DIR, TEMPLATES_DIR
from .errors import ApiError
from .utils import get_fault_logger

logger_ = get_fault_logger()


def _build_asset_version(*paths: Path) -> str:
    import hashlib

    digest = hashlib.md5()
    for path in paths:
        try:
            digest.update(path.read_bytes())
        except OSError:
            continue
    return digest.hexdigest()[:10]


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Console", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "error": exc.message, **exc.payload}
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc):
        errors = exc.errors()
        message = errors[0].get("msg", "请求参数无效") if errors else "请求参数无效"
        return JSONResponse(status_code=400, content={"ok": False, "error": message})

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"ok": False, "error": str(exc.detail)}
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})

    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        asset_version = _build_asset_version(
            Path(STATIC_DIR) / "js" / "chat.js",
            Path(STATIC_DIR) / "css" / "chat.css",
            Path(TEMPLATES_DIR) / "index.html",
        )
        response = templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "request": request,
                "defaults": {},
                "connected": False,
                "saved_connections": [],
                "package_machine_options": [],
                "module_machine_options": [],
                "asset_version": asset_version,
            },
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @app.post("/api/chat")
    async def api_chat(request: Request):
        body = await request.json()
        # 用户当前的输入
        message = str(body.get("message") or "").strip()
        # 继续执行的上下文
        continuation = body.get("continuation")
        # 前端的对话历史，用于提供给模型参考，帮助模型更好地理解上下文
        history = body.get("history")
        # 用户选择的playbook路由信息
        route_selection = body.get("route_selection")
        if continuation is not None and not isinstance(continuation, dict):
            return JSONResponse(content={"ok": False, "error": "continuation 必须是对象"}, status_code=400)
        if history is not None and not isinstance(history, list):
            return JSONResponse(content={"ok": False, "error": "history 必须是数组"}, status_code=400)
        if route_selection is not None and not isinstance(route_selection, dict):
            return JSONResponse(content={"ok": False, "error": "route_selection 必须是对象"}, status_code=400)
        if continuation is None and not message:
            return JSONResponse(content={"ok": False, "error": "消息内容不能为空"}, status_code=400)
        if isinstance(continuation, dict):
            user_message = str(continuation.get("user_message") or "").strip()
            if not user_message:
                return JSONResponse(content={"ok": False, "error": "continuation 缺少 user_message"}, status_code=400)
            tool_context: dict[str, Any] = dict(continuation.get("tool_context") or {})
        else:
            user_message = message
            tool_context = {}
        route_selection_payload = build_matched_playbook_payload_by_id(str((route_selection or {}).get("playbook_id") or "").strip())
        continuation_kind = str((continuation or {}).get("kind") or "").strip() if isinstance(continuation, dict) else ""
        logger_.info(
            "Chat 执行前状态重置 | has_route_selection=%s | playbook_id=%s | has_root=%s | continuation_kind=%s",
            bool(route_selection),
            str((route_selection or {}).get("playbook_id") or "").strip(),
            bool(isinstance(route_selection_payload, dict) and isinstance(route_selection_payload.get("root"), dict)),
            continuation_kind or "-",
        )
        # 如果用户选择了新的 playbook 路由，或者当前的继续执行上下文不是来自于 playbook 确认（即用户在确认某个 playbook 的执行），
        # 则重置当前的 playbook 执行状态，准备开始新的 playbook 执行流程；否则继续沿用当前的执行状态，继续执行后续步骤。
        if route_selection_payload:
            reset_live_playbook_execution(playbook=route_selection_payload)
        else:
            clear_live_playbook_state()
        # 调用核心的对话执行函数，传入用户消息、对话历史、继续执行上下文、用户选择的 playbook 路由等信息，得到模型的响应结果
        result = await asyncio.to_thread(
            run_fault_chat_graph,
            user_message,
            runtime_context={
                "connected": False,
            },
            tool_context=tool_context,
            conversation_history=[
                {
                    "role": str(item.get("role") or "").strip(),
                    "content": str(item.get("content") or "").strip(),
                }
                for item in (history or [])
                if isinstance(item, dict)
            ],
            # 继续执行的上下文
            resume_continuation=continuation if isinstance(continuation, dict) else None,
            # 用户确认的信息
            confirmation_response=message if continuation_kind == "playbook_confirmation" else "",
            # 用户选择的 playbook 路由信息，如果继续执行的上下文来自于 playbook 确认，则沿用当前的
            prefetched_playbook_id=str((route_selection or {}).get("playbook_id") or "").strip(),
            prefetched_playbook_title=str((route_selection or {}).get("playbook_title") or "").strip(),
            prefetched_reason=str((route_selection or {}).get("reason") or "").strip(),
        )
        logger_.info("Chat response: %s", result.get("message") or "")
        return {"ok": True, **result}

    @app.post("/api/chat/route")
    async def api_chat_route(request: Request):
        body = await request.json()
        message = str(body.get("message") or "").strip()
        continuation = body.get("continuation")
        if continuation is not None and not isinstance(continuation, dict):
            return JSONResponse(content={"ok": False, "error": "continuation 必须是对象"}, status_code=400)
        if not continuation and not message:
            return JSONResponse(content={"ok": False, "error": "消息内容不能为空"}, status_code=400)
        route_state = {
            **load_catalog_node({}),
            "user_message": message,
            "resume_continuation": continuation if isinstance(continuation, dict) else None,
        }
        route_result = await asyncio.to_thread(resolve_playbook_route, route_state, publish=True)
        playbook_id = str(route_result.get("selected_playbook_id") or "").strip()
        playbook_title = str(route_result.get("selected_playbook_title") or "").strip()
        reason = str(route_result.get("reason") or "").strip()
        playbook_payload = build_matched_playbook_payload_by_id(playbook_id)
        logger_.info(
            "路由接口返回 | playbook_id=%s | title=%s | has_root=%s",
            playbook_id,
            playbook_title,
            bool(isinstance(playbook_payload, dict) and isinstance(playbook_payload.get("root"), dict)),
        )
        return {
            "ok": True,
            "route_selection": {
                "playbook_id": playbook_id,
                "playbook_title": playbook_title,
                "reason": reason,
            },
            "playbook": playbook_payload,
        }

    @app.get("/api/chat/state")
    async def api_chat_state(request: Request):
        raw_since_version = request.query_params.get("since_version", "0")
        try:
            since_version = max(int(raw_since_version), 0)
        except ValueError:
            since_version = 0
        return {"ok": True, **get_live_playbook_state(since_version=since_version)}

    @app.get("/api/chat/events")
    async def api_chat_events(request: Request):
        raw_since_version = request.query_params.get("since_version", "0")
        try:
            since_version = max(int(raw_since_version), 0)
        except ValueError:
            since_version = 0
        return StreamingResponse(
            stream_live_playbook_events(since_version=since_version),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/chat/reset")
    async def api_chat_reset():
        clear_live_playbook_state()
        return {"ok": True}

    return app


app = create_app()


def main() -> None:
    import uvicorn
    print(f"Agent Console 已启动: http://{APP_HOST}:{APP_PORT}")
    uvicorn.run(app, host=APP_HOST, port=APP_PORT, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
