from __future__ import annotations

from copy import deepcopy
from hashlib import md5
import json
import threading
import time
from typing import Any
from uuid import uuid4

from app.analysis import (
    institution_keyword_and_topic,
    nmf_topic_model,
    parallel_yake_worker_count,
    tfidf_analysis,
    yake_keyword_rows,
)
from app.storage.artifacts import load_artifact_preview
from app.builtin_dictionary_data import builtin_dictionary_table_specs
from app.workflow.runtime.native import (
    NodeExecutionState,
    WorkflowExecutionContext,
    _export_selection_from_active_graph,
    dag_parallel_worker_count,
)
from app.domain.defaults import default_workflow_definition, empty_result_bundle, workflow_payload_hash
from app.workflow.runtime.incremental import select_incremental_scope
from app.workflow.registry import build_node_registry
from app.storage.projects import create_project, load_project, normalize_dictionary_set_record, save_project
from app.reporting.core import build_html_report
from app.workflow.runtime.support import dispatch_progress_callback
from app.analysis.text import apply_dictionary, apply_normalization
from app.workflow.runner import run_project_workflow


DICTIONARY_KINDS = [
    "stopwords",
    "custom_lexicon",
    "phrase_lexicon",
    "synonym_map",
    "near_synonym_map",
    "standard_terms",
    "exclusion_terms",
    "regex_rules",
]

ANALYSIS_NODE_TYPES = [
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
]

OUTPUT_NODE_TYPES = [
    "save_csv",
    "save_xlsx",
    "save_png",
    "save_html_report",
]

TEST_ANALYSIS_CONFIG = {
    "frequency_statistics": {"top_n": 20},
    "cooccurrence_analysis": {"cooccurrence_window": 3, "min_cooccurrence": 1},
    "feature_term_selection": {"feature_term_count": 24},
    "keyword_extraction": {"top_k_per_doc": 4, "top_k_project": 8},
    "keyword_clustering": {"keyword_cluster_k": 2, "topic_model_k": 2},
    "institution_topic_analysis": {"topic_model_k": 2},
    "document_clustering": {"document_cluster_k": 2},
}

TEST_DICTIONARY_ENTRIES = {
    "stopwords": [
        {"id": "stopword-1", "source": "the", "target": None, "enabled": True, "hits": 0, "tags": [], "notes": ""},
    ],
    "custom_lexicon": [
        {"id": "custom-1", "source": "智能制造", "target": None, "enabled": True, "hits": 0, "tags": [], "notes": ""},
    ],
    "phrase_lexicon": [
        {
            "id": "phrase-1",
            "source": "supply chain",
            "target": "supply_chain",
            "enabled": True,
            "hits": 0,
            "tags": [],
            "notes": "",
        },
    ],
    "synonym_map": [],
    "near_synonym_map": [],
    "standard_terms": [],
    "exclusion_terms": [],
    "regex_rules": [],
}


def _fixture_document(
    doc_id: str,
    *,
    title: str,
    raw_text: str,
    year: int,
    source: str,
    institution: str,
    source_profile: str,
    keyword_field: str = "",
) -> dict[str, Any]:
    return {
        "id": doc_id,
        "doc_id": doc_id,
        "source_profile": source_profile,
        "title": title,
        "raw_text": raw_text,
        "clean_text": "",
        "normalized_text": "",
        "tokens": [],
        "phrase_hits": [],
        "filtered_tokens": [],
        "year": year,
        "source": source,
        "author": "",
        "institution": institution,
        "country_or_region": "CN",
        "category_or_tag": "test-fixture",
        "keyword_field": keyword_field,
        "extra_metadata": {"fixture": True},
        "status": "ready",
        "raw_hash": md5(raw_text.encode("utf-8")).hexdigest(),
    }


def _build_test_corpus() -> list[dict[str, Any]]:
    return [
        _fixture_document(
            "DOC-001",
            title="生成式 AI 在学术写作支持中的应用边界",
            raw_text="生成式AI辅助写作正在改变研究流程，但也带来学术规范与引用透明度问题。",
            year=2024,
            source="Journal of Digital Humanities",
            institution="复旦大学",
            source_profile="literature",
            keyword_field="generative ai; academic writing",
        ),
        _fixture_document(
            "DOC-002",
            title="Battery recycling risk mapping",
            raw_text="Battery recycling analytics reveals supply chain risks and patent hotspots across East Asia.",
            year=2023,
            source="Patent Watch",
            institution="清华大学",
            source_profile="wos",
            keyword_field="battery recycling; supply chain",
        ),
        _fixture_document(
            "DOC-003",
            title="智能制造语料中的工艺知识抽取",
            raw_text="面向智能制造的工艺知识抽取，需要结合术语词典、规则治理和机构主题演化分析。",
            year=2025,
            source="IncoPat",
            institution="上海交通大学",
            source_profile="incopat",
            keyword_field="智能制造; 知识抽取",
        ),
    ]


def _build_test_dictionary_set() -> dict[str, Any]:
    collections: dict[str, Any] = {}
    sheets: dict[str, Any] = {}
    for kind in DICTIONARY_KINDS:
        entries = deepcopy(TEST_DICTIONARY_ENTRIES.get(kind, []))
        collections[kind] = {
            "kind": kind,
            "name": kind,
            "description": "workflow test fixture",
            "tables": [
                {
                    "id": f"{kind}-project-custom",
                    "kind": kind,
                    "name": "项目自定义",
                    "version": "2.0.0",
                    "description": "workflow test fixture",
                    "source_url": None,
                    "built_in": False,
                    "editable": True,
                    "enabled": True,
                    "tags": [],
                    "entries": entries,
                }
            ],
        }
        sheets[kind] = {
            "kind": kind,
            "name": kind,
            "version": "2.0.0",
            "entries": deepcopy(entries),
        }
    return {
        "id": "dict-test-fixture",
        "name": "测试词表集",
        "version": "2.0.0",
        "bound_to_project": True,
        "collections": collections,
        "sheets": sheets,
    }


def _tune_workflow_for_tests(workflow: dict[str, Any]) -> None:
    for node in workflow["nodes"]:
        node_type = str(node.get("node_type") or "")
        patch = TEST_ANALYSIS_CONFIG.get(node_type)
        if patch:
            node["config"] = {
                **(node.get("config") or {}),
                **deepcopy(patch),
            }


def _create_test_project(name: str, description: str) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
    project_dir, manifest = create_project(name, description)
    manifest["dictionary_set"] = _build_test_dictionary_set()
    manifest["source_files"] = [
        {
            "id": "source-workflow-test-fixture",
            "name": "workflow_test_fixture.json",
            "source_type": "fixture",
            "relative_path": "tests/fixtures/workflow_test_fixture.json",
            "imported_at": "2026-04-23T00:00:00+08:00",
            "row_count": 3,
        }
    ]
    _tune_workflow_for_tests(manifest["workflow_definitions"][0])
    corpus = _build_test_corpus()
    return project_dir, manifest, corpus


def _persist_runtime_project(project_dir: Any, manifest: dict[str, Any], corpus: list[dict[str, Any]]) -> None:
    save_project(project_dir, manifest, corpus, already_normalized=True)


def _disconnect_export_sinks(workflow: dict[str, Any]) -> None:
    workflow["edges"] = [
        edge
        for edge in workflow.get("edges", [])
        if not str(edge.get("to_node") or "").startswith("node-save-")
    ]


def _workflow_node(workflow: dict[str, Any], node_type: str) -> dict[str, Any]:
    return next(node for node in workflow["nodes"] if node["node_type"] == node_type)


def _bypass_node_types(workflow: dict[str, Any], *node_types: str) -> None:
    node_type_set = set(node_types)
    for node in workflow["nodes"]:
        if node["node_type"] in node_type_set:
            node.setdefault("ui_state", {})
            node["ui_state"]["bypassed"] = True


