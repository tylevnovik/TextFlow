from __future__ import annotations

from copy import deepcopy
import json
import os
import platform
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from .defaults import (
    default_dictionary_set,
    default_import_template,
    default_pipeline,
    default_project_manifest,
    empty_result_bundle,
    utc_now_iso,
)

PROJECT_FILENAME = "project.json"
CORPUS_FILENAME = "metadata/corpus.json"
WORKSPACE_FILENAME = "workspace.json"
WORKSPACE_ENV_VAR = "TEXTFLOW_WORKSPACE_ROOT"
PROJECT_TEMPLATES_DIRNAME = "project_templates"
IMPORT_TEMPLATES_DIRNAME = "import_templates"
PROJECT_PACKAGE_EXTENSION = ".tfproj"


def default_user_workspace_root() -> Path:
    system = platform.system().lower()
    if system == "windows":
        base = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "TextFlow Studio"
    if system == "darwin":
        return Path.home() / "Library" / "Application Support" / "TextFlow Studio"
    return Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "textflow-studio"


def workspace_root() -> Path:
    configured_root = os.getenv(WORKSPACE_ENV_VAR)
    if configured_root:
        root = Path(configured_root)
    else:
        root = default_user_workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def projects_root() -> Path:
    root = workspace_root() / "projects"
    root.mkdir(parents=True, exist_ok=True)
    return root


def data_root() -> Path:
    root = workspace_root() / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def templates_root() -> Path:
    root = workspace_root() / "templates"
    root.mkdir(parents=True, exist_ok=True)
    return root


def project_templates_root() -> Path:
    root = templates_root() / PROJECT_TEMPLATES_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def import_templates_root() -> Path:
    root = templates_root() / IMPORT_TEMPLATES_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def workspace_state_path() -> Path:
    return projects_root() / WORKSPACE_FILENAME


def default_workspace_state() -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "current_project_id": None,
        "recent_project_ids": [],
        "bootstrap_completed": False,
    }


def normalize_workspace_state(state: dict[str, Any] | None) -> dict[str, Any]:
    normalized = default_workspace_state()
    if not state:
        return normalized

    normalized["version"] = state.get("version", normalized["version"])
    normalized["current_project_id"] = state.get("current_project_id")
    normalized["recent_project_ids"] = [
        str(project_id)
        for project_id in state.get("recent_project_ids", [])
        if project_id
    ]
    normalized["bootstrap_completed"] = bool(state.get("bootstrap_completed", False))
    return normalized


def load_workspace_state() -> dict[str, Any]:
    path = workspace_state_path()
    if not path.exists():
        return default_workspace_state()
    return normalize_workspace_state(read_json(path))


def save_workspace_state(state: dict[str, Any]) -> None:
    write_json(workspace_state_path(), normalize_workspace_state(state))


def remember_project(project_id: str, set_current: bool = False) -> dict[str, Any]:
    state = load_workspace_state()
    recent = [item for item in state["recent_project_ids"] if item != project_id]
    recent.insert(0, project_id)
    state["recent_project_ids"] = recent[:24]
    if set_current:
        state["current_project_id"] = project_id
    save_workspace_state(state)
    return state


def remove_project_from_workspace(project_id: str) -> dict[str, Any]:
    state = load_workspace_state()
    state["recent_project_ids"] = [item for item in state["recent_project_ids"] if item != project_id]
    if state["current_project_id"] == project_id:
        state["current_project_id"] = state["recent_project_ids"][0] if state["recent_project_ids"] else None
    save_workspace_state(state)
    return state


def mark_workspace_bootstrapped() -> dict[str, Any]:
    state = load_workspace_state()
    state["bootstrap_completed"] = True
    save_workspace_state(state)
    return state


