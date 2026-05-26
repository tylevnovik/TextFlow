# Changelog

## v0.2.0 - 2026-05-26

### Highlights

- **Backend-Driven Node Schema Refactor**: Replaced frontend-coupled node configurations with schemas dynamically served by the Python backend catalog.
- **FastAPI Migration**: Ported the Python engine sidecar API from custom request dispatchers to a robust FastAPI application structure.
- **Fluent UI Workbench Integration**: Refactored the workflow workspace, adding dynamic node editing panels and slots using Fluent UI component guidelines.
- **Python Engine Restructuring**: Consolidated domain models, registry, and execution scheduler to improve modularity and clean architectural boundaries.
- **Performance & Testing**: Split engine tests into fast and full suites, and added contract validation tests for node schemas and catalog parity.

### Performance

- Split Python engine verification into a default `test:engine` fast tier and a heavier `test:engine:full` tier so day-to-day changes do not always pay for bundled sample integration coverage.
- Moved the three official revised-flow sample projects to a build-time bundled workspace template that ships inside the Python sidecar, avoiding first-run live generation for empty workspaces.

### Fixes

- Fixed IncoPat import presets to match real exported column names such as `标题 (中文)` / `摘要 (中文)` / `IPC`, added broader patent-text fallbacks, and improved source-field matching across punctuation and spacing variants.
- Fixed XLSX import normalization so empty spreadsheet cells no longer become literal `nan`, required-field checks correctly treat blank cells as missing, and date-like values now produce a usable document year.
- Fixed the advanced import field editor losing focus while typing by keeping mapping-row React keys stable during inline edits.

## v0.1.1 - 2026-04-25

### Highlights

- Promoted the current desktop build to `0.1.1` because `v0.1.0` already exists on GitHub and points to an older commit.
- Added nine backend-built official scenario sample projects based on public datasets, with strict English/Chinese `1:1` row balance.
- Switched the project model and runtime documentation to the current workflow-only native DAG execution path.
- Kept the result and export surfaces focused on lazy artifact previews, run diff, review queue and experiment matrix.

### Fixes

- Fixed project overview startup/rendering slowdown by removing full `run.logs` rendering from the overview page. The overview now shows only the latest three run summaries; full history stays in the results page.
- Fixed stale live workflow state leaking into the editor after a run completes.
- Fixed run artifact rendering for real artifact handles instead of assuming legacy step summaries.
- Reduced repeated large project refresh/write paths in the desktop store and Python project store.
- Replaced stale demo-style sample data with backend-generated public-source sample caches.

### Validation

- `npm run test --workspace apps/desktop`
- `npm run lint`
- `npm run test:engine`
- `npm run tauri:build --workspace apps/desktop`

### Release Asset

- `TextFlow Studio_0.1.1_x64-setup.exe`
