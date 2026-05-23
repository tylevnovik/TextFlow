from __future__ import annotations

from .support import *  # noqa: F401,F403

def _legacy_analysis_bundle(context: Any, node: dict[str, Any], corpus: list[dict[str, Any]]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    analysis_params = _analysis_params(
        context,
        node.get("config") if isinstance(node.get("config"), dict) else None,
    )
    include_frequency = bool(analysis_params.get("include_frequency_statistics", True))
    include_term_document = bool(analysis_params.get("include_term_document_relations", True))
    include_term_year = bool(analysis_params.get("include_term_year_relations", True))
    include_cooccurrence = bool(analysis_params.get("include_cooccurrence_analysis", True))
    include_similarity = bool(analysis_params.get("include_similarity_analysis", True))
    include_feature_terms = bool(analysis_params.get("include_feature_term_selection", True))
    include_keywords = bool(analysis_params.get("include_keyword_extraction", True))
    include_keyword_clusters = bool(analysis_params.get("include_keyword_clustering", True))
    include_institution_keywords = bool(analysis_params.get("include_institution_keyword_analysis", True))
    include_institution_topics = bool(analysis_params.get("include_institution_topic_analysis", True))
    include_document_clusters = bool(analysis_params.get("include_document_clustering", True))

    bundle = {
        "frequency_table": [],
        "term_document_table": [],
        "term_year_table": [],
        "cooccurrence_table": [],
        "similarity_table": [],
        "selected_feature_terms": [],
        "keyword_result": [],
        "keyword_cluster_result": [],
        "institution_keyword_cooccurrence": [],
        "institution_topic_cooccurrence": [],
        "clustering_result": [],
        "audit_table": list(context.result_bundle.get("audit_table") or []),
    }

    if include_frequency or include_term_document or include_term_year:
        _report_node_progress(context, node, 0.12, "旧版聚合分析：准备词项表")
        df_tokens = _token_frame(context, corpus)
        _report_node_progress(context, node, 0.2, f"旧版聚合分析：已展开 {len(df_tokens)} 条词项")
        if include_frequency:
            bundle["frequency_table"] = analysis_ops.frequency_table(df_tokens)
        if include_term_document:
            bundle["term_document_table"] = analysis_ops.term_document_table(df_tokens)
        if include_term_year:
            bundle["term_year_table"] = analysis_ops.term_year_table(df_tokens)
        _report_node_progress(context, node, 0.28, "旧版聚合分析：基础统计已生成")

    if include_cooccurrence:
        bundle["cooccurrence_table"] = analysis_ops.cooccurrence_table(
            corpus,
            int(analysis_params.get("cooccurrence_window", 5) or 5),
            int(analysis_params.get("min_cooccurrence", 2) or 2),
            progress_callback=lambda current, total: _report_node_progress(
                context,
                node,
                0.28 + 0.18 * current / max(total, 1),
                f"旧版聚合分析：共现 {current}/{total}",
            ),
        )
        _report_node_progress(context, node, 0.48, f"旧版聚合分析：共现生成 {len(bundle['cooccurrence_table'])} 行")

    needs_feature_payload = include_similarity or include_feature_terms or include_keyword_clusters or include_institution_topics or include_document_clusters
    feature_payload = (
        _feature_term_payload(
            context,
            corpus,
            {"feature_term_count": analysis_params.get("feature_term_count")},
        )
        if needs_feature_payload
        else None
    )
    if feature_payload is not None:
        _report_node_progress(context, node, 0.56, f"旧版聚合分析：特征词生成 {len(feature_payload['feature_rows'])} 行")
    if include_feature_terms and feature_payload is not None:
        bundle["selected_feature_terms"] = feature_payload["feature_rows"]

    if include_similarity and feature_payload is not None:
        bundle["similarity_table"] = analysis_ops.document_similarity_rows(
            corpus,
            feature_payload["tfidf_bundle"],
            analysis_params,
        )
        _report_node_progress(context, node, 0.62, f"旧版聚合分析：相似度生成 {len(bundle['similarity_table'])} 行")

    keyword_payload = (
        _keyword_payload(
            context,
            node,
            corpus,
            {
                "top_k_per_doc": analysis_params.get("top_k_per_doc"),
                "top_k_project": analysis_params.get("top_k_project"),
            },
            progress_start=0.62,
            progress_end=0.72,
        )
        if include_keywords or include_institution_keywords
        else None
    )
    if include_keywords and keyword_payload is not None:
        bundle["keyword_result"] = keyword_payload["keyword_rows"]
        _report_node_progress(context, node, 0.74, f"旧版聚合分析：关键词生成 {len(bundle['keyword_result'])} 行")

    topic_lookup: dict[int, dict[str, Any]] = {}
    doc_topics: dict[str, dict[str, Any]] = {}
    if include_keyword_clusters and feature_payload is not None:
        cluster_rows, topic_lookup = analysis_ops.keyword_clusters(
            feature_payload["feature_rows"],
            feature_payload["tfidf_bundle"],
            int(analysis_params.get("keyword_cluster_k", 4) or 4),
        )
        bundle["keyword_cluster_result"] = cluster_rows
        if hasattr(context, "set_shared_value"):
            context.set_shared_value("topic_lookup", topic_lookup)
        else:
            context.shared["topic_lookup"] = topic_lookup
        _report_node_progress(context, node, 0.8, f"旧版聚合分析：关键词聚类生成 {len(cluster_rows)} 行")

    if include_institution_topics and feature_payload is not None:
        _, doc_topics = analysis_ops.nmf_topic_model(corpus, feature_payload["tfidf_bundle"], analysis_params)
        _report_node_progress(context, node, 0.84, "旧版聚合分析：文档主题已计算")

    if include_institution_keywords or include_institution_topics:
        institution_keyword_rows, institution_topic_rows = analysis_ops.institution_keyword_and_topic(
            corpus,
            bundle["keyword_result"],
            doc_topics,
            topic_lookup,
        )
        if include_institution_keywords:
            bundle["institution_keyword_cooccurrence"] = institution_keyword_rows
        if include_institution_topics:
            bundle["institution_topic_cooccurrence"] = institution_topic_rows
        _report_node_progress(
            context,
            node,
            0.88,
            f"旧版聚合分析：机构分析生成 {len(institution_keyword_rows) + len(institution_topic_rows)} 行",
        )

    if include_document_clusters and feature_payload is not None:
        bundle["clustering_result"] = analysis_ops.document_clusters(
            corpus,
            feature_payload["tfidf_bundle"],
            int(analysis_params.get("document_cluster_k", 4) or 4),
        )
        _report_node_progress(context, node, 0.92, f"旧版聚合分析：文档聚类生成 {len(bundle['clustering_result'])} 行")

    return bundle


def execute_legacy_analyze_corpus(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _scoped_corpus_from_inputs(context, inputs)
    _report_node_progress(context, node, 0.08, f"旧版聚合分析：读取 {len(corpus)} 篇文档")
    bundle = _legacy_analysis_bundle(context, node, corpus)
    context.result_bundle.update(bundle)
    _report_node_progress(context, node, 0.94, "旧版聚合分析：结果已写入运行上下文")
    return {
        "analysis_bundle": bundle,
        "audit_table": bundle["audit_table"],
    }


def execute_legacy_export_results(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_bundle = inputs.get("analysis_bundle_in") or {}
    audit_rows = inputs.get("audit_table_in") or []
    bundle_count = len(analysis_bundle) if isinstance(analysis_bundle, dict) else 0
    audit_count = len(audit_rows) if isinstance(audit_rows, list) else 0
    _report_node_progress(context, node, 0.35, f"导出旧版结果：读取 {bundle_count} 组结果 / {audit_count} 条审计")
    if isinstance(analysis_bundle, dict):
        for key, value in analysis_bundle.items():
            if key in context.result_bundle and isinstance(value, list):
                context.result_bundle[key] = value
    if isinstance(audit_rows, list):
        context.result_bundle["audit_table"] = audit_rows
    _report_node_progress(context, node, 0.92, f"导出旧版结果：汇总 {len(context.result_bundle)} 个结果集")
    return {"artifact": {"kind": "legacy_export", "count": len(context.result_bundle)}}