def _bypass_analysis_except(workflow: dict[str, Any], *node_types: str) -> None:
    keep = set(node_types)
    _bypass_node_types(workflow, *[node_type for node_type in ANALYSIS_NODE_TYPES if node_type not in keep])


def _retain_output_bindings(workflow: dict[str, Any], allowed_sources_by_sink: dict[str, set[str]]) -> None:
    node_lookup = {
        str(node.get("node_id") or ""): str(node.get("node_type") or "")
        for node in workflow.get("nodes", [])
        if isinstance(node, dict)
    }
    for node in workflow.get("nodes", []):
        node_type = str(node.get("node_type") or "")
        if node_type in OUTPUT_NODE_TYPES:
            node.setdefault("ui_state", {})
            node["ui_state"]["bypassed"] = node_type not in allowed_sources_by_sink

    workflow["edges"] = [
        edge
        for edge in workflow.get("edges", [])
        if str(node_lookup.get(str(edge.get("to_node") or ""), "")) not in allowed_sources_by_sink
        or str(node_lookup.get(str(edge.get("from_node") or ""), "")) in allowed_sources_by_sink[
            str(node_lookup.get(str(edge.get("to_node") or ""), ""))
        ]
    ]


def _set_scope(
    workflow: dict[str, Any],
    *,
    mode: str,
    source_values: list[str] | None = None,
    institution_values: list[str] | None = None,
    category_values: list[str] | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    selected_doc_ids: list[str] | None = None,
) -> None:
    corpus_input = _workflow_node(workflow, "corpus_input")
    corpus_input["config"] = {
        **corpus_input["config"],
        "mode": mode,
        "source_values": list(source_values or []),
        "institution_values": list(institution_values or []),
        "category_values": list(category_values or []),
        "year_from": year_from,
        "year_to": year_to,
        "selected_doc_ids": list(selected_doc_ids or []),
    }


def _set_workflow_meta(workflow: dict[str, Any], *, template_id: str, output_bundle_id: str) -> None:
    workflow.setdefault("meta", {})
    workflow["meta"]["template_id"] = template_id
    workflow["meta"]["output_bundle_id"] = output_bundle_id


def _set_export_nodes(
    workflow: dict[str, Any],
    *,
    csv_enabled: bool | None = None,
    xlsx_enabled: bool | None = None,
    png_enabled: bool | None = None,
    html_enabled: bool | None = None,
    include_audit: bool | None = None,
    chart_dpi: int | None = None,
    watermark_enabled: bool | None = None,
    watermark_text: str | None = None,
) -> None:
    node_lookup = {node["node_type"]: node for node in workflow["nodes"]}
    toggle_map = {
        "save_csv": csv_enabled,
        "save_xlsx": xlsx_enabled,
        "save_png": png_enabled,
        "save_html_report": html_enabled,
    }
    for node_type, enabled in toggle_map.items():
        if enabled is None or node_type not in node_lookup:
            continue
        node_lookup[node_type].setdefault("ui_state", {})
        node_lookup[node_type]["ui_state"]["bypassed"] = not enabled
    if include_audit is not None and "save_html_report" in node_lookup:
        node_lookup["save_html_report"]["config"]["include_audit"] = include_audit
    if chart_dpi is not None and "save_png" in node_lookup:
        node_lookup["save_png"]["config"]["chart_dpi"] = chart_dpi
    if watermark_enabled is not None and "save_png" in node_lookup:
        node_lookup["save_png"]["config"]["watermark_enabled"] = watermark_enabled
    if watermark_text is not None and "save_png" in node_lookup:
        node_lookup["save_png"]["config"]["watermark_text"] = watermark_text


def _build_custom_node(node_type: str, node_id: str, config: dict[str, Any], *, x: int = 700, y: int = 330) -> dict[str, Any]:
    definition = build_node_registry().definitions_by_type[node_type]
    return {
        "node_id": node_id,
        "node_type": node_type,
        "label": str(definition.get("title") or node_type),
        "position": {"x": x, "y": y},
        "inputs": deepcopy(definition.get("inputs") or []),
        "outputs": deepcopy(definition.get("outputs") or []),
        "config": deepcopy(config),
        "ui_state": {"collapsed": False, "bypassed": False},
        "runtime_meta": {"node_impl_version": "1.0.0"},
    }


def _insert_corpus_process_node(
    workflow: dict[str, Any],
    *,
    node_type: str,
    node_id: str,
    config: dict[str, Any],
    x: int = 700,
    y: int = 330,
) -> dict[str, Any]:
    corpus_input = _workflow_node(workflow, "corpus_input")
    clean_text = _workflow_node(workflow, "clean_text")
    node = _build_custom_node(node_type, node_id, config, x=x, y=y)
    workflow["nodes"].append(node)
    workflow["edges"] = [
        edge
        for edge in workflow.get("edges", [])
        if not (
            str(edge.get("from_node") or "") == str(corpus_input["node_id"])
            and str(edge.get("to_node") or "") == str(clean_text["node_id"])
        )
    ]
    workflow["edges"].extend(
        [
            {
                "edge_id": f"edge-{uuid4().hex[:8]}",
                "from_node": corpus_input["node_id"],
                "from_port": "corpus",
                "to_node": node_id,
                "to_port": "corpus_in",
            },
            {
                "edge_id": f"edge-{uuid4().hex[:8]}",
                "from_node": node_id,
                "from_port": str(node["outputs"][0]["port_id"]),
                "to_node": clean_text["node_id"],
                "to_port": "corpus_in",
            },
        ]
    )
    return node


def _attach_table_node_to_csv_sink(
    workflow: dict[str, Any],
    *,
    node_type: str,
    node_id: str,
    config: dict[str, Any],
    x: int = 900,
    y: int = 900,
) -> dict[str, Any]:
    corpus_input = _workflow_node(workflow, "corpus_input")
    save_csv = _workflow_node(workflow, "save_csv")
    node = _build_custom_node(node_type, node_id, config, x=x, y=y)
    workflow["nodes"].append(node)
    workflow["edges"].extend(
        [
            {
                "edge_id": f"edge-{uuid4().hex[:8]}",
                "from_node": corpus_input["node_id"],
                "from_port": "corpus",
                "to_node": node_id,
                "to_port": "corpus_in",
            },
            {
                "edge_id": f"edge-{uuid4().hex[:8]}",
                "from_node": node_id,
                "from_port": str(node["outputs"][0]["port_id"]),
                "to_node": save_csv["node_id"],
                "to_port": "table_in",
            },
        ]
    )
    return node


def test_workflow_runner_end_to_end_generates_outputs(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "workflow test project")
    manifest, corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    assert run_record["status"] == "completed"
    assert manifest["results"]["frequency_table"]
    assert manifest["results"]["selected_feature_terms"]
    assert manifest["results"]["keyword_result"]
    assert manifest["results"]["keyword_cluster_result"]
    assert manifest["results"]["institution_topic_cooccurrence"]
    assert manifest["results"]["report_files"]
    assert run_record["workflow_id"] == manifest["active_workflow_id"]
    assert run_record["workflow_name"] == manifest["workflow_definitions"][0]["name"]
    assert run_record["workflow_hash"].startswith("sha256:")
    for relative_path in manifest["results"]["report_files"]:
        assert (project_dir / relative_path).exists()
    assert any(path.endswith("keyword_wordcloud.png") for path in manifest["results"]["report_files"])
    assert any(path.endswith("project_keywords.png") for path in manifest["results"]["report_files"])
    assert any(path.endswith("institution_topic_heatmap.png") for path in manifest["results"]["report_files"])


