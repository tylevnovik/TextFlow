from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def make_dictionary_entry(source: str, target: str | None = None, hits: int = 0) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "source": source,
        "target": target,
        "tags": [],
        "enabled": True,
        "hits": hits,
        "notes": "",
    }


def make_sheet(kind: str, name: str, rows: list[tuple[str, str | None, int]]) -> dict[str, Any]:
    return {
        "kind": kind,
        "name": name,
        "version": "1.0.0",
        "entries": [make_dictionary_entry(source, target, hits) for source, target, hits in rows],
    }


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
                {"source_field": "UT", "target_field": "doc_id", "required": True, "aliases": ["Accession Number"]},
                {"source_field": "TI", "target_field": "title", "required": True, "aliases": ["Article Title"]},
                {"source_field": "AB", "target_field": "raw_text", "required": True, "aliases": ["Abstract"]},
                {"source_field": "PY", "target_field": "year", "required": False, "aliases": ["Published Year"]},
                {"source_field": "SO", "target_field": "source", "required": False, "aliases": ["Publication Name"]},
                {"source_field": "AU", "target_field": "author", "required": False, "aliases": ["Authors"]},
                {"source_field": "C1", "target_field": "institution", "required": False, "aliases": ["Addresses"]},
                {"source_field": "DE", "target_field": "keyword_field", "required": False, "aliases": ["Author Keywords"]},
                {"source_field": "WC", "target_field": "category_or_tag", "required": False, "aliases": ["Web of Science Categories"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["TI", "AB", "DE"], "delimiter": "\n\n", "skip_empty": True},
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
                {"source_field": "公开（公告）号", "target_field": "doc_id", "required": True, "aliases": ["申请号", "专利号"]},
                {"source_field": "标题", "target_field": "title", "required": True, "aliases": ["专利名称"]},
                {"source_field": "摘要", "target_field": "raw_text", "required": True, "aliases": ["简介"]},
                {"source_field": "公开（公告）日", "target_field": "year", "required": False, "aliases": ["申请日", "年份"]},
                {"source_field": "申请人", "target_field": "institution", "required": False, "aliases": ["专利权人"]},
                {"source_field": "发明人", "target_field": "author", "required": False, "aliases": ["Inventor"]},
                {"source_field": "IPC分类号", "target_field": "category_or_tag", "required": False, "aliases": ["IPC"]},
                {"source_field": "关键词", "target_field": "keyword_field", "required": False, "aliases": ["主题词"]},
            ],
            "text_build": {"mode": "concat_fields", "fields": ["标题", "摘要", "关键词"], "delimiter": "\n\n", "skip_empty": True},
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


def default_dictionary_set() -> dict[str, Any]:
    sheets = {
        "stopwords": make_sheet("stopwords", "停用词表", [("的", None, 0), ("和", None, 0), ("but", None, 0)]),
        "custom_lexicon": make_sheet("custom_lexicon", "自定义词典", [("智能制造", None, 0), ("battery recycling", None, 0)]),
        "phrase_lexicon": make_sheet("phrase_lexicon", "短语词典", [("supply chain", "supply_chain", 0), ("学术规范", "学术规范", 0)]),
        "synonym_map": make_sheet("synonym_map", "同义词表", [("generative ai", "生成式", 0), ("battery recycling", "battery_recycling", 0)]),
        "near_synonym_map": make_sheet("near_synonym_map", "近义词表", [("文本挖掘", "分析", 0), ("知识抽取", "工艺知识", 0)]),
        "standard_terms": make_sheet("standard_terms", "标准词库", [("供应链", "supply_chain", 0), ("机构主题", "topic", 0)]),
        "exclusion_terms": make_sheet("exclusion_terms", "排除词表", [("etc", None, 0), ("misc", None, 0)]),
        "regex_rules": make_sheet("regex_rules", "Regex 规则表", [(r"\d{4}年", "YEAR_TOKEN", 0), (r"https?://\S+", "", 0)]),
    }
    return {
        "id": "dict-default",
        "name": "默认词表集",
        "version": "1.0.0",
        "bound_to_project": True,
        "sheets": sheets,
    }


def default_import_template(source_profile: str = "generic") -> dict[str, Any]:
    template = profile_import_template(source_profile)
    return {"id": f"template-{source_profile}", "source_profile": source_profile, **template}


def default_pipeline() -> dict[str, Any]:
    return {
        "id": "pipeline-default",
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
            "topic_model_k": 4,
            "keyword_cluster_k": 4,
            "document_cluster_k": 4,
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


def empty_result_bundle() -> dict[str, Any]:
    return {
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
        "audit_table": [],
        "report_files": [],
    }


def default_project_manifest(name: str, description: str, root_relative_path: str) -> dict[str, Any]:
    timestamp = utc_now_iso()
    return {
        "id": f"project-{uuid4().hex[:12]}",
        "schema_version": "1.0.0",
        "name": name,
        "description": description,
        "created_at": timestamp,
        "updated_at": timestamp,
        "version": "0.1.0",
        "source_files": [],
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
            "pipelines_dir": "pipelines",
            "runs_dir": "runs",
            "cache_dir": "cache",
            "exports_dir": "exports",
        },
        "import_template": default_import_template(),
        "dictionary_set": default_dictionary_set(),
        "pipeline": default_pipeline(),
        "run_history": [],
        "results": empty_result_bundle(),
    }


def deep_copy_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(manifest)
