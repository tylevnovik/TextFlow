from __future__ import annotations

from app.bundled_sample_workspace import (
    bundled_sample_workspace_is_usable,
    load_bundled_sample_workspace_metadata,
    restore_bundled_sample_workspace,
)
from app.project_store import list_project_dirs, load_workspace_state
from app.sample_projects import BUILTIN_SAMPLE_PROJECT_DATA_REVISION, BUILTIN_SAMPLE_PROJECTS
from tests.sample_test_support import TEST_SAMPLE_ROW_LIMIT


def test_bundled_sample_workspace_metadata_matches_template(monkeypatch, bundled_sample_workspace_120):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", str(TEST_SAMPLE_ROW_LIMIT))
    metadata = load_bundled_sample_workspace_metadata(bundled_sample_workspace_120)

    assert metadata is not None
    assert metadata["builtin_samples_revision"] == BUILTIN_SAMPLE_PROJECT_DATA_REVISION
    assert metadata["project_count"] == len(BUILTIN_SAMPLE_PROJECTS)
    assert metadata["row_limit"] == TEST_SAMPLE_ROW_LIMIT
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
