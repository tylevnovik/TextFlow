from __future__ import annotations

from app.api.actions.dispatcher import action_create_corpus_view
from app.storage.projects import create_project, read_json


def test_create_corpus_view_persists_filter_spec(isolated_workspace):
    project_dir, manifest = create_project("resource views", "resource views")

    created = action_create_corpus_view(
        {
            "project_id": manifest["id"],
            "name": "OpenAI corpus",
            "resource_ids": [],
            "filter_spec": {"institution": ["OpenAI"]},
        }
    )

    assert created["filter_spec"]["institution"] == ["OpenAI"]

    stored = read_json(project_dir / "metadata" / "corpus_views.json")
    assert stored[0]["filter_spec"]["institution"] == ["OpenAI"]
