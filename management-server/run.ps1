# Caret Management Server — launch script
# Usage: .\run.ps1
# Or with token: $env:CARET_MANAGEMENT_TOKEN='secret'; .\run.ps1

param(
    [string]$Token = $env:CARET_MANAGEMENT_TOKEN,
    [int]$Port = 8100,
    [string]$DbPath = "fleet.db"
)

$env:CARET_MANAGEMENT_TOKEN = $Token
$env:CARET_SERVER_PORT = $Port
$env:CARET_DB_PATH = $DbPath

Set-Location $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python not found. Install Python 3.11+ and retry."
    exit 1
}

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}

Write-Host "Installing dependencies..." -ForegroundColor Cyan
& .venv\Scripts\pip install -q -r requirements.txt

Write-Host "Starting Caret Management Server on port $Port..." -ForegroundColor Green
& .venv\Scripts\python server.py
