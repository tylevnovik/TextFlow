from __future__ import annotations

import argparse
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from ..domain.common import utc_now_iso
from ..storage.projects import (
    PROJECT_FILENAME,
    WORKSPACE_ENV_VAR,
    WORKSPACE_FILENAME,
    default_workspace_state,
    load_project,
    normalize_workspace_state,
    save_project,
    save_workspace_state,
    write_json,
)
from .projects import (
    BUILTIN_SAMPLE_PROJECT_BY_NAME,
    BUILTIN_SAMPLE_PROJECT_BY_SLUG,
    BUILTIN_SAMPLE_PROJECT_DATA_REVISION,
    BUILTIN_SAMPLE_PROJECTS,
    FIRST_BUILTIN_SAMPLE_PROJECT_NAME,
    LEGACY_BUILTIN_SAMPLE_SLUGS,
    create_builtin_sample_projects,
)

BUNDLED_SAMPLE_WORKSPACE_ENV_VAR = "TEXTFLOW_BUNDLED_SAMPLE_WORKSPACE_ROOT"
BUNDLED_SAMPLE_WORKSPACE_DIRNAME = "bundled_sample_workspace"
BUNDLED_SAMPLE_WORKSPACE_METADATA_FILENAME = "bundled_workspace.json"
SAMPLE_ROW_LIMIT_ENV_VAR = "TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT"


def default_bundled_sample_workspace_root() -> Path:
    return Path(__file__).resolve().parents[1] / BUNDLED_SAMPLE_WORKSPACE_DIRNAME


def bundled_sample_workspace_root() -> Path:
    configured_root = os.getenv(BUNDLED_SAMPLE_WORKSPACE_ENV_VAR)
    if configured_root:
        return Path(configured_root).expanduser().resolve()
    return default_bundled_sample_workspace_root()


def bundled_sample_workspace_metadata_path(root: Path | None = None) -> Path:
    return (root or bundled_sample_workspace_root()) / BUNDLED_SAMPLE_WORKSPACE_METADATA_FILENAME


def load_bundled_sample_workspace_metadata(root: Path | None = None) -> dict[str, Any] | None:
    metadata_path = bundled_sample_workspace_metadata_path(root)
    if not metadata_path.exists():
        return None
    try:
        payload = metadata_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        import json

        parsed = json.loads(payload)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def requested_sample_row_limit() -> int | None:
    override = os.getenv(SAMPLE_ROW_LIMIT_ENV_VAR)
    if not override:
        return None
    return int(override)


@contextmanager
def temporary_environment(name: str, value: str | None) -> Iterator[None]:
    original = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if original is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = original


def _clear_directory_contents(path: Path) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _directory_tree_is_empty(path: Path) -> bool:
    if not path.exists():
        return True
    for child in path.iterdir():
        if child.is_file():
            return False
        if child.is_dir() and not _directory_tree_is_empty(child):
            return False
    return True


def _seed_workspace_state(created: list[tuple[Path, dict[str, Any]]]) -> None:
    state = default_workspace_state()
    state["recent_project_ids"] = [manifest["id"] for _project_dir, manifest in created]
    state["current_project_id"] = created[0][1]["id"] if created else None
    state["bootstrap_completed"] = True
    state["builtin_samples_revision"] = BUILTIN_SAMPLE_PROJECT_DATA_REVISION
    save_workspace_state(state)


def _strip_bundled_raw_source_files(project_dir: Path, manifest: dict[str, Any]) -> None:
    seed_dir = project_dir / "metadata" / "sample_seed"
    if seed_dir.exists():
        shutil.rmtree(seed_dir)

    imported_dir = project_dir / "corpus" / "imported"
    if imported_dir.exists():
        shutil.rmtree(imported_dir)
        imported_dir.mkdir(parents=True, exist_ok=True)

    source_files = manifest.get("source_files") if isinstance(manifest.get("source_files"), list) else []
    for source in source_files:
        if not isinstance(source, dict):
            continue
        source["relative_path"] = ""
        source["retained_in_project"] = False
    project_file = project_dir / PROJECT_FILENAME
    if project_file.exists():
        _normalized_manifest, corpus = load_project(project_dir)
        save_project(project_dir, manifest, corpus, already_normalized=True, dirty_sections={"manifest", "dictionary_set"})


def build_bundled_sample_workspace(
    target_root: Path | None = None,
    *,
    row_count_override: int | None = None,
) -> Path:
    root = (target_root or bundled_sample_workspace_root()).expanduser().resolve()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    row_limit_value = None if row_count_override is None else str(int(row_count_override))
    with temporary_environment(WORKSPACE_ENV_VAR, str(root)), temporary_environment(SAMPLE_ROW_LIMIT_ENV_VAR, row_limit_value):
        created = create_builtin_sample_projects()
        _seed_workspace_state(created)

        # Strip raw import source files from bundled projects to reduce installer size.
        # Corpus rows are already persisted in project.db; bundled samples should open
        # as imported projects instead of pointing at raw seed files.
        for project_dir, manifest in created:
            _strip_bundled_raw_source_files(project_dir, manifest)

    metadata = {
        "version": "1.0.0",
        "built_at": utc_now_iso(),
        "builtin_samples_revision": BUILTIN_SAMPLE_PROJECT_DATA_REVISION,
        "row_limit": row_count_override,
        "project_count": len(created),
        "project_names": [manifest["name"] for _project_dir, manifest in created],
        "starter_project_name": FIRST_BUILTIN_SAMPLE_PROJECT_NAME,
        "sample_orders": [int(spec["order"]) for spec in BUILTIN_SAMPLE_PROJECTS],
    }
    write_json(bundled_sample_workspace_metadata_path(root), metadata)
    return root


