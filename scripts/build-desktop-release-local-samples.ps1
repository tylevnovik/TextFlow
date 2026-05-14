$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$seedRoot = Join-Path $projectRoot "sample_seed_sources"
if (-not (Test-Path $seedRoot)) {
  throw "Missing local sample seed folder: $seedRoot"
}

$wosSeedItem = Get-ChildItem -LiteralPath $seedRoot -File | Where-Object {
  $_.Extension -ieq ".xls" -and $_.Name -like "*wos*"
} | Select-Object -First 1
$incopatSeedItem = Get-ChildItem -LiteralPath $seedRoot -File | Where-Object {
  $_.Extension -ieq ".xlsx" -and $_.Name -notlike "*wos*" -and $_.Name -notlike "*scopus*"
} | Select-Object -First 1

if (-not $wosSeedItem) {
  throw "Missing local WoS sample seed matching *wos*.xls under $seedRoot"
}
if (-not $incopatSeedItem) {
  throw "Missing local IncoPat sample seed matching *.xlsx under $seedRoot"
}

& (Join-Path $PSScriptRoot "build-desktop-release.ps1") `
  -WosSeed $wosSeedItem.FullName `
  -IncopatSeed $incopatSeedItem.FullName `
  -AllowRestrictedSampleData