def forget_missing_projects(valid_project_ids: set[str]) -> dict[str, Any]:
    state = load_workspace_state()
    state["recent_project_ids"] = [item for item in state["recent_project_ids"] if item in valid_project_ids]
    if state["current_project_id"] not in valid_project_ids:
        state["current_project_id"] = state["recent_project_ids"][0] if state["recent_project_ids"] else None
    save_workspace_state(state)
    return state


def slugify(name: str) -> str:
    lowered = name.strip().lower()
    lowered = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-")
    return lowered or "textflow-project"


def project_dir_from_name(name: str) -> Path:
    return projects_root() / f"{slugify(name)}.tfproj"


def ensure_unique_project_dir(name: str) -> Path:
    base_slug = slugify(name)
    candidate = projects_root() / f"{base_slug}.tfproj"
    if not candidate.exists():
        return candidate

    index = 2
    while True:
        candidate = projects_root() / f"{base_slug}-{index}.tfproj"
        if not candidate.exists():
            return candidate
        index += 1


def ensure_project_layout(project_dir: Path) -> None:
    for relative in [
        "corpus/imported",
        "dictionaries",
        "pipelines",
        "metadata",
        "runs",
        "cache",
        "exports",
    ]:
        (project_dir / relative).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def project_relative_root(project_dir: Path) -> str:
    return project_dir.relative_to(workspace_root()).as_posix()


def template_path(root: Path, template_id: str) -> Path:
    return root / f"{template_id}.json"


def list_templates(root: Path) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = read_json(path)
        if isinstance(payload, dict):
            templates.append(payload)
    templates.sort(key=lambda item: (item.get("updated_at", ""), item.get("name", "")), reverse=True)
    return templates


def load_template(root: Path, template_id: str) -> dict[str, Any]:
    path = template_path(root, template_id)
    if not path.exists():
        raise ValueError(f"Template {template_id} not found")
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid template payload: {path}")
    return payload


