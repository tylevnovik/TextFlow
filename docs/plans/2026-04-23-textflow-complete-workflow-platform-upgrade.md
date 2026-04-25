# TextFlow Complete Workflow Platform Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete resource-aware, artifact-backed, reviewable, experiment-capable TextFlow that supports advanced corpus selection, comparison, human-in-the-loop correction, run diff, and incremental updates without breaking offline desktop packaging.

**Architecture:** Keep deterministic preprocessing and analysis inside the native DAG, but promote corpus views, dictionary overlays, artifacts, review tasks, and experiment specs to first-class project records. Runtime should emit artifact handles and previews instead of giant inline payloads; frontend should load previews lazily, expose review and experiment workflows as product features, and keep graph orchestration focused on reproducible dataflow instead of becoming a general-purpose workflow engine.

**Tech Stack:** Tauri 2, React 18, TypeScript, Python 3.11, pandas, scikit-learn, Pytest, Vitest, shared TS domain types

---

## Execution Rules

- Execute tasks strictly in the order listed below.
- Do not split this into separate milestone plans; this file is the single integrated backlog.
- Keep all schema changes backward-compatible with existing `.tfproj` projects.
- Prefer creating new modules over growing `screens.tsx` and `cli.py` further.
- After every task: run the targeted tests, run `npm run lint` if TypeScript files changed, update docs if behavior changed, and commit.

## Global Acceptance Criteria

- Existing `npm run lint` still passes.
- Existing `npm run test:engine` still passes.
- New backend modules each have dedicated tests.
- New frontend store/components have at least reducer/component tests under Vitest.
- Existing sample projects still open.
- Old projects without new fields still auto-normalize successfully.
- New project state remains portable and bundle-safe for Windows installer packaging.
- Large-run workflows no longer require inline materialization of all intermediate results in the manifest.

### Task 1: Write the Architecture Record and Add Frontend Test Harness

**Files:**
- Create: `docs/adr/2026-04-23-resource-artifact-review-experiment-architecture.md`
- Modify: `apps/desktop/package.json`
- Create: `apps/desktop/vitest.config.ts`
- Create: `apps/desktop/src/test/setup.ts`
- Create: `apps/desktop/src/store/workspaceStore.test.ts`

**Step 1: Write the failing frontend smoke test**

```ts
import { describe, expect, it } from "vitest";

describe("workspace store test harness", () => {
  it("loads the reducer module", async () => {
    const mod = await import("./workspaceStore");
    expect(mod).toBeTruthy();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `npm run test --workspace apps/desktop`
Expected: FAIL because Vitest is not installed or configured.

**Step 3: Add Vitest + RTL setup**

Add dev dependencies and scripts in `apps/desktop/package.json`:

```json
{
  "scripts": {
    "test": "vitest run"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "...",
    "@testing-library/react": "...",
    "jsdom": "...",
    "vitest": "..."
  }
}
```

**Step 4: Add ADR**

Record these decisions in `docs/adr/2026-04-23-resource-artifact-review-experiment-architecture.md`:

- deterministic transforms stay in DAG nodes
- resources/reviews/experiments become project records
- runtime outputs artifact handles
- loops stay out of the graph; parameter sweep belongs to experiment layer
- branching is allowed only through explicit router/gate nodes

**Step 5: Run verification**

Run: `npm run test --workspace apps/desktop`
Expected: PASS

Run: `npm run lint`
Expected: PASS

**Step 6: Commit**

```bash
git add docs/adr/2026-04-23-resource-artifact-review-experiment-architecture.md apps/desktop/package.json apps/desktop/vitest.config.ts apps/desktop/src/test/setup.ts apps/desktop/src/store/workspaceStore.test.ts package-lock.json
git commit -m "test: add frontend harness for workflow platform upgrade"
```

### Task 2: Expand Shared Domain Types and Project Schema

**Files:**
- Modify: `packages/shared-types/src/index.ts`
- Modify: `services/python-engine/app/defaults.py`
- Modify: `services/python-engine/app/project_store.py`
- Create: `services/python-engine/tests/test_project_resources.py`
- Modify: `services/python-engine/tests/test_workspace_cli.py`

**Step 1: Write the failing schema tests**

```python
def test_default_project_manifest_contains_resource_collections():
    project_dir, manifest = create_project("schema", "schema")
    assert manifest["corpus_resources"] == []
    assert manifest["corpus_views"] == []
    assert manifest["artifact_records"] == []
    assert manifest["review_tasks"] == []
    assert manifest["experiment_specs"] == []


