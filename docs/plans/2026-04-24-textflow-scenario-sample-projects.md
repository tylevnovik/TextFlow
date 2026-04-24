# TextFlow Scenario Sample Projects Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task.

**Goal:** Replace the current small capability-demo samples with nine large, scenario-based built-in sample projects backed only by real public datasets, with every scenario containing a 1:1 English/Chinese language split.

**Architecture:** Built-in sample projects must remain backend-owned. The Python sidecar creates normal `.tfproj` projects from packaged or cached normalized subsets of real public datasets, enforces per-sample `en`/`zh` balance, and stores source attribution plus scenario guidance in `settings.sample_project`. The frontend static `demoProject.ts` remains only a non-Tauri fallback/test fixture and must not become the source of real sample data.

**Tech Stack:** Python 3.11 sidecar, pandas/openpyxl for public sample files, existing TextFlow project store/workflow runtime, pytest for engine tests, Markdown docs.

---

## Non-Negotiable Decisions

- Create all nine sample projects during backend workspace bootstrap; do not hide advanced samples by default.
- Each official sample project must have a default corpus size of at least `10_000` documents.
- Every official sample project must contain exactly 50% English rows and 50% Chinese rows. For 10,000 rows this means 5,000 `en` rows and 5,000 `zh` rows; sample 01 has 10,000 `en` rows and 10,000 `zh` rows.
- Use only real public datasets; do not synthesize text rows, institutions, abstracts, reviews, complaints, patents, filings, labels, or metadata.
- Every sample row must be traceable to a public source dataset through `source_dataset_id`, `source_url`, `source_license`, and `source_record_id` where available.
- Every sample row must include a normalized `language` field with value `en` or `zh`, and language must be derived from source metadata or deterministic language detection over real text.
- If a public dataset must be subsetted for size, select a deterministic subset from real records only; do not fill gaps with fabricated text.
- Package normalized public-data subsets for offline first launch, or fetch/cache them during build; runtime bootstrap must not require internet.
- English-only datasets may be used only as optional enrichment and only if matched by the same number of real Chinese rows in the same sample.
- Keep normal Tauri app behavior backend-driven through Python sidecar projects.
- Do not bulk-expand `apps/desktop/src/data/demoProject.ts`; it is only a mock/test fixture.
- Do not teach or cover legacy nodes: `load_project_corpus`, `filter_corpus`, `project_dictionary_set`, `analyze_corpus`, `export_results`.
- If a sample needs faster development/test creation, use an environment override such as `TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT` to read fewer real records from the local public-data cache; production defaults must stay at `>= 10_000`.

## Approved Public Data Sources

The implementation may use these public sources. If a source becomes unavailable, replace it with another real public dataset and update this table before implementation.

