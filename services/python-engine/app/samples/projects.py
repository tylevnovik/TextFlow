from __future__ import annotations

import hashlib
import os
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd

from ..domain.common import utc_now_iso
from ..domain.dictionary import make_dictionary_entry
from ..domain.import_profiles import default_import_template
from ..domain.project import default_project_manifest
from ..ingestion import import_files
from ..workflow.templates import build_new_flow_workflow
from ..storage.projects import (
    create_project,
    list_project_dirs,
    load_project,
    project_relative_root,
    save_project,
)
from .seed_sources import (
    SampleSeedSource,
    assert_sample_seed_can_ship,
    default_sample_seed_sources,
)

FIRST_BUILTIN_SAMPLE_PROJECT_NAME = "示例 01 - WoS论文关键词与主题流程"
BUILTIN_SAMPLE_PROJECT_DATA_REVISION = 8
SAMPLE_ROW_LIMIT_ENV_VAR = "TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT"


BUILTIN_SAMPLE_PROJECTS: list[dict[str, Any]] = [
    {
        "order": 1,
        "slug": "sample-01-wos-paper-keyword-topic",
        "name": FIRST_BUILTIN_SAMPLE_PROJECT_NAME,
        "description": (
            "目标：从 WoS 稀土论文导出中形成一份可复现的研究热点、主题结构与年度趋势报告。"
            "处理流程：核对字段映射并拼接题名、摘要和关键词，去重后抽样到可交互规模，执行清洗、标准化、切词和词表归一，"
            "先用词频、特征词和项目级关键词筛掉低价值词项，再用聚焦词项白名单进入共现网络和图计算。"
            "预期结果：输出研究热点关键词表、主题摘要、词项年度趋势、聚焦后的共现网络、图指标，以及带审计记录的 CSV/XLSX/HTML 报告。"
        ),
        "difficulty": "基础",
        "default_row_count": 240,
        "goal": "如何从 WoS 论文导出中形成一份可复现的研究热点、主题结构与趋势报告？",
        "target_outputs": ["研究热点关键词表", "主题摘要", "词项年度趋势", "聚焦后的共现网络", "审计型 HTML 报告"],
        "screening_strategy": ["限定本次语料范围并去重", "按词频与词表规则去噪", "抽取项目级关键词", "仅用关键词白名单构建共现图"],
        "source_profiles": ["wos"],
        "flow_schema_version": "2026-05-new-flow",
        "seed_source_ids": ["wos-rare-earth"],
        "workflow_name": "WoS论文关键词与主题流程",
        "guided_steps": ["核对 WoS 字段映射", "运行清洗、切词和词表规则", "查看关键词、主题、年份趋势、共现网络和导出产物"],
        "covered_nodes": [
            "corpus_input",
            "normalize_metadata",
            "deduplicate_documents",
            "sample_corpus",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "frequency_statistics",
            "term_document_analysis",
            "term_year_analysis",
            "cooccurrence_analysis",
            "similarity_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "focus_terms",
            "keyword_clustering",
            "topic_modeling",
            "document_clustering",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "build_network",
            "graph_metrics",
            "community_detection",
            "main_path_analysis",
            "link_prediction",
            "save_csv",
            "save_xlsx",
            "save_png",
            "save_html_report",
        ],
        "covered_outputs": [
            "keyword_table",
            "topic_summary_table",
            "term_year_table",
            "focus_term_summary",
            "cooccurrence_table",
            "similarity_table",
            "graph_metric_table",
        ],
        "license_note": "Local WoS export seed only unless redistribution is explicitly approved.",
        "dictionary_terms": {
            "custom_lexicon": [("dysprosium", None), ("neodymium", None), ("rare earth", None)],
            "phrase_lexicon": [("rare earth", "rare_earth"), ("critical materials", "critical_materials")],
            "synonym_map": [("REE", "rare_earth"), ("稀土元素", "稀土")],
            "standard_terms": [("rare-earth", "rare_earth"), ("rare earths", "rare_earth")],
            "exclusion_terms": [("study", None), ("analysis", None)],
        },
        "node_config_overrides": {
            "deduplicate_documents": {"dedupe_keys_text": "doc_id,title,year"},
            "sample_corpus": {"sample_size": 180, "seed": 202601},
            "tokenize": {"enable_ngrams": True, "ngram_min": 2, "ngram_max": 2},
            "filter_terms": {"min_term_frequency": 2, "min_token_length": 2},
            "similarity_analysis": {"min_similarity": 0.05, "similarity_top_k": 200},
            "cooccurrence_analysis": {"min_cooccurrence": 2, "cooccurrence_window": 5},
            "feature_term_selection": {"feature_term_count": "100"},
            "keyword_extraction": {"top_k_per_doc": 6, "top_k_project": 60},
            "focus_terms": {"term_source": "keywords", "term_field": "keyword", "max_terms": 8, "project_keywords_only": True},
            "keyword_clustering": {"keyword_cluster_k": 4},
            "topic_modeling": {"topic_model_k": 4, "top_terms_per_topic": 6},
            "document_clustering": {"document_cluster_k": 4},
            "build_network": {"min_edge_weight": 2, "max_edges": 500},
            "link_prediction": {"link_prediction_top_n": 80},
            "save_html_report": {"include_audit": True},
        },
    },
    {
        "order": 2,
        "slug": "sample-02-incopat-patent-technology-graph",
        "name": "示例 02 - IncoPat专利技术识别与图分析",
        "description": (
            "目标：从 IncoPat 稀土专利数据中筛出关键技术词，并形成新兴、核心或衰退技术方向的判断。"
            "处理流程：核对专利题名、摘要、权利要求、申请人和年份字段，去重并抽样到可复现规模，执行专利术语清洗、切词和词表归并，"
            "先抽取项目级关键词控制图节点数量，再只对加权骨干网络运行中心性、社区、主路径、链接预测和技术指标节点。"
            "预期结果：输出技术指标表、技术分类表、关键词聚类、图指标与社区、主路径/链接预测结果，以及可审计的导出报告。"
        ),
        "difficulty": "进阶",
        "default_row_count": 240,
        "goal": "如何从 IncoPat 专利数据中筛出关键技术词，并形成新兴/核心技术判断？",
        "target_outputs": ["技术指标表", "技术分类表", "关键词聚类", "图指标与社区", "主路径和链接预测"],
        "screening_strategy": ["导入后保留可复现样本上限", "按术语词表归并专利技术表达", "用项目级关键词控制图节点规模", "只对加权骨干网络运行图算法"],
        "source_profiles": ["incopat"],
        "flow_schema_version": "2026-05-new-flow",
        "seed_source_ids": ["incopat-rare-earth"],
        "workflow_name": "IncoPat专利技术识别与图分析流程",
        "guided_steps": ["核对专利字段映射", "运行专利文本清洗与术语归并", "查看技术指标、分类、社区、主路径和链接预测"],
        "covered_nodes": [
            "corpus_input",
            "normalize_metadata",
            "deduplicate_documents",
            "sample_corpus",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "frequency_statistics",
            "term_year_analysis",
            "cooccurrence_analysis",
            "similarity_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "focus_terms",
            "keyword_clustering",
            "topic_modeling",
            "build_network",
            "graph_metrics",
            "community_detection",
            "main_path_analysis",
            "link_prediction",
            "technology_indicators",
            "technology_classification",
            "save_csv",
            "save_xlsx",
            "save_png",
            "save_html_report",
        ],
        "covered_outputs": [
            "technology_indicator_table",
            "technology_classification_table",
            "focus_term_summary",
            "similarity_table",
            "community_table",
            "main_path_table",
            "link_prediction_table",
        ],
        "license_note": "Local IncoPat export seed only unless redistribution is explicitly approved.",
        "dictionary_terms": {
            "custom_lexicon": [("separation", None), ("recycling", None), ("adsorption", None)],
            "phrase_lexicon": [("rare earth recovery", "rare_earth_recovery"), ("magnetic material", "magnetic_material")],
            "synonym_map": [("回收利用", "回收"), ("萃取分离", "萃取")],
            "standard_terms": [("neodymium iron boron", "ndfeb"), ("NdFeB", "ndfeb")],
            "exclusion_terms": [("method", None), ("device", None)],
        },
        "node_config_overrides": {
            "deduplicate_documents": {"dedupe_keys_text": "doc_id,title,year"},
            "sample_corpus": {"sample_size": 180, "seed": 202602},
            "tokenize": {"enable_ngrams": True, "ngram_min": 2, "ngram_max": 2},
            "filter_terms": {"min_term_frequency": 2, "min_token_length": 2},
            "similarity_analysis": {"min_similarity": 0.05, "similarity_top_k": 200},
            "cooccurrence_analysis": {"min_cooccurrence": 2, "cooccurrence_window": 6},
            "feature_term_selection": {"feature_term_count": "100"},
            "keyword_extraction": {"top_k_per_doc": 6, "top_k_project": 80},
            "focus_terms": {"term_source": "keywords", "term_field": "keyword", "max_terms": 10, "project_keywords_only": True},
            "keyword_clustering": {"keyword_cluster_k": 5},
            "topic_modeling": {"topic_algorithm": "lda", "topic_model_k": 5, "top_terms_per_topic": 6},
            "build_network": {"min_edge_weight": 2, "max_edges": 800},
            "community_detection": {"community_method": "greedy_modularity"},
            "link_prediction": {"link_prediction_top_n": 120},
            "technology_indicators": {"indicator_current_year": 2026},
            "save_html_report": {"include_audit": True},
        },
    },
    {
        "order": 3,
        "slug": "sample-03-paper-patent-integrated-map",
        "name": "示例 03 - 论文专利融合分析流程",
        "description": (
            "目标：把 WoS 论文和 IncoPat 专利放进同一套可审计流程，判断研究热点与专利技术方向是否正在汇合。"
            "处理流程：分别导入并保留 source profile，统一字段、机构、年份和主文本结构，跨来源去重并抽样到可交互规模，"
            "经过清洗、切词、词表归一、关键词抽取和主题建模后，用聚焦词项白名单生成融合共现图谱，再运行机构关系、图算法和技术分类。"
            "预期结果：输出跨来源机构关键词、机构主题关系、论文-专利融合主题、聚焦共现图谱、技术分类表和带规则审计的 CSV/XLSX/HTML 产物。"
        ),
        "difficulty": "高级",
        "default_row_count": 360,
        "goal": "如何把论文和专利语料放进同一套可审计流程，判断研究热点与专利技术方向是否汇合？",
        "target_outputs": ["跨来源机构关键词", "机构主题热力关系", "论文-专利融合主题", "聚焦共现图谱", "技术分类表"],
        "screening_strategy": ["分别导入后保留 source profile", "跨来源去重并抽样到可交互规模", "词表归一后做关键词抽取", "用关键词白名单生成融合图谱"],
        "source_profiles": ["wos", "incopat"],
        "flow_schema_version": "2026-05-new-flow",
        "seed_source_ids": ["wos-rare-earth", "incopat-rare-earth"],
        "workflow_name": "论文专利融合分析流程",
        "guided_steps": ["确认来源字段和 source_profile", "运行跨来源去重与统一清洗", "查看机构关键词、机构主题、图谱和技术分类"],
        "covered_nodes": [
            "corpus_input",
            "normalize_metadata",
            "deduplicate_documents",
            "sample_corpus",
            "clean_text",
            "normalize_text",
            "tokenize",
            "apply_dictionary_rules",
            "filter_terms",
            "frequency_statistics",
            "term_document_analysis",
            "term_year_analysis",
            "cooccurrence_analysis",
            "similarity_analysis",
            "feature_term_selection",
            "keyword_extraction",
            "focus_terms",
            "keyword_clustering",
            "topic_modeling",
            "document_clustering",
            "institution_keyword_analysis",
            "institution_topic_analysis",
            "build_network",
            "graph_metrics",
            "community_detection",
            "main_path_analysis",
            "link_prediction",
            "technology_indicators",
            "technology_classification",
            "save_csv",
            "save_xlsx",
            "save_png",
            "save_html_report",
        ],
        "covered_outputs": [
            "institution_keyword_table",
            "institution_topic_table",
            "topic_summary_table",
            "focus_term_summary",
            "similarity_table",
            "graph_metric_table",
            "technology_classification_table",
        ],
        "license_note": "Local WoS and IncoPat export seeds only unless redistribution is explicitly approved.",
        "dictionary_terms": {
            "custom_lexicon": [("rare earth", None), ("permanent magnet", None), ("稀土", None)],
            "phrase_lexicon": [("supply chain", "supply_chain"), ("critical mineral", "critical_mineral")],
            "synonym_map": [("NdFeB", "ndfeb"), ("rare earth element", "rare_earth")],
            "standard_terms": [("rare earth elements", "rare_earth"), ("稀土元素", "稀土")],
        },
        "node_config_overrides": {
            "deduplicate_documents": {"dedupe_keys_text": "title,year,source_profile"},
            "sample_corpus": {"sample_size": 260, "seed": 202603},
            "tokenize": {"enable_ngrams": True, "ngram_min": 2, "ngram_max": 2},
            "filter_terms": {"min_term_frequency": 2, "min_token_length": 2},
            "similarity_analysis": {"min_similarity": 0.05, "similarity_top_k": 300},
            "cooccurrence_analysis": {"min_cooccurrence": 2, "cooccurrence_window": 5},
            "feature_term_selection": {"feature_term_count": "100"},
            "keyword_extraction": {"top_k_per_doc": 6, "top_k_project": 100},
            "focus_terms": {"term_source": "keywords", "term_field": "keyword", "max_terms": 14, "project_keywords_only": True},
            "keyword_clustering": {"keyword_cluster_k": 5},
            "topic_modeling": {"topic_model_k": 5, "top_terms_per_topic": 6},
            "document_clustering": {"document_cluster_k": 5},
            "build_network": {"min_edge_weight": 2, "max_edges": 1000},
            "link_prediction": {"link_prediction_top_n": 160},
            "technology_indicators": {"indicator_current_year": 2026},
            "save_html_report": {"include_audit": True},
        },
    },
]