def test_legacy_project_load_backfills_new_fields(tmp_path):
    manifest = {"id": "project-1", "name": "legacy", "description": ""}
    # write minimal legacy project files here
    normalized, _ = load_project(project_dir)
    assert "corpus_views" in normalized
```

**Step 2: Run tests to verify they fail**

Run: `pytest services/python-engine/tests/test_project_resources.py -v`
Expected: FAIL because the new collections do not exist.

**Step 3: Add shared types**

Add TS and Python-compatible shapes for:

```ts
type CorpusResource = { id: string; name: string; source_files: string[]; fingerprint: string };
type CorpusView = { id: string; name: string; resource_ids: string[]; filter_spec: Record<string, unknown>; doc_ids?: string[] };
type IngestionSpec = { id: string; name: string; source_profile: string; field_mappings: unknown[]; text_build: Record<string, unknown>; dedupe_rules: Record<string, unknown> };
type ArtifactRecord = { artifact_id: string; run_id: string; node_id: string; kind: string; path: string; preview_path?: string; row_count?: number };
type ReviewTask = { review_id: string; project_id: string; review_type: string; status: "open" | "resolved"; target_ref: Record<string, string> };
type ExperimentSpec = { experiment_id: string; name: string; workflow_id: string; variant_matrix: Record<string, unknown>[] };
```

**Step 4: Add manifest defaults and normalization**

Backfill these manifest fields in `default_project_manifest()` and `normalize_project_manifest()`:

- `corpus_resources`
- `corpus_views`
- `ingestion_specs`
- `artifact_records`
- `review_tasks`
- `experiment_specs`
- `shared_resource_refs`

**Step 5: Run verification**

Run: `pytest services/python-engine/tests/test_project_resources.py services/python-engine/tests/test_workspace_cli.py -q`
Expected: PASS

Run: `npm run lint`
Expected: PASS

**Step 6: Commit**

```bash
git add packages/shared-types/src/index.ts services/python-engine/app/defaults.py services/python-engine/app/project_store.py services/python-engine/tests/test_project_resources.py services/python-engine/tests/test_workspace_cli.py
git commit -m "feat: add shared schema for resources artifacts reviews and experiments"
```

### Task 3: Implement Resource Store and Versioned Ingestion Specs

**Files:**
- Create: `services/python-engine/app/resource_store.py`
- Create: `services/python-engine/app/ingestion_specs.py`
- Modify: `services/python-engine/app/cli.py`
- Modify: `services/python-engine/app/ingestion.py`
- Modify: `services/python-engine/app/project_store.py`
- Create: `services/python-engine/tests/test_resource_store.py`
- Create: `services/python-engine/tests/test_ingestion_specs.py`

**Step 1: Write failing backend tests**

```python
def test_create_corpus_view_persists_filter_spec():
    created = action_create_corpus_view({...})
    assert created["filter_spec"]["institution"] == ["OpenAI"]


def test_saved_ingestion_spec_has_stable_hash():
    spec = save_ingestion_spec(...)
    assert spec["spec_hash"].startswith("sha256:")
```

**Step 2: Run tests to verify they fail**

Run: `pytest services/python-engine/tests/test_resource_store.py services/python-engine/tests/test_ingestion_specs.py -v`
Expected: FAIL because commands and storage helpers do not exist.

**Step 3: Implement resource store**

Create helpers:

```python
def create_corpus_view(project_dir: Path, manifest: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]: ...
def update_corpus_view(...)
def delete_corpus_view(...)
def resolve_corpus_view(manifest: dict[str, Any], corpus: list[dict[str, Any]], view_id: str) -> list[dict[str, Any]]: ...
```

Persist resource records under project metadata:

- `metadata/corpus_views.json`
- `metadata/ingestion_specs.json`

**Step 4: Implement versioned ingestion specs**

Store:

- field mappings
- text build strategy
- dedupe rules
- metadata normalization rules
- spec hash

Expose CLI actions:

- `save_ingestion_spec`
- `list_ingestion_specs`
- `create_corpus_view`
- `update_corpus_view`
- `delete_corpus_view`

**Step 5: Run verification**

Run: `pytest services/python-engine/tests/test_resource_store.py services/python-engine/tests/test_ingestion_specs.py -q`
Expected: PASS

Run: `pytest services/python-engine/tests/test_workspace_cli.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add services/python-engine/app/resource_store.py services/python-engine/app/ingestion_specs.py services/python-engine/app/cli.py services/python-engine/app/ingestion.py services/python-engine/app/project_store.py services/python-engine/tests/test_resource_store.py services/python-engine/tests/test_ingestion_specs.py
git commit -m "feat: add corpus views and versioned ingestion specs"
```

### Task 4: Add Artifact Store and Artifact-Handle Runtime Outputs

**Files:**
- Create: `services/python-engine/app/artifact_store.py`
- Modify: `services/python-engine/app/dag_runtime.py`
- Modify: `services/python-engine/app/runtime_support.py`
- Modify: `services/python-engine/app/reporting.py`
- Modify: `services/python-engine/app/workflow_runner.py`
- Modify: `services/python-engine/app/cli.py`
- Create: `services/python-engine/tests/test_artifact_store.py`
- Modify: `services/python-engine/tests/test_workflow_runner.py`

**Step 1: Write failing tests**

```python
def test_large_node_output_is_registered_as_artifact(tmp_path):
    run_record = run_project_workflow(...)
    assert run_record["artifacts"]
    assert any(item["kind"] == "table" for item in run_record["artifacts"])


