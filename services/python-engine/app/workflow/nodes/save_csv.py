from __future__ import annotations

from typing import Any

from ._support import _report_node_progress
from ._common import bool_param, field, graph, port, runtime, string_param, ui


def node_definition(_runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "save_csv",
        "title": "保存 CSV",
        "category": "output",
        "description": "把上游表格结果写成 CSV 文件。",
        "inputs": [port("table_in", "AnyTable", "表格输入", allow_multiple=True)],
        "outputs": [{**port("artifact", "ExportArtifact", "导出产物"), "artifact_kind": "export"}],
        "params": [
            string_param("file_prefix", "文件名前缀", "tables"),
            bool_param("export_csv", "启用 CSV 导出", True),
        ],
        "runtime": runtime(
            "export",
            "export.save_csv",
            cacheable=False,
            previewable=True,
            output_node=True,
            parallel_safe=True,
        ),
        "graph": graph((280, 210), (5340, 40), toolbox_order=410, starter_roles=["table_export_sink"]),
        "ui": ui(
            [
                field("text", "file_prefix", "文件名前缀"),
                field("switch", "export_csv", "启用 CSV 导出"),
            ],
            summary_template="CSV · {file_prefix}",
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    context.enable_export(export_csv=bool(config.get("export_csv", True)))


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    tables = inputs.get("table_in") or []
    if not isinstance(tables, list):
        tables = [tables]
    _report_node_progress(context, node, 0.92, f"保存 CSV：接收 {len(tables)} 行")
    return {"artifact": {"kind": "csv", "count": len(tables)}}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
