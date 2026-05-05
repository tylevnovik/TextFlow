from __future__ import annotations

from copy import deepcopy
from typing import Any

from .defaults import default_runtime_profile, default_workflow_definition
from .node_definitions import build_builtin_node_definitions


NODE_DEFINITION_BY_TYPE: dict[str, dict[str, Any]] | None = None


def _get_node_defs() -> dict[str, dict[str, Any]]:
    global NODE_DEFINITION_BY_TYPE
    if NODE_DEFINITION_BY_TYPE is None:
        NODE_DEFINITION_BY_TYPE = {
            definition["type"]: definition
            for definition in build_builtin_node_definitions()
        }
    return NODE_DEFINITION_BY_TYPE


def _default_node_config(node_type: str) -> dict[str, Any]:
    definition = _get_node_defs()[node_type]
    return {
        str(param.get("param_id")): deepcopy(param.get("default_value"))
        for param in definition.get("params", [])
        if isinstance(param, dict) and str(param.get("param_id") or "").strip()
    }


def _new_node(
    node_type: str,
    node_id: str,
    config: dict[str, Any] | None = None,
    *,
    x: int = 0,
    y: int = 0,
) -> dict[str, Any]:
    definition = _get_node_defs()[node_type]
    return {
        "node_id": node_id,
        "node_type": node_type,
        "label": str(definition.get("title") or node_type),
        "position": {"x": x, "y": y},
        "size": {"w": 230, "h": 190},
        "inputs": deepcopy(definition.get("inputs") or []),
        "outputs": deepcopy(definition.get("outputs") or []),
        "config": {**_default_node_config(node_type), **deepcopy(config or {})},
        "ui_state": {"collapsed": False, "bypassed": False},
        "runtime_meta": {
            "step_id": str(definition.get("category") or "manual"),
            "node_impl_version": "2.0.0",
        },
    }


def _edge(edge_id: str, from_node: str, from_port: str, to_node: str, to_port: str) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "from_node": from_node,
        "from_port": from_port,
        "to_node": to_node,
        "to_port": to_port,
    }


NEW_FLOW_NODE_POSITIONS: dict[str, tuple[int, int]] = {
    "corpus_input": (120, 330),
    "dictionary_input": (120, 80),
    "normalize_metadata": (520, 330),
    "clean_text": (900, 330),
    "normalize_text": (1280, 330),
    "tokenize": (1680, 330),
    "apply_dictionary_rules": (2060, 330),
    "filter_terms": (2460, 330),
    "frequency_statistics": (2860, 80),
    "term_document_analysis": (2860, 340),
    "term_year_analysis": (2860, 600),
    "cooccurrence_analysis": (2860, 860),
    "feature_term_selection": (2860, 1120),
    "keyword_extraction": (3240, 80),
    "keyword_clustering": (3240, 340),
    "institution_keyword_analysis": (3240, 600),
    "institution_topic_analysis": (3240, 860),
    "document_clustering": (3240, 1120),
    "build_network": (3620, 80),
    "graph_metrics": (3620, 340),
    "community_detection": (3620, 600),
    "main_path_analysis": (3620, 860),
    "link_prediction": (3620, 1120),
    "technology_indicators": (4000, 80),
    "technology_classification": (4000, 340),
    "save_csv": (4380, 80),
    "save_xlsx": (4380, 340),
    "save_png": (4380, 600),
    "save_html_report": (4380, 860),
}


