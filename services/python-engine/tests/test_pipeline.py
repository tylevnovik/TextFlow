from __future__ import annotations

from uuid import uuid4

from app.defaults import default_import_template
from app.ingestion import ensure_sample_files, import_files
from app.pipeline import (
    apply_dictionary,
    apply_normalization,
    institution_keyword_and_topic,
    nmf_topic_model,
    run_project_pipeline,
    tfidf_analysis,
)
from app.project_store import create_project, save_project


def test_pipeline_end_to_end_generates_outputs(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest = create_project(project_name, "pipeline test project")
    corpus, source_files, _issues = import_files(ensure_sample_files(), default_import_template(), project_dir=project_dir)
    manifest["source_files"] = source_files
    manifest, corpus, run_record = run_project_pipeline(project_dir, manifest, corpus)
    save_project(project_dir, manifest, corpus)

    assert run_record["status"] == "completed"
    assert manifest["results"]["frequency_table"]
    assert manifest["results"]["keyword_cluster_result"]
    assert manifest["results"]["report_files"]
    assert run_record["workflow_id"] == manifest["active_workflow_id"]
    assert run_record["workflow_name"] == manifest["workflow_definitions"][0]["name"]
    assert run_record["workflow_hash"].startswith("sha256:")
    for relative_path in manifest["results"]["report_files"]:
        assert (project_dir / relative_path).exists()
    assert any(path.endswith("keyword_wordcloud.png") for path in manifest["results"]["report_files"])
    assert any(path.endswith("project_keywords.png") for path in manifest["results"]["report_files"])
    assert any(path.endswith("institution_topic_heatmap.png") for path in manifest["results"]["report_files"])


def test_pipeline_respects_disabled_analysis_and_export_steps(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest = create_project(project_name, "pipeline step control")
    corpus, source_files, _issues = import_files(ensure_sample_files(), default_import_template(), project_dir=project_dir)
    manifest["source_files"] = source_files
    manifest["pipeline"]["enabled_steps"] = [
        "ingestion",
        "cleaning",
        "normalization",
        "tokenization",
        "dictionary_application",
        "filtering",
    ]
    manifest["pipeline"]["execution_order"] = manifest["pipeline"]["enabled_steps"][:]
    manifest, corpus, run_record = run_project_pipeline(project_dir, manifest, corpus)
    save_project(project_dir, manifest, corpus)

    run_root = project_dir / "runs" / run_record["run_id"]
    assert manifest["results"]["frequency_table"] == []
    assert manifest["results"]["report_files"] == []
    assert (run_root / "params_snapshot.json").exists()
    assert (run_root / "logs.json").exists()
    assert (run_root / "logs.txt").exists()
    assert (run_root / "corpus_snapshot.json").exists()
    assert not (run_root / "outputs" / "frequency_table.csv").exists()
    assert any("分析步骤已禁用" in entry["message"] for entry in run_record["logs"])


def test_pipeline_export_options_control_written_artifacts(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest = create_project(project_name, "pipeline export control")
    corpus, source_files, _issues = import_files(ensure_sample_files(), default_import_template(), project_dir=project_dir)
    manifest["source_files"] = source_files
    manifest["pipeline"]["export"] = {
        "export_csv": True,
        "export_xlsx": True,
        "export_png": False,
        "export_html_report": False,
        "include_audit": False,
    }
    manifest, corpus, run_record = run_project_pipeline(project_dir, manifest, corpus)
    save_project(project_dir, manifest, corpus)

    run_root = project_dir / "runs" / run_record["run_id"]
    assert (run_root / "outputs" / "frequency_table.csv").exists()
    assert (run_root / "outputs" / "analysis_bundle.xlsx").exists()
    assert not (run_root / "outputs" / "audit_table.csv").exists()
    assert not (run_root / "charts" / "frequency_top_terms.png").exists()
    assert not (run_root / "charts" / "keyword_wordcloud.png").exists()
    assert not (run_root / "charts" / "project_keywords.png").exists()
    assert not (run_root / "charts" / "institution_topic_heatmap.png").exists()
    assert not (run_root / "report" / "report.html").exists()


def test_pipeline_png_exports_include_visualizations_and_watermark_options(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest = create_project(project_name, "pipeline png export test")
    corpus, source_files, _issues = import_files(ensure_sample_files(), default_import_template(), project_dir=project_dir)
    manifest["source_files"] = source_files
    manifest["pipeline"]["export"] = {
        "export_csv": False,
        "export_xlsx": False,
        "export_png": True,
        "export_html_report": False,
        "include_audit": False,
        "chart_dpi": 360,
        "watermark_enabled": True,
        "watermark_text": "内部汇报",
    }
    manifest, corpus, run_record = run_project_pipeline(project_dir, manifest, corpus)
    save_project(project_dir, manifest, corpus)

    run_root = project_dir / "runs" / run_record["run_id"]
    assert (run_root / "charts" / "frequency_top_terms.png").exists()
    assert (run_root / "charts" / "keyword_wordcloud.png").exists()
    assert (run_root / "charts" / "project_keywords.png").exists()
    assert (run_root / "charts" / "institution_topic_heatmap.png").exists()
    assert (run_root / "charts" / "document_clusters.png").exists()


def test_pipeline_scope_filters_subset_and_records_summary(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest = create_project(project_name, "pipeline scope test")
    corpus, source_files, _issues = import_files(ensure_sample_files(), default_import_template(), project_dir=project_dir)
    manifest["source_files"] = source_files
    manifest["pipeline"]["run_scope"] = {
        "mode": "filtered_subset",
        "source_values": ["Journal of Digital Humanities"],
        "institution_values": [],
        "category_values": [],
        "year_from": 2024,
        "year_to": 2024,
        "selected_doc_ids": [],
    }
    manifest["pipeline"]["recipe_id"] = "keyword_topic"
    manifest["pipeline"]["output_bundle_id"] = "charts_and_report"

    manifest, processed_corpus, run_record = run_project_pipeline(project_dir, manifest, corpus)
    save_project(project_dir, manifest, processed_corpus)

    assert run_record["status"] == "completed"
    assert run_record["processed_document_count"] == 1
    assert "年份=2024-2024" in run_record["run_scope_summary"]
    assert run_record["workflow_id"] == manifest["active_workflow_id"]
    assert run_record["recipe_id"] == "keyword_topic"
    assert run_record["output_bundle_id"] == "charts_and_report"
    assert run_record["output_summary"]
    assert {row["doc_id"] for row in manifest["results"]["term_document_table"]} == {"DOC-001"}
    assert {row["year"] for row in manifest["results"]["term_year_table"]} == {2024}


def test_pipeline_uses_active_workflow_even_if_pipeline_snapshot_is_stale(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest = create_project(project_name, "workflow runtime compile test")
    corpus, source_files, _issues = import_files(ensure_sample_files(), default_import_template(), project_dir=project_dir)
    manifest["source_files"] = source_files
    manifest["pipeline"]["run_scope"]["mode"] = "all_documents"
    manifest["pipeline"]["recipe_id"] = "standard_analysis"
    manifest["pipeline"]["output_bundle_id"] = "full_report"

    active_workflow = manifest["workflow_definitions"][0]
    active_workflow["source"] = "manual"
    for node in active_workflow["nodes"]:
        if node["node_type"] == "corpus_input":
            node["config"] = {
                **node["config"],
                "mode": "filtered_subset",
                "source_values": ["Journal of Digital Humanities"],
                "institution_values": [],
                "category_values": [],
                "year_from": 2024,
                "year_to": 2024,
                "selected_doc_ids": [],
            }
        elif node["node_type"] == "filter_terms":
            node["config"]["min_term_frequency"] = 2
    active_workflow["meta"]["template_id"] = "keyword_topic"
    active_workflow["meta"]["output_bundle_id"] = "charts_and_report"

    manifest, processed_corpus, run_record = run_project_pipeline(project_dir, manifest, corpus)
    save_project(project_dir, manifest, processed_corpus)

    assert run_record["processed_document_count"] == 1
    assert run_record["recipe_id"] == "keyword_topic"
    assert run_record["output_bundle_id"] == "charts_and_report"
    assert manifest["pipeline"]["run_scope"]["mode"] == "filtered_subset"
    assert manifest["pipeline"]["filtering"]["min_term_frequency"] == 2


def test_pipeline_respects_disconnected_active_workflow_edges(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest = create_project(project_name, "workflow edge runtime test")
    corpus, source_files, _issues = import_files(ensure_sample_files(), default_import_template(), project_dir=project_dir)
    manifest["source_files"] = source_files

    active_workflow = manifest["workflow_definitions"][0]
    active_workflow["source"] = "manual"
    active_workflow["edges"] = [
        edge
        for edge in active_workflow["edges"]
        if not str(edge["to_node"]).startswith("node-save-")
    ]

    manifest, processed_corpus, run_record = run_project_pipeline(project_dir, manifest, corpus)
    save_project(project_dir, manifest, processed_corpus)

    assert "export" not in manifest["pipeline"]["enabled_steps"]
    assert manifest["results"]["report_files"] == []
    assert any("导出步骤已禁用" in entry["message"] for entry in run_record["logs"])


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


def test_pipeline_logs_yake_and_nmf_methods(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest = create_project(project_name, "analysis method log test")
    corpus, source_files, _issues = import_files(ensure_sample_files(), default_import_template(), project_dir=project_dir)
    manifest["source_files"] = source_files
    manifest, corpus, run_record = run_project_pipeline(project_dir, manifest, corpus)
    save_project(project_dir, manifest, corpus)

    assert any("YAKE" in entry["message"] and "NMF" in entry["message"] for entry in run_record["logs"])


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
    assert audits[0]["action"] == "keep"
