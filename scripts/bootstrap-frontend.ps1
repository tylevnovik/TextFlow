$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$cacheRoot = Join-Path $projectRoot ".npm-cache"
$tempRoot = Join-Path $projectRoot ".tmp\npm"

New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

$env:npm_config_cache = $cacheRoot
$env:TEMP = $tempRoot
$env:TMP = $tempRoot

Push-Location $projectRoot
try {
  npm install
}
finally {
  Pop-Location
}

Write-Host "Frontend dependencies installed with local cache at $cacheRoot"
