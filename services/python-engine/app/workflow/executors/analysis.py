from __future__ import annotations

from .corpus import _document_field_value
from .support import *  # noqa: F401,F403

def execute_frequency_statistics(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    _report_node_progress(context, node, 0.2, "词频统计：准备词项表")
    df_tokens = _token_frame(context, corpus)
    _report_node_progress(context, node, 0.65, f"词频统计：已展开 {len(df_tokens)} 条词项")
    rows = analysis_ops.frequency_table(df_tokens)
    _report_node_progress(context, node, 0.92, f"词频统计：生成 {len(rows)} 行")
    return {"frequency_table": rows}


def execute_term_document_analysis(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    _report_node_progress(context, node, 0.2, "词项-文档：准备词项表")
    df_tokens = _token_frame(context, corpus)
    _report_node_progress(context, node, 0.65, f"词项-文档：已展开 {len(df_tokens)} 条词项")
    rows = analysis_ops.term_document_table(df_tokens)
    _report_node_progress(context, node, 0.92, f"词项-文档：生成 {len(rows)} 行")
    return {"term_document_table": rows}


def execute_term_year_analysis(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    _report_node_progress(context, node, 0.2, "词项-年份：准备词项表")
    df_tokens = _token_frame(context, corpus)
    _report_node_progress(context, node, 0.65, f"词项-年份：已展开 {len(df_tokens)} 条词项")
    rows = analysis_ops.term_year_table(df_tokens)
    _report_node_progress(context, node, 0.92, f"词项-年份：生成 {len(rows)} 行")
    return {"term_year_table": rows}


def execute_cooccurrence_analysis(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.15, f"共现分析：读取 {len(corpus)} 篇文档")
    rows = analysis_ops.cooccurrence_table(
        corpus,
        int(params.get("cooccurrence_window", 5) or 5),
        int(params.get("min_cooccurrence", 2) or 2),
        progress_callback=lambda current, total: _report_node_progress(
            context,
            node,
            0.15 + 0.72 * current / max(total, 1),
            f"共现分析：处理 {current}/{total} 篇文档",
        ),
    )
    _report_node_progress(context, node, 0.92, f"共现分析：生成 {len(rows)} 行")
    return {
        "cooccurrence_table": rows
    }


def execute_similarity_analysis(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis_params = _analysis_params(
        context,
        {
            "feature_term_count": params.get("feature_term_count"),
            "similarity_method": params.get("similarity_method"),
            "min_similarity": params.get("min_similarity"),
            "similarity_top_k": params.get("similarity_top_k"),
        },
    )
    _report_node_progress(context, node, 0.2, "相似度计算：准备 TF-IDF 特征")
    payload = _feature_term_payload(
        context,
        corpus,
        {"feature_term_count": analysis_params.get("feature_term_count")},
    )
    _report_node_progress(context, node, 0.62, "相似度计算：TF-IDF 特征已生成")
    rows = analysis_ops.document_similarity_rows(
        corpus,
        payload["tfidf_bundle"],
        analysis_params,
    )
    _report_node_progress(context, node, 0.92, f"相似度计算：输出 {len(rows)} 个文档对")
    return {"similarity_table": rows}


def _comparison_groups(config: dict[str, Any], baseline_group: str, available_groups: set[str]) -> list[str]:
    raw_groups = config.get("comparison_groups")
    if isinstance(raw_groups, list):
        groups = [str(item).strip() for item in raw_groups if str(item).strip()]
        if groups:
            return groups
    groups_text = [item.strip() for item in str(config.get("comparison_groups_text") or "").split(",") if item.strip()]
    if groups_text:
        return groups_text
    return sorted(group for group in available_groups if group and group != baseline_group)


def _group_term_statistics(
    corpus: list[dict[str, Any]],
    group_field: str,
) -> tuple[dict[str, int], dict[tuple[str, str], int], dict[tuple[str, str], set[str]], set[str]]:
    group_totals: dict[str, int] = defaultdict(int)
    term_counts: dict[tuple[str, str], int] = defaultdict(int)
    doc_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    terms: set[str] = set()
    for item in corpus:
        group_value = str(_document_field_value(item, group_field) or "").strip()
        if not group_value:
            continue
        doc_id = str(item.get("doc_id") or item.get("id") or "")
        for token in item.get("filtered_tokens") or []:
            term = str(token or "").strip()
            if not term:
                continue
            group_totals[group_value] += 1
            term_counts[(group_value, term)] += 1
            if doc_id:
                doc_sets[(group_value, term)].add(doc_id)
            terms.add(term)
    return group_totals, term_counts, doc_sets, terms


def execute_group_compare(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    group_field = str(config.get("group_field") or "institution").strip()
    baseline_group = str(config.get("baseline_group") or "").strip()
    min_frequency = int(config.get("min_frequency", 1) or 1)
    _report_node_progress(context, node, 0.15, "分组比较：统计分组词频")
    group_totals, term_counts, doc_sets, terms = _group_term_statistics(corpus, group_field)
    if not group_totals:
        _report_node_progress(context, node, 0.92, "分组比较：无可比较分组")
        return {"group_metric_table": []}
    _report_node_progress(context, node, 0.45, f"分组比较：识别 {len(group_totals)} 个分组")
    comparison_groups = _comparison_groups(config, baseline_group, set(group_totals))
    selected_groups = [group for group in [baseline_group, *comparison_groups] if group and group in group_totals]
    if not selected_groups:
        selected_groups = sorted(group_totals)
    rows: list[dict[str, Any]] = []
    total_groups = len(selected_groups)
    for group_index, group_value in enumerate(selected_groups, start=1):
        total_terms = group_totals.get(group_value, 0)
        if not total_terms:
            continue
        for term in sorted(terms):
            term_count = term_counts.get((group_value, term), 0)
            baseline_term_count = term_counts.get((baseline_group, term), 0)
            if term_count + baseline_term_count < min_frequency:
                continue
            baseline_total = group_totals.get(baseline_group, 0)
            normalized_frequency = term_count / total_terms if total_terms else 0.0
            baseline_normalized_frequency = baseline_term_count / baseline_total if baseline_total else 0.0
            rows.append(
                {
                    "group_field": group_field,
                    "group_value": group_value,
                    "baseline_group": baseline_group,
                    "term": term,
                    "term_count": term_count,
                    "document_count": len(doc_sets.get((group_value, term), set())),
                    "total_terms": total_terms,
                    "normalized_frequency": round(normalized_frequency, 6),
                    "baseline_term_count": baseline_term_count,
                    "baseline_document_count": len(doc_sets.get((baseline_group, term), set())),
                    "baseline_total_terms": baseline_total,
                    "baseline_normalized_frequency": round(baseline_normalized_frequency, 6),
                    "ratio_vs_baseline": round((normalized_frequency + 1e-9) / (baseline_normalized_frequency + 1e-9), 6),
                }
            )
        _report_node_progress(
            context,
            node,
            0.45 + 0.42 * group_index / max(total_groups, 1),
            f"分组比较：完成 {group_index}/{total_groups} 个分组",
        )
    rows.sort(key=lambda item: (str(item["group_value"]), -int(item["term_count"]), str(item["term"])))
    _report_node_progress(context, node, 0.92, f"分组比较：生成 {len(rows)} 行")
    return {"group_metric_table": rows}


def _xlogx(value: float) -> float:
    return 0.0 if value <= 0 else value * math.log(value)


def _log_likelihood_ratio(comparison_term_count: int, comparison_total: int, baseline_term_count: int, baseline_total: int) -> float:
    k11 = float(comparison_term_count)
    k12 = float(baseline_term_count)
    k21 = float(max(comparison_total - comparison_term_count, 0))
    k22 = float(max(baseline_total - baseline_term_count, 0))
    row_sum_1 = k11 + k12
    row_sum_2 = k21 + k22
    total = float(comparison_total + baseline_total)
    return max(
        0.0,
        2.0
        * (
            _xlogx(k11)
            + _xlogx(k12)
            + _xlogx(k21)
            + _xlogx(k22)
            + _xlogx(total)
            - _xlogx(float(comparison_total))
            - _xlogx(float(baseline_total))
            - _xlogx(row_sum_1)
            - _xlogx(row_sum_2)
        ),
    )


def execute_keyness_analysis(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    group_field = str(config.get("group_field") or "institution").strip()
    baseline_group = str(config.get("baseline_group") or "").strip()
    comparison_group = str(config.get("comparison_group") or "").strip()
    min_frequency = int(config.get("min_frequency", 2) or 2)
    _report_node_progress(context, node, 0.18, "关键性分析：统计分组词频")
    group_totals, term_counts, doc_sets, terms = _group_term_statistics(corpus, group_field)
    comparison_total = group_totals.get(comparison_group, 0)
    baseline_total = group_totals.get(baseline_group, 0)
    if not comparison_total or not baseline_total:
        _report_node_progress(context, node, 0.92, "关键性分析：缺少基准组或比较组")
        return {"keyness_table": []}
    _report_node_progress(context, node, 0.45, f"关键性分析：准备比较 {len(terms)} 个词项")
    rows: list[dict[str, Any]] = []
    sorted_terms = sorted(terms)
    for term_index, term in enumerate(sorted_terms, start=1):
        comparison_term_count = term_counts.get((comparison_group, term), 0)
        baseline_term_count = term_counts.get((baseline_group, term), 0)
        if comparison_term_count + baseline_term_count < min_frequency:
            continue
        comparison_ratio = comparison_term_count / comparison_total if comparison_total else 0.0
        baseline_ratio = baseline_term_count / baseline_total if baseline_total else 0.0
        rows.append(
            {
                "group_field": group_field,
                "comparison_group": comparison_group,
                "baseline_group": baseline_group,
                "term": term,
                "comparison_term_count": comparison_term_count,
                "baseline_term_count": baseline_term_count,
                "comparison_document_count": len(doc_sets.get((comparison_group, term), set())),
                "baseline_document_count": len(doc_sets.get((baseline_group, term), set())),
                "comparison_normalized_frequency": round(comparison_ratio, 6),
                "baseline_normalized_frequency": round(baseline_ratio, 6),
                "relative_ratio": round((comparison_ratio + 1e-9) / (baseline_ratio + 1e-9), 6),
                "llr": round(
                    _log_likelihood_ratio(
                        comparison_term_count,
                        comparison_total,
                        baseline_term_count,
                        baseline_total,
                    ),
                    6,
                ),
            }
        )
        if term_index == len(sorted_terms) or term_index % 250 == 0:
            _report_node_progress(
                context,
                node,
                0.45 + 0.42 * term_index / max(len(sorted_terms), 1),
                f"关键性分析：完成 {term_index}/{len(sorted_terms)} 个词项",
            )
    rows.sort(key=lambda item: (-float(item["llr"]), -float(item["relative_ratio"]), str(item["term"])))
    _report_node_progress(context, node, 0.92, f"关键性分析：生成 {len(rows)} 行")
    return {"keyness_table": rows}


def execute_topic_modeling(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis_params = _analysis_params(
        context,
        {
            "topic_algorithm": config.get("topic_algorithm"),
            "topic_model_k": config.get("topic_model_k"),
            "feature_term_count": config.get("feature_term_count"),
        },
    )
    _report_node_progress(context, node, 0.18, "主题模型：准备 TF-IDF 特征")
    payload = _feature_term_payload(
        context,
        corpus,
        {"feature_term_count": analysis_params.get("feature_term_count")},
    )
    _report_node_progress(context, node, 0.55, "主题模型：TF-IDF 特征已生成")
    topic_term_rows, document_topic_rows, topic_summary_rows = analysis_ops.topic_model_tables(
        corpus,
        payload["tfidf_bundle"],
        analysis_params,
        top_terms_per_topic=int(config.get("top_terms_per_topic", 5) or 5),
    )
    _report_node_progress(context, node, 0.92, f"主题模型：生成 {len(topic_summary_rows)} 个主题")
    return {
        "topic_term_table": topic_term_rows,
        "document_topic_table": document_topic_rows,
        "topic_summary_table": topic_summary_rows,
    }


def execute_cluster_evaluation(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    cluster_rows = inputs.get("document_cluster_table_in") or []
    if not isinstance(cluster_rows, list):
        cluster_rows = [cluster_rows] if isinstance(cluster_rows, dict) else []
    _report_node_progress(context, node, 0.35, f"聚类评估：读取 {len(cluster_rows)} 条聚类结果")
    rows = analysis_ops.cluster_evaluation_rows(cluster_rows)
    _report_node_progress(context, node, 0.92, f"聚类评估：生成 {len(rows)} 行")
    return {"cluster_evaluation_table": rows}


def execute_join_results(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    left_rows = _table_rows_from_inputs_or_results(context, inputs, "left_table_in", str(config.get("left_artifact") or ""))
    right_rows = _table_rows_from_inputs_or_results(context, inputs, "right_table_in", str(config.get("right_artifact") or ""))
    _report_node_progress(context, node, 0.25, f"合并结果表：读取左表 {len(left_rows)} 行 / 右表 {len(right_rows)} 行")
    joined_rows = analysis_ops.join_table_rows(
        left_rows,
        right_rows,
        _join_keys(config),
        join_type=str(config.get("join_type") or "inner"),
    )
    _report_node_progress(context, node, 0.92, f"合并结果表：生成 {len(joined_rows)} 行")
    return {"joined_table": joined_rows}


def execute_feature_term_selection(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.25, "特征词筛选：准备 TF-IDF 特征")
    payload = _feature_term_payload(context, corpus, {"feature_term_count": params.get("feature_term_count")})
    _report_node_progress(context, node, 0.92, f"特征词筛选：输出 {len(payload['feature_rows'])} 个候选词")
    return {"feature_term_table": payload["feature_rows"]}


def execute_keyword_extraction(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.2, f"关键词提取：读取 {len(corpus)} 篇文档")
    payload = _keyword_payload(
        context,
        node,
        corpus,
        {
            "top_k_per_doc": params.get("top_k_per_doc"),
            "top_k_project": params.get("top_k_project"),
        },
    )
    _report_node_progress(context, node, 0.92, f"关键词提取：生成 {len(payload['keyword_rows'])} 行")
    return {"keyword_table": payload["keyword_rows"]}


def execute_keyword_clustering(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    feature_rows = inputs.get("feature_term_table_in") or []
    if not isinstance(feature_rows, list):
        feature_rows = [feature_rows]
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    selected_count = sum(1 for row in feature_rows if isinstance(row, dict) and row.get("selected"))
    _report_node_progress(context, node, 0.25, "关键词聚类：准备特征向量")
    payload = _feature_term_payload(context, corpus, {"feature_term_count": selected_count or "all"})
    _report_node_progress(context, node, 0.62, "关键词聚类：特征向量已生成")
    cluster_rows, topic_lookup = analysis_ops.keyword_clusters(
        feature_rows,
        payload["tfidf_bundle"],
        int(params.get("keyword_cluster_k", 4) or 4),
    )
    _report_node_progress(context, node, 0.92, f"关键词聚类：生成 {len(cluster_rows)} 行")
    if hasattr(context, "set_shared_value"):
        context.set_shared_value("topic_lookup", topic_lookup)
    else:
        context.shared["topic_lookup"] = topic_lookup
    return {"keyword_cluster_table": cluster_rows}


def execute_institution_keyword_analysis(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    keyword_rows = inputs.get("keyword_table_in") or []
    if not isinstance(keyword_rows, list):
        keyword_rows = [keyword_rows]
    corpus = _scoped_corpus_from_inputs(context, inputs)
    _report_node_progress(context, node, 0.35, f"机构-关键词：读取 {len(keyword_rows)} 个关键词")
    institution_keyword_rows, _ = analysis_ops.institution_keyword_and_topic(
        corpus,
        keyword_rows,
        {},
        {},
    )
    _report_node_progress(context, node, 0.92, f"机构-关键词：生成 {len(institution_keyword_rows)} 行")
    return {"institution_keyword_table": institution_keyword_rows}


def execute_institution_topic_analysis(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    cluster_rows = inputs.get("keyword_cluster_table_in") or []
    if not isinstance(cluster_rows, list):
        cluster_rows = [cluster_rows]
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    topic_feature_count = len(
        {
            str(row.get("term") or "")
            for row in cluster_rows
            if isinstance(row, dict) and str(row.get("term") or "")
        }
    )
    _report_node_progress(context, node, 0.2, "机构-主题：准备主题特征")
    payload = _feature_term_payload(
        context,
        corpus,
        {"feature_term_count": topic_feature_count or _analysis_params(context).get("feature_term_count")},
    )
    _report_node_progress(context, node, 0.52, "机构-主题：主题特征已生成")
    _, doc_topics = analysis_ops.nmf_topic_model(
        corpus,
        payload["tfidf_bundle"],
        _analysis_params(context, {"topic_model_k": params.get("topic_model_k")}),
    )
    _report_node_progress(context, node, 0.78, "机构-主题：文档主题已计算")
    topic_lookup = _topic_lookup_from_cluster_rows(cluster_rows)
    _, institution_topic_rows = analysis_ops.institution_keyword_and_topic(
        corpus,
        [],
        doc_topics,
        topic_lookup,
    )
    _report_node_progress(context, node, 0.92, f"机构-主题：生成 {len(institution_topic_rows)} 行")
    return {"institution_topic_table": institution_topic_rows}


def execute_document_clustering(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.25, "文档聚类：准备文档向量")
    payload = _feature_term_payload(context, corpus)
    _report_node_progress(context, node, 0.62, "文档聚类：文档向量已生成")
    rows = analysis_ops.document_clusters(
        corpus,
        payload["tfidf_bundle"],
        int(params.get("document_cluster_k", 4) or 4),
    )
    _report_node_progress(context, node, 0.92, f"文档聚类：生成 {len(rows)} 行")
    return {"document_cluster_table": rows}


