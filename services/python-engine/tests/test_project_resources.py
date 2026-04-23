from __future__ import annotations

from app.project_store import CORPUS_FILENAME, PROJECT_FILENAME, create_project, ensure_project_layout, load_project, write_json


def test_default_project_manifest_contains_resource_collections(isolated_workspace):
    _project_dir, manifest = create_project("schema", "schema")

    assert manifest["corpus_resources"] == []
    assert manifest["corpus_views"] == []
    assert manifest["ingestion_specs"] == []
    assert manifest["artifact_records"] == []
    assert manifest["review_tasks"] == []
    assert manifest["experiment_specs"] == []
    assert manifest["shared_resource_refs"] == []


def test_legacy_project_load_backfills_new_fields(isolated_workspace):
    project_dir = isolated_workspace / "projects" / "legacy.tfproj"
    ensure_project_layout(project_dir)

    write_json(project_dir / PROJECT_FILENAME, {"id": "project-1", "name": "legacy", "description": ""})
    write_json(project_dir / CORPUS_FILENAME, [])

    normalized, corpus = load_project(project_dir)

    assert corpus == []
    assert normalized["corpus_resources"] == []
    assert normalized["corpus_views"] == []
    assert normalized["ingestion_specs"] == []
    assert normalized["artifact_records"] == []
    assert normalized["review_tasks"] == []
    assert normalized["experiment_specs"] == []
    assert normalized["shared_resource_refs"] == []