def test_runtime_support_dispatch_progress_callback_accepts_legacy_signature():
    progress_events: list[tuple[float, str]] = []

    def legacy_callback(progress: float, message: str) -> None:
        progress_events.append((progress, message))

    dispatch_progress_callback(legacy_callback, 0.5, "halfway", {"stage": "analysis"})

    assert progress_events == [(0.5, "halfway")]


def test_export_selection_uses_registry_output_metadata():
    registry = build_node_registry()
    node_lookup = {
        "node-feature": {"node_id": "node-feature", "node_type": "feature_term_selection"},
        "node-keyword": {"node_id": "node-keyword", "node_type": "keyword_extraction"},
        "node-dictionary": {"node_id": "node-dictionary", "node_type": "apply_dictionary_rules"},
        "node-csv": {"node_id": "node-csv", "node_type": "save_csv"},
        "node-xlsx": {"node_id": "node-xlsx", "node_type": "save_xlsx"},
        "node-png": {"node_id": "node-png", "node_type": "save_png"},
        "node-report": {"node_id": "node-report", "node_type": "save_html_report"},
    }
    active_edges = [
        {
            "edge_id": "edge-feature-csv",
            "from_node": "node-feature",
            "from_port": "feature_term_table",
            "to_node": "node-csv",
            "to_port": "table_in",
        },
        {
            "edge_id": "edge-feature-xlsx",
            "from_node": "node-feature",
            "from_port": "feature_term_table",
            "to_node": "node-xlsx",
            "to_port": "table_in",
        },
        {
            "edge_id": "edge-keyword-png",
            "from_node": "node-keyword",
            "from_port": "keyword_table",
            "to_node": "node-png",
            "to_port": "render_in",
        },
        {
            "edge_id": "edge-keyword-report",
            "from_node": "node-keyword",
            "from_port": "keyword_table",
            "to_node": "node-report",
            "to_port": "report_in",
        },
        {
            "edge_id": "edge-audit-report",
            "from_node": "node-dictionary",
            "from_port": "audit_table",
            "to_node": "node-report",
            "to_port": "report_in",
        },
    ]

    selection = _export_selection_from_active_graph(node_lookup, active_edges, registry.definitions_by_type)

    assert selection["csv_tables"] == {"selected_feature_terms"}
    assert selection["xlsx_tables"] == {"selected_feature_terms"}
    assert selection["png_charts"] == {"project_keywords", "keyword_wordcloud"}
    assert selection["html_result_keys"] == {"keyword_result"}
    assert selection["include_audit"] == {"audit"}


def test_workflow_respects_disabled_analysis_and_export_steps(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "workflow step control")
    workflow = manifest["workflow_definitions"][0]
    _bypass_node_types(workflow, *ANALYSIS_NODE_TYPES, *OUTPUT_NODE_TYPES)
    manifest, corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    run_root = project_dir / "runs" / run_record["run_id"]
    assert manifest["results"]["frequency_table"] == []
    assert manifest["results"]["report_files"] == []
    assert (run_root / "params_snapshot.json").exists()
    assert (run_root / "logs.json").exists()
    assert (run_root / "logs.txt").exists()
    assert (run_root / "corpus_snapshot.json").exists()
    assert not (run_root / "outputs" / "frequency_table.csv").exists()
    assert any("分析步骤已禁用" in entry["message"] for entry in run_record["logs"])


def test_workflow_export_options_control_written_artifacts(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "workflow export control")
    workflow = manifest["workflow_definitions"][0]
    _bypass_analysis_except(workflow, "frequency_statistics")
    _set_export_nodes(workflow, csv_enabled=True, xlsx_enabled=True, png_enabled=False, html_enabled=False)
    _retain_output_bindings(
        workflow,
        {
            "save_csv": {"frequency_statistics"},
            "save_xlsx": {"frequency_statistics"},
        },
    )
    manifest, corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    run_root = project_dir / "runs" / run_record["run_id"]
    assert (run_root / "outputs" / "frequency_table.csv").exists()
    assert (run_root / "outputs" / "analysis_bundle.xlsx").exists()
    assert not (run_root / "outputs" / "audit_table.csv").exists()
    assert not (run_root / "charts" / "frequency_top_terms.png").exists()
    assert not (run_root / "charts" / "keyword_wordcloud.png").exists()
    assert not (run_root / "charts" / "project_keywords.png").exists()
    assert not (run_root / "charts" / "institution_topic_heatmap.png").exists()
    assert not (run_root / "report" / "report.html").exists()


def test_workflow_png_exports_include_visualizations_and_watermark_options(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "workflow png export test")
    workflow = manifest["workflow_definitions"][0]
    _bypass_analysis_except(
        workflow,
        "frequency_statistics",
        "feature_term_selection",
        "keyword_extraction",
        "keyword_clustering",
        "institution_topic_analysis",
        "document_clustering",
    )
    _set_export_nodes(
        workflow,
        csv_enabled=False,
        xlsx_enabled=False,
        png_enabled=True,
        html_enabled=False,
        chart_dpi=360,
        watermark_enabled=True,
        watermark_text="内部汇报",
    )
    _retain_output_bindings(
        workflow,
        {
            "save_png": {
                "frequency_statistics",
                "keyword_extraction",
                "institution_topic_analysis",
                "document_clustering",
            }
        },
    )
    manifest, corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    run_root = project_dir / "runs" / run_record["run_id"]
    assert (run_root / "charts" / "frequency_top_terms.png").exists()
    assert (run_root / "charts" / "keyword_wordcloud.png").exists()
    assert (run_root / "charts" / "project_keywords.png").exists()
    assert (run_root / "charts" / "institution_topic_heatmap.png").exists()
    assert (run_root / "charts" / "document_clusters.png").exists()


def test_workflow_scope_filters_subset_and_records_summary(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "workflow scope test")
    workflow = manifest["workflow_definitions"][0]
    _bypass_analysis_except(workflow, "term_document_analysis", "term_year_analysis")
    _set_scope(
        workflow,
        mode="filtered_subset",
        source_values=["Journal of Digital Humanities"],
        year_from=2024,
        year_to=2024,
    )
    _set_workflow_meta(workflow, template_id="keyword_topic", output_bundle_id="charts_and_report")
    _set_export_nodes(workflow, csv_enabled=False, xlsx_enabled=False, png_enabled=False, html_enabled=False)

    manifest, processed_corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    assert run_record["status"] == "completed"
    assert run_record["processed_document_count"] == 1
    assert "年份=2024-2024" in run_record["run_scope_summary"]
    assert run_record["workflow_id"] == manifest["active_workflow_id"]
    assert run_record["recipe_id"] == "keyword_topic"
    assert run_record["output_bundle_id"] == "charts_and_report"
    assert run_record["output_summary"]
    assert {row["doc_id"] for row in manifest["results"]["term_document_table"]} == {"DOC-001"}
    assert {row["year"] for row in manifest["results"]["term_year_table"]} == {2024}


def test_workflow_uses_active_workflow_even_if_runtime_profile_hint_is_stale(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "workflow runtime compile test")
    manifest["runtime_profile"] = {
        "run_scope": {"mode": "all_documents"},
        "recipe_id": "standard_analysis",
        "output_bundle_id": "full_report",
        "filtering": {"min_term_frequency": 99},
        "export": {
            "export_csv": True,
            "export_xlsx": True,
            "export_png": True,
            "export_html_report": True,
            "include_audit": True,
        },
    }

    active_workflow = manifest["workflow_definitions"][0]
    _set_scope(
        active_workflow,
        mode="filtered_subset",
        source_values=["Journal of Digital Humanities"],
        year_from=2024,
        year_to=2024,
    )
    _workflow_node(active_workflow, "filter_terms")["config"]["min_term_frequency"] = 2
    _set_workflow_meta(active_workflow, template_id="keyword_topic", output_bundle_id="charts_and_report")
    _disconnect_export_sinks(active_workflow)
    _bypass_analysis_except(active_workflow)

    manifest, processed_corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    assert run_record["processed_document_count"] == 1
    assert run_record["recipe_id"] == "keyword_topic"
    assert run_record["output_bundle_id"] == "charts_and_report"
    params_snapshot = json.loads((project_dir / "runs" / run_record["run_id"] / "params_snapshot.json").read_text(encoding="utf-8"))
    assert params_snapshot["runtime_profile"]["run_scope"]["mode"] == "filtered_subset"
    assert params_snapshot["runtime_profile"]["filtering"]["min_term_frequency"] == 2


