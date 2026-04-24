import sys, pdfplumber
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
path, page_num = sys.argv[1], int(sys.argv[2])
with pdfplumber.open(path) as pdf:
    p = pdf.pages[page_num - 1]
    words = p.extract_words(keep_blank_chars=False, use_text_flow=False)
    # Group by y
    from itertools import groupby
    words.sort(key=lambda w: (round(w["top"]), w["x0"]))
    print(f"page {page_num}, {len(words)} words, width={p.width} height={p.height}")
    last_top = None
    line = []
    for w in words:
        top = round(w["top"])
        if last_top is None or abs(top - last_top) > 3:
            if line:
                print(" | ".join(f"{w['x0']:.0f}:{w['text']}" for w in line))
            line = [w]
            last_top = top
        else:
            line.append(w)
    if line:
        print(" | ".join(f"{w['x0']:.0f}:{w['text']}" for w in line))
