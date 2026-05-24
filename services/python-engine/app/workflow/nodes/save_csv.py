from __future__ import annotations

from typing import Any

from ._support import _report_node_progress
from ._common import port, runtime, string_param


def node_definition(_runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "save_csv",
        "title": "保存 CSV",
        "category": "output",
        "description": "把上游表格结果写成 CSV 文件。",
        "inputs": [port("table_in", "AnyTable", "表格输入", allow_multiple=True)],
        "outputs": [{**port("artifact", "ExportArtifact", "导出产物"), "artifact_kind": "export"}],
        "params": [string_param("file_prefix", "文件名前缀", "tables")],
        "runtime": runtime(
            "export",
            "export.save_csv",
            cacheable=False,
            previewable=True,
            output_node=True,
            parallel_safe=True,
        ),
    }


def compile_node(context: Any, _node: dict[str, Any]) -> None:
    context.enable_export(export_csv=True)


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
