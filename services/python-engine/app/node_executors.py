from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from .node_definitions import build_builtin_node_definitions
from .node_registry import NodeRegistryBuilder


def _pipeline_ops():
    from . import pipeline as pipeline_ops

    return pipeline_ops


def _scoped_corpus_from_inputs(context: Any, inputs: dict[str, Any]) -> list[dict[str, Any]]:
    def is_corpus_rows(value: Any) -> bool:
        if not isinstance(value, list):
            return False
        if not value:
            return True
        first = value[0]
        if not isinstance(first, dict):
            return False
        return "doc_id" in first and any(
            key in first
            for key in ["raw_text", "clean_text", "normalized_text", "tokens", "filtered_tokens", "title"]
        )

    for value in inputs.values():
        if is_corpus_rows(value):
            return value
    shared = getattr(context, "shared", {})
    for key in [
        "filtered_corpus",
        "dictionary_corpus",
        "token_corpus",
        "normalized_corpus",
        "clean_corpus",
        "scoped_corpus",
    ]:
        value = shared.get(key)
        if is_corpus_rows(value):
            return value
    return []


def _analysis_params(context: Any, patch: dict[str, Any] | None = None) -> dict[str, Any]:
    base = deepcopy(((context.compiled_pipeline or {}).get("analysis") or {}))
    if patch:
        base.update(patch)
    return base


def _clone_corpus_rows(corpus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) if isinstance(item, dict) else item for item in corpus]


def _report_corpus_progress(context: Any, node: dict[str, Any], completed: int, total: int, stage: str) -> None:
    if not total:
        return
    if completed == total or completed % 250 == 0:
        context.node_progress(node, completed / total, f"{stage} {completed}/{total}")


