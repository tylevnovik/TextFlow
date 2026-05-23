from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.samples.bundled_workspace import build_bundled_sample_workspace

TEST_SAMPLE_ROW_LIMIT = 24


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


def _write_wos_seed(path: Path, row_count: int = 80) -> Path:
    rows = []
    terms = ["dysprosium", "neodymium", "rare earth", "critical materials", "recycling", "separation"]
    for index in range(row_count):
        term_a = terms[index % len(terms)]
        term_b = terms[(index + 2) % len(terms)]
        rows.append(
            {
                "UT": f"WOS:{index + 1:05d}",
                "TI": f"Rare earth {term_a} recovery route {index + 1}",
                "AB": f"This paper studies {term_a} and {term_b} recovery with rare earth recycling and separation.",
                "DE": f"rare earth; {term_a}; recycling",
                "ID": f"critical materials; {term_b}",
                "AU": "Li; Wang",
                "C1": "Example University; Materials Institute",
                "PY": 2018 + (index % 8),
                "SO": "Journal of Rare Earth Studies",
                "WC": "Materials Science",
                "DT": "Article",
                "DOI": f"10.1000/wos.{index + 1}",
            }
        )
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


def _write_incopat_seed(path: Path, row_count: int = 80) -> Path:
    rows = []
    methods = ["萃取", "吸附", "磁选", "浸出", "回收", "分离"]
    for index in range(row_count):
        method = methods[index % len(methods)]
        rows.append(
            {
                "公开（公告）号": f"CN{index + 1:08d}A",
                "标题 (中文)": f"一种稀土{method}回收方法 {index + 1}",
                "摘要 (中文)": f"本发明涉及稀土材料的{method}、分离和回收利用，适用于磁性材料和关键矿物处理。",
                "首项权利要求": f"一种包含{method}步骤的稀土回收工艺。",
                "技术功效短语": f"稀土回收; {method}; 磁性材料",
                "申请人": "示例科技大学; 稀土材料研究院",
                "发明人": "张三; 李四",
                "公开国别": "CN",
                "IPC": "C22B59/00",
                "公开（公告）日": pd.Timestamp(f"{2017 + (index % 9)}-06-15"),
                "被引证次数": index % 7,
                "引证次数": index % 5,
            }
        )
    pd.DataFrame(rows).to_excel(path, index=False)
    return path


@pytest.fixture(scope="session")
def sample_seed_paths(tmp_path_factory):
    root = tmp_path_factory.mktemp("sample-seeds")
    return {
        "wos": _write_wos_seed(root / "wos-rare-earth.xlsx"),
        "incopat": _write_incopat_seed(root / "incopat-rare-earth.xlsx"),
    }


@pytest.fixture(autouse=True)
def sample_seed_environment(monkeypatch, sample_seed_paths):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_WOS_SOURCE", str(sample_seed_paths["wos"]))
    monkeypatch.setenv("TEXTFLOW_SAMPLE_INCOPAT_SOURCE", str(sample_seed_paths["incopat"]))
    monkeypatch.setenv("TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA", "1")


@pytest.fixture
def isolated_workspace(monkeypatch, scratch_dir, sample_seed_paths):
    workspace = scratch_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TEXTFLOW_WORKSPACE_ROOT", str(workspace))
    monkeypatch.setenv("TEXTFLOW_SAMPLE_WOS_SOURCE", str(sample_seed_paths["wos"]))
    monkeypatch.setenv("TEXTFLOW_SAMPLE_INCOPAT_SOURCE", str(sample_seed_paths["incopat"]))
    monkeypatch.setenv("TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA", "1")
    return workspace


@pytest.fixture(scope="session")
def bundled_sample_workspace_120(tmp_path_factory, sample_seed_paths):
    workspace_root = tmp_path_factory.mktemp("bundled-sample-workspace") / "row-limit-24"
    with temporary_environment(
        {
            "TEXTFLOW_SAMPLE_WOS_SOURCE": str(sample_seed_paths["wos"]),
            "TEXTFLOW_SAMPLE_INCOPAT_SOURCE": str(sample_seed_paths["incopat"]),
            "TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA": "1",
            "TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT": None,
            "TEXTFLOW_WORKSPACE_ROOT": None,
        }
    ):
        build_bundled_sample_workspace(workspace_root, row_count_override=TEST_SAMPLE_ROW_LIMIT)
    return workspace_root


def placeholder_row(index: int = 0) -> dict[str, object]:
    return {
        "id": f"placeholder-{index}",
        "doc_id": f"placeholder-{index}",
        "source_profile": "generic",
        "title": f"placeholder title {index}",
        "raw_text": f"placeholder synthetic sample text {index}",
        "year": 2020,
        "source": "legacy",
        "institution": "Legacy University",
        "extra_metadata": {"synthetic_sample_seed": True},
        "status": "ready",
    }
