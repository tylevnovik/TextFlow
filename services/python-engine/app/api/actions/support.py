from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from ...storage.projects import (
    find_project_dir,
    load_project,
    list_project_dirs,
)
from ...samples.projects import BUILTIN_SAMPLE_PROJECT_DATA_REVISION
from ...samples.bundled_workspace import (
    restore_bundled_sample_workspace,
    restore_builtin_sample_projects_from_bundled,
)
from ...domain.common import json_ready
from ...storage.workspace import load_workspace_state, mark_workspace_bootstrapped, workspace_root

ProgressCallback = Callable[[float, str, dict[str, Any] | None], None]


def emit(payload: Any) -> None:
    sys.stdout.write(json.dumps(json_ready(payload), ensure_ascii=False))


def notify(
    progress_callback: ProgressCallback | None,
    progress: float,
    message: str,
    detail: dict[str, Any] | None = None,
) -> None:
    if progress_callback is None:
        return
    progress_callback(progress, message, detail)


def load_project_or_fail(project_id: str) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    project_dir = find_project_dir(project_id)
    if project_dir is None:
        raise ValueError(f"Project {project_id} not found")
    manifest, corpus = load_project(project_dir)
    return project_dir, manifest, corpus


def ensure_bootstrap_project() -> None:
    workspace_state = load_workspace_state()
    if (
        workspace_state.get("bootstrap_completed")
        and int(workspace_state.get("builtin_samples_revision") or 0) >= BUILTIN_SAMPLE_PROJECT_DATA_REVISION
    ):
        return

    project_dirs = list_project_dirs()
    first_run_needs_samples = not project_dirs and not workspace_state.get("bootstrap_completed")
    if first_run_needs_samples:
        if restore_bundled_sample_workspace(workspace_root(), allow_existing_scaffold=True):
            restored_state = load_workspace_state()
            if (
                restored_state.get("bootstrap_completed")
                and int(restored_state.get("builtin_samples_revision") or 0) >= BUILTIN_SAMPLE_PROJECT_DATA_REVISION
            ):
                return
        project_dirs = list_project_dirs()

    if restore_builtin_sample_projects_from_bundled(
        workspace_root(),
        create_missing=not project_dirs and not workspace_state.get("bootstrap_completed"),
    ):
        return

    if first_run_needs_samples and not list_project_dirs():
        raise RuntimeError(
            "Bundled sample workspace is missing or unusable; cannot bootstrap the official sample projects."
        )

    mark_workspace_bootstrapped(builtin_samples_revision=BUILTIN_SAMPLE_PROJECT_DATA_REVISION)
