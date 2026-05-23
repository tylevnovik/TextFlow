from __future__ import annotations

from app.storage.artifacts import load_artifact_payload, load_artifact_preview, write_artifact


def test_artifact_preview_loads_without_materializing_full_payload(scratch_dir):
    project_dir = scratch_dir / "artifact-project"
    payload = [{"term": f"term-{index}", "count": index} for index in range(75)]

    artifact = write_artifact(project_dir, "run-test", "node-frequency", "table", payload)

    preview = load_artifact_preview(project_dir, artifact["artifact_id"])
    full_payload = load_artifact_payload(project_dir, artifact["artifact_id"])

    assert "rows" in preview
    assert len(preview["rows"]) == 50
    assert len(full_payload) == 75
    assert artifact["path"].endswith(".json.gz")


def test_artifact_store_uses_project_database_when_available(scratch_dir):
    from app.storage.database import initialize_project_database
    from app.storage.projects import PROJECT_DATABASE_FILENAME

    project_dir = scratch_dir / "artifact-db-project"
    project_dir.mkdir()
    initialize_project_database(project_dir / PROJECT_DATABASE_FILENAME)
    payload = [{"term": f"term-{index}", "count": index} for index in range(75)]

    artifact = write_artifact(project_dir, "run-test", "node-frequency", "table", payload)

    preview = load_artifact_preview(project_dir, artifact["artifact_id"], limit=12)
    assert artifact["path"] == f"project.db:artifacts/{artifact['artifact_id']}/payload"
    assert artifact["preview_path"] == f"project.db:artifacts/{artifact['artifact_id']}/preview"
    assert len(preview["rows"]) == 12
    assert load_artifact_payload(project_dir, artifact["artifact_id"]) == payload
