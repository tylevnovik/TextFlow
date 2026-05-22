from __future__ import annotations

import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

from app.service import TaskManager, build_handler


def test_task_manager_tracks_progress_and_result(monkeypatch):
    def fake_execute_action(action, payload, progress_callback=None):
        assert action == "demo-action"
        assert payload == {"value": 1}
        if progress_callback is not None:
            progress_callback(0.25, "正在准备")
            progress_callback(0.7, "处理中")
        return {"ok": True}

    monkeypatch.setattr("app.service.execute_action", fake_execute_action)
    manager = TaskManager(max_workers=1)

    try:
        ticket = manager.start("demo-action", {"value": 1})
        snapshot = manager.get(ticket["task_id"])
        assert snapshot is not None

        deadline = time.time() + 2
        while time.time() < deadline:
            snapshot = manager.get(ticket["task_id"])
            if snapshot and snapshot["status"] == "completed":
                break
            time.sleep(0.02)

        assert snapshot is not None
        assert snapshot["status"] == "completed"
        assert snapshot["progress"] == 1.0
        assert snapshot["result"] == {"ok": True}
    finally:
        manager.shutdown()


def test_http_service_exposes_cors_headers_for_browser_dev():
    manager = TaskManager(max_workers=1)
    httpd: ThreadingHTTPServer | None = None

    def shutdown_server() -> None:
        if httpd is not None:
            httpd.shutdown()

    handler = build_handler(manager, shutdown_server)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        host, port = httpd.server_address
        base_url = f"http://{host}:{port}"
        options_request = urllib.request.Request(f"{base_url}/tasks/start", method="OPTIONS")
        with urllib.request.urlopen(options_request, timeout=2) as response:
            assert response.status == 204
            assert response.headers["Access-Control-Allow-Origin"] == "*"
            assert response.headers["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS"
            assert response.headers["Access-Control-Allow-Headers"] == "Content-Type"

        with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
            assert response.status == 200
            assert response.headers["Access-Control-Allow-Origin"] == "*"
    finally:
        httpd.shutdown()
        thread.join(timeout=2)
        httpd.server_close()
        manager.shutdown()