def test_manual_workflow_native_dag_hits_node_cache_on_second_run(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "native dag cache test")
    manifest["workflow_definitions"][0]["source"] = "manual"
    _disconnect_export_sinks(manifest["workflow_definitions"][0])
    _bypass_analysis_except(manifest["workflow_definitions"][0])

    manifest, processed_corpus, first_run = run_project_workflow(project_dir, manifest, corpus)
    _persist_runtime_project(project_dir, manifest, processed_corpus)

    manifest, reloaded_corpus = load_project(project_dir)
    manifest["workflow_definitions"][0]["source"] = "manual"
    _disconnect_export_sinks(manifest["workflow_definitions"][0])
    _bypass_analysis_except(manifest["workflow_definitions"][0])
    manifest["workflow_definitions"][0]["viewport"] = {
        "x": 1440,
        "y": -960,
        "zoom": 0.5,
    }
    manifest, processed_corpus, second_run = run_project_workflow(project_dir, manifest, reloaded_corpus)

    cache_files = list((project_dir / "cache" / "nodes").rglob("*.pkl"))

    assert first_run.get("node_runs")
    assert second_run.get("node_runs")
    assert cache_files
    assert any(node_run["cache_hit"] for node_run in second_run["node_runs"])
    assert any(node_run["status"] == "cached" for node_run in second_run["node_runs"])
    assert all(str(node_run.get("cache_path") or "").endswith(".pkl") for node_run in second_run["node_runs"] if node_run.get("cache_hit"))
    assert first_run["workflow_hash"] == second_run["workflow_hash"]


def test_manual_workflow_runtime_meta_can_disable_node_cache(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "native dag cache override")
    workflow = manifest["workflow_definitions"][0]
    workflow["source"] = "manual"
    _disconnect_export_sinks(workflow)
    _bypass_analysis_except(workflow)

    token_node = _workflow_node(workflow, "tokenize")
    token_node["runtime_meta"] = {
        **dict(token_node.get("runtime_meta") or {}),
        "cache_enabled": False,
    }

    manifest, processed_corpus, first_run = run_project_workflow(project_dir, manifest, corpus)
    _persist_runtime_project(project_dir, manifest, processed_corpus)

    manifest, reloaded_corpus = load_project(project_dir)
    workflow = manifest["workflow_definitions"][0]
    workflow["source"] = "manual"
    _disconnect_export_sinks(workflow)
    _bypass_analysis_except(workflow)
    token_node = _workflow_node(workflow, "tokenize")
    token_node["runtime_meta"] = {
        **dict(token_node.get("runtime_meta") or {}),
        "cache_enabled": False,
    }

    manifest, _processed_corpus, second_run = run_project_workflow(project_dir, manifest, reloaded_corpus)

    token_cache_files = list((project_dir / "cache" / "nodes" / token_node["node_id"]).glob("*.pkl"))
    token_runs = [
        node_run
        for node_run in second_run["node_runs"]
        if str(node_run.get("node_id") or "") == token_node["node_id"]
    ]

    assert first_run["status"] == "completed"
    assert second_run["status"] == "completed"
    assert token_runs
    assert not token_cache_files
    assert not any(node_run.get("cache_hit") for node_run in token_runs)
    assert all(node_run.get("cache_path") in (None, "") for node_run in token_runs)


def test_workflow_payload_hash_ignores_ui_only_changes():
    workflow = default_workflow_definition()
    baseline_hash = workflow_payload_hash(workflow)

    workflow["name"] = "重命名后的工作流"
    workflow["viewport"] = {"x": -1280, "y": 640, "zoom": 0.55}
    workflow["groups"] = [{"group_id": "group-a", "label": "仅 UI 分组", "node_ids": ["node-clean-text"], "collapsed": True}]
    workflow["nodes"][0]["label"] = "词表输入（展示名）"
    workflow["nodes"][0]["position"] = {"x": 999, "y": 555}
    workflow["nodes"][0]["size"] = {"w": 320, "h": 240}
    workflow["nodes"][0]["ui_state"]["collapsed"] = True
    workflow["nodes"][0]["ui_state"]["pinned_preview"] = True

    assert workflow_payload_hash(workflow) == baseline_hash

    workflow["nodes"][0]["ui_state"]["bypassed"] = True

    assert workflow_payload_hash(workflow) != baseline_hash


def test_manual_workflow_cached_nodes_do_not_emit_running_progress_on_second_run(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "native dag cache progress semantics")
    workflow = manifest["workflow_definitions"][0]
    workflow["source"] = "manual"
    _disconnect_export_sinks(workflow)
    _bypass_analysis_except(workflow)

    manifest, processed_corpus, _first_run = run_project_workflow(project_dir, manifest, corpus)
    _persist_runtime_project(project_dir, manifest, processed_corpus)

    manifest, reloaded_corpus = load_project(project_dir)
    workflow = manifest["workflow_definitions"][0]
    workflow["source"] = "manual"
    _disconnect_export_sinks(workflow)
    _bypass_analysis_except(workflow)

    progress_details: list[dict[str, Any]] = []

    def progress_callback(_progress: float, _message: str, detail: dict[str, Any] | None = None) -> None:
        if detail and detail.get("kind") == "workflow_run":
            progress_details.append(deepcopy(detail))

    manifest, _processed_corpus, second_run = run_project_workflow(
        project_dir,
        manifest,
        reloaded_corpus,
        progress_callback=progress_callback,
    )

    cached_node_ids = {
        str(node_run["node_id"])
        for node_run in second_run["node_runs"]
        if node_run.get("status") == "cached"
    }

    assert cached_node_ids
    assert progress_details
    assert not any(
        detail.get("current_node_id") in cached_node_ids
        and str((detail.get("node_states") or {}).get(str(detail.get("current_node_id")), {}).get("status") or "") == "running"
        for detail in progress_details
    )


def test_manual_workflow_progress_details_emit_full_node_state_sync(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "native dag full sync progress semantics")
    workflow = manifest["workflow_definitions"][0]
    workflow["source"] = "manual"
    _disconnect_export_sinks(workflow)
    _bypass_analysis_except(workflow, "frequency_statistics", "term_document_analysis")

    progress_details: list[dict[str, Any]] = []

    def progress_callback(_progress: float, _message: str, detail: dict[str, Any] | None = None) -> None:
        if detail and detail.get("kind") == "workflow_run":
            progress_details.append(deepcopy(detail))

    run_project_workflow(
        project_dir,
        manifest,
        corpus,
        progress_callback=progress_callback,
    )

    runtime_details = [detail for detail in progress_details if isinstance(detail.get("node_states"), dict)]

    assert runtime_details
    assert all(detail.get("full_node_state_sync") is True for detail in runtime_details)


