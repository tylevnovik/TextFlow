from __future__ import annotations

from typing import Any

from ..domain.workflow import default_workflow_definition
from .catalog import new_workflow_node


def _new_node(
    node_type: str,
    node_id: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return new_workflow_node(node_type, node_id, config=config)


def _edge(edge_id: str, from_node: str, from_port: str, to_node: str, to_port: str) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "from_node": from_node,
        "from_port": from_port,
        "to_node": to_node,
        "to_port": to_port,
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
        "deduplicate_documents",
        "sample_corpus",
        "clean_text",
        "normalize_text",
        "tokenize",
        "apply_dictionary_rules",
        "filter_terms",
        "frequency_statistics",
        "term_document_analysis",
        "term_year_analysis",
        "cooccurrence_analysis",
        "similarity_analysis",
        "feature_term_selection",
        "keyword_extraction",
        "focus_terms",
        "keyword_clustering",
        "topic_modeling",
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
    for node_type in node_types:
        nodes.append(_new_node(node_type, f"node-{node_type.replace('_', '-')}"))

    edges = []

    def add_edge(from_type: str, from_port: str, to_type: str, to_port: str) -> None:
        from_id = f"node-{from_type.replace('_', '-')}"
        to_id = f"node-{to_type.replace('_', '-')}"
        edge_id = f"edge-{from_type}-{from_port}-to-{to_type}-{to_port}"
        edges.append(_edge(edge_id, from_id, from_port, to_id, to_port))

    # core pipeline
    add_edge("corpus_input", "corpus", "normalize_metadata", "corpus_in")
    add_edge("normalize_metadata", "normalized_corpus", "deduplicate_documents", "corpus_in")
    add_edge("deduplicate_documents", "deduped_corpus", "sample_corpus", "corpus_in")
    add_edge("sample_corpus", "sampled_corpus", "clean_text", "corpus_in")
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
        "similarity_analysis",
        "feature_term_selection",
        "keyword_extraction",
        "topic_modeling",
        "document_clustering",
    ]:
        add_edge("filter_terms", "filtered_token_corpus", target, "token_corpus_in")

    add_edge("filter_terms", "filtered_token_corpus", "focus_terms", "token_corpus_in")
    add_edge("keyword_extraction", "keyword_table", "focus_terms", "term_table_in")
    add_edge("focus_terms", "focused_token_corpus", "cooccurrence_analysis", "token_corpus_in")
    add_edge("keyword_extraction", "keyword_table", "institution_keyword_analysis", "keyword_table_in")
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
    add_edge("graph_metrics", "graph_metric_table", "technology_indicators", "graph_metric_table_in")
    add_edge("technology_indicators", "technology_indicator_table", "technology_classification", "technology_indicator_table_in")

    # exports
    for node_type, port in [
        ("frequency_statistics", "frequency_table"),
        ("term_document_analysis", "term_document_table"),
        ("term_year_analysis", "term_year_table"),
        ("cooccurrence_analysis", "cooccurrence_table"),
        ("similarity_analysis", "similarity_table"),
        ("feature_term_selection", "feature_term_table"),
        ("focus_terms", "focus_term_summary"),
        ("keyword_extraction", "keyword_table"),
        ("keyword_clustering", "keyword_cluster_table"),
        ("topic_modeling", "topic_term_table"),
        ("topic_modeling", "document_topic_table"),
        ("topic_modeling", "topic_summary_table"),
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
        ("topic_modeling", "topic_summary_table"),
        ("document_clustering", "document_cluster_table"),
        ("institution_topic_analysis", "institution_topic_table"),
    ]:
        add_edge(node_type, port, "save_png", "render_in")

    for node_type, port in [
        ("frequency_statistics", "frequency_table"),
        ("term_document_analysis", "term_document_table"),
        ("term_year_analysis", "term_year_table"),
        ("cooccurrence_analysis", "cooccurrence_table"),
        ("similarity_analysis", "similarity_table"),
        ("feature_term_selection", "feature_term_table"),
        ("focus_terms", "focus_term_summary"),
        ("keyword_extraction", "keyword_table"),
        ("keyword_clustering", "keyword_cluster_table"),
        ("topic_modeling", "topic_term_table"),
        ("topic_modeling", "document_topic_table"),
        ("topic_modeling", "topic_summary_table"),
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
