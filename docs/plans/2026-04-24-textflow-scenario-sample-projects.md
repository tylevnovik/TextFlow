# TextFlow Scenario Sample Projects Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task.

**Goal:** Replace the current small capability-demo samples with nine deterministic, large, scenario-based built-in sample projects that teach real TextFlow workflows and cover nearly all non-legacy nodes and settings.

**Architecture:** Built-in sample projects must remain backend-owned. The Python sidecar generates deterministic sample corpora at workspace bootstrap, writes normal `.tfproj` projects, and stores scenario guidance in project `settings.sample_project`. The frontend static `demoProject.ts` remains only a non-Tauri fallback/test fixture and must not become the source of real sample data.

**Tech Stack:** Python 3.11 sidecar, pandas/openpyxl for generated sample files, existing TextFlow project store/workflow runtime, pytest for engine tests, Markdown docs.

---

## Non-Negotiable Decisions

- Create all nine sample projects during backend workspace bootstrap; do not hide advanced samples by default.
- Each official sample project must have a default generated corpus size of at least `10_000` documents.
- Do not commit large generated CSV/XLSX/JSON data to the repository.
- Use deterministic generators with fixed seeds so generated samples are reproducible.
- Keep normal Tauri app behavior backend-driven through Python sidecar projects.
- Do not bulk-expand `apps/desktop/src/data/demoProject.ts`; it is only a mock/test fixture.
- Do not teach or cover legacy nodes: `load_project_corpus`, `filter_corpus`, `project_dictionary_set`, `analyze_corpus`, `export_results`.
- If a sample needs faster development/test generation, use an environment override such as `TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT`; production defaults must stay at `>= 10_000`.

## Target Sample Projects

| Order | Sample Project | Default Rows | Primary User Question |
| --- | --- | ---: | --- |
| 01 | `示例 01 - 基础文本预处理` | 20,000 | “我有一批杂乱文本，如何清洗、标准化、切词并导出？” |
| 02 | `示例 02 - 词表治理与词频统计` | 10,000 | “如何保留行业术语、统一同义词、过滤噪声并看高频词？” |
| 03 | `示例 03 - 学术摘要关键词与主题` | 10,000 | “如何从论文摘要中找关键词、主题和时间趋势？” |
| 04 | `示例 04 - 机构主题与技术方向` | 10,000 | “如何比较机构、关键词和主题之间的关系？” |
| 05 | `示例 05 - 复核实验与增量运行` | 10,000 | “如何复核结果、调参比较，并只重跑变更文档？” |
| 06 | `示例 06 - 多来源语料合并与抽样` | 10,000 | “如何合并 CSV/XLSX/JSON/TXT，多来源去重和抽样？” |
| 07 | `示例 07 - 分组比较与关键性分析` | 10,000 | “如何比较不同时间、机构或产品线的关键词差异？” |
| 08 | `示例 08 - 切分评估与结果拼接` | 10,000 | “如何切分语料、建模、评估聚类并拼接结果？” |
| 09 | `示例 09 - 条件路由与人工门禁` | 10,000 | “如何用条件、指标门禁和人工复核控制工作流？” |

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

## Task 1: Add Deterministic Large Sample Data Generators

**Files:**
- Create: `services/python-engine/app/sample_dataset_generators.py`
- Create: `services/python-engine/tests/test_sample_dataset_generators.py`

**Step 1: Write failing generator tests**

Add tests:

```python
def test_generators_emit_requested_row_count_and_required_fields():
    rows = generate_preprocessing_rows(250, seed=11)
    assert len(rows) == 250
    assert {"doc_id", "title", "raw_text", "year", "source", "institution", "category_or_tag", "keyword_field"} <= rows[0].keys()


def test_generators_are_deterministic():
    assert generate_academic_rows(25, seed=7) == generate_academic_rows(25, seed=7)
```

Also test all public generators:

