from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
import sys
from typing import Any

DEFAULT_PROJECT_CONFIG: dict[str, Any] = {
    "product": {
        "name": "TextFlow Studio",
        "identifier": "com.textflow.studio",
        "version": "0.2.0",
    },
    "engine": {
        "serviceTitle": "TextFlow Python Engine",
    },
}


def _candidate_config_paths() -> list[Path]:
    candidates: list[Path] = []
    configured = os.getenv("TEXTFLOW_CONFIG_PATH", "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())

    module_path = Path(__file__).resolve()
    for parent in [module_path.parent, *module_path.parents]:
        candidates.append(parent / "textflow.config.json")

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "textflow.config.json")
        bundle_root = getattr(sys, "_MEIPASS", "")
        if bundle_root:
            candidates.append(Path(bundle_root) / "textflow.config.json")
            candidates.append(Path(bundle_root) / "app" / "textflow.config.json")

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


@lru_cache(maxsize=1)
def load_project_config() -> dict[str, Any]:
    for candidate in _candidate_config_paths():
        if not candidate.exists() or not candidate.is_file():
            continue
        with candidate.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
        return {
            "product": {
                **DEFAULT_PROJECT_CONFIG["product"],
                **(config.get("product") if isinstance(config.get("product"), dict) else {}),
            },
            "engine": {
                **DEFAULT_PROJECT_CONFIG["engine"],
                **(config.get("engine") if isinstance(config.get("engine"), dict) else {}),
            },
        }
    return DEFAULT_PROJECT_CONFIG


def product_version() -> str:
    return str(load_project_config()["product"]["version"])


def product_name() -> str:
    return str(load_project_config()["product"]["name"])


def engine_service_title() -> str:
    return str(load_project_config()["engine"]["serviceTitle"])
