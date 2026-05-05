from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bundled_sample_workspace import build_bundled_sample_workspace
from tests.sample_test_support import TEST_SAMPLE_ROW_LIMIT, populate_public_sample_cache


@contextmanager
def temporary_environment(overrides: dict[str, str | None]):
    original = {name: os.environ.get(name) for name in overrides}
    try:
        for name, value in overrides.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


@pytest.fixture
def scratch_dir():
    root = ROOT / ".test-scratch"
    root.mkdir(parents=True, exist_ok=True)
    path = root / uuid4().hex[:12]
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def isolated_workspace(monkeypatch, scratch_dir):
    workspace = scratch_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TEXTFLOW_WORKSPACE_ROOT", str(workspace))
    return workspace


@pytest.fixture(scope="session")
def public_sample_cache_root(tmp_path_factory):
    cache_root = tmp_path_factory.mktemp("public-sample-cache")
    return populate_public_sample_cache(cache_root)


@pytest.fixture(scope="session")
def bundled_sample_workspace_120(tmp_path_factory, public_sample_cache_root):
    workspace_root = tmp_path_factory.mktemp("bundled-sample-workspace") / "row-limit-120"
    with temporary_environment(
        {
            "TEXTFLOW_PUBLIC_SAMPLE_CACHE_ROOT": str(public_sample_cache_root),
            "TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT": None,
            "TEXTFLOW_WORKSPACE_ROOT": None,
        }
    ):
        build_bundled_sample_workspace(workspace_root, row_count_override=TEST_SAMPLE_ROW_LIMIT)
    return workspace_root
