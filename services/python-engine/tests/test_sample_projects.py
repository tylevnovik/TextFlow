from __future__ import annotations

import pytest

from app.sample_projects import BUILTIN_SAMPLE_PROJECTS, _sample_row_count


def test_builtin_sample_specs_cover_nine_scenarios():
    assert len(BUILTIN_SAMPLE_PROJECTS) == 9
    assert [spec["order"] for spec in BUILTIN_SAMPLE_PROJECTS] == list(range(1, 10))
    assert all(spec["default_row_count"] >= 10_000 for spec in BUILTIN_SAMPLE_PROJECTS)
    assert all(spec["source_datasets"] for spec in BUILTIN_SAMPLE_PROJECTS)
    assert all(spec["language_balance"] == {"en": 0.5, "zh": 0.5} for spec in BUILTIN_SAMPLE_PROJECTS)


def test_builtin_sample_specs_include_guidance_and_coverage():
    for spec in BUILTIN_SAMPLE_PROJECTS:
        assert spec["goal"]
        assert spec["guided_steps"]
        assert spec["covered_nodes"]
        assert spec["difficulty"] in {"基础", "进阶", "高级"}
        assert spec["public_data_only"] is True
        assert {source["language"] for source in spec["sources"]} == {"en", "zh"}


def test_sample_row_count_rejects_odd_override(monkeypatch):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "101")
    with pytest.raises(ValueError):
        _sample_row_count(BUILTIN_SAMPLE_PROJECTS[0])