```python
ALL_GENERATORS = [
    generate_preprocessing_rows,
    generate_feedback_dictionary_rows,
    generate_academic_rows,
    generate_institution_topic_rows,
    generate_review_experiment_rows,
    generate_multisource_rows,
    generate_group_compare_rows,
    generate_split_join_rows,
    generate_gate_control_rows,
]
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_dataset_generators.py -q
```

Expected: FAIL because `sample_dataset_generators.py` does not exist.

**Step 3: Implement generator module**

Create deterministic generator helpers:

```python
from __future__ import annotations

from random import Random
from typing import Any, Callable

Row = dict[str, Any]


def _row(
    *,
    doc_id: str,
    title: str,
    raw_text: str,
    year: int,
    source: str,
    institution: str,
    category_or_tag: str,
    keyword_field: str,
    source_profile: str = "generic",
    extra_metadata: dict[str, Any] | None = None,
) -> Row:
    return {
        "doc_id": doc_id,
        "title": title,
        "raw_text": raw_text,
        "year": year,
        "source": source,
        "author": "",
        "institution": institution,
        "country_or_region": "CN",
        "category_or_tag": category_or_tag,
        "keyword_field": keyword_field,
        "source_profile": source_profile,
        "extra_metadata": extra_metadata or {},
    }
```

Implement each generator by cycling domain-specific templates with `Random(seed)` variation. Keep text realistic enough to produce meaningful tokens and metadata distributions:

- `generate_preprocessing_rows(count: int, seed: int = 101)`
- `generate_feedback_dictionary_rows(count: int, seed: int = 102)`
- `generate_academic_rows(count: int, seed: int = 103)`
- `generate_institution_topic_rows(count: int, seed: int = 104)`
- `generate_review_experiment_rows(count: int, seed: int = 105)`
- `generate_multisource_rows(count: int, seed: int = 106)`
- `generate_group_compare_rows(count: int, seed: int = 107)`
- `generate_split_join_rows(count: int, seed: int = 108)`
- `generate_gate_control_rows(count: int, seed: int = 109)`

Use content families such as:

- customer feedback / app reviews
- literature abstracts
- patents and technology intelligence
- institution research portfolios
- product lines and time periods
- quality gate metrics

**Step 4: Run tests to verify they pass**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_dataset_generators.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/python-engine/app/sample_dataset_generators.py services/python-engine/tests/test_sample_dataset_generators.py
git commit -m "feat: add deterministic large sample data generators"
```

## Task 2: Refactor Built-In Sample Project Specs

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


def test_builtin_sample_specs_include_guidance_and_coverage():
    for spec in BUILTIN_SAMPLE_PROJECTS:
        assert spec["goal"]
        assert spec["guided_steps"]
        assert spec["covered_nodes"]
        assert spec["difficulty"] in {"基础", "进阶", "高级"}
```

**Step 2: Run tests to verify they fail**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_projects.py -q
```

Expected: FAIL because current specs are only three small samples.

**Step 3: Add scenario spec structure**

In `sample_projects.py`, replace the current row lists with generator-backed specs. Keep `FIRST_BUILTIN_SAMPLE_PROJECT_NAME`, but update it to:

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
    "source_profile": "generic",
    "sources": [
        {"filename": "basic_preprocessing.csv", "format": "csv", "generator": generate_preprocessing_rows, "ratio": 1.0},
    ],
    "workflow_name": "...",
    "import_template_overrides": {...},
    "node_config_overrides": {...},
    "dictionary_terms": {...},
    "review_tasks": [],
    "experiment_specs": [],
}
```

**Step 4: Add row limit helper**

Add:

```python
def _sample_row_count(spec: dict[str, Any]) -> int:
    override = os.getenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT")
    if override:
        return max(1, int(override))
    return int(spec.get("default_row_count") or 10_000)
```

Use this only at generation time. Do not lower `default_row_count`.

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

## Task 3: Build Scenario-Specific Workflows

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

Use `build_node_registry().definitions_by_type` to copy inputs/outputs from node definitions.

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

## Task 4: Add Project Guidance Metadata, Reviews, and Experiments

