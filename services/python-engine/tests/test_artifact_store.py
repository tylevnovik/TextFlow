from __future__ import annotations

from app.artifact_store import load_artifact_payload, load_artifact_preview, write_artifact


def test_artifact_preview_loads_without_materializing_full_payload(scratch_dir):
    project_dir = scratch_dir / "artifact-project"
    payload = [{"term": f"term-{index}", "count": index} for index in range(75)]

    artifact = write_artifact(project_dir, "run-test", "node-frequency", "table", payload)

    preview = load_artifact_preview(project_dir, artifact["artifact_id"])
    full_payload = load_artifact_payload(project_dir, artifact["artifact_id"])

    assert "rows" in preview
    assert len(preview["rows"]) == 50
    assert len(full_payload) == 75
