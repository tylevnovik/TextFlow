from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import math
import random
import re
from typing import Any


def _analysis_ops():
    from ... import analysis as analysis_ops_module

    return analysis_ops_module


def _text_ops():
    from ...analysis import text as text_ops_module

    return text_ops_module


def _runtime_support():
    from ...workflow.runtime import support as runtime_support_module

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


# --- Shared Helpers from executors/corpus.py ---

def _is_dictionary_set(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("collections"), dict) and isinstance(value.get("sheets"), dict)


def _active_dictionary_set(context: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    for value in inputs.values():
        if _is_dictionary_set(value):
            return value
    shared_dictionary_set = _shared_get(context, "active_dictionary_set")
    if _is_dictionary_set(shared_dictionary_set):
        return shared_dictionary_set
    manifest = getattr(context, "manifest", {}) if isinstance(getattr(context, "manifest", {}), dict) else {}
    dictionary_set = manifest.get("dictionary_set")
    return dictionary_set if _is_dictionary_set(dictionary_set) else {"collections": {}, "sheets": {}}


def _set_active_dictionary_set(context: Any, dictionary_set: dict[str, Any]) -> dict[str, Any]:
    _shared_set(context, "active_dictionary_set", dictionary_set)
    _shared_set(context, "dictionary_runtime_state_source_id", id(dictionary_set))
    _shared_pop(context, "dictionary_runtime_state")
    return dictionary_set


def _rebuild_dictionary_sheets(dictionary_set: dict[str, Any]) -> dict[str, Any]:
    collections = dictionary_set.get("collections") if isinstance(dictionary_set.get("collections"), dict) else {}
    sheets = dictionary_set.get("sheets") if isinstance(dictionary_set.get("sheets"), dict) else {}
    for kind, collection in collections.items():
        tables = collection.get("tables") if isinstance(collection, dict) and isinstance(collection.get("tables"), list) else []
        merged_entries: list[dict[str, Any]] = []
        for table in tables:
            if not isinstance(table, dict) or not bool(table.get("enabled", True)):
                continue
            merged_entries.extend(deepcopy(table.get("entries") or []))
        existing_sheet = sheets.get(kind) if isinstance(sheets.get(kind), dict) else {}
        sheets[kind] = {
            "kind": str(existing_sheet.get("kind") or kind),
            "name": str(existing_sheet.get("name") or kind),
            "version": str(existing_sheet.get("version") or "2.0.0"),
            "entries": merged_entries,
        }
    dictionary_set["sheets"] = sheets
    return dictionary_set


def _document_field_value(document: dict[str, Any], field: str) -> Any:
    if field in document:
        return document.get(field)
    extra_metadata = document.get("extra_metadata") if isinstance(document.get("extra_metadata"), dict) else {}
    return extra_metadata.get(field)


def _control_values(config: dict[str, Any]) -> list[Any]:
    raw_values = config.get("values")
    if isinstance(raw_values, list):
        values = [item for item in raw_values if str(item).strip()]
        if values:
            return values
    raw_value = config.get("value")
    if raw_value not in (None, ""):
        return [raw_value]
    values_text = str(config.get("values_text") or "")
    return [item.strip() for item in values_text.replace("\n", ",").split(",") if item.strip()]


def _control_rows_from_value(value: Any) -> list[dict[str, Any]]:
    if _is_table_rows(value):
        return deepcopy(value)
    if isinstance(value, dict):
        return [deepcopy(value)]
    return []


def _control_rows_from_inputs(inputs: dict[str, Any], *input_keys: str) -> list[dict[str, Any]]:
    for input_key in input_keys:
        rows = _control_rows_from_value(inputs.get(input_key))
        if rows:
            return rows
    return []


def _record_field_value(record: dict[str, Any], field: str) -> Any:
    normalized_field = str(field or "").strip()
    if not normalized_field:
        return None
    if normalized_field in record:
        return record.get(normalized_field)
    current: Any = record
    for part in normalized_field.split("."):
        if not isinstance(current, dict) or part not in current:
            current = None
            break
        current = current.get(part)
    if current is not None:
        return current
    extra_metadata = record.get("extra_metadata") if isinstance(record.get("extra_metadata"), dict) else {}
    return extra_metadata.get(normalized_field)


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _compare_control_value(value: Any, operator: str, expected_values: list[Any]) -> bool:
    normalized_operator = str(operator or "in").strip().lower()
    value_text = str(value if value is not None else "")
    expected_texts = [str(item) for item in expected_values if str(item).strip()]
    expected_set = set(expected_texts)

    if normalized_operator == "not_in":
        return value_text not in expected_set
    if normalized_operator == "contains":
        return any(expected in value_text for expected in expected_texts)
    if normalized_operator == "eq":
        return value_text == (expected_texts[0] if expected_texts else "")
    if normalized_operator == "neq":
        return value_text != (expected_texts[0] if expected_texts else "")
    if normalized_operator in {"gt", "gte", "lt", "lte"}:
        left = _as_number(value)
        right = _as_number(expected_values[0] if expected_values else None)
        if left is None or right is None:
            return False
        if normalized_operator == "gt":
            return left > right
        if normalized_operator == "gte":
            return left >= right
        if normalized_operator == "lt":
            return left < right
        return left <= right
    return value_text in expected_set


def _record_matches_control_condition(record: dict[str, Any], config: dict[str, Any]) -> bool:
    field = str(config.get("field") or "").strip()
    return _compare_control_value(
        _record_field_value(record, field),
        str(config.get("operator") or "in"),
        _control_values(config),
    )


# --- Shared Helpers from executors/analysis.py ---

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