def bundled_sample_workspace_is_usable(root: Path | None = None) -> bool:
    template_root = (root or bundled_sample_workspace_root()).expanduser().resolve()
    if not template_root.exists():
        return False

    metadata = load_bundled_sample_workspace_metadata(template_root)
    if metadata is None:
        return False

    try:
        revision = int(metadata.get("builtin_samples_revision") or 0)
    except (TypeError, ValueError):
        return False
    if revision != BUILTIN_SAMPLE_PROJECT_DATA_REVISION:
        return False

    requested_limit = requested_sample_row_limit()
    metadata_limit = metadata.get("row_limit")
    if metadata_limit is None:
        if requested_limit is not None:
            return False
    else:
        try:
            normalized_metadata_limit = int(metadata_limit)
        except (TypeError, ValueError):
            return False
        if requested_limit != normalized_metadata_limit:
            return False

    projects_dir = template_root / "projects"
    workspace_state_path = projects_dir / "workspace.json"
    if not projects_dir.exists() or not workspace_state_path.exists():
        return False

    return any(projects_dir.glob("*.tfproj"))


def _workspace_state_path_for_root(root: Path) -> Path:
    return root / "projects" / WORKSPACE_FILENAME


def _load_workspace_state_for_root(root: Path) -> dict[str, Any]:
    state_path = _workspace_state_path_for_root(root)
    if not state_path.exists():
        return default_workspace_state()
    try:
        import json

        parsed = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return default_workspace_state()
    return normalize_workspace_state(parsed if isinstance(parsed, dict) else None)


def _save_workspace_state_for_root(root: Path, state: dict[str, Any]) -> None:
    write_json(_workspace_state_path_for_root(root), normalize_workspace_state(state))


def _read_project_manifest(project_dir: Path) -> dict[str, Any] | None:
    manifest_path = project_dir / PROJECT_FILENAME
    if not manifest_path.exists():
        return None
    try:
        import json

        parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _builtin_sample_slug_from_manifest(manifest: dict[str, Any]) -> str | None:
    settings = manifest.get("settings") if isinstance(manifest.get("settings"), dict) else {}
    sample_project = settings.get("sample_project") if isinstance(settings.get("sample_project"), dict) else {}
    slug = str(sample_project.get("slug") or "").strip()
    if slug in LEGACY_BUILTIN_SAMPLE_SLUGS:
        return str(BUILTIN_SAMPLE_PROJECTS[0]["slug"])
    if slug in BUILTIN_SAMPLE_PROJECT_BY_SLUG:
        return slug

    spec = BUILTIN_SAMPLE_PROJECT_BY_NAME.get(str(manifest.get("name") or ""))
    if spec is None:
        return None
    return str(spec["slug"])


