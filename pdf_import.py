"""
PDF bank-statement importer for Matt's Abacus instance.

Handles formats we've seen so far:
  * Golden 1 Credit Union periodic statements (`dxweb*.pdf`)
  * nbkc bank / Gusto Spending monthly statements

Strategy: use pdfplumber word coordinates to split each line into
(date, description, withdrawal, deposit, balance) columns, then feed
the normalized rows into the existing TransactionImporter via an
in-memory CSV.

Usage:
  python pdf_import.py <org_prefix> <pdf_path> [pdf_path...]
  python pdf_import.py <org_prefix> --all      # imports everything in
                                                # imports/bank_statements/

<org_prefix>: rcr | kalshi | personal (prefix match on org name)
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ABACUS_ROOT = Path(os.environ.get("ABACUS_ROOT", "J:/QBO FOSS alternative"))
sys.path.insert(0, str(ABACUS_ROOT))
os.environ.setdefault("DEBUG", "true")

import pandas as pd
import pdfplumber
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from abacus.models import Organization
from abacus.importer import TransactionImporter

# ---------------------------------------------------------------------------
# DB setup (same as import_csv.py)
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{(DATA_DIR / 'ridge_cell_repair.db').as_posix()}",
)
engine_kwargs: dict = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_async_engine(DATABASE_URL, **engine_kwargs)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
@dataclass
class Txn:
    date: date
    description: str
    amount: Decimal
    balance: Decimal | None = None

    def to_row(self) -> dict:
        return {
            "date": self.date.isoformat(),
            "description": self.description,
            "amount": str(self.amount),
            "balance": str(self.balance) if self.balance is not None else "",
        }


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
_AMOUNT_RE = re.compile(r"^\(?-?\$?([\d,]+\.\d{2})\)?$")
_DATE_RE_SLASH = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")


def parse_amount(token: str, parens_negative: bool = False) -> Decimal | None:
    if not token or token in {"--", "-", "0", "0.00", "$0.00"}:
        return None
    m = _AMOUNT_RE.match(token)
    if not m:
        return None
    val = Decimal(m.group(1).replace(",", ""))
    if parens_negative and token.startswith("("):
        val = -val
    if token.startswith("-"):
        val = -val
    return val


def parse_date(token: str) -> date | None:
    if not _DATE_RE_SLASH.match(token):
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def group_lines(words: list[dict], tol: float = 3.0) -> list[list[dict]]:
    """Group words into lines by similar `top` coordinate."""
    words = sorted(words, key=lambda w: (round(w["top"]), w["x0"]))
    lines: list[list[dict]] = []
    for w in words:
        if lines and abs(w["top"] - lines[-1][-1]["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    for line in lines:
        line.sort(key=lambda w: w["x0"])
    return lines


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------
def detect_format(first_page_text: str) -> str | None:
    t = first_page_text.lower()
    if "nbkc bank" in t or "gusto spending" in t:
        return "nbkc"
    if "golden 1" in t or "golden1.com" in t:
        return "golden1"
    if "doordash crimson" in t or "dasher mobile app" in t:
        return "dasher"
    return None


# ---------------------------------------------------------------------------
# Golden 1 Credit Union parser
# ---------------------------------------------------------------------------
#
# Column x-coordinates (observed):
#   Post Date      ~43
#   Effective Date ~100
#   Description    ~170 .. <400
#   Withdrawals    ~400 .. 445   (negative; minus sign embedded)
#   Deposits       ~460 .. 510   (positive)
#   Balance        ~520 .. 560
#
# Each transaction is one line that starts with a date at x≈43, optionally
# followed by continuation lines at x≈170 with extra description.

G1_COL_WD_MIN = 395
G1_COL_WD_MAX = 448
G1_COL_DEP_MIN = 455
G1_COL_DEP_MAX = 512
G1_COL_BAL_MIN = 515
G1_COL_BAL_MAX = 570
G1_DESC_MIN = 165
G1_DESC_MAX = 390


def parse_golden1(pdf: pdfplumber.PDF) -> list[Txn]:
    txns: list[Txn] = []
    pending: Txn | None = None
    pending_continues = False

    def flush():
        nonlocal pending
        if pending is not None:
            txns.append(pending)
            pending = None

    for page in pdf.pages:
        words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
        for line in group_lines(words):
            tokens = line
            if not tokens:
                continue

            first = tokens[0]
            first_is_date_at_col1 = (first["x0"] < 60) and parse_date(first["text"])

            if first_is_date_at_col1:
                flush()

                post_date = parse_date(first["text"])
                # Optional effective date
                idx = 1
                if idx < len(tokens) and 85 < tokens[idx]["x0"] < 130 and parse_date(tokens[idx]["text"]):
                    idx += 1

                # Split remaining tokens by column
                desc_parts: list[str] = []
                wd_amt: Decimal | None = None
                dep_amt: Decimal | None = None
                bal_amt: Decimal | None = None

                for t in tokens[idx:]:
                    x = t["x0"]
                    text = t["text"]
                    if G1_COL_BAL_MIN <= x <= G1_COL_BAL_MAX:
                        amt = parse_amount(text)
                        if amt is not None:
                            bal_amt = amt
                            continue
                    if G1_COL_DEP_MIN <= x <= G1_COL_DEP_MAX:
                        amt = parse_amount(text)
                        if amt is not None:
                            dep_amt = amt
                            continue
                    if G1_COL_WD_MIN <= x <= G1_COL_WD_MAX:
                        amt = parse_amount(text)
                        if amt is not None:
                            # Already signed (minus embedded), but ensure negative
                            wd_amt = amt if amt < 0 else -amt
                            continue
                    if G1_DESC_MIN <= x <= G1_DESC_MAX:
                        # Skip the stray "0" filler Golden 1 inserts for empty amount cols
                        if text == "0":
                            continue
                        desc_parts.append(text)

                if wd_amt is None and dep_amt is None:
                    # "Beginning Balance" / "Ending Balance" rows — skip
                    pending = None
                    pending_continues = False
                    continue

                amount = wd_amt if wd_amt is not None else dep_amt
                description = " ".join(desc_parts).strip()

                pending = Txn(
                    date=post_date,
                    description=description,
                    amount=amount,
                    balance=bal_amt,
                )
                pending_continues = True

            elif pending_continues and pending is not None:
                # Continuation line — append description text in the description band
                cont = [t["text"] for t in tokens
                        if G1_DESC_MIN <= t["x0"] <= G1_DESC_MAX]
                if cont:
                    extra = " ".join(cont).strip()
                    if extra and extra not in pending.description:
                        pending.description = (pending.description + " " + extra).strip()
            else:
                pending_continues = False

    flush()
    return txns


# ---------------------------------------------------------------------------
# nbkc bank parser
# ---------------------------------------------------------------------------
#
# Column x-coordinates (observed):
#   DATE        ~148
#   DESCRIPTION ~198 .. 380
#   DEPOSITS    ~387 .. 445   (format "$200.00" or "--")
#   WITHDRAWALS ~447 .. 510   (format "($4.50)" or "--")
#   BALANCE     ~535 .. 570
#
# Transaction layout: date line has date + description + amounts + balance.
# Second line has time + description continuation.

NBKC_DATE_X = (140, 180)
NBKC_DESC_MIN = 190
NBKC_DESC_MAX = 385
NBKC_DEP_MIN = 385
NBKC_DEP_MAX = 445
NBKC_WD_MIN = 445
NBKC_WD_MAX = 525
NBKC_BAL_MIN = 525
NBKC_BAL_MAX = 580


def parse_nbkc(pdf: pdfplumber.PDF) -> list[Txn]:
    txns: list[Txn] = []
    pending: Txn | None = None
    pending_continues = False

    def flush():
        nonlocal pending
        if pending is not None:
            txns.append(pending)
            pending = None

    for page in pdf.pages:
        words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
        for line in group_lines(words):
            if not line:
                continue
            first = line[0]
            first_is_date = (NBKC_DATE_X[0] <= first["x0"] <= NBKC_DATE_X[1]
                             and parse_date(first["text"]))

            if first_is_date:
                flush()
                post_date = parse_date(first["text"])

                desc_parts: list[str] = []
                dep_amt: Decimal | None = None
                wd_amt: Decimal | None = None
                bal_amt: Decimal | None = None

                for t in line[1:]:
                    x = t["x0"]
                    text = t["text"]
                    if NBKC_BAL_MIN <= x <= NBKC_BAL_MAX:
                        amt = parse_amount(text, parens_negative=True)
                        if amt is not None:
                            bal_amt = amt
                            continue
                    if NBKC_WD_MIN <= x <= NBKC_WD_MAX:
                        amt = parse_amount(text, parens_negative=True)
                        if amt is not None:
                            wd_amt = amt if amt < 0 else -amt
                            continue
                    if NBKC_DEP_MIN <= x <= NBKC_DEP_MAX:
                        amt = parse_amount(text, parens_negative=True)
                        if amt is not None:
                            dep_amt = amt
                            continue
                    if NBKC_DESC_MIN <= x <= NBKC_DESC_MAX:
                        desc_parts.append(text)

                if wd_amt is None and dep_amt is None:
                    # Beginning/Ending Balance rows
                    pending = None
                    pending_continues = False
                    continue

                amount = wd_amt if wd_amt is not None else dep_amt
                description = " ".join(desc_parts).strip()

                pending = Txn(
                    date=post_date,
                    description=description,
                    amount=amount,
                    balance=bal_amt,
                )
                pending_continues = True

            elif pending_continues and pending is not None:
                # Continuation row(s): time at x≈148 (skip), description at x≈198.
                # Keep accepting continuation lines until we see the next date row.
                cont = [t["text"] for t in line
                        if NBKC_DESC_MIN <= t["x0"] <= NBKC_DESC_MAX]
                if cont:
                    extra = " ".join(cont).strip()
                    if extra:
                        pending.description = (pending.description + " | " + extra).strip()
            else:
                pending_continues = False

    flush()
    return txns


# ---------------------------------------------------------------------------
# DoorDash Crimson (DasherDirect) parser
# ---------------------------------------------------------------------------
#
# Column x-coordinates (observed):
#   Date          ~58     (MM/DD format — year inferred from statement header)
#   Description   ~95 .. 380
#   Debit         ~390 .. 425
#   Credit        ~450 .. 475
#   Balance       ~525 .. 545
#
# Quirks:
#   * MM/DD only — year must come from header "MM/DD/YYYY - MM/DD/YYYY"
#   * Some txns have description split: leading and/or trailing lines without
#     a date, wrapping around the numeric date row.

DASHER_DATE_X = (55, 65)
DASHER_DESC_MIN = 90
DASHER_DESC_MAX = 385
DASHER_DEBIT_MIN = 385
DASHER_DEBIT_MAX = 430
DASHER_CREDIT_MIN = 445
DASHER_CREDIT_MAX = 480
DASHER_BAL_MIN = 520
DASHER_BAL_MAX = 555

_MMDD_RE = re.compile(r"^(\d{1,2})/(\d{1,2})$")
_STMT_PERIOD_RE = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")


def _infer_dasher_year(pdf: pdfplumber.PDF) -> int:
    """Read the statement period off page 1 to get the year."""
    text = pdf.pages[0].extract_text() or ""
    m = _STMT_PERIOD_RE.search(text)
    if m:
        try:
            return datetime.strptime(m.group(1), "%m/%d/%Y").year
        except ValueError:
            pass
    return datetime.now().year


def parse_dasher(pdf: pdfplumber.PDF) -> list[Txn]:
    year = _infer_dasher_year(pdf)
    txns: list[Txn] = []

    pending: Txn | None = None
    preface_desc: list[str] = []   # description tokens on line(s) immediately before date

    def flush():
        nonlocal pending
        if pending is not None:
            txns.append(pending)
            pending = None

    SKIP_DESC = {"Beginning Balance", "Ending Balance"}

    for page in pdf.pages:
        words = page.extract_words(keep_blank_chars=False, use_text_flow=False)
        for line in group_lines(words):
            if not line:
                continue
            first = line[0]
            is_date_line = (
                DASHER_DATE_X[0] <= first["x0"] <= DASHER_DATE_X[1]
                and _MMDD_RE.match(first["text"])
            )

            if is_date_line:
                flush()
                mm, dd = map(int, _MMDD_RE.match(first["text"]).groups())
                try:
                    txn_date = date(year, mm, dd)
                except ValueError:
                    preface_desc = []
                    continue

                desc_parts: list[str] = list(preface_desc)
                preface_desc = []

                debit = credit = bal = None

                for t in line[1:]:
                    x = t["x0"]
                    text = t["text"]
                    if DASHER_BAL_MIN <= x <= DASHER_BAL_MAX:
                        amt = parse_amount(text)
                        if amt is not None:
                            bal = amt
                            continue
                    if DASHER_CREDIT_MIN <= x <= DASHER_CREDIT_MAX:
                        amt = parse_amount(text)
                        if amt is not None:
                            credit = amt
                            continue
                    if DASHER_DEBIT_MIN <= x <= DASHER_DEBIT_MAX:
                        amt = parse_amount(text)
                        if amt is not None:
                            debit = amt
                            continue
                    if DASHER_DESC_MIN <= x <= DASHER_DESC_MAX:
                        desc_parts.append(text)

                description = " ".join(desc_parts).strip()

                if debit is None and credit is None:
                    # Balance-only rows (Beginning/Ending Balance)
                    continue
                if any(skip.lower() in description.lower() for skip in SKIP_DESC):
                    continue

                amount = -debit if debit is not None else credit
                pending = Txn(
                    date=txn_date,
                    description=description,
                    amount=amount,
                    balance=bal,
                )

            else:
                # Non-date line — either trailing description for pending, or
                # leading description for the next date row.
                cont = [t["text"] for t in line
                        if DASHER_DESC_MIN <= t["x0"] <= DASHER_DESC_MAX]
                if not cont:
                    continue
                text = " ".join(cont).strip()
                if not text:
                    continue

                # Heuristic: lines containing typical footer/header keywords go nowhere
                if re.search(
                    r"(?i)(page \d+ of \d+|doordash crimson|in case of errors|"
                    r"fee summary|account activity|starion bank|member fdic|"
                    r"call us at|personal checking|account summary|deposit account|"
                    r"visa u\.s\.a|dasher mobile app|your deposit|beginning balance|"
                    r"ending balance|date\s+description|total for this period)",
                    text,
                ):
                    continue

                if pending is not None:
                    pending.description = (pending.description + " " + text).strip()
                else:
                    preface_desc.append(text)

    flush()
    return txns


# ---------------------------------------------------------------------------
# Top-level extraction
# ---------------------------------------------------------------------------
PARSERS = {"golden1": parse_golden1, "nbkc": parse_nbkc, "dasher": parse_dasher}


def extract_pdf(path: Path) -> tuple[str | None, list[Txn]]:
    with pdfplumber.open(path) as pdf:
        first_text = pdf.pages[0].extract_text() or ""
        fmt = detect_format(first_text)
        if not fmt:
            return None, []
        txns = PARSERS[fmt](pdf)
    return fmt, txns


def txns_to_csv_bytes(txns: list[Txn]) -> bytes:
    df = pd.DataFrame(t.to_row() for t in txns)
    return df.to_csv(index=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Import driver
# ---------------------------------------------------------------------------
async def import_pdfs(org_prefix: str, pdf_paths: Iterable[Path]):
    async with Session() as session:
        orgs = (await session.execute(select(Organization))).scalars().all()
        matches = [o for o in orgs if o.name.lower().startswith(org_prefix.lower())
                   or org_prefix.lower() in o.name.lower()]
        if len(matches) != 1:
            print(f"[error] org prefix '{org_prefix}' matched {len(matches)} orgs:")
            for o in orgs:
                print(f"  - {o.name}")
            sys.exit(2)
        org = matches[0]
        print(f"Target: {org.name}\n")

        importer = TransactionImporter(session, org.id)
        grand_in = grand_dup = grand_err = 0

        for path in pdf_paths:
            if not path.exists():
                print(f"  [skip] {path} — not found")
                continue
            fmt, txns = extract_pdf(path)
            if not fmt:
                print(f"  [skip] {path.name} — unknown format")
                continue
            if not txns:
                print(f"  [warn] {path.name} — {fmt}: 0 transactions extracted")
                continue

            csv_bytes = txns_to_csv_bytes(txns)
            try:
                result = await importer.import_file(csv_bytes, path.stem + ".csv")
            except Exception as e:
                print(f"  [fail] {path.name} — {e}")
                continue
            await session.commit()

            print(f"  {path.name} ({fmt}): parsed={len(txns)} "
                  f"imported={result.imported} dup={result.duplicates_skipped} "
                  f"err={len(result.errors)}")
            if result.errors:
                for e in result.errors[:3]:
                    print(f"    - {e}")
                if len(result.errors) > 3:
                    print(f"    ... +{len(result.errors)-3} more")

            grand_in += result.imported
            grand_dup += result.duplicates_skipped
            grand_err += len(result.errors)

        print(f"\nTotals: imported={grand_in} duplicates={grand_dup} errors={grand_err}")


def collect_pdfs(args: list[str]) -> list[Path]:
    if args == ["--all"]:
        d = Path(__file__).parent / "imports" / "bank_statements"
        return sorted(d.glob("*.pdf"))
    return [Path(a) for a in args]


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    org_prefix = sys.argv[1]
    pdf_paths = collect_pdfs(sys.argv[2:])
    if not pdf_paths:
        print("[error] no PDFs provided")
        sys.exit(1)
    asyncio.run(import_pdfs(org_prefix, pdf_paths))
