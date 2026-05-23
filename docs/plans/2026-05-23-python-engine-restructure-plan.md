# Python Engine Restructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn `services/python-engine/app` from a flat prototype-style module set into a layered package structure without changing user-visible behavior.

**Architecture:** Use a strangler migration. Move one cohesive slice at a time into the target packages documented in `docs/adr/2026-05-23-python-engine-module-boundaries.md`, keep thin compatibility wrappers at old import paths, and remove wrappers only after internal imports have migrated.

**Tech Stack:** Python 3.11+, pytest, npm workspace scripts, Tauri sidecar packaging, SQLite project store, native DAG workflow runtime.

---

## Guardrails

- Do not combine behavior changes with file movement.
- Preserve old import paths with compatibility wrappers during the migration.
- Keep heavy analysis/export imports out of `app.cli` and `app.service` cold-start paths.
- Do not introduce dynamic imports inside document/token loops.
- Do not reintroduce broad `deepcopy` of corpus rows or result bundles in workflow runtime.
- For sample, bundled workspace, bootstrap, or packaging path changes, run `npm run test:engine:full`.
- For pure non-sample engine refactors, run at least `npm run test:engine:fast`.

## Task 1: Record Target Architecture and Performance Assessment

**Files:**
- Create: `docs/adr/2026-05-23-python-engine-module-boundaries.md`
- Create: `docs/plans/2026-05-23-python-engine-restructure-plan.md`
- Modify: `docs/architecture.md`

**Step 1: Add the ADR**

Write the target tree, dependency rules, migration order, performance risks, and verification commands.

**Step 2: Add this plan**

Write the phased execution checklist so future sessions can continue without rediscovering the intended structure.

**Step 3: Link the ADR**

Add a short link from `docs/architecture.md` to the ADR.

**Step 4: Verify docs formatting**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

## Task 2: Move Sample Modules Into `app.samples`

**Files:**
- Create: `services/python-engine/app/samples/__init__.py`
- Move: `services/python-engine/app/sample_projects.py` -> `services/python-engine/app/samples/projects.py`
- Move: `services/python-engine/app/sample_seed_sources.py` -> `services/python-engine/app/samples/seed_sources.py`
- Move: `services/python-engine/app/bundled_sample_workspace.py` -> `services/python-engine/app/samples/bundled_workspace.py`
- Create compatibility wrappers:
  - `services/python-engine/app/sample_projects.py`
  - `services/python-engine/app/sample_seed_sources.py`
  - `services/python-engine/app/bundled_sample_workspace.py`
- Modify internal relative imports in moved modules.
- Test:
  - `services/python-engine/tests/test_sample_projects.py`
  - `services/python-engine/tests/test_bundled_sample_workspace.py`
  - `services/python-engine/tests/test_sample_seed_sources.py`
  - `services/python-engine/tests/test_workspace_cli.py`

**Step 1: Move files and preserve resource paths**

`samples/seed_sources.py` must keep `sample_seed_root()` pointing at the repository root `sample_seed_sources/` directory.

`samples/bundled_workspace.py` must keep `default_bundled_sample_workspace_root()` pointing at the existing packaged `app/bundled_sample_workspace/` directory.

**Step 2: Add wrappers**

Compatibility wrappers should forward old imports. `sample_seed_sources.py` should alias the moved module object so monkeypatching `app.sample_seed_sources.sample_seed_root` still affects `default_sample_seed_sources()`.

**Step 3: Update direct internal imports**

New code should prefer:

```python
from .samples.projects import ...
from .samples.bundled_workspace import ...
```

Keep tests on old imports until wrappers are proven.

**Step 4: Run focused tests**

```powershell
services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_sample_seed_sources.py services\python-engine\tests\test_bundled_sample_workspace.py services\python-engine\tests\test_sample_projects.py services\python-engine\tests\test_workspace_cli.py -q
```

Expected: pass.

**Step 5: Run full engine suite**

```powershell
npm run test:engine:full
```

Expected: pass.

## Task 3: Establish Workflow Package Imports

**Files:**
- Create: `services/python-engine/app/workflow/__init__.py`
- Move later, one file at a time:
  - `node_compilers.py` -> `workflow/compilers.py`
  - `node_plugins.py` -> `workflow/plugins.py`
  - `node_registry.py` -> `workflow/registry.py`
- Keep wrappers at old paths.

**Step 1: Move `node_compilers.py` first**

Adjust imports from `.defaults` and `.node_registry` to the correct package paths.

**Step 2: Move `node_plugins.py`**

Keep plugin root calculation stable.

**Step 3: Move `node_registry.py` last**

Update registry lazy imports so it imports from `workflow.compilers`, `workflow.plugins`, and the remaining old definitions/executors until those are split.

**Step 4: Run catalog/runtime tests**

```powershell
services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_node_catalog_parity.py services\python-engine\tests\test_workflow_runner.py -q
npm run test:engine:fast
```

Expected: pass.

## Task 4: Split Node Executors by Node Category

**Files:**
- Create:
  - `services/python-engine/app/workflow/executors/support.py`
  - `services/python-engine/app/workflow/executors/corpus.py`
  - `services/python-engine/app/workflow/executors/preprocessing.py`
  - `services/python-engine/app/workflow/executors/analysis.py`
  - `services/python-engine/app/workflow/executors/graph.py`
  - `services/python-engine/app/workflow/executors/export.py`
  - `services/python-engine/app/workflow/executors/legacy.py`
