# Quick-start for local dev with SQLite (no Docker needed)
# Uses the Abacus source directly from the sibling directory

$ErrorActionPreference = "Stop"

$ABACUS_ROOT = if ($env:ABACUS_ROOT) { $env:ABACUS_ROOT } else { "..\QBO FOSS alternative" }
$DATA_DIR = Join-Path $PSScriptRoot "data"

New-Item -ItemType Directory -Force -Path $DATA_DIR | Out-Null
New-Item -ItemType Directory -Force -Path "imports\bank_statements" | Out-Null
New-Item -ItemType Directory -Force -Path "imports\receipts" | Out-Null

# Set up environment
$env:DATABASE_URL = "sqlite+aiosqlite:///$DATA_DIR/ridge_cell_repair.db"
$env:SECRET_KEY = if ($env:SECRET_KEY) { $env:SECRET_KEY } else { "dev-only-change-in-prod" }
$env:DEBUG = "true"
$env:ABACUS_ROOT = $ABACUS_ROOT

# Check if DB exists, seed if not
$dbPath = Join-Path $DATA_DIR "ridge_cell_repair.db"
if (-not (Test-Path $dbPath)) {
    Write-Host "First run - seeding database with Ridge Cell Repair chart of accounts..." -ForegroundColor Cyan
    Push-Location $ABACUS_ROOT
    pip install -r requirements.txt -q 2>$null
    Pop-Location
    python seed_organizations.py
    Write-Host ""
}

# Start Abacus API
Write-Host "Starting Abacus API on http://localhost:8000" -ForegroundColor Green
Write-Host "Organizations: Ridge Cell Repair LLC | Kalshi Trading | Personal" -ForegroundColor Yellow
Write-Host ""
Push-Location $ABACUS_ROOT
python -m uvicorn abacus.main:app --reload --host 0.0.0.0 --port 8000
Pop-Location
