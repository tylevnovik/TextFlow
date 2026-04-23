from __future__ import annotations

import json
import shutil
import textwrap

import pytest

from app.cli import (
    action_create_project,
    action_create_project_from_template,
    action_delete_corpus_document,
    action_delete_project,
    action_export_dictionary_sheet,
    action_export_project,
    action_duplicate_project,
    action_export_project_backup,
    action_import_dictionary_sheet,
    action_import_project_package,
    action_import_project_files,
    action_list_import_templates,
    action_list_project_templates,
    action_load_import_template,
    action_load_workspace,
    action_open_project,
    action_save_import_template,
    action_save_project,
    action_save_project_template,
    action_update_corpus_document,
    normalize_corpus_document,
)
from app.defaults import compile_runtime_profile_from_workflow, default_runtime_profile, normalize_workflow_edges
from app.node_registry import build_node_registry
from app.project_store import CORPUS_FILENAME, PROJECT_FILENAME, create_project, find_project_dir, load_project, load_workspace_snapshot, load_workspace_state, save_project, workspace_state_path


@pytest.fixture(scope="session")
def workspace_cli_template(tmp_path_factory):
    workspace = tmp_path_factory.mktemp("workspace-cli-template")
    env = pytest.MonkeyPatch()
    try:
        env.setenv("TEXTFLOW_WORKSPACE_ROOT", str(workspace))
        action_load_workspace()
    finally:
        env.undo()
    return workspace


@pytest.fixture
def isolated_workspace(monkeypatch, scratch_dir, workspace_cli_template):
    workspace = scratch_dir / "workspace"
    shutil.copytree(workspace_cli_template, workspace, dirs_exist_ok=True)
    monkeypatch.setenv("TEXTFLOW_WORKSPACE_ROOT", str(workspace))
    return workspace


def test_workspace_cli_persists_current_project_and_recent_order(isolated_workspace):
    bootstrap_snapshot = action_load_workspace()
    assert workspace_state_path().exists()
    bootstrap_id = bootstrap_snapshot["current_project"]["id"]

    created = action_create_project({"name": "真实项目 A", "description": "test"})
    assert load_workspace_state()["current_project_id"] == created["id"]

    action_open_project({"project_id": bootstrap_id})
    assert load_workspace_state()["current_project_id"] == bootstrap_id

    duplicated = action_duplicate_project({"project_id": bootstrap_id, "name": "真实项目 A 副本"})
    assert load_workspace_state()["current_project_id"] == duplicated["id"]

    workspace_state = load_workspace_state()
    assert workspace_state["current_project_id"] == duplicated["id"]
    assert workspace_state["recent_project_ids"][0] == duplicated["id"]
    assert bootstrap_id in workspace_state["recent_project_ids"]
    assert created["id"] in workspace_state["recent_project_ids"]


def test_workspace_snapshot_only_fully_loads_current_project(isolated_workspace, monkeypatch):
    first = action_create_project({"name": "性能测试 A", "description": "A"})
    second = action_create_project({"name": "性能测试 B", "description": "B"})
    load_calls: list[str] = []

    original_load_project = load_project

    def tracked_load_project(project_dir):
        load_calls.append(str(project_dir))
        return original_load_project(project_dir)

    monkeypatch.setattr("app.project_store.load_project", tracked_load_project)

    snapshot = load_workspace_snapshot()

    assert snapshot["current_project"] is not None
    assert snapshot["current_project"]["id"] == second["id"]
    assert len(snapshot["recent_projects"]) >= 2
    assert len(load_calls) == 1


def test_bootstrap_project_guides_first_run(isolated_workspace):
    snapshot = action_load_workspace()
    sample_names = {project["name"] for project in snapshot["recent_projects"] if "示例项目" in project["name"]}

    assert snapshot["current_project"]["name"] == "示例项目 - 学术摘要机构主题"
    assert len(sample_names) == 3
    assert {
        "示例项目 - 学术摘要机构主题",
        "示例项目 - 新闻组主题聚类",
        "示例项目 - 短信词频与共现",
    }.issubset(sample_names)
    assert "OpenAlex" in snapshot["current_project"]["description"]
    assert len(snapshot["corpus"]) >= 6
    assert snapshot["selected_run"] is None
    assert snapshot["current_project"]["results"]["frequency_table"] == []
    assert snapshot["current_project"]["run_history"] == []
    assert any(
        len(str(item.get("raw_text") or "")) > len(str(item.get("title") or ""))
        for item in snapshot["corpus"]
    )
    assert snapshot["node_definitions"]
    assert any(node["type"] == "corpus_input" for node in snapshot["node_definitions"])
    assert any(node["type"] == "save_html_report" for node in snapshot["node_definitions"])