def test_artifact_preview_loads_without_materializing_full_payload():
    preview = load_artifact_preview(project_dir, artifact_id)
    assert "rows" in preview
```

**Step 2: Run tests to verify they fail**

Run: `pytest services/python-engine/tests/test_artifact_store.py services/python-engine/tests/test_workflow_runner.py -q`
Expected: FAIL

**Step 3: Implement artifact store**

Create:

```python
def write_artifact(project_dir: Path, run_id: str, node_id: str, kind: str, payload: Any) -> dict[str, Any]: ...
def load_artifact_preview(project_dir: Path, artifact_id: str, limit: int = 50) -> dict[str, Any]: ...
def load_artifact_payload(project_dir: Path, artifact_id: str) -> Any: ...
```

Write artifacts under:

- `runs/<run_id>/artifacts/<artifact_id>.json`
- `runs/<run_id>/artifacts/<artifact_id>.preview.json`

**Step 4: Change runtime output contract**

For large outputs, store:

```python
{
    "artifact_id": "...",
    "kind": "table",
    "row_count": 1234,
    "preview_rows": 20
}
```

Keep small scalar summaries inline so the UI still renders quick status text.

**Step 5: Add CLI preview commands**

- `load_artifact_preview`
- `load_artifact_payload`
- `list_run_artifacts`

**Step 6: Run verification**

Run: `pytest services/python-engine/tests/test_artifact_store.py services/python-engine/tests/test_workflow_runner.py -q`
Expected: PASS

Run: `npm run test:engine`
Expected: PASS

**Step 7: Commit**

```bash
git add services/python-engine/app/artifact_store.py services/python-engine/app/dag_runtime.py services/python-engine/app/runtime_support.py services/python-engine/app/reporting.py services/python-engine/app/workflow_runner.py services/python-engine/app/cli.py services/python-engine/tests/test_artifact_store.py services/python-engine/tests/test_workflow_runner.py
git commit -m "feat: add artifact-backed runtime outputs"
```

### Task 5: Add Corpus Selection, Dedupe, Sampling, Splitting, and Time-Bucketing Nodes

**Files:**
- Modify: `services/python-engine/app/node_definitions.py`
- Modify: `services/python-engine/app/node_compilers.py`
- Modify: `services/python-engine/app/node_executors.py`
- Modify: `services/python-engine/tests/test_node_catalog_parity.py`
- Modify: `services/python-engine/tests/test_workflow_runner.py`
- Modify: `apps/desktop/src/workflowNodeCatalog.ts`
- Modify: `apps/desktop/src/workflowNodeCompilers.ts`
- Modify: `apps/desktop/src/workflowNodeRegistry.tsx`

**Step 1: Write failing workflow tests**

```python
def test_filter_by_metadata_node_restricts_documents(): ...
def test_deduplicate_documents_node_keeps_single_copy(): ...
def test_sample_corpus_node_is_seeded_and_reproducible(): ...
def test_split_corpus_node_creates_named_views(): ...
def test_bucket_by_time_node_emits_time_bucket_assignments(): ...
```

**Step 2: Run tests to verify they fail**

Run: `pytest services/python-engine/tests/test_workflow_runner.py -k "metadata or deduplicate or sample or split or bucket" -q`
Expected: FAIL

**Step 3: Add node definitions**

Add nodes:

- `filter_by_metadata`
- `deduplicate_documents`
- `sample_corpus`
- `split_corpus`
- `bucket_by_time`

Use explicit config like:

```python
{"field": "institution", "operator": "in", "values": ["OpenAI"]}
{"dedupe_keys": ["title", "year"], "strategy": "keep_first"}
{"sample_mode": "random", "sample_size": 200, "seed": 42}
```

**Step 4: Implement executors**

Keep outputs deterministic and cacheable. `split_corpus` should return named view assignments instead of duplicating data repeatedly.

**Step 5: Update frontend node registry**

Expose form controls for:

- metadata condition lists
- dedupe key arrays
- sample size / ratio / seed
- split strategy
- time bucket granularity

**Step 6: Run verification**

Run: `pytest services/python-engine/tests/test_workflow_runner.py -q`
Expected: PASS

Run: `npm run lint`
Expected: PASS

**Step 7: Commit**

```bash
git add services/python-engine/app/node_definitions.py services/python-engine/app/node_compilers.py services/python-engine/app/node_executors.py services/python-engine/tests/test_node_catalog_parity.py services/python-engine/tests/test_workflow_runner.py apps/desktop/src/workflowNodeCatalog.ts apps/desktop/src/workflowNodeCompilers.ts apps/desktop/src/workflowNodeRegistry.tsx
git commit -m "feat: add corpus selection and splitting nodes"
```

### Task 6: Add Dictionary Selection, Overlay, Group Comparison, and Keyness Nodes

**Files:**
- Modify: `services/python-engine/app/node_definitions.py`
- Modify: `services/python-engine/app/node_compilers.py`
- Modify: `services/python-engine/app/node_executors.py`
- Create: `services/python-engine/tests/test_comparison_nodes.py`
- Modify: `apps/desktop/src/workflowNodeCatalog.ts`
- Modify: `apps/desktop/src/workflowNodeCompilers.ts`
- Modify: `apps/desktop/src/workflowNodeRegistry.tsx`

**Step 1: Write failing tests**

```python
def test_select_dictionary_tables_node_limits_active_tables(): ...
def test_overlay_dictionary_rules_node_applies_runtime_only_patch(): ...
def test_group_compare_node_emits_group_metric_table(): ...
def test_keyness_analysis_node_emits_llr_and_ratio_columns(): ...
```

**Step 2: Run tests to verify they fail**

Run: `pytest services/python-engine/tests/test_comparison_nodes.py -q`
Expected: FAIL

**Step 3: Add nodes**

Add:

- `select_dictionary_tables`
- `overlay_dictionary_rules`
- `group_compare`
- `keyness_analysis`

`group_compare` should accept:

```python
{"group_field": "institution", "baseline_group": "OpenAI", "comparison_groups": ["Anthropic", "Google"]}
```

**Step 4: Implement backend**

- `select_dictionary_tables` should emit a filtered `DictionarySet`
- `overlay_dictionary_rules` should apply ephemeral rule patches without mutating project defaults
- `group_compare` should compute per-group counts / normalized frequencies
- `keyness_analysis` should compute LLR, relative ratio, and support min-frequency thresholds

**Step 5: Update frontend node forms**

Add structured editors for:

- dictionary table selection
- runtime overlay rows
- comparison group pickers
- significance settings

**Step 6: Run verification**

Run: `pytest services/python-engine/tests/test_comparison_nodes.py services/python-engine/tests/test_workflow_runner.py -q`
Expected: PASS

Run: `npm run lint`
Expected: PASS

**Step 7: Commit**

```bash
git add services/python-engine/app/node_definitions.py services/python-engine/app/node_compilers.py services/python-engine/app/node_executors.py services/python-engine/tests/test_comparison_nodes.py apps/desktop/src/workflowNodeCatalog.ts apps/desktop/src/workflowNodeCompilers.ts apps/desktop/src/workflowNodeRegistry.tsx
git commit -m "feat: add dictionary overlay and comparison nodes"
```

### Task 7: Add Topic Modeling, Cluster Evaluation, and Result Join Nodes

**Files:**
- Modify: `services/python-engine/app/analysis_ops.py`
- Modify: `services/python-engine/app/node_definitions.py`
- Modify: `services/python-engine/app/node_compilers.py`
- Modify: `services/python-engine/app/node_executors.py`
- Create: `services/python-engine/tests/test_modeling_nodes.py`
- Modify: `apps/desktop/src/workflowNodeCatalog.ts`
- Modify: `apps/desktop/src/workflowNodeCompilers.ts`
- Modify: `apps/desktop/src/workflowNodeRegistry.tsx`

**Step 1: Write failing tests**

```python
def test_topic_modeling_node_outputs_topic_term_and_doc_topic_tables(): ...
def test_cluster_evaluation_node_outputs_silhouette_and_cluster_sizes(): ...
def test_join_results_node_merges_tables_on_named_keys(): ...
```

**Step 2: Run tests to verify they fail**

Run: `pytest services/python-engine/tests/test_modeling_nodes.py -q`
Expected: FAIL

**Step 3: Implement topic modeling**

Start with NMF-backed topic modeling and explicit artifact outputs:

- topic-term table
- document-topic table
- topic summary table

Do not add BERTopic or transformer dependencies in core runtime yet; keep that for plugins later.

**Step 4: Implement cluster evaluation**

Compute:

- silhouette score
- Davies-Bouldin score
- cluster size distribution

**Step 5: Implement result join**

Allow controlled table joins:

```python
{"left_artifact": "...", "right_artifact": "...", "join_keys": ["term"], "join_type": "inner"}
```

**Step 6: Run verification**

Run: `pytest services/python-engine/tests/test_modeling_nodes.py services/python-engine/tests/test_workflow_runner.py -q`
Expected: PASS

**Step 7: Commit**

```bash
git add services/python-engine/app/analysis_ops.py services/python-engine/app/node_definitions.py services/python-engine/app/node_compilers.py services/python-engine/app/node_executors.py services/python-engine/tests/test_modeling_nodes.py apps/desktop/src/workflowNodeCatalog.ts apps/desktop/src/workflowNodeCompilers.ts apps/desktop/src/workflowNodeRegistry.tsx
git commit -m "feat: add topic modeling and result evaluation nodes"
```

### Task 8: Implement Review Queue and Write-Back Workflows

**Files:**
- Create: `services/python-engine/app/review_store.py`
- Modify: `services/python-engine/app/cli.py`
- Modify: `services/python-engine/app/project_store.py`
- Create: `services/python-engine/tests/test_review_store.py`
- Create: `apps/desktop/src/features/review/ReviewQueuePanel.tsx`
- Create: `apps/desktop/src/features/review/reviewTypes.ts`
- Create: `apps/desktop/src/features/review/ReviewQueuePanel.test.tsx`
- Modify: `apps/desktop/src/bridge/desktopBridge.ts`
- Modify: `apps/desktop/src/store/workspaceStore.tsx`
- Modify: `apps/desktop/src/screens.tsx`

**Step 1: Write failing tests**

```python
def test_create_review_task_for_keyword_merge(): ...
def test_resolve_review_task_writes_dictionary_overlay(): ...
def test_resolve_review_task_can_patch_corpus_document(): ...
```

```ts
it("renders open review tasks and resolves one", async () => {
  render(<ReviewQueuePanel ... />);
  expect(screen.getByText("Open")).toBeInTheDocument();
});
```

**Step 2: Run tests to verify they fail**

Run: `pytest services/python-engine/tests/test_review_store.py -q`
Expected: FAIL

Run: `npm run test --workspace apps/desktop -- ReviewQueuePanel`
Expected: FAIL

**Step 3: Implement review store**

Add review types:

- `keyword_merge`
- `institution_merge`
- `cluster_rename`
- `document_patch`
- `dictionary_patch`

Expose commands:

- `create_review_task`
- `list_review_tasks`
- `resolve_review_task`
- `apply_review_resolution`

**Step 4: Implement write-back**

Resolution should mutate only:

- project custom dictionary table
- corpus document patch
- cluster label map

Do not mutate built-in dictionaries directly.

**Step 5: Add frontend review queue**

Add queue list, review detail panel, resolve/reject buttons, and refresh local store after resolution.

**Step 6: Run verification**

Run: `pytest services/python-engine/tests/test_review_store.py -q`
Expected: PASS

Run: `npm run test --workspace apps/desktop`
Expected: PASS

Run: `npm run lint`
Expected: PASS

**Step 7: Commit**

```bash
git add services/python-engine/app/review_store.py services/python-engine/app/cli.py services/python-engine/app/project_store.py services/python-engine/tests/test_review_store.py apps/desktop/src/features/review/ReviewQueuePanel.tsx apps/desktop/src/features/review/reviewTypes.ts apps/desktop/src/features/review/ReviewQueuePanel.test.tsx apps/desktop/src/bridge/desktopBridge.ts apps/desktop/src/store/workspaceStore.tsx apps/desktop/src/screens.tsx
git commit -m "feat: add review queue and write-back workflows"
```

### Task 9: Implement Experiment Specs, Parameter Matrix Runs, and Run Diff

**Files:**
- Create: `services/python-engine/app/experiment_store.py`
- Create: `services/python-engine/app/run_diff.py`
- Modify: `services/python-engine/app/cli.py`
- Modify: `services/python-engine/app/workflow_runner.py`
- Create: `services/python-engine/tests/test_experiment_store.py`
- Create: `services/python-engine/tests/test_run_diff.py`
- Create: `apps/desktop/src/features/experiments/ExperimentPanel.tsx`
- Create: `apps/desktop/src/features/experiments/ExperimentPanel.test.tsx`
- Create: `apps/desktop/src/features/results/RunDiffPanel.tsx`
- Modify: `apps/desktop/src/bridge/desktopBridge.ts`
- Modify: `apps/desktop/src/store/workspaceStore.tsx`
- Modify: `apps/desktop/src/screens.tsx`

**Step 1: Write failing tests**

```python
def test_run_experiment_matrix_creates_multiple_runs(): ...
def test_run_diff_compares_artifact_summaries_and_metrics(): ...
```

```ts
it("renders experiment variants and a diff summary", async () => {
  render(<ExperimentPanel ... />);
  expect(screen.getByText("Variants")).toBeInTheDocument();
});
```

**Step 2: Run tests to verify they fail**

Run: `pytest services/python-engine/tests/test_experiment_store.py services/python-engine/tests/test_run_diff.py -q`
Expected: FAIL

**Step 3: Implement experiment store**

Spec shape:

```python
{
    "experiment_id": "exp-...",
    "name": "keyword-method-compare",
    "workflow_id": "...",
    "variant_matrix": [
        {"label": "baseline", "node_overrides": {...}},
        {"label": "high-keywords", "node_overrides": {...}}
    ]
}
```

Expose commands:

- `save_experiment_spec`
- `list_experiment_specs`
- `run_experiment_matrix`

**Step 4: Implement run diff**

Compare:

- runtime profile differences
- node config differences
- artifact row counts
- top terms / top keywords / cluster counts

**Step 5: Add frontend experiment and diff panels**

Features:

- create/edit experiment matrix
- run selected experiment
- open run diff between any two runs

**Step 6: Run verification**

Run: `pytest services/python-engine/tests/test_experiment_store.py services/python-engine/tests/test_run_diff.py -q`
Expected: PASS

Run: `npm run test --workspace apps/desktop`
Expected: PASS

**Step 7: Commit**

```bash
git add services/python-engine/app/experiment_store.py services/python-engine/app/run_diff.py services/python-engine/app/cli.py services/python-engine/app/workflow_runner.py services/python-engine/tests/test_experiment_store.py services/python-engine/tests/test_run_diff.py apps/desktop/src/features/experiments/ExperimentPanel.tsx apps/desktop/src/features/experiments/ExperimentPanel.test.tsx apps/desktop/src/features/results/RunDiffPanel.tsx apps/desktop/src/bridge/desktopBridge.ts apps/desktop/src/store/workspaceStore.tsx apps/desktop/src/screens.tsx
git commit -m "feat: add experiment matrix and run diff support"
```

### Task 10: Implement Incremental Processing, Dirty Propagation, and Artifact Invalidation

**Files:**
- Create: `services/python-engine/app/incremental_runtime.py`
- Modify: `services/python-engine/app/dag_runtime.py`
- Modify: `services/python-engine/app/project_store.py`
- Modify: `services/python-engine/app/cli.py`
- Modify: `services/python-engine/tests/test_workflow_runner.py`
- Create: `services/python-engine/tests/test_incremental_runtime.py`

**Step 1: Write failing tests**

```python
def test_editing_single_document_invalidates_only_dependent_nodes(): ...
def test_incremental_run_processes_new_docs_only_when_requested(): ...
def test_dictionary_overlay_change_invalidates_dictionary_downstream_nodes(): ...
```

**Step 2: Run tests to verify they fail**

Run: `pytest services/python-engine/tests/test_incremental_runtime.py -q`
Expected: FAIL

**Step 3: Implement invalidation graph**

Track:

- input resource fingerprints
- node cache dependencies
- artifact provenance
- changed doc ids

Add helpers:

```python
def compute_dirty_node_ids(workflow_definition, changed_resources, dependency_index): ...
def select_incremental_scope(manifest, payload): ...
```

**Step 4: Add incremental run mode**

Expose CLI payload options:

- `run_mode: "full" | "incremental"`
- `changed_doc_ids`
- `changed_dictionary_tables`

**Step 5: Run verification**

Run: `pytest services/python-engine/tests/test_incremental_runtime.py services/python-engine/tests/test_workflow_runner.py -q`
Expected: PASS

Run: `npm run test:engine`
Expected: PASS

**Step 6: Commit**

```bash
git add services/python-engine/app/incremental_runtime.py services/python-engine/app/dag_runtime.py services/python-engine/app/project_store.py services/python-engine/app/cli.py services/python-engine/tests/test_incremental_runtime.py services/python-engine/tests/test_workflow_runner.py
git commit -m "feat: add incremental runtime and dirty propagation"
```

### Task 11: Add Controlled Graph Flow Primitives Without Turning DAG Into a Scripting Engine

**Files:**
- Modify: `services/python-engine/app/node_definitions.py`
- Modify: `services/python-engine/app/node_compilers.py`
- Modify: `services/python-engine/app/node_executors.py`
- Create: `services/python-engine/tests/test_control_flow_nodes.py`
- Modify: `apps/desktop/src/workflowNodeCatalog.ts`
- Modify: `apps/desktop/src/workflowNodeRegistry.tsx`

**Step 1: Write failing tests**

```python
def test_conditional_router_routes_records_by_predicate(): ...
def test_result_gate_blocks_downstream_when_threshold_not_met(): ...
def test_manual_review_gate_waits_for_resolved_review_task(): ...
```

**Step 2: Run tests to verify they fail**

Run: `pytest services/python-engine/tests/test_control_flow_nodes.py -q`
Expected: FAIL

**Step 3: Add graph nodes**

Add only these primitives:

- `conditional_router`
- `result_gate`
- `manual_review_gate`

Do not add loops or arbitrary scripting.

**Step 4: Implement backend behavior**

- `conditional_router` branches on corpus metadata or comparison result fields
- `result_gate` checks summary metrics from upstream artifacts
- `manual_review_gate` depends on a resolved review task id

**Step 5: Update frontend**

Add guarded config forms with expression builder dropdowns instead of raw code editors.

**Step 6: Run verification**

Run: `pytest services/python-engine/tests/test_control_flow_nodes.py services/python-engine/tests/test_workflow_runner.py -q`
Expected: PASS

Run: `npm run lint`
Expected: PASS

**Step 7: Commit**

```bash
git add services/python-engine/app/node_definitions.py services/python-engine/app/node_compilers.py services/python-engine/app/node_executors.py services/python-engine/tests/test_control_flow_nodes.py apps/desktop/src/workflowNodeCatalog.ts apps/desktop/src/workflowNodeRegistry.tsx
git commit -m "feat: add controlled graph flow primitives"
```

### Task 12: Build the Frontend Resource, Artifact, Review, and Experiment Surfaces

**Files:**
- Create: `apps/desktop/src/features/resources/ResourceBrowser.tsx`
- Create: `apps/desktop/src/features/resources/ResourceBrowser.test.tsx`
- Create: `apps/desktop/src/features/artifacts/ArtifactBrowser.tsx`
- Create: `apps/desktop/src/features/artifacts/ArtifactBrowser.test.tsx`
- Create: `apps/desktop/src/features/results/RunHistoryPanel.tsx`
- Modify: `apps/desktop/src/store/workspaceStore.tsx`
- Modify: `apps/desktop/src/bridge/desktopBridge.ts`
- Modify: `apps/desktop/src/screens.tsx`
- Modify: `apps/desktop/src/ui.tsx`
- Modify: `apps/desktop/src/styles.css`
- Modify: `apps/desktop/src/App.tsx`

**Step 1: Write failing component/store tests**

```ts
it("renders corpus views and can open one");
it("loads artifact preview rows lazily");
it("shows review badges and experiment links in run history");
```

**Step 2: Run tests to verify they fail**

Run: `npm run test --workspace apps/desktop`
Expected: FAIL

**Step 3: Add bridge/store actions**

Add bridge methods for:

- corpus view CRUD
- ingestion spec CRUD
- artifact preview load
- review task list/resolve
- experiment save/run
- run diff load

**Step 4: Build UI**

Add panels:

- Resource browser
- Artifact browser
- Review queue
- Experiment panel
- Run diff panel

Mount them into existing `screens.tsx` without creating a new navigation model yet.

**Step 5: Run verification**

Run: `npm run test --workspace apps/desktop`
Expected: PASS

Run: `npm run lint`
Expected: PASS

**Step 6: Commit**

```bash
git add apps/desktop/src/features/resources/ResourceBrowser.tsx apps/desktop/src/features/resources/ResourceBrowser.test.tsx apps/desktop/src/features/artifacts/ArtifactBrowser.tsx apps/desktop/src/features/artifacts/ArtifactBrowser.test.tsx apps/desktop/src/features/results/RunHistoryPanel.tsx apps/desktop/src/store/workspaceStore.tsx apps/desktop/src/bridge/desktopBridge.ts apps/desktop/src/screens.tsx apps/desktop/src/ui.tsx apps/desktop/src/styles.css apps/desktop/src/App.tsx
git commit -m "feat: add frontend surfaces for resources artifacts reviews and experiments"
```

### Task 13: Update Sample Project, Plugin Contracts, Docs, Benchmarks, and Final Verification

**Files:**
- Modify: `services/python-engine/app/node_plugins.py`
- Modify: `plugins/nodes/README.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/current-status.md`
- Modify: `docs/product-scope.md`
- Modify: `docs/workflow-runtime.md`
- Modify: `docs/benchmark.md`
- Modify: `docs/development.md`
- Modify: `apps/desktop/src/data/demoProject.ts`
- Modify: `services/python-engine/benchmarks/large_workflow_benchmark.py`
- Modify: `services/python-engine/tests/test_node_catalog_parity.py`

**Step 1: Add failing benchmark and plugin-compat expectations**

```python
def test_plugin_nodes_can_emit_artifact_handles(): ...
def test_benchmark_workflow_runs_with_artifact_store_enabled(): ...
```

**Step 2: Run tests to verify they fail**

Run: `pytest services/python-engine/tests/test_node_catalog_parity.py -q`
Expected: FAIL if plugin/runtime contract changed.

**Step 3: Update plugin API docs**

Document that plugin executors may now return artifact-backed payload summaries and must declare output kinds explicitly when needed.

**Step 4: Update sample/demo**

Add at least one sample that demonstrates:

- corpus view
- runtime dictionary overlay
- experiment spec
- review task

**Step 5: Run full verification**

Run: `npm run lint`
Expected: PASS

Run: `npm run test --workspace apps/desktop`
Expected: PASS

Run: `npm run test:engine`
Expected: PASS

Run: `npm run build`
Expected: PASS

Run: `npm run tauri:build --workspace apps/desktop`
Expected: PASS and produce a Windows installer.

**Step 6: Commit**

```bash
git add services/python-engine/app/node_plugins.py plugins/nodes/README.md README.md docs/architecture.md docs/current-status.md docs/product-scope.md docs/workflow-runtime.md docs/benchmark.md docs/development.md apps/desktop/src/data/demoProject.ts services/python-engine/benchmarks/large_workflow_benchmark.py services/python-engine/tests/test_node_catalog_parity.py
git commit -m "docs: finalize workflow platform upgrade docs samples and verification"
```

## Final Manual Acceptance Pass

After Task 13, do one manual desktop pass in the built app:

1. Create a new project.
2. Import a mixed CSV/XLSX corpus.
3. Save an ingestion spec.
4. Create two corpus views.
5. Build a workflow using metadata filter, dedupe, keyword extraction, keyness, topic modeling, and HTML export.
6. Run the workflow once in full mode.
7. Open artifact previews without loading full payloads.
8. Create a review task from a keyword or institution issue.
9. Resolve the review and verify write-back.
10. Create an experiment matrix with at least two variants.
11. Run both variants and open run diff.
12. Edit one source document and run incremental mode.
13. Verify only dependent nodes rerun and unaffected cached nodes stay cached.
14. Build the installer and open the app from the packaged binary.

If any step fails, add a dedicated regression test before fixing it.

## Done Definition

The work is only done when:

- project schema supports resources, artifacts, reviews, experiments, and shared refs
- workflow runtime can emit artifact handles and load previews on demand
- corpus and dictionary selection/comparison nodes exist and are usable from the graph UI
- review and experiment workflows exist as product surfaces, not hidden scripts
- incremental rerun works and respects dirty propagation
- controlled flow primitives exist without introducing general loops
- docs, demo data, tests, benchmark, and Windows build are updated together

## Next Session Handoff Prompt

Open a new Codex session in this repository and paste:

```text
请严格按照 docs/plans/2026-04-23-textflow-complete-workflow-platform-upgrade.md 执行，不要重写计划，不要再拆分阶段。按文档中的任务顺序逐个实现，每完成一个任务就：
1. 跑文档里指定的定向测试
2. 如果改了 TypeScript，再跑 npm run lint
3. 简短汇报当前任务完成情况和下一任务
4. 不要跳过文档、测试、样例和打包验证

如果发现计划中的文件路径需要微调，可以做最小必要调整，但必须先说明原因，再继续执行。
```
