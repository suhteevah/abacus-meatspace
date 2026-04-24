"""
Cash-flow / spending report for imported bank transactions.

Usage:
  python spend_report.py [org_prefix]   # default: personal

Applies Matt's heuristics:
  * Cash withdrawal or self-transfer >= $1000  → RENT
  * Cash withdrawal or self-transfer $500-999  → CASH (rent-portion / bulk food)
  * Cash withdrawal or self-transfer <  $500   → CASH (food / misc)
  * Known merchants → category by regex

Then splits spending into FIXED (rent, phone, insurance, subs) vs
VARIABLE (food, cash, misc) so we see what's actually flexible.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ABACUS_ROOT = Path(os.environ.get("ABACUS_ROOT", "J:/QBO FOSS alternative"))
sys.path.insert(0, str(ABACUS_ROOT))
os.environ.setdefault("DEBUG", "true")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import Organization, BankTransaction

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


# --------------------------------------------------------------------------
# Category rules (first match wins)
# --------------------------------------------------------------------------
# Tuple: (regex, category, bucket)  bucket ∈ {"fixed", "variable", "business", "income", "transfer"}
MERCHANT_RULES: list[tuple[str, str, str]] = [
    # Income
    (r"GUSTO.*PAY", "Payroll (Gusto)", "income"),
    (r"EARNIN", "Earnin advance (income)", "income"),
    (r"PATHWARD.*ON-DEMAND.*ADVANCE(?!.*REPAY)", "Earnin advance (income)", "income"),
    (r"DOORDASH.*ACH", "DoorDash payout", "income"),
    (r"CASH APP.*MATT", "Cash App income", "income"),
    (r"VENMO.*MATT", "Venmo income", "income"),
    (r"INTEREST PAID", "Interest", "income"),

    # Rent — specifically $1,750/mo. Matched by amount below, not regex.
    # (Other PayPal Michels / check lines fall through to "self-transfer".)

    # Fixed recurring
    (r"TMOBILE|T-?MOBILE", "Phone (T-Mobile)", "fixed"),
    (r"METROMILE|LEMONADE", "Car insurance", "fixed"),
    (r"PY\s*\*?\s*CROWN STORAGE", "Storage unit", "fixed"),
    (r"PP\*APPLE\.COM/BILL|APPLE\.COM/BILL", "Apple subscription", "fixed"),
    (r"NETFLIX", "Netflix", "fixed"),
    (r"SPOTIFY", "Spotify", "fixed"),
    (r"MICROSOFT|PAYPAL \*MICROSOFT", "Microsoft sub", "fixed"),
    (r"KEURIG", "Keurig pods (subscription)", "fixed"),

    # Business (personally paid — should reclass to RCR)
    (r"ANTHROPIC|CLAUDE\.AI", "BIZ: Anthropic / Claude", "business"),
    (r"OPENAI", "BIZ: OpenAI", "business"),
    (r"GOOGLE\s*\*?\s*WORKSPACE", "BIZ: Google Workspace", "business"),
    (r"GITHUB", "BIZ: GitHub", "business"),
    (r"CLOUDFLARE|VERCEL|SUPABASE", "BIZ: Hosting", "business"),
    (r"ZOHODIST|ZOHO", "BIZ: Zoho", "business"),
    (r"UPWORK", "BIZ: Upwork (dual-use)", "business"),

    # Food
    (r"SAFEWAY|GROCERY|WALMART|TRADER JOE|WINCO", "Food - Groceries", "variable"),
    (r"TACO BELL|STARBUCKS|SUSHI|BIG ALS|KWIK SERV|7-ELEVEN|909 FASTRIP", "Food - Fast/Dining", "variable"),

    # Cash & transfers
    (r"KALSHI", "Kalshi deposit", "transfer"),
    (r"PATHWARD.*REPAY|ADVANCE REPAYMENT", "Earnin repayment", "fixed"),
    (r"PATHWARD.*INSTANT TRANSFER FEE|INSTANT TRANSFER FEE", "Earnin fees", "fixed"),

    # Amazon / misc retail
    (r"AMAZON", "Amazon", "variable"),
    (r"WESTLAKE ACE|O'REILLY|UHI U-HAUL", "Hardware / auto", "variable"),
    (r"MANGROVE BOTTLE", "Alcohol / misc retail", "variable"),
    (r"TT\*\s*B-LINE|TOKENTRANSIT", "Transit (B-Line)", "variable"),

    # Returns
    (r"RETURN OF A WITHDRAWAL|DEPOSIT TO ON-DEMAND", "Internal transfer", "transfer"),
    (r"PROGRAM SETTLEMENT", "Internal transfer", "transfer"),
    (r"CUSTOMER TRANSFER TO PATHWARD", "Earnin repayment", "fixed"),
    (r"CUSTOMER TRANSFER FROM PATHWARD", "Earnin advance (income)", "income"),
]

def classify_merchant(desc: str) -> tuple[str, str] | None:
    for pat, cat, bucket in MERCHANT_RULES:
        if re.search(pat, desc, re.IGNORECASE):
            return cat, bucket
    return None


def classify_cash(amount: Decimal, desc: str) -> tuple[str, str] | None:
    """Matt's cash rules — only for ATM/branch withdrawals and ambiguous cash-outs."""
    if amount >= 0:
        return None
    cash_patterns = [
        r"CARD ATM CASH WITHDRAWAL",
        r"TRI COUNTIES",
        r"239 W 2ND ST.*GOLDEN 1",      # Golden 1 branch
        r"CARD MONEY TRANSFER FROM",
    ]
    if not any(re.search(p, desc, re.IGNORECASE) for p in cash_patterns):
        return None
    abs_amt = -amount
    if abs_amt >= 1000:
        return "Rent (cash)", "fixed"
    if abs_amt >= 500:
        return "Cash large ($500-999, rent/food)", "variable"
    return "Cash small (food/misc)", "variable"


