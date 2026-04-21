from __future__ import annotations

import json

from app.cli import (
    action_create_project,
    action_create_project_from_template,
    action_delete_corpus_document,
    action_delete_project,
    action_export_project,
    action_duplicate_project,
    action_export_project_backup,
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
)
from app.project_store import CORPUS_FILENAME, PROJECT_FILENAME, find_project_dir, load_project, load_workspace_state, workspace_state_path


def test_workspace_cli_persists_current_project_and_recent_order(isolated_workspace):
    bootstrap_snapshot = action_load_workspace()
    assert workspace_state_path().exists()
    bootstrap_id = bootstrap_snapshot["current_project"]["id"]

    created = action_create_project({"name": "真实项目 A", "description": "test"})
    after_create = action_load_workspace()
    assert after_create["current_project"]["id"] == created["id"]

    action_open_project({"project_id": bootstrap_id})
    after_open = action_load_workspace()
    assert after_open["current_project"]["id"] == bootstrap_id

    duplicated = action_duplicate_project({"project_id": bootstrap_id, "name": "真实项目 A 副本"})
    after_duplicate = action_load_workspace()
    assert after_duplicate["current_project"]["id"] == duplicated["id"]

    workspace_state = load_workspace_state()
    assert workspace_state["current_project_id"] == duplicated["id"]
    assert workspace_state["recent_project_ids"][0] == duplicated["id"]
    assert bootstrap_id in workspace_state["recent_project_ids"]
    assert created["id"] in workspace_state["recent_project_ids"]


def test_bootstrap_project_guides_first_run(isolated_workspace):
    snapshot = action_load_workspace()

    assert snapshot["current_project"]["name"] == "新能源与生成式语料示例项目"
    assert "新手上手示例" in snapshot["current_project"]["description"]
    assert len(snapshot["corpus"]) >= 3
    assert snapshot["selected_run"] is not None
    assert snapshot["current_project"]["results"]["frequency_table"]
    assert snapshot["node_definitions"]
    assert any(node["type"] == "corpus_input" for node in snapshot["node_definitions"])
    assert any(node["type"] == "save_html_report" for node in snapshot["node_definitions"])


def test_new_project_has_default_workflow_definition(isolated_workspace):
    created = action_create_project({"name": "工作流基础项目", "description": "workflow foundation"})
    project_dir = find_project_dir(created["id"])
    assert project_dir is not None

    manifest, _ = load_project(project_dir)
    workflow = manifest["workflow_definitions"][0]
    node_types = {node["node_type"] for node in workflow["nodes"]}

    assert manifest["workflow_definitions"]
    assert manifest["active_workflow_id"] == workflow["workflow_id"]
    assert workflow["graph_mode"] == "dag"
    assert "corpus_input" in node_types
    assert "dictionary_input" in node_types
    assert "keyword_extraction" in node_types
    assert "save_html_report" in node_types
    assert "analyze_corpus" not in node_types
    assert "export_results" not in node_types


def test_save_project_compiles_active_workflow_into_pipeline(isolated_workspace):
    created = action_create_project({"name": "工作流编译项目", "description": "workflow compiler"})
    project_dir = find_project_dir(created["id"])
    assert project_dir is not None

    manifest, _ = load_project(project_dir)
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

    assert reloaded_manifest["pipeline"]["recipe_id"] == "trend_scan"
    assert reloaded_manifest["pipeline"]["output_bundle_id"] == "charts_and_report"
    assert reloaded_manifest["pipeline"]["run_scope"]["mode"] == "filtered_subset"
    assert reloaded_manifest["pipeline"]["run_scope"]["year_from"] == 2024
    assert "cleaning" not in reloaded_manifest["pipeline"]["enabled_steps"]
    assert reloaded_manifest["pipeline"]["filtering"]["min_term_frequency"] == 3
    assert reloaded_manifest["pipeline"]["export"]["include_audit"] is False
    assert reloaded_manifest["pipeline"]["export"]["export_png"] is False


def test_save_project_respects_removed_optional_workflow_nodes(isolated_workspace):
    created = action_create_project({"name": "工作流删节点项目", "description": "workflow graph edit"})
    project_dir = find_project_dir(created["id"])
    assert project_dir is not None

    manifest, _ = load_project(project_dir)
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

    assert "cleaning" not in reloaded_manifest["pipeline"]["enabled_steps"]
    assert "filtering" not in reloaded_manifest["pipeline"]["enabled_steps"]


def test_save_project_disables_steps_when_workflow_inputs_are_disconnected(isolated_workspace):
    created = action_create_project({"name": "工作流断线项目", "description": "workflow disconnected edges"})
    project_dir = find_project_dir(created["id"])
    assert project_dir is not None

    manifest, _ = load_project(project_dir)
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

    assert "dictionary_application" not in reloaded_manifest["pipeline"]["enabled_steps"]
    assert "export" not in reloaded_manifest["pipeline"]["enabled_steps"]


