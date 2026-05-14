from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.bundled_sample_workspace import restore_bundled_sample_workspace
from app.project_store import PROJECT_DATABASE_FILENAME, PROJECT_FILENAME, create_project, list_project_dirs, load_project, save_project
from app.sample_projects import (
    BUILTIN_SAMPLE_PROJECT_DATA_REVISION,
    BUILTIN_SAMPLE_PROJECTS,
    FIRST_BUILTIN_SAMPLE_PROJECT_NAME,
    _is_synthetic_placeholder_row,
    _sample_row_count,
    create_builtin_sample_projects,
    reconcile_builtin_sample_projects,
)
from app.workflow_runner import run_project_workflow
from tests.conftest import TEST_SAMPLE_ROW_LIMIT, placeholder_row


@pytest.fixture(scope="session")
def bundled_builtin_sample_projects(bundled_sample_workspace_120):
    created: list[tuple[Path, dict[str, object]]] = []
    project_root = bundled_sample_workspace_120 / "projects"
    for project_dir in project_root.glob("*.tfproj"):
        manifest = json.loads((project_dir / PROJECT_FILENAME).read_text(encoding="utf-8"))
        created.append((project_dir, manifest))

    created.sort(
        key=lambda item: int(
            (
                item[1].get("settings", {})
                .get("sample_project", {})
                .get("order")
                or 999
            )
        )
    )
    return created


def _sample_by_name(
    projects: list[tuple[Path, dict[str, object]]],
    sample_name: str,
) -> tuple[Path, dict[str, object]]:
    return next(item for item in projects if item[1]["name"] == sample_name)


@pytest.fixture
def restored_builtin_sample_projects(monkeypatch, isolated_workspace, bundled_sample_workspace_120):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", str(TEST_SAMPLE_ROW_LIMIT))
    assert restore_bundled_sample_workspace(
        isolated_workspace,
        template_root=bundled_sample_workspace_120,
        clear_destination=True,
    )
    created: list[tuple[Path, dict[str, object]]] = []
    for project_dir in list_project_dirs():
        manifest, _corpus = load_project(project_dir)
        created.append((project_dir, manifest))
    created.sort(key=lambda item: int(item[1]["settings"]["sample_project"]["order"]))
    return created


def test_builtin_sample_specs_are_three_revised_flow_samples():
    assert len(BUILTIN_SAMPLE_PROJECTS) == 3
    assert [spec["order"] for spec in BUILTIN_SAMPLE_PROJECTS] == [1, 2, 3]
    assert [spec["slug"] for spec in BUILTIN_SAMPLE_PROJECTS] == [
        "sample-01-wos-paper-keyword-topic",
        "sample-02-incopat-patent-technology-graph",
        "sample-03-paper-patent-integrated-map",
    ]
    assert all(spec["flow_schema_version"] == "2026-05-new-flow" for spec in BUILTIN_SAMPLE_PROJECTS)
    assert [spec["source_profiles"] for spec in BUILTIN_SAMPLE_PROJECTS] == [
        ["wos"],
        ["incopat"],
        ["wos", "incopat"],
    ]


def test_sample_row_count_accepts_any_positive_override(monkeypatch):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "7")
    assert _sample_row_count(BUILTIN_SAMPLE_PROJECTS[0]) == 7


