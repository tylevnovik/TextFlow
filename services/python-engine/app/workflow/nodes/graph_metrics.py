from __future__ import annotations

from typing import Any

from ._common import analysis_passthrough_compiler, port, runtime, field, graph, slot, ui
from ._support import _report_node_progress, _table_rows_from_inputs_or_results


def _graph_ops():
    from ...analysis import graph as graph_ops_module
    return graph_ops_module


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "graph_metrics",
        "title": "网络指标",
        "category": "analysis",
        "description": "计算 PageRank、介数中心性等网络指标。",
        "inputs": [
            port("graph_node_table_in", "GraphNodeTable", "节点表输入"),
            port("graph_edge_table_in", "GraphEdgeTable", "边表输入"),
        ],
        "outputs": [
            port("graph_metric_table", "GraphMetricTable", "网络指标表", result_bundle_key="graph_metric_table")
        ],
        "params": [],
        "runtime": runtime(
            "analysis",
            "analysis.graph_metrics",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((320, 210), (4500, 1000), toolbox_order=440),
        "ui": ui([]),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    graph_ops = _graph_ops()
    nodes = _table_rows_from_inputs_or_results(context, inputs, "graph_node_table_in", "graph_node_table")
    edges = _table_rows_from_inputs_or_results(context, inputs, "graph_edge_table_in", "graph_edge_table")
    _report_node_progress(context, node, 0.25, f"图指标：读取 {len(nodes)} 个节点 / {len(edges)} 条边")
    rows = graph_ops.graph_metric_rows(nodes, edges)
    _report_node_progress(context, node, 0.92, f"图指标：生成 {len(rows)} 行")
    return {"graph_metric_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
