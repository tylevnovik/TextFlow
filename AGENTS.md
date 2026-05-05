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

## Deliverables
- Working desktop app skeleton
- Python engine skeleton
- Sample project
- Documentation
- Packaging scripts
- Automated tests for core logic
