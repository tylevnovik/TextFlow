from __future__ import annotations

import argparse
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .defaults import utc_now_iso
from .project_store import WORKSPACE_ENV_VAR, default_workspace_state, save_workspace_state, write_json
from .sample_projects import (
    BUILTIN_SAMPLE_PROJECT_DATA_REVISION,
    BUILTIN_SAMPLE_PROJECTS,
    FIRST_BUILTIN_SAMPLE_PROJECT_NAME,
    create_builtin_sample_projects,
)

BUNDLED_SAMPLE_WORKSPACE_ENV_VAR = "TEXTFLOW_BUNDLED_SAMPLE_WORKSPACE_ROOT"
BUNDLED_SAMPLE_WORKSPACE_DIRNAME = "bundled_sample_workspace"
BUNDLED_SAMPLE_WORKSPACE_METADATA_FILENAME = "bundled_workspace.json"
SAMPLE_ROW_LIMIT_ENV_VAR = "TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT"


def default_bundled_sample_workspace_root() -> Path:
    return Path(__file__).resolve().parent / BUNDLED_SAMPLE_WORKSPACE_DIRNAME


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


def _seed_workspace_state(created: list[tuple[Path, dict[str, Any]]]) -> None:
    state = default_workspace_state()
    state["recent_project_ids"] = [manifest["id"] for _project_dir, manifest in created]
    state["current_project_id"] = created[0][1]["id"] if created else None
    state["bootstrap_completed"] = True
    state["builtin_samples_revision"] = BUILTIN_SAMPLE_PROJECT_DATA_REVISION
    save_workspace_state(state)


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
    # Corpus is already persisted in project.db; seeds are recreated on first-run restore if needed.
    for project_dir, _manifest in created:
        seed_dir = project_dir / "metadata" / "sample_seed"
        if seed_dir.exists():
            shutil.rmtree(seed_dir)

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


def restore_bundled_sample_workspace(
    destination_root: Path,
    *,
    template_root: Path | None = None,
    clear_destination: bool = False,
) -> bool:
    source_root = (template_root or bundled_sample_workspace_root()).expanduser().resolve()
    destination_root = destination_root.expanduser().resolve()

    if not bundled_sample_workspace_is_usable(source_root):
        return False

    destination_root.mkdir(parents=True, exist_ok=True)
    if any(destination_root.iterdir()):
        if not clear_destination:
            return False
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
