param(
  [string]$OutputDir = "src-tauri/resources/windows"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Step {
  param([string]$Message)
  Write-Host "==> $Message" -ForegroundColor Cyan
}

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$outputPath = Join-Path $root $OutputDir
$specPath = Join-Path $root "build/windows/pyinstaller-spec"
$workPath = Join-Path $root "build/windows/pyinstaller-build"
$distPath = Join-Path $root "build/windows/pyinstaller-dist"

New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
New-Item -ItemType Directory -Path $specPath -Force | Out-Null
New-Item -ItemType Directory -Path $workPath -Force | Out-Null
New-Item -ItemType Directory -Path $distPath -Force | Out-Null

Push-Location $root
try {
  Write-Step "Installing backend packaging dependencies"
  python -m pip install --upgrade pip
  python -m pip install -r backend/requirements.txt pyinstaller

  Write-Step "Building Caret backend sidecar"
  python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name caret-backend `
    --distpath "$distPath" `
    --workpath "$workPath" `
    --specpath "$specPath" `
    --paths backend `
    --hidden-import uvicorn.logging `
    --hidden-import uvicorn.loops.auto `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import uvicorn.protocols.websockets.auto `
    --hidden-import uvicorn.lifespan.on `
    --hidden-import aiosqlite `
    --hidden-import litellm `
    backend/windows_entry.py

  Copy-Item "$distPath/caret-backend.exe" "$outputPath/caret-backend.exe" -Force
  "generated-by-build-backend" | Set-Content "$outputPath/caret-backend.manifest"
} finally {
  Pop-Location
}
