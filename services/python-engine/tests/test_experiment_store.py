from __future__ import annotations

from app.experiment_store import run_experiment_matrix, save_experiment_spec
from app.project_store import create_project


def test_run_experiment_matrix_creates_multiple_runs(isolated_workspace, monkeypatch):
    project_dir, manifest = create_project("experiment matrix", "experiment matrix")
    corpus: list[dict[str, object]] = []
    saved = save_experiment_spec(
        manifest,
        {
            "name": "keyword-method-compare",
            "workflow_id": manifest["active_workflow_id"],
            "variant_matrix": [
                {
                    "label": "baseline",
                    "node_overrides": {
                        "node-keyword-extraction": {
                            "top_k_project": 12
                        }
                    },
                },
                {
                    "label": "high-keywords",
                    "node_overrides": {
                        "node-keyword-extraction": {
                            "top_k_project": 24
                        }
                    },
                },
            ],
        },
    )

    observed_top_k: list[int] = []

    def fake_run(project_dir_arg, manifest_arg, corpus_arg, progress_callback=None):
        workflow = next(
            item
            for item in manifest_arg["workflow_definitions"]
            if item["workflow_id"] == manifest_arg["active_workflow_id"]
        )
        keyword_node = next(
            node
            for node in workflow["nodes"]
            if node["node_id"] == "node-keyword-extraction"
        )
        observed_top_k.append(int(keyword_node["config"]["top_k_project"]))
        run_record = {
            "run_id": f"run-{len(observed_top_k)}",
            "project_id": manifest_arg["id"],
            "workflow_version": workflow["version"],
            "workflow_id": workflow["workflow_id"],
            "workflow_name": workflow["name"],
            "workflow_hash": "workflow-hash",
            "dictionary_version": manifest_arg["dictionary_set"]["version"],
            "started_at": "2026-04-23T00:00:00+08:00",
            "ended_at": "2026-04-23T00:00:01+08:00",
            "status": "completed",
            "warnings": [],
            "errors": [],
            "logs": [],
            "artifacts": [],
            "params_snapshot_path": f"runs/run-{len(observed_top_k)}/params_snapshot.json",
            "processed_document_count": 0,
            "run_scope_summary": "all documents",
            "recipe_id": "standard_analysis",
            "output_bundle_id": "full_report",
            "output_summary": "report bundle",
        }
        manifest_arg.setdefault("run_history", []).append(run_record)
        return manifest_arg, corpus_arg, run_record

    monkeypatch.setattr("app.experiment_store.run_project_workflow", fake_run)

    executed = run_experiment_matrix(project_dir, manifest, corpus, saved["experiment_id"])

    assert observed_top_k == [12, 24]
    assert [run["variant_label"] for run in executed["runs"]] == ["baseline", "high-keywords"]
    assert executed["runs"][1]["variant_index"] == 1
