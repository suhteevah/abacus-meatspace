"""Apply the LLM classifications from the tab session to the BankTransaction rows."""
import asyncio, json, os, sys
from decimal import Decimal
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "J:/QBO FOSS alternative")
os.environ["DEBUG"] = "true"
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import Account, BankTransaction, Organization

SCRATCH = Path(__file__).parent / "scratch"
DB = Path(__file__).parent / "data" / "ridge_cell_repair.db"

e = create_async_engine(f"sqlite+aiosqlite:///{DB.as_posix()}", connect_args={"check_same_thread": False})
S = async_sessionmaker(e, class_=AsyncSession, expire_on_commit=False)

async def main():
    unclassified = json.loads((SCRATCH / "unclassified.json").read_text(encoding="utf-8"))
    results = json.loads((SCRATCH / "llm_classifications.json").read_text(encoding="utf-8"))
    assert len(results) == len(unclassified), f"{len(results)} results vs {len(unclassified)} txns"

    async with S() as s:
        org = (await s.execute(
            select(Organization).where(Organization.name.ilike("%Personal%"))
        )).scalar_one()
        accts = (await s.execute(
            select(Account).where(Account.organization_id == org.id)
        )).scalars().all()
        by_num = {a.account_number: a for a in accts}

        updated = 0
        skipped = 0
        for txn_dict, r in zip(unclassified, results):
            assert txn_dict["id"] == json.loads(json.dumps(txn_dict))["id"]  # sanity
            acct_no = r["acct"]
            a = by_num.get(acct_no)
            if not a:
                print(f"  [skip] {r['i']:3d} {acct_no} — not in chart; {r['why']}")
                skipped += 1
                continue
            t = (await s.execute(
                select(BankTransaction).where(BankTransaction.id == txn_dict["id"])
            )).scalar_one()
            t.suggested_account_id = a.id
            t.ai_category = r["why"][:240]
            t.ai_confidence = Decimal(str(round(float(r["conf"]), 4)))
            updated += 1

        await s.commit()
        print(f"updated={updated} skipped={skipped}")

asyncio.run(main())
