from __future__ import annotations

from typing import Any

from ._common import analysis_passthrough_compiler, number_param, port, runtime, field, graph, slot, ui
from ._support import _report_node_progress, _table_rows_from_inputs_or_results


def _graph_ops():
    from ...analysis import graph as graph_ops_module
    return graph_ops_module


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "build_network",
        "title": "构建网络",
        "category": "analysis",
        "description": "从共现表构建词项网络。",
        "inputs": [
            port("cooccurrence_table_in", "CooccurrenceTable", "共现表输入")
        ],
        "outputs": [
            port("graph_node_table", "GraphNodeTable", "网络节点表", result_bundle_key="graph_node_table"),
            port("graph_edge_table", "GraphEdgeTable", "网络边表", result_bundle_key="graph_edge_table"),
        ],
        "params": [
            number_param("min_edge_weight", "最小边权重", 1),
            number_param("max_edges", "最大边数", 5000),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.build_network",
            cacheable=True,
            previewable=True,
            parallel_safe=True,
        ),
        "graph": graph((340, 230), (4500, 680), toolbox_order=430),
        "ui": ui(
            [
                field("number", "min_edge_weight", "最小边权重", step=1),
                field("number", "max_edges", "最大边数", step=1),
            ],
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    analysis_passthrough_compiler(context, node)


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    graph_ops = _graph_ops()
    cooccurrence_rows = _table_rows_from_inputs_or_results(context, inputs, "cooccurrence_table_in", "cooccurrence_table")
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.25, f"构建网络：读取 {len(cooccurrence_rows)} 条共现边")
    nodes, edges = graph_ops.build_term_graph_tables(
        cooccurrence_rows,
        min_edge_weight=int(config.get("min_edge_weight", 1) or 1),
        max_edges=int(config.get("max_edges", 5000) or 5000),
    )
    _report_node_progress(context, node, 0.92, f"构建网络：生成 {len(nodes)} 个节点 / {len(edges)} 条边")
    return {"graph_node_table": nodes, "graph_edge_table": edges}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
