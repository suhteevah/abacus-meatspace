import httpx, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

tok = httpx.post("http://127.0.0.1:8000/api/auth/login",
                 json={"email":"matt@ridgecellrepair.com","password":"changeme"}).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}

for rt in ("profit-loss", "trial-balance", "balance-sheet"):
    body = {
        "report_type": rt,
        "start_date": "2025-12-01",
        "end_date": "2026-03-31",
        "as_of_date": "2026-03-31",
    }
    r = httpx.post(f"http://127.0.0.1:8000/api/reports/{rt}",
                   json=body, headers=h, timeout=30)
    print(f"=== {rt}  status={r.status_code} ===")
    if r.status_code != 200:
        print(r.text[:500])
        continue
    d = r.json()
    print(" keys:", list(d.keys()))
    for k, v in d.items():
        if isinstance(v, (int, float, str)):
            print(f"   {k}: {v}")
        elif isinstance(v, dict) and "total" in v:
            print(f"   {k}.total: {v['total']}")
    # If there's a line items section, print top rows
    for k in ("revenue", "expenses", "line_items", "accounts"):
        section = d.get(k)
        if isinstance(section, dict) and "accounts" in section:
            for a in section["accounts"][:8]:
                print(f"   {k}[{a.get('account_number','?')}] {a.get('account_name','?')}: {a.get('balance', a.get('amount', '?'))}")
        elif isinstance(section, list):
            for li in section[:8]:
                print(f"   {k}:", json.dumps(li, default=str)[:160])
