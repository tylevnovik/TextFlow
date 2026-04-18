$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot

Push-Location $projectRoot
try {
  powershell -ExecutionPolicy Bypass -File .\scripts\build-python-sidecar.ps1
  if ($LASTEXITCODE -ne 0) {
    throw "Desktop release build stopped because Python sidecar build failed."
  }

  npm run build --workspace apps/desktop
  if ($LASTEXITCODE -ne 0) {
    throw "Desktop release build stopped because frontend build failed."
  }
}
finally {
  Pop-Location
}
