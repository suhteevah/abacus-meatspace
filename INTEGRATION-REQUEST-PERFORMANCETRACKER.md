# Integration Request — PerformanceTracker iOS App

**From:** PerformanceTracker session (J:\fitness)
**To:** Abacus session (J:\abacus-meatspace, J:\QBO FOSS alternative)
**Drafted:** 2026-04-25
**Status:** Inbound request — Abacus session owns implementation

## What this is

PerformanceTracker is a Phase-1.5 iOS + Apple Watch app at `J:\fitness\` that grades Matt's weekly performance across 7 categories. Two of those categories — **Revenue & Pipeline** (20% weight) and **Strategic Decision-Making** (5% weight) — need real financial signal to be graded. We want to consume that signal from Abacus.

The PerformanceTracker app is **already built and installed on Matt's iPhone 17 Pro Max + Watch Ultra 3**. It currently uses manual entry for Revenue. Once Abacus exposes an API, PerformanceTracker will switch to consuming that as primary, with manual entry as override/supplement.

## Architectural rule (Matt's directive)

> Abacus is financial data — keep it FULLY on tailnet. No LAN/WAN exposure.

This is non-negotiable. iOS app will require Tailscale on the phone to query Abacus. PerformanceTracker has a graceful-degradation path: when Abacus isn't reachable, it falls back to local manual entries.

## What PerformanceTracker needs (the contract)

### 1. Tailscale-served HTTPS endpoint

We need Abacus's REST API exposed at a stable Tailscale URL, e.g.:

```
https://cnc-server.tailb85819.ts.net/abacus/api/...
```

The existing tailscale serve config on cnc-server already has `/`, `/api`, `/home`, `/uptime`, `/syncthing`, `/prometheus`. Adding `/abacus` to that list is the proposed shape:

```
sudo tailscale serve --bg --https=443 /abacus proxy http://127.0.0.1:8000
```

(Or whatever port the Abacus uvicorn lands on — last HANDOFF said it was running locally on port 8000 during dev, not yet started on cnc-server prod.)

### 2. Auth model

PerformanceTracker stores any auth credentials in iOS Keychain. We can support whatever Abacus chooses, but in priority order:

| Auth type | Notes |
|-----------|-------|
| **Bearer token (preferred)** | One token per device, generated server-side, revocable per-device. Simple iOS-side: `Authorization: Bearer <token>`. |
| **Tailscale identity (cleanest)** | Trust any caller that's on the tailnet (since it's already authenticated by Tailscale). No per-device tokens. Requires Abacus middleware to read the `Tailscale-User-*` headers `tailscale serve` injects. |
| **OAuth2 PKCE** | If Abacus already has OAuth wired in (HANDOFF mentioned `_oauth_probe.py` and OAuth-aware AI client). Heavier client work. |
| **Session cookie** | Last resort. Hard to do well from a mobile app. Rather not. |

**My vote: Tailscale identity.** Matt's already trusting the tailnet; piggybacking on that is the least friction. If Abacus session disagrees, bearer token is fine.

### 3. Required endpoints

In priority order (PerformanceTracker can ship with just #1 and #2; #3-5 are nice-to-haves).

#### Required for Phase 1.5

**`GET /abacus/api/orgs`** — list organizations
```json
[
  {"id": 1, "name": "Ridge Cell Repair LLC", "slug": "rcr"},
  {"id": 2, "name": "Kalshi Trading", "slug": "kalshi"},
  {"id": 3, "name": "Personal - Matt Gates", "slug": "personal"}
]
```

**`GET /abacus/api/revenue?org_id=1&since=2026-04-19&until=2026-04-25`** — revenue for a period
```json
{
  "org_id": 1,
  "period_start": "2026-04-19",
  "period_end": "2026-04-25",
  "total_usd": 0.00,
  "entries": [
    {
      "date": "2026-04-22",
      "amount_usd": 550.00,
      "client_name": "Brander Group",
      "source": "wire_transfer",
      "memo": "Vox Spectre delivery"
    }
  ]
}
```

If `entries[]` is too revealing for a mobile context, just `total_usd` + a count is enough. Detail is a nice-to-have.

#### Nice-to-have

**`GET /abacus/api/kalshi/pnl`** — Kalshi P&L snapshot
```json
{
  "as_of": "2026-04-25T18:00:00Z",
  "total_pnl_usd": 12450.00,
  "weekly_change_pct": 4.2,
  "open_positions_count": 7
}
```

**`GET /abacus/api/spending?org_id=1&since=...&until=...`** — burn rate
```json
{
  "total_usd": 1820.00,
  "by_category": {
    "infrastructure": 412.00,
    "subscriptions": 180.00,
    "food": 645.00,
    "other": 583.00
  }
}
```

**`GET /abacus/api/clients?org_id=1`** — active clients with last-payment dates
```json
[
  {"name": "Incognito Acquisitions", "last_payment_date": null, "active_engagement": true},
  {"name": "First Choice Plastics", "last_payment_date": null, "active_engagement": true}
]
```

This one is gold for the Client Work category. Maps directly to PerformanceTracker's `ClientEntry` model.

**`GET /abacus/api/health`** — service health
```json
{ "status": "ok", "db_transactions_count": 308, "last_import": "2026-04-23T11:00:00Z" }
```

For PerformanceTracker's Settings UI to show "Abacus connected · 308 transactions".

### 4. Schema stability

Once these endpoints ship, we'd like a versioned URL prefix (`/abacus/api/v1/...`) so we can evolve without breaking the iOS app. Mobile app updates lag because of Apple's free-team 7-day provisioning expiry.

### 5. CORS / mobile concerns (probably not needed)

Tailscale serve handles TLS. iOS uses `URLSession` against the served endpoint directly. No CORS issue (native client, not a browser). No special mobile concerns beyond keeping responses small (< 100 KB per call ideally).

## What PerformanceTracker will do with this data

- **Revenue grade** (currently 20% category weight): replace manual-entry-only path with Abacus revenue total per period.
- **Strategy grade** (5%): use revenue trend + Kalshi P&L delta as one of several signals.
- **Client Work grade** (15%): cross-reference Abacus's active clients with PerformanceTracker's project-status data (already harvested by 11pm Claude routine from `J:\` repos + HANDOFF.md files).
- **Dashboard tile**: add a "Finance" card showing weekly revenue + Kalshi P&L + burn rate at a glance.
- **Notification**: optional iOS local notification on revenue events ("Brander Group: $550 received").

## Suggested scope for the Abacus session

If you (Abacus session) want to scope this minimally:

1. Bring Abacus uvicorn up as a systemd service on cnc-server — referenced in HANDOFF.md as "medium priority/unfinished"
2. Add `tailscale serve` route for `/abacus`
3. Implement endpoints #1 (`/orgs`) and #2 (`/revenue`) — that's enough for PerformanceTracker to start consuming
4. Decide auth model and document it back here

Steps 1-3 plus a bearer-token auth = ~2 hours of focused work per the HANDOFF.md.

## How PerformanceTracker session will know this is done

When the Abacus session updates `J:\abacus-meatspace\HANDOFF.md` with:
- "Abacus exposed at https://cnc-server.tailb85819.ts.net/abacus/"
- Auth model + how to get a token / how Tailscale identity is read
- Confirmed endpoints `GET /abacus/api/orgs` and `GET /abacus/api/revenue` return real data

…the PerformanceTracker session will pick up the work to build the iOS-side `AbacusService.swift` and wire it into the grading engine.

## Reference points

- PerformanceTracker rubric source of truth: `J:\fitness\docs\GRADING-RUBRIC.md` (sections 2 "Revenue & Pipeline" and 4 "Client Work" describe what we need)
- PerformanceTracker daily-data routine schemas: `J:\fitness\docs\DAILY-DATA-ROUTINE.md` (the JSON shape we'd accept if you'd rather have the routine harvest Abacus and write `data/financial-daily/*.json` instead of building live API)
- Existing Abacus HANDOFF: `J:\abacus-meatspace\HANDOFF.md`
- iMac stability investigation (which got us this far) lives in `J:\llm-wiki\fleet\iMac.md` — irrelevant to Abacus but explains why the iOS client can be SSH-built now

## Alternative path: 11pm routine snapshot instead of live API

If standing up the Tailscale-served live API is more work than Abacus session wants right now, an **interim** option is for the existing 11pm Claude routine to query Abacus's local CLI / SQLite directly and write `J:\fitness\data\financial-daily\YYYY-MM-DD.json` matching this schema:

```json
{
  "schema": "financial-daily.v1",
  "date": "2026-04-25",
  "captured_at": "2026-04-25T23:00:00-07:00",
  "orgs": {
    "rcr":       { "revenue_today": 0,    "revenue_week": 0,    "active_clients": 2 },
    "kalshi":    { "pnl_total_usd": 12450, "weekly_change_pct": 4.2, "open_positions": 7 },
    "personal":  { "spend_today": 87,     "spend_week": 412 }
  }
}
```

This is **just as useful** for grading purposes, and zero infrastructure work. Live API is nicer for Settings UI / on-demand queries but not strictly required for the assessment engine.

## Out of scope for this request

- Health data (separate pipeline; Claude connectors → 11pm routine → `data/health-daily/*.json`)
- Project-status data (separate; same routine harvests `J:\` repos)
- Authentication of PerformanceTracker users (single-user app, Matt only — no multi-user complexity)

---

Ping back via this file or by updating `HANDOFF.md` when you want me (PerformanceTracker session) to consume this.
