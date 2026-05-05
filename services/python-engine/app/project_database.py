from __future__ import annotations

import gzip
import json
import platform
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS corpus_documents (
  doc_id TEXT PRIMARY KEY,
  id TEXT NOT NULL,
  source_profile TEXT NOT NULL,
  language TEXT,
  title TEXT NOT NULL,
  raw_text TEXT NOT NULL,
  year INTEGER,
  source TEXT,
  author TEXT,
  institution TEXT,
  country_or_region TEXT,
  category_or_tag TEXT,
  keyword_field TEXT,
  extra_metadata_json TEXT NOT NULL,
  status TEXT NOT NULL,
  raw_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_corpus_year ON corpus_documents(year);
CREATE INDEX IF NOT EXISTS idx_corpus_source_profile ON corpus_documents(source_profile);
CREATE INDEX IF NOT EXISTS idx_corpus_institution ON corpus_documents(institution);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  row_count INTEGER NOT NULL,
  preview_json TEXT NOT NULL,
  payload_json_gz BLOB NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_run ON artifacts(run_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_node ON artifacts(node_id);
"""

_JOURNAL_MODE = "DELETE" if platform.system().lower() == "windows" else "WAL"
PRAGMAS = [
    f"PRAGMA journal_mode={_JOURNAL_MODE}",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
]


class ProjectDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn


def initialize_project_database(db_path: Path) -> ProjectDatabase:
    db = ProjectDatabase(db_path)
    conn = db.connect()
    try:
        for pragma in PRAGMAS:
            conn.execute(pragma)
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("schema_version", "2026-05-v1"),
        )
        conn.commit()
    finally:
        conn.close()
    return db


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return str(value)


def replace_corpus_rows(db: ProjectDatabase, rows: list[dict[str, Any]]) -> None:
    conn = db.connect()
    try:
        conn.execute("DELETE FROM corpus_documents")
        for row in rows:
            conn.execute(
                """
                INSERT OR REPLACE INTO corpus_documents (
                    doc_id, id, source_profile, language, title, raw_text, year,
                    source, author, institution, country_or_region, category_or_tag,
                    keyword_field, extra_metadata_json, status, raw_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row.get("doc_id") or row.get("id") or ""),
                    str(row.get("id") or row.get("doc_id") or ""),
                    str(row.get("source_profile") or "generic"),
                    str(row.get("language") or "") or None,
                    str(row.get("title") or ""),
                    str(row.get("raw_text") or ""),
                    int(row["year"]) if row.get("year") is not None else None,
                    str(row.get("source") or "") or None,
                    str(row.get("author") or "") or None,
                    str(row.get("institution") or "") or None,
                    str(row.get("country_or_region") or "") or None,
                    str(row.get("category_or_tag") or "") or None,
                    str(row.get("keyword_field") or "") or None,
                    json.dumps(_json_ready(row.get("extra_metadata") or {}), ensure_ascii=False, separators=(",", ":")),
                    str(row.get("status") or "ready"),
                    str(row.get("raw_hash") or "") or None,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def load_corpus_rows(db: ProjectDatabase) -> list[dict[str, Any]]:
    conn = db.connect()
    try:
        cursor = conn.execute("SELECT * FROM corpus_documents ORDER BY doc_id")
        rows = []
        for row in cursor.fetchall():
            record = dict(row)
            extra = record.pop("extra_metadata_json", "{}")
            try:
                record["extra_metadata"] = json.loads(extra) if extra else {}
            except Exception:
                record["extra_metadata"] = {}
            for key in ["clean_text", "normalized_text", "tokens", "phrase_hits", "filtered_tokens"]:
                record.setdefault(key, [] if key in ("tokens", "phrase_hits", "filtered_tokens") else "")
            rows.append(record)
        return rows
    finally:
        conn.close()


def write_artifact_payload(
    db: ProjectDatabase,
    run_id: str,
    node_id: str,
    kind: str,
    payload: Any,
) -> dict[str, Any]:
    artifact_id = f"artifact-{uuid4().hex[:12]}"
    normalized_payload = _json_ready(payload)
    row_count = len(normalized_payload) if isinstance(normalized_payload, list) else (1 if normalized_payload not in (None, "") else 0)
    preview_rows = normalized_payload[:50] if isinstance(normalized_payload, list) else ([normalized_payload] if normalized_payload is not None else [])
    preview_json = json.dumps(preview_rows, ensure_ascii=False, separators=(",", ":"))
    payload_bytes = json.dumps(normalized_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload_gz = gzip.compress(payload_bytes, compresslevel=6)

    conn = db.connect()
    try:
        conn.execute(
            """
            INSERT INTO artifacts (artifact_id, run_id, node_id, kind, row_count, preview_json, payload_json_gz, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (artifact_id, run_id, node_id, kind, row_count, preview_json, payload_gz),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "artifact_id": artifact_id,
        "run_id": run_id,
        "node_id": node_id,
        "kind": kind,
        "row_count": row_count,
        "preview_rows": len(preview_rows),
    }


def load_artifact_payload(db: ProjectDatabase, artifact_id: str) -> Any:
    conn = db.connect()
    try:
        cursor = conn.execute(
            "SELECT payload_json_gz FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Artifact {artifact_id} not found")
        payload_bytes = gzip.decompress(row["payload_json_gz"])
        return json.loads(payload_bytes.decode("utf-8"))
    finally:
        conn.close()


def load_artifact_preview(db: ProjectDatabase, artifact_id: str, limit: int = 50) -> dict[str, Any]:
    conn = db.connect()
    try:
        cursor = conn.execute(
            "SELECT artifact_id, run_id, node_id, kind, row_count, preview_json FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Artifact {artifact_id} not found")
        preview = json.loads(row["preview_json"])
        if isinstance(preview, list) and limit >= 0:
            preview = preview[:limit]
        return {
            "artifact_id": row["artifact_id"],
            "run_id": row["run_id"],
            "node_id": row["node_id"],
            "kind": row["kind"],
            "row_count": row["row_count"],
            "preview_rows": len(preview),
            "rows": preview,
        }
    finally:
        conn.close()


def project_database_integrity_check(db: ProjectDatabase) -> str:
    conn = db.connect()
    try:
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        return str(result[0]) if result else "unknown"
    finally:
        conn.close()


def migrate_corpus_from_json(db: ProjectDatabase, corpus: list[dict[str, Any]]) -> None:
    replace_corpus_rows(db, corpus)