def _project_manifest_records(projects_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    records: list[tuple[Path, dict[str, Any]]] = []
    if not projects_dir.exists():
        return records
    for project_dir in sorted(projects_dir.glob("*.tfproj")):
        if not project_dir.is_dir():
            continue
        manifest = _read_project_manifest(project_dir)
        if manifest is not None:
            records.append((project_dir, manifest))
    return records


def _builtin_template_records(template_root: Path) -> list[tuple[Path, dict[str, Any], str]]:
    projects_dir = template_root / "projects"
    records: list[tuple[Path, dict[str, Any], str]] = []
    order_by_slug = {str(spec["slug"]): int(spec["order"]) for spec in BUILTIN_SAMPLE_PROJECTS}
    for project_dir, manifest in _project_manifest_records(projects_dir):
        slug = _builtin_sample_slug_from_manifest(manifest)
        if slug is None:
            continue
        records.append((project_dir, manifest, slug))
    records.sort(key=lambda item: order_by_slug.get(item[2], 999))
    return records


def _unique_project_target(projects_dir: Path, preferred_name: str) -> Path:
    target = projects_dir / preferred_name
    if not target.exists():
        return target
    stem = Path(preferred_name).stem
    suffix = Path(preferred_name).suffix
    index = 2
    while True:
        candidate = projects_dir / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _copy_builtin_template_project(source_dir: Path, destination_projects_dir: Path, destination_root: Path) -> dict[str, Any] | None:
    target = _unique_project_target(destination_projects_dir, source_dir.name)
    shutil.copytree(source_dir, target)
    manifest = _read_project_manifest(target)
    if manifest is None:
        return None
    manifest.setdefault("paths", {})
    if isinstance(manifest["paths"], dict):
        manifest["paths"]["root"] = target.relative_to(destination_root).as_posix()
    write_json(target / PROJECT_FILENAME, manifest)
    return manifest


def restore_builtin_sample_projects_from_bundled(
    destination_root: Path,
    *,
    template_root: Path | None = None,
    create_missing: bool = True,
) -> bool:
    source_root = (template_root or bundled_sample_workspace_root()).expanduser().resolve()
    destination_root = destination_root.expanduser().resolve()

    if not bundled_sample_workspace_is_usable(source_root):
        return False

    template_records = _builtin_template_records(source_root)
    if not template_records:
        return False

    destination_projects_dir = destination_root / "projects"
    destination_projects_dir.mkdir(parents=True, exist_ok=True)
    state = _load_workspace_state_for_root(destination_root)

    existing_by_slug: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    removed_project_ids: set[str] = set()
    for project_dir, manifest in _project_manifest_records(destination_projects_dir):
        slug = _builtin_sample_slug_from_manifest(manifest)
        if slug is not None:
            existing_by_slug.setdefault(slug, []).append((project_dir, manifest))

    effective_create_missing = create_missing or bool(existing_by_slug)
    if not effective_create_missing:
        return False

    template_slugs = {slug for _project_dir, _manifest, slug in template_records}
    for slug in template_slugs:
        for project_dir, manifest in existing_by_slug.get(slug, []):
            project_id = str(manifest.get("id") or "")
            if project_id:
                removed_project_ids.add(project_id)
            shutil.rmtree(project_dir, ignore_errors=True)

    sample_project_ids: list[str] = []
    starter_project_id: str | None = None
    for source_dir, _source_manifest, slug in template_records:
        copied_manifest = _copy_builtin_template_project(source_dir, destination_projects_dir, destination_root)
        if copied_manifest is None:
            continue
        project_id = str(copied_manifest.get("id") or "")
        if project_id:
            sample_project_ids.append(project_id)
            if copied_manifest.get("name") == FIRST_BUILTIN_SAMPLE_PROJECT_NAME:
                starter_project_id = project_id
        if starter_project_id is None and slug == str(BUILTIN_SAMPLE_PROJECTS[0]["slug"]):
            starter_project_id = project_id or None

    valid_project_ids = [
        str(manifest.get("id") or "")
        for _project_dir, manifest in _project_manifest_records(destination_projects_dir)
        if manifest.get("id")
    ]
    valid_project_id_set = set(valid_project_ids)

    recent_project_ids: list[str] = []
    for project_id in state.get("recent_project_ids", []):
        if project_id in valid_project_id_set and project_id not in removed_project_ids and project_id not in recent_project_ids:
            recent_project_ids.append(project_id)
    if not recent_project_ids:
        recent_project_ids.extend(sample_project_ids)
    else:
        for project_id in sample_project_ids:
            if project_id not in recent_project_ids:
                recent_project_ids.append(project_id)
    for project_id in valid_project_ids:
        if project_id not in recent_project_ids:
            recent_project_ids.append(project_id)

    current_project_id = str(state.get("current_project_id") or "")
    if current_project_id not in valid_project_id_set or current_project_id in removed_project_ids:
        current_project_id = starter_project_id or (recent_project_ids[0] if recent_project_ids else "")

    state["recent_project_ids"] = recent_project_ids[:24]
    state["current_project_id"] = current_project_id or None
    state["bootstrap_completed"] = True
    state["builtin_samples_revision"] = BUILTIN_SAMPLE_PROJECT_DATA_REVISION
    _save_workspace_state_for_root(destination_root, state)
    return bool(sample_project_ids)


def restore_bundled_sample_workspace(
    destination_root: Path,
    *,
    template_root: Path | None = None,
    clear_destination: bool = False,
    allow_existing_scaffold: bool = False,
) -> bool:
    source_root = (template_root or bundled_sample_workspace_root()).expanduser().resolve()
    destination_root = destination_root.expanduser().resolve()

    if not bundled_sample_workspace_is_usable(source_root):
        return False

    destination_root.mkdir(parents=True, exist_ok=True)
    if any(destination_root.iterdir()):
        if not clear_destination:
            if not allow_existing_scaffold or not _directory_tree_is_empty(destination_root):
                return False
        else:
            _clear_directory_contents(destination_root)

    for child in source_root.iterdir():
        target = destination_root / child.name
        if child.is_dir():
            shutil.copytree(child, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, target)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a bundled sample workspace template for TextFlow.")
    parser.add_argument("--output", dest="output", default=None, help="Target workspace template directory.")
    parser.add_argument("--row-limit", dest="row_limit", type=int, default=None, help="Optional even row limit override for dev/test templates.")
    args = parser.parse_args()

    output_root = Path(args.output).expanduser() if args.output else None
    built_root = build_bundled_sample_workspace(output_root, row_count_override=args.row_limit)
    print(str(built_root))


if __name__ == "__main__":
    main()
