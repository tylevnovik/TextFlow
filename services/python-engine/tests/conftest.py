from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
