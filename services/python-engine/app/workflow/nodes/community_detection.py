from __future__ import annotations

from typing import Any

from ._common import analysis_passthrough_compiler, enum_param, port, runtime
from ._support import _report_node_progress, _table_rows_from_inputs_or_results


def _graph_ops():
    from ...analysis import graph as graph_ops_module
    return graph_ops_module


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "community_detection",
        "title": "社区发现",
        "category": "analysis",
        "description": "检测网络中的社区结构。",
        "inputs": [
            port("graph_node_table_in", "GraphNodeTable", "节点表输入"),
            port("graph_edge_table_in", "GraphEdgeTable", "边表输入"),
        ],
        "outputs": [
            port("community_table", "CommunityTable", "社区表", result_bundle_key="community_table")
        ],
        "params": [
            enum_param("community_method", "社区方法", "greedy_modularity", [
                ("greedy_modularity", "贪心模块度"),
                ("label_propagation", "标签传播"),
            ]),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.community_detection",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    graph_ops = _graph_ops()
    nodes = _table_rows_from_inputs_or_results(context, inputs, "graph_node_table_in", "graph_node_table")
    edges = _table_rows_from_inputs_or_results(context, inputs, "graph_edge_table_in", "graph_edge_table")
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.25, f"社区发现：读取 {len(nodes)} 个节点 / {len(edges)} 条边")
    rows = graph_ops.community_rows(nodes, edges, method=str(config.get("community_method", "greedy_modularity")))
    _report_node_progress(context, node, 0.92, f"社区发现：生成 {len(rows)} 行")
    return {"community_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
