from __future__ import annotations

from app.cli import action_list_ingestion_specs, action_save_ingestion_spec
from app.project_store import create_project, read_json


def test_saved_ingestion_spec_has_stable_hash(isolated_workspace):
    project_dir, manifest = create_project("spec project", "spec project")

    spec = action_save_ingestion_spec(
        {
            "project_id": manifest["id"],
            "name": "Literature default",
            "source_profile": "literature",
            "field_mappings": [
                {"source_field": "title", "target_field": "title", "required": True},
                {"source_field": "abstract", "target_field": "raw_text", "required": True},
            ],
            "text_build": {
                "mode": "concat_fields",
                "fields": ["title", "abstract"],
                "delimiter": "\n\n",
                "skip_empty": True,
            },
            "dedupe_rules": {"keys": ["title", "year"], "strategy": "keep_first"},
            "metadata_normalization_rules": {"institution": {"strip": True}},
        }
    )

    assert spec["spec_hash"].startswith("sha256:")

    listed = action_list_ingestion_specs({"project_id": manifest["id"]})
    assert listed[0]["spec_hash"] == spec["spec_hash"]

    stored = read_json(project_dir / "metadata" / "ingestion_specs.json")
    assert stored[0]["spec_hash"] == spec["spec_hash"]
