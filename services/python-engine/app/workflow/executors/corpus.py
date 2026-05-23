from __future__ import annotations

from .support import *  # noqa: F401,F403

def execute_corpus_input(context: Any, node: dict[str, Any], _inputs: dict[str, Any]) -> dict[str, Any]:
    runtime_support = _runtime_support()
    scope = runtime_support.normalize_run_scope(node.get("config") if isinstance(node.get("config"), dict) else {})
    _report_node_progress(context, node, 0.25, f"语料输入：读取 {len(context.full_corpus)} 篇文档")
    scoped = [item for item in context.full_corpus if runtime_support.document_matches_scope(item, scope)]
    context.shared["run_scope"] = scope
    context.shared["run_scope_summary"] = runtime_support.describe_run_scope(scope, len(context.full_corpus), len(scoped))
    context.shared["scoped_corpus"] = scoped
    _report_node_progress(context, node, 0.92, f"语料输入：命中 {len(scoped)} 篇文档")
    return {"corpus": scoped}


def execute_filter_corpus(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    runtime_support = _runtime_support()
    scope = runtime_support.normalize_run_scope(node.get("config") if isinstance(node.get("config"), dict) else {})
    corpus = _scoped_corpus_from_inputs(context, inputs)
    _report_node_progress(context, node, 0.25, f"筛选语料：读取 {len(corpus)} 篇文档")
    scoped = [item for item in corpus if runtime_support.document_matches_scope(item, scope)]
    context.shared["run_scope"] = scope
    context.shared["run_scope_summary"] = runtime_support.describe_run_scope(scope, len(context.full_corpus), len(scoped))
    context.shared["scoped_corpus"] = scoped
    _report_node_progress(context, node, 0.92, f"筛选语料：命中 {len(scoped)} 篇文档")
    return {"corpus": scoped}


def execute_dictionary_input(context: Any, node: dict[str, Any], _inputs: dict[str, Any]) -> dict[str, Any]:
    _report_node_progress(context, node, 0.35, "词表输入：读取项目词表")
    dictionary_set = deepcopy(context.manifest["dictionary_set"])
    active_dictionary_set = _set_active_dictionary_set(context, dictionary_set)
    entry_count = sum(
        len(sheet.get("entries") or [])
        for sheet in (active_dictionary_set.get("sheets") or {}).values()
        if isinstance(sheet, dict)
    )
    _report_node_progress(context, node, 0.92, f"词表输入：启用 {entry_count} 条词表规则")
    return {"dictionary_set": active_dictionary_set}


def execute_merge_corpora(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpora = inputs.get("corpus_in") or []
    if isinstance(corpora, dict):
        corpora = [corpora]
    merged: list[dict[str, Any]] = []
    seen_doc_ids: set[str] = set()
    strategy = str((node.get("config") or {}).get("strategy") or "append")
    list_corpora = [corpus for corpus in corpora if isinstance(corpus, list)]
    total_corpora = len(list_corpora)
    for corpus_index, corpus in enumerate(list_corpora, start=1):
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
        _report_node_progress(
            context,
            node,
            0.2 + 0.7 * corpus_index / max(total_corpora, 1),
            f"合并语料：完成 {corpus_index}/{total_corpora} 路输入",
        )
    context.shared["scoped_corpus"] = merged
    _report_node_progress(context, node, 0.92, f"合并语料：输出 {len(merged)} 篇文档")
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
    _report_node_progress(context, node, 0.25, f"选择词表分表：读取 {len(selected_tokens)} 个选择条件")
    if not selected_tokens:
        active_dictionary_set = _set_active_dictionary_set(context, dictionary_set)
        _report_node_progress(context, node, 0.92, "选择词表分表：沿用全部词表")
        return {"dictionary_set": active_dictionary_set}
    collections = dictionary_set.get("collections") if isinstance(dictionary_set.get("collections"), dict) else {}
    collection_items = list(collections.items())
    for index, (kind, collection) in enumerate(collection_items, start=1):
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
        _report_node_progress(
            context,
            node,
            0.25 + 0.55 * index / max(len(collection_items), 1),
            f"选择词表分表：处理 {index}/{len(collection_items)} 类词表",
        )
    active_dictionary_set = _set_active_dictionary_set(context, _rebuild_dictionary_sheets(dictionary_set))
    active_table_count = sum(
        len(collection.get("tables") or [])
        for collection in (active_dictionary_set.get("collections") or {}).values()
        if isinstance(collection, dict)
    )
    _report_node_progress(context, node, 0.92, f"选择词表分表：启用 {active_table_count} 张表")
    return {"dictionary_set": active_dictionary_set}


def execute_overlay_dictionary_rules(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    dictionary_set = deepcopy(_active_dictionary_set(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    rows = _overlay_rows(config)
    _report_node_progress(context, node, 0.25, f"叠加临时词表规则：读取 {len(rows)} 条规则")
    if not rows:
        active_dictionary_set = _set_active_dictionary_set(context, dictionary_set)
        _report_node_progress(context, node, 0.92, "叠加临时词表规则：无临时规则")
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
        if index == len(rows) or index % 250 == 0:
            _report_node_progress(
                context,
                node,
                0.25 + 0.5 * index / max(len(rows), 1),
                f"叠加临时词表规则：整理 {index}/{len(rows)} 条规则",
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
    _report_node_progress(context, node, 0.92, f"叠加临时词表规则：写入 {sum(len(entries) for entries in grouped_rows.values())} 条临时规则")
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
    _report_node_progress(context, node, 0.2, f"条件分流：读取 {len(corpus) or len(table_rows)} 条记录")

    matched_corpus = [item for item in corpus if _record_matches_control_condition(item, config)] if corpus else []
    if corpus:
        _report_node_progress(context, node, 0.55, f"条件分流：命中 {len(matched_corpus)} 篇文档")
    unmatched_corpus = [item for item in corpus if not _record_matches_control_condition(item, config)] if corpus else []
    matched_table = [item for item in table_rows if _record_matches_control_condition(item, config)] if table_rows else []
    if table_rows:
        _report_node_progress(context, node, 0.55, f"条件分流：命中 {len(matched_table)} 行表记录")
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
    _report_node_progress(context, node, 0.92, f"条件分流：输出命中 {matched_count} / 未命中 {unmatched_count}")
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
    _report_node_progress(context, node, 0.25, f"结果闸门：读取 {len(metric_rows)} 条指标")
    metric_row = _select_metric_row(metric_rows, config)
    observed_value = _metric_observed_value(metric_row, config)
    threshold = config.get("threshold")
    passed = _compare_control_value(observed_value, str(config.get("operator") or "gte"), [threshold])
    _report_node_progress(context, node, 0.72, f"结果闸门：判定 {'通过' if passed else '阻断'}")
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
    _report_node_progress(context, node, 0.25, f"人工审核闸门：读取 {len(payload_rows)} 条待审记录")
    manifest = getattr(context, "manifest", {})
    task = _find_review_task(manifest, review_id) if isinstance(manifest, dict) and review_id else None
    current_status = str(task.get("status") or "missing").strip().lower() if isinstance(task, dict) else "missing"
    approved = current_status == required_status or (task is None and on_missing == "pass")
    waiting = not approved
    _report_node_progress(context, node, 0.72, f"人工审核闸门：状态 {current_status}")
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
    _report_node_progress(context, node, 0.2, f"元数据过滤：读取 {len(corpus)} 篇文档")
    if not conditions:
        context.shared["scoped_corpus"] = corpus
        _report_node_progress(context, node, 0.92, "元数据过滤：未配置条件，沿用全部文档")
        return {"filtered_corpus": corpus}
    filtered: list[dict[str, Any]] = []
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        if all(_document_matches_condition(item, condition) for condition in conditions):
            filtered.append(item)
        _report_corpus_progress(context, node, index, total, "元数据过滤")
    context.shared["scoped_corpus"] = filtered
    _report_node_progress(context, node, 0.92, f"元数据过滤：命中 {len(filtered)} 篇文档")
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
    _report_node_progress(context, node, 0.2, f"去重文档：读取 {len(corpus)} 篇文档")
    if not keys:
        context.shared["scoped_corpus"] = corpus
        _report_node_progress(context, node, 0.92, "去重文档：未配置键，沿用全部文档")
        return {"deduped_corpus": corpus}
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        signature = _dedupe_signature(item, keys)
        if signature in seen:
            _report_corpus_progress(context, node, index, total, "去重文档")
            continue
        seen.add(signature)
        deduped.append(item)
        _report_corpus_progress(context, node, index, total, "去重文档")
    context.shared["scoped_corpus"] = deduped
    _report_node_progress(context, node, 0.92, f"去重文档：保留 {len(deduped)} / {len(corpus)} 篇")
    return {"deduped_corpus": deduped}


def execute_sample_corpus(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    _report_node_progress(context, node, 0.2, f"抽样语料：读取 {len(corpus)} 篇文档")
    if not corpus:
        _report_node_progress(context, node, 0.92, "抽样语料：无文档可抽样")
        return {"sampled_corpus": []}
    seed = int(config.get("seed", 42) or 42)
    sample_ratio = config.get("sample_ratio")
    sample_size = config.get("sample_size")
    if sample_ratio not in (None, ""):
        requested = max(0, min(len(corpus), round(len(corpus) * float(sample_ratio))))
    else:
        requested = max(0, min(len(corpus), int(sample_size or len(corpus))))
    _report_node_progress(context, node, 0.55, f"抽样语料：目标 {requested} 篇")
    if requested >= len(corpus):
        sampled = corpus
    else:
        rng = random.Random(seed)
        sampled = [corpus[index] for index in sorted(rng.sample(range(len(corpus)), requested))]
    context.shared["scoped_corpus"] = sampled
    _report_node_progress(context, node, 0.92, f"抽样语料：输出 {len(sampled)} 篇")
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
    _report_node_progress(context, node, 0.2, f"划分语料：读取 {len(corpus)} 篇文档")
    if not corpus or not splits:
        _report_node_progress(context, node, 0.92, "划分语料：无可用划分")
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
        _report_node_progress(
            context,
            node,
            0.25 + 0.62 * (index + 1) / max(len(splits), 1),
            f"划分语料：完成 {index + 1}/{len(splits)} 个集合",
        )
    assignments.sort(key=lambda item: str(item.get("doc_id") or ""))
    _report_node_progress(context, node, 0.92, f"划分语料：生成 {len(assignments)} 条分配")
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
    _report_node_progress(context, node, 0.2, f"时间分桶：读取 {len(corpus)} 篇文档")
    assignments: list[dict[str, Any]] = []
    total = len(corpus)
    for index, item in enumerate(corpus, start=1):
        value = _document_field_value(item, field)
        try:
            year = int(value)
        except (TypeError, ValueError):
            _report_corpus_progress(context, node, index, total, "时间分桶")
            continue
        assignments.append(
            {
                "doc_id": item.get("doc_id"),
                "title": item.get("title"),
                "year": year,
                "time_bucket": _bucket_label(year, granularity),
            }
        )
        _report_corpus_progress(context, node, index, total, "时间分桶")
    _report_node_progress(context, node, 0.92, f"时间分桶：生成 {len(assignments)} 条分桶")
    return {"time_bucket_table": assignments}


