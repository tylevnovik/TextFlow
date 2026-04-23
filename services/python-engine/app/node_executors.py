from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import random
from typing import Any

from .node_definitions import build_builtin_node_definitions
from .node_registry import NodeRegistryBuilder


def _analysis_ops():
    from . import analysis_ops as analysis_ops_module

    return analysis_ops_module


def _text_ops():
    from . import text_ops as text_ops_module

    return text_ops_module


def _runtime_support():
    from . import runtime_support as runtime_support_module

    return runtime_support_module


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
    for key in [
        "filtered_corpus",
        "dictionary_corpus",
        "token_corpus",
        "normalized_corpus",
        "clean_corpus",
        "scoped_corpus",
    ]:
        if hasattr(context, "get_shared_value"):
            value = context.get_shared_value(key)
        else:
            shared = getattr(context, "shared", {})
            value = shared.get(key)
        if is_corpus_rows(value):
            return value
    return []


def _analysis_params(context: Any, patch: dict[str, Any] | None = None) -> dict[str, Any]:
    base = deepcopy(((context.runtime_profile or {}).get("analysis") or {}))
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
    payload = context.get_shared_cache_value("feature_term_payloads", cache_key) if hasattr(context, "get_shared_cache_value") else None
    if payload is not None:
        return payload
    analysis_ops = _analysis_ops()
    feature_rows, tfidf_bundle = analysis_ops.tfidf_feature_bundle(corpus, analysis_params)
    payload = {
        "feature_rows": feature_rows,
        "tfidf_bundle": tfidf_bundle,
        "analysis_params": analysis_params,
    }
    if hasattr(context, "set_shared_cache_value"):
        context.set_shared_cache_value("feature_term_payloads", cache_key, payload)
    else:
        context.shared.setdefault("feature_term_payloads", {})[cache_key] = payload
    return payload


