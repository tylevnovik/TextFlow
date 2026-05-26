# New Flow Samples, Kernel Nodes, and SQLite Store Implementation Plan

> **For Opencode:** Start in `/agents` -> `Plan`, review this plan against the current repository, ask only blocking questions, then switch to `/agents` -> `Build` and implement task-by-task. Do not skip tests between tasks.

**Goal:** Replace the old built-in sample set with multiple new-flow sample projects, make the missing flow nodes executable in the Python engine, and move large corpus/artifact storage into a project-local SQLite database.

**Architecture:** Keep Tauri + React + TypeScript as the UI shell and Python as the analysis engine. Keep `.tfproj/project.json` as the human-readable project manifest for project metadata, dictionaries, workflow definitions, settings, and run history; introduce `.tfproj/project.db` as the authoritative store for imported corpus rows and large run artifacts. Built-in sample projects must be prebuilt from seed data at packaging time and copied on first launch as already-imported projects, with no raw import source files retained inside the shipped `.tfproj`.

**Tech Stack:** Tauri, React, TypeScript, Python 3.11, pandas, scikit-learn, matplotlib, stdlib `sqlite3`, `networkx` for graph algorithms, `xlrd` for legacy WoS `.xls` seed/import support, pytest, Vitest.

---

## Confirmed Product Decisions

- Replace the previous nine public-data examples with multiple examples built around the revised flow.
- Remove the old nine-scenario sample system and its test/build harness from active code paths. Do not leave old sample bootstrap, public sample cache fetch scripts, or nine-sample assertions as dead-but-runnable maintenance burden.
- Use WoS and IncoPat as the real source-profile targets for bundled examples.
- Current local seed candidates are `C:\Users\blmpt\Downloads\TextFlow\稀土wos.xls` and `C:\Users\blmpt\Downloads\TextFlow\稀缺稀土元素.xlsx`.
- Do not include Scopus as a bundled example yet because a Scopus export is not available. Still add a Scopus import profile and unit fixture so the source profile is ready.
- Missing nodes are not placeholders. Implement runnable kernel nodes for metadata normalization, graph analysis, and technology identification.
- Bundled sample projects must be in an already-imported state. Do not ship `corpus/imported/*.csv`, `*.xlsx`, `*.json`, or `*.txt` inside sample `.tfproj` directories.
- Introduce SQLite now. This is worth doing because current project storage reads/writes large JSON files and compressed artifact files repeatedly, which hurts speed, package size, and crash reliability.

## Licensing Gate

Do not silently redistribute subscription exports. Treat user-supplied WoS, Scopus, and IncoPat exports as local development seed data unless redistribution rights are explicitly confirmed.

References checked on 2026-05-05:

- Clarivate says Web of Science data usage is governed by the customer contractual agreement: https://developer.clarivate.com/apis/woslite
- Clarivate terms reserve rights in products, databases, and data sets: https://clarivate.com/legal-center/terms-of-business/
- Elsevier says Scopus-derived data is subject to the Scopus subscription agreement: https://www.elsevier.com/en-in/legal/elsevier-product-specific-terms-and-conditions
- WIPO IP data terms include redistribution paths for data products under stated conditions, making WIPO/PATENTSCOPE a better candidate for distributable patent sample seeds if IncoPat redistribution is not cleared: https://www.wipo.int/export/sites/www/patentscope/en/data/pdf/terms_and_conditions_jan2016.pdf

Implementation rule:

- Add a build-time `TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA=1` override only for local/private builds.
- Public/release packaging must fail if sample seed metadata says the source is restricted and no approved redistribution note is present.
- If WoS or IncoPat redistribution is not cleared, create distributable examples from open metadata/patent sources while preserving WoS/IncoPat-shaped import templates for local validation.

## Target Built-In Sample Projects

Ship three sample projects by default:

| Order | Project | Source Profile | Purpose |
| --- | --- | --- | --- |
| 01 | `示例 01 - WoS论文关键词与主题流程` | `wos` | Field mapping, main-text construction from title/abstract/keywords, cleaning, tokenization, dictionary handling, feature terms, keywords, topics, term-year, co-occurrence, exports. |
| 02 | `示例 02 - IncoPat专利技术识别与图分析` | `incopat` | Patent metadata mapping, applicant/inventor/country/year/category normalization, claims-aware text construction, graph construction, graph metrics, community detection, main path, link prediction, technology indicators, technology classification. |
| 03 | `示例 03 - 论文专利融合分析流程` | `wos` + `incopat` | Multi-source corpus merge, source-profile preservation, metadata normalization, dedupe, institution-keyword/topic analysis, cross statistics, graph and technology outputs, audit report. |

Scopus:

- Add `scopus` source profile support and tests.
- Do not include a Scopus bundled sample until real redistributable seed data exists.
- If the user later supplies a redistributable Scopus export, add `示例 04 - Scopus论文主题与机构流程`.

## Revised Flow Coverage

The new default/sample workflow must represent this flow:

1. Corpus import from source profiles: WoS, Scopus, IncoPat, generic.
2. Source-profile metadata mapping.
3. Main-text construction from one or more fields.
4. Corpus-level cleaning: record dedupe and text cleaning.
5. Metadata normalization: author, institution, country/region, time, category.
6. Tokenization: dictionary, custom phrase preservation, configurable n-gram.
7. Term-level cleaning: lemmatization where available, standard stopwords, synonym merge, custom stopwords, exclusions, standard terms.
8. Feature-term selection: frequency, TF-IDF weighting, keyword extraction.
9. Analysis and visualization: frequency, term-document, term-year, co-occurrence, clustering, keyword clustering, institution-keyword, institution-topic.
10. Graph analysis: network build, main path, community detection, link prediction, graph metrics.
11. Technology identification: novelty/disruption indicators and classification.
12. Export: CSV, XLSX, PNG, HTML, with run logs and rule audit trails.

---

## Task 1: Add Source Seed Contract and Redistribution Gate

**Files:**

- Create: `services/python-engine/app/sample_seed_sources.py`
- Create: `services/python-engine/tests/test_sample_seed_sources.py`
- Modify: `scripts/build-bundled-sample-workspace.ps1`
- Modify: `services/python-engine/app/bundled_sample_workspace.py`
- Modify: `.gitignore`
- Create: `sample_seed_sources/README.md`

**Step 1: Write failing tests**

