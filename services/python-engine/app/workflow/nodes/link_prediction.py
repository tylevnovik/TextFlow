from __future__ import annotations

from typing import Any

from ._common import analysis_passthrough_compiler, number_param, port, runtime, field, graph, slot, ui
from ._support import _report_node_progress, _table_rows_from_inputs_or_results


def _graph_ops():
    from ...analysis import graph as graph_ops_module
    return graph_ops_module


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "link_prediction",
        "title": "链接预测",
        "category": "analysis",
        "description": "预测网络中可能缺失的链接。",
        "inputs": [
            port("graph_node_table_in", "GraphNodeTable", "节点表输入"),
            port("graph_edge_table_in", "GraphEdgeTable", "边表输入"),
        ],
        "outputs": [
            port("link_prediction_table", "LinkPredictionTable", "链接预测表", result_bundle_key="link_prediction_table")
        ],
        "params": [
            number_param("link_prediction_top_n", "Top N 预测", 200),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.link_prediction",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((340, 230), (4920, 360), toolbox_order=480),
        "ui": ui(
            [
                field("number", "link_prediction_top_n", "Top N 预测", step=1),
            ],
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    graph_ops = _graph_ops()
    nodes = _table_rows_from_inputs_or_results(context, inputs, "graph_node_table_in", "graph_node_table")
    edges = _table_rows_from_inputs_or_results(context, inputs, "graph_edge_table_in", "graph_edge_table")
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.25, f"链接预测：读取 {len(nodes)} 个节点 / {len(edges)} 条边")
    rows = graph_ops.link_prediction_rows(nodes, edges, top_n=int(config.get("link_prediction_top_n", 200) or 200))
    _report_node_progress(context, node, 0.92, f"链接预测：生成 {len(rows)} 行")
    return {"link_prediction_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
