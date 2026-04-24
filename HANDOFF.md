# Abacus — CNC-Server Deployment Handoff

**Session:** 2026-04-23 → early 2026-04-24
**Author:** Opus 4.7 (Claude Code session on kokonoe)

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