Add tests that prove seed metadata is explicit:

```python
from pathlib import Path

import pytest

from app.sample_seed_sources import (
    SampleSeedSource,
    validate_sample_seed_source,
    assert_sample_seed_can_ship,
)


def test_seed_source_requires_profile_and_license_note(tmp_path):
    seed = SampleSeedSource(
        seed_id="wos-rare-earth",
        source_profile="wos",
        path=tmp_path / "wos.xlsx",
        redistribution="restricted",
        redistribution_note="",
    )

    with pytest.raises(ValueError, match="redistribution_note"):
        validate_sample_seed_source(seed)


def test_restricted_seed_cannot_ship_without_override(tmp_path, monkeypatch):
    seed = SampleSeedSource(
        seed_id="wos-rare-earth",
        source_profile="wos",
        path=tmp_path / "wos.xlsx",
        redistribution="restricted",
        redistribution_note="Local development export only.",
    )

    with pytest.raises(ValueError, match="not approved for release packaging"):
        assert_sample_seed_can_ship(seed)

    monkeypatch.setenv("TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA", "1")
    assert_sample_seed_can_ship(seed)
```

Run:

```powershell
.\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_seed_sources.py -q
```

Expected: fail because the module does not exist.

**Step 2: Implement seed metadata types**

Implement a small dataclass:

```python
@dataclass(frozen=True)
class SampleSeedSource:
    seed_id: str
    source_profile: str
    path: Path
    redistribution: Literal["approved", "restricted", "unknown"]
    redistribution_note: str
```

Add helpers:

- `validate_sample_seed_source(seed)`
- `assert_sample_seed_can_ship(seed)`
- `sample_seed_root()`
- `default_sample_seed_sources()`

Use env vars:

- `TEXTFLOW_SAMPLE_WOS_SOURCE`
- `TEXTFLOW_SAMPLE_INCOPAT_SOURCE`
- `TEXTFLOW_SAMPLE_SCOPUS_SOURCE`
- `TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA`

Default seed paths should be under `sample_seed_sources/private/`, which must be ignored by git.

**Step 3: Update build script contract**

Change `scripts/build-bundled-sample-workspace.ps1` to accept optional paths:

```powershell
param(
  [Nullable[int]]$RowLimit = $null,
  [string]$WosSeed = "",
  [string]$IncopatSeed = "",
  [string]$ScopusSeed = "",
  [switch]$AllowRestrictedSampleData
)
```

Set the matching env vars before invoking Python.

**Step 4: Pass tests**

Run:

```powershell
npm run test:engine:fast
```

Expected: pass.

**Step 5: Commit**

```powershell
git add services/python-engine/app/sample_seed_sources.py services/python-engine/tests/test_sample_seed_sources.py scripts/build-bundled-sample-workspace.ps1 .gitignore sample_seed_sources/README.md
git commit -m "chore: add sample seed source gate"
```

---

## Task 2: Introduce Project-Local SQLite Storage

**Files:**

- Create: `services/python-engine/app/project_database.py`
- Create: `services/python-engine/tests/test_project_database.py`
- Modify: `services/python-engine/app/project_store.py`
- Modify: `services/python-engine/app/artifact_store.py`
- Modify: `services/python-engine/tests/test_project_resources.py`
- Modify: `services/python-engine/tests/test_artifact_store.py`
- Modify: `packages/shared-types/src/index.ts`
- Modify: `docs/architecture.md`
- Modify: `docs/workflow-runtime.md`

**Step 1: Write failing database tests**

Cover corpus round-trip, artifact round-trip, migration from legacy JSON, and integrity check:

```python
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
            "title": "Rare earth recovery",
            "raw_text": "Rare earth recovery text",
            "year": 2024,
            "institution": "Example University",
            "extra_metadata": {"UT": "WOS:1"},
            "status": "ready",
            "raw_hash": "hash-1",
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
```

Run:

```powershell
.\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_project_database.py -q
```

Expected: fail because `project_database.py` does not exist.

**Step 2: Implement SQLite schema**

Use stdlib `sqlite3`; no server dependency.

Required tables:

```sql
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
```