def save_template(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(payload)
    timestamp = utc_now_iso()
    record.setdefault("created_at", timestamp)
    record["updated_at"] = timestamp
    write_json(template_path(root, str(record["id"])), record)
    return record


def refresh_manifest_paths(manifest: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    manifest.setdefault("paths", {})
    manifest["paths"].update(
        {
            "root": project_relative_root(project_dir),
            "corpus_dir": "corpus",
            "dictionaries_dir": "dictionaries",
            "pipelines_dir": "pipelines",
            "runs_dir": "runs",
            "cache_dir": "cache",
            "exports_dir": "exports",
        }
    )
    return manifest


def normalize_import_template_record(import_template: dict[str, Any] | None) -> dict[str, Any]:
    source_profile = str((import_template or {}).get("source_profile") or "generic")
    baseline = default_import_template(source_profile)
    if not isinstance(import_template, dict):
        return baseline

    normalized = deepcopy(baseline)
    for key, value in import_template.items():
        if key == "text_build" and isinstance(value, dict):
            normalized["text_build"].update(value)
            continue
        normalized[key] = value

    if not isinstance(normalized.get("field_mappings"), list):
        normalized["field_mappings"] = baseline["field_mappings"]
    return normalized


def normalize_dictionary_set_record(dictionary_set: dict[str, Any] | None) -> dict[str, Any]:
    baseline = default_dictionary_set()
    if not isinstance(dictionary_set, dict):
        return baseline

    normalized = deepcopy(baseline)
    for key, value in dictionary_set.items():
        if key != "sheets":
            normalized[key] = value

    provided_sheets = dictionary_set.get("sheets", {})
    if isinstance(provided_sheets, dict):
        for kind, payload in provided_sheets.items():
            if kind in normalized["sheets"] and isinstance(payload, dict):
                merged = deepcopy(normalized["sheets"][kind])
                for field, value in payload.items():
                    merged[field] = value
                normalized["sheets"][kind] = merged
            else:
                normalized["sheets"][kind] = payload
    return normalized


def normalize_pipeline_record(pipeline: dict[str, Any] | None) -> dict[str, Any]:
    baseline = default_pipeline()
    if not isinstance(pipeline, dict):
        return baseline

    normalized = deepcopy(baseline)
    for key, value in pipeline.items():
        if key in normalized and isinstance(normalized[key], dict) and isinstance(value, dict):
            normalized[key].update(value)
            continue
        normalized[key] = value

    if not isinstance(normalized.get("enabled_steps"), list):
        normalized["enabled_steps"] = baseline["enabled_steps"]
    if not isinstance(normalized.get("execution_order"), list):
        normalized["execution_order"] = baseline["execution_order"]

    run_scope = normalized.get("run_scope")
    if not isinstance(run_scope, dict):
        normalized["run_scope"] = deepcopy(baseline["run_scope"])
    else:
        normalized["run_scope"] = {
            **deepcopy(baseline["run_scope"]),
            **run_scope,
        }

    normalized["recipe_id"] = str(normalized.get("recipe_id") or baseline["recipe_id"])
    normalized["output_bundle_id"] = str(normalized.get("output_bundle_id") or baseline["output_bundle_id"])
    return normalized


def normalize_results_bundle(results: dict[str, Any] | None) -> dict[str, Any]:
    baseline = empty_result_bundle()
    if not isinstance(results, dict):
        return baseline
    normalized = deepcopy(baseline)
    for key, value in results.items():
        normalized[key] = value
    return normalized


def default_run_scope_summary(document_count: int) -> str:
    return f"处理对象：项目内全部资料（共 {document_count} 篇）"


def default_output_summary(export_settings: dict[str, Any] | None) -> str:
    export_config = export_settings if isinstance(export_settings, dict) else {}
    outputs: list[str] = []
    if export_config.get("export_csv"):
        outputs.append("CSV 表格")
    if export_config.get("export_xlsx"):
        outputs.append("XLSX 汇总包")
    if export_config.get("export_png"):
        outputs.append("PNG 图表")
    if export_config.get("export_html_report"):
        outputs.append("HTML 报告")
    return "、".join(outputs) if outputs else "仅更新项目内结果快照"


def normalize_run_record(
    run_record: dict[str, Any] | None,
    pipeline: dict[str, Any],
    corpus: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = deepcopy(run_record) if isinstance(run_record, dict) else {}
    processed_document_count = normalized.get("processed_document_count")
    if not isinstance(processed_document_count, int):
        processed_document_count = len(corpus)
    normalized["processed_document_count"] = processed_document_count
    normalized["run_scope_summary"] = str(
        normalized.get("run_scope_summary") or default_run_scope_summary(processed_document_count)
    )
    normalized["recipe_id"] = str(normalized.get("recipe_id") or pipeline.get("recipe_id") or "standard_analysis")
    normalized["output_bundle_id"] = str(
        normalized.get("output_bundle_id") or pipeline.get("output_bundle_id") or "full_report"
    )
    normalized["output_summary"] = str(
        normalized.get("output_summary") or default_output_summary(pipeline.get("export"))
    )
    normalized.setdefault("logs", [])
    normalized.setdefault("artifacts", [])
    return normalized


def normalize_project_manifest(
    manifest: dict[str, Any] | None,
    corpus: list[dict[str, Any]],
    project_dir: Path,
) -> dict[str, Any]:
    payload = manifest if isinstance(manifest, dict) else {}
    name = str(payload.get("name") or project_dir.stem)
    description = str(payload.get("description") or "")
    baseline = default_project_manifest(name, description, project_relative_root(project_dir))
    normalized = deepcopy(baseline)

    for key, value in payload.items():
        if key in {"settings", "paths", "pipeline", "import_template", "dictionary_set", "results", "run_history"}:
            continue
        normalized[key] = value

    normalized["settings"].update(payload.get("settings", {}) if isinstance(payload.get("settings"), dict) else {})
    normalized["paths"].update(payload.get("paths", {}) if isinstance(payload.get("paths"), dict) else {})
    normalized["import_template"] = normalize_import_template_record(payload.get("import_template"))
    normalized["dictionary_set"] = normalize_dictionary_set_record(payload.get("dictionary_set"))
    normalized["pipeline"] = normalize_pipeline_record(payload.get("pipeline"))
    normalized["results"] = normalize_results_bundle(payload.get("results"))
    normalized["run_history"] = [
        normalize_run_record(run_record, normalized["pipeline"], corpus)
        for run_record in payload.get("run_history", [])
        if isinstance(run_record, dict)
    ]
    refresh_manifest_paths(normalized, project_dir)
    return normalized


def create_project(name: str, description: str) -> tuple[Path, dict[str, Any]]:
    project_dir = ensure_unique_project_dir(name)
    ensure_project_layout(project_dir)
    manifest = default_project_manifest(name, description, project_relative_root(project_dir))
    write_json(project_dir / PROJECT_FILENAME, manifest)
    write_json(project_dir / CORPUS_FILENAME, [])
    write_json(project_dir / "pipelines/default_pipeline.json", manifest["pipeline"])
    write_json(project_dir / "metadata/import_template.json", manifest["import_template"])
    for kind, sheet in manifest["dictionary_set"]["sheets"].items():
        write_json(project_dir / f"dictionaries/{kind}.json", sheet)
    return project_dir, manifest


def build_project_template(
    manifest: dict[str, Any],
    name: str | None = None,
    description: str | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    timestamp = utc_now_iso()
    return {
        "id": template_id or f"project-template-{uuid_suffix()}",
        "name": name or f"{manifest['name']} 模板",
        "description": description or manifest.get("description", ""),
        "source_profile": manifest["import_template"].get("source_profile", "generic"),
        "settings": deepcopy(manifest.get("settings", {})),
        "pipeline": deepcopy(manifest["pipeline"]),
        "dictionary_set": deepcopy(manifest["dictionary_set"]),
        "import_template": deepcopy(manifest["import_template"]),
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def create_project_from_template(
    name: str,
    description: str,
    template_payload: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    project_dir, manifest = create_project(name, description or template_payload.get("description", ""))
    if template_payload.get("settings"):
        manifest["settings"] = deepcopy(template_payload["settings"])
    manifest["pipeline"] = deepcopy(template_payload["pipeline"])
    manifest["dictionary_set"] = deepcopy(template_payload["dictionary_set"])
    manifest["import_template"] = deepcopy(template_payload["import_template"])
    save_project(project_dir, manifest, [])
    return project_dir, manifest


def save_project_template(
    manifest: dict[str, Any],
    name: str | None = None,
    description: str | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    payload = build_project_template(manifest, name=name, description=description, template_id=template_id)
    return save_template(project_templates_root(), payload)


def list_project_templates() -> list[dict[str, Any]]:
    return list_templates(project_templates_root())


def load_project_template(template_id: str) -> dict[str, Any]:
    return load_template(project_templates_root(), template_id)


def save_import_template_record(
    import_template: dict[str, Any],
    name: str | None = None,
    description: str | None = None,
    template_id: str | None = None,
) -> dict[str, Any]:
    payload = deepcopy(import_template)
    payload["id"] = template_id or payload.get("id") or f"import-template-{uuid_suffix()}"
    if name:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    return save_template(import_templates_root(), payload)


def list_import_templates() -> list[dict[str, Any]]:
    return list_templates(import_templates_root())


def load_import_template(template_id: str) -> dict[str, Any]:
    return load_template(import_templates_root(), template_id)


def save_project(project_dir: Path, manifest: dict[str, Any], corpus: list[dict[str, Any]]) -> None:
    ensure_project_layout(project_dir)
    manifest = normalize_project_manifest(manifest, corpus, project_dir)
    manifest["updated_at"] = utc_now_iso()
    write_json(project_dir / PROJECT_FILENAME, manifest)
    write_json(project_dir / CORPUS_FILENAME, corpus)
    write_json(project_dir / "pipelines/default_pipeline.json", manifest["pipeline"])
    write_json(project_dir / "metadata/import_template.json", manifest["import_template"])
    for kind, sheet in manifest["dictionary_set"]["sheets"].items():
        write_json(project_dir / f"dictionaries/{kind}.json", sheet)


def load_project(project_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest = read_json(project_dir / PROJECT_FILENAME)
    corpus = read_json(project_dir / CORPUS_FILENAME) if (project_dir / CORPUS_FILENAME).exists() else []
    manifest = normalize_project_manifest(manifest, corpus, project_dir)
    return manifest, corpus


def find_project_dir(project_id: str) -> Path | None:
    for project_dir in list_project_dirs():
        manifest_path = project_dir / PROJECT_FILENAME
        if manifest_path.exists():
            manifest = read_json(manifest_path)
            if manifest.get("id") == project_id:
                return project_dir
    return None


def list_project_dirs() -> list[Path]:
    return sorted(
        [
            path
            for path in projects_root().glob("*.tfproj")
            if path.is_dir()
        ]
    )


def delete_project(project_id: str) -> dict[str, Any]:
    project_dir = find_project_dir(project_id)
    if project_dir is None:
        raise ValueError(f"Project {project_id} not found")

    deleted_path = str(project_dir)
    shutil.rmtree(project_dir)
    remove_project_from_workspace(project_id)
    return {
        "project_id": project_id,
        "deleted_path": deleted_path,
    }


def project_package_name(manifest: dict[str, Any]) -> str:
    timestamp = str(manifest.get("updated_at") or utc_now_iso()).replace(":", "-").replace(".", "-")
    return f"{slugify(str(manifest.get('name') or manifest.get('id') or 'textflow-project'))}-{timestamp}{PROJECT_PACKAGE_EXTENSION}"


def normalize_project_package_path(path: Path) -> Path:
    if path.suffix.lower() == PROJECT_PACKAGE_EXTENSION:
        return path
    return path.with_suffix(PROJECT_PACKAGE_EXTENSION)


def find_project_root(search_root: Path) -> Path:
    direct_project = search_root / PROJECT_FILENAME
    if direct_project.exists():
        return search_root

    for manifest_path in sorted(search_root.rglob(PROJECT_FILENAME)):
        return manifest_path.parent
    raise ValueError(f"No project manifest found in {search_root}")


def _archive_members(project_dir: Path) -> list[Path]:
    members: list[Path] = []
    for path in sorted(project_dir.rglob("*")):
        if path.is_dir():
            continue
        relative_path = path.relative_to(project_dir)
        if relative_path.parts[:2] == ("exports", "backups"):
            continue
        members.append(path)
    return members


def export_project_package(project_dir: Path, output_path: Path | None = None) -> Path:
    manifest, _corpus = load_project(project_dir)
    if output_path is None:
        backup_dir = project_dir / "exports" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        output_path = backup_dir / project_package_name(manifest)
    output_path = normalize_project_package_path(output_path.expanduser().resolve())
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="textflow-project-package-") as temp_dir:
        zip_path = Path(temp_dir) / "project-package.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in _archive_members(project_dir):
                relative_path = path.relative_to(project_dir)
                archive.write(path, arcname=str(Path(project_dir.name) / relative_path))
        shutil.move(str(zip_path), output_path)

    return output_path


def import_project_package(package_path: Path) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    package_path = package_path.expanduser().resolve()
    if not package_path.exists():
        raise FileNotFoundError(f"Project package not found: {package_path}")

    with tempfile.TemporaryDirectory(prefix="textflow-project-import-") as temp_dir:
        temp_root = Path(temp_dir)
        shutil.unpack_archive(str(package_path), str(temp_root), format="zip")
        source_project_dir = find_project_root(temp_root)
        manifest = read_json(source_project_dir / PROJECT_FILENAME)
        corpus = read_json(source_project_dir / CORPUS_FILENAME) if (source_project_dir / CORPUS_FILENAME).exists() else []
        existing_dir = find_project_dir(str(manifest.get("id")))
        target_dir = ensure_unique_project_dir(str(manifest.get("name") or source_project_dir.stem))
        shutil.copytree(source_project_dir, target_dir)
        manifest, corpus = load_project(target_dir)

        if existing_dir is not None:
            timestamp = utc_now_iso()
            manifest["id"] = f"project-{uuid_suffix()}"
            manifest["name"] = f"{manifest['name']} 导入副本"
            manifest["created_at"] = timestamp
            manifest["updated_at"] = timestamp
            for run in manifest.get("run_history", []):
                run["project_id"] = manifest["id"]

        save_project(target_dir, manifest, corpus)
        return target_dir, manifest, corpus


def build_project_summary(project_dir: Path, manifest: dict[str, Any], corpus: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": manifest["id"],
        "name": manifest["name"],
        "description": manifest["description"],
        "path": str(project_dir),
        "updated_at": manifest["updated_at"],
        "document_count": len(corpus),
        "run_count": len(manifest.get("run_history", [])),
    }


def duplicate_project(project_id: str, duplicated_name: str | None = None) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    source_dir = find_project_dir(project_id)
    if source_dir is None:
        raise ValueError(f"Project {project_id} not found")

    source_manifest, _ = load_project(source_dir)
    target_name = duplicated_name or f"{source_manifest['name']} 副本"
    target_dir = ensure_unique_project_dir(target_name)
    shutil.copytree(source_dir, target_dir)

    manifest, corpus = load_project(target_dir)
    timestamp = utc_now_iso()
    manifest["id"] = f"project-{uuid_suffix()}"
    manifest["name"] = target_name
    manifest["created_at"] = timestamp
    manifest["updated_at"] = timestamp
    refresh_manifest_paths(manifest, target_dir)

    for run in manifest.get("run_history", []):
        run["project_id"] = manifest["id"]

    save_project(target_dir, manifest, corpus)
    return target_dir, manifest, corpus


def uuid_suffix() -> str:
    return uuid4().hex[:12]


def load_workspace_snapshot() -> dict[str, Any]:
    project_records: dict[str, tuple[Path, dict[str, Any], list[dict[str, Any]], dict[str, Any]]] = {}

    for project_dir in list_project_dirs():
        manifest, corpus = load_project(project_dir)
        summary = build_project_summary(project_dir, manifest, corpus)
        project_records[manifest["id"]] = (project_dir, manifest, corpus, summary)

    state = forget_missing_projects(set(project_records))
    recent_projects: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for project_id in state["recent_project_ids"]:
        if project_id in project_records:
            recent_projects.append(project_records[project_id][3])
            seen_ids.add(project_id)

    remaining_summaries = [
        record[3]
        for project_id, record in project_records.items()
        if project_id not in seen_ids
    ]
    remaining_summaries.sort(key=lambda item: item["updated_at"], reverse=True)
    recent_projects.extend(remaining_summaries)

    current_project = None
    current_corpus: list[dict[str, Any]] = []
    selected_run = None
    current_project_id = state.get("current_project_id")

    if current_project_id is None and recent_projects:
        current_project_id = recent_projects[0]["id"]
        state = remember_project(current_project_id, set_current=True)

    if current_project_id and current_project_id in project_records:
        _project_dir, manifest, corpus, _summary = project_records[current_project_id]
        current_project = manifest
        current_corpus = corpus
        history = manifest.get("run_history", [])
        selected_run = history[-1] if history else None

    return {
        "recent_projects": recent_projects,
        "current_project": current_project,
        "corpus": current_corpus,
        "selected_run": selected_run,
    }
