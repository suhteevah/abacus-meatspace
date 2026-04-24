"""Export unclassified BankTransactions + chart of accounts as JSON files,
for consumption by the in-browser LLM classifier."""
import asyncio, json, os, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "J:/QBO FOSS alternative")
os.environ["DEBUG"] = "true"
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import Account, BankTransaction, Organization

DB = Path(__file__).parent / "data" / "ridge_cell_repair.db"
OUT = Path(__file__).parent / "scratch"
OUT.mkdir(exist_ok=True)

e = create_async_engine(f"sqlite+aiosqlite:///{DB.as_posix()}", connect_args={"check_same_thread": False})
S = async_sessionmaker(e, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with S() as s:
        org = (await s.execute(
            select(Organization).where(Organization.name.ilike("%Personal%"))
        )).scalar_one()
        accounts = (await s.execute(
            select(Account).where(Account.organization_id == org.id).order_by(Account.account_number)
        )).scalars().all()
        txns = (await s.execute(
            select(BankTransaction).where(
                BankTransaction.organization_id == org.id,
                BankTransaction.suggested_account_id.is_(None),
            ).order_by(BankTransaction.transaction_date)
        )).scalars().all()

        acct_list = [{"number": a.account_number, "name": a.name,
                      "type": a.account_type.value if a.account_type else ""}
                     for a in accounts]
        txn_list = [{"id": str(t.id),
                     "date": t.transaction_date.isoformat(),
                     "amount": float(t.amount),
                     "description": t.description_raw}
                    for t in txns]

        (OUT / "accounts.json").write_text(json.dumps(acct_list, indent=2), encoding="utf-8")
        (OUT / "unclassified.json").write_text(json.dumps(txn_list, indent=2), encoding="utf-8")
        print(f"exported {len(acct_list)} accounts, {len(txn_list)} unclassified txns")
        print(f"  {OUT/'accounts.json'}")
        print(f"  {OUT/'unclassified.json'}")

asyncio.run(main())
