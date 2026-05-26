from __future__ import annotations

import sys
from typing import Any, Callable

# Import common helpers
from .support import ProgressCallback, emit, load_project_or_fail

# Import all actions from submodules
from .projects import (
    action_load_workspace,
    action_create_project,
    action_create_project_from_template,
    action_open_project,
    action_duplicate_project,
    action_delete_project,
    action_save_project,
    action_create_corpus_view,
    action_update_corpus_view,
    action_delete_corpus_view,
)
from .imports import (
    action_import_project_files,
    action_import_project_package,
    action_export_project_backup,
    action_update_corpus_document,
    action_delete_corpus_document,
    action_import_dictionary_sheet,
    action_export_dictionary_sheet,
    action_save_ingestion_spec,
    action_list_ingestion_specs,
    normalize_corpus_document,
)
from .workflows import (
    action_get_node_catalog,
    action_run_workflow,
    action_export_project,
    action_save_project_template,
    action_list_project_templates,
    action_save_import_template,
    action_list_import_templates,
    action_load_import_template,
    action_compare_runs,
    action_load_artifact_preview,
    action_load_artifact_payload,
    action_list_run_artifacts,
)
from .reviews import (
    action_create_review_task,
    action_list_review_tasks,
    action_resolve_review_task,
    action_apply_review_resolution,
)
from .experiments import (
    action_save_experiment_spec,
    action_list_experiment_specs,
    action_run_experiment_matrix,
)

ACTION_HANDLERS: dict[str, Callable[..., Any]] = {
    "load-workspace": action_load_workspace,
    "get-node-catalog": action_get_node_catalog,
    "create-project": action_create_project,
    "create-project-from-template": action_create_project_from_template,
    "open-project": action_open_project,
    "duplicate-project": action_duplicate_project,
    "delete-project": action_delete_project,
    "import-project-files": action_import_project_files,
    "run-workflow": action_run_workflow,
    "export-project": action_export_project,
    "export-project-backup": action_export_project_backup,
    "import-project-package": action_import_project_package,
    "save-project-template": action_save_project_template,
    "list-project-templates": action_list_project_templates,
    "save-import-template": action_save_import_template,
    "list-import-templates": action_list_import_templates,
    "load-import-template": action_load_import_template,
    "save-project": action_save_project,
    "update-corpus-document": action_update_corpus_document,
    "delete-corpus-document": action_delete_corpus_document,
    "import-dictionary-sheet": action_import_dictionary_sheet,
    "export-dictionary-sheet": action_export_dictionary_sheet,
    "create-review-task": action_create_review_task,
    "list-review-tasks": action_list_review_tasks,
    "resolve-review-task": action_resolve_review_task,
    "apply-review-resolution": action_apply_review_resolution,
    "save-experiment-spec": action_save_experiment_spec,
    "list-experiment-specs": action_list_experiment_specs,
    "run-experiment-matrix": action_run_experiment_matrix,
    "compare-runs": action_compare_runs,
    "save-ingestion-spec": action_save_ingestion_spec,
    "list-ingestion-specs": action_list_ingestion_specs,
    "create-corpus-view": action_create_corpus_view,
    "update-corpus-view": action_update_corpus_view,
    "delete-corpus-view": action_delete_corpus_view,
    "load-artifact-preview": action_load_artifact_preview,
    "load-artifact-payload": action_load_artifact_payload,
    "list-run-artifacts": action_list_run_artifacts,
}


def parse_payload() -> dict[str, Any]:
    import json
    if len(sys.argv) < 3:
        return {}
    return json.loads(sys.argv[2])


def execute_action(
    action: str,
    payload: dict[str, Any] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> Any:
    handler = ACTION_HANDLERS.get(action)
    if handler is None:
        raise ValueError(f"Unknown action: {action}")
    payload = payload or {}
    return handler(payload, progress_callback)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m app.cli <action> [json-payload]")

    action = sys.argv[1]
    payload = parse_payload()

    emit(execute_action(action, payload))


if __name__ == "__main__":
    main()
