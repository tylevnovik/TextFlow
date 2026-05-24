from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd
from sklearn.datasets import fetch_20newsgroups

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BENCHMARK_REQUIRES_ARTIFACT_STORE = True

from app.domain.defaults import default_import_template, utc_now_iso  # noqa: E402
from app.ingestion import import_files  # noqa: E402
from app.workflow.runner import run_project_workflow  # noqa: E402
from app.storage.projects import create_project, save_project  # noqa: E402
from app.samples.projects import _append_dictionary_terms  # noqa: E402
from app.workflow.templates import build_new_flow_workflow  # noqa: E402

KEEP_NODE_TYPES = {
    "corpus_input",
    "dictionary_input",
    "normalize_metadata",
    "deduplicate_documents",
    "clean_text",
    "normalize_text",
    "tokenize",
    "apply_dictionary_rules",
    "filter_terms",
    "frequency_statistics",
    "cooccurrence_analysis",
    "feature_term_selection",
    "keyword_extraction",
    "focus_terms",
    "keyword_clustering",
    "document_clustering",
    "save_csv",
    "save_png",
    "save_html_report",
}

NODE_CONFIG_OVERRIDES = {
    "deduplicate_documents": {"dedupe_keys_text": "doc_id,title"},
    "feature_term_selection": {"feature_term_count": 1000},
    "cooccurrence_analysis": {"cooccurrence_window": 3, "min_cooccurrence": 2},
    "keyword_extraction": {"top_k_per_doc": 8, "top_k_project": 120},
    "focus_terms": {"term_source": "keywords", "term_field": "keyword", "max_terms": 120, "project_keywords_only": True},
    "keyword_clustering": {"keyword_cluster_k": 8, "topic_model_k": 8},
    "document_clustering": {"document_cluster_k": 8},
    "save_html_report": {"include_audit": False},
}


def configure_benchmark_workflow(
    manifest: dict[str, Any],
    *,
    workflow_name: str,
    keep_node_types: set[str],
    node_config_overrides: dict[str, dict[str, Any]],
) -> None:
    workflow = build_new_flow_workflow(
        "wf-benchmark-20-newsgroups",
        workflow_name,
        source_profile=str(manifest.get("import_template", {}).get("source_profile") or "generic"),
        include_patent_graph=False,
    )
    kept_node_ids = {
        str(node.get("node_id") or "")
        for node in workflow.get("nodes", [])
        if isinstance(node, dict) and str(node.get("node_type") or "") in keep_node_types
    }
    workflow["nodes"] = [
        node
        for node in workflow.get("nodes", [])
        if isinstance(node, dict) and str(node.get("node_id") or "") in kept_node_ids
    ]
    workflow["edges"] = [
        edge
        for edge in workflow.get("edges", [])
        if isinstance(edge, dict)
        and str(edge.get("from_node") or "") in kept_node_ids
        and str(edge.get("to_node") or "") in kept_node_ids
    ]
    for node in workflow["nodes"]:
        override = node_config_overrides.get(str(node.get("node_type") or ""))
        if override:
            node["config"] = {
                **(node.get("config") if isinstance(node.get("config"), dict) else {}),
                **override,
            }
    manifest["workflow_definitions"] = [workflow]
    manifest["active_workflow_id"] = workflow["workflow_id"]

DICTIONARY_TERMS = {
    "phrase_lexicon": [
        ("space shuttle", "space_shuttle"),
        ("graphics card", "graphics_card"),
        ("x window", "x_window"),
        ("government policy", "government_policy"),
        ("car engine", "car_engine"),
    ],
}


