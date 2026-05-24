from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any

from .constants import (
    IMPORT_TEMPLATES_DIRNAME,
    PROJECT_TEMPLATES_DIRNAME,
    WORKSPACE_ENV_VAR,
    WORKSPACE_FILENAME,
)
from .io import read_json, write_json

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
        "builtin_samples_revision": 0,
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
    try:
        normalized["builtin_samples_revision"] = max(int(state.get("builtin_samples_revision", 0) or 0), 0)
    except (TypeError, ValueError):
        normalized["builtin_samples_revision"] = 0
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


def mark_workspace_bootstrapped(*, builtin_samples_revision: int | None = None) -> dict[str, Any]:
    state = load_workspace_state()
    state["bootstrap_completed"] = True
    if builtin_samples_revision is not None:
        state["builtin_samples_revision"] = max(int(builtin_samples_revision), 0)
    save_workspace_state(state)
    return state


def forget_missing_projects(valid_project_ids: set[str]) -> dict[str, Any]:
    state = load_workspace_state()
    state["recent_project_ids"] = [item for item in state["recent_project_ids"] if item in valid_project_ids]
    if state["current_project_id"] not in valid_project_ids:
        state["current_project_id"] = state["recent_project_ids"][0] if state["recent_project_ids"] else None
    save_workspace_state(state)
    return state