def test_runtime_context_does_not_synthesize_node_progress_without_executor_updates(tmp_path):
    progress_details: list[dict[str, Any]] = []

    def progress_callback(_progress: float, _message: str, detail: dict[str, Any] | None = None) -> None:
        if detail and detail.get("kind") == "workflow_run":
            progress_details.append(deepcopy(detail))

    node = {"node_id": "node-slow-analysis", "node_type": "frequency_statistics", "label": "慢速分析"}
    context = WorkflowExecutionContext(
        project_dir=tmp_path,
        manifest={"name": "heartbeat"},
        workflow_definition={"workflow_id": "workflow-heartbeat", "name": "heartbeat"},
        runtime_profile={},
        full_corpus=[],
        logs=[],
        warnings=[],
        errors=[],
        run_id="run-heartbeat",
        progress_callback=progress_callback,
        total_nodes=1,
    )
    start_clock = time.perf_counter()
    _node_id, started_at = context.begin_node(node, 1)

    time.sleep(0.7)

    context.finish_node(
        node,
        node_index=1,
        state=NodeExecutionState(outputs={}, output_hashes={}, cache_hit=False),
        started_at=started_at,
        start_clock=start_clock,
        status="completed",
    )

    running_progress_values = [
        float(((detail.get("node_states") or {}).get("node-slow-analysis") or {}).get("progress") or 0.0)
        for detail in progress_details
        if ((detail.get("node_states") or {}).get("node-slow-analysis") or {}).get("status") == "running"
    ]
    assert running_progress_values
    assert all(progress == 0.0 for progress in running_progress_values)


def test_dag_parallel_worker_count_respects_env_overrides(monkeypatch):
    registry = build_node_registry()
    nodes = [
        {"node_id": "node-frequency", "node_type": "frequency_statistics"},
        {"node_id": "node-term-doc", "node_type": "term_document_analysis"},
    ]

    monkeypatch.setenv("TEXTFLOW_DAG_WORKERS", "2")
    monkeypatch.delenv("TEXTFLOW_DISABLE_DAG_PARALLEL", raising=False)
    assert dag_parallel_worker_count(nodes, registry.definitions_by_type) == 2

    monkeypatch.setenv("TEXTFLOW_DISABLE_DAG_PARALLEL", "1")
    assert dag_parallel_worker_count(nodes, registry.definitions_by_type) == 1


def test_manual_workflow_parallel_safe_analysis_nodes_run_concurrently(isolated_workspace, monkeypatch):
    import app.workflow.executors as node_executor_module

    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "native dag parallel test")
    workflow = manifest["workflow_definitions"][0]
    workflow["source"] = "manual"
    _disconnect_export_sinks(workflow)
    _bypass_analysis_except(workflow, "frequency_statistics", "term_document_analysis")

    monkeypatch.setenv("TEXTFLOW_DAG_WORKERS", "2")
    monkeypatch.delenv("TEXTFLOW_DISABLE_DAG_PARALLEL", raising=False)

    state_lock = threading.Lock()
    running_count = 0
    max_running = 0

    def build_executor(port_id: str, row: dict[str, Any]):
        def execute(_context: Any, _node: dict[str, Any], _inputs: dict[str, Any]) -> dict[str, Any]:
            nonlocal running_count, max_running
            with state_lock:
                running_count += 1
                max_running = max(max_running, running_count)
            try:
                time.sleep(0.15)
                return {port_id: [dict(row)]}
            finally:
                with state_lock:
                    running_count -= 1

        return execute

    monkeypatch.setitem(
        node_executor_module.EXECUTORS_BY_TYPE,
        "frequency_statistics",
        build_executor(
            "frequency_table",
            {"term": "parallel-frequency", "tf": 2, "df": 1, "ratio": 1.0},
        ),
    )
    monkeypatch.setitem(
        node_executor_module.EXECUTORS_BY_TYPE,
        "term_document_analysis",
        build_executor(
            "term_document_table",
            {"term": "parallel-term-doc", "doc_id": "DOC-001", "title": "并行测试", "term_count_in_doc": 1},
        ),
    )

    manifest, processed_corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    assert run_record["status"] == "completed"
    assert processed_corpus
    assert max_running >= 2
    assert manifest["results"]["frequency_table"]
    assert manifest["results"]["term_document_table"]


def test_native_dag_accepts_two_argument_progress_callback(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "progress callback compatibility")
    manifest["workflow_definitions"][0]["source"] = "manual"
    _disconnect_export_sinks(manifest["workflow_definitions"][0])
    _bypass_analysis_except(manifest["workflow_definitions"][0])

    progress_events: list[tuple[float, str]] = []

    def progress_callback(progress: float, message: str) -> None:
        progress_events.append((progress, message))

    manifest, processed_corpus, run_record = run_project_workflow(
        project_dir,
        manifest,
        corpus,
        progress_callback=progress_callback,
    )

    assert run_record["status"] == "completed"
    assert progress_events
    assert any(progress >= 0.9 for progress, _message in progress_events)


def test_save_project_fast_path_preserves_runtime_results(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "fast save path")
    manifest["workflow_definitions"][0]["source"] = "manual"
    _disconnect_export_sinks(manifest["workflow_definitions"][0])
    _bypass_analysis_except(manifest["workflow_definitions"][0], "frequency_statistics")

    manifest, processed_corpus, run_record = run_project_workflow(project_dir, manifest, corpus)
    save_project(project_dir, manifest, processed_corpus, already_normalized=True)
    reloaded_manifest, reloaded_corpus = load_project(project_dir)

    assert run_record["status"] == "completed"
    assert reloaded_manifest["results"]["frequency_table"]
    assert reloaded_manifest["run_history"][-1]["run_id"] == run_record["run_id"]
    assert len(reloaded_corpus) == len(processed_corpus)


def test_workflow_respects_disconnected_active_workflow_edges(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "workflow edge runtime test")

    active_workflow = manifest["workflow_definitions"][0]
    active_workflow["source"] = "manual"
    _disconnect_export_sinks(active_workflow)
    _bypass_analysis_except(active_workflow)

    manifest, processed_corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    params_snapshot = json.loads((project_dir / "runs" / run_record["run_id"] / "params_snapshot.json").read_text(encoding="utf-8"))
    assert "export" not in params_snapshot["runtime_profile"]["enabled_steps"]
    assert manifest["results"]["report_files"] == []
    assert any("导出步骤已禁用" in entry["message"] for entry in run_record["logs"])


def test_manual_workflow_merge_corpora_executes_native_dag(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "workflow merge runtime test")

    active_workflow = manifest["workflow_definitions"][0]
    active_workflow["source"] = "manual"
    _disconnect_export_sinks(active_workflow)
    _bypass_analysis_except(active_workflow, "term_document_analysis")
    corpus_input = next(node for node in active_workflow["nodes"] if node["node_type"] == "corpus_input")
    clean_node = next(node for node in active_workflow["nodes"] if node["node_type"] == "clean_text")
    corpus_input["config"] = {
        **corpus_input["config"],
        "mode": "selected_documents",
        "source_values": [],
        "institution_values": [],
        "category_values": [],
        "year_from": None,
        "year_to": None,
        "selected_doc_ids": ["DOC-001"],
    }

    second_input = deepcopy(corpus_input)
    second_input["node_id"] = "node-corpus-input-b"
    second_input["label"] = "语料输入 B"
    second_input["position"] = {"x": 120, "y": 620}
    second_input["config"] = {
        **second_input["config"],
        "selected_doc_ids": ["DOC-002"],
    }
    merge_node = {
        "node_id": "node-merge-corpora",
        "node_type": "merge_corpora",
        "label": "合并语料",
        "position": {"x": 520, "y": 480},
        "inputs": [{"port_id": "corpus_in", "port_type": "CorpusTable", "label": "输入语料", "allow_multiple": True}],
        "outputs": [{"port_id": "corpus", "port_type": "CorpusTable", "label": "合并后语料"}],
        "config": {"strategy": "append"},
        "ui_state": {"collapsed": False, "bypassed": False},
        "runtime_meta": {"step_id": "merge", "node_impl_version": "1.0.0"},
    }
    active_workflow["nodes"].extend([second_input, merge_node])
    active_workflow["edges"] = [
        edge
        for edge in active_workflow["edges"]
        if not (edge["from_node"] == corpus_input["node_id"] and edge["to_node"] == clean_node["node_id"])
    ]
    active_workflow["edges"].extend(
        [
            {
                "edge_id": "edge-corpus-a-merge",
                "from_node": corpus_input["node_id"],
                "from_port": "corpus",
                "to_node": "node-merge-corpora",
                "to_port": "corpus_in",
            },
            {
                "edge_id": "edge-corpus-b-merge",
                "from_node": second_input["node_id"],
                "from_port": "corpus",
                "to_node": "node-merge-corpora",
                "to_port": "corpus_in",
            },
            {
                "edge_id": "edge-merge-clean",
                "from_node": "node-merge-corpora",
                "from_port": "corpus",
                "to_node": clean_node["node_id"],
                "to_port": "corpus_in",
            },
        ]
    )

    manifest, processed_corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    assert run_record["status"] == "completed"
    assert run_record["processed_document_count"] == 2
    assert {row["doc_id"] for row in manifest["results"]["term_document_table"]} == {"DOC-001", "DOC-002"}


