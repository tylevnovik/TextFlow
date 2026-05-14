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
  raw_hash TEXT,
  row_order INTEGER NOT NULL DEFAULT 0
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

CREATE TABLE IF NOT EXISTS dictionary_sets (
  set_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  bound_to_project INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dictionary_collections (
  kind TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  collection_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dictionary_tables (
  table_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  description TEXT NOT NULL,
  source_url TEXT,
  built_in INTEGER NOT NULL,
  editable INTEGER NOT NULL,
  enabled INTEGER NOT NULL,
  tags_json TEXT NOT NULL,
  table_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_dictionary_tables_kind ON dictionary_tables(kind, table_order);

CREATE TABLE IF NOT EXISTS dictionary_entries (
  entry_pk TEXT PRIMARY KEY,
  table_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  entry_id TEXT,
  source TEXT NOT NULL,
  target_json TEXT NOT NULL,
  tags_json TEXT NOT NULL,
  enabled INTEGER NOT NULL,
  hits INTEGER NOT NULL,
  notes TEXT NOT NULL,
  entry_order INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(table_id) REFERENCES dictionary_tables(table_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dictionary_entries_table ON dictionary_entries(table_id, entry_order);

CREATE TABLE IF NOT EXISTS result_tables (
  result_key TEXT PRIMARY KEY,
  row_count INTEGER NOT NULL,
  preview_json TEXT NOT NULL,
  payload_json_gz BLOB NOT NULL,
  updated_at TEXT NOT NULL
);
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
        _ensure_column(conn, "corpus_documents", "row_order", "INTEGER NOT NULL DEFAULT 0")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_corpus_row_order ON corpus_documents(row_order)")
        _ensure_column(conn, "dictionary_collections", "collection_order", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "dictionary_tables", "table_order", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "dictionary_entries", "entry_order", "INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
            ("schema_version", "2026-05-v1"),
        )
        conn.commit()
    finally:
        conn.close()
    return db


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_definition: str) -> None:
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    existing = {str(row["name"]) for row in cursor.fetchall()}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


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
        seen_doc_ids: set[str] = set()
        for row_order, row in enumerate(rows):
            doc_id = str(row.get("doc_id") or row.get("id") or "")
            original_doc_id = doc_id
            suffix = 1
            while doc_id in seen_doc_ids:
                doc_id = f"{original_doc_id}__lang_{suffix}"
                suffix += 1
            seen_doc_ids.add(doc_id)
            conn.execute(
                """
                INSERT INTO corpus_documents (
                    doc_id, id, source_profile, language, title, raw_text, year,
                    source, author, institution, country_or_region, category_or_tag,
                    keyword_field, extra_metadata_json, status, raw_hash, row_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
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
                    row_order,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def load_corpus_rows(db: ProjectDatabase) -> list[dict[str, Any]]:
    conn = db.connect()
    try:
        cursor = conn.execute("SELECT * FROM corpus_documents ORDER BY row_order, doc_id")
        rows = []
        for row in cursor.fetchall():
            record = dict(row)
            record.pop("row_order", None)
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


def replace_dictionary_set(db: ProjectDatabase, dictionary_set: dict[str, Any]) -> None:
    conn = db.connect()
    try:
        conn.execute("DELETE FROM dictionary_entries")
        conn.execute("DELETE FROM dictionary_tables")
        conn.execute("DELETE FROM dictionary_collections")
        conn.execute("DELETE FROM dictionary_sets")
        conn.execute(
            """
            INSERT INTO dictionary_sets (set_id, name, version, bound_to_project)
            VALUES (?, ?, ?, ?)
            """,
            (
                str(dictionary_set.get("id") or "dict-default"),
                str(dictionary_set.get("name") or "默认词表集"),
                str(dictionary_set.get("version") or "2.0.0"),
                1 if bool(dictionary_set.get("bound_to_project", True)) else 0,
            ),
        )
        collections = dictionary_set.get("collections") if isinstance(dictionary_set.get("collections"), dict) else {}
        for collection_order, (kind, collection) in enumerate(collections.items()):
            if not isinstance(collection, dict):
                continue
            kind = str(kind)
            conn.execute(
                """
                INSERT INTO dictionary_collections (kind, name, description, collection_order)
                VALUES (?, ?, ?, ?)
                """,
                (
                    kind,
                    str(collection.get("name") or kind),
                    str(collection.get("description") or ""),
                    collection_order,
                ),
            )
            tables = collection.get("tables") if isinstance(collection.get("tables"), list) else []
            for table_order, table in enumerate(tables):
                if not isinstance(table, dict):
                    continue
                table_id = str(table.get("id") or f"{kind}-table-{table_order}")
                conn.execute(
                    """
                    INSERT INTO dictionary_tables (
                        table_id, kind, name, version, description, source_url,
                        built_in, editable, enabled, tags_json, table_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        table_id,
                        kind,
                        str(table.get("name") or table_id),
                        str(table.get("version") or "2.0.0"),
                        str(table.get("description") or ""),
                        str(table.get("source_url")) if table.get("source_url") else None,
                        1 if bool(table.get("built_in", False)) else 0,
                        1 if bool(table.get("editable", not bool(table.get("built_in", False)))) else 0,
                        1 if bool(table.get("enabled", True)) else 0,
                        json.dumps(_json_ready(table.get("tags") or []), ensure_ascii=False, separators=(",", ":")),
                        table_order,
                    ),
                )
                entries = table.get("entries") if isinstance(table.get("entries"), list) else []
                for entry_order, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        continue
                    source = str(entry.get("source") or "")
                    target = entry.get("target")
                    entry_pk = f"{table_id}::{entry_order}"
                    conn.execute(
                        """
                        INSERT INTO dictionary_entries (
                            entry_pk, table_id, kind, entry_id, source, target_json,
                            tags_json, enabled, hits, notes, entry_order
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entry_pk,
                            table_id,
                            kind,
                            str(entry.get("id")) if entry.get("id") else None,
                            source,
                            json.dumps(_json_ready(target), ensure_ascii=False, separators=(",", ":")),
                            json.dumps(_json_ready(entry.get("tags") or []), ensure_ascii=False, separators=(",", ":")),
                            1 if bool(entry.get("enabled", True)) else 0,
                            int(entry.get("hits", 0) or 0),
                            str(entry.get("notes") or ""),
                            entry_order,
                        ),
                    )
        conn.commit()
    finally:
        conn.close()


def load_dictionary_set(db: ProjectDatabase) -> dict[str, Any] | None:
    conn = db.connect()
    try:
        set_row = conn.execute("SELECT * FROM dictionary_sets LIMIT 1").fetchone()
        if set_row is None:
            return None
        table_rows = conn.execute("SELECT * FROM dictionary_tables ORDER BY kind, table_order, table_id").fetchall()
        if not table_rows:
            return None

        dictionary_set: dict[str, Any] = {
            "id": set_row["set_id"],
            "name": set_row["name"],
            "version": set_row["version"],
            "bound_to_project": bool(set_row["bound_to_project"]),
            "collections": {},
        }
        collection_rows = conn.execute(
            "SELECT * FROM dictionary_collections ORDER BY collection_order, kind"
        ).fetchall()
        for row in collection_rows:
            dictionary_set["collections"][row["kind"]] = {
                "kind": row["kind"],
                "name": row["name"],
                "description": row["description"],
                "tables": [],
            }

        table_lookup: dict[str, dict[str, Any]] = {}
        for row in table_rows:
            kind = row["kind"]
            collection = dictionary_set["collections"].setdefault(
                kind,
                {"kind": kind, "name": kind, "description": "", "tables": []},
            )
            try:
                tags = json.loads(row["tags_json"]) if row["tags_json"] else []
            except Exception:
                tags = []
            table = {
                "id": row["table_id"],
                "kind": kind,
                "name": row["name"],
                "version": row["version"],
                "description": row["description"],
                "source_url": row["source_url"],
                "built_in": bool(row["built_in"]),
                "editable": bool(row["editable"]),
                "enabled": bool(row["enabled"]),
                "tags": tags if isinstance(tags, list) else [],
                "entries": [],
            }
            collection["tables"].append(table)
            table_lookup[row["table_id"]] = table

        entry_rows = conn.execute(
            "SELECT * FROM dictionary_entries ORDER BY table_id, entry_order, entry_pk"
        ).fetchall()
        for row in entry_rows:
            table = table_lookup.get(row["table_id"])
            if table is None:
                continue
            try:
                target = json.loads(row["target_json"]) if row["target_json"] else None
            except Exception:
                target = None
            try:
                tags = json.loads(row["tags_json"]) if row["tags_json"] else []
            except Exception:
                tags = []
            table["entries"].append(
                {
                    "id": row["entry_id"],
                    "source": row["source"],
                    "target": target,
                    "tags": tags if isinstance(tags, list) else [],
                    "enabled": bool(row["enabled"]),
                    "hits": int(row["hits"] or 0),
                    "notes": row["notes"],
                }
            )
        return dictionary_set
    finally:
        conn.close()


def dictionary_table_count(db: ProjectDatabase) -> int:
    conn = db.connect()
    try:
        row = conn.execute("SELECT COUNT(*) FROM dictionary_tables").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def replace_result_bundle(db: ProjectDatabase, results: dict[str, Any]) -> None:
    conn = db.connect()
    try:
        conn.execute("DELETE FROM result_tables")
        for result_key, value in results.items():
            normalized_payload = _json_ready(value)
            row_count = len(normalized_payload) if isinstance(normalized_payload, list) else (1 if normalized_payload not in (None, "") else 0)
            preview_rows = normalized_payload[:50] if isinstance(normalized_payload, list) else ([normalized_payload] if normalized_payload is not None else [])
            preview_json = json.dumps(preview_rows, ensure_ascii=False, separators=(",", ":"))
            payload_bytes = json.dumps(normalized_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            conn.execute(
                """
                INSERT INTO result_tables (result_key, row_count, preview_json, payload_json_gz, updated_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                (str(result_key), row_count, preview_json, gzip.compress(payload_bytes, compresslevel=6)),
            )
        conn.commit()
    finally:
        conn.close()


def load_result_bundle(db: ProjectDatabase) -> dict[str, Any] | None:
    conn = db.connect()
    try:
        rows = conn.execute("SELECT result_key, payload_json_gz FROM result_tables ORDER BY result_key").fetchall()
        if not rows:
            return None
        results: dict[str, Any] = {}
        for row in rows:
            try:
                payload_bytes = gzip.decompress(row["payload_json_gz"])
                results[row["result_key"]] = json.loads(payload_bytes.decode("utf-8"))
            except Exception:
                results[row["result_key"]] = []
        return results
    finally:
        conn.close()


def result_bundle_summary(db: ProjectDatabase) -> dict[str, Any]:
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT result_key, row_count, preview_json, updated_at FROM result_tables ORDER BY result_key"
        ).fetchall()
        keys: dict[str, Any] = {}
        for row in rows:
            try:
                preview_count = len(json.loads(row["preview_json"]) or [])
            except Exception:
                preview_count = 0
            keys[row["result_key"]] = {
                "row_count": int(row["row_count"] or 0),
                "preview_rows": preview_count,
                "updated_at": row["updated_at"],
            }
        return {"storage": "project.db", "table": "result_tables", "keys": keys}
    finally:
        conn.close()


def list_artifact_records(db: ProjectDatabase, run_id: str | None = None) -> list[dict[str, Any]]:
    conn = db.connect()
    try:
        if run_id:
            rows = conn.execute(
                """
                SELECT artifact_id, run_id, node_id, kind, row_count, preview_json
                FROM artifacts WHERE run_id = ? ORDER BY created_at, artifact_id
                """,
                (run_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT artifact_id, run_id, node_id, kind, row_count, preview_json
                FROM artifacts ORDER BY created_at, artifact_id
                """
            ).fetchall()
        records = []
        for row in rows:
            try:
                preview_rows = len(json.loads(row["preview_json"]) or [])
            except Exception:
                preview_rows = 0
            records.append(
                {
                    "artifact_id": row["artifact_id"],
                    "run_id": row["run_id"],
                    "node_id": row["node_id"],
                    "kind": row["kind"],
                    "path": f"project.db:artifacts/{row['artifact_id']}/payload",
                    "preview_path": f"project.db:artifacts/{row['artifact_id']}/preview",
                    "row_count": int(row["row_count"] or 0),
                    "preview_rows": preview_rows,
                }
            )
        return records
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
        "path": f"project.db:artifacts/{artifact_id}/payload",
        "preview_path": f"project.db:artifacts/{artifact_id}/preview",
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


def clear_artifacts_except_run(db: ProjectDatabase, keep_run_id: str) -> int:
    conn = db.connect()
    try:
        cursor = conn.execute("DELETE FROM artifacts WHERE run_id != ?", (keep_run_id,))
        conn.commit()
        return cursor.rowcount
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
