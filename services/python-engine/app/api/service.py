from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from uuid import uuid4

from .actions.dispatcher import execute_action
from ..defaults import json_ready, utc_now_iso


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


def build_handler(task_manager: TaskManager, shutdown_server: Callable[[], None]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return

            if self.path.startswith("/tasks/"):
                task_id = self.path.rsplit("/", 1)[-1]
                task = task_manager.get(task_id)
                if task is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "task not found"})
                    return
                self._send_json(HTTPStatus.OK, task)
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers()
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/tasks/start":
                payload = self._read_json()
                ticket = task_manager.start(payload.get("action", ""), payload.get("payload"))
                self._send_json(HTTPStatus.OK, ticket)
                return

            if self.path == "/shutdown":
                self._send_json(HTTPStatus.OK, {"status": "shutting_down"})
                threading.Thread(target=shutdown_server, daemon=True).start()
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def _read_json(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                return {}
            raw = self.rfile.read(content_length)
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(json_ready(payload), ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_cors_headers(self) -> None:
            # The service only binds to localhost. CORS lets the Vite dev server
            # exercise the real engine from a browser smoke test.
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    task_manager = TaskManager(max_workers=1)
    httpd: ThreadingHTTPServer | None = None

    def shutdown_server() -> None:
        if httpd is not None:
            httpd.shutdown()

    handler = build_handler(task_manager, shutdown_server)
    httpd = ThreadingHTTPServer((host, port), handler)
    httpd.daemon_threads = True

    try:
        httpd.serve_forever(poll_interval=0.2)
    finally:
        task_manager.shutdown()
        httpd.server_close()