def test_dictionary_set_normalization_backfills_builtin_stopwords():
    normalized = normalize_dictionary_set_record(
        {
            "sheets": {
                "stopwords": {
                    "entries": [
                        {
                            "id": "custom-stopword",
                            "source": "自定义停词",
                            "target": None,
                            "enabled": True,
                            "hits": 3,
                            "tags": [],
                            "notes": "",
                        }
                    ]
                }
            }
        }
    )

    stopword_entries = normalized["sheets"]["stopwords"]["entries"]
    stopword_lookup = {entry["source"]: entry for entry in stopword_entries}

    assert len(stopword_entries) > 1500
    assert "的" in stopword_lookup
    assert "about" in stopword_lookup
    assert stopword_lookup["自定义停词"]["hits"] == 3


def test_builtin_dictionary_specs_use_packaged_upstream_snapshots():
    specs = builtin_dictionary_table_specs()

    stopword_tables = {table["id"]: table for table in specs["stopwords"]}
    custom_tables = {table["id"]: table for table in specs["custom_lexicon"]}
    standard_tables = {table["id"]: table for table in specs["standard_terms"]}
    exclusion_tables = {table["id"]: table for table in specs["exclusion_terms"]}

    assert len(stopword_tables["builtin-stopwords-zh"]["rows"]) >= 700
    assert len(stopword_tables["builtin-stopwords-en"]["rows"]) >= 1200
    assert len(custom_tables["builtin-thuocl-it"]["rows"]) >= 15000
    assert len(custom_tables["builtin-thuocl-medical"]["rows"]) >= 18000
    assert len(standard_tables["builtin-misspell-main"]["rows"]) >= 25000
    assert len(exclusion_tables["builtin-thuocl-locations"]["rows"]) >= 40000
    assert stopword_tables["builtin-stopwords-zh"]["source_url"]
    assert custom_tables["builtin-thuocl-it"]["source_url"]
    assert standard_tables["builtin-misspell-main"]["source_url"]


def test_dictionary_set_normalization_migrates_legacy_sheet_into_collections():
    normalized = normalize_dictionary_set_record(
        {
            "version": "1.0.0",
            "sheets": {
                "custom_lexicon": {
                    "name": "旧版自定义词典",
                    "version": "1.0.0",
                    "entries": [
                        {
                            "id": "legacy-term-1",
                            "source": "智能制造",
                            "target": None,
                            "enabled": True,
                            "hits": 6,
                            "tags": ["legacy"],
                            "notes": "from old sheet",
                        }
                    ],
                }
            },
        }
    )

    collection = normalized["collections"]["custom_lexicon"]
    project_table = collection["tables"][0]
    aggregated_lookup = {entry["source"]: entry for entry in normalized["sheets"]["custom_lexicon"]["entries"]}

    assert normalized["sheets"]["custom_lexicon"]["version"] == "2.0.0"
    assert collection["name"] == "自定义词典"
    assert project_table["id"] == "custom_lexicon-project-custom"
    assert project_table["editable"] is True
    assert project_table["built_in"] is False
    assert any(table["built_in"] for table in collection["tables"][1:])
    assert aggregated_lookup["智能制造"]["hits"] == 6
    assert aggregated_lookup["智能制造"]["notes"] == "from old sheet"
    assert "字符串" in aggregated_lookup


def test_html_report_only_embeds_existing_charts():
    manifest = {
        "name": "报告测试项目",
        "description": "用于验证 HTML 报告渲染。",
        "active_workflow_id": "wf-default",
        "run_history": [
            {
                "run_scope_summary": "处理对象为 2 篇文档。",
                "output_summary": "HTML 报告与部分图表",
                "workflow_name": "默认工作流",
            }
        ],
    }
    corpus = [
        {"doc_id": "DOC-001", "title": "示例 A", "year": 2024, "institution": "机构A", "source": "paper"},
        {"doc_id": "DOC-002", "title": "示例 B", "year": 2025, "institution": "机构B", "source": "patent"},
    ]
    result_bundle = empty_result_bundle()
    result_bundle["frequency_table"] = [
        {"term": "分析", "tf": 8, "df": 2, "ratio": 0.5},
    ]
    result_bundle["cooccurrence_table"] = [
        {"term_a": "分析", "term_b": "主题", "cooccurrence_count": 3, "score": 1.3863},
    ]
    result_bundle["report_chart_cards"] = [
        {
            "relative_path": "../charts/frequency_top_terms.png",
            "title": "高频词 Top 15",
            "description": "测试图表。",
        }
    ]

    html = build_html_report(manifest, corpus, result_bundle)

    assert "核心发现" in html
    assert "../charts/frequency_top_terms.png" in html
    assert "keyword_wordcloud.png" not in html
    assert "document_clusters.png" not in html
    assert "规则审计摘要" not in html


def test_analysis_uses_yake_keywords_and_nmf_topics():
    corpus = [
        {
            "doc_id": "DOC-001",
            "title": "电池回收供应链风险",
            "filtered_tokens": ["电池", "回收", "供应链", "风险", "治理"],
            "keyword_field": "电池回收; 供应链",
            "institution": "机构A",
            "year": 2024,
            "source": "paper",
        },
        {
            "doc_id": "DOC-002",
            "title": "动力电池回收工艺",
            "filtered_tokens": ["动力电池", "回收", "工艺", "绿色", "制造"],
            "keyword_field": "动力电池; 回收工艺",
            "institution": "机构A",
            "year": 2024,
            "source": "patent",
        },
        {
            "doc_id": "DOC-003",
            "title": "学术写作与引用规范",
            "filtered_tokens": ["学术", "写作", "引用", "规范", "透明度"],
            "keyword_field": "学术写作; 引用规范",
            "institution": "机构B",
            "year": 2025,
            "source": "paper",
        },
        {
            "doc_id": "DOC-004",
            "title": "生成式 AI 辅助写作",
            "filtered_tokens": ["生成式", "ai", "辅助", "写作", "规范"],
            "keyword_field": "生成式AI; 写作辅助",
            "institution": "机构B",
            "year": 2025,
            "source": "paper",
        },
    ]
    analysis_params = {
        "feature_term_count": 20,
        "top_k_per_doc": 5,
        "top_k_project": 10,
        "keyword_cluster_k": 2,
    }

    feature_rows, keyword_rows, term_doc_df = tfidf_analysis(corpus, analysis_params)
    topic_lookup, doc_topics = nmf_topic_model(corpus, term_doc_df, analysis_params)
    institution_keyword_rows, institution_topic_rows = institution_keyword_and_topic(
        corpus,
        keyword_rows,
        doc_topics,
        topic_lookup,
    )

    assert feature_rows
    assert any(row["scope"] == "doc" for row in keyword_rows)
    assert any(row["scope"] == "project" for row in keyword_rows)
    assert any("电池" in row["keyword"] or "写作" in row["keyword"] for row in keyword_rows)
    assert len(topic_lookup) == 2
    assert all(payload["label"] for payload in topic_lookup.values())
    assert len(doc_topics) == len(corpus)
    assert institution_keyword_rows
    assert institution_topic_rows


