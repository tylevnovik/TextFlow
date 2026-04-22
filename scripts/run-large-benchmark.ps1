$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$engineRoot = Join-Path $projectRoot "services\python-engine"
$pythonExe = Join-Path $engineRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
  throw "Missing .venv. Run .\scripts\bootstrap-python.ps1 first."
}

Push-Location $engineRoot
try {
  & $pythonExe "benchmarks\large_workflow_benchmark.py" @args
}
finally {
  Pop-Location
}
