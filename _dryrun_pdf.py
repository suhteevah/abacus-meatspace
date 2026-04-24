import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from pdf_import import extract_pdf

for path in sys.argv[1:]:
    p = Path(path)
    fmt, txns = extract_pdf(p)
    print(f"\n=== {p.name} — format={fmt} — {len(txns)} txns ===")
    for t in txns:
        sign = "-" if t.amount < 0 else "+"
        print(f"  {t.date} {sign}{abs(t.amount):>10} | bal={t.balance} | {t.description[:80]}")
