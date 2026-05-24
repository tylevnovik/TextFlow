from __future__ import annotations

from typing import Any

from .common import json_ready

def empty_result_bundle() -> dict[str, Any]:
    return {
        "frequency_table": [],
        "term_document_table": [],
        "term_year_table": [],
        "cooccurrence_table": [],
        "similarity_table": [],
        "selected_feature_terms": [],
        "focus_term_summary": [],
        "keyword_result": [],
        "keyword_cluster_result": [],
        "institution_keyword_cooccurrence": [],
        "institution_topic_cooccurrence": [],
        "clustering_result": [],
        "graph_node_table": [],
        "graph_edge_table": [],
        "graph_metric_table": [],
        "community_table": [],
        "main_path_table": [],
        "link_prediction_table": [],
        "technology_indicator_table": [],
        "technology_classification_table": [],
        "metadata_audit_table": [],
        "audit_table": [],
        "report_files": [],
    }
