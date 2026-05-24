from __future__ import annotations

import shutil
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..domain.common import utc_now_iso
from .constants import CORPUS_FILENAME, PROJECT_DATABASE_FILENAME, PROJECT_FILENAME, PROJECT_PACKAGE_EXTENSION
from .database import initialize_project_database, project_database_integrity_check
from .io import read_json
from .workspace import projects_root


def project_package_name(manifest: dict[str, Any]) -> str:
    from .projects import slugify

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
    from .projects import load_project, uuid_suffix

    manifest, _corpus = load_project(project_dir)
    if output_path is None:
        backup_dir = project_dir / "exports" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        output_path = backup_dir / project_package_name(manifest)
    output_path = normalize_project_package_path(output_path.expanduser().resolve())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output_path = output_path.with_name(f"{output_path.stem}-{uuid_suffix()}{output_path.suffix}.tmp")
    if temp_output_path.exists():
        temp_output_path.unlink()

    try:
        with zipfile.ZipFile(temp_output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in _archive_members(project_dir):
                relative_path = path.relative_to(project_dir)
                archive.write(path, arcname=str(Path(project_dir.name) / relative_path))
        temp_output_path.replace(output_path)
    finally:
        if temp_output_path.exists():
            temp_output_path.unlink()

    return output_path


def import_project_package(package_path: Path) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    from .projects import find_project_dir, ensure_unique_project_dir, load_project, save_project, uuid_suffix

    package_path = package_path.expanduser().resolve()
    if not package_path.exists():
        raise FileNotFoundError(f"Project package not found: {package_path}")

    temp_root = projects_root() / f".import-{uuid_suffix()}"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    try:
        shutil.unpack_archive(str(package_path), str(temp_root), format="zip")
        source_project_dir = find_project_root(temp_root)
        manifest = read_json(source_project_dir / PROJECT_FILENAME)
        corpus = read_json(source_project_dir / CORPUS_FILENAME) if (source_project_dir / CORPUS_FILENAME).exists() else []
        db_path = source_project_dir / PROJECT_DATABASE_FILENAME
        if db_path.exists():
            db = initialize_project_database(db_path)
            integrity = project_database_integrity_check(db)
            if integrity != "ok":
                raise ValueError(f"Project database integrity check failed: {integrity}")
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

        save_project(target_dir, manifest, corpus, already_normalized=True)
        return target_dir, manifest, corpus
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root, ignore_errors=True)

def duplicate_project(project_id: str, duplicated_name: str | None = None) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    from .projects import find_project_dir, ensure_unique_project_dir, load_project, refresh_manifest_paths, save_project, uuid_suffix

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

    save_project(target_dir, manifest, corpus, already_normalized=True)
    return target_dir, manifest, corpus
