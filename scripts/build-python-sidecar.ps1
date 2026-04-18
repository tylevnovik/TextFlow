$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$engineRoot = Join-Path $projectRoot "services\python-engine"
$venvPython = Join-Path $engineRoot ".venv\Scripts\python.exe"
$distDir = Join-Path $engineRoot "dist"
$tempRoot = Join-Path $engineRoot ".tmp"
$buildStamp = "{0}-{1}" -f (Get-Date -Format "yyyyMMdd-HHmmss"), ([guid]::NewGuid().ToString("N").Substring(0, 8))
$pyinstallerDistRoot = Join-Path $tempRoot "pyinstaller-dist-$buildStamp"
$pyinstallerWorkRoot = Join-Path $tempRoot "pyinstaller-build-$buildStamp"
$pyinstallerSpecRoot = Join-Path $tempRoot "pyinstaller-spec-$buildStamp"
$sidecarDir = Join-Path $distDir "textflow-engine"
$sidecarExe = Join-Path $distDir "textflow-engine.exe"
$buildTempRoot = Join-Path $tempRoot "build-temp-$buildStamp"

New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
New-Item -ItemType Directory -Path $buildTempRoot -Force | Out-Null
$env:TEMP = $buildTempRoot
$env:TMP = $buildTempRoot

if (-not (Test-Path $venvPython)) {
  throw "Missing .venv. Run .\scripts\bootstrap-python.ps1 first."
}

& $venvPython -m pip install -e "$engineRoot[build]"
if ($LASTEXITCODE -ne 0) {
  throw "Failed to install Python engine build dependencies."
}

Push-Location $engineRoot
try {
  & $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --contents-directory . `
    --collect-data yake `
    --collect-data wordcloud `
    --name textflow-engine `
    --distpath $pyinstallerDistRoot `
    --workpath $pyinstallerWorkRoot `
    --specpath $pyinstallerSpecRoot `
    main.py
  if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed to build the Python sidecar."
  }
}
finally {
  Pop-Location
}

if (Test-Path $sidecarDir) {
  Remove-Item -LiteralPath $sidecarDir -Recurse -Force
}
if (Test-Path $sidecarExe) {
  Remove-Item -LiteralPath $sidecarExe -Force
}
New-Item -ItemType Directory -Path $distDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $pyinstallerDistRoot "textflow-engine") -Destination $sidecarDir -Recurse -Force

Write-Host "Sidecar built at $sidecarDir\textflow-engine.exe"