Set:

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA synchronous=NORMAL;
```

**Step 3: Integrate with project store**

Modify `project_store.py`:

- Add `PROJECT_DATABASE_FILENAME = "project.db"`.
- `ensure_project_layout()` must not require raw source files for samples.
- `save_project(project_dir, manifest, corpus)` writes corpus rows to SQLite.
- `load_project(project_dir)` reads from SQLite if `project.db` exists.
- If `metadata/corpus.json` exists but `project.db` does not, migrate rows into SQLite on first save/load.
- Keep `project.json` readable and compact.

Do not write giant corpus arrays back to `project.json`.

**Step 4: Integrate artifact store**

Modify `artifact_store.py`:

- Write artifact payloads into SQLite `artifacts`.
- Continue returning an `ArtifactRecord` shape with `artifact_id`, `run_id`, `node_id`, `kind`, `row_count`, `preview_rows`.
- For compatibility, allow `load_artifact_payload` to read old `runs/*/artifacts/*.json.gz` if a DB artifact is missing.
- New sample projects should not create JSON artifact payload files unless export nodes explicitly write external files.

**Step 5: Add package/export handling**

Modify project package export/import in `project_store.py`:

- Include `project.db` in `.tfproj` packages.
- On import, run `PRAGMA integrity_check`.
- If integrity check fails, reject the import with a clear error.

**Step 6: Pass storage tests**

Run:

```powershell
.\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_project_database.py services\python-engine\tests\test_artifact_store.py services\python-engine\tests\test_project_resources.py -q
```

Expected: pass.

**Step 7: Commit**

```powershell
git add services/python-engine/app/project_database.py services/python-engine/app/project_store.py services/python-engine/app/artifact_store.py services/python-engine/tests/test_project_database.py services/python-engine/tests/test_artifact_store.py services/python-engine/tests/test_project_resources.py packages/shared-types/src/index.ts docs/architecture.md docs/workflow-runtime.md
git commit -m "feat: store corpus and artifacts in project sqlite database"
```

---

## Task 3: Add WoS, Scopus, Legacy XLS, and Stronger IncoPat Import Profiles

**Files:**

- Modify: `services/python-engine/pyproject.toml`
- Modify: `services/python-engine/app/defaults.py`
- Modify: `services/python-engine/app/ingestion.py`
- Modify: `services/python-engine/tests/test_ingestion.py`
- Modify: `packages/shared-types/src/index.ts`
- Modify: `apps/desktop/src/screens.tsx`
- Modify: `docs/development.md`

**Step 1: Write failing import tests**

Add tests for WoS, Scopus, legacy `.xls` routing, and improved IncoPat text construction:

```python
def test_wos_import_template_maps_title_abstract_keywords_and_metadata(scratch_dir):
    path = scratch_dir / "wos.csv"
    path.write_text(
        "UT,TI,AB,DE,ID,AU,C1,PY,SO,WC,DT,DOI\n"
        "WOS:1,Rare earth recycling,Recovery of dysprosium.,rare earth; recycling,critical materials,Li; Wang,University A,2024,Journal A,Materials Science,Article,10.1/demo\n",
        encoding="utf-8-sig",
    )

    corpus, _sources, issues = import_files([path], default_import_template("wos"))

    assert issues == []
    assert corpus[0]["doc_id"] == "WOS:1"
    assert corpus[0]["raw_text"] == "Rare earth recycling\n\nRecovery of dysprosium.\n\nrare earth; recycling\n\ncritical materials"
    assert corpus[0]["author"] == "Li; Wang"
    assert corpus[0]["institution"] == "University A"
    assert corpus[0]["year"] == 2024
    assert corpus[0]["category_or_tag"] == "Materials Science"
    assert corpus[0]["extra_metadata"]["DOI"] == "10.1/demo"


def test_scopus_import_template_maps_common_export_headers(scratch_dir):
    path = scratch_dir / "scopus.csv"
    path.write_text(
        "EID,Title,Abstract,Author Keywords,Index Keywords,Authors,Affiliations,Year,Source title,DOI,Subject area,Document Type\n"
        "2-s2.0-1,Rare earth separation,Separation process text.,rare earth; separation,critical material,Smith J,Institute B,2023,Source B,10.2/demo,Chemistry,Article\n",
        encoding="utf-8-sig",
    )

    corpus, _sources, issues = import_files([path], default_import_template("scopus"))

    assert issues == []
    assert corpus[0]["doc_id"] == "2-s2.0-1"
    assert "rare earth; separation" in corpus[0]["raw_text"]
    assert corpus[0]["source_profile"] == "scopus"


def test_dataframe_from_source_routes_legacy_xls_to_read_excel(monkeypatch, scratch_dir):
    xls_path = scratch_dir / "legacy-wos.xls"
    xls_path.write_bytes(b"placeholder")
    calls = []

    def fake_read_excel(path, *args, **kwargs):
        calls.append(path)
        return pd.DataFrame([{"UT": "WOS:1", "TI": "Title", "AB": "Abstract"}])

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)

    frame = dataframe_from_source(xls_path)

    assert calls == [xls_path]
    assert frame.loc[0, "UT"] == "WOS:1"
```

Run:

```powershell
.\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_ingestion.py -q
```

Expected: fail until `scopus`, `.xls` routing, and stronger WoS/IncoPat templates exist.

**Step 2: Add legacy `.xls` support**

Add `xlrd>=2.0.1` to `services/python-engine/pyproject.toml`.

Update:

- `dataframe_from_source()` to accept `.xls` as Excel input.
- `SourceFileRecord.source_type` in shared types to include `"xls"`.
- Any source-file display code that assumes only `txt/csv/xlsx/json`.

The product target remains `txt/csv/xlsx/json`; this support exists because WoS still commonly exports legacy `.xls`.

**Step 3: Implement import templates**

Update `profile_import_template()`:

- `wos.text_build.fields`: `["TI", "AB", "DE", "ID"]`
- `scopus.text_build.fields`: `["Title", "Abstract", "Author Keywords", "Index Keywords"]`
- `incopat.text_build.fields`: `["标题 (中文)", "标题 (英文)", "摘要 (中文)", "摘要 (英文)", "首权翻译", "首项权利要求", "独立权利要求", "技术功效句", "技术功效短语", "用途"]`

Add Scopus aliases to `SOURCE_PROFILE_VALUES` and `SourceProfile` in shared types.

**Step 4: Preserve source-profile-specific metadata**

Ensure all unmapped source fields remain under `extra_metadata`.

For IncoPat, important metadata must be easy to use later:

- `公开（公告）号`
- `申请号`
- `公开国别`
- `IPC`
- `CPC`
- `申请人`
- `标准化申请人`
- `发明人`
- `引证专利`
- `被引证专利`
- `被引证次数`
- `引证次数`
- `技术功效1级`
- `技术功效2级`
- `技术功效3级`

**Step 5: Pass tests**

Run:

```powershell
npm run test:engine:fast
```

Expected: pass.

**Step 6: Commit**

```powershell
git add services/python-engine/pyproject.toml services/python-engine/app/defaults.py services/python-engine/app/ingestion.py services/python-engine/tests/test_ingestion.py packages/shared-types/src/index.ts apps/desktop/src/screens.tsx docs/development.md
git commit -m "feat: add source profiles for wos scopus and incopat flows"
```

---

## Task 4: Add Metadata Normalization Node

**Files:**

- Modify: `services/python-engine/app/analysis_ops.py`
- Modify: `services/python-engine/app/node_definitions.py`
- Modify: `services/python-engine/app/node_executors.py`
- Modify: `services/python-engine/tests/test_workflow_runner.py`
- Modify: `services/python-engine/tests/test_node_catalog_parity.py`
- Modify: `packages/shared-types/src/index.ts`
- Modify: `apps/desktop/src/<legacy-generated-node-schema>.ts`
- Modify: `apps/desktop/src/workflowNodeCatalog.ts`
- Modify: `apps/desktop/src/workflowNodeRegistry.tsx`

**Step 1: Write failing executor test**

Add:

```python
def test_normalize_metadata_node_standardizes_institution_country_year_and_category(isolated_workspace):
    project_dir, manifest, corpus = _create_test_project(
        "metadata normalization",
        "metadata normalization node",
        corpus=[
            {
                "doc_id": "DOC-1",
                "title": "A",
                "raw_text": "rare earth text",
                "year": "2024-05-01",
                "institution": "Univ. A; University A",
                "country_or_region": "CN",
                "category_or_tag": "C22B59/00",
                "extra_metadata": {},
            }
        ],
    )
    # Build minimal workflow corpus_input -> normalize_metadata -> save_html_report.
```

Expected output:

- `institution == "University A"`
- `country_or_region == "China"`
- `year == 2024`
- `extra_metadata["metadata_normalization_audit"]` contains applied rule records.

**Step 2: Implement node definition**

Node:

- Type: `normalize_metadata`
- Title: `元数据标准化`
- Category: `process`
- Input: `corpus_in: CorpusTable`
- Outputs:
  - `normalized_corpus: CorpusTable`
  - `metadata_audit_table: AnyTable`, result bundle key `metadata_audit_table`
- Params:
  - `institution_aliases_text`
  - `country_aliases_text`
  - `category_aliases_text`
  - `split_delimiters`
  - `keep_first_institution`
  - `year_source_field`

**Step 3: Implement executor**

Rules:

- Parse `alias|canonical` rows.
- Split multi-value institution/author fields on `;`, `；`, `|`.
- Use first institution by default, preserving all values in `extra_metadata["institution_values"]`.
- Normalize common countries: `CN`, `中国`, `China` -> `China`; `US`, `USA`, `United States`, `美国` -> `United States`.
- Normalize `year` through existing `parse_optional_year`.
- Return an audit row per changed field.

**Step 4: Update result bundle and UI schema**

Add `metadata_audit_table` to:

- `empty_result_bundle()`
- shared TypeScript result unions if needed
- generated schema
- workflow node catalog positions
- node registry editor controls

**Step 5: Pass tests**

Run:

```powershell
.\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_workflow_runner.py services\python-engine\tests\test_node_catalog_parity.py -q
npm run test --workspace apps/desktop
```

Expected: pass.

**Step 6: Commit**

```powershell
git add services/python-engine/app/analysis_ops.py services/python-engine/app/node_definitions.py services/python-engine/app/node_executors.py services/python-engine/tests/test_workflow_runner.py services/python-engine/tests/test_node_catalog_parity.py packages/shared-types/src/index.ts apps/desktop/src/<legacy-generated-node-schema>.ts apps/desktop/src/workflowNodeCatalog.ts apps/desktop/src/workflowNodeRegistry.tsx
git commit -m "feat: add metadata normalization node"
```

---

## Task 5: Add Graph Analysis Kernel Nodes

**Files:**

- Create: `services/python-engine/app/graph_ops.py`
- Create: `services/python-engine/tests/test_graph_ops.py`
- Modify: `services/python-engine/pyproject.toml`
- Modify: `services/python-engine/app/node_definitions.py`
- Modify: `services/python-engine/app/node_executors.py`
- Modify: `services/python-engine/app/defaults.py`
- Modify: `services/python-engine/tests/test_workflow_runner.py`
- Modify: `packages/shared-types/src/index.ts`
- Modify: `apps/desktop/src/<legacy-generated-node-schema>.ts`
- Modify: `apps/desktop/src/workflowNodeCatalog.ts`
- Modify: `apps/desktop/src/workflowNodeRegistry.tsx`

**Step 1: Add dependency**

Add:

```toml
"networkx>=3.4"
```

to `services/python-engine/pyproject.toml`.

Run:

```powershell
.\services\python-engine\.venv\Scripts\python.exe -m pip install -e .\services\python-engine[dev]
```

**Step 2: Write graph operation tests**

Add tests:

```python
from app.graph_ops import (
    build_term_graph_tables,
    graph_metric_rows,
    community_rows,
    main_path_rows,
    link_prediction_rows,
)


def test_build_term_graph_tables_from_cooccurrence_rows():
    nodes, edges = build_term_graph_tables(
        [{"term_a": "dysprosium", "term_b": "recycling", "cooccurrence_count": 4}]
    )
    assert {row["term"] for row in nodes} == {"dysprosium", "recycling"}
    assert edges[0]["weight"] == 4


def test_graph_metrics_include_pagerank_and_betweenness():
    nodes, edges = build_term_graph_tables(
        [
            {"term_a": "a", "term_b": "b", "cooccurrence_count": 4},
            {"term_a": "b", "term_b": "c", "cooccurrence_count": 3},
        ]
    )
    rows = graph_metric_rows(nodes, edges)
    row_b = next(row for row in rows if row["term"] == "b")
    assert row_b["degree"] == 2
    assert row_b["betweenness"] > 0


def test_community_and_link_prediction_are_deterministic():
    nodes, edges = build_term_graph_tables(
        [
            {"term_a": "a", "term_b": "b", "cooccurrence_count": 4},
            {"term_a": "b", "term_b": "c", "cooccurrence_count": 3},
            {"term_a": "d", "term_b": "e", "cooccurrence_count": 5},
        ]
    )
    assert community_rows(nodes, edges)
    assert link_prediction_rows(nodes, edges, top_n=5)
```

Run:

```powershell
.\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_graph_ops.py -q
```

Expected: fail until implemented.

**Step 3: Implement graph operations**

Implement pure table-in/table-out functions:

- `build_term_graph_tables(cooccurrence_rows, min_edge_weight=1, max_edges=5000)`
- `build_citation_graph_tables(corpus, citation_field="引证专利", cited_by_field="被引证专利")`
- `graph_metric_rows(nodes, edges)`
- `community_rows(nodes, edges, method="greedy_modularity")`
- `main_path_rows(nodes, edges, mode="directed_citation_or_weighted_backbone")`
- `link_prediction_rows(nodes, edges, top_n=200)`

Main-path V1 behavior:

- If edges are directed citation edges, compute a longest weighted DAG path when possible; if cycles exist, use weighted PageRank plus edge weights to produce a backbone path table.
- If only undirected co-occurrence edges exist, return a maximum-spanning-tree backbone ordered by edge weight and mark `main_path_mode = "cooccurrence_backbone"`.

**Step 4: Add nodes**

Add node definitions and executors:

- `build_network`
  - Inputs: `cooccurrence_table_in: CooccurrenceTable`, optional `corpus_in: CorpusTable`
  - Outputs: `graph_node_table`, `graph_edge_table`
- `graph_metrics`
  - Inputs: `graph_node_table_in`, `graph_edge_table_in`
  - Output: `graph_metric_table`
- `community_detection`
  - Inputs: graph node/edge tables
  - Output: `community_table`
- `main_path_analysis`
  - Inputs: graph node/edge tables
  - Output: `main_path_table`
- `link_prediction`
  - Inputs: graph node/edge tables
  - Output: `link_prediction_table`

Add result bundle keys:

- `graph_node_table`
- `graph_edge_table`
- `graph_metric_table`
- `community_table`
- `main_path_table`
- `link_prediction_table`

**Step 5: Add workflow runner integration tests**

Add a graph workflow test:

```python
def test_graph_nodes_run_from_cooccurrence_to_link_prediction(isolated_workspace):
    # corpus_input -> clean_text -> normalize_text -> tokenize -> apply_dictionary_rules
    # -> filter_terms -> cooccurrence_analysis -> build_network -> graph_metrics
    # -> community_detection -> main_path_analysis -> link_prediction -> save_html_report
    assert run["status"] == "completed"
    assert manifest["results"]["graph_metric_table"]
    assert manifest["results"]["community_table"]
    assert manifest["results"]["main_path_table"]
    assert manifest["results"]["link_prediction_table"]
```

**Step 6: Update frontend schema/editor**

Update:

- `packages/shared-types/src/index.ts`
- `apps/desktop/src/<legacy-generated-node-schema>.ts`
- `apps/desktop/src/workflowNodeCatalog.ts`
- `apps/desktop/src/workflowNodeRegistry.tsx`

Add compact editors for:

- min edge weight
- max edges
- graph mode
- community method
- link prediction top N

**Step 7: Pass tests**

Run:

```powershell
npm run test:engine:fast
npm run test --workspace apps/desktop
```

Expected: pass.

**Step 8: Commit**

```powershell
git add services/python-engine/pyproject.toml services/python-engine/app/graph_ops.py services/python-engine/app/node_definitions.py services/python-engine/app/node_executors.py services/python-engine/app/defaults.py services/python-engine/tests/test_graph_ops.py services/python-engine/tests/test_workflow_runner.py packages/shared-types/src/index.ts apps/desktop/src/<legacy-generated-node-schema>.ts apps/desktop/src/workflowNodeCatalog.ts apps/desktop/src/workflowNodeRegistry.tsx
git commit -m "feat: add runnable graph analysis nodes"
```

---

## Task 6: Add Technology Identification Kernel Nodes

**Files:**

- Create: `services/python-engine/app/technology_ops.py`
- Create: `services/python-engine/tests/test_technology_ops.py`
- Modify: `services/python-engine/app/node_definitions.py`
- Modify: `services/python-engine/app/node_executors.py`
- Modify: `services/python-engine/app/defaults.py`
- Modify: `services/python-engine/tests/test_workflow_runner.py`
- Modify: `packages/shared-types/src/index.ts`
- Modify: `apps/desktop/src/<legacy-generated-node-schema>.ts`
- Modify: `apps/desktop/src/workflowNodeCatalog.ts`
- Modify: `apps/desktop/src/workflowNodeRegistry.tsx`

**Step 1: Write failing technology tests**

```python
from app.technology_ops import technology_indicator_rows, technology_classification_rows


def test_technology_indicators_score_recent_growth_and_graph_bridge():
    term_year = [
        {"term": "dysprosium recycling", "year": 2021, "tf_in_year": 1, "df_in_year": 1},
        {"term": "dysprosium recycling", "year": 2024, "tf_in_year": 8, "df_in_year": 4},
        {"term": "legacy alloy", "year": 2021, "tf_in_year": 8, "df_in_year": 5},
        {"term": "legacy alloy", "year": 2024, "tf_in_year": 7, "df_in_year": 5},
    ]
    graph_metrics = [
        {"term": "dysprosium recycling", "betweenness": 0.5, "pagerank": 0.2},
        {"term": "legacy alloy", "betweenness": 0.01, "pagerank": 0.1},
    ]

    rows = technology_indicator_rows(term_year, graph_metrics, current_year=2024)
    emerging = next(row for row in rows if row["term"] == "dysprosium recycling")

    assert emerging["novelty_score"] > 0
    assert emerging["disruption_score"] > 0
    assert emerging["growth_rate"] > 1


def test_technology_classification_labels_emerging_terms():
    rows = technology_classification_rows(
        [
            {
                "term": "dysprosium recycling",
                "novelty_score": 0.9,
                "disruption_score": 0.7,
                "maturity_score": 0.2,
                "growth_rate": 3.0,
            }
        ]
    )
    assert rows[0]["technology_class"] == "emerging"
```

Run:

```powershell
.\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_technology_ops.py -q
```

Expected: fail.

**Step 2: Implement indicators**

Implement transparent V1 formulas:

- `first_year`
- `last_year`
- `total_tf`
- `recent_tf`
- `baseline_tf`
- `growth_rate = (recent_tf + 1) / (baseline_tf + 1)`
- `novelty_score`: high when first year is recent, baseline is low, and recent share is high.
- `disruption_score`: high when growth is high, betweenness is high, and the term bridges communities.
- `maturity_score`: high when the term is old, stable, and high-frequency.

Return every component column. Avoid hidden magic.

**Step 3: Implement classification**

Configurable thresholds:

- `emerging`: novelty >= `0.65` and growth >= `1.5`
- `disruptive`: disruption >= `0.65`
- `core`: maturity >= `0.65`
- `declining`: growth <= `0.75` and maturity >= `0.4`
- fallback: `monitor`

Return:

- `term`
- `technology_class`
- `confidence`
- `primary_reason`
- component scores

**Step 4: Add nodes**

Add:

- `technology_indicators`
  - Inputs: `term_year_table_in`, optional `graph_metric_table_in`, optional `community_table_in`
  - Output: `technology_indicator_table`
- `technology_classification`
  - Input: `technology_indicator_table_in`
  - Output: `technology_classification_table`

Add result bundle keys.

**Step 5: Add workflow tests**

Add a test that runs:

`term_year_analysis -> build_network -> graph_metrics -> technology_indicators -> technology_classification`

Expected:

- run completes
- both result tables are non-empty
- each classification row has `primary_reason`

**Step 6: Pass tests**

Run:

```powershell
npm run test:engine:fast
npm run test --workspace apps/desktop
```

Expected: pass.

**Step 7: Commit**

```powershell
git add services/python-engine/app/technology_ops.py services/python-engine/app/node_definitions.py services/python-engine/app/node_executors.py services/python-engine/app/defaults.py services/python-engine/tests/test_technology_ops.py services/python-engine/tests/test_workflow_runner.py packages/shared-types/src/index.ts apps/desktop/src/<legacy-generated-node-schema>.ts apps/desktop/src/workflowNodeCatalog.ts apps/desktop/src/workflowNodeRegistry.tsx
git commit -m "feat: add technology identification nodes"
```

---

## Task 7: Build New Flow Workflow Factory

**Files:**

- Create: `services/python-engine/app/new_flow_workflow.py`
- Create: `services/python-engine/tests/test_new_flow_workflow.py`
- Modify: `services/python-engine/app/defaults.py`
- Modify: `services/python-engine/app/sample_projects.py`
- Modify: `apps/desktop/src/workflowNodeCatalog.ts`
- Modify: `apps/desktop/src/screens.tsx`
- Modify: `docs/workflow-runtime.md`

**Step 1: Write failing workflow factory tests**

```python
from app.new_flow_workflow import build_new_flow_workflow


def test_new_flow_workflow_contains_revised_flow_nodes():
    workflow = build_new_flow_workflow("wf-test", "新版流程")
    node_types = {node["node_type"] for node in workflow["nodes"]}

    assert {
        "corpus_input",
        "normalize_metadata",
        "deduplicate_documents",
        "clean_text",
        "normalize_text",
        "tokenize",
        "apply_dictionary_rules",
        "filter_terms",
        "feature_term_selection",
        "keyword_extraction",
        "keyword_clustering",
        "topic_modeling",
        "document_clustering",
        "cooccurrence_analysis",
        "build_network",
        "graph_metrics",
        "community_detection",
        "main_path_analysis",
        "link_prediction",
        "technology_indicators",
        "technology_classification",
        "institution_keyword_analysis",
        "institution_topic_analysis",
        "save_csv",
        "save_xlsx",
        "save_png",
        "save_html_report",
    } <= node_types


def test_new_flow_workflow_edges_are_valid_against_node_ports():
    workflow = build_new_flow_workflow("wf-test", "新版流程")
    # Validate every edge references an existing node and port.
```

Run:

```powershell
.\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_new_flow_workflow.py -q
```

Expected: fail.

**Step 2: Implement workflow factory**

Do not hardcode workflow logic in UI. Build workflow graphs in Python from the node registry.

Expose:

```python
def build_new_flow_workflow(
    workflow_id: str,
    name: str,
    *,
    source_profile: str = "generic",
    include_multisource: bool = False,
    include_patent_graph: bool = True,
) -> dict[str, Any]:
    ...
```

Add workflow metadata:

```python
"meta": {
    "flow_schema_version": "2026-05-new-flow",
    "flow_source": "修改版流程.docx",
    "flow_blocks": [...]
}
```

**Step 3: Use the factory for default workflows**

Modify `default_workflow_definition()` only after tests are ready.

Keep fallback behavior if a plugin/custom workflow is loaded.

**Step 4: Update frontend node positions**

Add positions for all new nodes. Keep the canvas readable:

- left: source/input/profile nodes
- middle: cleaning/token/dictionary
- upper right: tables/statistics
- middle right: keywords/topics/clustering
- lower right: graph/technology
- far right: exports

**Step 5: Pass tests**

Run:

```powershell
npm run test:engine:fast
npm run test --workspace apps/desktop
```

Expected: pass.

**Step 6: Commit**

```powershell
git add services/python-engine/app/new_flow_workflow.py services/python-engine/app/defaults.py services/python-engine/app/sample_projects.py services/python-engine/tests/test_new_flow_workflow.py apps/desktop/src/workflowNodeCatalog.ts apps/desktop/src/screens.tsx docs/workflow-runtime.md
git commit -m "feat: define revised executable workflow graph"
```

---

## Task 8: Replace Old Built-In Sample Projects

**Files:**

- Rewrite: `services/python-engine/app/sample_projects.py`
- Modify: `services/python-engine/app/bundled_sample_workspace.py`
- Rewrite/update: `services/python-engine/tests/test_sample_projects.py`
- Modify: `services/python-engine/tests/test_workspace_cli.py`
- Modify: `scripts/build-bundled-sample-workspace.ps1`
- Modify: `scripts/build-python-sidecar.ps1`
- Modify: `docs/sample-projects.md`
- Modify: `docs/examples.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Step 1: Write failing sample spec tests**

Replace old nine-scenario tests with:

```python
def test_builtin_sample_specs_are_new_flow_samples():
    assert [spec["slug"] for spec in BUILTIN_SAMPLE_PROJECTS] == [
        "sample-01-wos-paper-keyword-topic",
        "sample-02-incopat-patent-technology-graph",
        "sample-03-paper-patent-integrated-map",
    ]
    assert all(spec["flow_schema_version"] == "2026-05-new-flow" for spec in BUILTIN_SAMPLE_PROJECTS)


def test_builtin_samples_do_not_retain_raw_import_files(bundled_builtin_sample_projects):
    for project_dir, manifest in bundled_builtin_sample_projects:
        imported_dir = project_dir / "corpus" / "imported"
        assert not any(imported_dir.glob("*"))
        assert (project_dir / "project.db").exists()
        assert all(not str(source.get("relative_path") or "").startswith("corpus/imported/") for source in manifest["source_files"])
```

**Step 2: Create tiny test seeds**

In test fixtures, create small WoS and IncoPat seed files with pandas in a temp directory.

Do not use the user-downloaded files in tests.

**Step 3: Rewrite sample specs**

`BUILTIN_SAMPLE_PROJECTS` should contain three specs only.

Each spec includes:

- `order`
- `slug`
- `name`
- `description`
- `source_profiles`
- `flow_schema_version`
- `seed_source_ids`
- `workflow_name`
- `guided_steps`
- `covered_nodes`
- `covered_outputs`
- `redistribution`
- `license_note`

**Step 4: Materialize samples as already-imported projects**

Sample build flow:

1. Read seed files from `sample_seed_sources.py`.
2. Validate redistribution gate.
3. Import rows using `import_files()` and source-profile templates.
4. Save imported corpus into `project.db`.
5. Delete or never create `corpus/imported/*`.
6. Save logical `source_files` records:

```python
{
    "id": "source-wos-seed",
    "name": "WoS rare-earth sample",
    "source_type": "xls",
    "source_profile": "wos",
    "relative_path": "",
    "retained_in_project": False,
    "imported_at": "...",
    "row_count": 250,
    "license_note": "..."
}
```

7. Save `ingestion_specs` with full field mapping and text build config.
8. Save workflow from `build_new_flow_workflow()`.
9. Save dictionary terms relevant to rare earth / patent intelligence.

**Step 5: Sample-specific workflows**

`示例 01 - WoS论文关键词与主题流程`:

- Uses WoS profile.
- Uses workflow branches through feature terms, keywords, topics, term-year, co-occurrence, graph from co-occurrence, exports.

`示例 02 - IncoPat专利技术识别与图分析`:

- Uses IncoPat profile.
- Includes metadata normalization, patent citation graph if citation fields exist, graph metrics, community detection, main path, link prediction, technology indicators, technology classification.

`示例 03 - 论文专利融合分析流程`:

- Imports both WoS and IncoPat seed rows into one project.
- Preserves `source_profile`.
- Includes dedupe, metadata normalization, institution keyword/topic, graph and technology outputs.

**Step 6: Remove old public sample cache dependency**

Delete or archive the old public cache modules and scripts unless a non-sample production path still needs them. Sample bootstrap must no longer require:

- `services/python-engine/app/public_sample_cache/*`
- `scripts/fetch-public-sample-data.ps1`
- `sample_dataset_sources.py`
- `sample_dataset_cache.py`
- `public_sample_data_builder.py`
- `tests/sample_test_support.py`
- `tests/test_public_sample_data_builder.py`
- `tests/test_sample_dataset_cache.py`
- `tests/test_sample_dataset_sources.py`

If a helper is still useful only as reference, move it under `docs/archive/` as documentation, not importable runtime/test code.

`scripts/build-python-sidecar.ps1` must package the built `bundled_sample_workspace` but not package local seed source directories.

**Step 7: Update workspace bootstrap tests**

Tests should assert:

- first launch restores three samples
- first current project is `示例 01 - WoS论文关键词与主题流程`
- `builtin_samples_revision` increments
- existing old sample projects are not recreated
- a workspace with legacy sample slugs gets refreshed to the new sample set only when it is a built-in sample, not a user project

**Step 8: Pass full engine tests**

This task touches sample bootstrap and packaging, so run:

```powershell
npm run test:engine:full
```

Expected: pass.

**Step 9: Commit**

```powershell
git add services/python-engine/app/sample_projects.py services/python-engine/app/bundled_sample_workspace.py services/python-engine/tests/test_sample_projects.py services/python-engine/tests/test_workspace_cli.py scripts/build-bundled-sample-workspace.ps1 scripts/build-python-sidecar.ps1 docs/sample-projects.md docs/examples.md README.md CHANGELOG.md
git commit -m "feat: replace built-in samples with revised flow projects"
```

---

## Task 8A: Purge Legacy Sample Scripts, Fixtures, and Assertions

**Files:**

- Delete: `scripts/fetch-public-sample-data.ps1`
- Delete: `services/python-engine/app/sample_dataset_sources.py`
- Delete: `services/python-engine/app/sample_dataset_cache.py`
- Delete: `services/python-engine/app/public_sample_data_builder.py`
- Delete: `services/python-engine/app/public_sample_cache/manifest.json`
- Delete: `services/python-engine/app/public_sample_cache/*.jsonl.gz`
- Delete: `services/python-engine/tests/sample_test_support.py`
- Delete: `services/python-engine/tests/test_public_sample_data_builder.py`
- Delete: `services/python-engine/tests/test_sample_dataset_cache.py`
- Delete: `services/python-engine/tests/test_sample_dataset_sources.py`
- Modify: `services/python-engine/tests/conftest.py`
- Modify: `services/python-engine/tests/test_sample_projects.py`
- Modify: `services/python-engine/tests/test_workspace_cli.py`
- Modify: `scripts/build-bundled-sample-workspace.ps1`
- Modify: `scripts/build-python-sidecar.ps1`
- Modify: `README.md`
- Modify: `docs/sample-projects.md`
- Modify: `docs/examples.md`
- Modify: `docs/development.md`
- Modify: `docs/benchmark.md`

**Step 1: Prove no active code imports legacy sample modules**

Run:

```powershell
git grep -n "sample_dataset_sources\|sample_dataset_cache\|public_sample_data_builder\|public_sample_cache\|fetch-public-sample-data" -- . ':!docs/archive'
```

Expected before cleanup: matches exist.

**Step 2: Remove imports and fixtures**

Update `services/python-engine/tests/conftest.py` so bundled sample fixtures are built from the new WoS/IncoPat test seed files, not `populate_public_sample_cache()`.

Remove any fixture or helper that mentions:

- `TEST_SAMPLE_ROW_LIMIT` as an English/Chinese balance rule
- `public_sample_cache_root`
- `bundled_public_sample_cache_root`
- `placeholder_row`
- nine-scenario sample names

**Step 3: Delete legacy files**

Delete the files listed above. If any file is still referenced by production code, stop and either remove that reference or document why the file is still required. Do not keep a stale test just to preserve coverage for deleted behavior.

**Step 4: Update build scripts**

`scripts/build-bundled-sample-workspace.ps1`:

- must not call `fetch-public-sample-data.ps1`
- must not validate `app/public_sample_cache`
- must pass seed paths and license flags to `app.bundled_sample_workspace`

`scripts/build-python-sidecar.ps1`:

- must not require or package `app/public_sample_cache`
- must package only built sample workspace, builtin dictionaries, and runtime dependencies

**Step 5: Update docs**

Replace old wording:

- "9 个官方场景样例"
- "英中 1:1"
- "public sample cache"
- "fetch-public-sample-data.ps1"
- "OpenAlex/Wikimedia/UN public sample cache"

with new wording:

- three revised-flow samples
- source-profile samples for WoS/IncoPat
- already-imported `project.db`
- no retained raw source files
- restricted/private seed build versus redistributable release build

**Step 6: Verify the purge**

Run:

```powershell
git grep -n "示例 09\|示例 08\|9 个官方\|public_sample_cache\|fetch-public-sample-data\|sample_dataset_sources\|sample_dataset_cache\|OpenAlex\|Wikimedia\|United Nations Parallel" -- . ':!docs/archive'
```

Expected: no active-code matches. Any remaining docs match must describe migration history or licensing context, not current behavior.

Run:

```powershell
npm run test:engine:full
```

Expected: pass.

**Step 7: Commit**

```powershell
git add -A scripts services/python-engine README.md docs/sample-projects.md docs/examples.md docs/development.md docs/benchmark.md
git commit -m "chore: remove legacy sample cache and tests"
```

---

## Task 9: Update Frontend Sample Guidance and Result Surfaces

**Files:**

- Modify: `apps/desktop/src/screens.tsx`
- Modify: `apps/desktop/src/features/artifacts/ArtifactBrowser.tsx`
- Modify: `apps/desktop/src/features/results/RunHistoryPanel.tsx`
- Modify: `apps/desktop/src/data/demoProject.ts`
- Modify: `apps/desktop/src/store/workspaceStore.test.ts`
- Modify: `apps/desktop/src/features/artifacts/ArtifactBrowser.test.tsx`
- Modify: `apps/desktop/src/features/resources/ResourceBrowser.test.tsx`

**Step 1: Write failing UI tests**

Update tests so they no longer expect the old demo name or nine samples.

Expected UI behavior:

- Welcome/sample area shows the new sample names.
- Sample quick actions open data, dictionaries, workflow.
- Artifact browser can preview new artifact kinds:
  - `graph_metric_table`
  - `community_table`
  - `main_path_table`
  - `link_prediction_table`
  - `technology_indicator_table`
  - `technology_classification_table`
  - `metadata_audit_table`

**Step 2: Update result summaries**

Update `summarizePortValue` / equivalent screen helpers so new result ports have meaningful summaries.

Examples:

- graph metrics: show top terms by PageRank/degree
- community: show community count and representative terms
- main path: show path length and top edges
- technology classification: show counts by class

**Step 3: Keep fallback demo small**

`apps/desktop/src/data/demoProject.ts` remains a tiny non-Tauri fallback, not a mirror of bundled samples.

Add only enough graph/technology rows for component tests.

**Step 4: Pass frontend tests**

Run:

```powershell
npm run test --workspace apps/desktop
npm run build --workspace apps/desktop
```

Expected: pass.

**Step 5: Commit**

```powershell
git add apps/desktop/src/screens.tsx apps/desktop/src/features/artifacts/ArtifactBrowser.tsx apps/desktop/src/features/results/RunHistoryPanel.tsx apps/desktop/src/data/demoProject.ts apps/desktop/src/store/workspaceStore.test.ts apps/desktop/src/features/artifacts/ArtifactBrowser.test.tsx apps/desktop/src/features/resources/ResourceBrowser.test.tsx
git commit -m "feat: surface revised sample and graph results in desktop UI"
```

---

## Task 10: Build, Size, and Reliability Validation

**Files:**

- Modify: `docs/benchmark.md`
- Modify: `docs/current-status.md`
- Modify: `docs/architecture.md`
- Modify: `README.md`

**Step 1: Build bundled sample workspace**

For local/private validation with restricted seed files:

```powershell
.\scripts\build-bundled-sample-workspace.ps1 `
  -WosSeed "C:\Users\blmpt\Downloads\TextFlow\稀土wos.xls" `
  -IncopatSeed "C:\Users\blmpt\Downloads\TextFlow\稀缺稀土元素.xlsx" `
  -AllowRestrictedSampleData `
  -RowLimit 300
```

For release validation, omit `-AllowRestrictedSampleData`. The build must fail unless seeds are marked `approved`.

**Step 2: Run full engine suite**

```powershell
npm run test:engine:full
```

Expected: pass.

**Step 3: Run frontend suite and build**

```powershell
npm run test --workspace apps/desktop
npm run build --workspace apps/desktop
```

Expected: pass.

**Step 4: Validate SQLite integrity on samples**

Add or run a small script/check:

```powershell
.\services\python-engine\.venv\Scripts\python.exe -m app.bundled_sample_workspace --output .\services\python-engine\app\bundled_sample_workspace --row-limit 300
```

Then verify each bundled sample:

- `project.db` exists
- `PRAGMA integrity_check` returns `ok`
- `corpus/imported` is empty
- workflows run
- artifacts preview from SQLite

**Step 5: Compare size**

Record:

- old bundled sample workspace size
- new bundled sample workspace size
- per-project `project.db` size
- first workflow run duration for each sample
- second workflow run duration to confirm cache behavior

Update `docs/benchmark.md`.

**Step 6: Build sidecar**

```powershell
.\scripts\build-python-sidecar.ps1
```

Expected:

- sidecar builds
- `networkx` included
- bundled workspace included
- seed source directory not included

**Step 7: Commit**

```powershell
git add docs/benchmark.md docs/current-status.md docs/architecture.md README.md
git commit -m "docs: record revised flow sample validation"
```

---

## Final Acceptance Checklist

- `npm run test:engine:fast` passes.
- `npm run test:engine:full` passes.
- `npm run test --workspace apps/desktop` passes.
- `npm run build --workspace apps/desktop` passes.
- `.\scripts\build-python-sidecar.ps1` succeeds.
- Fresh empty workspace restores exactly the new sample projects.
- Built-in samples contain `project.db`.
- Built-in samples do not contain raw import source files under `corpus/imported`.
- Every new node has Python definition, executor, result binding, frontend schema, and tests.
- Graph and technology nodes produce non-empty outputs on the IncoPat sample.
- WoS import profile is exercised by a bundled or private-build sample.
- Scopus import profile has unit tests but is not advertised as a bundled sample until data exists.
- Docs state the licensing gate and explain how to build private versus redistributable samples.

## Opencode Session Prompt

Paste this into a fresh Opencode Plan session:

```text
We are in C:\Users\blmpt\Downloads\TextFlow. Follow docs/plans/2026-05-05-new-flow-samples-kernel-and-sqlite.md exactly.

Important constraints:
- Read AGENTS.md first.
- Start in Plan mode and confirm the task order before editing.
- Do not ship raw sample source files inside bundled .tfproj projects.
- Add runnable engine nodes for metadata normalization, graph analysis, and technology identification.
- Add project-local SQLite storage for corpus and artifacts.
- Replace the old nine built-in samples with the three revised-flow samples.
- Scopus gets an import profile and tests, but no bundled sample until data exists.
- Run npm run test:engine:full after touching sample bootstrap or packaging.
```
