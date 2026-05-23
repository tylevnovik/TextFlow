from __future__ import annotations

from app.samples.bundled_workspace import (
    bundled_sample_workspace_is_usable,
    load_bundled_sample_workspace_metadata,
    restore_bundled_sample_workspace,
)
from app.storage.projects import PROJECT_DATABASE_FILENAME, list_project_dirs, load_project, load_workspace_state
from app.samples.projects import BUILTIN_SAMPLE_PROJECT_DATA_REVISION, BUILTIN_SAMPLE_PROJECTS
from tests.conftest import TEST_SAMPLE_ROW_LIMIT


def test_bundled_sample_workspace_metadata_matches_template(monkeypatch, bundled_sample_workspace_120):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", str(TEST_SAMPLE_ROW_LIMIT))
    metadata = load_bundled_sample_workspace_metadata(bundled_sample_workspace_120)

    assert metadata is not None
    assert metadata["builtin_samples_revision"] == BUILTIN_SAMPLE_PROJECT_DATA_REVISION
    assert metadata["project_count"] == len(BUILTIN_SAMPLE_PROJECTS)
    assert metadata["row_limit"] == TEST_SAMPLE_ROW_LIMIT
    assert metadata["project_names"] == [spec["name"] for spec in BUILTIN_SAMPLE_PROJECTS]
    assert bundled_sample_workspace_is_usable(bundled_sample_workspace_120) is True


def test_bundled_sample_workspace_rejects_mismatched_row_limit(monkeypatch, bundled_sample_workspace_120):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "150")

    assert bundled_sample_workspace_is_usable(bundled_sample_workspace_120) is False


def test_restore_bundled_sample_workspace_seeds_bootstrap_state(monkeypatch, isolated_workspace, bundled_sample_workspace_120):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", str(TEST_SAMPLE_ROW_LIMIT))
    restored = restore_bundled_sample_workspace(
        isolated_workspace,
        template_root=bundled_sample_workspace_120,
        clear_destination=True,
    )

    assert restored is True
    assert len(list_project_dirs()) == len(BUILTIN_SAMPLE_PROJECTS)

    workspace_state = load_workspace_state()
    assert workspace_state["bootstrap_completed"] is True
    assert workspace_state["builtin_samples_revision"] == BUILTIN_SAMPLE_PROJECT_DATA_REVISION


def test_bundled_sample_workspace_strips_raw_seed_files_but_keeps_source_audit(monkeypatch, isolated_workspace, bundled_sample_workspace_120):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", str(TEST_SAMPLE_ROW_LIMIT))
    restored = restore_bundled_sample_workspace(
        isolated_workspace,
        template_root=bundled_sample_workspace_120,
        clear_destination=True,
    )

    assert restored is True
    for project_dir in list_project_dirs():
        manifest, corpus = load_project(project_dir)
        assert corpus
        assert (project_dir / PROJECT_DATABASE_FILENAME).exists()
        assert manifest["source_files"]
        assert all(source["relative_path"] == "" for source in manifest["source_files"])
        assert all(source["retained_in_project"] is False for source in manifest["source_files"])
        assert not (project_dir / "metadata" / "sample_seed").exists()
        assert not any((project_dir / "corpus" / "imported").glob("*"))


def test_bundled_sample_manifest_keeps_dictionaries_out_of_project_json(bundled_sample_workspace_120):
    import json

    for project_file in bundled_sample_workspace_120.glob("projects/*.tfproj/project.json"):
        manifest = json.loads(project_file.read_text(encoding="utf-8"))
        dictionary_set = manifest["dictionary_set"]
        assert dictionary_set["storage"] == "project.db"
        assert "sheets" not in dictionary_set
        assert all("tables" not in collection for collection in dictionary_set["collections"].values())
        assert (project_file.parent / "project.db").exists()
        assert project_file.stat().st_size < 2 * 1024 * 1024
