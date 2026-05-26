# AGENTS.md

## Project
Build a desktop-first text preprocessing and basic text mining utility for end users.
The first shipping target is Windows, but the architecture must remain portable to macOS.
The product must be install-and-run and must not require users to configure Python, Node, or other dependencies manually.

## Product Priorities
1. Stable shipping quality over flashy features
2. Project-based organization of data, workflows, dictionaries, and outputs
3. Reproducible preprocessing workflow
4. Rule auditability and run history
5. Responsive desktop UI
6. Future compatibility with node-based workflow editor

## Mandatory V1 Features
- Project management
- Corpus import from txt/csv/xlsx/json
- Metadata mapping with source profiles
- Main-text construction from one or multiple fields
- Cleaning and normalization workflow
- Tokenization with phrase preservation
- Dictionary center
- Stopword / synonym / standard term / exclusion handling
- Frequency statistics
- Term-document relations
- Term-year relations
- Co-occurrence analysis
- Basic clustering visualization
- Feature-term selection
- Keyword extraction
- Keyword clustering
- Institution-keyword and institution-topic analysis
- Export to CSV/XLSX/PNG/HTML
- Saved runs and logs

## Explicit Non-Goals for V1
- Node-based drag-and-drop workflow UI
- Cloud sync
- Multi-user collaboration
- Native mobile apps

## Architecture Rules
- Desktop shell: Tauri
- Frontend: React + TypeScript
- Core analysis engine: Python sidecar/service
- Separate UI, domain types, and execution engine cleanly
- Do not hardcode workflow logic into UI components
- Do not couple project file format to transient UI state
- Reserve graph-based workflow schema even if V1 executes linearly

## Code Quality Rules
- Prefer typed interfaces and clear domain models
- Every major module must include tests
- All new features must update docs
- Avoid hidden magic behavior; users must be able to inspect what rules were applied
- Long-running tasks must not block UI

## Engine Test Selection Rules
- `npm run test:engine` and `npm run test:engine:fast` are the default day-to-day Python engine checks. Future AI should assume this fast suite is the minimum required validation for engine changes unless the heavier rules below apply.
- Run the fast suite after changes to normal engine/domain logic such as ingestion, dictionaries, workflow compilation, project storage, result shaping, or other Python behavior that does not change bundled sample bootstrapping or packaging.
- Run `npm run test:engine:full` when touching any first-run sample bootstrap, builtin sample generation, bundled sample workspace logic, public sample cache packaging, Python sidecar build scripts, or project flows that implicitly depend on seeded official samples.
- In practice, `test:engine:full` is required whenever changes touch files such as `services/python-engine/app/sample_projects.py`, `services/python-engine/app/bundled_sample_workspace.py`, `services/python-engine/app/cli.py` bootstrap paths, `services/python-engine/app/sample_dataset_*`, `scripts/build-bundled-sample-workspace.ps1`, `scripts/build-python-sidecar.ps1`, or tests marked `engine_full`.
- `test:engine:full` is also required for changes to export/import/template flows that may trigger seeded sample bootstrap or reuse packaged sample projects during validation.
- Frontend-only changes, docs-only changes, or styling changes do not require engine tests unless they also alter Python-facing contracts or packaged sample behavior.
- If there is doubt, run `npm run test:engine:full` before shipping or packaging.

## Packaging Rules
- Windows build must produce an installer
- Sidecar packaging must be reproducible
- Do not assume user-installed Python runtime
- Keep macOS portability in mind when selecting dependencies

## UX Rules
- Support medium and small desktop window sizes
- Use empty states and guided defaults
- Expose presets/templates where possible
- Make audit trails visible in the UI

## Frontend Browser Smoke Test Rules
- After significant frontend UI, visual, layout, or workbench changes, run a local browser smoke test before handing off.
- Start the desktop frontend with a local Vite server on a free localhost port, for example `npm run dev --workspace apps/desktop -- --host 127.0.0.1 --port 5174 --strictPort`.
- Use the Codex in-app Browser / Browser plugin to open `http://127.0.0.1:<port>/`; do not substitute an OS browser launch when working inside Codex.
- Smoke the surfaces touched by the change and include visual checks for app load, reachability, obvious runtime failures, text overlap, duplicate command/status surfaces, stale legacy controls, collapse/resize behavior for touched panes, and Fluent focus/border states.
- For workflow graph changes, verify the graph opens from the outer workbench object tree, the canvas/minimap render, workflow actions live in the outer left workbench surface, old internal rails/toolbars are absent, and the graph can be panned/zoomed without hiding primary content.
- Use a DOM snapshot plus a visible screenshot when the change is visual or layout-sensitive. Keep temporary smoke logs outside the repo, such as under `%TEMP%`.
- If the dev server is left running for the user, report the exact local URL; otherwise stop the temporary server after verification.

## CI/CD Diagnosis Rules
- Future agents can check GitHub Actions workflow status and logs directly from the terminal if the local system has an authenticated GitHub CLI (`gh`).
- Use `gh run list --limit <N>` to view recent workflow run statuses.
- Use `gh run view <run-id>` to check run details and jobs.
- Use `gh run view --log --job=<job-id>` to fetch and debug failing step logs.

## Deliverables
- Working desktop app skeleton
- Python engine skeleton
- Sample project
- Documentation
- Packaging scripts
- Automated tests for core logic
