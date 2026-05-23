from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import math
import random
import re
from typing import Any

def _analysis_ops():
    from ... import analysis_ops as analysis_ops_module

    return analysis_ops_module


def _text_ops():
    from ...analysis import text as text_ops_module

    return text_ops_module


def _runtime_support():
    from ... import runtime_support as runtime_support_module

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
        base.update({key: value for key, value in patch.items() if value is not None})
    return base


def _clone_corpus_rows(corpus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) if isinstance(item, dict) else item for item in corpus]


def _shared_get(context: Any, key: str, default: Any = None) -> Any:
    if hasattr(context, "get_shared_value"):
        return context.get_shared_value(key, default)
    shared = getattr(context, "shared", {})
    return shared.get(key, default) if isinstance(shared, dict) else default


def _shared_set(context: Any, key: str, value: Any) -> Any:
    if hasattr(context, "set_shared_value"):
        return context.set_shared_value(key, value)
    if not isinstance(getattr(context, "shared", None), dict):
        context.shared = {}
    context.shared[key] = value
    return value


def _shared_pop(context: Any, key: str) -> Any:
    shared = getattr(context, "shared", {})
    if isinstance(shared, dict):
        return shared.pop(key, None)
    return None


def _is_table_rows(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    if not value:
        return True
    return isinstance(value[0], dict)


def _table_rows_from_inputs_or_results(
    context: Any,
    inputs: dict[str, Any],
    input_key: str,
    artifact_key: str = "",
) -> list[dict[str, Any]]:
    input_value = inputs.get(input_key)
    if _is_table_rows(input_value):
        return deepcopy(input_value)
    if isinstance(input_value, dict):
        return [deepcopy(input_value)]
    if artifact_key:
        bundle = getattr(context, "result_bundle", {})
        value = bundle.get(artifact_key) if isinstance(bundle, dict) else None
        if _is_table_rows(value):
            return deepcopy(value)
        shared_value = _shared_get(context, artifact_key)
        if _is_table_rows(shared_value):
            return deepcopy(shared_value)
    return []


def _join_keys(config: dict[str, Any]) -> list[str]:
    raw_keys = config.get("join_keys")
    if isinstance(raw_keys, list):
        join_keys = [str(item).strip() for item in raw_keys if str(item).strip()]
        if join_keys:
            return join_keys
    return [item.strip() for item in str(config.get("join_keys_text") or "").split(",") if item.strip()]


def _report_corpus_progress(context: Any, node: dict[str, Any], completed: int, total: int, stage: str) -> None:
    if not total:
        return
    if completed == 1 or completed == total or completed % 250 == 0:
        context.node_progress(node, completed / total, f"{stage} {completed}/{total}")


def _report_node_progress(context: Any, node: dict[str, Any], fraction: float, detail: str) -> None:
    reporter = getattr(context, "node_progress", None)
    if callable(reporter):
        reporter(node, fraction, detail)


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
    *,
    progress_start: float = 0.2,
    progress_end: float = 0.87,
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
        progress_callback=lambda current, total: _report_node_progress(
            context,
            node,
            progress_start + (progress_end - progress_start) * current / max(total, 1),
            f"关键词提取：处理 {current}/{total} 篇文档",
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


__all__ = [name for name in globals() if not name.startswith("__")]
