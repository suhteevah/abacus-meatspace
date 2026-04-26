# Abacus — CNC-Server Deployment Handoff

**Session:** 2026-04-23 → early 2026-04-24, then 2026-04-25 (integration sprint)
**Author:** Opus 4.7 (Claude Code session on kokonoe)

> **✅ PerformanceTracker integration request fulfilled (2026-04-25).**
> Live at `https://cnc-server.tailb85819.ts.net/abacus/api/v1/`. Auth: `X-API-Key` header.
> Endpoints: `/health`, `/orgs`, `/revenue`, `/spending`. systemd unit `abacus-api.service`
> running on CNC. API keys for both iOS apps in `J:/abacus-meatspace/.secrets/integration-keys.json`.
> See "v1 Integration API (2026-04-25)" section below for full details.
> Deferred: `/clients` (no Vendor model yet) and `/kalshi/pnl` (separate system).

## v1 Integration API (2026-04-25)

### What shipped this session
- **New module:** `abacus/api/integrations.py` — versioned `/api/v1/*` read-only endpoints
- **Routes mounted in `main.py`** under `/api/v1` prefix
- **Synced to CNC:** `/opt/abacus/src/abacus/api/integrations.py` + updated `main.py`
- **systemd unit:** `/etc/systemd/system/abacus-api.service` — enabled + active, `--host 127.0.0.1 --port 8000`
- **Logs:** `/opt/abacus/logs/uvicorn.log` (append mode, both stdout + stderr)
- **Tailscale serve:** `/abacus` → `http://127.0.0.1:8000` (path prefix is stripped by tailscale)
- **API keys minted:** PerformanceTracker iOS + Abacus iOS, stored in `J:/abacus-meatspace/.secrets/integration-keys.json` (gitignored)

### Endpoint reference
Base: `https://cnc-server.tailb85819.ts.net/abacus/api/v1`
Auth: `X-API-Key: ol_...` (admin role required for cross-org reads)

| Method | Path | Query | Notes |
|--------|------|-------|-------|
| GET | `/health` | — | Liveness + txn count + last-import date |
| GET | `/orgs` | — | All orgs for admin; user's own org otherwise |
| GET | `/revenue` | `since`, `until`, `org_id?`, `include_entries?` | Revenue total + optional per-entry detail |
| GET | `/spending` | `since`, `until`, `org_id?` | Expense total + by-account breakdown |

`org_id` is the UUID from `/orgs`. If omitted, falls back to caller's primary org. Admin keys can pass any org_id.

