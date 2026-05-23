from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..builtin_dictionary_data import builtin_dictionary_table_specs

DICTIONARY_KIND_ORDER = [
    "stopwords",
    "custom_lexicon",
    "phrase_lexicon",
    "synonym_map",
    "near_synonym_map",
    "standard_terms",
    "exclusion_terms",
    "regex_rules",
]

DICTIONARY_COLLECTION_META: dict[str, dict[str, str]] = {
    "stopwords": {
        "name": "停用词",
        "description": "过滤无分析意义的虚词、常用词和套话。",
    },
    "custom_lexicon": {
        "name": "自定义词典",
        "description": "告诉切词器哪些术语和专名应该整体保留。",
    },
    "phrase_lexicon": {
        "name": "短语词典",
        "description": "把多词短语或固定表达当成一个整体处理。",
    },
    "synonym_map": {
        "name": "同义词表",
        "description": "把别名、区域说法和常见替代表达归并成统一写法。",
    },
    "near_synonym_map": {
        "name": "近义词表",
        "description": "保留可选的扩展归并资源，适合更强的术语合并。",
    },
    "standard_terms": {
        "name": "标准词库",
        "description": "用确定的一对一规则做词形和标准写法归一。",
    },
    "exclusion_terms": {
        "name": "排除词表",
        "description": "在当前课题无关时可整批排除的人名、地名或噪声词。",
    },
    "regex_rules": {
        "name": "Regex 规则",
        "description": "用于清洗和标准化的正则表达式规则。",
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_ready(item) for item in value]
    if hasattr(value, "item"):
        try:
            item = value.item()
        except Exception:
            item = value
        if item is not value:
            return json_ready(item)
    if hasattr(value, "tolist"):
        try:
            listed = value.tolist()
        except Exception:
            listed = value
        if listed is not value:
            return json_ready(listed)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def unpack_dictionary_row(row: tuple[Any, ...]) -> tuple[str, str | None, int, str | None]:
    source = str(row[0])
    target = row[1] if len(row) > 1 else None
    hits = int(row[2]) if len(row) > 2 else 0
    entry_id = str(row[3]) if len(row) > 3 and row[3] else None
    return source, target, hits, entry_id


def make_dictionary_entry(
    source: str,
    target: str | None = None,
    hits: int = 0,
    entry_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": entry_id or str(uuid4()),
        "source": source,
        "target": target,
        "tags": [],
        "enabled": True,
        "hits": hits,
        "notes": "",
    }


def make_sheet(kind: str, name: str, rows: list[tuple[Any, ...]]) -> dict[str, Any]:
    return {
        "kind": kind,
        "name": name,
        "version": "1.0.0",
        "entries": [make_dictionary_entry(*unpack_dictionary_row(row)) for row in rows],
    }


def make_dictionary_table_resource(
    kind: str,
    table_id: str,
    name: str,
    rows: list[tuple[Any, ...]],
    *,
    description: str = "",
    source_url: str | None = None,
    built_in: bool = False,
    editable: bool = True,
    enabled: bool = True,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": table_id,
        "kind": kind,
        "name": name,
        "version": "2.0.0",
        "description": description,
        "source_url": source_url,
        "built_in": built_in,
        "editable": editable,
        "enabled": enabled,
        "tags": list(tags or []),
        "entries": [make_dictionary_entry(*unpack_dictionary_row(row)) for row in rows],
    }


def make_dictionary_collection(kind: str, tables: list[dict[str, Any]]) -> dict[str, Any]:
    meta = DICTIONARY_COLLECTION_META[kind]
    return {
        "kind": kind,
        "name": meta["name"],
        "description": meta["description"],
        "tables": tables,
    }


def dictionary_entry_signature(entry: dict[str, Any], fallback_key: str) -> str:
    source = str(entry.get("source") or "").strip()
    target = str(entry.get("target") or "").strip()
    if not source:
        return fallback_key
    return f"{source.casefold()}::{target.casefold()}"


def build_dictionary_sheets_from_collections(collections: dict[str, Any]) -> dict[str, Any]:
    sheets: dict[str, Any] = {}
    for kind in DICTIONARY_KIND_ORDER:
        collection = collections.get(kind) if isinstance(collections, dict) else None
        collection_meta = DICTIONARY_COLLECTION_META[kind]
        entries: list[dict[str, Any]] = []
        seen: set[str] = set()
        if isinstance(collection, dict):
            for table in collection.get("tables", []):
                if not isinstance(table, dict) or not table.get("enabled", True):
                    continue
                for index, entry in enumerate(table.get("entries", [])):
                    if not isinstance(entry, dict) or not entry.get("enabled", True):
                        continue
                    signature = dictionary_entry_signature(entry, f"{kind}:{table.get('id') or 'table'}:{index}")
                    if signature in seen:
                        continue
                    seen.add(signature)
                    entries.append(entry)
        sheets[kind] = {
            "kind": kind,
            "name": str((collection or {}).get("name") or collection_meta["name"]),
            "version": "2.0.0",
            "entries": entries,
        }
    return sheets


def profile_import_template(source_profile: str) -> dict[str, Any]:
    templates: dict[str, dict[str, Any]] = {
        "generic": {
            "name": "通用导入模板",
            "description": "适合 txt/csv/xlsx/json 的通用结构化文本导入。",
            "field_mappings": [
                {"source_field": "doc_id", "target_field": "doc_id", "required": False, "aliases": ["id", "document_id"]},
                {"source_field": "title", "target_field": "title", "required": False, "aliases": ["name", "subject"]},
                {"source_field": "abstract", "target_field": "raw_text", "required": False, "aliases": ["raw_text", "content", "text", "summary"]},
                {"source_field": "year", "target_field": "year", "required": False, "aliases": ["published", "publication_year"]},
                {"source_field": "source", "target_field": "source", "required": False, "aliases": ["journal", "origin"]},
                {"source_field": "author", "target_field": "author", "required": False, "aliases": ["authors", "creator"]},
                {"source_field": "institution", "target_field": "institution", "required": False, "aliases": ["org", "organization", "affiliation"]},
                {"source_field": "country_or_region", "target_field": "country_or_region", "required": False, "aliases": ["country", "region"]},
                {"source_field": "category_or_tag", "target_field": "category_or_tag", "required": False, "aliases": ["category", "tag"]},
                {"source_field": "keyword_field", "target_field": "keyword_field", "required": False, "aliases": ["keywords", "keyword"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["title", "abstract"], "delimiter": "\n\n", "skip_empty": True},
        },
        "literature": {
            "name": "文献导入模板",
            "description": "面向论文、报告和综述等文献数据。",
            "field_mappings": [
                {"source_field": "title", "target_field": "title", "required": True, "aliases": ["Title", "article_title"]},
                {"source_field": "abstract", "target_field": "raw_text", "required": True, "aliases": ["Abstract", "summary"]},
                {"source_field": "year", "target_field": "year", "required": False, "aliases": ["PY", "published", "publication_year"]},
                {"source_field": "source", "target_field": "source", "required": False, "aliases": ["journal", "SO"]},
                {"source_field": "author", "target_field": "author", "required": False, "aliases": ["authors", "AU"]},
                {"source_field": "institution", "target_field": "institution", "required": False, "aliases": ["org", "affiliation", "C1"]},
                {"source_field": "keyword_field", "target_field": "keyword_field", "required": False, "aliases": ["keywords", "DE"]},
                {"source_field": "category_or_tag", "target_field": "category_or_tag", "required": False, "aliases": ["category", "WC"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["title", "abstract"], "delimiter": "\n\n", "skip_empty": True},
        },
        "wos": {
            "name": "Web of Science 模板",
            "description": "预置 WoS 常见字段别名和主文本拼接策略。",
            "field_mappings": [
                {"source_field": "UT", "target_field": "doc_id", "required": True, "aliases": ["Accession Number", "UT (Unique WOS ID)"]},
                {"source_field": "TI", "target_field": "title", "required": True, "aliases": ["Article Title"]},
                {"source_field": "AB", "target_field": "raw_text", "required": True, "aliases": ["Abstract"]},
                {"source_field": "PY", "target_field": "year", "required": False, "aliases": ["Published Year", "Publication Year"]},
                {"source_field": "SO", "target_field": "source", "required": False, "aliases": ["Publication Name", "Source Title"]},
                {"source_field": "AU", "target_field": "author", "required": False, "aliases": ["Authors"]},
                {"source_field": "C1", "target_field": "institution", "required": False, "aliases": ["Addresses", "Affiliations"]},
                {"source_field": "DE", "target_field": "keyword_field", "required": False, "aliases": ["Author Keywords"]},
                {"source_field": "ID", "target_field": "keyword_field", "required": False, "aliases": ["Keywords Plus"]},
                {"source_field": "WC", "target_field": "category_or_tag", "required": False, "aliases": ["Web of Science Categories", "WoS Categories"]},
                {"source_field": "DOI", "target_field": "extra_metadata", "required": False, "aliases": []},
                {"source_field": "DT", "target_field": "extra_metadata", "required": False, "aliases": ["Document Type"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["TI", "AB", "DE", "ID"], "delimiter": "\n\n", "skip_empty": True},
        },
        "scopus": {
            "name": "Scopus 模板",
            "description": "预置 Scopus 常见字段别名和主文本拼接策略。",
            "field_mappings": [
                {"source_field": "EID", "target_field": "doc_id", "required": True, "aliases": ["EID"]},
                {"source_field": "Title", "target_field": "title", "required": True, "aliases": ["Article Title"]},
                {"source_field": "Abstract", "target_field": "raw_text", "required": True, "aliases": ["abstract"]},
                {"source_field": "Year", "target_field": "year", "required": False, "aliases": ["Publication Year"]},
                {"source_field": "Source title", "target_field": "source", "required": False, "aliases": ["Journal"]},
                {"source_field": "Authors", "target_field": "author", "required": False, "aliases": ["Author full names"]},
                {"source_field": "Affiliations", "target_field": "institution", "required": False, "aliases": ["Author affiliations"]},
                {"source_field": "Author Keywords", "target_field": "keyword_field", "required": False, "aliases": ["Index Keywords"]},
                {"source_field": "Index Keywords", "target_field": "keyword_field", "required": False, "aliases": ["Author Keywords"]},
                {"source_field": "Subject area", "target_field": "category_or_tag", "required": False, "aliases": ["Subject areas"]},
                {"source_field": "DOI", "target_field": "extra_metadata", "required": False, "aliases": []},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["Title", "Abstract", "Author Keywords", "Index Keywords"], "delimiter": "\n\n", "skip_empty": True},
        },
        "patent": {
            "name": "专利导入模板",
            "description": "适合公开文本、摘要、申请人和 IPC/主题字段。",
            "field_mappings": [
                {"source_field": "publication_number", "target_field": "doc_id", "required": True, "aliases": ["pn", "patent_no", "公开（公告）号"]},
                {"source_field": "title", "target_field": "title", "required": True, "aliases": ["invention_title", "标题", "专利名称"]},
                {"source_field": "abstract", "target_field": "raw_text", "required": True, "aliases": ["摘要", "abstract_text"]},
                {"source_field": "publication_year", "target_field": "year", "required": False, "aliases": ["year", "公开（公告）日"]},
                {"source_field": "applicant", "target_field": "institution", "required": False, "aliases": ["assignee", "申请人"]},
                {"source_field": "inventor", "target_field": "author", "required": False, "aliases": ["发明人"]},
                {"source_field": "ipc", "target_field": "category_or_tag", "required": False, "aliases": ["IPC", "IPC分类号"]},
                {"source_field": "keywords", "target_field": "keyword_field", "required": False, "aliases": ["主题词"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["title", "abstract", "keywords"], "delimiter": "\n\n", "skip_empty": True},
        },
        "incopat": {
            "name": "IncoPat 模板",
            "description": "预置 IncoPat 常见中文字段名与别名。",
            "field_mappings": [
                {"source_field": "公开（公告）号", "target_field": "doc_id", "required": True, "aliases": ["公开(公告)号", "申请号", "专利号", "公开号", "授权公告号", "首次公开号"]},
                {"source_field": "标题 (中文)", "target_field": "title", "required": True, "aliases": ["标题（中文）", "标题(中文)", "标题", "专利名称", "标题 (英文)", "标题（英文）", "标题(英文)", "标题（小语种原文）"]},
                {"source_field": "摘要 (中文)", "target_field": "raw_text", "required": True, "aliases": ["摘要（中文）", "摘要(中文)", "摘要", "摘要 (英文)", "摘要（英文）", "摘要(英文)", "摘要（小语种原文）", "首权翻译", "首项权利要求", "独立权利要求", "简介"]},
                {"source_field": "公开（公告）日", "target_field": "year", "required": False, "aliases": ["公开(公告)日", "申请日", "优先权日", "最早优先权日", "年份", "首次公开日", "授权公告日"]},
                {"source_field": "申请人", "target_field": "institution", "required": False, "aliases": ["标准化申请人", "当前权利人", "标准化当前权利人", "第一申请人", "专利权人", "申请人(翻译)", "申请人（翻译）"]},
                {"source_field": "发明人", "target_field": "author", "required": False, "aliases": ["第一发明(设计)人", "第一发明（设计）人", "发明(设计)人(其他)", "发明（设计）人（其他）", "Inventor"]},
                {"source_field": "公开国别", "target_field": "country_or_region", "required": False, "aliases": ["申请人国家/地区", "优先权国别", "同族国家/地区"]},
                {"source_field": "IPC", "target_field": "category_or_tag", "required": False, "aliases": ["IPC分类号", "IPC主分类-小组", "CPC"]},
                {"source_field": "技术功效短语", "target_field": "keyword_field", "required": False, "aliases": ["技术功效句", "用途", "关键词", "主题词"]},
                {"source_field": "引证专利", "target_field": "extra_metadata", "required": False, "aliases": []},
                {"source_field": "被引证专利", "target_field": "extra_metadata", "required": False, "aliases": []},
                {"source_field": "被引证次数", "target_field": "extra_metadata", "required": False, "aliases": []},
                {"source_field": "引证次数", "target_field": "extra_metadata", "required": False, "aliases": []},
                {"source_field": "技术功效1级", "target_field": "extra_metadata", "required": False, "aliases": ["技术功效2级", "技术功效3级"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["标题 (中文)", "标题 (英文)", "摘要 (中文)", "摘要 (英文)", "首权翻译", "首项权利要求", "独立权利要求", "技术功效句", "技术功效短语", "用途"], "delimiter": "\n\n", "skip_empty": True},
        },
        "business_reserved": {
            "name": "商业数据模板",
            "description": "预留给后续商业数据/行业报告导入。",
            "field_mappings": [
                {"source_field": "record_id", "target_field": "doc_id", "required": False, "aliases": ["id"]},
                {"source_field": "title", "target_field": "title", "required": True, "aliases": ["subject"]},
                {"source_field": "content", "target_field": "raw_text", "required": True, "aliases": ["raw_text", "text"]},
                {"source_field": "year", "target_field": "year", "required": False, "aliases": ["published_year"]},
                {"source_field": "company", "target_field": "institution", "required": False, "aliases": ["institution", "organization"]},
                {"source_field": "topic", "target_field": "category_or_tag", "required": False, "aliases": ["category"]},
                {"source_field": "keywords", "target_field": "keyword_field", "required": False, "aliases": ["tags"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["title", "content"], "delimiter": "\n\n", "skip_empty": True},
        },
    }
    return deepcopy(templates.get(source_profile, templates["generic"]))


@lru_cache(maxsize=1)
def default_dictionary_set_seed() -> dict[str, Any]:
    builtin_specs = builtin_dictionary_table_specs()
    collections: dict[str, Any] = {}
    for kind in DICTIONARY_KIND_ORDER:
        project_custom = make_dictionary_table_resource(
            kind,
            f"{kind}-project-custom",
            "项目自定义",
            [],
            description="项目内可直接编辑、删除、导入和新增的自定义词表资源。",
            built_in=False,
            editable=True,
            enabled=True,
        )
        builtin_tables = [
            make_dictionary_table_resource(
                kind,
                spec["id"],
                spec["name"],
                list(spec.get("rows") or []),
                description=str(spec.get("description") or ""),
                source_url=str(spec.get("source_url") or "") or None,
                built_in=bool(spec.get("built_in", True)),
                editable=bool(spec.get("editable", False)),
                enabled=bool(spec.get("enabled", True)),
                tags=list(spec.get("tags") or []),
            )
            for spec in builtin_specs.get(kind, [])
            if isinstance(spec, dict)
        ]
        collections[kind] = make_dictionary_collection(kind, [project_custom, *builtin_tables])

    dictionary_set = {
        "id": "dict-default",
        "name": "默认词表集",
        "version": "2.0.0",
        "bound_to_project": True,
        "collections": collections,
    }
    dictionary_set["sheets"] = build_dictionary_sheets_from_collections(collections)
    return dictionary_set


def default_dictionary_set() -> dict[str, Any]:
    return deepcopy(default_dictionary_set_seed())


def default_import_template(source_profile: str = "generic") -> dict[str, Any]:
    template = profile_import_template(source_profile)
    return {"id": f"template-{source_profile}", "source_profile": source_profile, **template}


def default_runtime_profile() -> dict[str, Any]:
    return {
        "id": "runtime-profile-default",
        "name": "默认 V1 流程",
        "enabled_steps": [
            "ingestion",
            "cleaning",
            "normalization",
            "tokenization",
            "dictionary_application",
            "filtering",
            "analysis",
            "export",
        ],
        "cleaning": {
            "strip_html": True,
            "strip_urls": True,
            "strip_email": False,
            "strip_phone": False,
            "normalize_whitespace": True,
            "normalize_punctuation": True,
            "full_half_width_normalize": True,
            "lowercase_english": True,
            "remove_emoji": False,
            "remove_special_chars": False,
        },
        "normalization": {
            "convert_traditional_to_simplified": False,
            "normalize_numbers": False,
            "normalize_time_expr": False,
            "apply_regex_rules": True,
            "regex_rule_priority": "rule_order",
        },
        "tokenization": {
            "language_mode": "mixed",
            "tokenizer_backend": "default",
            "use_custom_lexicon": True,
            "use_phrase_lexicon": True,
            "preserve_domain_phrases": True,
            "split_hyphenated_terms": True,
            "split_slash_terms": False,
            "normalize_camel_case": True,
            "keep_original_order": True,
            "min_token_length_before_filter": 1,
            "enable_ngrams": False,
            "ngram_min": 2,
            "ngram_max": 2,
        },
        "dictionary": {
            "apply_standard_terms": True,
            "apply_synonym_map": True,
            "apply_near_synonym_map": True,
            "apply_stopwords": True,
            "apply_exclusion_terms": True,
            "conflict_resolution": "priority",
        },
        "filtering": {
            "min_token_length": 2,
            "filter_numeric_tokens": False,
            "min_term_frequency": 1,
            "filter_by_pos": False,
            "keep_single_char_important_terms": True,
        },
        "analysis": {
            "top_n": 200,
            "cooccurrence_window": 5,
            "min_cooccurrence": 2,
            "feature_term_count": 1000,
            "top_k_per_doc": 10,
            "top_k_project": 100,
            "similarity_method": "cosine",
            "min_similarity": 0.2,
            "similarity_top_k": 200,
            "topic_algorithm": "nmf",
            "topic_model_k": 4,
            "keyword_cluster_k": 4,
            "document_cluster_k": 4,
            "include_frequency_statistics": True,
            "include_term_document_relations": True,
            "include_term_year_relations": True,
            "include_cooccurrence_analysis": True,
            "include_similarity_analysis": True,
            "include_feature_term_selection": True,
            "include_keyword_extraction": True,
            "include_keyword_clustering": True,
            "include_institution_keyword_analysis": True,
            "include_institution_topic_analysis": True,
            "include_document_clustering": True,
        },
        "export": {
            "export_csv": True,
            "export_xlsx": True,
            "export_png": True,
            "export_html_report": True,
            "include_audit": True,
            "chart_dpi": 320,
            "watermark_enabled": False,
            "watermark_text": "TextFlow Studio",
        },
        "nodes": [],
        "edges": [],
        "node_configs": {},
        "execution_order": [
            "ingestion",
            "cleaning",
            "normalization",
            "tokenization",
            "dictionary_application",
            "filtering",
            "analysis",
            "export",
        ],
        "run_scope": {
            "mode": "all_documents",
            "source_values": [],
            "institution_values": [],
            "category_values": [],
            "year_from": None,
            "year_to": None,
            "selected_doc_ids": [],
        },
        "recipe_id": "standard_analysis",
        "output_bundle_id": "full_report",
    }


def workflow_payload_hash(workflow_definition: dict[str, Any] | None) -> str:
    payload = workflow_execution_payload(workflow_definition)
    encoded = json.dumps(json_ready(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def workflow_execution_payload(workflow_definition: dict[str, Any] | None) -> dict[str, Any]:
    workflow = workflow_definition if isinstance(workflow_definition, dict) else {}
    return {
        "workflow_id": str(workflow.get("workflow_id") or ""),
        "version": str(workflow.get("version") or ""),
        "graph_mode": str(workflow.get("graph_mode") or ""),
        "source": str(workflow.get("source") or ""),
        "meta": deepcopy(workflow.get("meta") if isinstance(workflow.get("meta"), dict) else {}),
        "nodes": [
            workflow_node_execution_payload(node)
            for node in workflow.get("nodes", [])
            if isinstance(node, dict)
        ],
        "edges": [
            workflow_edge_execution_payload(edge)
            for edge in workflow.get("edges", [])
            if isinstance(edge, dict)
        ],
    }


def workflow_node_execution_payload(node: dict[str, Any] | None) -> dict[str, Any]:
    payload = node if isinstance(node, dict) else {}
    ui_state = payload.get("ui_state") if isinstance(payload.get("ui_state"), dict) else {}
    return {
        "node_id": str(payload.get("node_id") or ""),
        "node_type": str(payload.get("node_type") or ""),
        "config": deepcopy(payload.get("config") if isinstance(payload.get("config"), dict) else {}),
        "ui_state": {
            "bypassed": bool(ui_state.get("bypassed")),
        },
        "runtime_meta": deepcopy(payload.get("runtime_meta") if isinstance(payload.get("runtime_meta"), dict) else {}),
        "inputs": [
            workflow_port_execution_payload(port)
            for port in payload.get("inputs", [])
            if isinstance(port, dict)
        ],
        "outputs": [
            workflow_port_execution_payload(port)
            for port in payload.get("outputs", [])
            if isinstance(port, dict)
        ],
    }


def workflow_port_execution_payload(port: dict[str, Any] | None) -> dict[str, Any]:
    payload = port if isinstance(port, dict) else {}
    normalized = {
        "port_id": str(payload.get("port_id") or ""),
        "port_type": str(payload.get("port_type") or ""),
    }
    if payload.get("allow_multiple"):
        normalized["allow_multiple"] = True
    return normalized


def workflow_edge_execution_payload(edge: dict[str, Any] | None) -> dict[str, Any]:
    payload = edge if isinstance(edge, dict) else {}
    return {
        "from_node": str(payload.get("from_node") or ""),
        "from_port": str(payload.get("from_port") or ""),
        "to_node": str(payload.get("to_node") or ""),
        "to_port": str(payload.get("to_port") or ""),
    }


def default_workflow_definition(
    runtime_profile: dict[str, Any] | None = None,
    *,
    workflow_id: str = "wf-default",
    name: str = "默认工作流",
    source: str = "system_default",
) -> dict[str, Any]:
    runtime_profile_definition = deepcopy(runtime_profile if isinstance(runtime_profile, dict) else default_runtime_profile())
    enabled_steps = set(runtime_profile_definition.get("enabled_steps") or [])
    timestamp = utc_now_iso()
    node_positions = {
        "dictionary_input": {"x": 120, "y": 80},
        "corpus_input": {"x": 120, "y": 330},
        "merge_corpora": {"x": 520, "y": 330},
        "clean_text": {"x": 900, "y": 330},
        "normalize_text": {"x": 1280, "y": 330},
        "tokenize": {"x": 1680, "y": 330},
        "apply_dictionary_rules": {"x": 2060, "y": 330},
        "filter_terms": {"x": 2460, "y": 330},
        "frequency_statistics": {"x": 2860, "y": 80},
        "term_document_analysis": {"x": 2860, "y": 340},
        "term_year_analysis": {"x": 2860, "y": 600},
        "cooccurrence_analysis": {"x": 2860, "y": 860},
        "feature_term_selection": {"x": 2860, "y": 1120},
        "keyword_extraction": {"x": 3240, "y": 80},
        "keyword_clustering": {"x": 3240, "y": 340},
        "institution_keyword_analysis": {"x": 3240, "y": 600},
        "institution_topic_analysis": {"x": 3240, "y": 860},
        "document_clustering": {"x": 3240, "y": 1120},
        "save_csv": {"x": 3620, "y": 80},
        "save_xlsx": {"x": 3620, "y": 340},
        "save_png": {"x": 3620, "y": 600},
        "save_html_report": {"x": 3620, "y": 860},
    }
    default_node_size = {"w": 230, "h": 190}

    def workflow_port(
        port_id: str,
        port_type: str,
        label: str,
        *,
        allow_multiple: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "port_id": port_id,
            "port_type": port_type,
            "label": label,
        }
        if allow_multiple:
            payload["allow_multiple"] = True
        return payload

    def workflow_node(
        node_id: str,
        node_type: str,
        label: str,
        inputs: list[dict[str, Any]],
        outputs: list[dict[str, Any]],
        config: dict[str, Any],
        step_id: str,
    ) -> dict[str, Any]:
        return {
            "node_id": node_id,
            "node_type": node_type,
            "label": label,
            "position": deepcopy(node_positions[node_type]),
            "size": deepcopy(default_node_size),
            "inputs": deepcopy(inputs),
            "outputs": deepcopy(outputs),
            "config": deepcopy(config),
            "ui_state": {
                "collapsed": False,
                "bypassed": False,
            },
            "runtime_meta": {
                "step_id": step_id,
                "node_impl_version": "2.0.0",
            },
        }

    def make_edge(
        edge_id: str,
        from_node: str,
        from_port: str,
        to_node: str,
        to_port: str,
    ) -> dict[str, Any]:
        return {
            "edge_id": edge_id,
            "from_node": from_node,
            "from_port": from_port,
            "to_node": to_node,
            "to_port": to_port,
        }

    export_definition = deepcopy(runtime_profile_definition.get("export") or {})
    run_scope_definition = deepcopy(runtime_profile_definition.get("run_scope") or {})

    filtered_sequence: list[str] = ["corpus_input"]
    if "cleaning" in enabled_steps:
        filtered_sequence.append("clean_text")
    if "normalization" in enabled_steps:
        filtered_sequence.append("normalize_text")
    filtered_sequence.append("tokenize")
    if "dictionary_application" in enabled_steps:
        filtered_sequence.append("apply_dictionary_rules")
    if "filtering" in enabled_steps:
        filtered_sequence.append("filter_terms")

    starter_nodes: list[dict[str, Any]] = []

    starter_nodes.append(
        workflow_node(
            "node-corpus-input",
            "corpus_input",
            "语料输入",
            [],
            [workflow_port("corpus", "CorpusTable", "语料")],
            {
                "resource_mode": "project_corpus",
                "resource_id": "project:corpus",
                **run_scope_definition,
            },
            "scope",
        )
    )
    starter_nodes.append(
        workflow_node(
            "node-dictionary-input",
            "dictionary_input",
            "词表输入",
            [],
            [workflow_port("dictionary_set", "DictionarySet", "词表")],
            {
                "resource_mode": "project_dictionary",
                "resource_id": "project:dictionary_set",
                "use_custom_lexicon": True,
                "use_phrase_lexicon": True,
                "apply_regex_rules": True,
                "apply_standard_terms": True,
                "apply_synonym_map": True,
                "apply_near_synonym_map": True,
                "apply_stopwords": True,
                "apply_exclusion_terms": True,
            },
            "resource",
        )
    )

    if "clean_text" in filtered_sequence:
        starter_nodes.append(
            workflow_node(
                "node-clean-text",
                "clean_text",
                "基础清洗",
                [workflow_port("corpus_in", "CorpusTable", "语料输入")],
                [workflow_port("clean_corpus", "CleanCorpus", "清洗后语料")],
                deepcopy(runtime_profile_definition.get("cleaning") or {}),
                "cleaning",
            )
        )
    if "normalize_text" in filtered_sequence:
        starter_nodes.append(
            workflow_node(
                "node-normalize-text",
                "normalize_text",
                "统一写法",
                [workflow_port("corpus_in", "CleanCorpus", "清洗后语料")],
                [workflow_port("normalized_corpus", "NormalizedCorpus", "标准化语料")],
                deepcopy(runtime_profile_definition.get("normalization") or {}),
                "normalization",
            )
        )
    starter_nodes.append(
        workflow_node(
            "node-tokenize",
            "tokenize",
            "切词",
            [workflow_port("corpus_in", "NormalizedCorpus", "标准化语料")],
            [workflow_port("token_corpus", "TokenCorpus", "Token 语料")],
            deepcopy(runtime_profile_definition.get("tokenization") or {}),
            "tokenization",
        )
    )
    if "apply_dictionary_rules" in filtered_sequence:
        starter_nodes.append(
            workflow_node(
                "node-apply-dictionary-rules",
                "apply_dictionary_rules",
                "套用词表",
                [
                    workflow_port("token_corpus_in", "TokenCorpus", "Token 输入"),
                    workflow_port("dictionary_set_in", "DictionarySet", "词表输入"),
                ],
                [
                    workflow_port("token_corpus", "TokenCorpus", "规则处理后 Token"),
                    workflow_port("audit_table", "AuditTable", "审计表"),
                ],
                deepcopy(runtime_profile_definition.get("dictionary") or {}),
                "dictionary_application",
            )
        )
    if "filter_terms" in filtered_sequence:
        starter_nodes.append(
            workflow_node(
                "node-filter-terms",
                "filter_terms",
                "过滤词项",
                [workflow_port("token_corpus_in", "TokenCorpus", "Token 输入")],
                [workflow_port("filtered_token_corpus", "FilteredTokenCorpus", "分析词项")],
                deepcopy(runtime_profile_definition.get("filtering") or {}),
                "filtering",
            )
        )

    starter_nodes.extend(
        [
            workflow_node(
                "node-frequency-statistics",
                "frequency_statistics",
                "词频统计",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("frequency_table", "FrequencyTable", "词频表")],
                {"top_n": int((runtime_profile_definition.get("analysis") or {}).get("top_n", 200))},
                "analysis",
            ),
            workflow_node(
                "node-term-document-analysis",
                "term_document_analysis",
                "词项文档分析",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("term_document_table", "TermDocumentTable", "词项文档表")],
                {},
                "analysis",
            ),
            workflow_node(
                "node-term-year-analysis",
                "term_year_analysis",
                "词项年份分析",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("term_year_table", "TermYearTable", "词项年份表")],
                {},
                "analysis",
            ),
            workflow_node(
                "node-cooccurrence-analysis",
                "cooccurrence_analysis",
                "共现分析",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("cooccurrence_table", "CooccurrenceTable", "共现表")],
                {
                    "cooccurrence_window": int((runtime_profile_definition.get("analysis") or {}).get("cooccurrence_window", 5)),
                    "min_cooccurrence": int((runtime_profile_definition.get("analysis") or {}).get("min_cooccurrence", 2)),
                },
                "analysis",
            ),
            workflow_node(
                "node-feature-term-selection",
                "feature_term_selection",
                "特征词筛选",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("feature_term_table", "FeatureTermTable", "特征词表")],
                {
                    "feature_term_count": (runtime_profile_definition.get("analysis") or {}).get("feature_term_count", 1000),
                },
                "analysis",
            ),
            workflow_node(
                "node-keyword-extraction",
                "keyword_extraction",
                "关键词提取",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("keyword_table", "KeywordTable", "关键词表")],
                {
                    "top_k_per_doc": int((runtime_profile_definition.get("analysis") or {}).get("top_k_per_doc", 10)),
                    "top_k_project": int((runtime_profile_definition.get("analysis") or {}).get("top_k_project", 100)),
                },
                "analysis",
            ),
            workflow_node(
                "node-keyword-clustering",
                "keyword_clustering",
                "关键词聚类",
                [workflow_port("feature_term_table_in", "FeatureTermTable", "特征词输入")],
                [workflow_port("keyword_cluster_table", "KeywordClusterTable", "关键词聚类表")],
                {
                    "keyword_cluster_k": int((runtime_profile_definition.get("analysis") or {}).get("keyword_cluster_k", 4)),
                    "topic_model_k": int((runtime_profile_definition.get("analysis") or {}).get("topic_model_k", 4)),
                },
                "analysis",
            ),
            workflow_node(
                "node-institution-keyword-analysis",
                "institution_keyword_analysis",
                "机构关键词分析",
                [workflow_port("keyword_table_in", "KeywordTable", "关键词输入")],
                [workflow_port("institution_keyword_table", "InstitutionKeywordTable", "机构关键词表")],
                {},
                "analysis",
            ),
            workflow_node(
                "node-institution-topic-analysis",
                "institution_topic_analysis",
                "机构主题分析",
                [workflow_port("keyword_cluster_table_in", "KeywordClusterTable", "主题输入")],
                [workflow_port("institution_topic_table", "InstitutionTopicTable", "机构主题表")],
                {
                    "topic_model_k": int((runtime_profile_definition.get("analysis") or {}).get("topic_model_k", 4)),
                },
                "analysis",
            ),
            workflow_node(
                "node-document-clustering",
                "document_clustering",
                "文档聚类",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("document_cluster_table", "DocumentClusterTable", "文档聚类表")],
                {
                    "document_cluster_k": int((runtime_profile_definition.get("analysis") or {}).get("document_cluster_k", 4)),
                },
                "analysis",
            ),
        ]
    )

    if bool(export_definition.get("export_csv", True)):
        starter_nodes.append(
            workflow_node(
                "node-save-csv",
                "save_csv",
                "保存 CSV",
                [workflow_port("table_in", "AnyTable", "表格输入", allow_multiple=True)],
                [workflow_port("artifact", "ExportArtifact", "导出产物")],
                {"file_prefix": "tables", "export_csv": True},
                "export",
            )
        )
    if bool(export_definition.get("export_xlsx", True)):
        starter_nodes.append(
            workflow_node(
                "node-save-xlsx",
                "save_xlsx",
                "保存 XLSX",
                [workflow_port("table_in", "AnyTable", "表格输入", allow_multiple=True)],
                [workflow_port("artifact", "ExportArtifact", "导出产物")],
                {"file_prefix": "tables", "export_xlsx": True},
                "export",
            )
        )
    if bool(export_definition.get("export_png", True)):
        starter_nodes.append(
            workflow_node(
                "node-save-png",
                "save_png",
                "保存 PNG",
                [workflow_port("render_in", "AnyRenderable", "图像输入", allow_multiple=True)],
                [workflow_port("artifact", "ExportArtifact", "导出产物")],
                {
                    "file_prefix": "charts",
                    "chart_dpi": int(export_definition.get("chart_dpi", 320)),
                },
                "export",
            )
        )
    if bool(export_definition.get("export_html_report", True)):
        starter_nodes.append(
            workflow_node(
                "node-save-html-report",
                "save_html_report",
                "保存 HTML 报告",
                [workflow_port("report_in", "AnyAnalysisResult", "报告输入", allow_multiple=True)],
                [workflow_port("artifact", "ExportArtifact", "导出产物")],
                {
                    "file_prefix": "report",
                    "include_audit": bool(export_definition.get("include_audit", True)),
                },
                "export",
            )
        )

    node_by_type = {
        str(node["node_type"]): node
        for node in starter_nodes
    }

    def single_output_port(node_type: str) -> str | None:
        node = node_by_type.get(node_type)
        if not isinstance(node, dict):
            return None
        outputs = node.get("outputs")
        if not isinstance(outputs, list) or not outputs:
            return None
        first_port = outputs[0]
        return str(first_port.get("port_id") or "") if isinstance(first_port, dict) else None

    edges: list[dict[str, Any]] = []
    edge_counter = 1

    for from_type, to_type in zip(filtered_sequence, filtered_sequence[1:]):
        from_node = node_by_type.get(from_type)
        to_node = node_by_type.get(to_type)
        from_port = single_output_port(from_type)
        to_port = str((to_node.get("inputs") or [{}])[0].get("port_id") or "") if isinstance(to_node, dict) else ""
        if from_node and to_node and from_port and to_port:
            edges.append(make_edge(f"edge-{edge_counter}", str(from_node["node_id"]), from_port, str(to_node["node_id"]), to_port))
            edge_counter += 1

    dictionary_node = node_by_type.get("dictionary_input")
    dictionary_apply_node = node_by_type.get("apply_dictionary_rules")
    if dictionary_node and dictionary_apply_node:
        edges.append(
            make_edge(
                f"edge-{edge_counter}",
                str(dictionary_node["node_id"]),
                "dictionary_set",
                str(dictionary_apply_node["node_id"]),
                "dictionary_set_in",
            )
        )
        edge_counter += 1

    last_process_node = None
    for node_type in ["filter_terms", "apply_dictionary_rules", "tokenize", "normalize_text", "clean_text", "corpus_input"]:
        candidate = node_by_type.get(node_type)
        if candidate:
            last_process_node = candidate
            break

    for analysis_type in [
        "frequency_statistics",
        "term_document_analysis",
        "term_year_analysis",
        "cooccurrence_analysis",
        "feature_term_selection",
        "keyword_extraction",
        "keyword_clustering",
        "institution_keyword_analysis",
        "institution_topic_analysis",
        "document_clustering",
    ]:
        analysis_node = node_by_type.get(analysis_type)
        if not analysis_node:
            continue
        if analysis_type == "keyword_clustering":
            feature_term_node = node_by_type.get("feature_term_selection")
            if feature_term_node:
                edges.append(
                    make_edge(
                        f"edge-{edge_counter}",
                        str(feature_term_node["node_id"]),
                        "feature_term_table",
                        str(analysis_node["node_id"]),
                        "feature_term_table_in",
                    )
                )
                edge_counter += 1
            continue
        if analysis_type == "institution_keyword_analysis":
            keyword_node = node_by_type.get("keyword_extraction")
            if keyword_node:
                edges.append(
                    make_edge(
                        f"edge-{edge_counter}",
                        str(keyword_node["node_id"]),
                        "keyword_table",
                        str(analysis_node["node_id"]),
                        "keyword_table_in",
                    )
                )
                edge_counter += 1
            continue
        if analysis_type == "institution_topic_analysis":
            cluster_node = node_by_type.get("keyword_clustering")
            if cluster_node:
                edges.append(
                    make_edge(
                        f"edge-{edge_counter}",
                        str(cluster_node["node_id"]),
                        "keyword_cluster_table",
                        str(analysis_node["node_id"]),
                        "keyword_cluster_table_in",
                    )
                )
                edge_counter += 1
            continue
        if last_process_node:
            from_port = str(((last_process_node.get("outputs") or [{}])[0]).get("port_id") or "")
            to_port = str(((analysis_node.get("inputs") or [{}])[0]).get("port_id") or "")
            if from_port and to_port:
                edges.append(
                    make_edge(
                        f"edge-{edge_counter}",
                        str(last_process_node["node_id"]),
                        from_port,
                        str(analysis_node["node_id"]),
                        to_port,
                    )
                )
                edge_counter += 1

    sink_mappings = {
        "save_csv": [
            "frequency_statistics",
            "term_document_analysis",
            "term_year_analysis",
            "cooccurrence_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "keyword_clustering",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "document_clustering",
        ],
        "save_xlsx": [
            "frequency_statistics",
            "term_document_analysis",
            "term_year_analysis",
            "cooccurrence_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "keyword_clustering",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "document_clustering",
        ],
        "save_png": [
            "frequency_statistics",
            "keyword_extraction",
            "keyword_clustering",
            "institution_topic_analysis",
            "document_clustering",
        ],
        "save_html_report": [
            "frequency_statistics",
            "term_document_analysis",
            "term_year_analysis",
            "cooccurrence_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "keyword_clustering",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "document_clustering",
        ],
    }

    for sink_type, source_types in sink_mappings.items():
        sink_node = node_by_type.get(sink_type)
        if not sink_node:
            continue
        sink_port = str(((sink_node.get("inputs") or [{}])[0]).get("port_id") or "")
        if not sink_port:
            continue
        for source_type in source_types:
            source_node = node_by_type.get(source_type)
            from_port = single_output_port(source_type)
            if not source_node or not from_port:
                continue
            edges.append(
                make_edge(
                    f"edge-{edge_counter}",
                    str(source_node["node_id"]),
                    from_port,
                    str(sink_node["node_id"]),
                    sink_port,
                )
            )
            edge_counter += 1
        if sink_type == "save_html_report" and dictionary_apply_node:
            edges.append(
                make_edge(
                    f"edge-{edge_counter}",
                    str(dictionary_apply_node["node_id"]),
                    "audit_table",
                    str(sink_node["node_id"]),
                    sink_port,
                )
            )
            edge_counter += 1

    return {
        "workflow_id": workflow_id,
        "name": name,
        "version": "2.0.0",
        "graph_mode": "dag",
        "source": source,
        "meta": {
            "template_id": str(runtime_profile_definition.get("recipe_id") or "standard_analysis"),
            "output_bundle_id": str(runtime_profile_definition.get("output_bundle_id") or "full_report"),
        },
        "nodes": starter_nodes,
        "edges": edges,
        "groups": [],
        "viewport": {
            "x": 0,
            "y": 0,
            "zoom": 0.82,
        },
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def workflow_port_compatible(source_type: str, target_type: str) -> bool:
    if source_type == target_type:
        return True
    table_source_types = {
        "FrequencyTable",
        "TermDocumentTable",
        "TermYearTable",
        "CooccurrenceTable",
        "FeatureTermTable",
        "KeywordTable",
        "KeywordClusterTable",
        "InstitutionKeywordTable",
        "InstitutionTopicTable",
        "DocumentClusterTable",
        "AuditTable",
        "MetadataAuditTable",
        "GraphNodeTable",
        "GraphEdgeTable",
        "GraphMetricTable",
        "CommunityTable",
        "MainPathTable",
        "LinkPredictionTable",
        "TechnologyIndicatorTable",
        "TechnologyClassificationTable",
    }
    renderable_source_types = {
        "FrequencyTable",
        "KeywordTable",
        "TermYearTable",
        "CooccurrenceTable",
        "DocumentClusterTable",
        "KeywordClusterTable",
        "InstitutionTopicTable",
        "AnalysisBundle",
        "AnyTable",
    }
    analysis_result_types = set(table_source_types) | {"AnalysisBundle", "AnyTable"}
    if target_type == "AnyTable" and source_type in table_source_types:
        return True
    if target_type == "AnyRenderable" and source_type in renderable_source_types:
        return True
    if target_type == "AnyAnalysisResult" and source_type in analysis_result_types:
        return True
    corpus_port_order = [
        "CorpusTable",
        "ProjectCorpus",
        "ScopedCorpus",
        "CleanCorpus",
        "NormalizedCorpus",
        "TokenCorpus",
        "FilteredTokenCorpus",
    ]
    try:
        source_index = corpus_port_order.index(source_type)
        target_index = corpus_port_order.index(target_type)
    except ValueError:
        if source_type in {"ProjectCorpus", "ScopedCorpus"} and target_type == "CorpusTable":
            return True
        if source_type == "CorpusTable" and target_type in {"ProjectCorpus", "ScopedCorpus"}:
            return True
        return False
    return source_index <= target_index


def workflow_find_port(node: dict[str, Any] | None, port_id: str, direction: str) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    ports = node.get(direction)
    if not isinstance(ports, list):
        return None
    for port in ports:
        if isinstance(port, dict) and str(port.get("port_id")) == port_id:
            return port
    return None


def normalize_workflow_edges(
    workflow_definition: dict[str, Any] | None,
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    edge_rows = workflow_definition.get("edges") if isinstance(workflow_definition, dict) else []
    if not isinstance(edge_rows, list):
        return []

    node_lookup = {
        str(node.get("node_id")): node
        for node in nodes
        if isinstance(node, dict) and node.get("node_id")
    }
    normalized: list[dict[str, Any]] = []

    for edge in edge_rows:
        if not isinstance(edge, dict):
            continue
        from_node_id = str(edge.get("from_node") or "")
        to_node_id = str(edge.get("to_node") or "")
        from_port_id = str(edge.get("from_port") or "")
        to_port_id = str(edge.get("to_port") or "")
        if not from_node_id or not to_node_id or from_node_id == to_node_id:
            continue
        from_node = node_lookup.get(from_node_id)
        to_node = node_lookup.get(to_node_id)
        from_port = workflow_find_port(from_node, from_port_id, "outputs")
        to_port = workflow_find_port(to_node, to_port_id, "inputs")
        if not isinstance(from_port, dict) or not isinstance(to_port, dict):
            continue
        if not workflow_port_compatible(str(from_port.get("port_type") or ""), str(to_port.get("port_type") or "")):
            continue

        target_allows_multiple = bool(to_port.get("allow_multiple"))
        if not target_allows_multiple:
            normalized = [
                existing
                for existing in normalized
                if not (
                    str(existing.get("to_node")) == to_node_id
                    and str(existing.get("to_port")) == to_port_id
                )
            ]
        if any(
            str(existing.get("from_node")) == from_node_id
            and str(existing.get("from_port")) == from_port_id
            and str(existing.get("to_node")) == to_node_id
            and str(existing.get("to_port")) == to_port_id
            for existing in normalized
        ):
            continue
        normalized.append(deepcopy(edge))

    return normalized


def workflow_reachable_node_ids(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> set[str]:
    incoming: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        key = (str(edge.get("to_node") or ""), str(edge.get("to_port") or ""))
        if not all(key):
            continue
        incoming.setdefault(key, []).append(edge)

    reachable = set()
    for node in nodes:
        if not isinstance(node, dict) or not node.get("node_id"):
            continue
        inputs = node.get("inputs")
        if isinstance(inputs, list) and not inputs:
            reachable.add(str(node["node_id"]))

    changed = True
    while changed:
        changed = False
        for node in nodes:
            if not isinstance(node, dict) or not node.get("node_id"):
                continue
            node_id = str(node["node_id"])
            if node_id in reachable:
                continue
            inputs = node.get("inputs")
            if not isinstance(inputs, list) or not inputs:
                continue
            if all(
                any(str(edge.get("from_node") or "") in reachable for edge in incoming.get((node_id, str(port.get("port_id") or "")), []))
                for port in inputs
                if isinstance(port, dict)
            ):
                reachable.add(node_id)
                changed = True
    return reachable


def workflow_active_node_ids_from_sinks(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    reachable_node_ids: set[str],
) -> set[str]:
    sink_node_types = {"save_csv", "save_xlsx", "save_png", "save_html_report", "export_results"}
    incoming_by_key: dict[str, list[dict[str, Any]]] = {}
    node_lookup = {str(node.get("node_id") or ""): node for node in nodes if isinstance(node, dict)}
    for edge in edges:
        to_node_id = str(edge.get("to_node") or "")
        to_port_id = str(edge.get("to_port") or "")
        incoming_by_key.setdefault(f"{to_node_id}:{to_port_id}", []).append(edge)

    sink_ids: list[str] = []
    for node in nodes:
        node_id = str(node.get("node_id") or "")
        if node_id not in reachable_node_ids:
            continue
        if str(node.get("node_type") or "") not in sink_node_types:
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, list):
            continue
        if all(incoming_by_key.get(f"{node_id}:{str(port.get('port_id') or '')}") for port in inputs if isinstance(port, dict)):
            sink_ids.append(node_id)

    active_ids = set(sink_ids)
    stack = sink_ids[:]
    while stack:
        current_id = stack.pop()
        current_node = node_lookup.get(current_id)
        if not isinstance(current_node, dict):
            continue
        inputs = current_node.get("inputs")
        if not isinstance(inputs, list):
            continue
        for port in inputs:
            if not isinstance(port, dict):
                continue
            for edge in incoming_by_key.get(f"{current_id}:{str(port.get('port_id') or '')}", []):
                from_node_id = str(edge.get("from_node") or "")
                if from_node_id and from_node_id not in active_ids:
                    active_ids.add(from_node_id)
                    stack.append(from_node_id)
    return active_ids


def compile_runtime_profile_from_workflow(
    workflow_definition: dict[str, Any] | None,
    runtime_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from ..workflow.compilers import compile_runtime_profile_from_workflow as compile_runtime_profile_with_registry

    return compile_runtime_profile_with_registry(workflow_definition, runtime_profile)


def empty_result_bundle() -> dict[str, Any]:
    return {
        "frequency_table": [],
        "term_document_table": [],
        "term_year_table": [],
        "cooccurrence_table": [],
        "similarity_table": [],
        "selected_feature_terms": [],
        "focus_term_summary": [],
        "keyword_result": [],
        "keyword_cluster_result": [],
        "institution_keyword_cooccurrence": [],
        "institution_topic_cooccurrence": [],
        "clustering_result": [],
        "graph_node_table": [],
        "graph_edge_table": [],
        "graph_metric_table": [],
        "community_table": [],
        "main_path_table": [],
        "link_prediction_table": [],
        "technology_indicator_table": [],
        "technology_classification_table": [],
        "metadata_audit_table": [],
        "audit_table": [],
        "report_files": [],
    }


def default_project_manifest(
    name: str,
    description: str,
    root_relative_path: str,
    *,
    include_dictionary_set: bool = True,
) -> dict[str, Any]:
    timestamp = utc_now_iso()
    workflow = default_workflow_definition(default_runtime_profile())
    return {
        "id": f"project-{uuid4().hex[:12]}",
        "schema_version": "2.0.0",
        "name": name,
        "description": description,
        "created_at": timestamp,
        "updated_at": timestamp,
        "version": "0.2.0",
        "source_files": [],
        "corpus_resources": [],
        "corpus_views": [],
        "ingestion_specs": [],
        "artifact_records": [],
        "review_tasks": [],
        "experiment_specs": [],
        "shared_resource_refs": [],
        "settings": {
            "default_language": "mixed",
            "preferred_theme": "paper",
            "enable_auto_save": True,
            "enable_update_check": False,
            "default_export_formats": ["csv", "xlsx", "png", "html"],
        },
        "paths": {
            "root": root_relative_path,
            "corpus_dir": "corpus",
            "dictionaries_dir": "dictionaries",
            "runs_dir": "runs",
            "cache_dir": "cache",
            "exports_dir": "exports",
        },
        "import_template": default_import_template(),
        "dictionary_set": default_dictionary_set() if include_dictionary_set else {},
        "workflow_definitions": [workflow],
        "active_workflow_id": workflow["workflow_id"],
        "run_history": [],
        "results": empty_result_bundle(),
    }


def deep_copy_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(manifest)

