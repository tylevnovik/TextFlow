import json
from pathlib import Path

from app.project_database import (
    initialize_project_database,
    load_corpus_rows,
    replace_corpus_rows,
    write_artifact_payload,
    load_artifact_payload,
    project_database_integrity_check,
)


def test_project_database_round_trips_corpus_rows(tmp_path):
    db = initialize_project_database(tmp_path / "project.db")
    rows = [
        {
            "id": "DOC-1",
            "doc_id": "DOC-1",
            "source_profile": "wos",
            "language": None,
            "title": "Rare earth recovery",
            "raw_text": "Rare earth recovery text",
            "year": 2024,
            "source": None,
            "author": None,
            "institution": "Example University",
            "country_or_region": None,
            "category_or_tag": None,
            "keyword_field": None,
            "extra_metadata": {"UT": "WOS:1"},
            "status": "ready",
            "raw_hash": "hash-1",
            "clean_text": "",
            "normalized_text": "",
            "tokens": [],
            "phrase_hits": [],
            "filtered_tokens": [],
        }
    ]

    replace_corpus_rows(db, rows)

    assert load_corpus_rows(db) == rows
    assert project_database_integrity_check(db) == "ok"


def test_project_database_round_trips_compressed_artifacts(tmp_path):
    db = initialize_project_database(tmp_path / "project.db")
    artifact = write_artifact_payload(
        db,
        run_id="run-1",
        node_id="node-frequency",
        kind="table",
        payload=[{"term": "dysprosium", "tf": 3}],
    )

    assert artifact["row_count"] == 1
    assert load_artifact_payload(db, artifact["artifact_id"]) == [{"term": "dysprosium", "tf": 3}]
