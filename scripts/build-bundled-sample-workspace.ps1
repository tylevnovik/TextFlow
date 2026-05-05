param(
  [Nullable[int]]$RowLimit = $null,
  [string]$WosSeed = "",
  [string]$IncopatSeed = "",
  [string]$ScopusSeed = "",
  [switch]$AllowRestrictedSampleData
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$engineRoot = Join-Path $projectRoot "services\python-engine"
$venvPython = Join-Path $engineRoot ".venv\Scripts\python.exe"
$bundledWorkspaceDir = Join-Path $engineRoot "app\bundled_sample_workspace"

if (-not (Test-Path $venvPython)) {
  throw "Missing .venv. Run .\scripts\bootstrap-python.ps1 first."
}

$env:TEXTFLOW_SAMPLE_WOS_SOURCE = $WosSeed
$env:TEXTFLOW_SAMPLE_INCOPAT_SOURCE = $IncopatSeed
$env:TEXTFLOW_SAMPLE_SCOPUS_SOURCE = $ScopusSeed
if ($AllowRestrictedSampleData) {
  $env:TEXTFLOW_ALLOW_RESTRICTED_SAMPLE_DATA = "1"
}

$pythonArgs = @("-m", "app.bundled_sample_workspace", "--output", $bundledWorkspaceDir)
if ($null -ne $RowLimit) {
  $pythonArgs += @("--row-limit", [string]$RowLimit)
}

Push-Location $engineRoot
try {
  & $venvPython @pythonArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to build the bundled sample workspace."
  }
}
finally {
  Pop-Location
}

Write-Host "Bundled sample workspace built at $bundledWorkspaceDir"
