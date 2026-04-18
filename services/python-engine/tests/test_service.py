from __future__ import annotations

import time

from app.service import TaskManager


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
