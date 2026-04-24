import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "J:/QBO FOSS alternative")
os.environ["DEBUG"] = "true"
from datetime import date
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import (Organization, Account, AccountType, JournalEntry, JournalLineItem, EntryStatus)

e = create_async_engine("sqlite+aiosqlite:///J:/abacus-meatspace/data/ridge_cell_repair.db",
                        connect_args={"check_same_thread": False})
S = async_sessionmaker(e, class_=AsyncSession, expire_on_commit=False)

APPROVED = [EntryStatus.APPROVED, EntryStatus.AUTO_APPROVED]

async def m():
    async with S() as s:
        org = (await s.execute(select(Organization).where(Organization.name.ilike("%Personal%")))).scalar_one()
        q = (
            select(
                Account.account_number, Account.name, Account.account_type,
                Account.normal_balance, Account.is_active,
                func.coalesce(func.sum(JournalLineItem.debit_amount), 0).label("dr"),
                func.coalesce(func.sum(JournalLineItem.credit_amount), 0).label("cr"),
            )
            .outerjoin(JournalLineItem, Account.id == JournalLineItem.account_id)
            .outerjoin(JournalEntry, and_(
                JournalLineItem.journal_entry_id == JournalEntry.id,
                JournalEntry.entry_date >= date(2025, 12, 1),
                JournalEntry.entry_date <= date(2026, 3, 31),
                JournalEntry.status.in_(APPROVED),
                JournalEntry.organization_id == org.id,
            ))
            .where(
                Account.organization_id == org.id,
                Account.is_active.is_(True),
                Account.account_type.in_([AccountType.REVENUE, AccountType.EXPENSE,
                                           AccountType.CONTRA_REVENUE, AccountType.CONTRA_EXPENSE]),
            )
            .group_by(Account.account_number, Account.name, Account.account_type,
                       Account.normal_balance, Account.is_active)
            .order_by(Account.account_number)
        )
        rows = (await s.execute(q)).all()
        print(f"{'acct':<6} {'name':<28} {'type':<12} {'nb':<7} {'active':<6} {'dr':>10} {'cr':>10}")
        for r in rows:
            print(f"{r.account_number:<6} {r.name[:28]:<28} {r.account_type.value:<12} "
                  f"{str(r.normal_balance):<7} {str(r.is_active):<6} {float(r.dr):>10} {float(r.cr):>10}")

asyncio.run(m())
