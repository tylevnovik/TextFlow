from __future__ import annotations

import hashlib
import json
import math
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd

from .defaults import default_import_template, make_dictionary_entry, utc_now_iso
from .experiment_store import save_experiment_spec
from .node_definitions import build_builtin_node_definitions
from .project_store import create_project, save_project
from .review_store import create_review_task
from .sample_dataset_cache import ensure_public_sample_cache_available, read_normalized_sample_cache, sample_data_cache_root

FIRST_BUILTIN_SAMPLE_PROJECT_NAME = "示例 01 - 基础文本预处理"
NODE_DEFINITION_BY_TYPE = {
    definition["type"]: definition for definition in build_builtin_node_definitions()
}


def _source_spec(
    filename: str,
    file_format: str,
    dataset_id: str,
    language: str,
    selector: str,
    ratio: float,
) -> dict[str, Any]:
    return {
        "filename": filename,
        "format": file_format,
        "dataset_id": dataset_id,
        "language": language,
        "selector": selector,
        "ratio": ratio,
    }


BUILTIN_SAMPLE_PROJECTS: list[dict[str, Any]] = [
    {
        "order": 1,
        "slug": "sample-01-basic-preprocessing",
        "name": FIRST_BUILTIN_SAMPLE_PROJECT_NAME,
        "description": "使用真实公开百科文本演示清洗、标准化、切词与导出。",
        "difficulty": "基础",
        "default_row_count": 20_000,
        "goal": "我有一批杂乱文本，如何清洗、标准化、切词并导出？",
        "guided_steps": ["查看样例说明与审计来源", "运行清洗与标准化节点", "检查切词结果并导出 HTML 报告"],
        "covered_nodes": ["corpus_input", "dictionary_input", "clean_text", "normalize_text", "tokenize", "apply_dictionary_rules", "filter_terms", "frequency_statistics", "save_csv", "save_html_report", "note", "group"],
        "covered_settings": ["strip_html", "normalize_whitespace", "case_mode", "language_mode"],
        "public_data_only": True,
        "language_balance": {"en": 0.5, "zh": 0.5},
        "source_datasets": ["wikimedia_enwiki", "wikimedia_zhwiki"],
        "source_profile": "generic",
        "sources": [
            _source_spec("basic_preprocessing_en.csv", "csv", "wikimedia_enwiki", "en", "sample_01_basic_en", 0.5),
            _source_spec("basic_preprocessing_zh.csv", "csv", "wikimedia_zhwiki", "zh", "sample_01_basic_zh", 0.5),
        ],
        "workflow_name": "基础文本预处理工作流",
        "import_template_overrides": {"text_build": {"mode": "concat_fields", "fields": ["raw_text"], "delimiter": "\n\n", "skip_empty": True}},
        "node_config_overrides": {"clean_text": {"strip_html": True}, "normalize_text": {"normalize_whitespace": True}, "save_html_report": {"include_audit": True}},
        "dictionary_terms": {"phrase_lexicon": [("text mining", "text_mining"), ("自然语言处理", "自然语言处理")]},
        "review_tasks": [],
        "experiment_specs": [],
    },
    {
        "order": 2,
        "slug": "sample-02-dictionary-frequency",
        "name": "示例 02 - 词表治理与词频统计",
        "description": "使用真实公开双语语料演示术语保留、同义词统一、噪声过滤与高频词统计。",
        "difficulty": "基础",
        "default_row_count": 10_000,
        "goal": "如何保留行业术语、统一同义词、过滤噪声并看高频词？",
        "guided_steps": ["查看词表资源与覆盖范围", "叠加词表规则后运行词频", "检查共现与词项-文档关系"],
        "covered_nodes": ["corpus_input", "dictionary_input", "select_dictionary_tables", "overlay_dictionary_rules", "clean_text", "normalize_text", "tokenize", "apply_dictionary_rules", "filter_terms", "frequency_statistics", "term_document_analysis", "cooccurrence_analysis", "save_xlsx", "save_html_report", "note", "group"],
        "covered_settings": ["selected_tables", "overlay_rows_text", "min_term_frequency", "cooccurrence_window"],
        "public_data_only": True,
        "language_balance": {"en": 0.5, "zh": 0.5},
        "source_datasets": ["un_parallel_en_zh"],
        "source_profile": "generic",
        "sources": [
            _source_spec("dictionary_frequency_en.csv", "csv", "un_parallel_en_zh", "en", "sample_02_dictionary_en", 0.5),
            _source_spec("dictionary_frequency_zh.csv", "csv", "un_parallel_en_zh", "zh", "sample_02_dictionary_zh", 0.5),
        ],
        "workflow_name": "词表治理与词频统计工作流",
        "import_template_overrides": {"text_build": {"mode": "concat_fields", "fields": ["raw_text"], "delimiter": "\n\n", "skip_empty": True}},
        "node_config_overrides": {"cooccurrence_analysis": {"cooccurrence_window": 4}, "save_html_report": {"include_audit": True}},
        "dictionary_terms": {"phrase_lexicon": [("climate finance", "climate_finance"), ("可持续发展", "可持续发展")], "synonym_map": [("llm", "large language model"), ("人工智能", "人工智能")]},
        "review_tasks": [],
        "experiment_specs": [],
    },
    {
        "order": 3,
        "slug": "sample-03-academic-keywords-topics",
        "name": "示例 03 - 学术摘要关键词与主题",
        "description": "使用 OpenAlex 双语摘要演示关键词、主题、时间趋势与文档聚类。",
        "difficulty": "进阶",
        "default_row_count": 10_000,
        "goal": "如何从论文摘要中找关键词、主题和时间趋势？",
        "guided_steps": ["查看摘要语料与年份字段", "运行关键词提取与主题建模", "对照主题与时间趋势导出图表"],
        "covered_nodes": ["corpus_input", "dictionary_input", "clean_text", "normalize_text", "tokenize", "apply_dictionary_rules", "filter_terms", "term_document_analysis", "term_year_analysis", "feature_term_selection", "keyword_extraction", "keyword_clustering", "topic_modeling", "document_clustering", "save_xlsx", "save_png", "save_html_report", "note", "group"],
        "covered_settings": ["feature_term_count", "top_k_project", "topic_model_k", "document_cluster_k"],
        "public_data_only": True,
        "language_balance": {"en": 0.5, "zh": 0.5},
        "source_datasets": ["openalex_works"],
        "source_profile": "literature",
        "sources": [
            _source_spec("academic_topics_en.xlsx", "xlsx", "openalex_works", "en", "sample_03_openalex_en", 0.5),
            _source_spec("academic_topics_zh.xlsx", "xlsx", "openalex_works", "zh", "sample_03_openalex_zh", 0.5),
        ],
        "workflow_name": "学术关键词与主题工作流",
        "import_template_overrides": {"text_build": {"mode": "concat_fields", "fields": ["raw_text"], "delimiter": "\n\n", "skip_empty": True}},
        "node_config_overrides": {"feature_term_selection": {"feature_term_count": 120}, "keyword_clustering": {"keyword_cluster_k": 6}, "topic_modeling": {"topic_model_k": 6}},
        "dictionary_terms": {"phrase_lexicon": [("large language model", "large_language_model"), ("机器学习", "机器学习")]},
        "review_tasks": [],
        "experiment_specs": [],
    },
    {
        "order": 4,
        "slug": "sample-04-institution-topics",
        "name": "示例 04 - 机构主题与技术方向",
        "description": "使用 OpenAlex 双语摘要比较机构、关键词、主题与年份关系。",
        "difficulty": "进阶",
        "default_row_count": 10_000,
        "goal": "如何比较机构、关键词和主题之间的关系？",
        "guided_steps": ["先按机构与年份查看分布", "运行机构关键词与机构主题分析", "导出图表并核对来源归属"],
        "covered_nodes": ["corpus_input", "dictionary_input", "filter_by_metadata", "bucket_by_time", "clean_text", "normalize_text", "tokenize", "apply_dictionary_rules", "filter_terms", "term_year_analysis", "feature_term_selection", "keyword_extraction", "institution_keyword_analysis", "institution_topic_analysis", "save_xlsx", "save_png", "save_html_report", "note", "group"],
        "covered_settings": ["metadata_field", "bucket_unit", "feature_term_count", "topic_model_k"],
        "public_data_only": True,
        "language_balance": {"en": 0.5, "zh": 0.5},
        "source_datasets": ["openalex_works"],
        "source_profile": "literature",
        "sources": [
            _source_spec("institution_topics_en.xlsx", "xlsx", "openalex_works", "en", "sample_04_institution_en", 0.5),
            _source_spec("institution_topics_zh.xlsx", "xlsx", "openalex_works", "zh", "sample_04_institution_zh", 0.5),
        ],
        "workflow_name": "机构主题与技术方向工作流",
        "import_template_overrides": {"text_build": {"mode": "concat_fields", "fields": ["raw_text"], "delimiter": "\n\n", "skip_empty": True}},
        "node_config_overrides": {"institution_topic_analysis": {"topic_model_k": 5}, "save_html_report": {"include_audit": True}},
        "dictionary_terms": {"phrase_lexicon": [("research policy", "research_policy"), ("技术路线", "技术路线")]},
        "review_tasks": [],
        "experiment_specs": [],
    },
    {
        "order": 5,
        "slug": "sample-05-review-experiment-incremental",
        "name": "示例 05 - 复核实验与增量运行",
        "description": "使用联合国语料演示规则复核、实验对比与增量运行的基本场景。",
        "difficulty": "高级",
        "default_row_count": 10_000,
        "goal": "如何复核结果、调参比较，并只重跑变更文档？",
        "guided_steps": ["先运行基线词表规则", "查看复核与实验入口", "对比增量运行前后的差异"],
        "covered_nodes": ["corpus_input", "dictionary_input", "overlay_dictionary_rules", "clean_text", "normalize_text", "tokenize", "apply_dictionary_rules", "filter_terms", "keyword_extraction", "keyword_clustering", "save_html_report", "note", "group"],
        "covered_settings": ["overlay_rows_text", "top_k_project", "keyword_cluster_k", "incremental_mode"],
        "public_data_only": True,
        "language_balance": {"en": 0.5, "zh": 0.5},
        "source_datasets": ["un_parallel_en_zh"],
        "source_profile": "generic",
        "sources": [
            _source_spec("review_experiment_en.json", "json", "un_parallel_en_zh", "en", "sample_05_review_en", 0.5),
            _source_spec("review_experiment_zh.json", "json", "un_parallel_en_zh", "zh", "sample_05_review_zh", 0.5),
        ],
        "workflow_name": "复核实验与增量运行工作流",
        "import_template_overrides": {"text_build": {"mode": "concat_fields", "fields": ["raw_text"], "delimiter": "\n\n", "skip_empty": True}},
        "node_config_overrides": {"keyword_extraction": {"top_k_project": 80}, "keyword_clustering": {"keyword_cluster_k": 5}},
        "dictionary_terms": {"phrase_lexicon": [("peacekeeping mission", "peacekeeping_mission"), ("国际合作", "国际合作")]},
        "review_tasks": [],
        "experiment_specs": [],
    },
    {
        "order": 6,
        "slug": "sample-06-multisource-merge-sampling",
        "name": "示例 06 - 多来源语料合并与抽样",
        "description": "使用百科与 OpenAlex 双语公开语料演示多来源合并、去重、抽样与多格式 seed 文件。",
        "difficulty": "进阶",
        "default_row_count": 10_000,
        "goal": "如何合并 CSV/XLSX/JSON/TXT，多来源去重和抽样？",
        "guided_steps": ["检查四种输入格式的 seed 文件", "运行合并、去重与抽样节点", "查看共现统计与导出图表"],
        "covered_nodes": ["corpus_input", "dictionary_input", "merge_corpora", "filter_by_metadata", "deduplicate_documents", "sample_corpus", "clean_text", "normalize_text", "tokenize", "apply_dictionary_rules", "filter_terms", "frequency_statistics", "cooccurrence_analysis", "save_csv", "save_png", "save_html_report", "note", "group"],
        "covered_settings": ["dedupe_key", "sample_size", "sample_seed", "metadata_field"],
        "public_data_only": True,
        "language_balance": {"en": 0.5, "zh": 0.5},
        "source_datasets": ["wikimedia_enwiki", "wikimedia_zhwiki", "openalex_works"],
        "source_profile": "generic",
        "sources": [
            _source_spec("multisource_en.csv", "csv", "wikimedia_enwiki", "en", "sample_06_csv_en", 0.25),
            _source_spec("multisource_zh.xlsx", "xlsx", "wikimedia_zhwiki", "zh", "sample_06_xlsx_zh", 0.25),
            _source_spec("multisource_openalex_en.json", "json", "openalex_works", "en", "sample_06_json_en", 0.25),
            _source_spec("multisource_openalex_zh.txt", "txt", "openalex_works", "zh", "sample_06_txt_zh", 0.25),
        ],
        "workflow_name": "多来源合并与抽样工作流",
        "import_template_overrides": {"text_build": {"mode": "concat_fields", "fields": ["raw_text"], "delimiter": "\n\n", "skip_empty": True}},
        "node_config_overrides": {"cooccurrence_analysis": {"cooccurrence_window": 5}, "save_html_report": {"include_audit": True}},
        "dictionary_terms": {"phrase_lexicon": [("knowledge graph", "knowledge_graph"), ("主题聚类", "主题聚类")]},
        "review_tasks": [],
        "experiment_specs": [],
    },
    {
        "order": 7,
        "slug": "sample-07-group-compare-keyness",
        "name": "示例 07 - 分组比较与关键性分析",
        "description": "使用 OpenAlex 双语数据演示分组比较、关键性分析与时间切片。",
        "difficulty": "高级",
        "default_row_count": 10_000,
        "goal": "如何比较不同时间、机构或产品线的关键词差异？",
        "guided_steps": ["按年份或机构建立分组", "运行组间比较与 keyness", "对照频率和时间趋势图"],
        "covered_nodes": ["corpus_input", "dictionary_input", "filter_by_metadata", "bucket_by_time", "clean_text", "normalize_text", "tokenize", "apply_dictionary_rules", "filter_terms", "frequency_statistics", "term_year_analysis", "group_compare", "keyness_analysis", "save_csv", "save_png", "save_html_report", "note", "group"],
        "covered_settings": ["group_field", "comparison_mode", "keyness_metric", "bucket_unit"],
        "public_data_only": True,
        "language_balance": {"en": 0.5, "zh": 0.5},
        "source_datasets": ["openalex_works"],
        "source_profile": "literature",
        "sources": [
            _source_spec("group_compare_en.csv", "csv", "openalex_works", "en", "sample_07_group_en", 0.5),
            _source_spec("group_compare_zh.csv", "csv", "openalex_works", "zh", "sample_07_group_zh", 0.5),
        ],
        "workflow_name": "分组比较与关键性分析工作流",
        "import_template_overrides": {"text_build": {"mode": "concat_fields", "fields": ["raw_text"], "delimiter": "\n\n", "skip_empty": True}},
        "node_config_overrides": {"keyness_analysis": {"keyness_metric": "log_likelihood"}, "save_html_report": {"include_audit": True}},
        "dictionary_terms": {"phrase_lexicon": [("policy diffusion", "policy_diffusion"), ("对比分析", "对比分析")]},
        "review_tasks": [],
        "experiment_specs": [],
    },
    {
        "order": 8,
        "slug": "sample-08-split-evaluate-join",
        "name": "示例 08 - 切分评估与结果拼接",
        "description": "使用双语百科文本演示语料切分、聚类评估与结果拼接。",
        "difficulty": "高级",
        "default_row_count": 10_000,
        "goal": "如何切分语料、建模、评估聚类并拼接结果？",
        "guided_steps": ["切分语料并观察样本差异", "运行主题建模与聚类评估", "拼接结果后导出表格和图表"],
        "covered_nodes": ["corpus_input", "dictionary_input", "split_corpus", "clean_text", "normalize_text", "tokenize", "apply_dictionary_rules", "filter_terms", "topic_modeling", "cluster_evaluation", "join_results", "document_clustering", "save_csv", "save_xlsx", "save_png", "save_html_report", "note", "group"],
        "covered_settings": ["split_ratio", "topic_model_k", "document_cluster_k", "evaluation_metric"],
        "public_data_only": True,
        "language_balance": {"en": 0.5, "zh": 0.5},
        "source_datasets": ["wikimedia_enwiki", "wikimedia_zhwiki"],
        "source_profile": "generic",
        "sources": [
            _source_spec("split_evaluate_en.json", "json", "wikimedia_enwiki", "en", "sample_08_split_en", 0.5),
            _source_spec("split_evaluate_zh.json", "json", "wikimedia_zhwiki", "zh", "sample_08_split_zh", 0.5),
        ],
        "workflow_name": "切分评估与结果拼接工作流",
        "import_template_overrides": {"text_build": {"mode": "concat_fields", "fields": ["raw_text"], "delimiter": "\n\n", "skip_empty": True}},
        "node_config_overrides": {"cluster_evaluation": {"evaluation_metric": "silhouette"}, "topic_modeling": {"topic_model_k": 5}},
        "dictionary_terms": {"phrase_lexicon": [("semantic search", "semantic_search"), ("结果拼接", "结果拼接")]},
        "review_tasks": [],
        "experiment_specs": [],
    },
    {
        "order": 9,
        "slug": "sample-09-conditional-routing",
        "name": "示例 09 - 条件路由与人工门禁",
        "description": "使用联合国语料与 OpenAlex 双语数据演示条件路由、结果门禁与人工复核入口。",
        "difficulty": "高级",
        "default_row_count": 10_000,
        "goal": "如何用条件、指标门禁和人工复核控制工作流？",
        "guided_steps": ["检查路由条件与门禁阈值", "运行主流程并观察门禁结果", "进入人工复核后查看审计记录"],
        "covered_nodes": ["corpus_input", "dictionary_input", "conditional_router", "result_gate", "manual_review_gate", "clean_text", "normalize_text", "tokenize", "apply_dictionary_rules", "filter_terms", "save_html_report", "note", "group"],
        "covered_settings": ["condition_expression", "gate_metric", "gate_threshold", "review_task_id"],
        "public_data_only": True,
        "language_balance": {"en": 0.5, "zh": 0.5},
        "source_datasets": ["un_parallel_en_zh", "openalex_works"],
        "source_profile": "generic",
        "sources": [
            _source_spec("conditional_router_en.csv", "csv", "un_parallel_en_zh", "en", "sample_09_router_en", 0.25),
            _source_spec("conditional_router_zh.csv", "csv", "un_parallel_en_zh", "zh", "sample_09_router_zh", 0.25),
            _source_spec("conditional_router_openalex_en.json", "json", "openalex_works", "en", "sample_09_openalex_en", 0.25),
            _source_spec("conditional_router_openalex_zh.json", "json", "openalex_works", "zh", "sample_09_openalex_zh", 0.25),
        ],
        "workflow_name": "条件路由与人工门禁工作流",
        "import_template_overrides": {"text_build": {"mode": "concat_fields", "fields": ["raw_text"], "delimiter": "\n\n", "skip_empty": True}},
        "node_config_overrides": {"result_gate": {"gate_threshold": 0.6}, "save_html_report": {"include_audit": True}},
        "dictionary_terms": {"phrase_lexicon": [("human review", "human_review"), ("质量门禁", "质量门禁")]},
        "review_tasks": [],
        "experiment_specs": [],
    },
]


