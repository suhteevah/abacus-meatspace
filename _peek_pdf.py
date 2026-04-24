import sys, pdfplumber
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
path = sys.argv[1]
start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
end   = int(sys.argv[3]) if len(sys.argv) > 3 else 99
with pdfplumber.open(path) as pdf:
    print(f"=== {path} — {len(pdf.pages)} pages ===")
    for i, p in enumerate(pdf.pages, start=1):
        if i < start or i > end: continue
        print(f"\n--- page {i} TEXT ---")
        print((p.extract_text() or "")[:5000])
