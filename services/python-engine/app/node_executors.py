from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import math
import random
import re
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
    dictionary_set = deepcopy(context.manifest["dictionary_set"])
    active_dictionary_set = _set_active_dictionary_set(context, dictionary_set)
    return {"dictionary_set": active_dictionary_set}


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


def _selected_table_ids(config: dict[str, Any]) -> list[str]:
    raw_ids = config.get("selected_table_ids")
    if isinstance(raw_ids, list):
        selected = [str(item).strip() for item in raw_ids if str(item).strip()]
        if selected:
            return selected
    return [
        item.strip()
        for item in re.split(r"[\r\n,]+", str(config.get("selected_table_ids_text") or ""))
        if item.strip()
    ]


def _overlay_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(config.get("overlay_rows"), list):
        rows = [item for item in config.get("overlay_rows", []) if isinstance(item, dict)]
        if rows:
            return rows
    rows: list[dict[str, Any]] = []
    for line in str(config.get("overlay_rows_text") or "").splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3 or not parts[0] or not parts[1]:
            continue
        rows.append(
            {
                "kind": parts[0],
                "source": parts[1],
                "target": parts[2] or None,
                "enabled": parts[3].lower() != "false" if len(parts) > 3 else True,
            }
        )
    return rows


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


def execute_select_dictionary_tables(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    dictionary_set = deepcopy(_active_dictionary_set(context, inputs))
    selected_tokens = {
        item.casefold()
        for item in _selected_table_ids(node.get("config") if isinstance(node.get("config"), dict) else {})
    }
    if not selected_tokens:
        active_dictionary_set = _set_active_dictionary_set(context, dictionary_set)
        return {"dictionary_set": active_dictionary_set}
    collections = dictionary_set.get("collections") if isinstance(dictionary_set.get("collections"), dict) else {}
    for kind, collection in collections.items():
        if not isinstance(collection, dict):
            continue
        tables = collection.get("tables")
        if isinstance(tables, list):
            collection["tables"] = [
                deepcopy(table)
                for table in tables
                if isinstance(table, dict)
                and (
                    str(table.get("id") or "").strip().casefold() in selected_tokens
                    or str(table.get("kind") or kind).strip().casefold() in selected_tokens
                )
            ]
    active_dictionary_set = _set_active_dictionary_set(context, _rebuild_dictionary_sheets(dictionary_set))
    return {"dictionary_set": active_dictionary_set}


def execute_overlay_dictionary_rules(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    dictionary_set = deepcopy(_active_dictionary_set(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    rows = _overlay_rows(config)
    if not rows:
        active_dictionary_set = _set_active_dictionary_set(context, dictionary_set)
        return {"dictionary_set": active_dictionary_set}
    collections = dictionary_set.get("collections") if isinstance(dictionary_set.get("collections"), dict) else {}
    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rows, start=1):
        kind = str(row.get("kind") or "").strip()
        source = str(row.get("source") or "").strip()
        if not kind or not source or kind not in collections:
            continue
        grouped_rows[kind].append(
            {
                "id": f"runtime-{kind}-{index}",
                "source": source,
                "target": row.get("target"),
                "enabled": bool(row.get("enabled", True)),
                "hits": 0,
                "tags": ["runtime-overlay"],
                "notes": "Runtime overlay node",
            }
        )
    for kind, entries in grouped_rows.items():
        collection = collections.get(kind)
        if not isinstance(collection, dict):
            continue
        tables = collection.get("tables") if isinstance(collection.get("tables"), list) else []
        tables.append(
            {
                "id": f"runtime-overlay-{kind}",
                "kind": kind,
                "name": "运行时叠加",
                "version": "2.0.0",
                "description": "Runtime-only dictionary overlay",
                "source_url": None,
                "built_in": False,
                "editable": False,
                "enabled": True,
                "tags": ["runtime-overlay"],
                "entries": entries,
            }
        )
        collection["tables"] = tables
    active_dictionary_set = _set_active_dictionary_set(context, _rebuild_dictionary_sheets(dictionary_set))
    return {"dictionary_set": active_dictionary_set}


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


def execute_conditional_router(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    corpus_input = inputs.get("corpus_in")
    corpus = _clone_corpus_rows(corpus_input) if _is_table_rows(corpus_input) else _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    table_rows = _control_rows_from_inputs(inputs, "table_in", "record_table_in", "comparison_table_in")

    matched_corpus = [item for item in corpus if _record_matches_control_condition(item, config)] if corpus else []
    unmatched_corpus = [item for item in corpus if not _record_matches_control_condition(item, config)] if corpus else []
    matched_table = [item for item in table_rows if _record_matches_control_condition(item, config)] if table_rows else []
    unmatched_table = [item for item in table_rows if not _record_matches_control_condition(item, config)] if table_rows else []

    if matched_corpus:
        context.shared["scoped_corpus"] = matched_corpus

    matched_count = len(matched_corpus) if corpus else len(matched_table)
    unmatched_count = len(unmatched_corpus) if corpus else len(unmatched_table)
    route_summary = [
        {
            "source_kind": str(config.get("source_kind") or "corpus_metadata"),
            "field": str(config.get("field") or ""),
            "operator": str(config.get("operator") or "in"),
            "values": [str(item) for item in _control_values(config)],
            "matched_count": matched_count,
            "unmatched_count": unmatched_count,
            "corpus_input_count": len(corpus),
            "table_input_count": len(table_rows),
        }
    ]
    return {
        "matched_corpus": matched_corpus,
        "unmatched_corpus": unmatched_corpus,
        "matched_table": matched_table,
        "unmatched_table": unmatched_table,
        "route_summary": route_summary,
    }


def _metric_rows_from_context(context: Any, config: dict[str, Any]) -> list[dict[str, Any]]:
    artifact_key = str(config.get("metric_artifact") or "").strip()
    if not artifact_key:
        return []
    bundle = getattr(context, "result_bundle", {})
    if isinstance(bundle, dict):
        rows = _control_rows_from_value(bundle.get(artifact_key))
        if rows:
            return rows
    return _control_rows_from_value(_shared_get(context, artifact_key))


def _select_metric_row(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    metric_name = str(config.get("metric_name") or "").strip()
    metric_name_field = str(config.get("metric_name_field") or "metric").strip()
    if metric_name:
        for row in rows:
            if str(_record_field_value(row, metric_name_field) or "") == metric_name:
                return row
        for row in rows:
            if metric_name in row:
                return row
    for row in rows:
        if str(row.get("row_type") or "").lower() == "overall":
            return row
    return rows[0] if rows else {}


def _metric_observed_value(row: dict[str, Any], config: dict[str, Any]) -> Any:
    metric_field = str(config.get("metric_field") or "value").strip()
    metric_name = str(config.get("metric_name") or "").strip()
    value = _record_field_value(row, metric_field)
    if value is None and metric_name:
        value = _record_field_value(row, metric_name)
    return value


def execute_result_gate(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    metric_rows = _control_rows_from_inputs(inputs, "metric_table_in", "table_in") or _metric_rows_from_context(context, config)
    payload_rows = _control_rows_from_inputs(inputs, "payload_in") or metric_rows
    metric_row = _select_metric_row(metric_rows, config)
    observed_value = _metric_observed_value(metric_row, config)
    threshold = config.get("threshold")
    passed = _compare_control_value(observed_value, str(config.get("operator") or "gte"), [threshold])
    metric_name = str(config.get("metric_name") or config.get("metric_field") or "metric")
    gate_summary = [
        {
            "metric": metric_name,
            "metric_field": str(config.get("metric_field") or "value"),
            "operator": str(config.get("operator") or "gte"),
            "threshold": threshold,
            "observed_value": observed_value,
            "passed": passed,
            "input_count": len(payload_rows),
        }
    ]
    return {
        "passed": passed,
        "passed_table": payload_rows if passed else [],
        "blocked_table": [] if passed else payload_rows,
        "gate_summary": gate_summary,
    }


def _find_review_task(manifest: dict[str, Any], review_id: str) -> dict[str, Any] | None:
    tasks = manifest.get("review_tasks")
    if not isinstance(tasks, list):
        return None
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_review_id = str(task.get("review_id") or task.get("id") or "").strip()
        if task_review_id == review_id:
            return task
    return None


def execute_manual_review_gate(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    payload_rows = _control_rows_from_inputs(inputs, "payload_in", "table_in", "corpus_in")
    review_id = str(config.get("review_id") or config.get("task_id") or "").strip()
    required_status = str(config.get("required_status") or "resolved").strip().lower()
    on_missing = str(config.get("on_missing") or "block").strip().lower()
    manifest = getattr(context, "manifest", {})
    task = _find_review_task(manifest, review_id) if isinstance(manifest, dict) and review_id else None
    current_status = str(task.get("status") or "missing").strip().lower() if isinstance(task, dict) else "missing"
    approved = current_status == required_status or (task is None and on_missing == "pass")
    waiting = not approved
    review_gate_summary = [
        {
            "review_id": review_id,
            "required_status": required_status,
            "status": current_status,
            "waiting": waiting,
            "input_count": len(payload_rows),
        }
    ]
    return {
        "waiting": waiting,
        "approved_payload": payload_rows if approved else [],
        "blocked_payload": [] if approved else payload_rows,
        "review_gate_summary": review_gate_summary,
    }


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
            collect_audit=bool(getattr(context, "audit_enabled", True)),
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
    dictionary_set = _active_dictionary_set(context, inputs)
    params = node.get("config") if isinstance(node.get("config"), dict) else {}
    node_audits: list[dict[str, Any]] = []
    runtime_state = _shared_get(context, "dictionary_runtime_state")
    if runtime_state is None or _shared_get(context, "dictionary_runtime_state_source_id") != id(dictionary_set):
        runtime_state = text_ops.build_dictionary_runtime_state(dictionary_set)
        _shared_set(context, "dictionary_runtime_state", runtime_state)
        _shared_set(context, "dictionary_runtime_state_source_id", id(dictionary_set))
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        mapped_tokens, audits = text_ops.apply_dictionary(
            item["doc_id"],
            list(item.get("tokens") or []),
            dictionary_set,
            params,
            runtime_state=runtime_state,
            collect_audit=bool(getattr(context, "audit_enabled", True)),
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
    group_totals, term_counts, doc_sets, terms = _group_term_statistics(corpus, group_field)
    if not group_totals:
        return {"group_metric_table": []}
    comparison_groups = _comparison_groups(config, baseline_group, set(group_totals))
    selected_groups = [group for group in [baseline_group, *comparison_groups] if group and group in group_totals]
    if not selected_groups:
        selected_groups = sorted(group_totals)
    rows: list[dict[str, Any]] = []
    for group_value in selected_groups:
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
    rows.sort(key=lambda item: (str(item["group_value"]), -int(item["term_count"]), str(item["term"])))
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
    group_totals, term_counts, doc_sets, terms = _group_term_statistics(corpus, group_field)
    comparison_total = group_totals.get(comparison_group, 0)
    baseline_total = group_totals.get(baseline_group, 0)
    if not comparison_total or not baseline_total:
        return {"keyness_table": []}
    rows: list[dict[str, Any]] = []
    for term in sorted(terms):
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
    rows.sort(key=lambda item: (-float(item["llr"]), -float(item["relative_ratio"]), str(item["term"])))
    return {"keyness_table": rows}


def execute_topic_modeling(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    corpus = _scoped_corpus_from_inputs(context, inputs)
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    analysis_params = _analysis_params(
        context,
        {
            "topic_model_k": config.get("topic_model_k"),
            "feature_term_count": config.get("feature_term_count"),
        },
    )
    payload = _feature_term_payload(
        context,
        corpus,
        {"feature_term_count": analysis_params.get("feature_term_count")},
    )
    topic_term_rows, document_topic_rows, topic_summary_rows = analysis_ops.topic_model_tables(
        corpus,
        payload["tfidf_bundle"],
        analysis_params,
        top_terms_per_topic=int(config.get("top_terms_per_topic", 5) or 5),
    )
    return {
        "topic_term_table": topic_term_rows,
        "document_topic_table": document_topic_rows,
        "topic_summary_table": topic_summary_rows,
    }


def execute_cluster_evaluation(context: Any, _node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    cluster_rows = inputs.get("document_cluster_table_in") or []
    if not isinstance(cluster_rows, list):
        cluster_rows = [cluster_rows] if isinstance(cluster_rows, dict) else []
    return {"cluster_evaluation_table": analysis_ops.cluster_evaluation_rows(cluster_rows)}


def execute_join_results(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    analysis_ops = _analysis_ops()
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    left_rows = _table_rows_from_inputs_or_results(context, inputs, "left_table_in", str(config.get("left_artifact") or ""))
    right_rows = _table_rows_from_inputs_or_results(context, inputs, "right_table_in", str(config.get("right_artifact") or ""))
    joined_rows = analysis_ops.join_table_rows(
        left_rows,
        right_rows,
        _join_keys(config),
        join_type=str(config.get("join_type") or "inner"),
    )
    return {"joined_table": joined_rows}


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
    "select_dictionary_tables": execute_select_dictionary_tables,
    "overlay_dictionary_rules": execute_overlay_dictionary_rules,
    "filter_by_metadata": execute_filter_by_metadata,
    "deduplicate_documents": execute_deduplicate_documents,
    "sample_corpus": execute_sample_corpus,
    "split_corpus": execute_split_corpus,
    "bucket_by_time": execute_bucket_by_time,
    "conditional_router": execute_conditional_router,
    "result_gate": execute_result_gate,
    "manual_review_gate": execute_manual_review_gate,
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
    "group_compare": execute_group_compare,
    "keyness_analysis": execute_keyness_analysis,
    "topic_modeling": execute_topic_modeling,
    "cluster_evaluation": execute_cluster_evaluation,
    "join_results": execute_join_results,
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