RENT_AMOUNT = Decimal("1750.00")

def classify(t: BankTransaction) -> tuple[str, str]:
    # Rent-by-amount rule (Matt: $1,750/mo is rent, paid various ways)
    if t.amount < 0 and abs(t.amount) == RENT_AMOUNT:
        return "Rent ($1,750/mo)", "fixed"

    m = classify_merchant(t.description_raw)
    if m:
        return m
    c = classify_cash(t.amount, t.description_raw)
    if c:
        return c

    # Self-transfer fallbacks
    desc = t.description_raw.upper()
    if re.search(r"PAYPAL\s*\*?\s*MICHELS|#?12[6-9]\b|VENMO.*MATT", desc):
        return "Self-transfer / check", "transfer"

    if t.amount > 0:
        return "Uncategorized income", "income"
    return "UNCLASSIFIED", "variable"


# --------------------------------------------------------------------------
@dataclass
class Bucket:
    count: int = 0
    total: Decimal = Decimal(0)


async def main(org_prefix: str = "personal"):
    async with Session() as session:
        orgs = (await session.execute(select(Organization))).scalars().all()
        org = next((o for o in orgs if org_prefix.lower() in o.name.lower()), None)
        if not org:
            print(f"[error] no org matching '{org_prefix}'")
            sys.exit(2)

        txns = (await session.execute(
            select(BankTransaction).where(BankTransaction.organization_id == org.id)
        )).scalars().all()
        if not txns:
            print(f"{org.name}: no transactions imported yet")
            return

        print(f"\n╔═ {org.name} — {len(txns)} transactions ═╗\n")

        by_bucket_cat: dict[tuple[str, str], Bucket] = defaultdict(Bucket)
        unclassified: list[BankTransaction] = []

        total_income = Decimal(0)
        total_fixed = Decimal(0)
        total_variable = Decimal(0)
        total_business = Decimal(0)
        total_transfer_out = Decimal(0)

        for t in txns:
            cat, bucket = classify(t)
            row = by_bucket_cat[(bucket, cat)]
            row.count += 1
            if t.amount > 0:
                row.total += t.amount
            else:
                row.total += -t.amount

            if cat == "UNCLASSIFIED":
                unclassified.append(t)

            if bucket == "income" and t.amount > 0:
                total_income += t.amount
            elif t.amount < 0:
                if bucket == "fixed":
                    total_fixed += -t.amount
                elif bucket == "variable":
                    total_variable += -t.amount
                elif bucket == "business":
                    total_business += -t.amount
                elif bucket == "transfer":
                    total_transfer_out += -t.amount

        # ── Print buckets ──
        for bucket_label, bucket_key in [
            ("INCOME",            "income"),
            ("FIXED (rent, phone, subs, fees)", "fixed"),
            ("VARIABLE (food, cash, misc)",     "variable"),
            ("BUSINESS paid personally",        "business"),
            ("TRANSFERS (internal)",            "transfer"),
        ]:
            rows = sorted(
                [(cat, b) for (bk, cat), b in by_bucket_cat.items() if bk == bucket_key],
                key=lambda kv: kv[1].total,
                reverse=True,
            )
            if not rows:
                continue
            print(f"┌─ {bucket_label} " + "─" * max(1, 62 - len(bucket_label)))
            print(f"│ {'category':<42} {'#':>4} {'total':>12}")
            sub = Decimal(0)
            for cat, b in rows:
                print(f"│ {cat:<42} {b.count:>4} {b.total:>12,.2f}")
                sub += b.total
            print(f"│ {'── subtotal':<42} {'':>4} {sub:>12,.2f}")
            print("└" + "─" * 64)
            print()

        # ── Monthly breakdown with buckets ──
        by_month = defaultdict(lambda: {"income": Decimal(0), "fixed": Decimal(0),
                                         "variable": Decimal(0), "business": Decimal(0)})
        for t in txns:
            _, bucket = classify(t)
            m = t.transaction_date.strftime("%Y-%m")
            if bucket == "income" and t.amount > 0:
                by_month[m]["income"] += t.amount
            elif t.amount < 0 and bucket in ("fixed", "variable", "business"):
                by_month[m][bucket] += -t.amount

        print("┌─ Monthly breakdown (excluding internal transfers) " + "─" * 12)
        print(f"│ {'month':<8} {'income':>10} {'fixed':>10} {'variable':>10} {'biz':>8} {'net':>10}")
        for m in sorted(by_month):
            d = by_month[m]
            spend = d["fixed"] + d["variable"] + d["business"]
            print(f"│ {m:<8} {d['income']:>10,.2f} {d['fixed']:>10,.2f} "
                  f"{d['variable']:>10,.2f} {d['business']:>8,.2f} {d['income']-spend:>+10,.2f}")
        print("└" + "─" * 64)

        # ── Grand totals ──
        print()
        print(f"  INCOME:             {total_income:>12,.2f}")
        print(f"  FIXED spend:        {total_fixed:>12,.2f}  ({total_fixed/total_income*100:>5.1f}% of income)")
        print(f"  VARIABLE spend:     {total_variable:>12,.2f}  ({total_variable/total_income*100:>5.1f}% of income)")
        print(f"  BUSINESS (personal):{total_business:>12,.2f}  ← reclass to RCR")
        print(f"  TRUE NET:           {total_income - total_fixed - total_variable - total_business:>+12,.2f}")
        print()

        # ── Unclassified tail ──
        if unclassified:
            unclassified.sort(key=lambda t: t.amount)
            print(f"┌─ UNCLASSIFIED ({len(unclassified)}) — top 15 by size " + "─" * 20)
            for t in unclassified[:15]:
                print(f"│ {t.transaction_date} {t.amount:>10,.2f}  {t.description_raw[:70]}")
            print("└" + "─" * 64)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "personal"))
