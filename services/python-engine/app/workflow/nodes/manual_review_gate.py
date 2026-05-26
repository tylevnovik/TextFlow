from __future__ import annotations

from typing import Any

from ._common import enum_param, string_param, port, runtime, node_definition_from_base, passthrough_compiler, field, graph, slot, ui
from ._support import (
    _control_rows_from_inputs,
    _report_node_progress,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    base = {
        "type": "manual_review_gate",
        "title": "人工复核门禁",
        "category": "process",
        "description": "等待指定复核任务达到目标状态后再放行下游表格。",
        "inputs": [
            port("payload_in", "AnyTable", "待复核表格")
        ],
        "outputs": [
            port("approved_payload", "AnyTable", "已放行表格"),
            port("blocked_payload", "AnyTable", "待复核表格"),
            port(
                "review_gate_summary",
                "AnyTable",
                "复核门禁摘要",
                result_bundle_key="review_gate_summary",
            ),
        ],
        "params": [
            string_param("review_id", "复核任务", "", ""),
            enum_param(
                "required_status",
                "放行状态",
                "resolved",
                [("resolved", "已解决"), ("open", "打开")],
                "",
            ),
            enum_param(
                "on_missing",
                "找不到任务时",
                "block",
                [("block", "拦截"), ("pass", "放行")],
                "",
            ),
        ],
        "runtime": runtime(
            "resource",
            "control.manual_review_gate",
            cacheable=False,
            previewable=True,
            output_node=False,
        ),
        "graph": graph((360, 260), (5340, 680), toolbox_order=260),
        "ui": ui(
            [
                slot("review_task_selector"),
            ],
        ),
    }
    return node_definition_from_base(base, runtime_profile, None)


def compile_node(context: Any, node: dict[str, Any]) -> None:
    passthrough_compiler(context, node)


def _find_review_task(manifest: dict[str, Any], review_id: str) -> dict[str, Any] | None:
    tasks = manifest.get("review_tasks")
    if not isinstance(tasks, list):
        return None
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_review_id = str(task.get("review_id") or task.get("id") or "").strip()
        if task_review_id == review_id:
            return task
    return None


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    payload_rows = _control_rows_from_inputs(inputs, "payload_in", "table_in", "corpus_in")
    review_id = str(config.get("review_id") or config.get("task_id") or "").strip()
    required_status = str(config.get("required_status") or "resolved").strip().lower()
    on_missing = str(config.get("on_missing") or "block").strip().lower()
    _report_node_progress(context, node, 0.25, f"人工审核闸门：读取 {len(payload_rows)} 条待审记录")
    manifest = getattr(context, "manifest", {})
    task = _find_review_task(manifest, review_id) if isinstance(manifest, dict) and review_id else None
    current_status = str(task.get("status") or "missing").strip().lower() if isinstance(task, dict) else "missing"
    approved = current_status == required_status or (task is None and on_missing == "pass")
    waiting = not approved
    _report_node_progress(context, node, 0.72, f"人工审核闸门：状态 {current_status}")
    review_gate_summary = [
        {
            "review_id": review_id,
            "required_status": required_status,
            "status": current_status,
            "waiting": waiting,
            "input_count": len(payload_rows),
        }
    ]
    return {
        "waiting": waiting,
        "approved_payload": payload_rows if approved else [],
        "blocked_payload": [] if approved else payload_rows,
        "review_gate_summary": review_gate_summary,
    }


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
