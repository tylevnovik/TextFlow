from __future__ import annotations

from typing import Any

from ._common import export_results_compiler, port, runtime
from ._support import _report_node_progress


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "export_results",
        "title": "导出结果",
        "category": "legacy",
        "description": "旧版兼容节点：已拆分为多个输出节点。",
        "hidden_from_toolbox": True,
        "inputs": [
            port("analysis_bundle_in", "AnalysisBundle", "分析结果"),
            port("audit_table_in", "AuditTable", "审计表"),
        ],
        "outputs": [
            port("export_bundle", "ExportBundle", "导出包")
        ],
        "params": [],
        "runtime": runtime(
            "export",
            "legacy.export_results",
            cacheable=False,
            previewable=False,
            output_node=True,
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    export_results_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_bundle = inputs.get("analysis_bundle_in") or {}
    audit_rows = inputs.get("audit_table_in") or []
    bundle_count = len(analysis_bundle) if isinstance(analysis_bundle, dict) else 0
    audit_count = len(audit_rows) if isinstance(audit_rows, list) else 0
    _report_node_progress(context, node, 0.35, f"导出旧版结果：读取 {bundle_count} 组结果 / {audit_count} 条审计")
    if isinstance(analysis_bundle, dict):
        for key, value in analysis_bundle.items():
            if key in context.result_bundle and isinstance(value, list):
                context.result_bundle[key] = value
    if isinstance(audit_rows, list):
        context.result_bundle["audit_table"] = audit_rows
    _report_node_progress(context, node, 0.92, f"导出旧版结果：汇总 {len(context.result_bundle)} 个结果集")
    return {"artifact": {"kind": "legacy_export", "count": len(context.result_bundle)}}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