def _feature_term_payload(context: Any, corpus: list[dict[str, Any]], patch: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis_params = _analysis_params(context, patch)
    cache_key = (tuple(item.get("doc_id") for item in corpus), analysis_params.get("feature_term_count"))
    shared_cache = context.shared.setdefault("feature_term_payloads", {})
    payload = shared_cache.get(cache_key)
    if payload is not None:
        return payload
    pipeline_ops = _pipeline_ops()
    feature_rows, tfidf_bundle = pipeline_ops.tfidf_feature_bundle(corpus, analysis_params)
    payload = {
        "feature_rows": feature_rows,
        "tfidf_bundle": tfidf_bundle,
        "analysis_params": analysis_params,
    }
    shared_cache[cache_key] = payload
    return payload


def _keyword_payload(
    context: Any,
    node: dict[str, Any],
    corpus: list[dict[str, Any]],
    patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    analysis_params = _analysis_params(context, patch)
    cache_key = (
        tuple(item.get("doc_id") for item in corpus),
        analysis_params.get("top_k_per_doc"),
        analysis_params.get("top_k_project"),
    )
    shared_cache = context.shared.setdefault("keyword_payloads", {})
    payload = shared_cache.get(cache_key)
    if payload is not None:
        return payload
    pipeline_ops = _pipeline_ops()
    feature_payload = _feature_term_payload(
        context,
        corpus,
        {"feature_term_count": analysis_params.get("feature_term_count")},
    )
    keyword_rows = pipeline_ops.extract_keyword_rows(
        corpus,
        analysis_params,
        feature_payload.get("tfidf_bundle"),
        progress_callback=lambda current, total: context.node_progress(
            node,
            current / max(total, 1),
            f"关键词提取 {current}/{total}",
        ),
    )
    payload = {
        "keyword_rows": keyword_rows,
        "analysis_params": analysis_params,
    }
    shared_cache[cache_key] = payload
    return payload


def _topic_lookup_from_cluster_rows(cluster_rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    topic_lookup: dict[int, dict[str, Any]] = defaultdict(lambda: {"terms": []})
    for row in cluster_rows:
        topic_id = int(row.get("cluster_id", 0))
        topic_lookup[topic_id]["label"] = row.get("cluster_label") or f"主题 {topic_id + 1}"
        topic_lookup[topic_id]["terms"].append(
            {
                "term": row.get("term"),
                "score": float(row.get("centroid_weight", 0.0) or 0.0),
            }
        )
    for payload in topic_lookup.values():
        payload["terms"] = sorted(payload["terms"], key=lambda item: item["score"], reverse=True)
    return dict(topic_lookup)


def execute_corpus_input(context: Any, node: dict[str, Any], _inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    scope = pipeline_ops.normalize_run_scope(node.get("config") if isinstance(node.get("config"), dict) else {})
    scoped = [item for item in context.full_corpus if pipeline_ops.document_matches_scope(item, scope)]
    context.shared["run_scope"] = scope
    context.shared["run_scope_summary"] = pipeline_ops.describe_run_scope(scope, len(context.full_corpus), len(scoped))
    context.shared["scoped_corpus"] = scoped
    return {"corpus": scoped}


def execute_filter_corpus(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    scope = pipeline_ops.normalize_run_scope(node.get("config") if isinstance(node.get("config"), dict) else {})
    corpus = _scoped_corpus_from_inputs(context, inputs)
    scoped = [item for item in corpus if pipeline_ops.document_matches_scope(item, scope)]
    context.shared["run_scope"] = scope
    context.shared["run_scope_summary"] = pipeline_ops.describe_run_scope(scope, len(context.full_corpus), len(scoped))
    context.shared["scoped_corpus"] = scoped
    return {"corpus": scoped}


def execute_dictionary_input(context: Any, _node: dict[str, Any], _inputs: dict[str, Any]) -> dict[str, Any]:
    return {"dictionary_set": deepcopy(context.manifest["dictionary_set"])}


def execute_merge_corpora(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpora = inputs.get("corpus_in") or []
    if isinstance(corpora, dict):
        corpora = [corpora]
    merged: list[dict[str, Any]] = []
    seen_doc_ids: set[str] = set()
    strategy = str((node.get("config") or {}).get("strategy") or "append")
    for corpus in corpora:
        if not isinstance(corpus, list):
            continue
        for item in corpus:
            if not isinstance(item, dict):
                continue
            doc_id = str(item.get("doc_id") or item.get("id") or "")
            if strategy == "dedupe" and doc_id and doc_id in seen_doc_ids:
                continue
            merged.append(item)
            if doc_id:
                seen_doc_ids.add(doc_id)
    context.shared["scoped_corpus"] = merged
    return {"corpus": merged}


def execute_clean_text(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        cleaned, flags = pipeline_ops.apply_cleaning(str(item.get("raw_text") or ""), params)
        item["clean_text"] = cleaned
        if flags:
            context.log(node, f"{item['doc_id']} 命中清洗规则：{', '.join(flags)}")
        if not cleaned:
            item["status"] = "warning"
            context.warning(f"{item['doc_id']} 在清洗后为空。", node)
        _report_corpus_progress(context, node, index, total, "基础清洗")
    context.shared["clean_corpus"] = corpus
    return {"clean_corpus": corpus}


def execute_normalize_text(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        normalized, audit_rows = pipeline_ops.apply_normalization(
            str(item.get("clean_text") or ""),
            context.manifest["dictionary_set"],
            params,
        )
        item["normalized_text"] = normalized
        for audit in audit_rows:
            audit["doc_id"] = item["doc_id"]
        context.add_audits(audit_rows)
        _report_corpus_progress(context, node, index, total, "统一写法")
    context.shared["normalized_corpus"] = corpus
    return {"normalized_corpus": corpus}


def execute_tokenize(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        tokens, phrase_hits = pipeline_ops.tokenize_text(
            str(item.get("normalized_text") or item.get("clean_text") or ""),
            context.manifest["dictionary_set"],
            params,
        )
        item["tokens"] = tokens
        item["phrase_hits"] = phrase_hits
        _report_corpus_progress(context, node, index, total, "切词")
    context.shared["token_corpus"] = corpus
    return {"token_corpus": corpus}


def execute_apply_dictionary_rules(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    node_audits: list[dict[str, Any]] = []
    runtime_state = context.shared.get("dictionary_runtime_state")
    if runtime_state is None:
        runtime_state = pipeline_ops.build_dictionary_runtime_state(context.manifest["dictionary_set"])
        context.shared["dictionary_runtime_state"] = runtime_state
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        mapped_tokens, audits = pipeline_ops.apply_dictionary(
            item["doc_id"],
            list(item.get("tokens") or []),
            context.manifest["dictionary_set"],
            params,
            runtime_state=runtime_state,
        )
        item["tokens"] = mapped_tokens
        node_audits.extend(audits)
        _report_corpus_progress(context, node, index, total, "套用词表")
    context.add_audits(node_audits)
    context.shared["dictionary_corpus"] = corpus
    return {"token_corpus": corpus, "audit_table": node_audits}


def execute_filter_terms(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    if params.get("filter_by_pos", False):
        context.warning("当前原生 DAG 运行时尚未实现词性过滤，已按关闭处理。", node)
    pipeline_ops.filter_token_lists(corpus, params, context.manifest["dictionary_set"])
    context.node_progress(node, 1.0, f"过滤词项 {len(corpus)}/{len(corpus) or 1}")
    context.shared["filtered_corpus"] = corpus
    return {"filtered_token_corpus": corpus}


def execute_frequency_statistics(context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    df_tokens = pipeline_ops.explode_tokens(corpus)
    return {"frequency_table": pipeline_ops.frequency_table(df_tokens)}


def execute_term_document_analysis(context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    df_tokens = pipeline_ops.explode_tokens(corpus)
    return {"term_document_table": pipeline_ops.term_document_table(df_tokens)}


def execute_term_year_analysis(context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    df_tokens = pipeline_ops.explode_tokens(corpus)
    return {"term_year_table": pipeline_ops.term_year_table(df_tokens)}


def execute_cooccurrence_analysis(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    return {
        "cooccurrence_table": pipeline_ops.cooccurrence_table(
            corpus,
            int(params.get("cooccurrence_window", 5) or 5),
            int(params.get("min_cooccurrence", 2) or 2),
            progress_callback=lambda current, total: context.node_progress(node, current / max(total, 1), f"共现分析 {current}/{total}"),
        )
    }


def execute_feature_term_selection(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    payload = _feature_term_payload(context, corpus, {"feature_term_count": params.get("feature_term_count")})
    return {"feature_term_table": payload["feature_rows"]}


def execute_keyword_extraction(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    payload = _keyword_payload(
        context,
        node,
        corpus,
        {
            "top_k_per_doc": params.get("top_k_per_doc"),
            "top_k_project": params.get("top_k_project"),
        },
    )
    return {"keyword_table": payload["keyword_rows"]}


def execute_keyword_clustering(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    feature_rows = inputs.get("feature_term_table_in") or []
    if not isinstance(feature_rows, list):
        feature_rows = [feature_rows]
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    selected_count = sum(1 for row in feature_rows if isinstance(row, dict) and row.get("selected"))
    payload = _feature_term_payload(context, corpus, {"feature_term_count": selected_count or "all"})
    cluster_rows, topic_lookup = pipeline_ops.keyword_clusters(
        feature_rows,
        payload["tfidf_bundle"],
        int(params.get("keyword_cluster_k", 4) or 4),
    )
    context.shared["topic_lookup"] = topic_lookup
    return {"keyword_cluster_table": cluster_rows}


def execute_institution_keyword_analysis(context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    keyword_rows = inputs.get("keyword_table_in") or []
    if not isinstance(keyword_rows, list):
        keyword_rows = [keyword_rows]
    corpus = _scoped_corpus_from_inputs(context, inputs)
    institution_keyword_rows, _ = pipeline_ops.institution_keyword_and_topic(
        corpus,
        keyword_rows,
        {},
        {},
    )
    return {"institution_keyword_table": institution_keyword_rows}


def execute_institution_topic_analysis(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
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
    payload = _feature_term_payload(
        context,
        corpus,
        {"feature_term_count": topic_feature_count or _analysis_params(context).get("feature_term_count")},
    )
    _, doc_topics = pipeline_ops.nmf_topic_model(
        corpus,
        payload["tfidf_bundle"],
        _analysis_params(context, {"topic_model_k": params.get("topic_model_k")}),
    )
    topic_lookup = _topic_lookup_from_cluster_rows(cluster_rows)
    _, institution_topic_rows = pipeline_ops.institution_keyword_and_topic(
        corpus,
        [],
        doc_topics,
        topic_lookup,
    )
    return {"institution_topic_table": institution_topic_rows}


def execute_document_clustering(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    pipeline_ops = _pipeline_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    payload = _feature_term_payload(context, corpus)
    rows = pipeline_ops.document_clusters(
        corpus,
        payload["tfidf_bundle"],
        int(params.get("document_cluster_k", 4) or 4),
    )
    return {"document_cluster_table": rows}


def execute_save_csv(_context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    tables = inputs.get("table_in") or []
    if not isinstance(tables, list):
        tables = [tables]
    return {"artifact": {"kind": "csv", "count": len(tables)}}


def execute_save_xlsx(_context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    tables = inputs.get("table_in") or []
    if not isinstance(tables, list):
        tables = [tables]
    return {"artifact": {"kind": "xlsx", "count": len(tables)}}


def execute_save_png(_context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    renderables = inputs.get("render_in") or []
    if not isinstance(renderables, list):
        renderables = [renderables]
    return {"artifact": {"kind": "png", "count": len(renderables)}}


def execute_save_html_report(_context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    report_inputs = inputs.get("report_in") or []
    if not isinstance(report_inputs, list):
        report_inputs = [report_inputs]
    return {"artifact": {"kind": "html", "count": len(report_inputs)}}


def execute_legacy_passthrough(_context: Any, _node: dict[str, Any], _inputs: dict[str, Any]) -> dict[str, Any]:
    return {}


EXECUTORS_BY_TYPE = {
    "corpus_input": execute_corpus_input,
    "load_project_corpus": execute_corpus_input,
    "filter_corpus": execute_filter_corpus,
    "dictionary_input": execute_dictionary_input,
    "project_dictionary_set": execute_dictionary_input,
    "merge_corpora": execute_merge_corpora,
    "clean_text": execute_clean_text,
    "normalize_text": execute_normalize_text,
    "tokenize": execute_tokenize,
    "apply_dictionary_rules": execute_apply_dictionary_rules,
    "filter_terms": execute_filter_terms,
    "frequency_statistics": execute_frequency_statistics,
    "term_document_analysis": execute_term_document_analysis,
    "term_year_analysis": execute_term_year_analysis,
    "cooccurrence_analysis": execute_cooccurrence_analysis,
    "feature_term_selection": execute_feature_term_selection,
    "keyword_extraction": execute_keyword_extraction,
    "keyword_clustering": execute_keyword_clustering,
    "institution_keyword_analysis": execute_institution_keyword_analysis,
    "institution_topic_analysis": execute_institution_topic_analysis,
    "document_clustering": execute_document_clustering,
    "save_csv": execute_save_csv,
    "save_xlsx": execute_save_xlsx,
    "save_png": execute_save_png,
    "save_html_report": execute_save_html_report,
    "analyze_corpus": execute_legacy_passthrough,
    "export_results": execute_legacy_passthrough,
}


def register_builtin_node_executors(builder: NodeRegistryBuilder) -> None:
    for definition in build_builtin_node_definitions(builder.pipeline_definition):
        runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
        executor_id = str(runtime.get("executor") or "")
        node_type = str(definition.get("type") or "")
        if not executor_id or not node_type:
            continue
        executor = EXECUTORS_BY_TYPE.get(node_type, execute_legacy_passthrough)
        builder.register_executor(executor_id, executor)