def _append_dictionary_terms(manifest: dict[str, Any], dictionary_terms: dict[str, list[tuple[str, str | None]]]) -> None:
    for kind, rows in dictionary_terms.items():
        sheet = manifest["dictionary_set"]["sheets"].get(kind)
        if not isinstance(sheet, dict):
            continue
        existing_sources = {str(entry.get("source") or "").casefold() for entry in sheet.get("entries", [])}
        for source, target in rows:
            if str(source).casefold() in existing_sources:
                continue
            sheet["entries"].append(make_dictionary_entry(source, target, 0))


def _node_by_type(workflow: dict[str, Any], node_type: str) -> dict[str, Any]:
    for node in workflow.get("nodes", []):
        if isinstance(node, dict) and str(node.get("node_type") or "") == node_type:
            return node
    raise KeyError(f"Workflow node not found for type: {node_type}")


def _default_node_config(node_type: str) -> dict[str, Any]:
    definition = NODE_DEFINITION_BY_TYPE[node_type]
    return {
        str(param.get("param_id")): deepcopy(param.get("default_value"))
        for param in definition.get("params", [])
        if isinstance(param, dict) and str(param.get("param_id") or "").strip()
    }


def _new_registry_node(node_type: str, node_id: str, config: dict[str, Any], *, x: int, y: int) -> dict[str, Any]:
    definition = NODE_DEFINITION_BY_TYPE[node_type]
    return {
        "node_id": node_id,
        "node_type": node_type,
        "label": str(definition.get("title") or node_type),
        "position": {"x": x, "y": y},
        "size": {"w": 230, "h": 190},
        "inputs": deepcopy(definition.get("inputs") or []),
        "outputs": deepcopy(definition.get("outputs") or []),
        "config": {**_default_node_config(node_type), **deepcopy(config)},
        "ui_state": {"collapsed": False, "bypassed": False},
        "runtime_meta": {
            "step_id": str(definition.get("category") or "manual"),
            "node_impl_version": "2.0.0",
        },
    }


