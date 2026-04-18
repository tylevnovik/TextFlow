# AGENTS.md

## Project
Build a desktop-first text preprocessing and basic text mining utility for end users.
The first shipping target is Windows, but the architecture must remain portable to macOS.
The product must be install-and-run and must not require users to configure Python, Node, or other dependencies manually.

## Product Priorities
1. Stable shipping quality over flashy features
2. Project-based organization of data, pipelines, dictionaries, and outputs
3. Reproducible preprocessing workflow
4. Rule auditability and run history
5. Responsive desktop UI
6. Future compatibility with node-based pipeline editor

## Mandatory V1 Features
- Project management
- Corpus import from txt/csv/xlsx/json
- Metadata mapping with source profiles
- Main-text construction from one or multiple fields
- Cleaning and normalization pipeline
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
- Node-based drag-and-drop pipeline UI
- Cloud sync
- Multi-user collaboration
- Native mobile apps

## Architecture Rules
- Desktop shell: Tauri
- Frontend: React + TypeScript
- Core analysis engine: Python sidecar/service
- Separate UI, domain types, and execution engine cleanly
- Do not hardcode all pipeline logic into UI components
- Do not couple project file format to transient UI state
- Reserve graph-based pipeline schema even if V1 executes linearly

## Code Quality Rules
- Prefer typed interfaces and clear domain models
- Every major module must include tests
- All new features must update docs
- Avoid hidden magic behavior; users must be able to inspect what rules were applied
- Long-running tasks must not block UI

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
