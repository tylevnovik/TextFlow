from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from app.builtin_dictionary_data import builtin_dictionary_table_specs
from app.dag_runtime import _export_selection_from_active_graph
from app.defaults import default_import_template, empty_result_bundle
from app.ingestion import ensure_sample_files, import_files
from app.node_registry import build_node_registry
from app.pipeline import (
    apply_dictionary,
    apply_normalization,
    institution_keyword_and_topic,
    nmf_topic_model,
    run_project_pipeline,
    tfidf_analysis,
)
from app.project_store import create_project, load_project, normalize_dictionary_set_record, save_project
from app.reporting import build_html_report


def test_pipeline_end_to_end_generates_outputs(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest = create_project(project_name, "pipeline test project")
    corpus, source_files, _issues = import_files(ensure_sample_files(), default_import_template(), project_dir=project_dir)
    manifest["source_files"] = source_files
    manifest, corpus, run_record = run_project_pipeline(project_dir, manifest, corpus)
    save_project(project_dir, manifest, corpus)

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


def test_manual_workflow_native_dag_hits_node_cache_on_second_run(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest = create_project(project_name, "native dag cache test")
    corpus, source_files, _issues = import_files(ensure_sample_files(), default_import_template(), project_dir=project_dir)
    manifest["source_files"] = source_files
    manifest["workflow_definitions"][0]["source"] = "manual"

    manifest, processed_corpus, first_run = run_project_pipeline(project_dir, manifest, corpus)
    save_project(project_dir, manifest, processed_corpus)

    manifest, reloaded_corpus = load_project(project_dir)
    manifest["workflow_definitions"][0]["source"] = "manual"
    manifest, processed_corpus, second_run = run_project_pipeline(project_dir, manifest, reloaded_corpus)

    assert first_run.get("node_runs")
    assert second_run.get("node_runs")
    assert any(node_run["cache_hit"] for node_run in second_run["node_runs"])
    assert any(node_run["status"] == "cached" for node_run in second_run["node_runs"])


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


def test_manual_workflow_merge_corpora_executes_native_dag(isolated_workspace):
    project_name = f"pytest-{uuid4().hex[:8]}"
    project_dir, manifest = create_project(project_name, "workflow merge runtime test")
    corpus, source_files, _issues = import_files(ensure_sample_files(), default_import_template(), project_dir=project_dir)
    manifest["source_files"] = source_files

    active_workflow = manifest["workflow_definitions"][0]
    active_workflow["source"] = "manual"
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

    manifest, processed_corpus, run_record = run_project_pipeline(project_dir, manifest, corpus)
    save_project(project_dir, manifest, processed_corpus)

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
        "pipeline": {"export": {"export_png": True}},
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
