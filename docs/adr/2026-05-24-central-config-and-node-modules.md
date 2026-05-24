# ADR: Central Project Config and Directory-Scanned Built-In Nodes

## Status

Accepted

## Context

TextFlow had release metadata and node registration details spread across npm manifests, Tauri config, Cargo metadata, Python package metadata, the FastAPI app, and workflow registry modules. Updating a version or adding a node could require touching unrelated framework files, which increases release risk and makes built-in nodes behave differently from local plugin nodes.

## Decision

Use `textflow.config.json` at the repository root as the source of truth for product metadata such as product name, app identifier, and release version. `scripts/sync-project-config.mjs` propagates that source into required tool manifests and supports `--check` for CI/build validation. Release builds run the check before packaging.

Add `services/python-engine/app/workflow/nodes/` as the built-in node module directory. Modules in that directory expose `node_definition`, `node_definitions`, `register_nodes`, or `register`, and the registry scans them with the same shape used by plugin registration. A node module should own the node-level definition, compiler hook, executor hook, and registration in one file; shared algorithms may still live in analysis, storage, reporting, or workflow support modules.

All built-in nodes now live under `services/python-engine/app/workflow/nodes/`. The old `definitions/builtin.py` entry point remains as a compatibility facade for callers that need the catalog, but it builds that catalog entirely from directory-scanned node modules. The old global compiler and executor maps are no longer a registration source.

## Consequences

- Release version changes should start in `textflow.config.json`, then run `npm run config:sync`.
- Build validation can fail early with `npm run config:check` if required manifests drift.
- New built-in nodes can be added as files under `app/workflow/nodes/` without editing the core registry or global compiler/executor maps.
- Built-in and external plugin nodes now use the same registration boundary, which keeps node metadata and hooks auditable in one place.
- Frontend generated schema still depends on the Python catalog, so schema generation/parity remains the guardrail for UI-facing node metadata.

## Follow-Ups

- Generate frontend UI defaults from node metadata where possible, keeping custom rich editors as explicit overrides.
- Add a CI job that runs `npm run config:check`, `npm run lint --workspace apps/desktop`, and `npm run test:engine:fast`.