- Modify: `services/python-engine/app/node_executors.py`

**Step 1: Extract shared helpers**

Move `_shared_get`, `_shared_set`, `_table_rows_from_inputs_or_results`, `_scoped_corpus_from_inputs`, progress helpers, and other cross-category helpers into `support.py`.

**Step 2: Move corpus and preprocessing executors**

Move corpus input/filter/merge/sampling/splitting and clean/normalize/tokenize/dictionary/filter/focus functions first.

**Step 3: Move analysis and graph executors**

Move analysis functions, then graph functions. Keep algorithm implementation in `analysis_ops.py`, `graph_ops.py`, and `technology_ops.py` until Task 5.

**Step 4: Move export and legacy executors**

Keep output artifact semantics unchanged.

**Step 5: Keep old registration surface**

`node_executors.py` should only assemble `EXECUTORS_BY_TYPE` and call category registration helpers.

**Step 6: Verify**

```powershell
services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_modeling_nodes.py services\python-engine\tests\test_workflow_runner.py services\python-engine\tests\test_new_flow_workflow.py -q
npm run test:engine:fast
```

Expected: pass.

## Task 5: Split Analysis Operations

**Files:**
- Create:
  - `services/python-engine/app/analysis/__init__.py`
  - `services/python-engine/app/analysis/statistics.py`
  - `services/python-engine/app/analysis/keywords.py`
  - `services/python-engine/app/analysis/topics.py`
  - `services/python-engine/app/analysis/graph.py`
  - `services/python-engine/app/analysis/technology.py`
- Keep compatibility wrappers:
  - `services/python-engine/app/analysis_ops.py`
  - `services/python-engine/app/graph_ops.py`
  - `services/python-engine/app/technology_ops.py`

**Step 1: Move pure functions by topic**

Do not change algorithms or output row shape.

**Step 2: Preserve import laziness**

Large libraries should be imported in the same or lazier paths than before.

**Step 3: Verify analysis behavior**

```powershell
services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_modeling_nodes.py services\python-engine\tests\test_comparison_nodes.py -q
npm run test:engine:fast
```

Expected: pass.

## Task 6: Split Storage and Defaults

**Files:**
- Create:
  - `services/python-engine/app/domain/`
  - `services/python-engine/app/storage/`
- Split `defaults.py`, `project_store.py`, and `project_database.py` gradually.

**Step 1: Extract domain constants and result bundle helpers**

Move pure constants and normalization helpers first.

**Step 2: Extract workspace/project storage**

Separate workspace state, project CRUD, templates, package import/export, and SQLite adapters.

**Step 3: Keep manifest format stable**

No field rename, no output bundle key change, no schema migration unless separately planned.

**Step 4: Verify**

```powershell
services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_project_store.py services\python-engine\tests\test_workspace_cli.py -q
npm run test:engine:fast
```

Expected: pass.

## Task 7: Split DAG Runtime Last

**Files:**
- Create:
  - `services/python-engine/app/workflow/runtime/context.py`
  - `services/python-engine/app/workflow/runtime/scheduler.py`
  - `services/python-engine/app/workflow/runtime/cache.py`
  - `services/python-engine/app/workflow/runtime/artifacts.py`
  - `services/python-engine/app/workflow/runtime/previews.py`
- Keep wrapper: `services/python-engine/app/dag_runtime.py`

**Step 1: Extract preview helpers**

Lowest behavior risk.

**Step 2: Extract cache helpers**

Preserve cache key and payload format.

**Step 3: Extract context/state dataclasses**

No semantic changes to shared values, artifact records, or progress events.

**Step 4: Extract scheduler loop**

Only after earlier pieces are stable.

**Step 5: Verify and benchmark**

```powershell
npm run test:engine:fast
powershell -ExecutionPolicy Bypass -File .\scripts\run-large-benchmark.ps1 --limit 1200
```

Expected: pass; benchmark should not regress materially from file movement alone.

## Task 8: Split API Actions

**Files:**
- Create:
  - `services/python-engine/app/api/actions/projects.py`
  - `services/python-engine/app/api/actions/imports.py`
  - `services/python-engine/app/api/actions/workflows.py`
  - `services/python-engine/app/api/actions/reviews.py`
  - `services/python-engine/app/api/actions/experiments.py`
- Keep `services/python-engine/app/cli.py` as the action dispatcher.

**Step 1: Move action handlers by product area**

No payload contract changes.

**Step 2: Keep `execute_action()` stable**

Frontend/Tauri bridge should not need changes.

**Step 3: Verify CLI/workspace tests**

```powershell
services\python-engine\.venv\Scripts\python.exe -m pytest services\python-engine\tests\test_workspace_cli.py -q
npm run test:engine:fast
```

Expected: pass.

## Task 9: Remove Compatibility Wrappers

Only start this task after all internal imports have moved and at least one release has shipped with wrappers.

**Files:**
- Delete old wrapper modules after repo-wide search confirms no internal imports remain.
- Update docs and migration notes.

**Verification:**

```powershell
rg -n "from app\.(sample_projects|node_registry|node_compilers|node_executors|project_store|defaults)|from \.(sample_projects|node_registry|node_compilers|node_executors|project_store|defaults)" services apps packages
npm run test:engine:full
```

Expected: no internal legacy imports except documented compatibility tests; full suite passes.
