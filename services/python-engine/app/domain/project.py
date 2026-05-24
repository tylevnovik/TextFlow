from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from .common import utc_now_iso
from .dictionary import default_dictionary_set
from .import_profiles import default_import_template
from .results import empty_result_bundle
from .runtime_profile import default_runtime_profile
from .workflow import default_workflow_definition

def default_project_manifest(
    name: str,
    description: str,
    root_relative_path: str,
    *,
    include_dictionary_set: bool = True,
) -> dict[str, Any]:
    timestamp = utc_now_iso()
    workflow = default_workflow_definition(default_runtime_profile())
    return {
        "id": f"project-{uuid4().hex[:12]}",
        "schema_version": "2.0.0",
        "name": name,
        "description": description,
        "created_at": timestamp,
        "updated_at": timestamp,
        "version": "0.2.0",
        "source_files": [],
        "corpus_resources": [],
        "corpus_views": [],
        "ingestion_specs": [],
        "artifact_records": [],
        "review_tasks": [],
        "experiment_specs": [],
        "shared_resource_refs": [],
        "settings": {
            "default_language": "mixed",
            "preferred_theme": "paper",
            "enable_auto_save": True,
            "enable_update_check": False,
            "default_export_formats": ["csv", "xlsx", "png", "html"],
        },
        "paths": {
            "root": root_relative_path,
            "corpus_dir": "corpus",
            "dictionaries_dir": "dictionaries",
            "runs_dir": "runs",
            "cache_dir": "cache",
            "exports_dir": "exports",
        },
        "import_template": default_import_template(),
        "dictionary_set": default_dictionary_set() if include_dictionary_set else {},
        "workflow_definitions": [workflow],
        "active_workflow_id": workflow["workflow_id"],
        "run_history": [],
        "results": empty_result_bundle(),
    }


def deep_copy_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(manifest)