BUILTIN_SAMPLE_PROJECT_BY_SLUG = {
    str(spec["slug"]): spec for spec in BUILTIN_SAMPLE_PROJECTS
}
BUILTIN_SAMPLE_PROJECT_BY_NAME = {
    str(spec["name"]): spec for spec in BUILTIN_SAMPLE_PROJECTS
}
LEGACY_BUILTIN_SAMPLE_SLUGS = {
    "sample-01-basic-preprocessing",
    "sample-02-dictionary-frequency",
    "sample-03-academic-keywords-topics",
    "sample-04-institution-topics",
    "sample-05-review-experiment-incremental",
    "sample-06-multisource-merge-sampling",
    "sample-07-group-compare-keyness",
    "sample-08-split-evaluate-join",
    "sample-09-conditional-routing",
    "sample-10-network-technology",
}


def _builtin_sample_spec_for_manifest(manifest: dict[str, Any]) -> dict[str, Any] | None:
    settings = manifest.get("settings") if isinstance(manifest.get("settings"), dict) else {}
    sample_project = settings.get("sample_project") if isinstance(settings.get("sample_project"), dict) else {}
    slug = str(sample_project.get("slug") or "").strip()
    if slug:
        spec = BUILTIN_SAMPLE_PROJECT_BY_SLUG.get(slug)
        if spec is not None:
            return spec
        if slug in LEGACY_BUILTIN_SAMPLE_SLUGS:
            return BUILTIN_SAMPLE_PROJECTS[0]
    return BUILTIN_SAMPLE_PROJECT_BY_NAME.get(str(manifest.get("name") or ""))