### Smoke-test results (2026-04-25 18:08 PT)
- `/health` → 200, 308 transactions, last txn 2026-03-31
- `/orgs` → 3 orgs (Kalshi Trading, Personal - Matt Gates, Ridge Cell Repair LLC)
- `/revenue?since=2026-01-01&until=2026-04-25` (Personal) → $348.18 YTD
- `/spending?since=2026-04-01&until=2026-04-25` (Personal) → $0 (April has no posted expense entries — possibly because the 81 review-queue txns include April spending that hasn't been classified/posted yet; LLM pass when P100s land will fix)

### What PerformanceTracker session needs to do next
1. Read `INTEGRATION-REQUEST-PERFORMANCETRACKER.md` (still authoritative for what to consume)
2. Create `AbacusService.swift` in `J:\fitness\PerformanceTracker\` using the URL + key from `.secrets/integration-keys.json`
3. Wire it into the grading engine as the Revenue (20%) + Strategy (5%) signal source
4. Manual entry path stays as fallback when Tailscale unreachable

### What the existing Abacus iOS app needs
- The shell at `J:/QBO FOSS alternative/ios/Abacus/` is already wired for `X-API-Key` (`Data/Remote/AuthInterceptor.swift:6`). It uses Keychain-stored `serverUrl` + `apiKey` set via the `ServerSetupView` on first launch.
- **First-run config on Matt's iPhone:**
  - Server URL: `https://cnc-server.tailb85819.ts.net/abacus`
  - API key: the `abacus_ios` raw_key from `.secrets/integration-keys.json`
  - Tailscale must be active on the iPhone
- **Building it:** requires Mac (Xcode). Project structure exists; out-of-scope for this Windows session.

### Tech debt / follow-ups
- **Vendor/Customer model still missing** — blocks `/v1/clients` endpoint
- **CORS wildcard active in DEBUG mode on CNC** — fine because tailnet-only, but flip `DEBUG=false` in `/opt/abacus/.env` and restart `abacus-api` once the iOS apps don't need `/docs` open
- **No rate limiting on /v1/*** — single-user system, low priority, but consider if tokens ever leak
- **/kalshi/pnl deferred** — would need a Kalshi positions-tracking pipeline that doesn't exist yet
- **Admin password still `changeme`** — same as prior handoff, rotate via `maintenance.py`

### Quick commands
```bash
# On CNC: service control
systemctl status abacus-api
systemctl restart abacus-api
journalctl -u abacus-api -f
tail -f /opt/abacus/logs/uvicorn.log

# On kokonoe: re-sync after edits
scp "J:/QBO FOSS alternative/abacus/api/integrations.py" root@192.168.168.100:/opt/abacus/src/abacus/api/integrations.py
ssh root@192.168.168.100 "systemctl restart abacus-api"

# Smoke test from any tailnet device (PowerShell)
$h = @{ "X-API-Key" = "<key from .secrets/integration-keys.json>" }
Invoke-WebRequest -UseBasicParsing -Uri "https://cnc-server.tailb85819.ts.net/abacus/api/v1/health" -Headers $h
```

---

## What's done

### On kokonoe (J:\abacus-meatspace\ + J:\QBO FOSS alternative\)
- PDF bank-statement parser for Golden 1 CU, nbkc bank, DoorDash Crimson (`pdf_import.py`)
- 10 statements → 308 transactions imported
- Rule-based classifier (`abacus/classifier.py`) covering ~80% of known merchants
- Claude.ai session-cookie LLM bridge (`abacus/claude_ai_client.py`) — zero-cost classification via Matt's Claude Max
- OAuth-aware AI client rewrite (`abacus/ai_service.py` — prefers OAuth token when set, falls back to API key)
- Config fields for OAuth + claude.ai session cookie paths (`abacus/config.py`)
- Full pipeline ran via Chrome CDP + claude-in-chrome MCP: 308/308 classified, 267 journal entries posted, P&L/Balance Sheet/Trial Balance live via REST API
- API + frontend running at **http://localhost:8000** / **http://localhost:3000**
  - Login: `matt@ridgecellrepair.com` / `changeme`
  - Admin user was reassigned from RCR org to Personal org

### On CNC-Server (192.168.168.100, /opt/abacus/)
- Full Python backend synced via scp (GitHub repo was 55 commits behind — needs push)
- SQLite DB at `/opt/abacus/data/ridge_cell_repair.db` (was going to be PG but Alembic migrations have SQLite-isms that PG rejects — deferred)
- All 10 PDFs synced to `/opt/abacus/imports/bank_statements/`
- Seeded 3 orgs, 157 accounts, admin user (moved to Personal org)
- Rule-classified 250/308, posted 227 journal entries
- Restic (existing on CNC) covers `/opt/` daily at 2am — Abacus data backed up automatically
- `cnc_pipeline.sh` at `/opt/abacus/bin/` runs the full weekly review
- `cnc_status.py` at `/opt/abacus/bin/` dumps DB state

### Current CNC state
```
organizations          3
bank_transactions      308
journal_entries        227 (160 auto-approved, 67 draft)
journal_line_items     454   (balanced double-entry)
accounts               157
review_queue           81 (58 unclassified + 23 low-confidence)
```

## What's left (tomorrow when P100s land)

### P100 LLM backend (high priority)
- When the P100s arrive: install CUDA, stand up llama-server with a 70B-class model on localhost:8080
- Abacus LLM backend already has the claude.ai path; add `openai_compat` backend to point at `http://localhost:8080/v1/chat/completions`
- Config flip: `LLM_BACKEND=openai_compat LLM_BASE_URL=http://127.0.0.1:8080/v1`
- Once this works, run LLM pass on the 58 unclassified → another ~50 entries post

### Frontend + Tailscale (medium priority)
- Frontend not yet deployed on CNC. Two paths:
  - (a) Build static files with `npm run build` on CNC, serve via nginx or caddy
  - (b) Run `npm run dev` with vite proxy to API — heavier, dev-only
- Tailscale serve config: expose at `https://cnc-server.tailb85819.ts.net/abacus/`
  - **Rule: Tailscale-only, no LAN/WAN. Financial data.**

### Weekly automation (medium priority)
- systemd timer: `/etc/systemd/system/abacus-weekly.timer` Mondays 10am local (`OnCalendar=Mon 10:00 America/Los_Angeles`)
- Service unit calls `/opt/abacus/bin/cnc_pipeline.sh`
- Telegram notifier: port `/j/baremetal claude/tools/notify-telegram.sh` + the `.env` with bot token/chat_id to `/opt/abacus/bin/`
- Weekly summary: "N new txns, +$X income, -$Y spend, Z need review"

### Statement intake — Syncthing share (low priority)
- Set up shared folder `J:\abacus-meatspace\imports\` ↔ `/opt/abacus/imports/`
- kokonoe needs syncthing client (not currently running — verify)
- Until this lands, Matt drops PDFs manually and rsyncs to CNC (or we use scp as we did tonight)

### Tech debt
- **GitHub push needed.** Kokonoe local is 55 commits ahead of `origin/main`. Push whenever Matt is ready to publish.
- **Alembic migrations are SQLite-only.** The `BOOLEAN DEFAULT '0'` syntax breaks PG. Needs: either per-dialect migration logic, or switch migrations to emit dialect-neutral SQL (e.g., `DEFAULT FALSE`).
- **41 review-queue txns** (on kokonoe's run) / **81 on CNC** — need LLM pass or manual review in the UI.
- **Admin password is still `changeme` on CNC.** Rotate via:
  ```
  ssh root@192.168.168.100
  export NEW_ADMIN_PASSWORD='...'; cd /opt/abacus
  set -a; source .env; set +a
  export PYTHONPATH=/opt/abacus/src ABACUS_ROOT=/opt/abacus/src
  /opt/abacus/venv/bin/python maintenance.py
  ```
- **Semgrep hook noise on ai_service.py:292** — pre-existing NL-query `text(sql + " LIMIT 200")` pattern trips CWE-89 on every edit to that file. Real fix: refactor NL-query to emit SQLAlchemy expression objects instead of raw SQL.

## Quick commands (CNC)

```bash
# Re-run the full pipeline after dropping new PDFs
/opt/abacus/bin/cnc_pipeline.sh

# Status dump
/opt/abacus/venv/bin/python /opt/abacus/bin/cnc_status.py

# Start the API (not running as systemd yet)
cd /opt/abacus
set -a; source .env; set +a
export PYTHONPATH=/opt/abacus/src ABACUS_ROOT=/opt/abacus/src
/opt/abacus/venv/bin/python -m uvicorn abacus.main:app --host 127.0.0.1 --port 8000

# Postgres cleanup (if deciding to switch back)
podman ps -a --filter name=abacus-postgres   # container was stopped + removed
# PG password still in /opt/abacus/data/pg_password.txt if needed
```

## Structural decisions made this session

1. **Finance data stays Tailscale-only.** No public domain, no LAN exposure.
2. **CNC over kokonoe** — kokonoe is dev, gets reinstalled. Abacus needs prod stability.
3. **SQLite for now on CNC**, not PG — Alembic migration incompatibility is a ratholed fix.
4. **LLM backend stays pluggable.** Browser-tab claude.ai (kokonoe manual) for now; P100 llama-server when GPUs land; Anthropic API as paid fallback.
5. **Restic daily backup of /opt/** covers Abacus data — no separate backup system.
6. **Per-org dedicated PG rejected** in favor of SQLite simplicity until scale demands it.

## The bigger picture

**Matt's 90-day financial diagnosis:** Base income ~$3,050/mo W-2 (Gusto). DoorDash peaked at ~$1,000/mo Nov-Jan, then went dark Feb-Mar. Rent $1,750/mo = 48% of primary income. Monthly net hovers ±$500, mostly break-even. The structural problem is rent + dead business ventures (ClawHub/LatchPac/OpenClaw/3D) burning ~$200/mo in tools with zero revenue to deduct against. Biggest unlock: get DoorDash consistency back to $1K/mo pace OR ship a revenue-producing product.

Full analysis in this session's transcript; spending patterns captured in Abacus ledger on CNC.