def test_import_project_files_persists_corpus_and_copies_sources(isolated_workspace, scratch_dir):
    created = action_create_project({"name": "导入项目", "description": "import"})
    source_path = scratch_dir / "custom.csv"
    source_path.write_text(
        "Title,Abstract,Published,Org,Notes\n项目化导入,需要复制进 tfproj,2026,上海交通大学,extra\n",
        encoding="utf-8",
    )

    result = action_import_project_files(
        {
            "project_id": created["id"],
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
    project_dir = find_project_dir(created["id"])
    assert project_dir is not None

    manifest, corpus = load_project(project_dir)
    assert len(corpus) == 1
    assert corpus[0]["raw_text"] == "项目化导入\n\n需要复制进 tfproj"
    assert corpus[0]["extra_metadata"]["Notes"] == "extra"
    assert manifest["source_files"]

    relative_path = manifest["source_files"][0]["relative_path"]
    assert relative_path.startswith("corpus/imported/")
    assert (project_dir / relative_path).exists()


def test_export_project_backup_creates_zip_archive(isolated_workspace):
    created = action_create_project({"name": "备份项目", "description": "backup"})
    result = action_export_project_backup({"project_id": created["id"]})

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
    created = action_create_project({"name": "可携带项目", "description": "portable"})
    exported = action_export_project_backup({"project_id": created["id"]})

    imported = action_import_project_package({"path": exported["path"]})
    imported_project_dir = find_project_dir(imported["id"])
    assert imported_project_dir is not None

    manifest, corpus = load_project(imported_project_dir)
    assert manifest["name"].startswith("可携带项目")
    assert manifest["workflow_definitions"]
    assert manifest["active_workflow_id"]
    assert corpus == []


def test_delete_project_removes_workspace_entry_and_files(isolated_workspace):
    created = action_create_project({"name": "待删除项目", "description": "delete me"})
    project_dir = find_project_dir(created["id"])
    assert project_dir is not None
    assert project_dir.exists()

    result = action_delete_project({"project_id": created["id"]})

    assert result["project_id"] == created["id"]
    assert not project_dir.exists()

    snapshot = action_load_workspace()
    assert all(item["id"] != created["id"] for item in snapshot["recent_projects"])
    assert snapshot["current_project"] is None


def test_bootstrap_project_is_not_recreated_after_manual_delete(isolated_workspace):
    snapshot = action_load_workspace()
    bootstrap_id = snapshot["current_project"]["id"]

    action_delete_project({"project_id": bootstrap_id})
    after_delete = action_load_workspace()

    assert after_delete["recent_projects"] == []
    assert after_delete["current_project"] is None


def test_update_and_delete_corpus_document_persists_changes(isolated_workspace, scratch_dir):
    created = action_create_project({"name": "语料编辑项目", "description": "edit corpus"})
    source_path = scratch_dir / "edit-target.csv"
    source_path.write_text(
        "title,abstract,year,institution\n原始标题,原始内容,2024,浙江大学\n",
        encoding="utf-8",
    )

    action_import_project_files(
        {
            "project_id": created["id"],
            "file_paths": [str(source_path)],
        }
    )

    project_dir = find_project_dir(created["id"])
    assert project_dir is not None
    manifest, corpus = load_project(project_dir)
    assert len(corpus) == 1
    document = corpus[0]

    updated = action_update_corpus_document(
        {
            "project_id": created["id"],
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

    deleted = action_delete_corpus_document({"project_id": created["id"], "doc_id": corpus[0]["doc_id"]})
    assert deleted["document_count"] == 0

    manifest, corpus = load_project(project_dir)
    assert corpus == []
    assert manifest["source_files"] == []


def test_load_project_normalizes_legacy_run_intent_fields(isolated_workspace):
    created = action_create_project({"name": "旧项目兼容测试", "description": "legacy manifest"})
    project_dir = find_project_dir(created["id"])
    assert project_dir is not None

    manifest, corpus = load_project(project_dir)
    manifest["pipeline"].pop("run_scope", None)
    manifest["pipeline"].pop("recipe_id", None)
    manifest["pipeline"].pop("output_bundle_id", None)
    manifest.pop("workflow_definitions", None)
    manifest.pop("active_workflow_id", None)
    manifest["run_history"] = [
        {
            "run_id": "run-legacy",
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

    assert reloaded_manifest["pipeline"]["run_scope"]["mode"] == "all_documents"
    assert reloaded_manifest["pipeline"]["recipe_id"] == "standard_analysis"
    assert reloaded_manifest["pipeline"]["output_bundle_id"] == "full_report"
    assert reloaded_manifest["workflow_definitions"]
    assert reloaded_manifest["active_workflow_id"] == reloaded_manifest["workflow_definitions"][0]["workflow_id"]
    assert run_record["processed_document_count"] == 0
    assert "项目内全部资料" in run_record["run_scope_summary"]
    assert run_record["workflow_id"] == reloaded_manifest["active_workflow_id"]
    assert run_record["workflow_name"] == reloaded_manifest["workflow_definitions"][0]["name"]
    assert run_record["workflow_hash"].startswith("sha256:")
    assert run_record["output_summary"]


def test_project_templates_and_import_templates_roundtrip(isolated_workspace):
    created = action_create_project({"name": "模板来源项目", "description": "template source"})
    project_dir = find_project_dir(created["id"])
    assert project_dir is not None

    manifest, corpus = load_project(project_dir)
    manifest["pipeline"]["name"] = "模板流程"
    manifest["pipeline"]["analysis"]["keyword_cluster_k"] = 6
    manifest["import_template"]["name"] = "WoS 导入模板"
    manifest["import_template"]["source_profile"] = "wos"
    manifest["dictionary_set"]["version"] = "2.0.0"
    action_save_project(manifest)

    saved_import_template = action_save_import_template(
        {
            "project_id": created["id"],
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
            "project_id": created["id"],
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
    assert cloned_manifest["pipeline"]["name"] == "模板流程"
    assert cloned_manifest["workflow_definitions"]
    assert cloned_manifest["active_workflow_id"]
    assert cloned_manifest["pipeline"]["analysis"]["keyword_cluster_k"] == 6
    assert cloned_manifest["import_template"]["source_profile"] == "wos"
    assert cloned_manifest["dictionary_set"]["version"] == "2.0.0"