def _input_allows_multiple(node: dict[str, Any], port_id: str) -> bool:
    for port in node.get("inputs", []):
        if isinstance(port, dict) and str(port.get("port_id") or "") == port_id:
            return bool(port.get("allow_multiple"))
    return False


def _connect(workflow: dict[str, Any], from_node: str, from_port: str, to_node: str, to_port: str) -> None:
    node_lookup = {str(node.get("node_id") or ""): node for node in workflow.get("nodes", []) if isinstance(node, dict)}
    target = node_lookup[to_node]
    next_edges = [
        edge
        for edge in workflow.get("edges", [])
        if not (
            str(edge.get("from_node") or "") == from_node
            and str(edge.get("from_port") or "") == from_port
            and str(edge.get("to_node") or "") == to_node
            and str(edge.get("to_port") or "") == to_port
        )
    ]
    if not _input_allows_multiple(target, to_port):
        next_edges = [
            edge
            for edge in next_edges
            if not (
                str(edge.get("to_node") or "") == to_node
                and str(edge.get("to_port") or "") == to_port
            )
        ]
    next_edges.append(
        {
            "edge_id": f"edge-{from_node}-{from_port}-to-{to_node}-{to_port}",
            "from_node": from_node,
            "from_port": from_port,
            "to_node": to_node,
            "to_port": to_port,
        }
    )
    workflow["edges"] = next_edges


def _bypass_node_types(workflow: dict[str, Any], node_types: set[str]) -> None:
    for node in workflow.get("nodes", []):
        if not isinstance(node, dict):
            continue
        if str(node.get("node_type") or "") in node_types:
            node.setdefault("ui_state", {})
            node["ui_state"]["bypassed"] = True


def _keep_only_nodes(workflow: dict[str, Any], node_types: set[str]) -> None:
    workflow["nodes"] = [
        node
        for node in workflow.get("nodes", [])
        if isinstance(node, dict) and str(node.get("node_type") or "") in node_types
    ]
    kept_ids = {str(node.get("node_id") or "") for node in workflow["nodes"]}
    workflow["edges"] = [
        edge
        for edge in workflow.get("edges", [])
        if str(edge.get("from_node") or "") in kept_ids and str(edge.get("to_node") or "") in kept_ids
    ]


