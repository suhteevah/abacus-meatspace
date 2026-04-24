import asyncio, os, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "J:/QBO FOSS alternative")
os.environ["DEBUG"] = "true"
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import (Organization, JournalEntry, JournalLineItem,
                           Account, AccountType, EntryStatus)

e = create_async_engine("sqlite+aiosqlite:///J:/abacus-meatspace/data/ridge_cell_repair.db",
                        connect_args={"check_same_thread": False})
S = async_sessionmaker(e, class_=AsyncSession, expire_on_commit=False)

async def m():
    async with S() as s:
        org = (await s.execute(select(Organization).where(Organization.name.ilike("%Personal%")))).scalar_one()
        # pick a recent auto-approved entry
        je = (await s.execute(
            select(JournalEntry).where(
                JournalEntry.organization_id == org.id,
                JournalEntry.status == EntryStatus.AUTO_APPROVED,
            ).limit(3)
        )).scalars().all()
        for j in je:
            print(f"JE {j.id} date={j.entry_date} status={j.status.value} desc={j.description[:50]}")
            lis = (await s.execute(
                select(JournalLineItem, Account).join(Account, JournalLineItem.account_id==Account.id)
                .where(JournalLineItem.journal_entry_id == j.id)
            )).all()
            for li, acct in lis:
                print(f"  {acct.account_number} {acct.name} [{acct.account_type.value}] DR={li.debit_amount} CR={li.credit_amount}")
        # Count line items by account type in auto/approved entries in our date range
        print("\nTotals by account type (auto+approved entries):")
        from sqlalchemy import and_
        from datetime import date
        result = await s.execute(
            select(Account.account_type, func.sum(JournalLineItem.debit_amount), func.sum(JournalLineItem.credit_amount))
            .join(JournalLineItem, JournalLineItem.account_id == Account.id)
            .join(JournalEntry, JournalEntry.id == JournalLineItem.journal_entry_id)
            .where(
                JournalEntry.organization_id == org.id,
                JournalEntry.status.in_([EntryStatus.AUTO_APPROVED, EntryStatus.APPROVED]),
                JournalEntry.entry_date >= date(2025, 12, 1),
                JournalEntry.entry_date <= date(2026, 3, 31),
            ).group_by(Account.account_type)
        )
        for row in result.all():
            print(f"  {row[0].value:<20} DR={row[1]} CR={row[2]}")

asyncio.run(m())
