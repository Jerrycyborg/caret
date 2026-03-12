param(
  [string]$InstallRoot = "$env:LOCALAPPDATA\Caret",
  [switch]$SkipPrerequisites
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
  param([string]$Message)
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-CommandExists {
  param([string]$Name)
  return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Install-WingetPackage {
  param(
    [string]$Id,
    [string]$DisplayName
  )

  if (-not (Test-CommandExists "winget")) {
    throw "winget is required to install missing prerequisite: $DisplayName"
  }

  Write-Step "Installing $DisplayName"
  winget install -e --id $Id --accept-package-agreements --accept-source-agreements --silent
}

function Ensure-Prerequisites {
  if ($SkipPrerequisites) {
    Write-Step "Skipping prerequisite installation"
    return
  }

  if (-not (Test-CommandExists "node")) {
    Install-WingetPackage -Id "OpenJS.NodeJS.LTS" -DisplayName "Node.js LTS"
  }

  if (-not (Test-CommandExists "python")) {
    Install-WingetPackage -Id "Python.Python.3.11" -DisplayName "Python 3.11"
  }

  if (-not (Test-CommandExists "cargo")) {
    Install-WingetPackage -Id "Rustlang.Rustup" -DisplayName "Rustup"
  }

  if (-not (Test-Path "$env:USERPROFILE\.cargo\bin\cargo.exe")) {
    throw "Rust installation did not expose cargo.exe under $env:USERPROFILE\.cargo\bin"
  }

  if (-not ($env:Path -split ";" | Where-Object { $_ -eq "$env:USERPROFILE\.cargo\bin" })) {
    $env:Path += ";$env:USERPROFILE\.cargo\bin"
  }

  if (-not (Test-CommandExists "git")) {
    Install-WingetPackage -Id "Git.Git" -DisplayName "Git"
  }

  try {
    Get-Command "msedgewebview2.exe" -ErrorAction Stop | Out-Null
  } catch {
    Install-WingetPackage -Id "Microsoft.EdgeWebView2Runtime" -DisplayName "Microsoft Edge WebView2 Runtime"
  }
}

function Copy-EnvIfMissing {
  param([string]$RepoRoot)

  $envFile = Join-Path $RepoRoot ".env"
  $exampleFile = Join-Path $RepoRoot ".env.example"
  if ((-not (Test-Path $envFile)) -and (Test-Path $exampleFile)) {
    Write-Step "Creating .env from .env.example"
    Copy-Item $exampleFile $envFile
  }
}

function Get-RepoRoot {
  $candidate = Resolve-Path (Join-Path $PSScriptRoot "..\..")
  if (-not (Test-Path (Join-Path $candidate "package.json"))) {
    throw "Could not resolve repo root from script location."
  }
  return $candidate.Path
}

function Install-Caret {
  param([string]$RepoRoot)

  New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
  Copy-EnvIfMissing -RepoRoot $RepoRoot

  Push-Location $RepoRoot
  try {
    Write-Step "Installing npm dependencies"
    npm install

    Write-Step "Building Windows installer"
    npm run windows:package

    $msi = Get-ChildItem -Path (Join-Path $RepoRoot "src-tauri\target\release\bundle\msi") -Filter "*.msi" |
      Sort-Object LastWriteTime -Descending |
      Select-Object -First 1

    if ($null -eq $msi) {
      throw "No MSI artifact was produced."
    }

    Write-Step "Installing $($msi.Name)"
    Start-Process msiexec.exe -ArgumentList @("/i", $msi.FullName, "/passive") -Wait

    $installedExe = Get-ChildItem -Path "$env:LOCALAPPDATA\Programs" -Filter "Caret.exe" -Recurse -ErrorAction SilentlyContinue |
      Select-Object -First 1

    if ($null -ne $installedExe) {
      Write-Step "Launching Caret"
      Start-Process $installedExe.FullName
    } else {
      Write-Step "Caret installed. Launch it from the Start menu if it does not open automatically."
    }
  } finally {
    Pop-Location
  }
}

$repoRoot = Get-RepoRoot
Ensure-Prerequisites
Install-Caret -RepoRoot $repoRoot