def test_parallel_yake_worker_count_respects_env_overrides(monkeypatch):
    corpus = [{"filtered_tokens": ["battery"] * 400} for _ in range(6)]

    monkeypatch.setenv("TEXTFLOW_YAKE_WORKERS", "4")
    assert parallel_yake_worker_count(corpus) == 4

    monkeypatch.setenv("TEXTFLOW_DISABLE_PARALLEL_YAKE", "1")
    assert parallel_yake_worker_count(corpus) == 1


def test_parallel_yake_matches_serial_output(monkeypatch):
    import app.analysis as analysis_module

    corpus = [
        {
            "doc_id": f"DOC-{index:03d}",
            "title": f"Battery recycling process {index}",
            "filtered_tokens": ["battery", "recycling", "process", "supply", "chain", f"node{index % 3}"] * 12,
            "keyword_field": "battery recycling; supply chain",
        }
        for index in range(1, 13)
    ]
    analysis_params = {
        "top_k_per_doc": 5,
        "top_k_project": 10,
    }

    monkeypatch.setenv("TEXTFLOW_DISABLE_PARALLEL_YAKE", "1")
    serial_rows = yake_keyword_rows(corpus, analysis_params)

    monkeypatch.delenv("TEXTFLOW_DISABLE_PARALLEL_YAKE", raising=False)
    monkeypatch.setenv("TEXTFLOW_YAKE_WORKERS", "2")

    original_serial = analysis_module._yake_keyword_rows_serial

    def fail_if_fallback(*args, **kwargs):
        raise AssertionError("parallel YAKE unexpectedly fell back to serial execution")

    monkeypatch.setattr(analysis_module, "_yake_keyword_rows_serial", fail_if_fallback)
    parallel_rows = yake_keyword_rows(corpus, analysis_params)
    monkeypatch.setattr(analysis_module, "_yake_keyword_rows_serial", original_serial)

    assert parallel_rows == serial_rows


def test_normalization_supports_time_expr_and_basic_traditional_to_simplified():
    dictionary_set = {
        "sheets": {
            "regex_rules": {
                "entries": [],
            }
        }
    }
    normalized, audits = apply_normalization(
        "學術寫作時間為 2026年04月16日 10:30",
        dictionary_set,
        {
            "convert_traditional_to_simplified": True,
            "normalize_numbers": False,
            "normalize_time_expr": True,
            "apply_regex_rules": False,
            "regex_rule_priority": "rule_order",
        },
    )

    assert "学术写作时间为" in normalized
    assert "TIME_TOKEN" in normalized
    assert any(row["rule_type"] == "traditional_to_simplified" for row in audits)
    assert any(row["rule_type"] == "time_normalization" for row in audits)


def test_workflow_logs_yake_and_nmf_methods(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "analysis method log test")
    workflow = manifest["workflow_definitions"][0]
    _bypass_analysis_except(workflow, "feature_term_selection", "keyword_extraction", "keyword_clustering")
    _set_export_nodes(workflow, csv_enabled=False, xlsx_enabled=False, png_enabled=False, html_enabled=False)
    manifest, corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    assert any(
        "已按节点选择生成分析结果" in entry["message"]
        and "关键词" in entry["message"]
        and "关键词聚类" in entry["message"]
        for entry in run_record["logs"]
    )


def test_disabled_dictionary_entries_are_ignored():
    dictionary_set = {
        "sheets": {
            "standard_terms": {"entries": []},
            "synonym_map": {"entries": []},
            "near_synonym_map": {"entries": []},
            "stopwords": {
                "entries": [
                    {"source": "analysis", "target": None, "enabled": False, "hits": 0},
                ]
            },
            "exclusion_terms": {"entries": []},
        }
    }

    tokens, audits = apply_dictionary(
        "DOC-001",
        ["analysis"],
        dictionary_set,
        {
            "apply_standard_terms": True,
            "apply_synonym_map": True,
            "apply_near_synonym_map": True,
            "apply_stopwords": True,
            "apply_exclusion_terms": True,
            "conflict_resolution": "priority",
        },
    )

    assert tokens == ["analysis"]
    assert audits == []


def test_filter_by_metadata_node_restricts_documents(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "metadata filter node")
    workflow = manifest["workflow_definitions"][0]
    _insert_corpus_process_node(
        workflow,
        node_type="filter_by_metadata",
        node_id="node-filter-by-metadata",
        config={"conditions": [{"field": "institution", "operator": "in", "values": ["清华大学"]}]},
    )
    _bypass_analysis_except(workflow, "term_document_analysis")
    _set_export_nodes(workflow, csv_enabled=False, xlsx_enabled=False, png_enabled=False, html_enabled=False)

    manifest, _processed_corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    assert run_record["processed_document_count"] == 1
    assert {row["doc_id"] for row in manifest["results"]["term_document_table"]} == {"DOC-002"}


def test_deduplicate_documents_node_keeps_single_copy(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "deduplicate node")
    duplicate = deepcopy(corpus[0])
    duplicate["id"] = "DOC-004"
    duplicate["doc_id"] = "DOC-004"
    corpus.append(duplicate)
    workflow = manifest["workflow_definitions"][0]
    _insert_corpus_process_node(
        workflow,
        node_type="deduplicate_documents",
        node_id="node-deduplicate-documents",
        config={"dedupe_keys": ["title", "year"], "strategy": "keep_first"},
        y=540,
    )
    _bypass_analysis_except(workflow, "term_document_analysis")
    _set_export_nodes(workflow, csv_enabled=False, xlsx_enabled=False, png_enabled=False, html_enabled=False)

    manifest, _processed_corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    assert run_record["processed_document_count"] == 3
    assert {row["doc_id"] for row in manifest["results"]["term_document_table"]} == {"DOC-001", "DOC-002", "DOC-003"}


def test_sample_corpus_node_is_seeded_and_reproducible(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "sample corpus node")
    workflow = manifest["workflow_definitions"][0]
    _insert_corpus_process_node(
        workflow,
        node_type="sample_corpus",
        node_id="node-sample-corpus",
        config={"sample_mode": "random", "sample_size": 2, "seed": 42},
        y=720,
    )
    _bypass_analysis_except(workflow, "term_document_analysis")
    _set_export_nodes(workflow, csv_enabled=False, xlsx_enabled=False, png_enabled=False, html_enabled=False)

    manifest, _processed_corpus, _first_run = run_project_workflow(project_dir, manifest, corpus)
    first_sample = [row["doc_id"] for row in manifest["results"]["term_document_table"]]

    manifest, _processed_corpus, _second_run = run_project_workflow(project_dir, manifest, corpus)
    second_sample = [row["doc_id"] for row in manifest["results"]["term_document_table"]]

    assert len(set(first_sample)) == 2
    assert first_sample == second_sample


def test_split_corpus_node_creates_named_views(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "split corpus node")
    workflow = manifest["workflow_definitions"][0]
    _attach_table_node_to_csv_sink(
        workflow,
        node_type="split_corpus",
        node_id="node-split-corpus",
        config={
            "split_strategy": "ratio",
            "splits": [{"name": "train", "ratio": 0.67}, {"name": "test", "ratio": 0.33}],
            "seed": 42,
        },
    )
    _retain_output_bindings(workflow, {"save_csv": {"split_corpus"}})
    _bypass_analysis_except(workflow)
    _set_export_nodes(workflow, csv_enabled=True, xlsx_enabled=False, png_enabled=False, html_enabled=False)

    manifest, _processed_corpus, _run_record = run_project_workflow(project_dir, manifest, corpus)

    assert {row["split_name"] for row in manifest["results"]["split_assignments"]} == {"train", "test"}
    assert len(manifest["results"]["split_assignments"]) == 3


