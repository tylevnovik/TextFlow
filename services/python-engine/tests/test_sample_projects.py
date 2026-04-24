from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

from app.node_definitions import build_builtin_node_definitions
from app.sample_dataset_cache import read_normalized_sample_cache, write_normalized_sample_cache
from app.sample_dataset_sources import normalize_public_sample_row
from app.sample_projects import (
    BUILTIN_SAMPLE_PROJECTS,
    FIRST_BUILTIN_SAMPLE_PROJECT_NAME,
    _is_synthetic_placeholder_row,
    _sample_row_count,
    _write_rows_to_source_file,
    create_builtin_sample_projects,
    reconcile_builtin_sample_projects,
)
from app.project_store import create_project, load_project, save_project
from app.workflow_runner import run_project_workflow


def _bundled_public_sample_cache_root() -> Path:
    return Path(__file__).resolve().parents[1] / "app" / "public_sample_cache"


def _placeholder_row(dataset_id: str, language: str, idx: int) -> dict[str, object]:
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


def _copy_bundled_real_cache_rows(
    cache_root: Path,
    dataset_id: str,
    *,
    row_count_by_language: dict[str, int],
) -> None:
    bundled_root = _bundled_public_sample_cache_root()
    source_rows = read_normalized_sample_cache(bundled_root, dataset_id)
    selected_rows: list[dict[str, object]] = []
    for language, requested_count in row_count_by_language.items():
        language_rows = [
            row
            for row in source_rows
            if str(row.get("language") or "") == language
        ]
        if len(language_rows) < requested_count:
            raise AssertionError(
                f"Bundled real cache does not have enough rows for dataset={dataset_id} language={language}: "
                f"requested={requested_count} available={len(language_rows)}"
            )
        selected_rows.extend(language_rows[:requested_count])
    write_normalized_sample_cache(cache_root, dataset_id, selected_rows)


def _populate_public_sample_cache(monkeypatch, tmp_path) -> None:
    cache_root = tmp_path / "public-sample-cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TEXTFLOW_PUBLIC_SAMPLE_CACHE_ROOT", str(cache_root))

    row_count = 240
    _copy_bundled_real_cache_rows(
        cache_root,
        "un_parallel_en_zh",
        row_count_by_language={"en": row_count, "zh": row_count},
    )
    _copy_bundled_real_cache_rows(
        cache_root,
        "wikimedia_enwiki",
        row_count_by_language={"en": row_count},
    )
    _copy_bundled_real_cache_rows(
        cache_root,
        "wikimedia_zhwiki",
        row_count_by_language={"zh": row_count},
    )
    _copy_bundled_real_cache_rows(
        cache_root,
        "openalex_works",
        row_count_by_language={"en": row_count, "zh": row_count},
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


def test_create_builtin_sample_projects_creates_all_projects_with_large_defaults(monkeypatch, isolated_workspace, tmp_path):
    _populate_public_sample_cache(monkeypatch, tmp_path)
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "150")
    created = create_builtin_sample_projects()
    assert len(created) == 9
    for project_dir, manifest in created:
        _manifest, corpus = load_project(project_dir)
        assert len(corpus) >= 150
        assert manifest["settings"]["sample_project"]["default_row_count"] >= 10_000
        assert Counter(row["language"] for row in corpus) == {"en": len(corpus) // 2, "zh": len(corpus) // 2}
        assert all(row["language"] in {"en", "zh"} for row in corpus)
        assert not any(_is_synthetic_placeholder_row(row) for row in corpus[:8])


@pytest.mark.parametrize(
    "sample_name",
    [
        "示例 01 - 基础文本预处理",
        "示例 03 - 学术摘要关键词与主题",
        "示例 06 - 多来源语料合并与抽样",
        "示例 07 - 分组比较与关键性分析",
        "示例 09 - 条件路由与人工门禁",
    ],
)
def test_representative_sample_workflows_run(monkeypatch, isolated_workspace, tmp_path, sample_name):
    _populate_public_sample_cache(monkeypatch, tmp_path)
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "120")
    created = create_builtin_sample_projects()
    project_dir, manifest = next(item for item in created if item[1]["name"] == sample_name)
    manifest, corpus = load_project(project_dir)
    manifest, corpus, run = run_project_workflow(project_dir, manifest, corpus)
    assert run["status"] == "completed"
    assert run["artifacts"]


def test_reconcile_builtin_sample_projects_refreshes_placeholder_corpus(monkeypatch, isolated_workspace, tmp_path):
    _populate_public_sample_cache(monkeypatch, tmp_path)
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "120")
    project_dir, manifest = create_project(FIRST_BUILTIN_SAMPLE_PROJECT_NAME, "legacy placeholder sample")

    legacy_corpus = [
        _placeholder_row("wikimedia_enwiki", "en", idx)
        for idx in range(60)
    ] + [
        _placeholder_row("wikimedia_zhwiki", "zh", idx)
        for idx in range(60)
    ]
    manifest["settings"]["sample_project"] = {"slug": "sample-01-basic-preprocessing"}
    save_project(project_dir, manifest, legacy_corpus)

    reconcile_builtin_sample_projects()

    refreshed_manifest, refreshed_corpus = load_project(project_dir)
    assert refreshed_manifest["description"] == BUILTIN_SAMPLE_PROJECTS[0]["description"]
    assert refreshed_manifest["settings"]["sample_project"]["source_datasets"] == ["wikimedia_enwiki", "wikimedia_zhwiki"]
    assert Counter(row["language"] for row in refreshed_corpus) == {"en": 60, "zh": 60}
    assert not any(_is_synthetic_placeholder_row(row) for row in refreshed_corpus[:8])


def test_xlsx_seed_export_sanitizes_illegal_excel_characters(tmp_path):
    path = tmp_path / "seed.xlsx"
    row = normalize_public_sample_row(
        {
            "doc_id": "openalex-en-illegal",
            "title": "A real public record with a control character",
            "raw_text": "beta-VAE with appropriately tuned\f beta > 1 remains real text after cleanup.",
            "year": 2017,
            "source": "OpenAlex",
        },
        dataset_id="openalex_works",
        language="en",
        source_record_id="W-illegal",
        source_url="https://openalex.org/W-illegal",
        source_profile="literature",
    )

    _write_rows_to_source_file(path, "xlsx", [row])

    frame = pd.read_excel(path)
    assert frame.loc[0, "doc_id"] == "openalex-en-illegal"
    assert "\f" not in frame.loc[0, "raw_text"]
    assert "beta-VAE" in frame.loc[0, "raw_text"]