| Dataset ID | Source | Languages | Public Access / License Notes | Intended Samples |
| --- | --- | --- | --- | --- |
| `un_parallel_en_zh` | [United Nations Parallel Corpus v1.0](https://www.un.org/dgacm/en/node/5471) and [download page](https://www.un.org/dgacm/en/content/uncorpus/download) | `en`, `zh` | Official UN records and parliamentary documents in the public domain, manually translated across UN official languages. | 02, 05, 09 |
| `wikimedia_enwiki` | [English Wikipedia dumps](https://dumps.wikimedia.org/enwiki/latest/) | `en` | Wikimedia text dumps are reusable under CC BY-SA 4.0 / GFDL terms, with attribution and share-alike obligations. | 01, 06, 07, 08 |
| `wikimedia_zhwiki` | [Chinese Wikipedia dumps](https://dumps.wikimedia.org/zhwiki/latest/) | `zh` | Same Wikimedia text dump licensing; use text-only article dumps and preserve source page attribution. | 01, 06, 07, 08 |
| `openalex_works` | [OpenAlex Works API or snapshot](https://developers.openalex.org/) | `en`, `zh` | OpenAlex documents its complete dataset as free under CC0 / No Rights Reserved; select by source `language` metadata. | 03, 04, 06, 09 |
| `cfpb_complaints_optional` | [CFPB Consumer Complaint Database](https://www.consumerfinance.gov/data-research/consumer-complaints/) | `en` | CFPB says all published complaint data is freely available to use, analyze, and build on; use only as balanced optional enrichment. | optional enrichment only |
| `patentsview_optional` | [USPTO PatentsView](https://www.uspto.gov/ip-policy/economic-research/patentsview) and [PatentsView data downloads](https://patentsview.org/downloads/data-downloads) | `en` | USPTO describes PatentsView as a public, research-grade patent-data resource; use only as balanced optional enrichment. | optional enrichment only |
| `20_newsgroups_optional` | [UCI KDD 20 Newsgroups](https://kdd.ics.uci.edu/databases/20newsgroups/20newsgroups.html) | `en` | Public research dataset hosted by UCI KDD; use only as an optional substitute if redistribution terms are reviewed and documented in the manifest. | optional substitute only |

Default sample execution must use bilingual-capable or paired sources: `un_parallel_en_zh`, `wikimedia_enwiki` + `wikimedia_zhwiki`, and `openalex_works` filtered to `en` and `zh`. Do not use AG News, Yelp, Amazon reviews, or other datasets with unclear redistribution terms unless their license is reviewed and documented in this plan before implementation.

## Language Balance Rule

Every sample project is a bilingual task scenario. The implementation must calculate the requested row count per sample, split it into equal `en` and `zh` quotas, then pull real rows from approved public sources for each quota. If a source cannot satisfy either quota, fail the sample creation with a clear error; do not downsample only one language, backfill with another language, translate rows, or create synthetic rows.

The per-row `language` value must be visible in imported corpus metadata so users can filter, group, and audit language-specific behavior.

## Target Sample Projects

| Order | Sample Project | Default Rows | Language Split | Primary User Question |
| --- | --- | ---: | --- | --- |
| 01 | `示例 01 - 基础文本预处理` | 20,000 | 10,000 `en` / 10,000 `zh` | “我有一批杂乱文本，如何清洗、标准化、切词并导出？” |
| 02 | `示例 02 - 词表治理与词频统计` | 10,000 | 5,000 `en` / 5,000 `zh` | “如何保留行业术语、统一同义词、过滤噪声并看高频词？” |
| 03 | `示例 03 - 学术摘要关键词与主题` | 10,000 | 5,000 `en` / 5,000 `zh` | “如何从论文摘要中找关键词、主题和时间趋势？” |
| 04 | `示例 04 - 机构主题与技术方向` | 10,000 | 5,000 `en` / 5,000 `zh` | “如何比较机构、关键词和主题之间的关系？” |
| 05 | `示例 05 - 复核实验与增量运行` | 10,000 | 5,000 `en` / 5,000 `zh` | “如何复核结果、调参比较，并只重跑变更文档？” |
| 06 | `示例 06 - 多来源语料合并与抽样` | 10,000 | 5,000 `en` / 5,000 `zh` | “如何合并 CSV/XLSX/JSON/TXT，多来源去重和抽样？” |
| 07 | `示例 07 - 分组比较与关键性分析` | 10,000 | 5,000 `en` / 5,000 `zh` | “如何比较不同时间、机构或产品线的关键词差异？” |
| 08 | `示例 08 - 切分评估与结果拼接` | 10,000 | 5,000 `en` / 5,000 `zh` | “如何切分语料、建模、评估聚类并拼接结果？” |
| 09 | `示例 09 - 条件路由与人工门禁` | 10,000 | 5,000 `en` / 5,000 `zh` | “如何用条件、指标门禁和人工复核控制工作流？” |

## Node Coverage Matrix

| Node | Covered By |
| --- | --- |
| `corpus_input` | 01-09 |
| `dictionary_input` | 01-09 |
| `merge_corpora` | 06 |
| `select_dictionary_tables` | 02 |
| `overlay_dictionary_rules` | 02, 05 |
| `filter_by_metadata` | 04, 06, 07 |
| `deduplicate_documents` | 06 |
| `sample_corpus` | 06 |
| `split_corpus` | 08 |
| `bucket_by_time` | 04, 07 |
| `conditional_router` | 09 |
| `result_gate` | 09 |
| `manual_review_gate` | 09 |
| `clean_text` | 01-09 |
| `normalize_text` | 01-09 |
| `tokenize` | 01-09 |
| `apply_dictionary_rules` | 01-09 |
| `filter_terms` | 01-09 |
| `frequency_statistics` | 01, 02, 06, 07 |
| `term_document_analysis` | 02, 03 |
| `term_year_analysis` | 03, 04, 07 |
| `cooccurrence_analysis` | 02, 06 |
| `group_compare` | 07 |
| `keyness_analysis` | 07 |
| `topic_modeling` | 03, 08 |
| `cluster_evaluation` | 08 |
| `join_results` | 08 |
| `feature_term_selection` | 03, 04 |
| `keyword_extraction` | 03, 04, 05 |
| `keyword_clustering` | 03, 05 |
| `institution_keyword_analysis` | 04 |
| `institution_topic_analysis` | 04 |
| `document_clustering` | 03, 08 |
| `save_csv` | 01, 02, 06, 07, 08 |
| `save_xlsx` | 02, 03, 04, 08 |
| `save_png` | 03, 04, 06, 07, 08 |
| `save_html_report` | 01-09 |
| `note` | 01-09 |
| `group` | 01-09 |

## Task 1: Add Public Dataset Source Registry and Normalization

**Files:**
- Create: `services/python-engine/app/sample_dataset_sources.py`
- Create: `services/python-engine/tests/test_sample_dataset_sources.py`

**Step 1: Write failing source registry tests**

Add tests:

```python
def test_public_source_registry_contains_only_real_public_sources():
    source_ids = {source.source_id for source in PUBLIC_SAMPLE_DATA_SOURCES}
    assert {"un_parallel_en_zh", "wikimedia_enwiki", "wikimedia_zhwiki", "openalex_works"} <= source_ids
    for source in PUBLIC_SAMPLE_DATA_SOURCES:
        assert source.name
        assert source.homepage_url.startswith("https://")
        assert source.license_name
        assert source.public_access_note
        assert source.redistribution_note
        assert set(source.languages) <= {"en", "zh"}


def test_default_sources_can_supply_english_and_chinese_rows():
    assert source_supports_language("un_parallel_en_zh", "en")
    assert source_supports_language("un_parallel_en_zh", "zh")
    assert source_supports_language("wikimedia_enwiki", "en")
    assert source_supports_language("wikimedia_zhwiki", "zh")
    assert source_supports_language("openalex_works", "en")
    assert source_supports_language("openalex_works", "zh")


def test_normalized_public_row_requires_source_attribution():
    row = normalize_public_sample_row(
        {
            "doc_id": "source-1",
            "title": "真实公开来源标题",
            "raw_text": "真实公开来源文本",
            "year": 2024,
        },
        dataset_id="un_parallel_en_zh",
        language="zh",
        source_record_id="source-1",
        source_url="https://www.un.org/dgacm/en/node/5471",
    )
    assert row["language"] == "zh"
    assert row["extra_metadata"]["source_dataset_id"] == "un_parallel_en_zh"
    assert row["extra_metadata"]["source_record_id"] == "source-1"
    assert row["raw_text"] == "真实公开来源文本"
```

Also add a guard test:

```python
def test_normalization_rejects_missing_text():
    with pytest.raises(ValueError):
        normalize_public_sample_row({"doc_id": "bad"}, dataset_id="un_parallel_en_zh", language="en")


def test_normalization_rejects_unsupported_language():
    with pytest.raises(ValueError):
        normalize_public_sample_row({"doc_id": "bad", "raw_text": "bonjour"}, dataset_id="un_parallel_en_zh", language="fr")
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_dataset_sources.py -q
```

Expected: FAIL because `sample_dataset_sources.py` does not exist.

**Step 3: Implement public source registry**

Create `sample_dataset_sources.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PublicSampleDataSource:
    source_id: str
    name: str
    homepage_url: str
    download_url: str | None
    languages: tuple[str, ...]
    license_name: str
    public_access_note: str
    redistribution_note: str
    citation: str


PUBLIC_SAMPLE_DATA_SOURCES = [
    PublicSampleDataSource(
        source_id="un_parallel_en_zh",
        name="United Nations Parallel Corpus v1.0",
        homepage_url="https://www.un.org/dgacm/en/node/5471",
        download_url="https://www.un.org/dgacm/en/content/uncorpus/download",
        languages=("en", "zh"),
        license_name="Public domain UN official records and parliamentary documents",
        public_access_note="UN describes the corpus as public-domain official records and other parliamentary documents.",
        redistribution_note="Package only normalized text rows with UN corpus attribution and language metadata.",
        citation="United Nations Parallel Corpus v1.0.",
    ),
    ...
]


PUBLIC_SAMPLE_DATA_SOURCE_BY_ID = {source.source_id: source for source in PUBLIC_SAMPLE_DATA_SOURCES}


def source_supports_language(dataset_id: str, language: str) -> bool:
    source = PUBLIC_SAMPLE_DATA_SOURCE_BY_ID.get(dataset_id)
    return bool(source and language in source.languages)
```

Include registry entries for:

- `un_parallel_en_zh`
- `wikimedia_enwiki`
- `wikimedia_zhwiki`
- `openalex_works`
- `cfpb_complaints_optional` only as English enrichment with a matched Chinese row source
- `patentsview_optional` only as English enrichment with a matched Chinese row source
- `20_newsgroups_optional` only if redistribution terms are reviewed and documented

Do not include a source if its redistribution terms are unknown and cannot be documented.

**Step 4: Implement row normalization**

Add:

```python
REQUIRED_SAMPLE_ROW_FIELDS = {
    "doc_id",
    "language",
    "title",
    "raw_text",
    "year",
    "source",
    "institution",
    "category_or_tag",
    "keyword_field",
}


def normalize_public_sample_row(
    row: dict[str, Any],
    *,
    dataset_id: str,
    language: str,
    source_record_id: str | None = None,
    source_url: str | None = None,
    source_profile: str = "generic",
) -> dict[str, Any]:
    ...
```

Rules:

- never fabricate replacement text if source text is missing
- require non-empty `raw_text`
- require `language in {"en", "zh"}` and verify the dataset source supports that language
- preserve original title/text/metadata where available
- write attribution into `extra_metadata`
- set `source_profile` according to the scenario, not by inventing a dataset

**Step 5: Run tests to verify they pass**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_dataset_sources.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add services/python-engine/app/sample_dataset_sources.py services/python-engine/tests/test_sample_dataset_sources.py
git commit -m "feat: add public sample dataset source registry"
```

## Task 2: Add Public Dataset Acquisition and Local Cache Builder

**Files:**
- Create: `services/python-engine/app/sample_dataset_cache.py`
- Create: `services/python-engine/tests/test_sample_dataset_cache.py`
- Create: `scripts/fetch-public-sample-data.ps1`
- Modify: `scripts/build-python-sidecar.ps1`

**Step 1: Write failing cache tests**

Add:

```python
from collections import Counter
from typing import Any


def _row(language: str, idx: int) -> dict[str, Any]:
    return normalize_public_sample_row(
        {
            "doc_id": f"{language}-{idx}",
            "title": f"Real {language} source title {idx}",
            "raw_text": "Real public source text" if language == "en" else "真实公开来源文本",
            "year": 2024,
        },
        dataset_id="wikimedia_enwiki" if language == "en" else "wikimedia_zhwiki",
        language=language,
        source_record_id=f"{language}-{idx}",
        source_url="https://dumps.wikimedia.org/",
    )


def test_cache_loader_reads_real_rows_with_attribution(tmp_path):
    cache_dir = tmp_path / "public-sample-cache"
    write_normalized_sample_cache(
        cache_dir,
        "un_parallel_en_zh",
        [
            normalize_public_sample_row(
                {"doc_id": "un-en-1", "title": "A real UN document", "raw_text": "Real English UN text", "year": 2014},
                dataset_id="un_parallel_en_zh",
                language="en",
                source_record_id="un-en-1",
                source_url="https://www.un.org/dgacm/en/node/5471",
            ),
            normalize_public_sample_row(
                {"doc_id": "un-zh-1", "title": "真实联合国文件", "raw_text": "真实中文联合国文本", "year": 2014},
                dataset_id="un_parallel_en_zh",
                language="zh",
                source_record_id="un-zh-1",
                source_url="https://www.un.org/dgacm/en/node/5471",
            ),
        ],
    )
    rows = read_normalized_sample_cache(cache_dir, "un_parallel_en_zh", limit=2)
    assert {row["language"] for row in rows} == {"en", "zh"}
    assert rows[0]["extra_metadata"]["source_dataset_id"] == "un_parallel_en_zh"


def test_cache_loader_reads_language_balanced_rows(tmp_path):
    cache_dir = tmp_path / "public-sample-cache"
    write_normalized_sample_cache(cache_dir, "wikimedia_enwiki", [_row("en", idx) for idx in range(4)])
    write_normalized_sample_cache(cache_dir, "wikimedia_zhwiki", [_row("zh", idx) for idx in range(4)])
    rows = read_language_balanced_sample_rows(
        cache_dir,
        [
            {"dataset_id": "wikimedia_enwiki", "language": "en", "selector": "sample_01_basic", "ratio": 0.5},
            {"dataset_id": "wikimedia_zhwiki", "language": "zh", "selector": "sample_01_basic", "ratio": 0.5},
        ],
        total_count=6,
    )
    assert Counter(row["language"] for row in rows) == {"en": 3, "zh": 3}


def test_cache_loader_fails_when_real_rows_are_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_normalized_sample_cache(tmp_path, "un_parallel_en_zh", limit=10)


def test_language_balanced_loader_rejects_odd_row_counts(tmp_path):
    with pytest.raises(ValueError):
        read_language_balanced_sample_rows(tmp_path, [], total_count=101)
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_dataset_cache.py -q
```

Expected: FAIL because cache module does not exist.

**Step 3: Implement cache module**

Implement:

```python
def sample_data_cache_root() -> Path: ...
def normalized_cache_path(cache_root: Path, dataset_id: str) -> Path: ...
def write_normalized_sample_cache(cache_root: Path, dataset_id: str, rows: list[dict[str, Any]]) -> Path: ...
def read_normalized_sample_cache(cache_root: Path, dataset_id: str, *, limit: int | None = None, selector: str | None = None) -> list[dict[str, Any]]: ...
def read_language_balanced_sample_rows(cache_root: Path, sources: list[dict[str, Any]], *, total_count: int) -> list[dict[str, Any]]: ...
def ensure_public_sample_cache_available(required_dataset_ids: Iterable[str]) -> None: ...
```

Use `.jsonl.gz` for normalized cache files. The cache rows are derived from real public records only. `read_language_balanced_sample_rows` must require exactly two language groups, split `total_count` evenly, and fail loudly if either language cannot provide enough rows.

**Step 4: Add acquisition script**

Create `scripts/fetch-public-sample-data.ps1` that calls a Python module or inline Python entry point to:

- download or read source data for approved public datasets
- normalize selected fields into TextFlow rows
- normalize and persist `language` as `en` or `zh`
- enforce `LimitPerLanguage` for default sample caches
- preserve source attribution fields
- write `.jsonl.gz` cache files
- write a `manifest.json` with dataset id, URL, license note, row count by language, SHA256, created timestamp

The script may support:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\fetch-public-sample-data.ps1 -Dataset un_parallel_en_zh -Language en,zh -LimitPerLanguage 10000
powershell -ExecutionPolicy Bypass -File .\scripts\fetch-public-sample-data.ps1 -All
```

**Step 5: Package cache with sidecar**

Update `scripts/build-python-sidecar.ps1` only if needed so packaged builds include the normalized public sample cache. The packaged app must not require internet on first launch.

**Step 6: Run cache tests**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_dataset_cache.py -q
```

Expected: PASS.

**Step 7: Commit**

```bash
git add services/python-engine/app/sample_dataset_cache.py services/python-engine/tests/test_sample_dataset_cache.py scripts/fetch-public-sample-data.ps1 scripts/build-python-sidecar.ps1
git commit -m "feat: add public sample dataset cache builder"
```

## Task 3: Refactor Built-In Sample Project Specs

**Files:**
- Modify: `services/python-engine/app/sample_projects.py`
- Modify: `services/python-engine/tests/test_sample_projects.py`

**Step 1: Write failing sample spec tests**

Create or update tests:

```python
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
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_projects.py -q
```

Expected: FAIL because current specs are only three small samples.

**Step 3: Add public-data scenario spec structure**

In `sample_projects.py`, replace the current small inline row lists with public-dataset-backed specs. Keep `FIRST_BUILTIN_SAMPLE_PROJECT_NAME`, but update it to:

```python
FIRST_BUILTIN_SAMPLE_PROJECT_NAME = "示例 01 - 基础文本预处理"
```

Each spec must include:

```python
{
    "order": 1,
    "slug": "sample-01-basic-preprocessing",
    "name": "示例 01 - 基础文本预处理",
    "difficulty": "基础",
    "default_row_count": 20_000,
    "goal": "...",
    "guided_steps": ["...", "..."],
    "covered_nodes": ["corpus_input", "clean_text", ...],
    "covered_settings": ["strip_html", "normalize_numbers", ...],
    "public_data_only": True,
    "language_balance": {"en": 0.5, "zh": 0.5},
    "source_datasets": ["wikimedia_enwiki", "wikimedia_zhwiki"],
    "source_profile": "generic",
    "sources": [
        {"filename": "basic_preprocessing_en.csv", "format": "csv", "dataset_id": "wikimedia_enwiki", "language": "en", "selector": "sample_01_basic", "ratio": 0.5},
        {"filename": "basic_preprocessing_zh.csv", "format": "csv", "dataset_id": "wikimedia_zhwiki", "language": "zh", "selector": "sample_01_basic", "ratio": 0.5},
    ],
    "workflow_name": "...",
    "import_template_overrides": {...},
    "node_config_overrides": {...},
    "dictionary_terms": {...},
    "review_tasks": [],
    "experiment_specs": [],
}
```

Every spec must map to real public datasets and keep a 1:1 English/Chinese split:

- sample 01: `wikimedia_enwiki` + `wikimedia_zhwiki`
- sample 02: `un_parallel_en_zh` with `language=en` and `language=zh`
- sample 03: `openalex_works` filtered to `language=en` and `language=zh`
- sample 04: `openalex_works` filtered to `language=en` and `language=zh`; optional `patentsview_optional` rows require equal Chinese technology rows from `openalex_works`
- sample 05: `un_parallel_en_zh` with `language=en` and `language=zh`
- sample 06: `wikimedia_enwiki` + `wikimedia_zhwiki` plus balanced `openalex_works` slices
- sample 07: `openalex_works` filtered to `language=en` and `language=zh`
- sample 08: `wikimedia_enwiki` + `wikimedia_zhwiki`
- sample 09: `un_parallel_en_zh` plus balanced `openalex_works` slices

Do not use optional sources in default samples unless their redistribution terms are reviewed and documented in the manifest.

**Step 4: Add row limit helper**

Add:

```python
def _sample_row_count(spec: dict[str, Any]) -> int:
    override = os.getenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT")
    if override:
        row_count = int(override)
    else:
        row_count = int(spec.get("default_row_count") or 10_000)
    if row_count < 2 or row_count % 2:
        raise ValueError("Sample row count must be an even number so en/zh rows stay 1:1")
    return row_count
```

Use this only at sample creation time. Do not lower `default_row_count`.

**Step 5: Add multi-source support**

Replace `_write_sample_source(...)` with `_write_sample_sources(...)`:

```python
def _write_sample_sources(project_dir: Path, spec: dict[str, Any], row_count: int) -> list[Path]:
    ...
```

Support formats:

- `csv`
- `xlsx`
- `json`
- `txt`

Use split ratios for sample 06. For `txt`, write one document per line or one file per small batch only if current importer supports it. If importer only treats `.txt` as one document, use `.txt` to demonstrate TXT import and keep most rows in CSV/XLSX/JSON.

All written rows must come from cached public-data records. If a selector cannot provide enough real rows for either language, fail loudly with a message naming the dataset, language, and requested row count. Do not silently replace missing Chinese rows with English rows or vice versa.

**Step 6: Run tests**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_projects.py -q
```

Expected: PASS for spec tests.

**Step 7: Commit**

```bash
git add services/python-engine/app/sample_projects.py services/python-engine/tests/test_sample_projects.py
git commit -m "feat: define nine scenario sample project specs"
```

## Task 4: Build Scenario-Specific Workflows

**Files:**
- Modify: `services/python-engine/app/sample_projects.py`
- Modify: `services/python-engine/tests/test_sample_projects.py`

**Step 1: Write failing workflow coverage tests**

Add:

```python
from app.node_definitions import build_builtin_node_definitions


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
```

Add:

```python
def test_sample_workflow_nodes_match_declared_coverage(monkeypatch, isolated_workspace):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "120")
    created = create_builtin_sample_projects()
    for _project_dir, manifest in created:
        workflow_nodes = {node["node_type"] for node in manifest["workflow_definitions"][0]["nodes"]}
        declared = set(manifest["settings"]["sample_project"]["covered_nodes"])
        assert declared <= workflow_nodes | {"artifact_preview", "review_task", "experiment_matrix", "run_diff", "incremental_run"}
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_projects.py -q
```

Expected: FAIL until workflows include all declared nodes.

**Step 3: Add workflow builder helpers**

In `sample_projects.py`, add helpers:

```python
def _node_by_type(workflow: dict[str, Any], node_type: str) -> dict[str, Any]: ...
def _new_registry_node(node_type: str, node_id: str, config: dict[str, Any], *, x: int, y: int) -> dict[str, Any]: ...
def _connect(workflow: dict[str, Any], from_node: str, from_port: str, to_node: str, to_port: str) -> None: ...
def _bypass_node_types(workflow: dict[str, Any], node_types: set[str]) -> None: ...
def _keep_only_nodes(workflow: dict[str, Any], node_types: set[str]) -> None: ...
```

Use built-in node definitions from `build_builtin_node_definitions()` to copy inputs/outputs from node definitions.

**Step 4: Implement workflow scenario functions**

Add one function per sample:

- `_configure_basic_preprocessing_workflow`
- `_configure_dictionary_frequency_workflow`
- `_configure_academic_keyword_topic_workflow`
- `_configure_institution_topic_workflow`
- `_configure_review_experiment_incremental_workflow`
- `_configure_multisource_merge_sampling_workflow`
- `_configure_group_compare_keyness_workflow`
- `_configure_split_evaluate_join_workflow`
- `_configure_control_gate_workflow`

Each function must:

- set `workflow["source"] = "manual"`
- set a clear `workflow["name"]`
- add `note` and `group` nodes with user-facing explanations
- leave only scenario-relevant outputs active
- use explicit node configs, not hidden defaults, for the settings the sample teaches

**Step 5: Run workflow coverage tests**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_projects.py::test_sample_workflows_cover_all_non_legacy_nodes services\python-engine\tests\test_sample_projects.py::test_sample_workflow_nodes_match_declared_coverage -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add services/python-engine/app/sample_projects.py services/python-engine/tests/test_sample_projects.py
git commit -m "feat: add scenario workflows for built-in samples"
```

## Task 5: Add Project Guidance Metadata, Reviews, and Experiments

**Files:**
- Modify: `services/python-engine/app/sample_projects.py`
- Modify: `services/python-engine/tests/test_sample_projects.py`

**Step 1: Write failing metadata tests**

Add:

```python
def test_created_sample_projects_persist_guidance_metadata(monkeypatch, isolated_workspace):
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
```

Add:

```python
def test_review_and_experiment_sample_contains_product_surfaces(monkeypatch, isolated_workspace):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "120")
    created = create_builtin_sample_projects()
    review_sample = next(manifest for _project_dir, manifest in created if manifest["name"] == "示例 05 - 复核实验与增量运行")
    assert review_sample["review_tasks"]
    assert review_sample["experiment_specs"]
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_projects.py -q
```

Expected: FAIL until metadata/review/experiment fields are persisted.

**Step 3: Persist guidance metadata**

When creating each sample project, write:

```python
manifest.setdefault("settings", {})
manifest["settings"]["sample_project"] = {
    "order": spec["order"],
    "slug": spec["slug"],
    "difficulty": spec["difficulty"],
    "goal": spec["goal"],
    "guided_steps": deepcopy(spec["guided_steps"]),
    "covered_nodes": deepcopy(spec["covered_nodes"]),
    "covered_settings": deepcopy(spec["covered_settings"]),
    "default_row_count": spec["default_row_count"],
    "public_row_count": row_count,
    "language_balance": deepcopy(spec["language_balance"]),
    "language_counts": {"en": row_count // 2, "zh": row_count // 2},
    "estimated_runtime": spec.get("estimated_runtime", ""),
    "dataset": deepcopy(spec.get("dataset", {})),
}
```

**Step 4: Add review and experiment fixtures**

For sample 05:

- add at least two open review tasks:
  - keyword merge
  - institution merge or document patch
- add one experiment spec with at least two variants:
  - baseline keyword extraction
  - stricter keyword extraction or alternate clustering count

For sample 09:

- add one review task intended for `manual_review_gate`
- set the gate config to reference that review ID after task creation

**Step 5: Run metadata tests**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_projects.py -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add services/python-engine/app/sample_projects.py services/python-engine/tests/test_sample_projects.py
git commit -m "feat: add guidance metadata to scenario samples"
```

## Task 6: Smoke-Test Sample Project Creation and Workflow Runs

**Files:**
- Modify: `services/python-engine/tests/test_sample_projects.py`

**Step 1: Write failing creation/run smoke tests**

Add:

```python
from collections import Counter


def test_create_builtin_sample_projects_creates_all_projects_with_large_defaults(monkeypatch, isolated_workspace):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "150")
    created = create_builtin_sample_projects()
    assert len(created) == 9
    for project_dir, manifest in created:
        _manifest, corpus = load_project(project_dir)
        assert len(corpus) >= 150
        assert manifest["settings"]["sample_project"]["default_row_count"] >= 10_000
        assert Counter(row["language"] for row in corpus) == {"en": len(corpus) // 2, "zh": len(corpus) // 2}
        assert all(row["language"] in {"en", "zh"} for row in corpus)
```

Add a run smoke test for representative scenarios:

```python
@pytest.mark.parametrize("sample_name", [
    "示例 01 - 基础文本预处理",
    "示例 03 - 学术摘要关键词与主题",
    "示例 06 - 多来源语料合并与抽样",
    "示例 07 - 分组比较与关键性分析",
    "示例 09 - 条件路由与人工门禁",
])
def test_representative_sample_workflows_run(monkeypatch, isolated_workspace, sample_name):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "120")
    created = create_builtin_sample_projects()
    project_dir, manifest = next(item for item in created if item[1]["name"] == sample_name)
    manifest, corpus = load_project(project_dir)
    manifest, corpus, run = run_project_workflow(project_dir, manifest, corpus)
    assert run["status"] == "completed"
    assert run["artifacts"]
```

**Step 2: Run tests to verify they fail if any workflow is not executable**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_projects.py -q
```

Expected: FAIL until all representative workflows run.

**Step 3: Fix sample workflows minimally**

If any sample workflow fails:

- inspect the failing node/edge
- adjust only sample workflow wiring/config
- do not weaken runtime validation
- if a runtime bug is uncovered, add a focused regression test before fixing runtime code

**Step 4: Run targeted sample tests**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_dataset_sources.py services\python-engine\tests\test_sample_dataset_cache.py services\python-engine\tests\test_sample_projects.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/python-engine/tests/test_sample_projects.py services/python-engine/app/sample_projects.py
git commit -m "test: cover scenario sample project creation"
```

## Task 7: Update Example Documentation

**Files:**
- Create: `docs/examples.md`
- Modify: `README.md`
- Modify: `docs/current-status.md`
- Modify: `docs/product-scope.md`
- Modify: `docs/development.md`

**Step 1: Write docs**

Create `docs/examples.md` with:

- why samples are large
- which real public datasets power each sample
- each sample's exact English/Chinese row split
- how public source rows are downloaded, normalized, cached, and attributed
- how `language` is detected or taken from source metadata
- list of all nine samples
- what each sample teaches
- which output to open first
- expected runtime level
- warning that sample text is real public data and may contain noisy or historically dated language from the source datasets
- note that frontend `demoProject.ts` is only mock/test fallback

**Step 2: Update README**

Add a short section:

```markdown
## Built-In Scenario Samples

On first launch, TextFlow creates nine backend-built sample projects from real public datasets. Each official sample has at least 10,000 public-source documents, split exactly 1:1 between English and Chinese rows, and demonstrates a real workflow scenario from preprocessing to advanced gates.

See `docs/examples.md`.
```

**Step 3: Update status/scope/development docs**

Update:

- `docs/current-status.md`: sample projects are now scenario-based large projects backed by real public datasets with 1:1 English/Chinese rows.
- `docs/product-scope.md`: sample projects cover V1 features and advanced workflow surfaces.
- `docs/development.md`: document `TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT` for tests/dev and require even row counts to preserve language balance.

**Step 4: Run markdown sanity checks**

Run:

```powershell
git diff --check -- README.md docs/examples.md docs/current-status.md docs/product-scope.md docs/development.md
```

Expected: no trailing whitespace.

**Step 5: Commit**

```bash
git add docs/examples.md README.md docs/current-status.md docs/product-scope.md docs/development.md
git commit -m "docs: add scenario sample project guide"
```

## Task 8: Clarify Frontend Mock Data Boundary

**Files:**
- Modify: `apps/desktop/src/data/demoProject.ts`
- Modify: `apps/desktop/src/bridge/desktopBridge.ts`

**Step 1: Add explanatory comments only**

At the top of `demoProject.ts`, add a concise comment:

```ts
// This file is a lightweight non-Tauri fallback and component-test fixture.
// Official built-in sample projects are created by the Python sidecar in
// services/python-engine/app/sample_projects.py.
// Do not mirror large public sample corpora here.
```

Near the `demoWorkspace` fallback use in `desktopBridge.ts`, add a concise comment:

```ts
// Browser-only fallback: normal desktop builds use the Tauri/Python sidecar.
```

Do not add 10,000-row frontend mock data.

**Step 2: Run frontend tests and lint**

Because TypeScript files changed, run:

```powershell
npm run test --workspace apps/desktop
npm run lint
```

Expected: PASS.

**Step 3: Commit**

```bash
git add apps/desktop/src/data/demoProject.ts apps/desktop/src/bridge/desktopBridge.ts
git commit -m "docs: clarify frontend demo data boundary"
```

## Task 9: Full Engine Verification

**Files:**
- No planned source edits unless verification uncovers bugs.

**Step 1: Run targeted sample tests**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_dataset_sources.py services\python-engine\tests\test_sample_dataset_cache.py services\python-engine\tests\test_sample_projects.py -q
```

Expected: PASS.

**Step 2: Run full engine tests**

Run:

```powershell
npm run test:engine
```

Expected: PASS.

**Step 3: If TypeScript changed, verify frontend again**

Run:

```powershell
npm run test --workspace apps/desktop
npm run lint
```

Expected: PASS.

**Step 4: Optional bootstrap smoke test with isolated workspace**

Run:

```powershell
$env:TEXTFLOW_WORKSPACE_ROOT = Join-Path $env:TEMP ("textflow-samples-" + [guid]::NewGuid().ToString("N"))
$env:TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT = "300"
@'
from app.cli import action_load_workspace
snapshot = action_load_workspace()
print(len(snapshot["recent_projects"]))
print(snapshot["current_project"]["name"])
'@ | .\services\python-engine\.venv\Scripts\python.exe -
```

Expected:

- first printed value is at least `9`
- current project is `示例 01 - 基础文本预处理`

**Step 5: Commit only if verification required fixes**

If no fixes were needed, do not create an empty commit.

## Task 10: Final Packaging Verification

**Files:**
- No planned source edits unless packaging uncovers bugs.

**Step 1: Run app build**

Run:

```powershell
npm run build
```

Expected: PASS.

**Step 2: Run Tauri build**

Run:

```powershell
npm run tauri:build --workspace apps/desktop
```

Expected: PASS and produce:

```text
apps/desktop/src-tauri/target/release/bundle/nsis/TextFlow Studio_0.1.0_x64-setup.exe
```

**Step 3: Launch packaged binary smoke test**

Run:

```powershell
$exe = Resolve-Path "apps\desktop\src-tauri\target\release\textflow-desktop.exe"
$workdir = Split-Path $exe
$p = Start-Process -FilePath $exe -WorkingDirectory $workdir -PassThru
Start-Sleep -Seconds 8
$alive = -not $p.HasExited
[PSCustomObject]@{ ProcessId = $p.Id; AliveAfter8Seconds = $alive; ExitCode = if ($p.HasExited) { $p.ExitCode } else { $null } }
if ($alive) { Stop-Process -Id $p.Id -Force }
```

Expected: `AliveAfter8Seconds` is `True`.

**Step 4: Update docs only if output path or behavior changed**

If packaging output path changes, update `docs/development.md`.

**Step 5: Commit only if docs or packaging fixes were needed**

If no fixes were needed, do not create an empty commit.

## Done Definition

The work is done when:

- first-launch backend bootstrap creates nine sample projects
- all nine samples are visible as normal projects; no frontend hiding or special filtering
- every official sample defaults to at least `10_000` real public-source rows
- every official sample has exactly 50% English rows and 50% Chinese rows
- every sample row has `language` set to `en` or `zh`
- no sample text or metadata is synthetic
- every sample row keeps dataset attribution and source record metadata where available
- packaged builds can create sample projects offline from the bundled/cache public-data subset
- every non-legacy node appears in at least one sample workflow
- sample 05 includes review and experiment surfaces
- sample 09 includes controlled flow primitives
- docs explain which sample to open for each real task
- frontend mock data is explicitly documented as mock/fallback only
- targeted sample tests pass
- full engine tests pass
- TypeScript tests/lint pass if TS comments or UI metadata are changed
- packaging still builds and produces a Windows installer

## Handoff Prompt

Open a new Codex session in this repository and paste:

```text
请严格按照 docs/plans/2026-04-24-textflow-scenario-sample-projects.md 执行，不要重写计划，不要再拆分阶段。按文档中的任务顺序逐个实现，每完成一个任务就：
1. 跑文档里指定的定向测试
2. 如果改了 TypeScript，再跑 npm run test --workspace apps/desktop 和 npm run lint
3. 简短汇报当前任务完成情况和下一任务
4. 不要跳过文档、测试、样例创建和打包验证

如果发现计划中的文件路径需要微调，可以做最小必要调整，但必须先说明原因，再继续执行。
```