**Files:**
- Modify: `services/python-engine/app/sample_projects.py`
- Modify: `services/python-engine/tests/test_sample_projects.py`

**Step 1: Write failing metadata tests**

Add:

```python
def test_generated_sample_projects_persist_guidance_metadata(monkeypatch, isolated_workspace):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "120")
    created = create_builtin_sample_projects()
    for _project_dir, manifest in created:
        sample = manifest["settings"]["sample_project"]
        assert sample["order"] >= 1
        assert sample["difficulty"]
        assert sample["goal"]
        assert sample["guided_steps"]
        assert sample["default_row_count"] >= 10_000
        assert sample["generated_row_count"] == 120
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

Expected: FAIL until metadata/review/experiment fields are generated.

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
    "generated_row_count": row_count,
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

## Task 5: Smoke-Test Sample Project Generation and Workflow Runs

**Files:**
- Modify: `services/python-engine/tests/test_sample_projects.py`

**Step 1: Write failing generation/run smoke tests**

Add:

```python
def test_create_builtin_sample_projects_generates_all_projects_with_large_defaults(monkeypatch, isolated_workspace):
    monkeypatch.setenv("TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT", "150")
    created = create_builtin_sample_projects()
    assert len(created) == 9
    for project_dir, manifest in created:
        _manifest, corpus = load_project(project_dir)
        assert len(corpus) >= 150
        assert manifest["settings"]["sample_project"]["default_row_count"] >= 10_000
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
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_dataset_generators.py services\python-engine\tests\test_sample_projects.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/python-engine/tests/test_sample_projects.py services/python-engine/app/sample_projects.py
git commit -m "test: cover scenario sample project generation"
```

## Task 6: Update Example Documentation

**Files:**
- Create: `docs/examples.md`
- Modify: `README.md`
- Modify: `docs/current-status.md`
- Modify: `docs/product-scope.md`
- Modify: `docs/development.md`

**Step 1: Write docs**

Create `docs/examples.md` with:

- why samples are large
- how samples are generated
- list of all nine samples
- what each sample teaches
- which output to open first
- expected runtime level
- warning that generated sample data is synthetic/deterministic
- note that frontend `demoProject.ts` is only mock/test fallback

**Step 2: Update README**

Add a short section:

```markdown
## Built-In Scenario Samples

On first launch, TextFlow creates nine backend-generated sample projects. Each official sample has at least 10,000 generated documents and demonstrates a real workflow scenario from preprocessing to advanced gates.

See `docs/examples.md`.
```

**Step 3: Update status/scope/development docs**

Update:

- `docs/current-status.md`: sample projects are now scenario-based large generated projects.
- `docs/product-scope.md`: sample projects cover V1 features and advanced workflow surfaces.
- `docs/development.md`: document `TEXTFLOW_SAMPLE_PROJECT_ROW_LIMIT` for tests/dev.

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

## Task 7: Clarify Frontend Mock Data Boundary

**Files:**
- Modify: `apps/desktop/src/data/demoProject.ts`
- Modify: `apps/desktop/src/bridge/desktopBridge.ts`

**Step 1: Add explanatory comments only**

At the top of `demoProject.ts`, add a concise comment:

```ts
// This file is a lightweight non-Tauri fallback and component-test fixture.
// Official built-in sample projects are generated by the Python sidecar in
// services/python-engine/app/sample_projects.py.
// Do not mirror large generated sample corpora here.
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

## Task 8: Full Engine Verification

**Files:**
- No planned source edits unless verification uncovers bugs.

**Step 1: Run targeted sample tests**

Run:

```powershell
& .\services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_dataset_generators.py services\python-engine\tests\test_sample_projects.py -q
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

## Task 9: Final Packaging Verification

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
- every official sample defaults to at least `10_000` generated rows
- generated sample data is deterministic and not committed as bulk data
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
4. 不要跳过文档、测试、样例生成和打包验证

如果发现计划中的文件路径需要微调，可以做最小必要调整，但必须先说明原因，再继续执行。
```