def _token_frame(context: Any, corpus: list[dict[str, Any]]) -> Any:
    cache_key = id(corpus)
    frame = context.get_shared_cache_value("token_frames", cache_key) if hasattr(context, "get_shared_cache_value") else None
    if frame is not None:
        return frame
    analysis_ops = _analysis_ops()
    frame = analysis_ops.explode_tokens(corpus)
    if hasattr(context, "set_shared_cache_value"):
        context.set_shared_cache_value("token_frames", cache_key, frame)
    else:
        context.shared.setdefault("token_frames", {})[cache_key] = frame
    return frame


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
    payload = context.get_shared_cache_value("keyword_payloads", cache_key) if hasattr(context, "get_shared_cache_value") else None
    if payload is not None:
        return payload
    analysis_ops = _analysis_ops()
    feature_payload = _feature_term_payload(
        context,
        corpus,
        {"feature_term_count": analysis_params.get("feature_term_count")},
    )
    keyword_rows = analysis_ops.extract_keyword_rows(
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
    if hasattr(context, "set_shared_cache_value"):
        context.set_shared_cache_value("keyword_payloads", cache_key, payload)
    else:
        context.shared.setdefault("keyword_payloads", {})[cache_key] = payload
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
    runtime_support = _runtime_support()
    scope = runtime_support.normalize_run_scope(node.get("config") if isinstance(node.get("config"), dict) else {})
    scoped = [item for item in context.full_corpus if runtime_support.document_matches_scope(item, scope)]
    context.shared["run_scope"] = scope
    context.shared["run_scope_summary"] = runtime_support.describe_run_scope(scope, len(context.full_corpus), len(scoped))
    context.shared["scoped_corpus"] = scoped
    return {"corpus": scoped}


def execute_filter_corpus(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    runtime_support = _runtime_support()
    scope = runtime_support.normalize_run_scope(node.get("config") if isinstance(node.get("config"), dict) else {})
    corpus = _scoped_corpus_from_inputs(context, inputs)
    scoped = [item for item in corpus if runtime_support.document_matches_scope(item, scope)]
    context.shared["run_scope"] = scope
    context.shared["run_scope_summary"] = runtime_support.describe_run_scope(scope, len(context.full_corpus), len(scoped))
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


def _metadata_filter_conditions(config: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(config.get("conditions"), list):
        conditions = [item for item in config.get("conditions", []) if isinstance(item, dict)]
        if conditions:
            return conditions
    field = str(config.get("field") or "").strip()
    if not field:
        return []
    values = config.get("values")
    if isinstance(values, list):
        normalized_values = [str(item) for item in values if str(item).strip()]
    else:
        values_text = str(config.get("values_text") or "")
        normalized_values = [item.strip() for item in values_text.split(",") if item.strip()]
    return [{
        "field": field,
        "operator": str(config.get("operator") or "in"),
        "values": normalized_values,
    }]


def _document_field_value(document: dict[str, Any], field: str) -> Any:
    if field in document:
        return document.get(field)
    extra_metadata = document.get("extra_metadata") if isinstance(document.get("extra_metadata"), dict) else {}
    return extra_metadata.get(field)


def _document_matches_condition(document: dict[str, Any], condition: dict[str, Any]) -> bool:
    field = str(condition.get("field") or "").strip()
    operator = str(condition.get("operator") or "in")
    values = [str(item) for item in condition.get("values", []) if str(item).strip()]
    value = _document_field_value(document, field)
    value_text = str(value or "")
    if operator == "not_in":
        return value_text not in set(values)
    if operator == "contains":
        return any(item in value_text for item in values)
    if operator == "eq":
        return value_text == (values[0] if values else "")
    return value_text in set(values)


def execute_filter_by_metadata(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    conditions = _metadata_filter_conditions(config)
    if not conditions:
        context.shared["scoped_corpus"] = corpus
        return {"filtered_corpus": corpus}
    filtered = [
        item
        for item in corpus
        if all(_document_matches_condition(item, condition) for condition in conditions)
    ]
    context.shared["scoped_corpus"] = filtered
    return {"filtered_corpus": filtered}


def _dedupe_signature(item: dict[str, Any], keys: list[str]) -> tuple[Any, ...]:
    return tuple(_document_field_value(item, key) for key in keys)


def execute_deduplicate_documents(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    dedupe_keys = config.get("dedupe_keys")
    if isinstance(dedupe_keys, list):
        keys = [str(item) for item in dedupe_keys if str(item).strip()]
    else:
        keys = [item.strip() for item in str(config.get("dedupe_keys_text") or "title,year").split(",") if item.strip()]
    if not keys:
        context.shared["scoped_corpus"] = corpus
        return {"deduped_corpus": corpus}
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for item in corpus:
        signature = _dedupe_signature(item, keys)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(item)
    context.shared["scoped_corpus"] = deduped
    return {"deduped_corpus": deduped}


def execute_sample_corpus(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    if not corpus:
        return {"sampled_corpus": []}
    seed = int(config.get("seed", 42) or 42)
    sample_ratio = config.get("sample_ratio")
    sample_size = config.get("sample_size")
    if sample_ratio not in (None, ""):
        requested = max(0, min(len(corpus), round(len(corpus) * float(sample_ratio))))
    else:
        requested = max(0, min(len(corpus), int(sample_size or len(corpus))))
    if requested >= len(corpus):
        sampled = corpus
    else:
        rng = random.Random(seed)
        sampled = [corpus[index] for index in sorted(rng.sample(range(len(corpus)), requested))]
    context.shared["scoped_corpus"] = sampled
    return {"sampled_corpus": sampled}


def _normalize_split_definitions(config: dict[str, Any]) -> list[tuple[str, float]]:
    raw_splits = config.get("splits")
    if isinstance(raw_splits, list):
        normalized = [
            (str(item.get("name") or ""), float(item.get("ratio") or 0))
            for item in raw_splits
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
        if normalized:
            return normalized
    splits_text = str(config.get("splits_text") or "train:0.7\ntest:0.3")
    splits: list[tuple[str, float]] = []
    for line in splits_text.splitlines():
        if ":" not in line:
            continue
        name, raw_ratio = line.split(":", 1)
        name = name.strip()
        if not name:
            continue
        try:
            ratio = float(raw_ratio.strip())
        except ValueError:
            continue
        splits.append((name, ratio))
    return splits


def execute_split_corpus(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    splits = _normalize_split_definitions(config)
    if not corpus or not splits:
        return {"split_assignment_table": []}
    seed = int(config.get("seed", 42) or 42)
    rng = random.Random(seed)
    ordered_indices = list(range(len(corpus)))
    rng.shuffle(ordered_indices)
    total_ratio = sum(max(ratio, 0.0) for _, ratio in splits) or float(len(splits))
    assignments: list[dict[str, Any]] = []
    offset = 0
    for index, (name, ratio) in enumerate(splits):
        if index == len(splits) - 1:
            bucket_indices = ordered_indices[offset:]
        else:
            bucket_size = round(len(corpus) * (max(ratio, 0.0) / total_ratio))
            bucket_indices = ordered_indices[offset : offset + bucket_size]
        for item_index in bucket_indices:
            item = corpus[item_index]
            assignments.append(
                {
                    "doc_id": item.get("doc_id"),
                    "title": item.get("title"),
                    "split_name": name,
                }
            )
        offset += len(bucket_indices)
    assignments.sort(key=lambda item: str(item.get("doc_id") or ""))
    return {"split_assignment_table": assignments}


def _bucket_label(year: int, granularity: str) -> str:
    if granularity == "5_year":
        bucket_start = year - ((year - 1) % 5)
        return f"{bucket_start}-{bucket_start + 4}"
    if granularity == "decade":
        bucket_start = year - (year % 10)
        return f"{bucket_start}s"
    return str(year)


def execute_bucket_by_time(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    field = str(config.get("field") or "year")
    granularity = str(config.get("granularity") or "year")
    assignments: list[dict[str, Any]] = []
    for item in corpus:
        value = _document_field_value(item, field)
        try:
            year = int(value)
        except (TypeError, ValueError):
            continue
        assignments.append(
            {
                "doc_id": item.get("doc_id"),
                "title": item.get("title"),
                "year": year,
                "time_bucket": _bucket_label(year, granularity),
            }
        )
    return {"time_bucket_table": assignments}


def execute_clean_text(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    text_ops = _text_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        cleaned, flags = text_ops.apply_cleaning(str(item.get("raw_text") or ""), params)
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
    text_ops = _text_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        normalized, audit_rows = text_ops.apply_normalization(
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
    text_ops = _text_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        tokens, phrase_hits = text_ops.tokenize_text(
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
    text_ops = _text_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    node_audits: list[dict[str, Any]] = []
    runtime_state = context.shared.get("dictionary_runtime_state")
    if runtime_state is None:
        runtime_state = text_ops.build_dictionary_runtime_state(context.manifest["dictionary_set"])
        context.shared["dictionary_runtime_state"] = runtime_state
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        mapped_tokens, audits = text_ops.apply_dictionary(
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
    text_ops = _text_ops()
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    if params.get("filter_by_pos", False):
        context.warning("当前原生 DAG 运行时尚未实现词性过滤，已按关闭处理。", node)
    text_ops.filter_token_lists(corpus, params, context.manifest["dictionary_set"])
    context.node_progress(node, 1.0, f"过滤词项 {len(corpus)}/{len(corpus) or 1}")
    context.shared["filtered_corpus"] = corpus
    return {"filtered_token_corpus": corpus}


def execute_frequency_statistics(context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    df_tokens = _token_frame(context, corpus)
    return {"frequency_table": analysis_ops.frequency_table(df_tokens)}


def execute_term_document_analysis(context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    df_tokens = _token_frame(context, corpus)
    return {"term_document_table": analysis_ops.term_document_table(df_tokens)}


def execute_term_year_analysis(context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    df_tokens = _token_frame(context, corpus)
    return {"term_year_table": analysis_ops.term_year_table(df_tokens)}


def execute_cooccurrence_analysis(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    return {
        "cooccurrence_table": analysis_ops.cooccurrence_table(
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
    analysis_ops = _analysis_ops()
    feature_rows = inputs.get("feature_term_table_in") or []
    if not isinstance(feature_rows, list):
        feature_rows = [feature_rows]
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    selected_count = sum(1 for row in feature_rows if isinstance(row, dict) and row.get("selected"))
    payload = _feature_term_payload(context, corpus, {"feature_term_count": selected_count or "all"})
    cluster_rows, topic_lookup = analysis_ops.keyword_clusters(
        feature_rows,
        payload["tfidf_bundle"],
        int(params.get("keyword_cluster_k", 4) or 4),
    )
    if hasattr(context, "set_shared_value"):
        context.set_shared_value("topic_lookup", topic_lookup)
    else:
        context.shared["topic_lookup"] = topic_lookup
    return {"keyword_cluster_table": cluster_rows}


def execute_institution_keyword_analysis(context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    keyword_rows = inputs.get("keyword_table_in") or []
    if not isinstance(keyword_rows, list):
        keyword_rows = [keyword_rows]
    corpus = _scoped_corpus_from_inputs(context, inputs)
    institution_keyword_rows, _ = analysis_ops.institution_keyword_and_topic(
        corpus,
        keyword_rows,
        {},
        {},
    )
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
    payload = _feature_term_payload(
        context,
        corpus,
        {"feature_term_count": topic_feature_count or _analysis_params(context).get("feature_term_count")},
    )
    _, doc_topics = analysis_ops.nmf_topic_model(
        corpus,
        payload["tfidf_bundle"],
        _analysis_params(context, {"topic_model_k": params.get("topic_model_k")}),
    )
    topic_lookup = _topic_lookup_from_cluster_rows(cluster_rows)
    _, institution_topic_rows = analysis_ops.institution_keyword_and_topic(
        corpus,
        [],
        doc_topics,
        topic_lookup,
    )
    return {"institution_topic_table": institution_topic_rows}


def execute_document_clustering(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    payload = _feature_term_payload(context, corpus)
    rows = analysis_ops.document_clusters(
        corpus,
        payload["tfidf_bundle"],
        int(params.get("document_cluster_k", 4) or 4),
    )
    return {"document_cluster_table": rows}


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
        "selected_feature_terms": [],
        "keyword_result": [],
        "keyword_cluster_result": [],
        "institution_keyword_cooccurrence": [],
        "institution_topic_cooccurrence": [],
        "clustering_result": [],
        "audit_table": list(context.result_bundle.get("audit_table") or []),
    }

    if include_frequency or include_term_document or include_term_year:
        df_tokens = _token_frame(context, corpus)
        if include_frequency:
            bundle["frequency_table"] = analysis_ops.frequency_table(df_tokens)
        if include_term_document:
            bundle["term_document_table"] = analysis_ops.term_document_table(df_tokens)
        if include_term_year:
            bundle["term_year_table"] = analysis_ops.term_year_table(df_tokens)

    if include_cooccurrence:
        bundle["cooccurrence_table"] = analysis_ops.cooccurrence_table(
            corpus,
            int(analysis_params.get("cooccurrence_window", 5) or 5),
            int(analysis_params.get("min_cooccurrence", 2) or 2),
            progress_callback=lambda current, total: context.node_progress(
                node,
                current / max(total, 1),
                f"旧版聚合分析 {current}/{total}",
            ),
        )

    needs_feature_payload = include_feature_terms or include_keyword_clusters or include_institution_topics or include_document_clusters
    feature_payload = (
        _feature_term_payload(
            context,
            corpus,
            {"feature_term_count": analysis_params.get("feature_term_count")},
        )
        if needs_feature_payload
        else None
    )
    if include_feature_terms and feature_payload is not None:
        bundle["selected_feature_terms"] = feature_payload["feature_rows"]

    keyword_payload = (
        _keyword_payload(
            context,
            node,
            corpus,
            {
                "top_k_per_doc": analysis_params.get("top_k_per_doc"),
                "top_k_project": analysis_params.get("top_k_project"),
            },
        )
        if include_keywords or include_institution_keywords
        else None
    )
    if include_keywords and keyword_payload is not None:
        bundle["keyword_result"] = keyword_payload["keyword_rows"]

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

    if include_institution_topics and feature_payload is not None:
        _, doc_topics = analysis_ops.nmf_topic_model(corpus, feature_payload["tfidf_bundle"], analysis_params)

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

    if include_document_clusters and feature_payload is not None:
        bundle["clustering_result"] = analysis_ops.document_clusters(
            corpus,
            feature_payload["tfidf_bundle"],
            int(analysis_params.get("document_cluster_k", 4) or 4),
        )

    return bundle


def execute_legacy_analyze_corpus(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _scoped_corpus_from_inputs(context, inputs)
    bundle = _legacy_analysis_bundle(context, node, corpus)
    context.result_bundle.update(bundle)
    return {
        "analysis_bundle": bundle,
        "audit_table": bundle["audit_table"],
    }


def execute_legacy_export_results(context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_bundle = inputs.get("analysis_bundle_in") or {}
    audit_rows = inputs.get("audit_table_in") or []
    if isinstance(analysis_bundle, dict):
        for key, value in analysis_bundle.items():
            if key in context.result_bundle and isinstance(value, list):
                context.result_bundle[key] = value
    if isinstance(audit_rows, list):
        context.result_bundle["audit_table"] = audit_rows
    return {"artifact": {"kind": "legacy_export", "count": len(context.result_bundle)}}


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
    "filter_by_metadata": execute_filter_by_metadata,
    "deduplicate_documents": execute_deduplicate_documents,
    "sample_corpus": execute_sample_corpus,
    "split_corpus": execute_split_corpus,
    "bucket_by_time": execute_bucket_by_time,
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
    "analyze_corpus": execute_legacy_analyze_corpus,
    "export_results": execute_legacy_export_results,
}


def register_builtin_node_executors(builder: NodeRegistryBuilder) -> None:
    for definition in build_builtin_node_definitions(builder.runtime_profile_definition):
        runtime = definition.get("runtime") if isinstance(definition.get("runtime"), dict) else {}
        executor_id = str(runtime.get("executor") or "")
        node_type = str(definition.get("type") or "")
        if not executor_id or not node_type:
            continue
        executor = EXECUTORS_BY_TYPE.get(node_type, execute_legacy_passthrough)
        builder.register_executor(executor_id, executor)
