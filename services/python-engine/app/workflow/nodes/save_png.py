from __future__ import annotations

from copy import deepcopy
from typing import Any

from ._support import _report_node_progress
from ._common import number_param, port, runtime, string_param


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    export = deepcopy((runtime_profile or {}).get("export") or {})
    return {
        "type": "save_png",
        "title": "保存 PNG",
        "category": "output",
        "description": "把上游分析结果按默认图表规则渲染为 PNG。",
        "inputs": [port("render_in", "AnyRenderable", "图像输入", allow_multiple=True)],
        "outputs": [{**port("artifact", "ExportArtifact", "导出产物"), "artifact_kind": "export"}],
        "params": [
            string_param("file_prefix", "文件名前缀", "charts"),
            number_param("chart_dpi", "PNG 分辨率（DPI）", int(export.get("chart_dpi", 320))),
        ],
        "runtime": runtime(
            "export",
            "export.save_png",
            cacheable=False,
            previewable=True,
            output_node=True,
            parallel_safe=True,
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    chart_dpi = int(config.get("chart_dpi") or context.export_config.get("chart_dpi", 320))
    context.enable_export(export_png=True, chart_dpi=chart_dpi)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    renderables = inputs.get("render_in") or []
    if not isinstance(renderables, list):
        renderables = [renderables]
    _report_node_progress(context, node, 0.92, f"保存 PNG：接收 {len(renderables)} 个可视化对象")
    return {"artifact": {"kind": "png", "count": len(renderables)}}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
