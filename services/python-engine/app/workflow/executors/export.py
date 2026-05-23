from __future__ import annotations

from .support import *  # noqa: F401,F403

def execute_save_csv(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    tables = inputs.get("table_in") or []
    if not isinstance(tables, list):
        tables = [tables]
    _report_node_progress(context, node, 0.92, f"保存 CSV：接收 {len(tables)} 行")
    return {"artifact": {"kind": "csv", "count": len(tables)}}


def execute_save_xlsx(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    tables = inputs.get("table_in") or []
    if not isinstance(tables, list):
        tables = [tables]
    _report_node_progress(context, node, 0.92, f"保存 XLSX：接收 {len(tables)} 行")
    return {"artifact": {"kind": "xlsx", "count": len(tables)}}


def execute_save_png(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    renderables = inputs.get("render_in") or []
    if not isinstance(renderables, list):
        renderables = [renderables]
    _report_node_progress(context, node, 0.92, f"保存 PNG：接收 {len(renderables)} 个可视化对象")
    return {"artifact": {"kind": "png", "count": len(renderables)}}


def execute_save_html_report(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    report_inputs = inputs.get("report_in") or []
    if not isinstance(report_inputs, list):
        report_inputs = [report_inputs]
    _report_node_progress(context, node, 0.92, f"保存 HTML 报告：接收 {len(report_inputs)} 组内容")
    return {"artifact": {"kind": "html", "count": len(report_inputs)}}


def execute_legacy_passthrough(_context: Any, _node: dict[str, Any], _inputs: dict[str, Any]) -> dict[str, Any]:
    return {}

