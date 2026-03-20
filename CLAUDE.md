# Abacus Meatspace - Matt's Financial Data Instance

This is the **data/deployment repo** for Matt Gates' Abacus instance.
The Abacus application source lives at `J:/QBO FOSS alternative`.

## Three Organizations

1. **Ridge Cell Repair LLC** - The business (digital services, ClawHub SaaS, LatchPac hardware, 3D printing, OpenClaw)
2. **Kalshi Trading** - Prediction market trading (weather, political, events)
3. **Personal - Matt Gates** - Personal finances

## Structure

- `seed_organizations.py` - Creates orgs + customized charts of accounts
- `docker-compose.yml` - Production deployment (references Abacus source as build context)
- `start-dev.ps1` / `start-dev.sh` - Local dev with SQLite
- `imports/` - Drop bank CSVs and receipts here for import
- `data/` - SQLite database (gitignored, contains real financial data)

## Quick Start (Windows)

```powershell
cp .env.example .env  # Edit with real values
.\start-dev.ps1       # Seeds DB on first run, starts API
```

## Important

- Real financial data is in `data/` - NEVER commit it
- Bank statements go in `imports/bank_statements/`
- Receipts go in `imports/receipts/`
- The seed script creates an admin user: matt@ridgecellrepair.com / changeme
