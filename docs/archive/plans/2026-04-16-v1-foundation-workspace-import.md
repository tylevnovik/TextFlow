# TextFlow V1 Foundation Workspace And Import Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the current demo-like prototype into a real V1 foundation by adding explicit workspace/project lifecycle management and real corpus import with persisted import settings.

**Architecture:** Keep the existing Tauri -> Python sidecar boundary, but make the Python engine own workspace state, project selection, import execution, and project persistence. The desktop app should stop inferring state from demo data and instead render real workspace/project/import state returned by the sidecar.

**Tech Stack:** Tauri 2, React 18, TypeScript, Python 3.11+, pandas, pytest

---

### Task 1: Workspace State And Project Lifecycle

**Files:**
- Modify: `services/python-engine/app/project_store.py`
- Modify: `services/python-engine/app/cli.py`
- Test: `services/python-engine/tests/test_workspace_cli.py`

**Step 1: Write the failing tests**

Add tests that verify:
- workspace metadata is created on first load
- current project selection is persisted
- projects can be created, opened, and duplicated
- recent projects ordering is updated after open/create

**Step 2: Run test to verify it fails**

Run: `.\services\python-engine\.venv\Scripts\python.exe -m pytest services/python-engine/tests/test_workspace_cli.py -q`
Expected: FAIL because workspace metadata and project lifecycle helpers do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- `workspace.json` metadata under samples/projects
- helpers to read/write workspace metadata
- explicit `open-project` and `duplicate-project` CLI actions
- `load_workspace_snapshot()` using persisted current project instead of “latest modified”

**Step 4: Run test to verify it passes**

Run: `.\services\python-engine\.venv\Scripts\python.exe -m pytest services/python-engine/tests/test_workspace_cli.py -q`
Expected: PASS

### Task 2: Real Import Configuration And Import Execution

**Files:**
- Modify: `services/python-engine/app/ingestion.py`
- Modify: `services/python-engine/app/defaults.py`
- Modify: `services/python-engine/app/project_store.py`
- Modify: `services/python-engine/app/cli.py`
- Test: `services/python-engine/tests/test_ingestion.py`

**Step 1: Write the failing test**

Add tests that verify:
- field mappings are applied instead of hardcoded field names
- `raw_text` can be built from multiple configured fields
- unmapped fields are preserved in `extra_metadata`
- import appends new source file records and persists corpus

**Step 2: Run test to verify it fails**

Run: `.\services\python-engine\.venv\Scripts\python.exe -m pytest services/python-engine/tests/test_ingestion.py -q`
Expected: FAIL because mappings are only partially respected and no project import action exists.

**Step 3: Write minimal implementation**

Implement:
- source-field to target-field mapping resolution
- project-level import action accepting file paths plus optional import template override
- duplicate detection during import
- source file record updates and project timestamp refresh

**Step 4: Run test to verify it passes**

Run: `.\services\python-engine\.venv\Scripts\python.exe -m pytest services/python-engine/tests/test_ingestion.py -q`
Expected: PASS

### Task 3: Desktop Bridge For Real Workspace Commands

**Files:**
- Modify: `apps/desktop/src/bridge/desktopBridge.ts`
- Modify: `apps/desktop/src/store/workspaceStore.tsx`
- Modify: `packages/shared-types/src/index.ts`

**Step 1: Write the failing TypeScript integration expectations**

Update types and store usage so the compiler fails until:
- workspace state includes import status and selected project controls
- bridge exposes `openProject`, `duplicateProject`, `importFiles`, and import-template save/update APIs

**Step 2: Run typecheck to verify it fails**

Run: `npm run lint --workspace apps/desktop`
Expected: FAIL until the new bridge/store contracts are wired.

**Step 3: Write minimal implementation**

Implement:
- real bridge commands for new Tauri actions
- workspace store actions for create/open/duplicate/import/update-import-template
- state refresh rules that keep the current project stable

**Step 4: Run typecheck to verify it passes**

Run: `npm run lint --workspace apps/desktop`
Expected: PASS

### Task 4: Replace Demo-Only UI Paths On Home/Data/Project Pages

**Files:**
- Modify: `apps/desktop/src/screens.tsx`
- Modify: `apps/desktop/src/ui.tsx`
- Modify: `apps/desktop/src/styles.css`

**Step 1: Write the failing UI assumptions**

Update pages to require:
- explicit project open/create controls on home page
- source file list and import form on data page
- real project path/run/source summary on project page
- editable import-template fields for text build and field mapping

**Step 2: Run typecheck/build to verify it fails**

Run: `npm run build --workspace apps/desktop`
Expected: FAIL until the pages no longer depend on demo-only assumptions.

**Step 3: Write minimal implementation**

Implement:
- project cards with “open” and “duplicate”
- import form using pasted absolute file paths for now
- import template editor for source profile, mappings, and text build
- visible source file history and corpus stats

**Step 4: Run build to verify it passes**

Run: `npm run build --workspace apps/desktop`
Expected: PASS

### Task 5: Verification And Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/pipeline-spec.md`

**Step 1: Run targeted verification**

Run:
- `.\services\python-engine\.venv\Scripts\python.exe -m pytest services/python-engine/tests -q`
- `npm run lint --workspace apps/desktop`
- `npm run build --workspace apps/desktop`

Expected:
- Python tests PASS
- TypeScript lint/typecheck PASS
- Desktop build PASS

**Step 2: Document what changed**

Document:
- workspace metadata model
- project lifecycle commands
- import configuration flow
- known gaps for later V1 slices: dictionary editing, result drill-down, export presets, richer desktop file picking
