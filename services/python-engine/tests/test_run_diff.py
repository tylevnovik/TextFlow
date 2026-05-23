from __future__ import annotations

from app.storage.run_diff import compare_runs


def test_run_diff_compares_artifact_summaries_and_metrics():
    manifest = {
        "run_history": [
            {
                "run_id": "run-baseline",
                "processed_document_count": 3,
                "warnings": [],
                "errors": [],
                "artifacts": [
                    {
                        "step": "analysis",
                        "output_files": ["outputs/frequency_table.csv"],
                        "record_count": 9,
                        "cache_hit": False,
                    }
                ],
                "output_summary": "baseline summary",
            },
            {
                "run_id": "run-high-keywords",
                "processed_document_count": 5,
                "warnings": ["variant widened"],
                "errors": [],
                "artifacts": [
                    {
                        "step": "analysis",
                        "output_files": ["outputs/frequency_table.csv", "outputs/keyness.csv"],
                        "record_count": 14,
                        "cache_hit": False,
                    }
                ],
                "output_summary": "high keyword summary",
            },
        ]
    }

    diff = compare_runs(manifest, "run-baseline", "run-high-keywords")

    assert diff["metrics"]["processed_document_count"]["delta"] == 2
    analysis_diff = next(item for item in diff["artifact_diffs"] if item["step"] == "analysis")
    assert analysis_diff["record_count_delta"] == 5
    assert diff["summary"].startswith("Compared run-baseline vs run-high-keywords")
