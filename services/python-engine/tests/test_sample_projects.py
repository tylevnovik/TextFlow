from __future__ import annotations

import pytest

from app.node_definitions import build_builtin_node_definitions
from app.sample_dataset_cache import write_normalized_sample_cache
from app.sample_dataset_sources import normalize_public_sample_row
from app.sample_projects import BUILTIN_SAMPLE_PROJECTS, _sample_row_count, create_builtin_sample_projects


def _cache_row(dataset_id: str, language: str, idx: int) -> dict[str, object]:
    source_url_map = {
        "un_parallel_en_zh": "https://www.un.org/dgacm/en/node/5471",
        "wikimedia_enwiki": "https://dumps.wikimedia.org/enwiki/latest/",
        "wikimedia_zhwiki": "https://dumps.wikimedia.org/zhwiki/latest/",
        "openalex_works": "https://api.openalex.org/works",
    }
    category = "policy" if idx % 2 == 0 else "technology"
    institution = (
        ["OpenAI Research", "Example Institute", "Policy Lab"][idx % 3]
        if language == "en"
        else ["清华大学", "复旦大学", "政策研究院"][idx % 3]
    )
    raw_text = (
        f"Public {dataset_id} document {idx} discusses {category} strategy, topic clustering, keyword extraction, and language balance."
        if language == "en"
        else f"公开数据 {dataset_id} 文档 {idx} 讨论 {category} 策略、主题聚类、关键词提取和语言平衡。"
    )
    return normalize_public_sample_row(
        {
            "doc_id": f"{dataset_id}-{language}-{idx}",
            "title": f"{dataset_id} {language} title {idx}",
            "raw_text": raw_text,
            "year": 2018 + (idx % 6),
            "source": dataset_id,
            "institution": institution,
            "category_or_tag": category,
            "keyword_field": "topic modeling; keyword extraction" if language == "en" else "主题建模; 关键词提取",
        },
        dataset_id=dataset_id,
        language=language,
        source_record_id=f"{dataset_id}-{language}-{idx}",
        source_url=source_url_map[dataset_id],
        source_profile="literature" if dataset_id == "openalex_works" else "generic",
    )


def _populate_public_sample_cache(monkeypatch, tmp_path) -> None:
    cache_root = tmp_path / "public-sample-cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TEXTFLOW_PUBLIC_SAMPLE_CACHE_ROOT", str(cache_root))

    row_count = 240
    write_normalized_sample_cache(
        cache_root,
        "un_parallel_en_zh",
        [_cache_row("un_parallel_en_zh", "en", idx) for idx in range(row_count)]
        + [_cache_row("un_parallel_en_zh", "zh", idx) for idx in range(row_count)],
    )
    write_normalized_sample_cache(
        cache_root,
        "wikimedia_enwiki",
        [_cache_row("wikimedia_enwiki", "en", idx) for idx in range(row_count)],
    )
    write_normalized_sample_cache(
        cache_root,
        "wikimedia_zhwiki",
        [_cache_row("wikimedia_zhwiki", "zh", idx) for idx in range(row_count)],
    )
    write_normalized_sample_cache(
        cache_root,
        "openalex_works",
        [_cache_row("openalex_works", "en", idx) for idx in range(row_count)]
        + [_cache_row("openalex_works", "zh", idx) for idx in range(row_count)],
    )


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


def test_sample_workflows_cover_all_non_legacy_nodes():
    covered = set()
    for spec in BUILTIN_SAMPLE_PROJECTS:
        covered.update(spec["covered_nodes"])
    registry_nodes = {
        definition["type"]
        for definition in build_builtin_node_definitions()
        if definition.get("category") != "legacy"
    }
    assert registry_nodes - covered == set()


def test_sample_workflow_nodes_match_declared_coverage(monkeypatch, isolated_workspace, tmp_path):
    _populate_public_sample_cache(monkeypatch, tmp_path)
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "120")
    created = create_builtin_sample_projects()
    for _project_dir, manifest in created:
        workflow_nodes = {node["node_type"] for node in manifest["workflow_definitions"][0]["nodes"]}
        declared = set(manifest["settings"]["sample_project"]["covered_nodes"])
        assert declared <= workflow_nodes | {"artifact_preview", "review_task", "experiment_matrix", "run_diff", "incremental_run"}


def test_created_sample_projects_persist_guidance_metadata(monkeypatch, isolated_workspace, tmp_path):
    _populate_public_sample_cache(monkeypatch, tmp_path)
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "120")
    created = create_builtin_sample_projects()
    for _project_dir, manifest in created:
        sample = manifest["settings"]["sample_project"]
        assert sample["order"] >= 1
        assert sample["difficulty"]
        assert sample["goal"]
        assert sample["guided_steps"]
        assert sample["default_row_count"] >= 10_000
        assert sample["public_row_count"] == 120
        assert sample["language_balance"] == {"en": 0.5, "zh": 0.5}
        assert sample["language_counts"] == {"en": 60, "zh": 60}


def test_review_and_experiment_sample_contains_product_surfaces(monkeypatch, isolated_workspace, tmp_path):
    _populate_public_sample_cache(monkeypatch, tmp_path)
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "120")
    created = create_builtin_sample_projects()
    review_sample = next(manifest for _project_dir, manifest in created if manifest["name"] == "示例 05 - 复核实验与增量运行")
    assert review_sample["review_tasks"]
    assert review_sample["experiment_specs"]