@pytest.mark.engine_full
def test_create_builtin_sample_projects_writes_sqlite_and_no_raw_sources(monkeypatch, isolated_workspace):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", str(TEST_SAMPLE_ROW_LIMIT))
    created = create_builtin_sample_projects()

    assert len(created) == len(BUILTIN_SAMPLE_PROJECTS)
    for project_dir, manifest in created:
        loaded_manifest, corpus = load_project(project_dir)
        sample = loaded_manifest["settings"]["sample_project"]
        assert (project_dir / PROJECT_DATABASE_FILENAME).exists()
        assert not (project_dir / "metadata" / "corpus.json").exists()
        assert not any((project_dir / "corpus" / "imported").glob("*"))
        assert not (project_dir / "metadata" / "sample_seed").exists()
        assert len(corpus) == sample["public_row_count"]
        assert sample["data_revision"] == BUILTIN_SAMPLE_PROJECT_DATA_REVISION
        assert sample["flow_schema_version"] == "2026-05-new-flow"
        assert loaded_manifest["workflow_definitions"][0]["meta"]["flow_schema_version"] == "2026-05-new-flow"
        assert manifest["id"] == loaded_manifest["id"]
        assert loaded_manifest["source_files"]
        assert all(source["relative_path"] == "" for source in loaded_manifest["source_files"])
        assert all(source["retained_in_project"] is False for source in loaded_manifest["source_files"])
        assert all(source["license_note"] for source in loaded_manifest["source_files"])
        assert not any(_is_synthetic_placeholder_row(row) for row in corpus)


def test_bundled_sample_workflows_match_declared_coverage(bundled_builtin_sample_projects):
    for _project_dir, manifest in bundled_builtin_sample_projects:
        workflow_nodes = {node["node_type"] for node in manifest["workflow_definitions"][0]["nodes"]}
        declared = set(manifest["settings"]["sample_project"]["covered_nodes"])
        assert declared <= workflow_nodes
        assert "topic_modeling" in workflow_nodes
        assert "deduplicate_documents" in workflow_nodes


@pytest.mark.parametrize(
    "sample_name",
    [
        "示例 01 - WoS论文关键词与主题流程",
        "示例 02 - IncoPat专利技术识别与图分析",
        "示例 03 - 论文专利融合分析流程",
    ],
)
@pytest.mark.engine_full
def test_revised_flow_sample_workflows_run(restored_builtin_sample_projects, sample_name):
    project_dir, _manifest = _sample_by_name(restored_builtin_sample_projects, sample_name)
    manifest, corpus = load_project(project_dir)
    manifest, _corpus, run = run_project_workflow(project_dir, manifest, corpus)

    artifact_node_ids = {str(item.get("node_id") or "") for item in manifest["artifact_records"]}
    assert run["status"] == "completed"
    assert run["artifacts"]
    assert manifest["results"]["frequency_table"]
    assert manifest["results"]["term_year_table"]
    assert manifest["results"]["cooccurrence_table"]
    assert manifest["results"]["keyword_result"]
    assert manifest["results"]["topic_summary_table"]
    assert "node-topic-modeling" in artifact_node_ids
    assert "node-save-html-report" in artifact_node_ids
    assert "node-save-xlsx" in artifact_node_ids
    if "IncoPat" in sample_name or "融合" in sample_name:
        assert manifest["results"]["technology_indicator_table"]
        assert manifest["results"]["technology_classification_table"]


@pytest.mark.engine_full
def test_reconcile_refreshes_legacy_builtin_sample_and_creates_missing_new_samples(monkeypatch, isolated_workspace):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", str(TEST_SAMPLE_ROW_LIMIT))
    project_dir, manifest = create_project(FIRST_BUILTIN_SAMPLE_PROJECT_NAME, "legacy placeholder sample")
    manifest["settings"]["sample_project"] = {"slug": "sample-01-basic-preprocessing", "data_revision": 1}
    save_project(project_dir, manifest, [placeholder_row(index) for index in range(4)])

    reconciled = reconcile_builtin_sample_projects(create_missing=False)

    assert len(reconciled) == len(BUILTIN_SAMPLE_PROJECTS)
    refreshed_manifest, refreshed_corpus = load_project(project_dir)
    assert refreshed_manifest["name"] == FIRST_BUILTIN_SAMPLE_PROJECT_NAME
    assert refreshed_manifest["settings"]["sample_project"]["slug"] == "sample-01-wos-paper-keyword-topic"
    assert refreshed_manifest["settings"]["sample_project"]["data_revision"] == BUILTIN_SAMPLE_PROJECT_DATA_REVISION
    assert len(refreshed_corpus) == TEST_SAMPLE_ROW_LIMIT
    assert not any(_is_synthetic_placeholder_row(row) for row in refreshed_corpus)