def _apply_node_config(workflow: dict[str, Any], node_type: str, config: dict[str, Any]) -> None:
    node = _node_by_type(workflow, node_type)
    node["config"] = {**dict(node.get("config") or {}), **deepcopy(config)}


def _add_note_and_group(workflow: dict[str, Any], *, group_title: str, note_text: str, x: int = 40, y: int = 40) -> None:
    workflow["nodes"].append(_new_registry_node("group", f"group-{group_title}", {"title": group_title}, x=x, y=y))
    workflow["nodes"].append(_new_registry_node("note", f"note-{group_title}", {"text": note_text}, x=x + 24, y=y + 28))


def _configure_basic_preprocessing_workflow(workflow: dict[str, Any]) -> None:
    workflow["source"] = "manual"
    workflow["name"] = "基础文本预处理工作流"
    _keep_only_nodes(
        workflow,
        {
            "corpus_input",
            "dictionary_input",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "frequency_statistics",
            "save_csv",
            "save_html_report",
        },
    )
    workflow["edges"] = []
    _add_note_and_group(workflow, group_title="示例 01", note_text="从项目语料进入清洗、标准化、切词和词频导出。")
    _apply_node_config(workflow, "clean_text", {"strip_html": True, "strip_urls": True, "normalize_whitespace": True})
    _apply_node_config(workflow, "normalize_text", {"case_mode": "lower", "normalize_numbers": True})
    _apply_node_config(workflow, "tokenize", {"language_mode": "mixed"})
    _connect(workflow, "node-corpus-input", "corpus", "node-clean-text", "corpus_in")
    _connect(workflow, "node-clean-text", "clean_corpus", "node-normalize-text", "corpus_in")
    _connect(workflow, "node-normalize-text", "normalized_corpus", "node-tokenize", "corpus_in")
    _connect(workflow, "node-tokenize", "token_corpus", "node-apply-dictionary-rules", "token_corpus_in")
    _connect(workflow, "node-dictionary-input", "dictionary_set", "node-apply-dictionary-rules", "dictionary_set_in")
    _connect(workflow, "node-apply-dictionary-rules", "token_corpus", "node-filter-terms", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-frequency-statistics", "token_corpus_in")
    _connect(workflow, "node-frequency-statistics", "frequency_table", "node-save-csv", "table_in")
    _connect(workflow, "node-frequency-statistics", "frequency_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-apply-dictionary-rules", "audit_table", "node-save-html-report", "report_in")


def _configure_dictionary_frequency_workflow(workflow: dict[str, Any]) -> None:
    workflow["source"] = "manual"
    workflow["name"] = "词表治理与词频统计工作流"
    _keep_only_nodes(
        workflow,
        {
            "corpus_input",
            "dictionary_input",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "frequency_statistics",
            "term_document_analysis",
            "cooccurrence_analysis",
            "save_xlsx",
            "save_html_report",
        },
    )
    workflow["nodes"].extend(
        [
            _new_registry_node("select_dictionary_tables", "node-select-dictionary-tables", {"selected_table_ids_text": "phrase_lexicon\nsynonym_map\nstopwords\nstandard_terms"}, x=420, y=80),
            _new_registry_node("overlay_dictionary_rules", "node-overlay-dictionary-rules", {"overlay_rows_text": "standard_terms|llm|large language model|true\nstandard_terms|人工智能|人工智能|true"}, x=760, y=80),
        ]
    )
    workflow["edges"] = []
    _add_note_and_group(workflow, group_title="示例 02", note_text="先挑词表，再叠加临时规则，最后看词频、词项-文档和共现。")
    _apply_node_config(workflow, "cooccurrence_analysis", {"cooccurrence_window": 4, "min_cooccurrence": 2})
    _connect(workflow, "node-corpus-input", "corpus", "node-clean-text", "corpus_in")
    _connect(workflow, "node-clean-text", "clean_corpus", "node-normalize-text", "corpus_in")
    _connect(workflow, "node-normalize-text", "normalized_corpus", "node-tokenize", "corpus_in")
    _connect(workflow, "node-tokenize", "token_corpus", "node-apply-dictionary-rules", "token_corpus_in")
    _connect(workflow, "node-dictionary-input", "dictionary_set", "node-select-dictionary-tables", "dictionary_set_in")
    _connect(workflow, "node-select-dictionary-tables", "dictionary_set", "node-overlay-dictionary-rules", "dictionary_set_in")
    _connect(workflow, "node-overlay-dictionary-rules", "dictionary_set", "node-apply-dictionary-rules", "dictionary_set_in")
    _connect(workflow, "node-apply-dictionary-rules", "token_corpus", "node-filter-terms", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-frequency-statistics", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-term-document-analysis", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-cooccurrence-analysis", "token_corpus_in")
    _connect(workflow, "node-frequency-statistics", "frequency_table", "node-save-xlsx", "table_in")
    _connect(workflow, "node-term-document-analysis", "term_document_table", "node-save-xlsx", "table_in")
    _connect(workflow, "node-cooccurrence-analysis", "cooccurrence_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-frequency-statistics", "frequency_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-term-document-analysis", "term_document_table", "node-save-html-report", "report_in")


def _configure_academic_keyword_topic_workflow(workflow: dict[str, Any]) -> None:
    workflow["source"] = "manual"
    workflow["name"] = "学术关键词与主题工作流"
    _keep_only_nodes(
        workflow,
        {
            "corpus_input",
            "dictionary_input",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "term_document_analysis",
            "term_year_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "keyword_clustering",
            "topic_modeling",
            "document_clustering",
            "save_xlsx",
            "save_png",
            "save_html_report",
        },
    )
    workflow["nodes"].append(_new_registry_node("topic_modeling", "node-topic-modeling", {"topic_model_k": 6, "top_terms_per_topic": 8}, x=3240, y=860))
    workflow["edges"] = []
    _add_note_and_group(workflow, group_title="示例 03", note_text="围绕学术摘要同时跑关键词、主题、文档聚类和年份趋势。")
    _apply_node_config(workflow, "feature_term_selection", {"feature_term_count": 120})
    _apply_node_config(workflow, "keyword_extraction", {"top_k_per_doc": 8, "top_k_project": 80})
    _apply_node_config(workflow, "keyword_clustering", {"keyword_cluster_k": 6})
    _apply_node_config(workflow, "document_clustering", {"document_cluster_k": 6})
    _connect(workflow, "node-corpus-input", "corpus", "node-clean-text", "corpus_in")
    _connect(workflow, "node-clean-text", "clean_corpus", "node-normalize-text", "corpus_in")
    _connect(workflow, "node-normalize-text", "normalized_corpus", "node-tokenize", "corpus_in")
    _connect(workflow, "node-tokenize", "token_corpus", "node-apply-dictionary-rules", "token_corpus_in")
    _connect(workflow, "node-dictionary-input", "dictionary_set", "node-apply-dictionary-rules", "dictionary_set_in")
    _connect(workflow, "node-apply-dictionary-rules", "token_corpus", "node-filter-terms", "token_corpus_in")
    for target in ["node-term-document-analysis", "node-term-year-analysis", "node-feature-term-selection", "node-keyword-extraction", "node-topic-modeling", "node-document-clustering"]:
        _connect(workflow, "node-filter-terms", "filtered_token_corpus", target, "token_corpus_in")
    _connect(workflow, "node-feature-term-selection", "feature_term_table", "node-keyword-clustering", "feature_term_table_in")
    _connect(workflow, "node-keyword-extraction", "keyword_table", "node-save-xlsx", "table_in")
    _connect(workflow, "node-term-document-analysis", "term_document_table", "node-save-xlsx", "table_in")
    _connect(workflow, "node-topic-modeling", "document_topic_table", "node-save-xlsx", "table_in")
    _connect(workflow, "node-term-year-analysis", "term_year_table", "node-save-png", "render_in")
    _connect(workflow, "node-keyword-clustering", "keyword_cluster_table", "node-save-png", "render_in")
    _connect(workflow, "node-document-clustering", "document_cluster_table", "node-save-png", "render_in")
    _connect(workflow, "node-topic-modeling", "topic_summary_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-keyword-extraction", "keyword_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-keyword-clustering", "keyword_cluster_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-term-year-analysis", "term_year_table", "node-save-html-report", "report_in")


def _configure_institution_topic_workflow(workflow: dict[str, Any]) -> None:
    workflow["source"] = "manual"
    workflow["name"] = "机构主题与技术方向工作流"
    _keep_only_nodes(
        workflow,
        {
            "corpus_input",
            "dictionary_input",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "term_year_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "save_xlsx",
            "save_png",
            "save_html_report",
        },
    )
    workflow["nodes"].extend(
        [
            _new_registry_node("filter_by_metadata", "node-filter-by-metadata", {"field": "language", "operator": "in", "values": ["en", "zh"]}, x=420, y=330),
            _new_registry_node("bucket_by_time", "node-bucket-by-time", {"field": "year", "granularity": "year"}, x=420, y=620),
            _new_registry_node("keyword_clustering", "node-keyword-clustering-extra", {"keyword_cluster_k": 5}, x=3000, y=860),
        ]
    )
    workflow["edges"] = []
    _add_note_and_group(workflow, group_title="示例 04", note_text="先过滤元数据和时间桶，再分析机构关键词与机构主题。")
    _apply_node_config(workflow, "feature_term_selection", {"feature_term_count": 100})
    _apply_node_config(workflow, "keyword_extraction", {"top_k_per_doc": 8, "top_k_project": 60})
    _apply_node_config(workflow, "institution_topic_analysis", {"topic_model_k": 5})
    _connect(workflow, "node-corpus-input", "corpus", "node-filter-by-metadata", "corpus_in")
    _connect(workflow, "node-filter-by-metadata", "filtered_corpus", "node-bucket-by-time", "corpus_in")
    _connect(workflow, "node-filter-by-metadata", "filtered_corpus", "node-clean-text", "corpus_in")
    _connect(workflow, "node-clean-text", "clean_corpus", "node-normalize-text", "corpus_in")
    _connect(workflow, "node-normalize-text", "normalized_corpus", "node-tokenize", "corpus_in")
    _connect(workflow, "node-tokenize", "token_corpus", "node-apply-dictionary-rules", "token_corpus_in")
    _connect(workflow, "node-dictionary-input", "dictionary_set", "node-apply-dictionary-rules", "dictionary_set_in")
    _connect(workflow, "node-apply-dictionary-rules", "token_corpus", "node-filter-terms", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-term-year-analysis", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-feature-term-selection", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-keyword-extraction", "token_corpus_in")
    _connect(workflow, "node-feature-term-selection", "feature_term_table", "node-keyword-clustering-extra", "feature_term_table_in")
    _connect(workflow, "node-keyword-extraction", "keyword_table", "node-institution-keyword-analysis", "keyword_table_in")
    _connect(workflow, "node-keyword-clustering-extra", "keyword_cluster_table", "node-institution-topic-analysis", "keyword_cluster_table_in")
    _connect(workflow, "node-institution-keyword-analysis", "institution_keyword_table", "node-save-xlsx", "table_in")
    _connect(workflow, "node-institution-topic-analysis", "institution_topic_table", "node-save-xlsx", "table_in")
    _connect(workflow, "node-term-year-analysis", "term_year_table", "node-save-png", "render_in")
    _connect(workflow, "node-institution-topic-analysis", "institution_topic_table", "node-save-png", "render_in")
    _connect(workflow, "node-bucket-by-time", "time_bucket_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-institution-keyword-analysis", "institution_keyword_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-institution-topic-analysis", "institution_topic_table", "node-save-html-report", "report_in")


def _configure_review_experiment_incremental_workflow(workflow: dict[str, Any]) -> None:
    workflow["source"] = "manual"
    workflow["name"] = "复核实验与增量运行工作流"
    _keep_only_nodes(
        workflow,
        {
            "corpus_input",
            "dictionary_input",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "keyword_extraction",
            "keyword_clustering",
            "save_html_report",
        },
    )
    workflow["nodes"].extend(
        [
            _new_registry_node("overlay_dictionary_rules", "node-overlay-dictionary-rules", {"overlay_rows_text": "standard_terms|复核|复核|true"}, x=760, y=80),
            _new_registry_node("feature_term_selection", "node-feature-term-selection-extra", {"feature_term_count": 80}, x=2860, y=80),
        ]
    )
    workflow["edges"] = []
    _add_note_and_group(workflow, group_title="示例 05", note_text="这个流程把规则叠加、关键词聚类和后续复核/实验入口放在一起。")
    _apply_node_config(workflow, "keyword_extraction", {"top_k_per_doc": 6, "top_k_project": 60})
    _connect(workflow, "node-corpus-input", "corpus", "node-clean-text", "corpus_in")
    _connect(workflow, "node-clean-text", "clean_corpus", "node-normalize-text", "corpus_in")
    _connect(workflow, "node-normalize-text", "normalized_corpus", "node-tokenize", "corpus_in")
    _connect(workflow, "node-tokenize", "token_corpus", "node-apply-dictionary-rules", "token_corpus_in")
    _connect(workflow, "node-dictionary-input", "dictionary_set", "node-overlay-dictionary-rules", "dictionary_set_in")
    _connect(workflow, "node-overlay-dictionary-rules", "dictionary_set", "node-apply-dictionary-rules", "dictionary_set_in")
    _connect(workflow, "node-apply-dictionary-rules", "token_corpus", "node-filter-terms", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-feature-term-selection-extra", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-keyword-extraction", "token_corpus_in")
    _connect(workflow, "node-feature-term-selection-extra", "feature_term_table", "node-keyword-clustering", "feature_term_table_in")
    _connect(workflow, "node-keyword-extraction", "keyword_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-keyword-clustering", "keyword_cluster_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-apply-dictionary-rules", "audit_table", "node-save-html-report", "report_in")


def _configure_multisource_merge_sampling_workflow(workflow: dict[str, Any], spec: dict[str, Any]) -> None:
    workflow["source"] = "manual"
    workflow["name"] = "多来源合并与抽样工作流"
    _keep_only_nodes(
        workflow,
        {
            "corpus_input",
            "dictionary_input",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "frequency_statistics",
            "cooccurrence_analysis",
            "save_csv",
            "save_png",
            "save_html_report",
        },
    )
    filter_nodes = []
    positions = [(420, 120), (420, 340), (420, 560), (420, 780)]
    for index, (source, (x, y)) in enumerate(zip(spec["sources"], positions, strict=True), start=1):
        filter_nodes.append(
            _new_registry_node(
                "filter_by_metadata",
                f"node-filter-source-{index}",
                {"field": "_source_file_name", "operator": "in", "values_text": str(source["filename"])},
                x=x,
                y=y,
            )
        )
    workflow["nodes"].extend(
        filter_nodes
        + [
            _new_registry_node("merge_corpora", "node-merge-corpora", {"strategy": "append"}, x=820, y=420),
            _new_registry_node("deduplicate_documents", "node-deduplicate-documents", {"dedupe_keys_text": "title,language", "strategy": "first"}, x=1160, y=420),
            _new_registry_node("sample_corpus", "node-sample-corpus", {"sample_mode": "sample_ratio", "sample_ratio": 0.8, "sample_size": 100, "seed": 42}, x=1520, y=420),
        ]
    )
    workflow["edges"] = []
    _add_note_and_group(workflow, group_title="示例 06", note_text="从多个 seed 文件筛出子集后合并、去重、抽样，再做统计和导出。")
    _apply_node_config(workflow, "cooccurrence_analysis", {"cooccurrence_window": 5, "min_cooccurrence": 2})
    for index in range(1, len(spec["sources"]) + 1):
        _connect(workflow, "node-corpus-input", "corpus", f"node-filter-source-{index}", "corpus_in")
        _connect(workflow, f"node-filter-source-{index}", "filtered_corpus", "node-merge-corpora", "corpus_in")
    _connect(workflow, "node-merge-corpora", "corpus", "node-deduplicate-documents", "corpus_in")
    _connect(workflow, "node-deduplicate-documents", "deduped_corpus", "node-sample-corpus", "corpus_in")
    _connect(workflow, "node-sample-corpus", "sampled_corpus", "node-clean-text", "corpus_in")
    _connect(workflow, "node-clean-text", "clean_corpus", "node-normalize-text", "corpus_in")
    _connect(workflow, "node-normalize-text", "normalized_corpus", "node-tokenize", "corpus_in")
    _connect(workflow, "node-tokenize", "token_corpus", "node-apply-dictionary-rules", "token_corpus_in")
    _connect(workflow, "node-dictionary-input", "dictionary_set", "node-apply-dictionary-rules", "dictionary_set_in")
    _connect(workflow, "node-apply-dictionary-rules", "token_corpus", "node-filter-terms", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-frequency-statistics", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-cooccurrence-analysis", "token_corpus_in")
    _connect(workflow, "node-frequency-statistics", "frequency_table", "node-save-csv", "table_in")
    _connect(workflow, "node-cooccurrence-analysis", "cooccurrence_table", "node-save-csv", "table_in")
    _connect(workflow, "node-cooccurrence-analysis", "cooccurrence_table", "node-save-png", "render_in")
    _connect(workflow, "node-frequency-statistics", "frequency_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-cooccurrence-analysis", "cooccurrence_table", "node-save-html-report", "report_in")


def _configure_group_compare_keyness_workflow(workflow: dict[str, Any]) -> None:
    workflow["source"] = "manual"
    workflow["name"] = "分组比较与关键性分析工作流"
    _keep_only_nodes(
        workflow,
        {
            "corpus_input",
            "dictionary_input",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "frequency_statistics",
            "term_year_analysis",
            "save_csv",
            "save_png",
            "save_html_report",
        },
    )
    workflow["nodes"].extend(
        [
            _new_registry_node("filter_by_metadata", "node-filter-by-metadata", {"field": "language", "operator": "in", "values": ["en", "zh"]}, x=420, y=330),
            _new_registry_node("bucket_by_time", "node-bucket-by-time", {"field": "year", "granularity": "year"}, x=420, y=620),
            _new_registry_node("group_compare", "node-group-compare", {"group_field": "language", "baseline_group": "en", "comparison_groups_text": "zh", "min_frequency": 2}, x=2860, y=600),
            _new_registry_node("keyness_analysis", "node-keyness-analysis", {"group_field": "language", "baseline_group": "en", "comparison_group": "zh", "min_frequency": 2}, x=3240, y=600),
        ]
    )
    workflow["edges"] = []
    _add_note_and_group(workflow, group_title="示例 07", note_text="先固定分组条件，再比较不同组的高频词、时间趋势和关键性。")
    _connect(workflow, "node-corpus-input", "corpus", "node-filter-by-metadata", "corpus_in")
    _connect(workflow, "node-filter-by-metadata", "filtered_corpus", "node-bucket-by-time", "corpus_in")
    _connect(workflow, "node-filter-by-metadata", "filtered_corpus", "node-clean-text", "corpus_in")
    _connect(workflow, "node-clean-text", "clean_corpus", "node-normalize-text", "corpus_in")
    _connect(workflow, "node-normalize-text", "normalized_corpus", "node-tokenize", "corpus_in")
    _connect(workflow, "node-tokenize", "token_corpus", "node-apply-dictionary-rules", "token_corpus_in")
    _connect(workflow, "node-dictionary-input", "dictionary_set", "node-apply-dictionary-rules", "dictionary_set_in")
    _connect(workflow, "node-apply-dictionary-rules", "token_corpus", "node-filter-terms", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-frequency-statistics", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-term-year-analysis", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-group-compare", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-keyness-analysis", "token_corpus_in")
    _connect(workflow, "node-group-compare", "group_metric_table", "node-save-csv", "table_in")
    _connect(workflow, "node-keyness-analysis", "keyness_table", "node-save-csv", "table_in")
    _connect(workflow, "node-term-year-analysis", "term_year_table", "node-save-png", "render_in")
    _connect(workflow, "node-keyness-analysis", "keyness_table", "node-save-png", "render_in")
    _connect(workflow, "node-bucket-by-time", "time_bucket_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-frequency-statistics", "frequency_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-group-compare", "group_metric_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-keyness-analysis", "keyness_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-apply-dictionary-rules", "audit_table", "node-save-html-report", "report_in")


def _configure_split_evaluate_join_workflow(workflow: dict[str, Any]) -> None:
    workflow["source"] = "manual"
    workflow["name"] = "切分评估与结果拼接工作流"
    _keep_only_nodes(
        workflow,
        {
            "corpus_input",
            "dictionary_input",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "document_clustering",
            "save_csv",
            "save_xlsx",
            "save_png",
            "save_html_report",
        },
    )
    workflow["nodes"].extend(
        [
            _new_registry_node("split_corpus", "node-split-corpus", {"split_strategy": "ratio", "splits_text": "train:0.7\ntest:0.3", "seed": 42}, x=420, y=620),
            _new_registry_node("topic_modeling", "node-topic-modeling", {"topic_model_k": 5, "top_terms_per_topic": 6}, x=2860, y=80),
            _new_registry_node("cluster_evaluation", "node-cluster-evaluation", {}, x=3240, y=340),
            _new_registry_node("join_results", "node-join-results", {"join_keys_text": "doc_id", "join_type": "left"}, x=3240, y=620),
        ]
    )
    workflow["edges"] = []
    _add_note_and_group(workflow, group_title="示例 08", note_text="切分语料后，同时看主题结果、聚类评估，再把表格拼回一起导出。")
    _apply_node_config(workflow, "document_clustering", {"document_cluster_k": 5})
    _connect(workflow, "node-corpus-input", "corpus", "node-split-corpus", "corpus_in")
    _connect(workflow, "node-corpus-input", "corpus", "node-clean-text", "corpus_in")
    _connect(workflow, "node-clean-text", "clean_corpus", "node-normalize-text", "corpus_in")
    _connect(workflow, "node-normalize-text", "normalized_corpus", "node-tokenize", "corpus_in")
    _connect(workflow, "node-tokenize", "token_corpus", "node-apply-dictionary-rules", "token_corpus_in")
    _connect(workflow, "node-dictionary-input", "dictionary_set", "node-apply-dictionary-rules", "dictionary_set_in")
    _connect(workflow, "node-apply-dictionary-rules", "token_corpus", "node-filter-terms", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-topic-modeling", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-document-clustering", "token_corpus_in")
    _connect(workflow, "node-document-clustering", "document_cluster_table", "node-cluster-evaluation", "document_cluster_table_in")
    _connect(workflow, "node-topic-modeling", "document_topic_table", "node-join-results", "left_table_in")
    _connect(workflow, "node-document-clustering", "document_cluster_table", "node-join-results", "right_table_in")
    _connect(workflow, "node-join-results", "joined_table", "node-save-csv", "table_in")
    _connect(workflow, "node-cluster-evaluation", "cluster_evaluation_table", "node-save-xlsx", "table_in")
    _connect(workflow, "node-join-results", "joined_table", "node-save-xlsx", "table_in")
    _connect(workflow, "node-topic-modeling", "topic_summary_table", "node-save-png", "render_in")
    _connect(workflow, "node-split-corpus", "split_assignment_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-cluster-evaluation", "cluster_evaluation_table", "node-save-html-report", "report_in")
    _connect(workflow, "node-join-results", "joined_table", "node-save-html-report", "report_in")


def _configure_control_gate_workflow(workflow: dict[str, Any]) -> None:
    workflow["source"] = "manual"
    workflow["name"] = "条件路由与人工门禁工作流"
    _keep_only_nodes(
        workflow,
        {
            "corpus_input",
            "dictionary_input",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "frequency_statistics",
            "save_html_report",
        },
    )
    workflow["nodes"].extend(
        [
            _new_registry_node("conditional_router", "node-conditional-router", {"source_kind": "table_field", "field": "document_count", "operator": "gte", "values_text": "1"}, x=3240, y=80),
            _new_registry_node("result_gate", "node-result-gate", {"metric_field": "matched_count", "metric_name": "matched_count", "operator": "gte", "threshold": 1}, x=3620, y=80),
            _new_registry_node("manual_review_gate", "node-manual-review-gate", {"review_id": "sample-09-review", "required_status": "resolved", "on_missing": "pass"}, x=4000, y=80),
        ]
    )
    workflow["edges"] = []
    _add_note_and_group(workflow, group_title="示例 09", note_text="先路由，再按指标门禁，最后把结果交给人工复核门禁。")
    _connect(workflow, "node-corpus-input", "corpus", "node-clean-text", "corpus_in")
    _connect(workflow, "node-clean-text", "clean_corpus", "node-normalize-text", "corpus_in")
    _connect(workflow, "node-normalize-text", "normalized_corpus", "node-tokenize", "corpus_in")
    _connect(workflow, "node-tokenize", "token_corpus", "node-apply-dictionary-rules", "token_corpus_in")
    _connect(workflow, "node-dictionary-input", "dictionary_set", "node-apply-dictionary-rules", "dictionary_set_in")
    _connect(workflow, "node-apply-dictionary-rules", "token_corpus", "node-filter-terms", "token_corpus_in")
    _connect(workflow, "node-filter-terms", "filtered_token_corpus", "node-frequency-statistics", "token_corpus_in")
    _connect(workflow, "node-frequency-statistics", "frequency_table", "node-conditional-router", "table_in")
    _connect(workflow, "node-conditional-router", "route_summary", "node-result-gate", "metric_table_in")
    _connect(workflow, "node-conditional-router", "matched_table", "node-result-gate", "payload_in")
    _connect(workflow, "node-result-gate", "passed_table", "node-manual-review-gate", "payload_in")
    _connect(workflow, "node-conditional-router", "route_summary", "node-save-html-report", "report_in")
    _connect(workflow, "node-result-gate", "gate_summary", "node-save-html-report", "report_in")
    _connect(workflow, "node-manual-review-gate", "review_gate_summary", "node-save-html-report", "report_in")


def _configure_workflow_for_spec(manifest: dict[str, Any], spec: dict[str, Any]) -> None:
    workflow = manifest["workflow_definitions"][0]
    slug = str(spec["slug"])
    if slug == "sample-01-basic-preprocessing":
        _configure_basic_preprocessing_workflow(workflow)
    elif slug == "sample-02-dictionary-frequency":
        _configure_dictionary_frequency_workflow(workflow)
    elif slug == "sample-03-academic-keywords-topics":
        _configure_academic_keyword_topic_workflow(workflow)
    elif slug == "sample-04-institution-topics":
        _configure_institution_topic_workflow(workflow)
    elif slug == "sample-05-review-experiment-incremental":
        _configure_review_experiment_incremental_workflow(workflow)
    elif slug == "sample-06-multisource-merge-sampling":
        _configure_multisource_merge_sampling_workflow(workflow, spec)
    elif slug == "sample-07-group-compare-keyness":
        _configure_group_compare_keyness_workflow(workflow)
    elif slug == "sample-08-split-evaluate-join":
        _configure_split_evaluate_join_workflow(workflow)
    elif slug == "sample-09-conditional-routing":
        _configure_control_gate_workflow(workflow)
    else:
        raise ValueError(f"Unknown sample project workflow slug: {slug}")

    for node in workflow.get("nodes", []):
        patch = dict(spec.get("node_config_overrides") or {}).get(str(node.get("node_type")))
        if patch:
            node["config"] = {**dict(node.get("config") or {}), **patch}


def _seed_review_and_experiment_surfaces(manifest: dict[str, Any], spec: dict[str, Any], corpus: list[dict[str, Any]]) -> None:
    slug = str(spec["slug"])

    if slug == "sample-05-review-experiment-incremental":
        if not manifest.get("review_tasks"):
            create_review_task(
                manifest,
                review_type="keyword_merge",
                target_ref={"source_term": "llm", "target_term": "large language model"},
                title="合并关键词 llm",
                description="把缩写 llm 统一到标准术语 large language model。",
                payload={
                    "dictionary_kind": "standard_terms",
                    "source_term": "llm",
                    "target_term": "large language model",
                },
            )
            target_doc = str(corpus[0].get("doc_id") or "sample-doc-1") if corpus else "sample-doc-1"
            create_review_task(
                manifest,
                review_type="document_patch",
                target_ref={"doc_id": target_doc},
                title=f"修订文档 {target_doc}",
                description="补充机构字段并确认摘要内容是否需要人工修订。",
                payload={
                    "doc_id": target_doc,
                    "patch": {"institution": "示例复核机构"},
                },
            )
        if not manifest.get("experiment_specs"):
            save_experiment_spec(
                manifest,
                {
                    "name": "关键词提取阈值对比",
                    "variant_matrix": [
                        {
                            "label": "baseline keyword extraction",
                            "node_overrides": {
                                "node-keyword-extraction": {"top_k_per_doc": 6, "top_k_project": 60},
                                "node-keyword-clustering": {"keyword_cluster_k": 4},
                            },
                        },
                        {
                            "label": "stricter keyword extraction",
                            "node_overrides": {
                                "node-keyword-extraction": {"top_k_per_doc": 4, "top_k_project": 40},
                                "node-keyword-clustering": {"keyword_cluster_k": 6},
                            },
                        },
                    ],
                },
            )
        return

    if slug == "sample-09-conditional-routing":
        existing_tasks = manifest.get("review_tasks") if isinstance(manifest.get("review_tasks"), list) else []
        review_task = existing_tasks[0] if existing_tasks else None
        if review_task is None:
            target_doc = str(corpus[0].get("doc_id") or "sample-doc-1") if corpus else "sample-doc-1"
            review_task = create_review_task(
                manifest,
                review_type="document_patch",
                target_ref={"doc_id": target_doc},
                title="人工门禁复核任务",
                description="确认条件路由放行的文档是否满足人工复核标准。",
                payload={"doc_id": target_doc},
            )
        gate_node = _node_by_type(manifest["workflow_definitions"][0], "manual_review_gate")
        gate_node["config"] = {
            **dict(gate_node.get("config") or {}),
            "review_id": str(review_task.get("review_id") or ""),
            "required_status": "resolved",
            "on_missing": "block",
        }


def _sample_row_count(spec: dict[str, Any]) -> int:
    override = os.getenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT")
    if override:
        row_count = int(override)
    else:
        row_count = int(spec.get("default_row_count") or 10_000)
    if row_count < 2 or row_count % 2:
        raise ValueError("Sample row count must be an even number so en/zh rows stay 1:1")
    return row_count


def _allocate_counts(sources: list[dict[str, Any]], target_total: int) -> list[int]:
    if target_total == 0:
        return [0 for _ in sources]

    ratios = [max(float(source.get("ratio", 0.0) or 0.0), 0.0) for source in sources]
    ratio_total = sum(ratios)
    if ratio_total <= 0:
        ratios = [1.0 for _ in sources]
        ratio_total = float(len(sources))

    exact_counts = [(target_total * ratio) / ratio_total for ratio in ratios]
    counts = [math.floor(value) for value in exact_counts]
    remainder = target_total - sum(counts)
    ranked = sorted(
        enumerate(exact_counts),
        key=lambda item: (item[1] - math.floor(item[1]), -item[0]),
        reverse=True,
    )
    for index, _value in ranked[:remainder]:
        counts[index] += 1
    return counts


def _exportable_source_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exported: list[dict[str, Any]] = []
    for row in rows:
        exported.append(
            {
                "doc_id": row.get("doc_id"),
                "language": row.get("language"),
                "title": row.get("title"),
                "raw_text": row.get("raw_text"),
                "year": row.get("year"),
                "source": row.get("source"),
                "institution": row.get("institution"),
                "category_or_tag": row.get("category_or_tag"),
                "keyword_field": row.get("keyword_field"),
                "source_profile": row.get("source_profile"),
                "extra_metadata_json": json.dumps(row.get("extra_metadata") or {}, ensure_ascii=False, sort_keys=True),
            }
        )
    return exported


def _write_rows_to_source_file(path: Path, file_format: str, rows: list[dict[str, Any]]) -> None:
    export_rows = _exportable_source_rows(rows)
    format_name = file_format.lower()
    if format_name == "csv":
        pd.DataFrame(export_rows).to_csv(path, index=False, encoding="utf-8-sig")
        return
    if format_name == "xlsx":
        pd.DataFrame(export_rows).to_excel(path, index=False)
        return
    if format_name == "json":
        path.write_text(json.dumps(export_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    if format_name == "txt":
        path.write_text("\n".join(str(row.get("raw_text") or "").replace("\r", " ").replace("\n", " ") for row in rows), encoding="utf-8")
        return
    raise ValueError(f"Unsupported sample source format: {file_format}")


def _sample_seed_dir(project_dir: Path) -> Path:
    seed_dir = project_dir / "metadata" / "sample_seed"
    seed_dir.mkdir(parents=True, exist_ok=True)
    return seed_dir


def _source_file_record(project_dir: Path, path: Path, row_count: int) -> dict[str, Any]:
    relative_path = path.relative_to(project_dir).as_posix()
    digest = hashlib.md5(relative_path.encode("utf-8")).hexdigest()[:8]
    return {
        "id": f"source-{path.stem}-{digest}",
        "name": path.name,
        "source_type": path.suffix.lower().lstrip("."),
        "relative_path": relative_path,
        "imported_at": utc_now_iso(),
        "row_count": row_count,
    }


def _load_cache_rows(dataset_id: str, language: str, selector: str | None) -> list[dict[str, Any]]:
    cache_rows = read_normalized_sample_cache(sample_data_cache_root(), dataset_id, selector=selector)
    return [deepcopy(row) for row in cache_rows if str(row.get("language") or "") == language]


def _materialize_sample_sources(project_dir: Path, spec: dict[str, Any], row_count: int) -> tuple[list[Path], list[dict[str, Any]], list[dict[str, Any]]]:
    ensure_public_sample_cache_available(spec["source_datasets"])
    indexed_sources = list(enumerate(spec["sources"]))
    sources_by_language: dict[str, list[tuple[int, dict[str, Any]]]] = {"en": [], "zh": []}
    for index, source in indexed_sources:
        language = str(source.get("language") or "")
        if language not in sources_by_language:
            raise ValueError(f"Unsupported sample source language: {language}")
        sources_by_language[language].append((index, source))

    source_payloads: dict[int, dict[str, Any]] = {}
    per_language_target = row_count // 2
    cache_pools: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    cache_offsets: dict[tuple[str, str, str], int] = {}

    for language in ("en", "zh"):
        language_sources = sources_by_language[language]
        allocations = _allocate_counts([source for _index, source in language_sources], per_language_target)
        for (index, source), requested_count in zip(language_sources, allocations, strict=True):
            dataset_id = str(source["dataset_id"])
            selector = str(source.get("selector") or "")
            key = (dataset_id, language, selector)
            rows = cache_pools.setdefault(key, _load_cache_rows(dataset_id, language, selector or None))
            start = cache_offsets.get(key, 0)
            end = start + requested_count
            if len(rows) < end:
                raise ValueError(
                    f"Not enough real rows for dataset={dataset_id} language={language} selector={selector!r}: "
                    f"requested={requested_count} available={max(len(rows) - start, 0)}"
                )
            cache_offsets[key] = end
            selected_rows: list[dict[str, Any]] = []
            for row in rows[start:end]:
                materialized = deepcopy(row)
                materialized["source_profile"] = str(spec["source_profile"])
                selected_rows.append(materialized)
            source_payloads[index] = {"source": source, "rows": selected_rows}

    seed_dir = _sample_seed_dir(project_dir)
    written_paths: list[Path] = []
    corpus: list[dict[str, Any]] = []
    source_files: list[dict[str, Any]] = []

    for index, source in indexed_sources:
        payload = source_payloads[index]
        rows = payload["rows"]
        path = seed_dir / str(source["filename"])
        _write_rows_to_source_file(path, str(source["format"]), rows)
        written_paths.append(path)
        source_files.append(_source_file_record(project_dir, path, len(rows)))
        relative_path = path.relative_to(project_dir).as_posix()
        for row_index, row in enumerate(rows, start=1):
            extra_metadata = dict(row.get("extra_metadata") or {})
            extra_metadata["_source_relative_path"] = relative_path
            extra_metadata["_source_file_name"] = path.name
            extra_metadata["_source_row_index"] = row_index
            row["extra_metadata"] = extra_metadata
            corpus.append(row)

    return written_paths, corpus, source_files


def _write_sample_sources(project_dir: Path, spec: dict[str, Any], row_count: int) -> list[Path]:
    written_paths, _corpus, _source_files = _materialize_sample_sources(project_dir, spec, row_count)
    return written_paths


def create_builtin_sample_projects() -> list[tuple[Path, dict[str, Any]]]:
    created: list[tuple[Path, dict[str, Any]]] = []

    for spec in BUILTIN_SAMPLE_PROJECTS:
        row_count = _sample_row_count(spec)
        project_dir, manifest = create_project(str(spec["name"]), str(spec["description"]))
        manifest["import_template"] = default_import_template(str(spec["source_profile"]))
        manifest["import_template"] = {
            **manifest["import_template"],
            **deepcopy(spec.get("import_template_overrides") or {}),
        }
        manifest.setdefault("settings", {})
        manifest["settings"]["sample_project"] = {
            "order": spec["order"],
            "slug": spec["slug"],
            "difficulty": spec["difficulty"],
            "goal": spec["goal"],
            "workflow_name": spec["workflow_name"],
            "guided_steps": deepcopy(spec["guided_steps"]),
            "covered_nodes": deepcopy(spec["covered_nodes"]),
            "covered_settings": deepcopy(spec["covered_settings"]),
            "default_row_count": spec["default_row_count"],
            "public_row_count": row_count,
            "public_data_only": True,
            "language_balance": deepcopy(spec["language_balance"]),
            "language_counts": {"en": row_count // 2, "zh": row_count // 2},
            "estimated_runtime": str(spec.get("estimated_runtime") or ""),
            "dataset": deepcopy(spec.get("dataset") or {"source_datasets": deepcopy(spec["source_datasets"])}),
            "source_datasets": deepcopy(spec["source_datasets"]),
        }
        manifest["review_tasks"] = deepcopy(spec.get("review_tasks") or [])
        manifest["experiment_specs"] = deepcopy(spec.get("experiment_specs") or [])
        _append_dictionary_terms(manifest, deepcopy(spec.get("dictionary_terms") or {}))
        _configure_workflow_for_spec(manifest, spec)

        _written_paths, corpus, source_files = _materialize_sample_sources(project_dir, spec, row_count)
        manifest["source_files"] = source_files
        _seed_review_and_experiment_surfaces(manifest, spec, corpus)
        save_project(project_dir, manifest, corpus)
        created.append((project_dir, manifest))

    return created
