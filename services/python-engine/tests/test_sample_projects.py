from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

import pandas as pd
import pytest

from app.bundled_sample_workspace import restore_bundled_sample_workspace
from app.node_definitions import build_builtin_node_definitions
from app.sample_dataset_sources import normalize_public_sample_row
from app.sample_projects import (
    BUILTIN_SAMPLE_PROJECT_DATA_REVISION,
    BUILTIN_SAMPLE_PROJECTS,
    FIRST_BUILTIN_SAMPLE_PROJECT_NAME,
    _is_synthetic_placeholder_row,
    _sample_row_count,
    _write_rows_to_source_file,
    create_builtin_sample_projects,
    reconcile_builtin_sample_projects,
)
from app.project_store import PROJECT_FILENAME, create_project, list_project_dirs, load_project, save_project
from app.workflow_runner import run_project_workflow
from tests.sample_test_support import TEST_SAMPLE_ROW_LIMIT, placeholder_row


@pytest.fixture
def public_sample_cache(monkeypatch, public_sample_cache_root):
    monkeypatch.setenv("TEXTFLOW_PUBLIC_SAMPLE_CACHE_ROOT", str(public_sample_cache_root))
    return public_sample_cache_root


@pytest.fixture(scope="session")
def bundled_builtin_sample_projects(bundled_sample_workspace_120):
    created: list[tuple[Path, dict[str, object]]] = []
    project_root = bundled_sample_workspace_120 / "projects"
    for project_dir in project_root.glob("*.tfproj"):
        manifest = json.loads((project_dir / PROJECT_FILENAME).read_text(encoding="utf-8"))
        created.append((project_dir, manifest))

    created.sort(
        key=lambda item: int(
            (
                item[1].get("settings", {})
                .get("sample_project", {})
                .get("order")
                or 999
            )
        )
    )
    return created


@pytest.fixture
def restored_builtin_sample_projects(monkeypatch, isolated_workspace, bundled_sample_workspace_120):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", str(TEST_SAMPLE_ROW_LIMIT))
    restored = restore_bundled_sample_workspace(
        isolated_workspace,
        template_root=bundled_sample_workspace_120,
        clear_destination=True,
    )
    assert restored

    created: list[tuple[Path, dict[str, object]]] = []
    for project_dir in list_project_dirs():
        manifest, _corpus = load_project(project_dir)
        created.append((project_dir, manifest))

    created.sort(
        key=lambda item: int(
            (
                item[1].get("settings", {})
                .get("sample_project", {})
                .get("order")
                or 999
            )
        )
    )
    return created


def _create_builtin_sample_projects_for_test(
    monkeypatch,
    public_sample_cache,
    *,
    row_limit: int = TEST_SAMPLE_ROW_LIMIT,
) -> list[tuple[Path, dict[str, object]]]:
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", str(row_limit))
    return create_builtin_sample_projects()


def _restored_sample_project(
    restored_builtin_sample_projects: list[tuple[Path, dict[str, object]]],
    sample_name: str,
) -> tuple[Path, dict[str, object]]:
    return next(item for item in restored_builtin_sample_projects if item[1]["name"] == sample_name)


def _run_restored_sample(
    restored_builtin_sample_projects: list[tuple[Path, dict[str, object]]],
    sample_name: str,
) -> tuple[Path, dict[str, object], list[dict[str, object]], dict[str, object]]:
    project_dir, _manifest = _restored_sample_project(restored_builtin_sample_projects, sample_name)
    manifest, corpus = load_project(project_dir)
    manifest, corpus, run = run_project_workflow(project_dir, manifest, corpus)
    return project_dir, manifest, corpus, run


def test_builtin_sample_specs_cover_nine_scenarios():
    assert len(BUILTIN_SAMPLE_PROJECTS) == 10
    assert [spec["order"] for spec in BUILTIN_SAMPLE_PROJECTS] == list(range(1, 11))
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


