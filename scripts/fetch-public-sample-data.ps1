$ErrorActionPreference = "Stop"

param(
  [string[]]$Dataset,
  [string[]]$Language = @("en", "zh"),
  [int]$LimitPerLanguage = 10000,
  [switch]$All
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$engineRoot = Join-Path $projectRoot "services\python-engine"
$venvPython = Join-Path $engineRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
  throw "Missing .venv. Run .\scripts\bootstrap-python.ps1 first."
}

$datasetList = @()
if ($All) {
  $datasetList = @(
    "un_parallel_en_zh",
    "wikimedia_enwiki",
    "wikimedia_zhwiki",
    "openalex_works"
  )
}
elseif ($Dataset) {
  foreach ($item in $Dataset) {
    if (-not $item) {
      continue
    }
    $datasetList += ($item -split "," | Where-Object { $_ } | ForEach-Object { $_.Trim() })
  }
}
else {
  throw "Specify -Dataset <id> or use -All."
}

$languageList = @()
foreach ($item in $Language) {
  if (-not $item) {
    continue
  }
  $languageList += ($item -split "," | Where-Object { $_ } | ForEach-Object { $_.Trim() })
}

$payload = @{
  datasets = $datasetList
  languages = $languageList
  limit_per_language = $LimitPerLanguage
} | ConvertTo-Json -Compress

$script = @'
from __future__ import annotations

import gzip
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone

from app.sample_dataset_cache import normalized_cache_path, sample_data_cache_root
from app.sample_dataset_sources import PUBLIC_SAMPLE_DATA_SOURCE_BY_ID

payload = json.loads(sys.argv[1])
datasets = payload["datasets"]
languages = set(payload["languages"])
limit_per_language = int(payload["limit_per_language"])

cache_root = sample_data_cache_root()
manifest = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "limit_per_language": limit_per_language,
    "datasets": [],
}

for dataset_id in datasets:
    source = PUBLIC_SAMPLE_DATA_SOURCE_BY_ID.get(dataset_id)
    if source is None:
        raise ValueError(f"Unknown public dataset id: {dataset_id}")

    cache_path = normalized_cache_path(cache_root, dataset_id)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"Normalized cache not found for {dataset_id}: {cache_path}. "
            "Create the real public-data subset before packaging."
        )

    counts = Counter()
    with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            language = str(row.get("language") or "")
            if not languages or language in languages:
                counts[language] += 1

    digest = hashlib.sha256(cache_path.read_bytes()).hexdigest()
    manifest["datasets"].append(
        {
            "dataset_id": dataset_id,
            "name": source.name,
            "homepage_url": source.homepage_url,
            "download_url": source.download_url,
            "license_name": source.license_name,
            "public_access_note": source.public_access_note,
            "redistribution_note": source.redistribution_note,
            "row_count_by_language": {language: counts.get(language, 0) for language in sorted(counts)},
            "sha256": digest,
            "cache_file": cache_path.name,
        }
    )

manifest_path = cache_root / "manifest.json"
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print(manifest_path)
'@

& $venvPython -c $script $payload
if ($LASTEXITCODE -ne 0) {
  throw "Failed to prepare public sample data manifest."
}
