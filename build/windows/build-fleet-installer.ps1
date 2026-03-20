# Caret Fleet Installer Builder
# Prompts for org config, builds a self-contained fleet installer EXE.
# Requires NSIS installed: https://nsis.sourceforge.io/
#
# Usage: .\build-fleet-installer.ps1
# Or with params:
#   .\build-fleet-installer.ps1 `
#     -ManagementUrl "https://caret.tws-partners.com/admin" `
#     -ManagementToken "secret" `
#     -AdminGroup "ROL-ADM-Admins" `
#     -OrgName "TWS Partners AG"

param(
    [string]$ManagementUrl   = $env:CARET_MANAGEMENT_SERVER_URL,
    [string]$ManagementToken = $env:CARET_MANAGEMENT_TOKEN,
    [string]$AdminGroup      = $env:CARET_ADMIN_GROUP,
    [string]$OrgName         = $env:CARET_ORG_NAME,
    [string]$EnvLabel        = $env:CARET_ENV_LABEL,
    [string]$JiraProjectKey  = $env:CARET_JIRA_PROJECT_KEY
)

# Prompt for any missing required values
if (-not $ManagementUrl) {
    $ManagementUrl = Read-Host "Management server URL (e.g. https://caret.tws-partners.com/admin)"
}
if (-not $ManagementToken) {
    $ManagementToken = Read-Host "Management token (bearer secret)"
}
if (-not $AdminGroup) {
    $AdminGroup = Read-Host "AD admin group SAM name (leave blank for local admin)"
}
if (-not $OrgName) {
    $OrgName = Read-Host "Org name (e.g. TWS Partners AG)"
}

# Find NSIS
$makensis = Get-Command makensis -ErrorAction SilentlyContinue
if (-not $makensis) {
    $makensis = "C:\Program Files (x86)\NSIS\makensis.exe"
    if (-not (Test-Path $makensis)) {
        Write-Error "NSIS not found. Install from https://nsis.sourceforge.io/ and retry."
        exit 1
    }
}

$nsiScript   = "$PSScriptRoot\fleet-installer.nsi"
$distDir     = "$PSScriptRoot\..\..\dist"
$baseInstaller = "$distDir\Caret_0.1.9_x64-setup.exe"
$cargoInstaller = "C:\Users\lawrencem\cargo-targets\caret\release\bundle\nsis\Caret_0.1.9_x64-setup.exe"

# Copy base installer into dist/ if not already there
if (-not (Test-Path $baseInstaller)) {
    if (Test-Path $cargoInstaller) {
        Copy-Item $cargoInstaller $baseInstaller
        Write-Host "Copied base installer to dist\" -ForegroundColor Gray
    } else {
        Write-Error "Base installer not found at:`n  $cargoInstaller`nRun a full package build first."
        exit 1
    }
}

Write-Host ""
Write-Host "Building Caret Fleet Installer..." -ForegroundColor Cyan
Write-Host "  Management URL : $ManagementUrl"
Write-Host "  Admin group    : $(if ($AdminGroup) { $AdminGroup } else { '(local admin)' })"
Write-Host "  Org name       : $OrgName"
Write-Host ""

& $makensis `
    /DMANAGEMENT_URL="$ManagementUrl" `
    /DMANAGEMENT_TOKEN="$ManagementToken" `
    /DADMIN_GROUP="$AdminGroup" `
    /DORG_NAME="$OrgName" `
    /DENV_LABEL="$EnvLabel" `
    /DJIRA_PROJECT_KEY="$JiraProjectKey" `
    $nsiScript

if ($LASTEXITCODE -eq 0) {
    $output = "$PSScriptRoot\Caret-Fleet-Setup.exe"
    Write-Host ""
    Write-Host "Fleet installer built:" -ForegroundColor Green
    Write-Host "  $output"
    Write-Host ""
    Write-Host "Deploy via GPO, Intune, PDQ Deploy, or SCCM:"
    Write-Host "  Caret-Fleet-Setup.exe /S"
} else {
    Write-Error "Build failed (exit code $LASTEXITCODE)"
    exit 1
}