def test_sample_workflow_nodes_match_declared_coverage(bundled_builtin_sample_projects):
    created = bundled_builtin_sample_projects
    for _project_dir, manifest in created:
        workflow_nodes = {node["node_type"] for node in manifest["workflow_definitions"][0]["nodes"]}
        declared = set(manifest["settings"]["sample_project"]["covered_nodes"])
        assert declared <= workflow_nodes | {"artifact_preview", "review_task", "experiment_matrix", "run_diff", "incremental_run"}


def test_created_sample_projects_persist_guidance_metadata(bundled_builtin_sample_projects):
    created = bundled_builtin_sample_projects
    for _project_dir, manifest in created:
        sample = manifest["settings"]["sample_project"]
        assert sample["order"] >= 1
        assert sample["data_revision"] == BUILTIN_SAMPLE_PROJECT_DATA_REVISION
        assert sample["difficulty"]
        assert sample["goal"]
        assert sample["guided_steps"]
        assert sample["default_row_count"] >= 10_000
        assert sample["public_row_count"] == TEST_SAMPLE_ROW_LIMIT
        assert sample["language_balance"] == {"en": 0.5, "zh": 0.5}
        assert sample["language_counts"] == {"en": 60, "zh": 60}


def test_basic_preprocessing_sample_disables_full_audit_report(bundled_builtin_sample_projects):
    _project_dir, manifest = _restored_sample_project(bundled_builtin_sample_projects, "示例 01 - 基础文本预处理")
    workflow = manifest["workflow_definitions"][0]
    report_node = next(node for node in workflow["nodes"] if node["node_type"] == "save_html_report")
    assert report_node["config"]["include_audit"] is False


def test_basic_preprocessing_sample_disables_heavy_transform_node_cache(bundled_builtin_sample_projects):
    _project_dir, manifest = _restored_sample_project(bundled_builtin_sample_projects, "示例 01 - 基础文本预处理")
    workflow = manifest["workflow_definitions"][0]

    disabled_nodes = {
        node["node_type"]
        for node in workflow["nodes"]
        if (node.get("runtime_meta") or {}).get("cache_enabled") is False
    }

    assert {"clean_text", "normalize_text", "tokenize", "apply_dictionary_rules", "filter_terms"} <= disabled_nodes


def test_review_and_experiment_sample_contains_product_surfaces(bundled_builtin_sample_projects):
    _project_dir, review_sample = _restored_sample_project(bundled_builtin_sample_projects, "示例 05 - 复核实验与增量运行")
    assert review_sample["review_tasks"]
    assert review_sample["experiment_specs"]


@pytest.mark.engine_full
def test_create_builtin_sample_projects_creates_all_projects_with_large_defaults(monkeypatch, isolated_workspace, public_sample_cache):
    created = _create_builtin_sample_projects_for_test(monkeypatch, public_sample_cache, row_limit=150)
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
@pytest.mark.engine_full
def test_representative_sample_workflows_run(restored_builtin_sample_projects, sample_name):
    project_dir, manifest = _restored_sample_project(restored_builtin_sample_projects, sample_name)
    manifest, corpus = load_project(project_dir)
    manifest, corpus, run = run_project_workflow(project_dir, manifest, corpus)
    assert run["status"] == "completed"
    assert run["artifacts"]


@pytest.mark.engine_full
def test_basic_preprocessing_sample_run_avoids_full_audit_snapshot(restored_builtin_sample_projects):
    project_dir, manifest = _restored_sample_project(restored_builtin_sample_projects, "示例 01 - 基础文本预处理")
    manifest, corpus = load_project(project_dir)
    manifest, _corpus, run = run_project_workflow(project_dir, manifest, corpus)

    assert run["status"] == "completed"
    assert manifest["results"]["audit_table"] == []


@pytest.mark.engine_full
def test_dictionary_frequency_sample_removes_builtin_stopwords(restored_builtin_sample_projects):
    project_dir, _manifest = _restored_sample_project(restored_builtin_sample_projects, "示例 02 - 词表治理与词频统计")
    manifest, corpus = load_project(project_dir)
    manifest, processed_corpus, run = run_project_workflow(project_dir, manifest, corpus)

    frequency_terms = {str(row.get("term") or "") for row in manifest["results"]["frequency_table"]}
    surviving_tokens = {
        str(token)
        for row in processed_corpus
        for token in (row.get("tokens") or [])
    }

    assert run["status"] == "completed"
    assert "the" not in frequency_terms
    assert "a" not in frequency_terms
    assert "the" not in surviving_tokens
    assert "a" not in surviving_tokens


