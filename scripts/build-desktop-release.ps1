param(
  [Nullable[int]]$RowLimit = $null,
  [string]$WosSeed = "",
  [string]$IncopatSeed = "",
  [string]$ScopusSeed = "",
  [switch]$AllowRestrictedSampleData
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot

Push-Location $projectRoot
try {
  npm run config:check
  if ($LASTEXITCODE -ne 0) {
    throw "Desktop release build stopped because project config is out of sync."
  }

  $sidecarArgs = @{}
  if ($null -ne $RowLimit) {
    $sidecarArgs.RowLimit = $RowLimit
  }
  if ($WosSeed) {
    $sidecarArgs.WosSeed = $WosSeed
  }
  if ($IncopatSeed) {
    $sidecarArgs.IncopatSeed = $IncopatSeed
  }
  if ($ScopusSeed) {
    $sidecarArgs.ScopusSeed = $ScopusSeed
  }
  if ($AllowRestrictedSampleData) {
    $sidecarArgs.AllowRestrictedSampleData = $true
  }

  & (Join-Path $PSScriptRoot "build-python-sidecar.ps1") @sidecarArgs
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