def _safe_title(text: str, fallback: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return fallback
    title = re.sub(r"\s+", " ", lines[0]).strip()
    if len(title) > 120:
        title = f"{title[:117]}..."
    return title or fallback


def build_newsgroups_rows(limit: int | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dataset = fetch_20newsgroups(subset="train", remove=("headers", "footers", "quotes"))
    rows: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}

    for index, text in enumerate(dataset.data):
        if limit is not None and len(rows) >= limit:
            break
        normalized_text = re.sub(r"\s+", " ", str(text or "")).strip()
        if not normalized_text:
            continue
        category = dataset.target_names[int(dataset.target[index])]
        category_counts[category] = category_counts.get(category, 0) + 1
        rows.append(
            {
                "doc_id": f"NEWSFULL-{index + 1:05d}",
                "title": _safe_title(normalized_text, f"{category} #{index + 1}"),
                "raw_text": normalized_text,
                "source": "20 Newsgroups train",
                "category_or_tag": category,
                "keyword_field": category,
                "year": 1993,
            }
        )

    return rows, {
        "name": "20 Newsgroups train",
        "license": "Public research corpus",
        "url": "https://scikit-learn.org/stable/datasets/real_world.html#newsgroups-dataset",
        "category_count": len(category_counts),
        "category_counts": category_counts,
        "row_count": len(rows),
    }


def write_seed_csv(project_dir: Path, rows: list[dict[str, Any]]) -> Path:
    output_dir = project_dir / "metadata" / "benchmark_seed"
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "20_newsgroups_train_full.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
    return csv_path


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a large-workflow benchmark for TextFlow.")
    parser.add_argument("--limit", type=int, default=None, help="Optional row cap for debugging.")
    parser.add_argument(
        "--workspace-root",
        type=str,
        default=str(ROOT / ".tmp" / "benchmarks" / "workspace-large-newsgroups"),
        help="Isolated workspace root used during the benchmark run.",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).expanduser().resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)
    os.environ["TEXTFLOW_WORKSPACE_ROOT"] = str(workspace_root)

    benchmark_started = perf_counter()
    rows, dataset_meta = build_newsgroups_rows(limit=args.limit)
    project_dir, manifest = create_project(
        name=f"benchmark-20-newsgroups-{dataset_meta['row_count']}",
        description="万条级 20 Newsgroups 压力测试项目",
    )
    manifest["import_template"] = default_import_template("generic")
    manifest["import_template"] = {
        **manifest["import_template"],
        "text_build": {"mode": "concat_fields", "fields": ["title", "raw_text"], "delimiter": "\n\n", "skip_empty": True},
    }
    manifest.setdefault("settings", {})
    manifest["settings"]["sample_project"] = {
        "slug": "benchmark-20-newsgroups-train-full",
        "name": dataset_meta["name"],
        "license": dataset_meta["license"],
        "url": dataset_meta["url"],
        "workflow_name": "20 Newsgroups 全量压力测试流",
    }
    _append_dictionary_terms(manifest, DICTIONARY_TERMS)
    configure_benchmark_workflow(
        manifest,
        workflow_name="20 Newsgroups 全量压力测试流",
        keep_node_types=KEEP_NODE_TYPES,
        node_config_overrides=NODE_CONFIG_OVERRIDES,
    )

    source_path = write_seed_csv(project_dir, rows)

    import_started = perf_counter()
    corpus, source_files, issues = import_files([source_path], manifest["import_template"], project_dir=project_dir)
    import_seconds = round(perf_counter() - import_started, 3)
    manifest["source_files"] = source_files

    progress_events: list[dict[str, Any]] = []
    run_started = perf_counter()

    def on_progress(progress: float, message: str, _detail: dict[str, Any] | None = None) -> None:
        progress_events.append(
            {
                "elapsed_seconds": round(perf_counter() - run_started, 3),
                "progress": round(progress, 4),
                "message": message,
            }
        )

    manifest, corpus, run_record = run_project_workflow(project_dir, manifest, corpus, progress_callback=on_progress)
    run_seconds = round(perf_counter() - run_started, 3)
    save_project(project_dir, manifest, corpus, already_normalized=True)
    total_seconds = round(perf_counter() - benchmark_started, 3)

    result_bundle = manifest["results"]
    summary = {
        "generated_at": utc_now_iso(),
        "workspace_root": str(workspace_root),
        "project_dir": str(project_dir),
        "dataset": dataset_meta,
        "import": {
            "seconds": import_seconds,
            "imported_documents": len(corpus),
            "validation_issue_count": len(issues),
        },
        "run": {
            "seconds": run_seconds,
            "total_seconds": total_seconds,
            "status": run_record["status"],
            "run_id": run_record["run_id"],
            "processed_document_count": run_record["processed_document_count"],
            "artifact_store_enabled": True,
            "artifact_record_count": len(manifest.get("artifact_records", [])),
            "artifact_count": len(run_record.get("artifacts", [])),
            "report_file_count": len(result_bundle.get("report_files", [])),
        },
        "results": {
            "frequency_rows": len(result_bundle.get("frequency_table", [])),
            "cooccurrence_rows": len(result_bundle.get("cooccurrence_table", [])),
            "focus_term_summary_rows": len(result_bundle.get("focus_term_summary", [])),
            "feature_term_rows": len(result_bundle.get("selected_feature_terms", [])),
            "selected_feature_terms": sum(1 for row in result_bundle.get("selected_feature_terms", []) if row.get("selected")),
            "keyword_rows": len(result_bundle.get("keyword_result", [])),
            "keyword_cluster_rows": len(result_bundle.get("keyword_cluster_result", [])),
            "document_cluster_rows": len(result_bundle.get("clustering_result", [])),
        },
        "progress_events": progress_events[-12:],
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
    }

    summary_path = project_dir / "metadata" / "benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nBenchmark summary saved to: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
