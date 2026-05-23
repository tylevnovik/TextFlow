from __future__ import annotations

from .corpus import _active_dictionary_set, _record_field_value
from .support import *  # noqa: F401,F403

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


def execute_normalize_metadata(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
    corpus = _clone_corpus_rows(_scoped_corpus_from_inputs(context, inputs))
    config = node.get("config") if isinstance(node.get("config"), dict) else {}

    def _parse_aliases(text: str) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for line in str(text or "").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t") if "\t" in line else line.split("|")
            if len(parts) >= 2:
                aliases[parts[0].strip()] = parts[1].strip()
        return aliases

    institution_aliases = _parse_aliases(config.get("institution_aliases_text"))
    country_aliases = _parse_aliases(config.get("country_aliases_text"))
    category_aliases = _parse_aliases(config.get("category_aliases_text"))

    country_map: dict[str, str] = {
        **country_aliases,
        "CN": "China",
        "中国": "China",
        "China": "China",
        "US": "United States",
        "USA": "United States",
        "United States": "United States",
        "美国": "United States",
    }

    split_delimiters = str(config.get("split_delimiters") or ";；|")
    keep_first = bool(config.get("keep_first_institution", True))
    year_source = str(config.get("year_source_field") or "year").strip() or "year"

    audit_rows: list[dict[str, Any]] = []
    total = len(corpus)

    for index, item in enumerate(corpus, start=1):
        doc_id = str(item.get("doc_id") or item.get("id") or "")
        changed = False

        # institution normalization
        institution = str(item.get("institution") or "").strip()
        if institution:
            for delim in split_delimiters:
                institution = institution.replace(delim, ";")
            parts = [p.strip() for p in institution.split(";") if p.strip()]
            if keep_first and parts:
                parts = parts[:1]
            normalized_parts = [institution_aliases.get(p, p) for p in parts]
            new_institution = "; ".join(normalized_parts)
            if new_institution != item.get("institution"):
                item["institution"] = new_institution
                if keep_first:
                    item.setdefault("extra_metadata", {})["institution_values"] = parts
                audit_rows.append({"doc_id": doc_id, "field": "institution", "old": institution, "new": new_institution})
                changed = True

        # country normalization
        country = str(item.get("country_or_region") or "").strip()
        if country:
            new_country = country_map.get(country, country)
            if new_country != country:
                item["country_or_region"] = new_country
                audit_rows.append({"doc_id": doc_id, "field": "country_or_region", "old": country, "new": new_country})
                changed = True

        # year normalization
        year_value = item.get(year_source)
        if year_value is not None:
            from ...ingestion import parse_optional_year
            parsed_year = parse_optional_year(year_value)
            if parsed_year is not None and parsed_year != item.get("year"):
                old_year = item.get("year")
                item["year"] = parsed_year
                audit_rows.append({"doc_id": doc_id, "field": "year", "old": old_year, "new": parsed_year})
                changed = True

        # category normalization
        category = str(item.get("category_or_tag") or "").strip()
        if category:
            new_category = category_aliases.get(category, category)
            if new_category != category:
                item["category_or_tag"] = new_category
                audit_rows.append({"doc_id": doc_id, "field": "category_or_tag", "old": category, "new": new_category})
                changed = True

        if changed:
            item.setdefault("extra_metadata", {})["metadata_normalization_audit"] = True

        _report_corpus_progress(context, node, index, total, "元数据标准化")

    context.shared["scoped_corpus"] = corpus
    return {"normalized_corpus": corpus, "metadata_audit_table": audit_rows}


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
    _report_node_progress(context, node, 0.25, f"过滤词项：读取 {len(corpus)} 篇文档")
    text_ops.filter_token_lists(corpus, params, context.manifest["dictionary_set"])
    _report_node_progress(context, node, 0.92, f"过滤词项：完成 {len(corpus)} 篇文档")
    context.shared["filtered_corpus"] = corpus
    return {"filtered_token_corpus": corpus}


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
            return deepcopy(value)
        shared_value = _shared_get(context, result_key)
        if _is_table_rows(shared_value):
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


def execute_focus_terms(context: Any, node: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
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


