param(
  [ValidateSet("fast", "full")]
  [string]$Suite = "fast",
  [string[]]$AdditionalPytestArgs = @()
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$engineRoot = Join-Path $projectRoot "services\python-engine"
$pythonExe = Join-Path $engineRoot ".venv\Scripts\python.exe"
$tempRoot = Join-Path $engineRoot ".tmp"
$pytestTemp = Join-Path $tempRoot "pytest"
$pytestCache = Join-Path $tempRoot "pytest-cache"

if (-not (Test-Path $pythonExe)) {
  throw "Missing .venv. Run .\scripts\bootstrap-python.ps1 first."
}

New-Item -ItemType Directory -Path $pytestTemp -Force | Out-Null
New-Item -ItemType Directory -Path $pytestCache -Force | Out-Null
$env:TEMP = $tempRoot
$env:TMP = $tempRoot

Push-Location $engineRoot
try {
  $pytestArgs = @("-m", "pytest", "tests", "-q")
  if ($Suite -eq "fast") {
    $pytestArgs += @("-m", "not engine_full")
  }
  if ($AdditionalPytestArgs.Count -gt 0) {
    $pytestArgs += $AdditionalPytestArgs
  }
  & $pythonExe @pytestArgs
}
finally {
  Pop-Location
}
