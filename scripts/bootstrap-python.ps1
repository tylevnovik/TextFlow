$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$engineRoot = Join-Path $projectRoot "services\python-engine"
$venvPath = Join-Path $engineRoot ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"
$tempRoot = Join-Path $engineRoot ".tmp"

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
$env:TEMP = $tempRoot
$env:TMP = $tempRoot

if (-not (Test-Path $pythonExe)) {
  python -m venv $venvPath
}

& $pythonExe -m ensurepip --upgrade --default-pip
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -e "$engineRoot[dev]"

Write-Host "Python venv is ready at $venvPath"