def build_new_flow_workflow(
    workflow_id: str,
    name: str,
    *,
    source_profile: str = "generic",
    include_multisource: bool = False,
    include_patent_graph: bool = True,
) -> dict[str, Any]:
    base = default_workflow_definition()
    base["workflow_id"] = workflow_id
    base["name"] = name
    base["source"] = "manual"
    base["meta"] = {
        **base.get("meta", {}),
        "flow_schema_version": "2026-05-new-flow",
        "flow_source": "修改版流程.docx",
    }

    node_types = [
        "corpus_input",
        "dictionary_input",
        "normalize_metadata",
        "clean_text",
        "normalize_text",
        "tokenize",
        "apply_dictionary_rules",
        "filter_terms",
        "frequency_statistics",
        "term_document_analysis",
        "term_year_analysis",
        "cooccurrence_analysis",
        "feature_term_selection",
        "keyword_extraction",
        "keyword_clustering",
        "institution_keyword_analysis",
        "institution_topic_analysis",
        "document_clustering",
        "build_network",
        "graph_metrics",
        "community_detection",
        "main_path_analysis",
        "link_prediction",
        "technology_indicators",
        "technology_classification",
        "save_csv",
        "save_xlsx",
        "save_png",
        "save_html_report",
    ]

    nodes = []
    for index, node_type in enumerate(node_types):
        x, y = NEW_FLOW_NODE_POSITIONS.get(node_type, (2860 + (index % 4) * 380, 80 + (index // 4) * 260))
        nodes.append(_new_node(node_type, f"node-{node_type.replace('_', '-')}", x=x, y=y))

    edges = []

    def add_edge(from_type: str, from_port: str, to_type: str, to_port: str) -> None:
        from_id = f"node-{from_type.replace('_', '-')}"
        to_id = f"node-{to_type.replace('_', '-')}"
        edges.append(_edge(f"edge-{from_type}-to-{to_type}", from_id, from_port, to_id, to_port))

    # core pipeline
    add_edge("corpus_input", "corpus", "normalize_metadata", "corpus_in")
    add_edge("normalize_metadata", "normalized_corpus", "clean_text", "corpus_in")
    add_edge("clean_text", "clean_corpus", "normalize_text", "corpus_in")
    add_edge("normalize_text", "normalized_corpus", "tokenize", "corpus_in")
    add_edge("tokenize", "token_corpus", "apply_dictionary_rules", "token_corpus_in")
    add_edge("dictionary_input", "dictionary_set", "apply_dictionary_rules", "dictionary_set_in")
    add_edge("apply_dictionary_rules", "token_corpus", "filter_terms", "token_corpus_in")

    # analysis branches
    for target in [
        "frequency_statistics",
        "term_document_analysis",
        "term_year_analysis",
        "cooccurrence_analysis",
        "feature_term_selection",
        "keyword_extraction",
        "institution_keyword_analysis",
        "document_clustering",
    ]:
        add_edge("filter_terms", "filtered_token_corpus", target, "token_corpus_in")

    add_edge("feature_term_selection", "feature_term_table", "keyword_clustering", "feature_term_table_in")
    add_edge("keyword_clustering", "keyword_cluster_table", "institution_topic_analysis", "keyword_cluster_table_in")

    # graph branch
    add_edge("cooccurrence_analysis", "cooccurrence_table", "build_network", "cooccurrence_table_in")
    add_edge("build_network", "graph_node_table", "graph_metrics", "graph_node_table_in")
    add_edge("build_network", "graph_edge_table", "graph_metrics", "graph_edge_table_in")
    add_edge("build_network", "graph_node_table", "community_detection", "graph_node_table_in")
    add_edge("build_network", "graph_edge_table", "community_detection", "graph_edge_table_in")
    add_edge("build_network", "graph_node_table", "main_path_analysis", "graph_node_table_in")
    add_edge("build_network", "graph_edge_table", "main_path_analysis", "graph_edge_table_in")
    add_edge("build_network", "graph_node_table", "link_prediction", "graph_node_table_in")
    add_edge("build_network", "graph_edge_table", "link_prediction", "graph_edge_table_in")

    # technology branch
    add_edge("term_year_analysis", "term_year_table", "technology_indicators", "term_year_table_in")
    add_edge("technology_indicators", "technology_indicator_table", "technology_classification", "technology_indicator_table_in")

    # exports
    for node_type, port in [
        ("frequency_statistics", "frequency_table"),
        ("term_document_analysis", "term_document_table"),
        ("term_year_analysis", "term_year_table"),
        ("cooccurrence_analysis", "cooccurrence_table"),
        ("feature_term_selection", "feature_term_table"),
        ("keyword_extraction", "keyword_table"),
        ("keyword_clustering", "keyword_cluster_table"),
        ("institution_keyword_analysis", "institution_keyword_table"),
        ("institution_topic_analysis", "institution_topic_table"),
        ("document_clustering", "document_cluster_table"),
        ("graph_metrics", "graph_metric_table"),
        ("community_detection", "community_table"),
        ("main_path_analysis", "main_path_table"),
        ("link_prediction", "link_prediction_table"),
        ("technology_indicators", "technology_indicator_table"),
        ("technology_classification", "technology_classification_table"),
    ]:
        add_edge(node_type, port, "save_csv", "table_in")
        add_edge(node_type, port, "save_xlsx", "table_in")

    for node_type, port in [
        ("cooccurrence_analysis", "cooccurrence_table"),
        ("keyword_clustering", "keyword_cluster_table"),
        ("document_clustering", "document_cluster_table"),
        ("institution_topic_analysis", "institution_topic_table"),
    ]:
        add_edge(node_type, port, "save_png", "render_in")

    for node_type, port in [
        ("frequency_statistics", "frequency_table"),
        ("term_document_analysis", "term_document_table"),
        ("term_year_analysis", "term_year_table"),
        ("cooccurrence_analysis", "cooccurrence_table"),
        ("feature_term_selection", "feature_term_table"),
        ("keyword_extraction", "keyword_table"),
        ("keyword_clustering", "keyword_cluster_table"),
        ("institution_keyword_analysis", "institution_keyword_table"),
        ("institution_topic_analysis", "institution_topic_table"),
        ("document_clustering", "document_cluster_table"),
        ("graph_metrics", "graph_metric_table"),
        ("community_detection", "community_table"),
        ("main_path_analysis", "main_path_table"),
        ("link_prediction", "link_prediction_table"),
        ("technology_indicators", "technology_indicator_table"),
        ("technology_classification", "technology_classification_table"),
    ]:
        add_edge(node_type, port, "save_html_report", "report_in")

    add_edge("apply_dictionary_rules", "audit_table", "save_html_report", "report_in")
    add_edge("normalize_metadata", "metadata_audit_table", "save_html_report", "report_in")

    base["nodes"] = nodes
    base["edges"] = edges
    base["groups"] = []
    return base
