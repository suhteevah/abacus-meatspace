"""Analyze ATM / cash withdrawal patterns — specifically looking for
cashless-ATM signatures common at dispensaries ($XX3.50 or $XX3.00
amounts, odd locations, round bases)."""
import asyncio, os, sys, re
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ABACUS_ROOT = Path(os.environ.get("ABACUS_ROOT", "J:/QBO FOSS alternative"))
sys.path.insert(0, str(ABACUS_ROOT))
os.environ.setdefault("DEBUG", "true")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import Organization, BankTransaction

DATABASE_URL = f"sqlite+aiosqlite:///{(Path(__file__).parent/'data'/'ridge_cell_repair.db').as_posix()}"
engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def main():
    async with Session() as s:
        txns = (await s.execute(select(BankTransaction))).scalars().all()
        cash = [t for t in txns if t.amount < 0 and re.search(
            r"ATM|CASH WITHDRAWAL|GOLDEN 1 CU|239 W 2ND ST|TRI COUNTIES",
            t.description_raw, re.IGNORECASE)]
        cash.sort(key=lambda t: t.transaction_date)

        print(f"\n{len(cash)} cash/ATM withdrawals — 90 days\n")
        print(f"  {'date':<12} {'amount':>10}  {'location':<60}")
        for t in cash:
            loc = re.sub(r"^(Withdrawal|Card ATM Cash Withdrawal|Checking Deposit)\s+", "",
                         t.description_raw, flags=re.IGNORECASE)[:60]
            print(f"  {t.transaction_date}  {float(t.amount):>+10,.2f}  {loc}")

        # Amount pattern analysis
        amts = [abs(t.amount) for t in cash]
        print(f"\n  count: {len(amts)}  sum: {sum(amts):,.2f}  avg: {sum(amts)/len(amts):,.2f}")

        # Frequency by amount
        from collections import Counter
        c = Counter(str(a) for a in amts)
        print("\n  by amount:")
        for a, n in sorted(c.items(), key=lambda kv: -float(kv[0])):
            print(f"    ${a:>8} × {n}")

        # Suspicious patterns: amounts ending in .50 (cashless-ATM dispensary fee)
        cashless_atm_likely = [t for t in cash if (abs(t.amount) % 1 == Decimal("0.50"))]
        if cashless_atm_likely:
            print(f"\n  ⚠ {len(cashless_atm_likely)} withdrawals end in .50 — common at cashless-ATM dispensaries")
            for t in cashless_atm_likely:
                print(f"    {t.transaction_date} ${abs(t.amount)}  {t.description_raw[:70]}")

        # Location frequency
        print("\n  locations (normalized):")
        locs = Counter()
        for t in cash:
            loc = re.sub(r"[0-9]+", "", t.description_raw)
            loc = re.sub(r"\s+", " ", loc)[:60]
            locs[loc] += 1
        for loc, n in locs.most_common():
            print(f"    {n} × {loc}")


if __name__ == "__main__":
    asyncio.run(main())