@pytest.mark.engine_full
def test_institution_topic_sample_produces_institution_and_trend_outputs(restored_builtin_sample_projects):
    _project_dir, manifest, _corpus, run = _run_restored_sample(restored_builtin_sample_projects, "示例 04 - 机构主题与技术方向")

    artifact_node_ids = {str(item.get("node_id") or "") for item in manifest["artifact_records"]}

    assert run["status"] == "completed"
    assert manifest["results"]["term_year_table"]
    assert manifest["results"]["institution_keyword_cooccurrence"]
    assert manifest["results"]["institution_topic_cooccurrence"]
    assert manifest["results"]["report_files"]
    assert {
        "node-term-year-analysis",
        "node-institution-keyword-analysis",
        "node-institution-topic-analysis",
        "node-save-xlsx",
        "node-save-html-report",
    } <= artifact_node_ids


@pytest.mark.engine_full
def test_review_experiment_sample_produces_keyword_outputs_and_surface_artifacts(restored_builtin_sample_projects):
    _project_dir, manifest, _corpus, run = _run_restored_sample(restored_builtin_sample_projects, "示例 05 - 复核实验与增量运行")

    artifact_node_ids = {str(item.get("node_id") or "") for item in manifest["artifact_records"]}

    assert run["status"] == "completed"
    assert manifest["review_tasks"]
    assert manifest["experiment_specs"]
    assert manifest["results"]["keyword_result"]
    assert manifest["results"]["keyword_cluster_result"]
    assert manifest["results"]["report_files"]
    assert {
        "node-keyword-extraction",
        "node-keyword-clustering",
        "node-save-html-report",
    } <= artifact_node_ids


@pytest.mark.engine_full
def test_split_evaluate_join_sample_produces_joined_and_evaluation_artifacts(restored_builtin_sample_projects):
    _project_dir, manifest, _corpus, run = _run_restored_sample(restored_builtin_sample_projects, "示例 08 - 切分评估与结果拼接")

    artifact_records_by_node = {
        str(item.get("node_id") or ""): item
        for item in manifest["artifact_records"]
    }

    assert run["status"] == "completed"
    assert manifest["results"]["clustering_result"]
    assert manifest["results"]["report_files"]
    assert artifact_records_by_node["node-cluster-evaluation"]["row_count"] > 0
    assert artifact_records_by_node["node-join-results"]["row_count"] > 0
    assert {
        "node-cluster-evaluation",
        "node-join-results",
        "node-save-csv",
        "node-save-xlsx",
    } <= set(artifact_records_by_node)


@pytest.mark.engine_full
def test_reconcile_builtin_sample_projects_refreshes_placeholder_corpus(monkeypatch, isolated_workspace, public_sample_cache):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", str(TEST_SAMPLE_ROW_LIMIT))
    project_dir, manifest = create_project(FIRST_BUILTIN_SAMPLE_PROJECT_NAME, "legacy placeholder sample")

    legacy_corpus = [
        placeholder_row("wikimedia_enwiki", "en", idx)
        for idx in range(60)
    ] + [
        placeholder_row("wikimedia_zhwiki", "zh", idx)
        for idx in range(60)
    ]
    manifest["settings"]["sample_project"] = {"slug": "sample-01-basic-preprocessing"}
    save_project(project_dir, manifest, legacy_corpus)

    reconcile_builtin_sample_projects()

    refreshed_manifest, refreshed_corpus = load_project(project_dir)
    assert refreshed_manifest["description"] == BUILTIN_SAMPLE_PROJECTS[0]["description"]
    assert refreshed_manifest["settings"]["sample_project"]["data_revision"] == BUILTIN_SAMPLE_PROJECT_DATA_REVISION
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
