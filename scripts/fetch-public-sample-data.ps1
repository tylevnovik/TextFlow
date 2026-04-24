param(
  [string[]]$Dataset,
  [string[]]$Language = @("en", "zh"),
  [int]$LimitPerLanguage = 10000,
  [switch]$All
)

$ErrorActionPreference = "Stop"

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

$args = @(
  "-m",
  "app.public_sample_data_builder",
  "--limit-per-language",
  "$LimitPerLanguage"
)

foreach ($datasetId in $datasetList) {
  $args += @("--dataset", $datasetId)
}

foreach ($languageId in $languageList) {
  $args += @("--language", $languageId)
}

& $venvPython @args
if ($LASTEXITCODE -ne 0) {
  throw "Failed to prepare real public sample data cache."
}