def _is_synthetic_placeholder_row(row: dict[str, Any]) -> bool:
    extra = row.get("extra_metadata") if isinstance(row.get("extra_metadata"), dict) else {}
    return bool(extra.get("synthetic_sample_seed"))


def _sample_row_count(spec: dict[str, Any]) -> int:
    override = os.getenv(SAMPLE_ROW_LIMIT_ENV_VAR)
    if override:
        value = int(override)
    else:
        value = int(spec.get("default_row_count") or 0)
    if value <= 0:
        raise ValueError("Sample row count must be positive")
    return value


def _copy_shipping_metadata(source_file: dict[str, Any], seed: SampleSeedSource, row_count: int) -> dict[str, Any]:
    return {
        **deepcopy(source_file),
        "relative_path": "",
        "retained_in_project": False,
        "row_count": row_count,
        "source_profile": seed.source_profile,
        "seed_id": seed.seed_id,
        "redistribution": seed.redistribution,
        "license_note": seed.redistribution_note,
    }


def _dictionary_table_by_kind(manifest: dict[str, Any], kind: str) -> dict[str, Any]:
    dictionary_set = manifest.setdefault("dictionary_set", {})
    collections = dictionary_set.setdefault("collections", {})
    collection = collections.setdefault(kind, {"kind": kind, "name": kind, "description": "", "tables": []})
    tables = collection.setdefault("tables", [])
    for table in tables:
        if isinstance(table, dict) and str(table.get("id") or "") == f"{kind}-project-custom":
            return table
    table = {
        "id": f"{kind}-project-custom",
        "kind": kind,
        "name": "项目自定义",
        "version": "2.0.0",
        "description": "样例项目内置词表规则。",
        "built_in": False,
        "editable": True,
        "enabled": True,
        "tags": ["sample"],
        "entries": [],
    }
    tables.insert(0, table)
    return table


