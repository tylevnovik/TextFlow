from __future__ import annotations

import re
from typing import Any

from ._common import bool_param, enum_param, filtering_passthrough_compiler, number_param, port, runtime, string_param, field, graph, slot, ui
from ._support import (
    _clone_corpus_rows,
    _is_table_rows,
    _record_field_value,
    _report_corpus_progress,
    _report_node_progress,
    _scoped_corpus_from_inputs,
    _shared_get,
    _table_rows_from_inputs_or_results,
)


def node_definition(runtime_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "focus_terms",
        "title": "聚焦词项",
        "category": "process",
        "description": "用特征词或关键词结果收窄下游分析词项，降低共现网络和图计算规模。",
        "inputs": [
            port("token_corpus_in", "FilteredTokenCorpus", "分析词项"),
            port("term_table_in", "AnyTable", "候选词表"),
        ],
        "outputs": [
            port("focused_token_corpus", "FilteredTokenCorpus", "聚焦后词项"),
            port("focus_term_summary", "AnyTable", "聚焦摘要", result_bundle_key="focus_term_summary", include_in_html_audit=True),
        ],
        "params": [
            enum_param("term_source", "词项来源", "auto", [
                ("auto", "自动识别"),
                ("feature_terms", "特征词表"),
                ("keywords", "关键词表"),
            ]),
            string_param("term_field", "词项字段", "auto"),
            number_param("max_terms", "最大词项数", 80),
            bool_param("selected_only", "仅保留已选特征词", True),
            bool_param("project_keywords_only", "仅项目级关键词", True),
            enum_param("on_empty", "无候选词时", "pass_through", [
                ("pass_through", "沿用上游"),
                ("empty", "输出空词项"),
            ]),
        ],
        "runtime": runtime(
            "filtering",
            "workflow.focus_terms",
            cacheable=True,
            previewable=True,
        ),
        "graph": graph((360, 280), (4080, 1640), toolbox_order=250),
        "ui": ui(
            [
                field("select", "term_source", "词项来源"),
                field("text", "term_field", "词项字段"),
                field("number", "max_terms", "最大词项数", step=1),
                field("switch", "selected_only", "仅保留已选特征词"),
                field("switch", "project_keywords_only", "仅项目级关键词"),
                field("select", "on_empty", "无候选词时"),
            ],
        ),
    }


def compile_node(context: Any, node: dict[str, Any]) -> None:
    filtering_passthrough_compiler(context, node)


def _focus_term_variants(value: Any) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return set()
    collapsed = re.sub(r"\s+", " ", raw)
    underscore = collapsed.replace(" ", "_")
    spaced = collapsed.replace("_", " ")
    compact = re.sub(r"[\s_]+", "", collapsed)
    variants = {
        variant.casefold()
        for variant in [raw, collapsed, underscore, spaced, compact]
        if variant
    }
    parts = [
        part.strip()
        for part in re.split(r"[\s_;/,，、-]+", collapsed)
        if len(part.strip()) > 1
    ]
    variants.update(part.casefold() for part in parts)
    return variants


def _focus_term_signature(value: Any) -> str:
    return re.sub(r"[\s_]+", "", str(value or "").strip()).casefold()


def _focus_candidate_rows(context: Any, inputs: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _table_rows_from_inputs_or_results(context, inputs, "term_table_in")
    if rows:
        return rows
    for result_key in ["selected_feature_terms", "keyword_result"]:
        value = getattr(context, "result_bundle", {}).get(result_key) if isinstance(getattr(context, "result_bundle", {}), dict) else None
        if _is_table_rows(value):
            from copy import deepcopy
            return deepcopy(value)
        shared_value = _shared_get(context, result_key)
        if _is_table_rows(shared_value):
            from copy import deepcopy
            return deepcopy(shared_value)
    return []


def _focus_term_from_row(row: dict[str, Any], config: dict[str, Any]) -> str:
    requested_field = str(config.get("term_field") or "auto").strip()
    if requested_field and requested_field != "auto":
        return str(_record_field_value(row, requested_field) or "").strip()
    term_source = str(config.get("term_source") or "auto")
    candidate_fields = ["term", "keyword"] if term_source != "keywords" else ["keyword", "term"]
    for field in candidate_fields:
        value = _record_field_value(row, field)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _selected_focus_terms(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[str]:
    selected_only = bool(config.get("selected_only", True))
    project_keywords_only = bool(config.get("project_keywords_only", True))
    max_terms_value = config.get("max_terms", 80)
    max_terms = int(max_terms_value or 0)
    terms: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if selected_only and "selected" in row and not bool(row.get("selected")):
            continue
        if project_keywords_only and "scope" in row and str(row.get("scope") or "") != "project":
            continue
        term = _focus_term_from_row(row, config)
        if not term:
            continue
        signature = _focus_term_signature(term)
        if signature in seen:
            continue
        seen.add(signature)
        terms.append(term)
        if max_terms > 0 and len(terms) >= max_terms:
            break
    return terms


def execute_node(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}
    candidate_rows = _focus_candidate_rows(context, inputs)
    selected_terms = _selected_focus_terms(candidate_rows, config)
    tokens_before = sum(len(item.get("filtered_tokens") or []) for item in corpus)
    _report_node_progress(
        context,
        node,
        0.25,
        f"聚焦词项：读取 {len(candidate_rows)} 条候选词 / {tokens_before} 个词项",
    )

    allowed_variants: set[str] = set()
    for term in selected_terms:
        allowed_variants.update(_focus_term_variants(term))

    on_empty = str(config.get("on_empty") or "pass_through")
    if not allowed_variants and on_empty == "pass_through":
        focused = corpus
    else:
        focused = []
        total = len(corpus)
        for index, item in enumerate(corpus, start=1):
            next_item = dict(item)
            next_item["filtered_tokens"] = [
                token
                for token in item.get("filtered_tokens") or []
                if _focus_term_variants(token) & allowed_variants
            ]
            focused.append(next_item)
            _report_corpus_progress(context, node, index, total, "聚焦词项")

    tokens_after = sum(len(item.get("filtered_tokens") or []) for item in focused)
    summary = [
        {
            "candidate_row_count": len(candidate_rows),
            "selected_term_count": len(selected_terms),
            "document_count": len(focused),
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "token_retention_ratio": round(tokens_after / max(tokens_before, 1), 6),
            "max_terms": config.get("max_terms", 80),
            "term_source": str(config.get("term_source") or "auto"),
            "term_field": str(config.get("term_field") or "auto"),
            "on_empty": on_empty,
            "selected_terms_preview": " / ".join(selected_terms[:8]),
        }
    ]
    _report_node_progress(
        context,
        node,
        0.92,
        f"聚焦词项：保留 {len(selected_terms)} 个候选词，词项 {tokens_before} -> {tokens_after}",
    )
    context.shared["focused_token_corpus"] = focused
    context.shared["filtered_corpus"] = focused
    context.result_bundle["focus_term_summary"] = summary
    return {"focused_token_corpus": focused, "focus_term_summary": summary}


def register_nodes(builder: Any, runtime_profile: dict[str, Any] | None = None) -> None:
    builder.register_node(
        node_definition(runtime_profile),
        compiler=compile_node,
        executor=execute_node,
    )
