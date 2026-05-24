from __future__ import annotations

from copy import deepcopy
from typing import Any

from ._support import _report_node_progress
from ._common import bool_param, port, runtime, string_param


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    export = deepcopy((runtime_profile or {}).get("export") or {})
    return {
        "type": "save_html_report",
        "title": "保存 HTML 报告",
        "category": "output",
        "description": "根据上游分析结果生成 HTML 报告。",
        "inputs": [port("report_in", "AnyAnalysisResult", "报告输入", allow_multiple=True)],
        "outputs": [{**port("artifact", "ExportArtifact", "导出产物"), "artifact_kind": "export"}],
        "params": [
            string_param("file_prefix", "文件名前缀", "report"),
            bool_param("include_audit", "附带审计摘要", bool(export.get("include_audit", True))),
        ],
        "runtime": runtime(
            "export",
            "export.save_html_report",
            cacheable=False,
            previewable=True,
            output_node=True,
            parallel_safe=True,
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    include_audit = bool(config.get("include_audit", context.export_config.get("include_audit", True)))
    context.enable_export(export_html_report=True, include_audit=include_audit)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    report_inputs = inputs.get("report_in") or []
    if not isinstance(report_inputs, list):
        report_inputs = [report_inputs]
    _report_node_progress(context, node, 0.92, f"保存 HTML 报告：接收 {len(report_inputs)} 组内容")
    return {"artifact": {"kind": "html", "count": len(report_inputs)}}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
