from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
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


def workflow_payload_hash(workflow_definition: dict[str, Any] | None) -> str:
    payload = deepcopy(workflow_definition) if isinstance(workflow_definition, dict) else {}
    if isinstance(payload, dict):
        payload.pop("created_at", None)
        payload.pop("updated_at", None)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def default_workflow_definition(
    pipeline: dict[str, Any] | None = None,
    *,
    workflow_id: str = "wf-default",
    name: str = "默认工作流",
    source: str = "system_default",
) -> dict[str, Any]:
    pipeline_definition = deepcopy(pipeline if isinstance(pipeline, dict) else default_pipeline())
    enabled_steps = set(pipeline_definition.get("enabled_steps") or [])
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
        "term_year_analysis": {"x": 2860, "y": 340},
        "cooccurrence_analysis": {"x": 2860, "y": 600},
        "keyword_extraction": {"x": 2860, "y": 860},
        "keyword_clustering": {"x": 3240, "y": 860},
        "institution_topic_analysis": {"x": 3240, "y": 600},
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

    export_definition = deepcopy(pipeline_definition.get("export") or {})
    run_scope_definition = deepcopy(pipeline_definition.get("run_scope") or {})

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
                deepcopy(pipeline_definition.get("cleaning") or {}),
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
                deepcopy(pipeline_definition.get("normalization") or {}),
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
            deepcopy(pipeline_definition.get("tokenization") or {}),
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
                deepcopy(pipeline_definition.get("dictionary") or {}),
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
                deepcopy(pipeline_definition.get("filtering") or {}),
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
                {"top_n": int((pipeline_definition.get("analysis") or {}).get("top_n", 200))},
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
                    "cooccurrence_window": int((pipeline_definition.get("analysis") or {}).get("cooccurrence_window", 5)),
                    "min_cooccurrence": int((pipeline_definition.get("analysis") or {}).get("min_cooccurrence", 2)),
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
                    "top_k_per_doc": int((pipeline_definition.get("analysis") or {}).get("top_k_per_doc", 10)),
                    "top_k_project": int((pipeline_definition.get("analysis") or {}).get("top_k_project", 100)),
                },
                "analysis",
            ),
            workflow_node(
                "node-keyword-clustering",
                "keyword_clustering",
                "关键词聚类",
                [workflow_port("keyword_table_in", "KeywordTable", "关键词输入")],
                [workflow_port("keyword_cluster_table", "KeywordClusterTable", "关键词聚类表")],
                {
                    "keyword_cluster_k": int((pipeline_definition.get("analysis") or {}).get("keyword_cluster_k", 4)),
                    "topic_model_k": int((pipeline_definition.get("analysis") or {}).get("topic_model_k", 4)),
                },
                "analysis",
            ),
            workflow_node(
                "node-institution-topic-analysis",
                "institution_topic_analysis",
                "机构主题分析",
                [workflow_port("token_corpus_in", "FilteredTokenCorpus", "分析词项")],
                [workflow_port("institution_topic_table", "InstitutionTopicTable", "机构主题表")],
                {
                    "topic_model_k": int((pipeline_definition.get("analysis") or {}).get("topic_model_k", 4)),
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
        "term_year_analysis",
        "cooccurrence_analysis",
        "keyword_extraction",
        "keyword_clustering",
        "institution_topic_analysis",
    ]:
        analysis_node = node_by_type.get(analysis_type)
        if not analysis_node:
            continue
        if analysis_type == "keyword_clustering":
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
            "term_year_analysis",
            "cooccurrence_analysis",
            "keyword_extraction",
            "keyword_clustering",
            "institution_topic_analysis",
        ],
        "save_xlsx": [
            "frequency_statistics",
            "term_year_analysis",
            "cooccurrence_analysis",
            "keyword_extraction",
            "keyword_clustering",
            "institution_topic_analysis",
        ],
        "save_png": [
            "frequency_statistics",
            "term_year_analysis",
            "cooccurrence_analysis",
            "keyword_clustering",
            "institution_topic_analysis",
        ],
        "save_html_report": [
            "frequency_statistics",
            "term_year_analysis",
            "cooccurrence_analysis",
            "keyword_extraction",
            "keyword_clustering",
            "institution_topic_analysis",
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
            "template_id": str(pipeline_definition.get("recipe_id") or "standard_analysis"),
            "output_bundle_id": str(pipeline_definition.get("output_bundle_id") or "full_report"),
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
        "KeywordTable",
        "KeywordClusterTable",
        "InstitutionTopicTable",
        "AuditTable",
    }
    renderable_source_types = {
        "FrequencyTable",
        "TermYearTable",
        "CooccurrenceTable",
        "KeywordClusterTable",
        "InstitutionTopicTable",
        "AnalysisBundle",
    }
    analysis_result_types = set(table_source_types) | {"AnalysisBundle"}
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


