import asyncio, os, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "J:/QBO FOSS alternative")
os.environ["DEBUG"] = "true"
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import (
    Organization, BankTransaction, JournalEntry, JournalLineItem,
    Account, Receipt,
)

e = create_async_engine(
    "sqlite+aiosqlite:///J:/abacus-meatspace/data/ridge_cell_repair.db",
    connect_args={"check_same_thread": False},
)
S = async_sessionmaker(e, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with S() as s:
        orgs = (await s.execute(select(Organization))).scalars().all()
        for o in orgs:
            n_acc = (await s.execute(
                select(func.count()).select_from(Account).where(Account.organization_id == o.id)
            )).scalar()
            n_btx = (await s.execute(
                select(func.count()).select_from(BankTransaction).where(BankTransaction.organization_id == o.id)
            )).scalar()
            n_btx_classified = (await s.execute(
                select(func.count()).select_from(BankTransaction).where(
                    BankTransaction.organization_id == o.id,
                    BankTransaction.suggested_account_id.isnot(None),
                )
            )).scalar()
            n_btx_entry = (await s.execute(
                select(func.count()).select_from(BankTransaction).where(
                    BankTransaction.organization_id == o.id,
                    BankTransaction.journal_entry_id.isnot(None),
                )
            )).scalar()
            n_je = (await s.execute(
                select(func.count()).select_from(JournalEntry).where(JournalEntry.organization_id == o.id)
            )).scalar()
            n_rec = (await s.execute(
                select(func.count()).select_from(Receipt).where(Receipt.organization_id == o.id)
            )).scalar()

            print(f"\n═══ {o.name} ═══")
            print(f"  chart of accounts:        {n_acc}")
            print(f"  bank transactions:        {n_btx}")
            print(f"    ↳ AI-classified:        {n_btx_classified}")
            print(f"    ↳ journal entry posted: {n_btx_entry}")
            print(f"  journal entries:          {n_je}")
            print(f"  receipts:                 {n_rec}")

asyncio.run(main())
