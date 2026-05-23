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
$bundledWorkspaceManifest = Join-Path $bundledWorkspaceDir "bundled_workspace.json"
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

$sampleBuildArgs = @{}
if ($null -ne $RowLimit) {
  $sampleBuildArgs.RowLimit = $RowLimit
}
if ($WosSeed) {
  $sampleBuildArgs.WosSeed = $WosSeed
}
if ($IncopatSeed) {
  $sampleBuildArgs.IncopatSeed = $IncopatSeed
}
if ($ScopusSeed) {
  $sampleBuildArgs.ScopusSeed = $ScopusSeed
}
if ($AllowRestrictedSampleData) {
  $sampleBuildArgs.AllowRestrictedSampleData = $true
}

& (Join-Path $PSScriptRoot "build-bundled-sample-workspace.ps1") @sampleBuildArgs
if ($LASTEXITCODE -ne 0) {
  throw "Failed to build the bundled sample workspace."
}

if (-not (Test-Path $bundledWorkspaceDir) -or -not (Test-Path $bundledWorkspaceManifest)) {
  throw "Missing bundled sample workspace or manifest. Run .\scripts\build-bundled-sample-workspace.ps1 before building."
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
    --hidden-import uvicorn.lifespan.on `
    --hidden-import uvicorn.loops.asyncio `
    --hidden-import uvicorn.protocols.http.h11_impl `
    --add-data "$engineRoot\app\builtin_dictionary_sources;app\builtin_dictionary_sources" `
    --add-data "$bundledWorkspaceDir;app\bundled_sample_workspace" `
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
