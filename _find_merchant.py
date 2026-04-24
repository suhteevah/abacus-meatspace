"""Quick merchant search across imported transactions."""
import asyncio, os, sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ABACUS_ROOT = Path(os.environ.get("ABACUS_ROOT", "J:/QBO FOSS alternative"))
sys.path.insert(0, str(ABACUS_ROOT))
os.environ.setdefault("DEBUG", "true")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import Organization, BankTransaction

DATA_DIR = Path(__file__).parent / "data"
DATABASE_URL = f"sqlite+aiosqlite:///{(DATA_DIR / 'ridge_cell_repair.db').as_posix()}"
engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def main(pattern: str):
    async with Session() as s:
        txns = (await s.execute(select(BankTransaction))).scalars().all()
        hits = [t for t in txns if re.search(pattern, t.description_raw, re.IGNORECASE)]
        hits.sort(key=lambda t: t.transaction_date)
        print(f"\n{pattern!r} — {len(hits)} hits\n")
        total = 0
        for t in hits:
            total += float(t.amount)
            print(f"  {t.transaction_date}  {float(t.amount):>+10,.2f}   {t.description_raw[:90]}")
        print(f"\n  total: {total:+,.2f}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
