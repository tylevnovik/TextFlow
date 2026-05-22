# Workbench Smoke Defect Fix Implementation Plan

> **For future agents:** use the project browser smoke-test workflow in `docs/development.md` after each visible frontend pass.

**Goal:** Turn the smoke-test findings into concrete UI fixes that make TextFlow feel like a coherent desktop workbench instead of several overlapping pages.

**Architecture:** Keep the existing React/Tauri shell and Fluent UI dependency. Fix the app from the outside inward: command ownership, workbench navigation, status surfaces, then individual corpus/lexicon/workflow surfaces.

**Tech Stack:** React, TypeScript, Fluent UI v9, CSS tokens in `apps/desktop/src/styles.css` and `apps/desktop/src/app/fluentTheme.ts`.

---

## Task 1: Contextual Workbench Commands

**Files:**
- Modify: `apps/desktop/src/app/ProjectWorkbench.tsx`
- Modify: `apps/desktop/src/styles.css`

**Steps:**
1. Replace the always-on global command bar with context-aware command groups.
2. Keep project commands always visible only as project navigation/opening affordances.
3. Show `导入语料` only on corpus/home/project contexts.
4. Show `保存图` only on workflow.
5. Show `运行` only when a workflow is active, and label it as running the workflow.
6. Show `导出` only on project/results/report contexts where artifacts/project package exports make sense.
7. Remove the inert `搜索` global command until it opens an actual command/search surface.

**Acceptance:** The top bar no longer displays disabled or irrelevant commands such as `保存图` on the home/corpus/lexicon pages, and there is no visible global `搜索` button that does nothing.

## Task 2: Object Tree Deglobalization

**Files:**
- Modify: `apps/desktop/src/app/workbenchNavigation.ts`
- Modify: `apps/desktop/src/app/ProjectWorkbench.tsx`

**Steps:**
1. Keep left object tree focused on project, corpus collections, lexicon categories, one active workflow, recent run, artifact list, and settings.
2. Remove leaf-level lexicon resource tables from the default tree; show them in the lexicon workspace/inspector instead.
3. Move workflow action items into a compact workflow action strip in the object pane when the workflow page is active.
4. Remove workflow node-library and node-instance spam from the default tree unless a later dedicated palette/search is introduced.
5. Default-open only project and the active page group instead of every group.

**Acceptance:** The left pane fits the primary product objects without forcing users to scroll through every resource table before reaching `节点图`.

## Task 3: Remove Home Landing Page Feel

**Files:**
- Modify: `apps/desktop/src/screens.tsx`
- Modify: `apps/desktop/src/styles.css`

**Steps:**
1. Replace the large instructional hero with a compact project manager surface.
2. Keep create/import/open/export actions, but present them as desktop command rows, not marketing copy.
3. Remove always-visible onboarding prose from the current-project view.
4. Keep the project library searchable and action-oriented.

**Acceptance:** Opening the app lands on a project manager, not a large explanation page that repeats the top bar.

## Task 4: Run Pane Cleanup

**Files:**
- Modify: `apps/desktop/src/features/runs/RunStatusPane.tsx`
- Modify: `apps/desktop/src/styles.css`
- Test: `apps/desktop/src/app/ProjectWorkbench.test.tsx`

**Steps:**
1. Fix duplicated accessible tab names by using explicit `aria-label` and simple visible labels.
2. Replace the four-card progress summary with a compact status strip.
3. Make the pane easier to scan in small desktop windows.

**Acceptance:** DOM snapshots no longer show `节点日志 节点日志` / `产物列表 产物列表`, and the bottom pane takes less visual attention.

## Task 5: Workflow Canvas First

**Files:**
- Modify: `apps/desktop/src/app/ProjectWorkbench.tsx`
- Modify: `apps/desktop/src/screens.tsx`
- Modify: `apps/desktop/src/styles.css`

**Steps:**
1. Make the workflow surface header compact or hidden so the canvas becomes the first visual priority.
2. Keep workflow actions in the outer object pane action strip, not as canvas-internal duplicated toolbar.
3. De-emphasize raw port IDs visually while preserving connection targets and tooltips.

**Acceptance:** Workflow view opens with a larger canvas, visible minimap, no internal old rail, and fewer user-facing technical strings.

## Verification

Run after implementation:

```powershell
npm run lint --workspace apps/desktop
npm run test --workspace apps/desktop
npm run build
```

Then use Codex Browser against the local Vite URL, following `docs/development.md`:

- Default/project manager loads.
- Corpus page has no irrelevant `保存图` command.
- Lexicon page left tree is not flooded by resource tables.
- Workflow page reaches canvas without scrolling through a giant header.
- Bottom tabs have unique names.
- Small desktop viewport remains usable.