def test_workspace_snapshot_loads_python_node_plugins(isolated_workspace, scratch_dir, monkeypatch):
    plugin_root = scratch_dir / "plugins" / "nodes"
    plugin_root.mkdir(parents=True, exist_ok=True)
    (plugin_root / "demo_plugin.py").write_text(
        textwrap.dedent(
            """
            def _compile(context, node):
                context.merge_section("analysis", {"top_n": int(node.get("config", {}).get("top_n", 77))})
                context.enable_step("analysis")


            def register_nodes(builder):
                builder.register_node(
                    {
                        "type": "demo_plugin_node",
                        "title": "Demo Plugin Node",
                        "category": "analysis",
                        "description": "Loaded from plugins/nodes.",
                        "inputs": [],
                        "outputs": [{"port_id": "plugin_out", "port_type": "KeywordTable", "label": "插件输出"}],
                        "params": [{"param_id": "top_n", "label": "Top N", "kind": "number", "default_value": 77}],
                        "runtime": {
                            "step_id": "analysis",
                            "executor": "plugin.demo",
                            "cacheable": False,
                            "previewable": False,
                            "output_node": False,
                        },
                    },
                    compiler=_compile,
                    executor=lambda *_args, **_kwargs: {"status": "ok"},
                )
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEXTFLOW_NODE_PLUGIN_DIR", str(plugin_root))

    snapshot = action_load_workspace()
    assert any(node["type"] == "demo_plugin_node" for node in snapshot["node_definitions"])

    compiled = compile_runtime_profile_from_workflow(
        {
            "nodes": [
                {
                    "node_id": "node-demo-plugin",
                    "node_type": "demo_plugin_node",
                    "label": "Demo Plugin Node",
                    "inputs": [],
                    "outputs": [{"port_id": "plugin_out", "port_type": "KeywordTable", "label": "插件输出"}],
                    "config": {"top_n": 88},
                    "ui_state": {"collapsed": False, "bypassed": False},
                    "runtime_meta": {"node_impl_version": "1.0.0"},
                }
            ],
            "edges": [],
            "meta": {},
        },
        default_runtime_profile(),
    )
    assert compiled["analysis"]["top_n"] == 88
    assert "analysis" in compiled["enabled_steps"]


def test_new_project_has_default_workflow_definition(isolated_workspace):
    project_dir, manifest = create_project("工作流基础项目", "workflow foundation")
    workflow = manifest["workflow_definitions"][0]
    node_types = {node["node_type"] for node in workflow["nodes"]}

    assert manifest["workflow_definitions"]
    assert manifest["active_workflow_id"] == workflow["workflow_id"]
    assert workflow["graph_mode"] == "dag"
    assert "corpus_input" in node_types
    assert "dictionary_input" in node_types
    assert "term_document_analysis" in node_types
    assert "feature_term_selection" in node_types
    assert "keyword_extraction" in node_types
    assert "institution_keyword_analysis" in node_types
    assert "document_clustering" in node_types
    assert "save_html_report" in node_types
    assert "analyze_corpus" not in node_types
    assert "export_results" not in node_types


def test_new_project_snapshot_contains_resource_collections(isolated_workspace):
    created = action_create_project({"name": "资源集合项目", "description": "resource schema"})

    snapshot = action_load_workspace()
    current_project = snapshot["current_project"]

    assert current_project is not None
    assert current_project["id"] == created["id"]
    assert current_project["corpus_resources"] == []
    assert current_project["corpus_views"] == []
    assert current_project["ingestion_specs"] == []
    assert current_project["artifact_records"] == []
    assert current_project["review_tasks"] == []
    assert current_project["experiment_specs"] == []
    assert current_project["shared_resource_refs"] == []


def test_project_storage_compacts_builtin_dictionary_entries_and_rehydrates_on_load(isolated_workspace):
    project_dir, _manifest = create_project("词表轻量存储项目", "dictionary storage")

    raw_manifest = json.loads((project_dir / PROJECT_FILENAME).read_text(encoding="utf-8"))
    assert "sheets" not in raw_manifest["dictionary_set"]

    raw_stopword_collection = raw_manifest["dictionary_set"]["collections"]["stopwords"]
    raw_stopword_table = next(table for table in raw_stopword_collection["tables"] if table["id"] == "builtin-stopwords-zh")
    assert raw_stopword_table["entries"] == []

    manifest, corpus = load_project(project_dir)
    hydrated_stopword_table = next(
        table
        for table in manifest["dictionary_set"]["collections"]["stopwords"]["tables"]
        if table["id"] == "builtin-stopwords-zh"
    )
    hydrated_lookup = {entry["source"]: entry for entry in hydrated_stopword_table["entries"]}
    assert len(hydrated_lookup) >= 700
    assert "的" in hydrated_lookup

    hydrated_lookup["的"]["hits"] = 9
    save_project(project_dir, manifest, corpus, already_normalized=True)

    raw_manifest = json.loads((project_dir / PROJECT_FILENAME).read_text(encoding="utf-8"))
    raw_stopword_collection = raw_manifest["dictionary_set"]["collections"]["stopwords"]
    raw_stopword_table = next(table for table in raw_stopword_collection["tables"] if table["id"] == "builtin-stopwords-zh")
    assert len(raw_stopword_table["entries"]) == 1
    assert raw_stopword_table["entries"][0]["source"] == "的"
    assert raw_stopword_table["entries"][0]["hits"] == 9

    reloaded_manifest, _ = load_project(project_dir)
    reloaded_entries = reloaded_manifest["dictionary_set"]["sheets"]["stopwords"]["entries"]
    reloaded_lookup = {entry["source"]: entry for entry in reloaded_entries}
    assert len(reloaded_lookup) > 1500
    assert reloaded_lookup["的"]["hits"] == 9
    assert "about" in reloaded_lookup


def test_workspace_snapshot_backfills_legacy_project_summary_counts(isolated_workspace):
    snapshot = action_load_workspace()
    sample_project = next(project for project in snapshot["recent_projects"] if "示例项目" in project["name"])
    project_dir = find_project_dir(sample_project["id"])
    assert project_dir is not None

    raw_manifest = json.loads((project_dir / PROJECT_FILENAME).read_text(encoding="utf-8"))
    raw_manifest.pop("document_count", None)
    raw_manifest.pop("run_count", None)
    (project_dir / PROJECT_FILENAME).write_text(json.dumps(raw_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    refreshed = load_workspace_snapshot()
    refreshed_summary = next(project for project in refreshed["recent_projects"] if project["id"] == sample_project["id"])
    reloaded_manifest = json.loads((project_dir / PROJECT_FILENAME).read_text(encoding="utf-8"))

    assert refreshed_summary["document_count"] > 0
    assert refreshed_summary["run_count"] == 0
    assert reloaded_manifest["document_count"] == refreshed_summary["document_count"]
    assert reloaded_manifest["run_count"] == refreshed_summary["run_count"]


def test_builtin_toolbox_nodes_have_registered_compilers_and_executors():
    registry = build_node_registry(default_runtime_profile())
    visible_definitions = [
        definition
        for definition in registry.definitions
        if not definition.get("hidden_from_toolbox") and definition.get("category") != "utility"
    ]

    for definition in visible_definitions:
        node_type = str(definition["type"])
        runtime = definition.get("runtime") or {}
        executor_id = str(runtime.get("executor") or "")
        assert node_type in registry.compilers, f"{node_type} 缺少 compiler 注册"
        assert executor_id in registry.executors, f"{node_type} 缺少 executor 注册"


def test_compile_runtime_profile_from_workflow_scopes_analysis_outputs_to_connected_nodes():
    compiled = compile_runtime_profile_from_workflow(
        {
            "nodes": [
                {
                    "node_id": "node-corpus",
                    "node_type": "corpus_input",
                    "label": "语料输入",
                    "inputs": [],
                    "outputs": [{"port_id": "corpus", "port_type": "CorpusTable", "label": "语料"}],
                    "config": {"mode": "all_documents", "source_values": [], "institution_values": [], "category_values": [], "selected_doc_ids": []},
                    "ui_state": {"collapsed": False, "bypassed": False},
                    "runtime_meta": {"node_impl_version": "2.0.0"},
                },
                {
                    "node_id": "node-clean",
                    "node_type": "clean_text",
                    "label": "文本清洗",
                    "inputs": [{"port_id": "corpus_in", "port_type": "CorpusTable", "label": "语料输入"}],
                    "outputs": [{"port_id": "clean_corpus", "port_type": "CleanCorpus", "label": "清洗语料"}],
                    "config": {},
                    "ui_state": {"collapsed": False, "bypassed": False},
                    "runtime_meta": {"node_impl_version": "2.0.0"},
                },
                {
                    "node_id": "node-normalize",
                    "node_type": "normalize_text",
                    "label": "文本标准化",
                    "inputs": [{"port_id": "clean_corpus_in", "port_type": "CleanCorpus", "label": "清洗语料"}],
                    "outputs": [{"port_id": "normalized_corpus", "port_type": "NormalizedCorpus", "label": "标准化语料"}],
                    "config": {},
                    "ui_state": {"collapsed": False, "bypassed": False},
                    "runtime_meta": {"node_impl_version": "2.0.0"},
                },
                {
                    "node_id": "node-tokenize",
                    "node_type": "tokenize",
                    "label": "分词",
                    "inputs": [{"port_id": "normalized_corpus_in", "port_type": "NormalizedCorpus", "label": "标准化语料"}],
                    "outputs": [{"port_id": "token_corpus", "port_type": "TokenCorpus", "label": "Token 语料"}],
                    "config": {},
                    "ui_state": {"collapsed": False, "bypassed": False},
                    "runtime_meta": {"node_impl_version": "2.0.0"},
                },
                {
                    "node_id": "node-token-filtered",
                    "node_type": "filter_terms",
                    "label": "过滤词项",
                    "inputs": [{"port_id": "token_corpus_in", "port_type": "TokenCorpus", "label": "Token 输入"}],
                    "outputs": [{"port_id": "filtered_token_corpus", "port_type": "FilteredTokenCorpus", "label": "分析词项"}],
                    "config": {"min_term_frequency": 2},
                    "ui_state": {"collapsed": False, "bypassed": False},
                    "runtime_meta": {"node_impl_version": "2.0.0"},
                },
                {
                    "node_id": "node-feature-terms",
                    "node_type": "feature_term_selection",
                    "label": "特征词筛选",
                    "inputs": [{"port_id": "token_corpus_in", "port_type": "FilteredTokenCorpus", "label": "分析词项"}],
                    "outputs": [{"port_id": "feature_term_table", "port_type": "FeatureTermTable", "label": "特征词表"}],
                    "config": {"feature_term_count": "500"},
                    "ui_state": {"collapsed": False, "bypassed": False},
                    "runtime_meta": {"node_impl_version": "2.0.0"},
                },
                {
                    "node_id": "node-clusters",
                    "node_type": "keyword_clustering",
                    "label": "关键词聚类",
                    "inputs": [{"port_id": "feature_term_table_in", "port_type": "FeatureTermTable", "label": "特征词输入"}],
                    "outputs": [{"port_id": "keyword_cluster_table", "port_type": "KeywordClusterTable", "label": "关键词聚类表"}],
                    "config": {"keyword_cluster_k": 6, "topic_model_k": 6},
                    "ui_state": {"collapsed": False, "bypassed": False},
                    "runtime_meta": {"node_impl_version": "2.0.0"},
                },
                {
                    "node_id": "node-save-xlsx",
                    "node_type": "save_xlsx",
                    "label": "保存 XLSX",
                    "inputs": [{"port_id": "table_in", "port_type": "AnyTable", "label": "表格输入", "allow_multiple": True}],
                    "outputs": [{"port_id": "artifact", "port_type": "ExportArtifact", "label": "导出产物"}],
                    "config": {"file_prefix": "tables"},
                    "ui_state": {"collapsed": False, "bypassed": False},
                    "runtime_meta": {"node_impl_version": "2.0.0"},
                },
            ],
            "edges": [
                {"edge_id": "edge-0", "from_node": "node-corpus", "from_port": "corpus", "to_node": "node-clean", "to_port": "corpus_in"},
                {"edge_id": "edge-0b", "from_node": "node-clean", "from_port": "clean_corpus", "to_node": "node-normalize", "to_port": "clean_corpus_in"},
                {"edge_id": "edge-0c", "from_node": "node-normalize", "from_port": "normalized_corpus", "to_node": "node-tokenize", "to_port": "normalized_corpus_in"},
                {"edge_id": "edge-0d", "from_node": "node-tokenize", "from_port": "token_corpus", "to_node": "node-token-filtered", "to_port": "token_corpus_in"},
                {"edge_id": "edge-1", "from_node": "node-token-filtered", "from_port": "filtered_token_corpus", "to_node": "node-feature-terms", "to_port": "token_corpus_in"},
                {"edge_id": "edge-2", "from_node": "node-feature-terms", "from_port": "feature_term_table", "to_node": "node-clusters", "to_port": "feature_term_table_in"},
                {"edge_id": "edge-3", "from_node": "node-clusters", "from_port": "keyword_cluster_table", "to_node": "node-save-xlsx", "to_port": "table_in"},
            ],
            "meta": {},
        },
        default_runtime_profile(),
    )

    assert "analysis" in compiled["enabled_steps"]
    assert compiled["analysis"]["include_feature_term_selection"] is True
    assert compiled["analysis"]["include_keyword_clustering"] is True
    assert compiled["analysis"]["include_keyword_extraction"] is False
    assert compiled["analysis"]["include_frequency_statistics"] is False
    assert compiled["analysis"]["feature_term_count"] == 500
    assert compiled["analysis"]["keyword_cluster_k"] == 6


def test_compile_runtime_profile_from_workflow_keeps_document_clustering_edges_to_export_sinks():
    workflow_definition = {
        "nodes": [
            {
                "node_id": "node-corpus",
                "node_type": "corpus_input",
                "label": "语料输入",
                "inputs": [],
                "outputs": [{"port_id": "corpus", "port_type": "CorpusTable", "label": "语料"}],
                "config": {
                    "mode": "all_documents",
                    "source_values": [],
                    "institution_values": [],
                    "category_values": [],
                    "selected_doc_ids": [],
                },
                "ui_state": {"collapsed": False, "bypassed": False},
                "runtime_meta": {"node_impl_version": "2.0.0"},
            },
            {
                "node_id": "node-clean",
                "node_type": "clean_text",
                "label": "文本清洗",
                "inputs": [{"port_id": "corpus_in", "port_type": "CorpusTable", "label": "语料输入"}],
                "outputs": [{"port_id": "clean_corpus", "port_type": "CleanCorpus", "label": "清洗语料"}],
                "config": {},
                "ui_state": {"collapsed": False, "bypassed": False},
                "runtime_meta": {"node_impl_version": "2.0.0"},
            },
            {
                "node_id": "node-normalize",
                "node_type": "normalize_text",
                "label": "文本标准化",
                "inputs": [{"port_id": "clean_corpus_in", "port_type": "CleanCorpus", "label": "清洗语料"}],
                "outputs": [{"port_id": "normalized_corpus", "port_type": "NormalizedCorpus", "label": "标准化语料"}],
                "config": {},
                "ui_state": {"collapsed": False, "bypassed": False},
                "runtime_meta": {"node_impl_version": "2.0.0"},
            },
            {
                "node_id": "node-tokenize",
                "node_type": "tokenize",
                "label": "分词",
                "inputs": [{"port_id": "normalized_corpus_in", "port_type": "NormalizedCorpus", "label": "标准化语料"}],
                "outputs": [{"port_id": "token_corpus", "port_type": "TokenCorpus", "label": "Token 语料"}],
                "config": {},
                "ui_state": {"collapsed": False, "bypassed": False},
                "runtime_meta": {"node_impl_version": "2.0.0"},
            },
            {
                "node_id": "node-token-filtered",
                "node_type": "filter_terms",
                "label": "过滤词项",
                "inputs": [{"port_id": "token_corpus_in", "port_type": "TokenCorpus", "label": "Token 输入"}],
                "outputs": [{"port_id": "filtered_token_corpus", "port_type": "FilteredTokenCorpus", "label": "分析词项"}],
                "config": {"min_term_frequency": 2},
                "ui_state": {"collapsed": False, "bypassed": False},
                "runtime_meta": {"node_impl_version": "2.0.0"},
            },
            {
                "node_id": "node-document-clusters",
                "node_type": "document_clustering",
                "label": "文档聚类",
                "inputs": [{"port_id": "token_corpus_in", "port_type": "FilteredTokenCorpus", "label": "分析词项"}],
                "outputs": [{"port_id": "document_cluster_table", "port_type": "DocumentClusterTable", "label": "文档聚类表"}],
                "config": {"document_cluster_k": 7},
                "ui_state": {"collapsed": False, "bypassed": False},
                "runtime_meta": {"node_impl_version": "2.0.0"},
            },
            {
                "node_id": "node-save-csv",
                "node_type": "save_csv",
                "label": "保存 CSV",
                "inputs": [{"port_id": "table_in", "port_type": "AnyTable", "label": "表格输入", "allow_multiple": True}],
                "outputs": [{"port_id": "artifact", "port_type": "ExportArtifact", "label": "导出产物"}],
                "config": {"file_prefix": "tables"},
                "ui_state": {"collapsed": False, "bypassed": False},
                "runtime_meta": {"node_impl_version": "2.0.0"},
            },
            {
                "node_id": "node-save-png",
                "node_type": "save_png",
                "label": "保存 PNG",
                "inputs": [{"port_id": "render_in", "port_type": "AnyRenderable", "label": "图像输入", "allow_multiple": True}],
                "outputs": [{"port_id": "artifact", "port_type": "ExportArtifact", "label": "导出产物"}],
                "config": {"chart_dpi": 320},
                "ui_state": {"collapsed": False, "bypassed": False},
                "runtime_meta": {"node_impl_version": "2.0.0"},
            },
            {
                "node_id": "node-save-report",
                "node_type": "save_html_report",
                "label": "保存 HTML 报告",
                "inputs": [{"port_id": "report_in", "port_type": "AnyAnalysisResult", "label": "报告输入", "allow_multiple": True}],
                "outputs": [{"port_id": "artifact", "port_type": "ExportArtifact", "label": "导出产物"}],
                "config": {"include_audit": False},
                "ui_state": {"collapsed": False, "bypassed": False},
                "runtime_meta": {"node_impl_version": "2.0.0"},
            },
        ],
        "edges": [
            {"edge_id": "edge-0", "from_node": "node-corpus", "from_port": "corpus", "to_node": "node-clean", "to_port": "corpus_in"},
            {"edge_id": "edge-1", "from_node": "node-clean", "from_port": "clean_corpus", "to_node": "node-normalize", "to_port": "clean_corpus_in"},
            {"edge_id": "edge-2", "from_node": "node-normalize", "from_port": "normalized_corpus", "to_node": "node-tokenize", "to_port": "normalized_corpus_in"},
            {"edge_id": "edge-3", "from_node": "node-tokenize", "from_port": "token_corpus", "to_node": "node-token-filtered", "to_port": "token_corpus_in"},
            {"edge_id": "edge-4", "from_node": "node-token-filtered", "from_port": "filtered_token_corpus", "to_node": "node-document-clusters", "to_port": "token_corpus_in"},
            {"edge_id": "edge-5", "from_node": "node-document-clusters", "from_port": "document_cluster_table", "to_node": "node-save-csv", "to_port": "table_in"},
            {"edge_id": "edge-6", "from_node": "node-document-clusters", "from_port": "document_cluster_table", "to_node": "node-save-png", "to_port": "render_in"},
            {"edge_id": "edge-7", "from_node": "node-document-clusters", "from_port": "document_cluster_table", "to_node": "node-save-report", "to_port": "report_in"},
        ],
        "meta": {},
    }

    normalized_edges = normalize_workflow_edges(workflow_definition, workflow_definition["nodes"])
    normalized_edge_pairs = {
        (edge["from_node"], edge["from_port"], edge["to_node"], edge["to_port"])
        for edge in normalized_edges
    }

    assert (
        "node-document-clusters",
        "document_cluster_table",
        "node-save-csv",
        "table_in",
    ) in normalized_edge_pairs
    assert (
        "node-document-clusters",
        "document_cluster_table",
        "node-save-png",
        "render_in",
    ) in normalized_edge_pairs
    assert (
        "node-document-clusters",
        "document_cluster_table",
        "node-save-report",
        "report_in",
    ) in normalized_edge_pairs

    compiled = compile_runtime_profile_from_workflow(workflow_definition, default_runtime_profile())

    assert "analysis" in compiled["enabled_steps"]
    assert "export" in compiled["enabled_steps"]
    assert compiled["analysis"]["include_document_clustering"] is True
    assert compiled["analysis"]["document_cluster_k"] == 7
    assert compiled["export"]["export_csv"] is True
    assert compiled["export"]["export_png"] is True
    assert compiled["export"]["export_html_report"] is True


def test_save_project_compiles_active_workflow_into_runtime_profile(isolated_workspace):
    project_dir, manifest = create_project("工作流编译项目", "workflow compiler")
    workflow = manifest["workflow_definitions"][0]
    workflow["source"] = "manual"
    removed_node_ids = set()

    for node in workflow["nodes"]:
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
        elif node["node_type"] == "clean_text":
            node["ui_state"]["bypassed"] = True
        elif node["node_type"] == "filter_terms":
            node["config"]["min_term_frequency"] = 3
        elif node["node_type"] == "save_html_report":
            node["config"]["include_audit"] = False
        elif node["node_type"] == "save_png":
            removed_node_ids.add(node["node_id"])

    workflow["nodes"] = [
        node
        for node in workflow["nodes"]
        if node["node_id"] not in removed_node_ids
    ]
    workflow["edges"] = [
        edge
        for edge in workflow["edges"]
        if edge["from_node"] not in removed_node_ids and edge["to_node"] not in removed_node_ids
    ]

    workflow["meta"]["template_id"] = "trend_scan"
    workflow["meta"]["output_bundle_id"] = "charts_and_report"

    action_save_project(manifest)
    reloaded_manifest, _ = load_project(project_dir)

    runtime_profile = compile_runtime_profile_from_workflow(reloaded_manifest["workflow_definitions"][0], default_runtime_profile())

    assert "workflow" not in reloaded_manifest
    assert runtime_profile["recipe_id"] == "trend_scan"
    assert runtime_profile["output_bundle_id"] == "charts_and_report"
    assert runtime_profile["run_scope"]["mode"] == "filtered_subset"
    assert runtime_profile["run_scope"]["year_from"] == 2024
    assert "cleaning" not in runtime_profile["enabled_steps"]
    assert runtime_profile["filtering"]["min_term_frequency"] == 3
    assert runtime_profile["export"]["include_audit"] is False
    assert runtime_profile["export"]["export_png"] is False


def test_save_project_respects_removed_optional_workflow_nodes(isolated_workspace):
    project_dir, manifest = create_project("工作流删节点项目", "workflow graph edit")
    workflow = manifest["workflow_definitions"][0]
    workflow["source"] = "manual"
    workflow["nodes"] = [
        node
        for node in workflow["nodes"]
        if node["node_type"] not in {"clean_text", "filter_terms"}
    ]
    workflow["edges"] = [
        edge
        for edge in workflow["edges"]
        if edge["from_node"] not in {"node-clean-text", "node-filter-terms"}
        and edge["to_node"] not in {"node-clean-text", "node-filter-terms"}
    ]

    action_save_project(manifest)
    reloaded_manifest, _ = load_project(project_dir)

    runtime_profile = compile_runtime_profile_from_workflow(reloaded_manifest["workflow_definitions"][0], default_runtime_profile())

    assert "cleaning" not in runtime_profile["enabled_steps"]
    assert "filtering" not in runtime_profile["enabled_steps"]


def test_save_project_disables_steps_when_workflow_inputs_are_disconnected(isolated_workspace):
    project_dir, manifest = create_project("工作流断线项目", "workflow disconnected edges")
    workflow = manifest["workflow_definitions"][0]
    workflow["source"] = "manual"
    workflow["edges"] = [
        edge
        for edge in workflow["edges"]
        if not (
            (edge["to_node"] == "node-apply-dictionary-rules" and edge["to_port"] == "dictionary_set_in")
            or str(edge["to_node"]).startswith("node-save-")
        )
    ]

    action_save_project(manifest)
    reloaded_manifest, _ = load_project(project_dir)

    runtime_profile = compile_runtime_profile_from_workflow(reloaded_manifest["workflow_definitions"][0], default_runtime_profile())

    assert "dictionary_application" not in runtime_profile["enabled_steps"]
    assert "export" not in runtime_profile["enabled_steps"]


def test_import_project_files_persists_corpus_and_copies_sources(isolated_workspace, scratch_dir):
    project_dir, manifest = create_project("导入项目", "import")
    source_path = scratch_dir / "custom.csv"
    source_path.write_text(
        "Title,Abstract,Published,Org,Notes\n项目化导入,需要复制进 tfproj,2026,上海交通大学,extra\n",
        encoding="utf-8",
    )

    result = action_import_project_files(
        {
            "project_id": manifest["id"],
            "file_paths": [str(source_path)],
            "import_template": {
                "id": "custom-template",
                "name": "自定义模板",
                "source_profile": "literature",
                "description": "test import",
                "field_mappings": [
                    {"source_field": "Title", "target_field": "title"},
                    {"source_field": "Abstract", "target_field": "raw_text"},
                    {"source_field": "Published", "target_field": "year"},
                    {"source_field": "Org", "target_field": "institution"},
                ],
                "text_build": {
                    "mode": "concat_fields",
                    "fields": ["Title", "Abstract"],
                    "delimiter": "\n\n",
                    "skip_empty": True,
                },
            },
        }
    )

    assert result["imported_documents"] == 1
    manifest, corpus = load_project(project_dir)
    assert len(corpus) == 1
    assert corpus[0]["raw_text"] == "项目化导入\n\n需要复制进 tfproj"
    assert corpus[0]["extra_metadata"]["Notes"] == "extra"
    assert manifest["source_files"]

    relative_path = manifest["source_files"][0]["relative_path"]
    assert relative_path.startswith("corpus/imported/")
    assert (project_dir / relative_path).exists()


def test_export_project_backup_creates_zip_archive(isolated_workspace):
    project_dir, manifest = create_project("备份项目", "backup")
    assert project_dir.exists()
    result = action_export_project_backup({"project_id": manifest["id"]})

    assert result["path"].endswith(".tfproj")
    assert "exports/backups/" in result["relative_path"]


def test_export_project_returns_export_dir_and_files(isolated_workspace):
    snapshot = action_load_workspace()
    project_id = snapshot["current_project"]["id"]

    result = action_export_project({"project_id": project_id, "formats": ["csv", "html"]})

    assert result["project_id"] == project_id
    assert result["relative_export_dir"].startswith("exports/")
    assert result["files"]
    assert all(item["path"].endswith(item["relative_path"].split("/")[-1]) for item in result["files"])


def test_import_project_package_restores_portable_project(isolated_workspace):
    project_dir, manifest = create_project("可携带项目", "portable")
    assert project_dir.exists()
    exported = action_export_project_backup({"project_id": manifest["id"]})

    imported = action_import_project_package({"path": exported["path"]})
    imported_project_dir = find_project_dir(imported["id"])
    assert imported_project_dir is not None

    manifest, corpus = load_project(imported_project_dir)
    assert manifest["name"].startswith("可携带项目")
    assert manifest["workflow_definitions"]
    assert manifest["active_workflow_id"]
    assert corpus == []


def test_delete_project_removes_workspace_entry_and_files(isolated_workspace):
    project_dir, manifest = create_project("待删除项目", "delete me")
    assert project_dir.exists()

    result = action_delete_project({"project_id": manifest["id"]})

    assert result["project_id"] == manifest["id"]
    assert not project_dir.exists()

    snapshot = action_load_workspace()
    assert all(item["id"] != manifest["id"] for item in snapshot["recent_projects"])
    assert snapshot["current_project"] is not None
    assert snapshot["current_project"]["id"] != manifest["id"]


def test_bootstrap_project_is_not_recreated_after_manual_delete(isolated_workspace):
    snapshot = action_load_workspace()
    bootstrap_ids = [project["id"] for project in snapshot["recent_projects"] if "示例项目" in project["name"]]

    for project_id in bootstrap_ids:
        action_delete_project({"project_id": project_id})
    after_delete = action_load_workspace()

    assert after_delete["recent_projects"] == []
    assert after_delete["current_project"] is None


def test_update_and_delete_corpus_document_persists_changes(isolated_workspace):
    project_dir, manifest = create_project("语料编辑项目", "edit corpus")
    corpus = [
        normalize_corpus_document(
            {
                "doc_id": "DOC-EDIT-001",
                "title": "原始标题",
                "raw_text": "原始内容",
                "year": 2024,
                "institution": "浙江大学",
                "source_profile": "generic",
            }
        )
    ]
    save_project(project_dir, manifest, corpus, already_normalized=True)
    assert project_dir is not None
    assert len(corpus) == 1
    document = corpus[0]

    updated = action_update_corpus_document(
        {
            "project_id": manifest["id"],
            "document": {
                **document,
                "title": "修改后的标题",
                "raw_text": "修改后的正文",
                "year": "2026",
            },
        }
    )
    assert updated["title"] == "修改后的标题"
    assert updated["raw_text"] == "修改后的正文"
    assert updated["year"] == 2026
    assert updated["tokens"] == []

    manifest, corpus = load_project(project_dir)
    assert corpus[0]["title"] == "修改后的标题"
    assert corpus[0]["raw_text"] == "修改后的正文"

    deleted = action_delete_corpus_document({"project_id": manifest["id"], "doc_id": corpus[0]["doc_id"]})
    assert deleted["document_count"] == 0

    manifest, corpus = load_project(project_dir)
    assert corpus == []
    assert manifest["source_files"] == []


def test_load_project_normalizes_run_intent_fields_from_workflow(isolated_workspace):
    project_dir, manifest = create_project("workflow 运行意图测试", "workflow manifest")
    corpus: list[dict[str, object]] = []
    manifest["workflow_definitions"][0]["meta"]["template_id"] = "keyword_topic"
    manifest["workflow_definitions"][0]["meta"]["output_bundle_id"] = "charts_and_report"
    manifest["run_history"] = [
        {
            "run_id": "run-workflow-only",
            "project_id": manifest["id"],
            "started_at": manifest["updated_at"],
            "ended_at": manifest["updated_at"],
            "status": "completed",
            "params_snapshot_path": "runs/run-legacy/params_snapshot.json",
            "artifacts": [],
            "logs": [],
        }
    ]
    (project_dir / PROJECT_FILENAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (project_dir / CORPUS_FILENAME).write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")

    reloaded_manifest, _ = load_project(project_dir)
    run_record = reloaded_manifest["run_history"][0]
    runtime_profile = compile_runtime_profile_from_workflow(reloaded_manifest["workflow_definitions"][0], default_runtime_profile())

    assert "workflow" not in reloaded_manifest
    assert runtime_profile["run_scope"]["mode"] == "all_documents"
    assert runtime_profile["recipe_id"] == "keyword_topic"
    assert runtime_profile["output_bundle_id"] == "charts_and_report"
    assert reloaded_manifest["workflow_definitions"]
    assert reloaded_manifest["active_workflow_id"] == reloaded_manifest["workflow_definitions"][0]["workflow_id"]
    assert run_record["processed_document_count"] == 0
    assert "项目内全部资料" in run_record["run_scope_summary"]
    assert run_record["workflow_version"] == reloaded_manifest["workflow_definitions"][0]["version"]
    assert run_record["workflow_id"] == reloaded_manifest["active_workflow_id"]
    assert run_record["workflow_name"] == reloaded_manifest["workflow_definitions"][0]["name"]
    assert run_record["workflow_hash"].startswith("sha256:")
    assert run_record["output_summary"]


def test_project_templates_and_import_templates_roundtrip(isolated_workspace):
    project_dir, manifest = create_project("模板来源项目", "template source")
    corpus: list[dict[str, object]] = []
    manifest["workflow_definitions"][0]["name"] = "模板流程"
    keyword_cluster_node = next(
        node
        for node in manifest["workflow_definitions"][0]["nodes"]
        if node["node_type"] == "keyword_clustering"
    )
    keyword_cluster_node["config"]["keyword_cluster_k"] = 6
    manifest["import_template"]["name"] = "WoS 导入模板"
    manifest["import_template"]["source_profile"] = "wos"
    manifest["dictionary_set"]["version"] = "2.0.0"
    save_project(project_dir, manifest, corpus, already_normalized=True)

    saved_import_template = action_save_import_template(
        {
            "project_id": manifest["id"],
            "name": "我的 WoS 模板",
            "description": "for tests",
        }
    )
    listed_import_templates = action_list_import_templates()
    loaded_import_template = action_load_import_template({"template_id": saved_import_template["id"]})

    assert any(item["id"] == saved_import_template["id"] for item in listed_import_templates)
    assert loaded_import_template["name"] == "我的 WoS 模板"
    assert loaded_import_template["source_profile"] == "wos"

    saved_project_template = action_save_project_template(
        {
            "project_id": manifest["id"],
            "name": "分析项目模板",
            "description": "template snapshot",
        }
    )
    listed_project_templates = action_list_project_templates()
    cloned = action_create_project_from_template(
        {
            "template_id": saved_project_template["id"],
            "name": "模板生成项目",
            "description": "from template",
        }
    )
    cloned_project_dir = find_project_dir(cloned["id"])
    assert cloned_project_dir is not None
    cloned_manifest, _ = load_project(cloned_project_dir)

    assert any(item["id"] == saved_project_template["id"] for item in listed_project_templates)
    assert cloned_manifest["workflow_definitions"][0]["name"] == "模板流程"
    assert cloned_manifest["workflow_definitions"]
    assert cloned_manifest["active_workflow_id"]
    cloned_runtime_profile = compile_runtime_profile_from_workflow(cloned_manifest["workflow_definitions"][0], default_runtime_profile())
    assert cloned_runtime_profile["analysis"]["keyword_cluster_k"] == 6
    assert cloned_manifest["import_template"]["source_profile"] == "wos"
    assert cloned_manifest["dictionary_set"]["version"] == "2.0.0"


def test_dictionary_table_import_and_export_roundtrip(isolated_workspace, tmp_path):
    project_dir, manifest = create_project("词表导入导出项目", "dictionary import/export")

    import_path = tmp_path / "synonym-table.json"
    import_payload = {
        "id": "synonym-table-demo",
        "name": "导入同义词表",
        "description": "用于测试分类下新增资源表。",
        "entries": [
            {
                "id": "entry-1",
                "source": "生成式AI",
                "target": "生成式 AI",
                "enabled": True,
                "hits": 0,
                "tags": ["imported"],
                "notes": "",
            }
        ],
    }
    import_path.write_text(json.dumps(import_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    imported = action_import_dictionary_sheet(
        {
            "project_id": manifest["id"],
            "kind": "synonym_map",
            "path": str(import_path),
        }
    )

    manifest, _ = load_project(project_dir)
    collection = manifest["dictionary_set"]["collections"]["synonym_map"]
    imported_table = next(table for table in collection["tables"] if table["id"] == imported["id"])

    assert imported["id"] == "synonym-table-demo"
    assert imported_table["name"] == "导入同义词表"
    assert imported_table["editable"] is True
    assert imported_table["built_in"] is False
    assert any(entry["source"] == "生成式AI" and entry["target"] == "生成式 AI" for entry in imported_table["entries"])
    assert any(entry["source"] == "生成式AI" for entry in manifest["dictionary_set"]["sheets"]["synonym_map"]["entries"])

    export_path = tmp_path / "exported-synonym-table.json"
    exported = action_export_dictionary_sheet(
        {
            "project_id": manifest["id"],
            "kind": "synonym_map",
            "table_id": imported["id"],
            "path": str(export_path),
        }
    )
    exported_payload = json.loads(export_path.read_text(encoding="utf-8"))

    assert exported["table_id"] == imported["id"]
    assert exported_payload["id"] == imported["id"]
    assert exported_payload["name"] == "导入同义词表"
    assert exported_payload["entries"][0]["source"] == "生成式AI"