def _append_dictionary_terms(manifest: dict[str, Any], dictionary_terms: dict[str, list[tuple[str, str | None]]]) -> None:
    if not dictionary_terms:
        return
    for kind, rows in dictionary_terms.items():
        table = _dictionary_table_by_kind(manifest, str(kind))
        entries = table.setdefault("entries", [])
        seen = {
            (str(entry.get("source") or "").casefold(), str(entry.get("target") or "").casefold())
            for entry in entries
            if isinstance(entry, dict)
        }
        for source, target in rows:
            signature = (str(source).casefold(), str(target or "").casefold())
            if signature in seen:
                continue
            entries.append(make_dictionary_entry(str(source), target))
            seen.add(signature)


def _build_workflow_for_spec(spec: dict[str, Any]) -> dict[str, Any]:
    workflow = build_new_flow_workflow(
        f"workflow-{spec['slug']}",
        str(spec["workflow_name"]),
        source_profile=str((spec.get("source_profiles") or ["generic"])[0]),
        include_multisource=len(spec.get("source_profiles") or []) > 1,
        include_patent_graph="incopat" in set(spec.get("source_profiles") or []),
    )
    overrides = spec.get("node_config_overrides") if isinstance(spec.get("node_config_overrides"), dict) else {}
    for node in workflow.get("nodes", []):
        if not isinstance(node, dict):
            continue
        override = overrides.get(str(node.get("node_type") or ""))
        if isinstance(override, dict):
            node["config"] = {
                **(node.get("config") if isinstance(node.get("config"), dict) else {}),
                **deepcopy(override),
            }
    return workflow


