#!/bin/bash
# Quick-start for local dev with SQLite (no Docker needed)
# Uses the Abacus source directly from the sibling directory

set -e

ABACUS_ROOT="${ABACUS_ROOT:-../QBO FOSS alternative}"
DATA_DIR="$(pwd)/data"

mkdir -p "$DATA_DIR"
mkdir -p imports/bank_statements imports/receipts

# Set up environment
export DATABASE_URL="sqlite+aiosqlite:///${DATA_DIR}/ridge_cell_repair.db"
export SECRET_KEY="${SECRET_KEY:-dev-only-change-in-prod}"
export DEBUG=true
export ABACUS_ROOT

# Check if DB exists, seed if not
if [ ! -f "${DATA_DIR}/ridge_cell_repair.db" ]; then
    echo "First run - seeding database with Ridge Cell Repair chart of accounts..."
    cd "$ABACUS_ROOT"
    pip install -r requirements.txt -q 2>/dev/null || true
    cd -
    python seed_organizations.py
    echo ""
fi

# Start Abacus API
echo "Starting Abacus API on http://localhost:8000"
echo "Organizations: Ridge Cell Repair LLC | Kalshi Trading | Personal"
echo ""
cd "$ABACUS_ROOT"
python -m uvicorn abacus.main:app --reload --host 0.0.0.0 --port 8000
