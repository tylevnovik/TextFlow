from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Any, Callable
from uuid import uuid4

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from .actions.dispatcher import execute_action
from ..domain.defaults import json_ready, utc_now_iso


class TextFlowJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(json_ready(content), ensure_ascii=False).encode("utf-8")


class StartTaskRequest(BaseModel):
    action: str = Field(default="")
    payload: dict[str, Any] | None = None


class TaskManager:
    def __init__(self, max_workers: int = 1) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="textflow-engine")
        self._lock = threading.Lock()
        self._tasks: dict[str, dict[str, Any]] = {}

    def start(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        task_id = f"task-{uuid4().hex}"
        task = {
            "task_id": task_id,
            "action": action,
            "status": "pending",
            "progress": 0.0,
            "message": "等待后台处理",
            "detail": None,
            "result": None,
            "error": None,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
        with self._lock:
            self._tasks[task_id] = task
        self._executor.submit(self._run_task, task_id, action, payload or {})
        return {"task_id": task_id}

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            return dict(task)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _update(self, task_id: str, **patch: Any) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            if "detail" in patch and patch["detail"] is None and task.get("detail") is not None:
                patch.pop("detail")
            task.update(patch)
            task["updated_at"] = utc_now_iso()

    def _run_task(self, task_id: str, action: str, payload: dict[str, Any]) -> None:
        self._update(task_id, status="running", progress=0.02, message="后台已开始处理")

        def progress_callback(progress: float, message: str, detail: dict[str, Any] | None = None) -> None:
            bounded = max(0.0, min(1.0, float(progress)))
            self._update(task_id, status="running", progress=bounded, message=message, detail=detail)

        try:
            result = execute_action(action, payload, progress_callback)
        except Exception as error:  # pragma: no cover - defensive fallback
            self._update(task_id, status="failed", progress=1.0, message="处理失败", error=str(error))
            return

        self._update(task_id, status="completed", progress=1.0, message="处理完成", result=result)


def create_app(
    task_manager: TaskManager | None = None,
    shutdown_server: Callable[[], None] | None = None,
) -> FastAPI:
    owns_task_manager = task_manager is None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manager = task_manager or TaskManager(max_workers=1)
        app.state.task_manager = manager
        app.state.shutdown_server = shutdown_server or (lambda: None)
        try:
            yield
        finally:
            if owns_task_manager:
                manager.shutdown()

    app = FastAPI(
        title="TextFlow Python Engine",
        version="0.1.1",
        default_response_class=TextFlowJSONResponse,
        lifespan=lifespan,
    )
    # The service only binds to localhost. CORS lets the Vite dev server
    # exercise the real engine from a browser smoke test.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    def manager_from_request(request: Request) -> TaskManager:
        manager = getattr(request.app.state, "task_manager", None)
        if manager is None:
            raise RuntimeError("task manager is not initialized")
        return manager

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_request: Request, exc: StarletteHTTPException) -> TextFlowJSONResponse:
        detail = exc.detail
        if isinstance(detail, dict):
            payload = detail
        else:
            message = str(detail).lower() if detail else "not found"
            payload = {"error": message}
        return TextFlowJSONResponse(payload, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/tasks/{task_id}")
    def get_task(task_id: str, request: Request) -> dict[str, Any]:
        task = manager_from_request(request).get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail={"error": "task not found"})
        return task

    @app.post("/tasks/start")
    def start_task(request: Request, request_body: StartTaskRequest | None = None) -> dict[str, str]:
        body = request_body or StartTaskRequest()
        return manager_from_request(request).start(body.action, body.payload)

    @app.post("/shutdown")
    def shutdown(background_tasks: BackgroundTasks, request: Request) -> dict[str, str]:
        background_tasks.add_task(request.app.state.shutdown_server)
        return {"status": "shutting_down"}

    return app


app = create_app()


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    server_box: dict[str, uvicorn.Server] = {}

    def shutdown_server() -> None:
        server = server_box.get("server")
        if server is not None:
            server.should_exit = True

    server_app = create_app(shutdown_server=shutdown_server)
    config = uvicorn.Config(
        server_app,
        host=host,
        port=port,
        access_log=False,
        http="h11",
        lifespan="on",
        log_level="warning",
        loop="asyncio",
        ws="none",
    )
    server = uvicorn.Server(config)
    server_box["server"] = server
    server.run()

