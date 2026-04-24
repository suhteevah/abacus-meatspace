import asyncio, os, sys
from pathlib import Path
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "J:/QBO FOSS alternative")
os.environ["DEBUG"] = "true"
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import BankTransaction

e = create_async_engine("sqlite+aiosqlite:///J:/abacus-meatspace/data/ridge_cell_repair.db",
                        connect_args={"check_same_thread": False})
S = async_sessionmaker(e, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with S() as s:
        txns = (await s.execute(select(BankTransaction))).scalars().all()
        dd = defaultdict(float)
        dd_count = defaultdict(int)
        for t in txns:
            if "DoorDash Payout" in t.description_raw:
                k = t.transaction_date.strftime("%Y-%m")
                dd[k] += float(t.amount)
                dd_count[k] += 1
        print("DoorDash payouts observed (bank + Crimson combined):")
        for k in sorted(dd):
            print(f"  {k}: ${dd[k]:>9,.2f}  ({dd_count[k]} payouts)")
        print(f"  TOTAL:   ${sum(dd.values()):,.2f}")

asyncio.run(main())
