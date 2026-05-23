from __future__ import annotations

from .support import *  # noqa: F401,F403

def _graph_ops():
    from ...analysis import graph as graph_ops_module
    return graph_ops_module


def execute_build_network(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
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


def execute_graph_metrics(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    graph_ops = _graph_ops()
    nodes = _table_rows_from_inputs_or_results(context, inputs, "graph_node_table_in", "graph_node_table")
    edges = _table_rows_from_inputs_or_results(context, inputs, "graph_edge_table_in", "graph_edge_table")
    _report_node_progress(context, node, 0.25, f"图指标：读取 {len(nodes)} 个节点 / {len(edges)} 条边")
    rows = graph_ops.graph_metric_rows(nodes, edges)
    _report_node_progress(context, node, 0.92, f"图指标：生成 {len(rows)} 行")
    return {"graph_metric_table": rows}


def execute_community_detection(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    graph_ops = _graph_ops()
    nodes = _table_rows_from_inputs_or_results(context, inputs, "graph_node_table_in", "graph_node_table")
    edges = _table_rows_from_inputs_or_results(context, inputs, "graph_edge_table_in", "graph_edge_table")
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.25, f"社区发现：读取 {len(nodes)} 个节点 / {len(edges)} 条边")
    rows = graph_ops.community_rows(nodes, edges, method=str(config.get("community_method", "greedy_modularity")))
    _report_node_progress(context, node, 0.92, f"社区发现：生成 {len(rows)} 行")
    return {"community_table": rows}


def execute_main_path_analysis(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    graph_ops = _graph_ops()
    nodes = _table_rows_from_inputs_or_results(context, inputs, "graph_node_table_in", "graph_node_table")
    edges = _table_rows_from_inputs_or_results(context, inputs, "graph_edge_table_in", "graph_edge_table")
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.25, f"主路径：读取 {len(nodes)} 个节点 / {len(edges)} 条边")
    rows = graph_ops.main_path_rows(nodes, edges, mode=str(config.get("main_path_mode", "directed_citation_or_weighted_backbone")))
    _report_node_progress(context, node, 0.92, f"主路径：生成 {len(rows)} 行")
    return {"main_path_table": rows}


def execute_link_prediction(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    graph_ops = _graph_ops()
    nodes = _table_rows_from_inputs_or_results(context, inputs, "graph_node_table_in", "graph_node_table")
    edges = _table_rows_from_inputs_or_results(context, inputs, "graph_edge_table_in", "graph_edge_table")
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.25, f"链接预测：读取 {len(nodes)} 个节点 / {len(edges)} 条边")
    rows = graph_ops.link_prediction_rows(nodes, edges, top_n=int(config.get("link_prediction_top_n", 200) or 200))
    _report_node_progress(context, node, 0.92, f"链接预测：生成 {len(rows)} 行")
    return {"link_prediction_table": rows}


