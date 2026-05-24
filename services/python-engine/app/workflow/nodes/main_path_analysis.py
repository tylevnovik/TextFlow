from __future__ import annotations

from typing import Any

from ._common import analysis_passthrough_compiler, enum_param, port, runtime
from ._support import _report_node_progress, _table_rows_from_inputs_or_results


def _graph_ops():
    from ...analysis import graph as graph_ops_module
    return graph_ops_module


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "main_path_analysis",
        "title": "主路径分析",
        "category": "analysis",
        "description": "提取网络的主干路径。",
        "inputs": [
            port("graph_node_table_in", "GraphNodeTable", "节点表输入"),
            port("graph_edge_table_in", "GraphEdgeTable", "边表输入"),
        ],
        "outputs": [
            port("main_path_table", "MainPathTable", "主路径表", result_bundle_key="main_path_table")
        ],
        "params": [
            enum_param("main_path_mode", "主路径模式", "directed_citation_or_weighted_backbone", [
                ("directed_citation_or_weighted_backbone", "有向引用或加权骨干"),
                ("cooccurrence_backbone", "共现骨干"),
            ]),
        ],
        "runtime": runtime(
            "analysis",
            "analysis.main_path_analysis",
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
    _report_node_progress(context, node, 0.25, f"主路径：读取 {len(nodes)} 个节点 / {len(edges)} 条边")
    rows = graph_ops.main_path_rows(nodes, edges, mode=str(config.get("main_path_mode", "directed_citation_or_weighted_backbone")))
    _report_node_progress(context, node, 0.92, f"主路径：生成 {len(rows)} 行")
    return {"main_path_table": rows}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