def test_bucket_by_time_node_emits_time_bucket_assignments(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "bucket by time node")
    workflow = manifest["workflow_definitions"][0]
    _attach_table_node_to_csv_sink(
        workflow,
        node_type="bucket_by_time",
        node_id="node-bucket-by-time",
        config={"field": "year", "granularity": "decade"},
        x=1260,
        y=900,
    )
    _retain_output_bindings(workflow, {"save_csv": {"bucket_by_time"}})
    _bypass_analysis_except(workflow)
    _set_export_nodes(workflow, csv_enabled=True, xlsx_enabled=False, png_enabled=False, html_enabled=False)

    manifest, _processed_corpus, _run_record = run_project_workflow(project_dir, manifest, corpus)

    assert {row["time_bucket"] for row in manifest["results"]["time_bucket_assignments"]} == {"2020s"}


def test_large_node_output_is_registered_as_artifact(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "artifact-backed runtime output")
    workflow = manifest["workflow_definitions"][0]
    _bypass_analysis_except(workflow, "frequency_statistics", "term_document_analysis")
    _set_export_nodes(workflow, csv_enabled=False, xlsx_enabled=False, png_enabled=False, html_enabled=False)

    _manifest, _processed_corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    assert run_record["artifacts"]
    assert any(item["kind"] == "table" for item in run_record["artifacts"])


def test_artifact_preview_loads_without_materializing_full_payload(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "artifact preview test")
    workflow = manifest["workflow_definitions"][0]
    _bypass_analysis_except(workflow, "frequency_statistics")
    _set_export_nodes(workflow, csv_enabled=False, xlsx_enabled=False, png_enabled=False, html_enabled=False)

    _manifest, _processed_corpus, run_record = run_project_workflow(project_dir, manifest, corpus)
    artifact_id = next(item["artifact_id"] for item in run_record["artifacts"] if item["kind"] == "table")

    preview = load_artifact_preview(project_dir, artifact_id)

    assert "rows" in preview
    assert preview["rows"]


def test_non_artifact_node_runs_persist_lightweight_output_previews(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "node output preview persistence")

    manifest, processed_corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    clean_node_run = next(node_run for node_run in run_record["node_runs"] if node_run["node_type"] == "clean_text")
    output_previews = clean_node_run.get("output_previews")
    assert isinstance(output_previews, dict)
    clean_preview = output_previews.get("clean_corpus")
    assert isinstance(clean_preview, dict)
    assert clean_preview["kind"] == "table"
    assert clean_preview["row_count"] == len(processed_corpus)
    assert clean_preview["rows"]
    assert clean_preview["rows"][0].get("clean_text")

    save_project(project_dir, manifest, processed_corpus, already_normalized=True)
    reloaded_manifest, reloaded_corpus = load_project(project_dir)
    assert all(not item.get("clean_text") for item in reloaded_corpus)
    reloaded_clean_node_run = next(
        node_run
        for node_run in reloaded_manifest["run_history"][-1]["node_runs"]
        if node_run["node_type"] == "clean_text"
    )
    assert reloaded_clean_node_run["output_previews"]["clean_corpus"]["rows"][0].get("clean_text")


def test_incremental_scope_can_limit_workflow_to_changed_documents(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest, corpus = _create_test_project(project_name, "incremental scope test")
    workflow = manifest["workflow_definitions"][0]
    _bypass_analysis_except(workflow, "term_document_analysis")
    _set_export_nodes(workflow, csv_enabled=False, xlsx_enabled=False, png_enabled=False, html_enabled=False)
    new_doc = _fixture_document(
        "DOC-004",
        title="新增文档",
        raw_text="新增文档只用于增量处理验证。",
        year=2026,
        source="manual",
        institution="测试机构",
        source_profile="generic",
    )
    corpus.append(new_doc)
    scope = select_incremental_scope(
        manifest,
        {"run_mode": "incremental", "changed_doc_ids": ["DOC-004"], "process_changed_only": True},
    )

    manifest, _processed_corpus, run_record = run_project_workflow(
        project_dir,
        manifest,
        corpus,
        run_options=scope,
    )

    assert run_record["run_mode"] == "incremental"
    assert run_record["processed_document_count"] == 1
    assert {row["doc_id"] for row in manifest["results"]["term_document_table"]} == {"DOC-004"}


def test_normalize_metadata_node_standardizes_institution_country_year_and_category(isolated_workspace):
    project_dir, manifest = create_project("metadata normalization", "metadata normalization node")
    corpus = [
        {
            "doc_id": "DOC-1",
            "title": "A",
            "raw_text": "rare earth text",
            "year": "2024-05-01",
            "institution": "Univ. A; University A",
            "country_or_region": "CN",
            "category_or_tag": "C22B59/00",
            "extra_metadata": {},
            "status": "ready",
            "source_profile": "wos",
        }
    ]
    manifest["dictionary_set"] = _build_test_dictionary_set()
    _tune_workflow_for_tests(manifest["workflow_definitions"][0])
    workflow = manifest["workflow_definitions"][0]

    # inject normalize_metadata between corpus_input and clean_text
    from app.workflow.definitions.builtin import build_builtin_node_definitions
    node_defs = {d["type"]: d for d in build_builtin_node_definitions()}
    norm_meta_node = {
        "node_id": "node-normalize-metadata",
        "node_type": "normalize_metadata",
        "label": "元数据标准化",
        "position": {"x": 520, "y": 330},
        "size": {"w": 230, "h": 190},
        "inputs": deepcopy(node_defs["normalize_metadata"]["inputs"]),
        "outputs": deepcopy(node_defs["normalize_metadata"]["outputs"]),
        "config": {
            "institution_aliases_text": "Univ. A\tUniversity A",
            "country_aliases_text": "",
            "category_aliases_text": "",
            "split_delimiters": ";；|",
            "keep_first_institution": True,
            "year_source_field": "year",
        },
        "ui_state": {"collapsed": False, "bypassed": False},
        "runtime_meta": {"step_id": "normalization", "node_impl_version": "2.0.0"},
    }
    workflow["nodes"].append(norm_meta_node)
    # reconnect: corpus_input -> normalize_metadata -> clean_text
    workflow["edges"] = [
        edge for edge in workflow["edges"]
        if not (edge["from_node"] == "node-corpus-input" and edge["to_node"] == "node-clean-text")
    ]
    workflow["edges"].append({
        "edge_id": "edge-corpus-to-normalize-metadata",
        "from_node": "node-corpus-input",
        "from_port": "corpus",
        "to_node": "node-normalize-metadata",
        "to_port": "corpus_in",
    })
    workflow["edges"].append({
        "edge_id": "edge-normalize-metadata-to-clean",
        "from_node": "node-normalize-metadata",
        "from_port": "normalized_corpus",
        "to_node": "node-clean-text",
        "to_port": "corpus_in",
    })

    manifest, _processed_corpus, run_record = run_project_workflow(project_dir, manifest, corpus)

    assert run_record["status"] == "completed"
    doc = _processed_corpus[0]
    assert doc["institution"] == "University A"
    assert doc["country_or_region"] == "China"
    assert doc["year"] == 2024
    assert doc["extra_metadata"]["metadata_normalization_audit"] is True
    assert manifest["results"]["metadata_audit_table"]
    audit = manifest["results"]["metadata_audit_table"]
    assert any(row["field"] == "institution" for row in audit)
    assert any(row["field"] == "country_or_region" for row in audit)
    assert any(row["field"] == "year" for row in audit)
