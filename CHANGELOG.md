# Changelog

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
