from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.api.service import TaskManager, create_app


def test_task_manager_tracks_progress_and_result(monkeypatch):
    def fake_execute_action(action, payload, progress_callback=None):
        assert action == "demo-action"
        assert payload == {"value": 1}
        if progress_callback is not None:
            progress_callback(0.25, "正在准备")
            progress_callback(0.7, "处理中")
        return {"ok": True}

    monkeypatch.setattr("app.api.service.execute_action", fake_execute_action)
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


def test_fastapi_service_exposes_cors_headers_for_browser_dev():
    manager = TaskManager(max_workers=1)
    app = create_app(task_manager=manager)
    try:
        with TestClient(app) as client:
            response = client.options(
                "/tasks/start",
                headers={
                    "Origin": "http://127.0.0.1:5174",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )
            assert response.status_code == 200
            assert response.headers["Access-Control-Allow-Origin"] == "*"
            assert "GET" in response.headers["Access-Control-Allow-Methods"]
            assert "POST" in response.headers["Access-Control-Allow-Methods"]
            assert "OPTIONS" in response.headers["Access-Control-Allow-Methods"]
            assert "Content-Type" in response.headers["Access-Control-Allow-Headers"]

            health = client.get("/health", headers={"Origin": "http://127.0.0.1:5174"})
            assert health.status_code == 200
            assert health.json() == {"status": "ok"}
            assert health.headers["Access-Control-Allow-Origin"] == "*"
    finally:
        manager.shutdown()


def test_fastapi_task_endpoints_queue_and_poll(monkeypatch):
    def fake_execute_action(action, payload, progress_callback=None):
        if progress_callback is not None:
            progress_callback(0.5, "半程完成", {"stage": "demo"})
        return {"score": float("nan"), "action": action, "payload": payload}

    monkeypatch.setattr("app.api.service.execute_action", fake_execute_action)
    manager = TaskManager(max_workers=1)
    app = create_app(task_manager=manager)

    try:
        with TestClient(app) as client:
            ticket_response = client.post("/tasks/start", json={"action": "demo-action", "payload": {"value": 7}})
            assert ticket_response.status_code == 200
            task_id = ticket_response.json()["task_id"]

            deadline = time.time() + 2
            snapshot = None
            while time.time() < deadline:
                response = client.get(f"/tasks/{task_id}")
                assert response.status_code == 200
                snapshot = response.json()
                if snapshot["status"] == "completed":
                    break
                time.sleep(0.02)

            assert snapshot is not None
            assert snapshot["status"] == "completed"
            assert snapshot["detail"] == {"stage": "demo"}
            assert snapshot["result"] == {"score": None, "action": "demo-action", "payload": {"value": 7}}

            missing = client.get("/tasks/not-found")
            assert missing.status_code == 404
            assert missing.json() == {"error": "task not found"}
    finally:
        manager.shutdown()
