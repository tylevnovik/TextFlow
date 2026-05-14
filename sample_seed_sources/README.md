# Sample Seed Sources

This directory contains sample seed data used to build bundled example projects.

## Licensing Gate

- `private/` is gitignored and must not be committed. It is for local development seed files only.
- Spreadsheet/CSV seed files placed directly in this folder are also gitignored for local discovery during private builds.
- WoS, Scopus, and IncoPat exports are typically restricted by subscription agreements.
- Do not redistribute restricted seed files in public releases.

## Build Instructions

For local/private builds with restricted seed data:

```powershell
.\scripts\build-bundled-sample-workspace.ps1 `
  -WosSeed "path\to\wos.xls" `
  -IncopatSeed "path\to\incopat.xlsx" `
  -AllowRestrictedSampleData `
  -RowLimit 300
```

For release builds, omit `-AllowRestrictedSampleData`. The build will fail unless all seeds are marked `approved` for redistribution.

## Approved Redistribution

If you obtain explicit redistribution rights for a seed dataset:

1. Move the file to a named subdirectory under this folder (not `private/`).
2. Update `services/python-engine/app/sample_seed_sources.py` to set `redistribution="approved"` and include the license note.
3. Remove the `-AllowRestrictedSampleData` requirement for that seed.