def compile_pipeline_from_workflow(
    workflow_definition: dict[str, Any] | None,
    pipeline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    compiled = deepcopy(pipeline if isinstance(pipeline, dict) else default_pipeline())
    execution_order = list(compiled.get("execution_order") or default_pipeline()["execution_order"])
    enabled_steps: list[str] = ["ingestion"]
    nodes = workflow_definition.get("nodes") if isinstance(workflow_definition, dict) else []

    if isinstance(nodes, list):
        normalized_nodes = [node for node in nodes if isinstance(node, dict) and node.get("node_id")]
        normalized_edges = normalize_workflow_edges(workflow_definition, normalized_nodes)
        reachable_node_ids = workflow_reachable_node_ids(normalized_nodes, normalized_edges)
        active_node_ids = workflow_active_node_ids_from_sinks(normalized_nodes, normalized_edges, reachable_node_ids)
        if not active_node_ids:
            active_node_ids = set(reachable_node_ids)

        export_config = deepcopy(compiled.get("export") or {})
        export_config.update(
            {
                "export_csv": False,
                "export_xlsx": False,
                "export_png": False,
                "export_html_report": False,
            }
        )

        for node in normalized_nodes:
            node_id = str(node.get("node_id") or "")
            if node_id not in active_node_ids:
                continue
            if not isinstance(node, dict):
                continue
            node_type = str(node.get("node_type") or "")
            config = node.get("config")
            if not isinstance(config, dict):
                config = {}
            ui_state = node.get("ui_state")
            bypassed = bool(ui_state.get("bypassed")) if isinstance(ui_state, dict) else False
            if bypassed:
                continue

            if node_type in {"corpus_input", "filter_corpus"}:
                compiled["run_scope"] = {
                    **deepcopy(compiled.get("run_scope") or {}),
                    **config,
                }
                continue

            if node_type == "dictionary_input":
                compiled["tokenization"] = {
                    **deepcopy(compiled.get("tokenization") or {}),
                    "use_custom_lexicon": bool(config.get("use_custom_lexicon", (compiled.get("tokenization") or {}).get("use_custom_lexicon", True))),
                    "use_phrase_lexicon": bool(config.get("use_phrase_lexicon", (compiled.get("tokenization") or {}).get("use_phrase_lexicon", True))),
                }
                compiled["normalization"] = {
                    **deepcopy(compiled.get("normalization") or {}),
                    "apply_regex_rules": bool(config.get("apply_regex_rules", (compiled.get("normalization") or {}).get("apply_regex_rules", True))),
                }
                compiled["dictionary"] = {
                    **deepcopy(compiled.get("dictionary") or {}),
                    "apply_standard_terms": bool(config.get("apply_standard_terms", (compiled.get("dictionary") or {}).get("apply_standard_terms", True))),
                    "apply_synonym_map": bool(config.get("apply_synonym_map", (compiled.get("dictionary") or {}).get("apply_synonym_map", True))),
                    "apply_near_synonym_map": bool(config.get("apply_near_synonym_map", (compiled.get("dictionary") or {}).get("apply_near_synonym_map", True))),
                    "apply_stopwords": bool(config.get("apply_stopwords", (compiled.get("dictionary") or {}).get("apply_stopwords", True))),
                    "apply_exclusion_terms": bool(config.get("apply_exclusion_terms", (compiled.get("dictionary") or {}).get("apply_exclusion_terms", True))),
                }
                continue

            if node_type == "clean_text":
                compiled["cleaning"] = {**deepcopy(compiled.get("cleaning") or {}), **config}
                if "cleaning" not in enabled_steps:
                    enabled_steps.append("cleaning")
                continue

            if node_type == "normalize_text":
                compiled["normalization"] = {**deepcopy(compiled.get("normalization") or {}), **config}
                if "normalization" not in enabled_steps:
                    enabled_steps.append("normalization")
                continue

            if node_type == "tokenize":
                compiled["tokenization"] = {**deepcopy(compiled.get("tokenization") or {}), **config}
                if "tokenization" not in enabled_steps:
                    enabled_steps.append("tokenization")
                continue

            if node_type == "apply_dictionary_rules":
                compiled["dictionary"] = {**deepcopy(compiled.get("dictionary") or {}), **config}
                if "dictionary_application" not in enabled_steps:
                    enabled_steps.append("dictionary_application")
                continue

            if node_type == "filter_terms":
                compiled["filtering"] = {**deepcopy(compiled.get("filtering") or {}), **config}
                if "filtering" not in enabled_steps:
                    enabled_steps.append("filtering")
                continue

            if node_type == "analyze_corpus":
                compiled["analysis"] = {**deepcopy(compiled.get("analysis") or {}), **config}
                if "analysis" not in enabled_steps:
                    enabled_steps.append("analysis")
                continue

            if node_type == "frequency_statistics":
                compiled["analysis"] = {**deepcopy(compiled.get("analysis") or {}), "top_n": int(config.get("top_n") or (compiled.get("analysis") or {}).get("top_n", 200))}
                if "analysis" not in enabled_steps:
                    enabled_steps.append("analysis")
                continue

            if node_type == "term_year_analysis":
                if "analysis" not in enabled_steps:
                    enabled_steps.append("analysis")
                continue

            if node_type == "cooccurrence_analysis":
                compiled["analysis"] = {
                    **deepcopy(compiled.get("analysis") or {}),
                    "cooccurrence_window": int(config.get("cooccurrence_window") or (compiled.get("analysis") or {}).get("cooccurrence_window", 5)),
                    "min_cooccurrence": int(config.get("min_cooccurrence") or (compiled.get("analysis") or {}).get("min_cooccurrence", 2)),
                }
                if "analysis" not in enabled_steps:
                    enabled_steps.append("analysis")
                continue

            if node_type == "keyword_extraction":
                compiled["analysis"] = {
                    **deepcopy(compiled.get("analysis") or {}),
                    "top_k_per_doc": int(config.get("top_k_per_doc") or (compiled.get("analysis") or {}).get("top_k_per_doc", 10)),
                    "top_k_project": int(config.get("top_k_project") or (compiled.get("analysis") or {}).get("top_k_project", 100)),
                }
                if "analysis" not in enabled_steps:
                    enabled_steps.append("analysis")
                continue

            if node_type == "keyword_clustering":
                compiled["analysis"] = {
                    **deepcopy(compiled.get("analysis") or {}),
                    "keyword_cluster_k": int(config.get("keyword_cluster_k") or (compiled.get("analysis") or {}).get("keyword_cluster_k", 4)),
                    "topic_model_k": int(config.get("topic_model_k") or (compiled.get("analysis") or {}).get("topic_model_k", 4)),
                }
                if "analysis" not in enabled_steps:
                    enabled_steps.append("analysis")
                continue

            if node_type == "institution_topic_analysis":
                compiled["analysis"] = {
                    **deepcopy(compiled.get("analysis") or {}),
                    "topic_model_k": int(config.get("topic_model_k") or (compiled.get("analysis") or {}).get("topic_model_k", 4)),
                }
                if "analysis" not in enabled_steps:
                    enabled_steps.append("analysis")
                continue

            if node_type == "save_csv":
                export_config["export_csv"] = True
                if "export" not in enabled_steps:
                    enabled_steps.append("export")
                continue

            if node_type == "save_xlsx":
                export_config["export_xlsx"] = True
                if "export" not in enabled_steps:
                    enabled_steps.append("export")
                continue

            if node_type == "save_png":
                export_config["export_png"] = True
                export_config["chart_dpi"] = int(config.get("chart_dpi") or export_config.get("chart_dpi", 320))
                if "export" not in enabled_steps:
                    enabled_steps.append("export")
                continue

            if node_type == "save_html_report":
                export_config["export_html_report"] = True
                export_config["include_audit"] = bool(config.get("include_audit", export_config.get("include_audit", True)))
                if "export" not in enabled_steps:
                    enabled_steps.append("export")
                continue

            if node_type == "export_results":
                export_config = {**export_config, **config}
                if "export" not in enabled_steps:
                    enabled_steps.append("export")

        compiled["export"] = export_config

    meta = workflow_definition.get("meta") if isinstance(workflow_definition, dict) else {}
    if isinstance(meta, dict):
        compiled["recipe_id"] = str(meta.get("template_id") or compiled.get("recipe_id") or "standard_analysis")
        compiled["output_bundle_id"] = str(
            meta.get("output_bundle_id") or compiled.get("output_bundle_id") or "full_report"
        )

    compiled["enabled_steps"] = [
        step_id
        for step_id in execution_order
        if step_id == "ingestion" or step_id in enabled_steps
    ]
    compiled["execution_order"] = execution_order
    return compiled


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
    pipeline = default_pipeline()
    workflow = default_workflow_definition(pipeline)
    return {
        "id": f"project-{uuid4().hex[:12]}",
        "schema_version": "2.0.0",
        "name": name,
        "description": description,
        "created_at": timestamp,
        "updated_at": timestamp,
        "version": "0.2.0",
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
        "pipeline": pipeline,
        "workflow_definitions": [workflow],
        "active_workflow_id": workflow["workflow_id"],
        "run_history": [],
        "results": empty_result_bundle(),
    }


def deep_copy_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(manifest)