def _build_builtin_sample_manifest(
    project_dir: Path,
    spec: dict[str, Any],
    row_count: int,
    source_files: list[dict[str, Any]],
    validation_issues: list[dict[str, Any]],
    existing_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = default_project_manifest(
        str(spec["name"]),
        str(spec["description"]),
        project_relative_root(project_dir),
    )
    if existing_manifest is not None:
        manifest["id"] = str(existing_manifest.get("id") or manifest["id"])
        manifest["created_at"] = str(existing_manifest.get("created_at") or manifest["created_at"])
        existing_settings = existing_manifest.get("settings") if isinstance(existing_manifest.get("settings"), dict) else {}
        for key in [
            "default_language",
            "preferred_theme",
            "enable_auto_save",
            "enable_update_check",
            "default_export_formats",
        ]:
            if key in existing_settings:
                manifest["settings"][key] = deepcopy(existing_settings[key])

    source_profiles = [str(item) for item in spec.get("source_profiles", [])]
    manifest["import_template"] = default_import_template(source_profiles[0] if len(source_profiles) == 1 else "generic")
    manifest["source_files"] = deepcopy(source_files)
    manifest["ingestion_specs"] = [
        {
            "id": f"ingestion-{spec['slug']}",
            "name": f"{spec['name']} 导入记录",
            "created_at": utc_now_iso(),
            "source_profiles": source_profiles,
            "source_file_count": len(source_files),
            "validation_issue_count": len(validation_issues),
            "raw_sources_retained": False,
        }
    ]
    manifest["settings"]["sample_project"] = {
        "order": int(spec["order"]),
        "slug": str(spec["slug"]),
        "data_revision": BUILTIN_SAMPLE_PROJECT_DATA_REVISION,
        "difficulty": str(spec["difficulty"]),
        "goal": str(spec["goal"]),
        "target_outputs": deepcopy(spec.get("target_outputs") or []),
        "screening_strategy": deepcopy(spec.get("screening_strategy") or []),
        "workflow_name": str(spec["workflow_name"]),
        "guided_steps": deepcopy(spec.get("guided_steps") or []),
        "covered_nodes": deepcopy(spec.get("covered_nodes") or []),
        "covered_outputs": deepcopy(spec.get("covered_outputs") or []),
        "default_row_count": int(spec["default_row_count"]),
        "public_row_count": row_count,
        "source_profiles": source_profiles,
        "seed_source_ids": deepcopy(spec.get("seed_source_ids") or []),
        "flow_schema_version": str(spec["flow_schema_version"]),
        "raw_sources_retained": False,
        "license_note": str(spec.get("license_note") or ""),
    }
    workflow = _build_workflow_for_spec(spec)
    manifest["workflow_definitions"] = [workflow]
    manifest["active_workflow_id"] = workflow["workflow_id"]
    _append_dictionary_terms(manifest, deepcopy(spec.get("dictionary_terms") or {}))
    return manifest


def _clear_directory_contents(path: Path) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _reset_builtin_sample_project_storage(project_dir: Path) -> None:
    for relative_path in [
        "metadata/sample_seed",
        "corpus/imported",
        "runs",
        "cache",
        "exports",
    ]:
        _clear_directory_contents(project_dir / relative_path)


def _row_limit_for_seed(seed: SampleSeedSource, spec: dict[str, Any], total_row_count: int) -> int:
    seed_ids = list(spec.get("seed_source_ids") or [])
    if len(seed_ids) <= 1:
        return total_row_count
    return max(1, total_row_count // len(seed_ids))


def _import_seed_rows(
    project_dir: Path,
    seed: SampleSeedSource,
    row_limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    template = default_import_template(seed.source_profile)
    corpus, source_files, issues = import_files([seed.path], template, project_dir=None)
    if row_limit > 0:
        corpus = corpus[:row_limit]
    for row in corpus:
        row["source_profile"] = seed.source_profile
        row.setdefault("extra_metadata", {})
        if isinstance(row["extra_metadata"], dict):
            row["extra_metadata"]["_source_relative_path"] = ""
            row["extra_metadata"]["_source_file_name"] = seed.path.name
            row["extra_metadata"]["sample_seed_id"] = seed.seed_id
            row["extra_metadata"]["sample_seed_profile"] = seed.source_profile
    source_file = source_files[0] if source_files else {
        "id": f"source-{seed.seed_id}-{hashlib.md5(str(seed.path).encode('utf-8')).hexdigest()[:8]}",
        "name": seed.path.name,
        "source_type": seed.path.suffix.lower().lstrip("."),
        "relative_path": "",
        "imported_at": utc_now_iso(),
        "row_count": len(corpus),
    }
    return corpus, _copy_shipping_metadata(source_file, seed, len(corpus)), issues


def _seed_source_by_id(sources: list[SampleSeedSource]) -> dict[str, SampleSeedSource]:
    return {source.seed_id: source for source in sources}


def _ensure_required_seed_sources(spec: dict[str, Any], sources: list[SampleSeedSource]) -> list[SampleSeedSource]:
    lookup = _seed_source_by_id(sources)
    required_ids = [str(seed_id) for seed_id in spec.get("seed_source_ids", [])]
    missing = [seed_id for seed_id in required_ids if seed_id not in lookup]
    if missing:
        raise FileNotFoundError(
            "Missing built-in sample seed source(s): "
            + ", ".join(missing)
            + ". Set TEXTFLOW_SAMPLE_WOS_SOURCE and TEXTFLOW_SAMPLE_INCOPAT_SOURCE, "
            "or use scripts/build-bundled-sample-workspace.ps1 with -WosSeed/-IncopatSeed."
        )
    return [lookup[seed_id] for seed_id in required_ids]


def _materialize_builtin_sample_project(
    project_dir: Path,
    spec: dict[str, Any],
    *,
    existing_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row_count = _sample_row_count(spec)
    seeds = _ensure_required_seed_sources(spec, default_sample_seed_sources())
    _reset_builtin_sample_project_storage(project_dir)

    corpus: list[dict[str, Any]] = []
    source_files: list[dict[str, Any]] = []
    validation_issues: list[dict[str, Any]] = []
    seen_doc_ids: set[str] = set()
    for seed in seeds:
        assert_sample_seed_can_ship(seed)
        seed_corpus, source_file, issues = _import_seed_rows(project_dir, seed, _row_limit_for_seed(seed, spec, row_count))
        for row in seed_corpus:
            doc_id = str(row.get("doc_id") or row.get("id") or "")
            if doc_id in seen_doc_ids:
                row["doc_id"] = f"{seed.source_profile}:{doc_id}"
                row["id"] = row["doc_id"]
            seen_doc_ids.add(str(row.get("doc_id") or ""))
            corpus.append(row)
        source_files.append(source_file)
        validation_issues.extend(issues)

    manifest = _build_builtin_sample_manifest(project_dir, spec, len(corpus), source_files, validation_issues, existing_manifest)
    save_project(project_dir, manifest, corpus)
    _clear_directory_contents(project_dir / "corpus" / "imported")
    if (project_dir / "metadata" / "sample_seed").exists():
        shutil.rmtree(project_dir / "metadata" / "sample_seed")
    return load_project(project_dir)[0]


def _builtin_sample_project_requires_refresh(
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    spec: dict[str, Any],
) -> bool:
    sample_project = (
        manifest.get("settings", {}).get("sample_project", {})
        if isinstance(manifest.get("settings"), dict)
        else {}
    )
    if not isinstance(sample_project, dict):
        return True
    if sample_project.get("slug") != spec["slug"]:
        return True
    if int(sample_project.get("data_revision") or 0) < BUILTIN_SAMPLE_PROJECT_DATA_REVISION:
        return True
    if not corpus:
        return True
    if any(_is_synthetic_placeholder_row(row) for row in corpus[:10]):
        return True
    source_files = manifest.get("source_files") if isinstance(manifest.get("source_files"), list) else []
    if any(str(source.get("relative_path") or "") for source in source_files if isinstance(source, dict)):
        return True
    return False


def create_builtin_sample_projects() -> list[tuple[Path, dict[str, Any]]]:
    created: list[tuple[Path, dict[str, Any]]] = []
    for spec in BUILTIN_SAMPLE_PROJECTS:
        project_dir, manifest = create_project(str(spec["name"]), str(spec["description"]))
        created.append((project_dir, _materialize_builtin_sample_project(project_dir, spec, existing_manifest=manifest)))
    return created


def reconcile_builtin_sample_projects(*, create_missing: bool = True) -> list[tuple[Path, dict[str, Any]]]:
    reconciled: list[tuple[Path, dict[str, Any]]] = []
    existing_by_slug: dict[str, list[tuple[Path, dict[str, Any], list[dict[str, Any]]]]] = {}
    legacy_matches: list[tuple[Path, dict[str, Any], list[dict[str, Any]]]] = []

    for project_dir in list_project_dirs():
        manifest, corpus = load_project(project_dir)
        spec = _builtin_sample_spec_for_manifest(manifest)
        if spec is None:
            continue
        sample_project = (
            manifest.get("settings", {}).get("sample_project", {})
            if isinstance(manifest.get("settings"), dict)
            else {}
        )
        slug = str(sample_project.get("slug") or spec["slug"])
        if slug in LEGACY_BUILTIN_SAMPLE_SLUGS:
            legacy_matches.append((project_dir, manifest, corpus))
            continue
        existing_by_slug.setdefault(slug, []).append((project_dir, manifest, corpus))

    if legacy_matches:
        legacy_matches.sort(key=lambda item: str(item[1].get("created_at") or item[0].name))
        existing_by_slug.setdefault(str(BUILTIN_SAMPLE_PROJECTS[0]["slug"]), []).append(legacy_matches[0])
        for project_dir, _manifest, _corpus in legacy_matches[1:]:
            shutil.rmtree(project_dir, ignore_errors=True)

    effective_create_missing = create_missing or bool(existing_by_slug)

    for spec in BUILTIN_SAMPLE_PROJECTS:
        matches = existing_by_slug.get(str(spec["slug"]), [])
        if not matches and effective_create_missing:
            project_dir, manifest = create_project(str(spec["name"]), str(spec["description"]))
            reconciled.append((project_dir, _materialize_builtin_sample_project(project_dir, spec, existing_manifest=manifest)))
            continue
        if not matches:
            continue
        for project_dir, manifest, corpus in matches:
            if _builtin_sample_project_requires_refresh(manifest, corpus, spec):
                manifest = _materialize_builtin_sample_project(project_dir, spec, existing_manifest=manifest)
            reconciled.append((project_dir, manifest))

    return reconciled
