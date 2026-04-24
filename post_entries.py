"""Post journal entries for every classified BankTransaction above 0.80 confidence."""
import asyncio, os, sys
from decimal import Decimal
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "J:/QBO FOSS alternative")
os.environ["DEBUG"] = "true"

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import Organization
from abacus.transaction_pipeline import TransactionPipeline

DB = Path(__file__).parent / "data" / "ridge_cell_repair.db"
e = create_async_engine(f"sqlite+aiosqlite:///{DB.as_posix()}",
                        connect_args={"check_same_thread": False})
S = async_sessionmaker(e, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with S() as s:
        org = (await s.execute(
            select(Organization).where(Organization.name.ilike("%Personal%"))
        )).scalar_one()
        pipeline = TransactionPipeline(s, org.id)

        result = await pipeline.create_entries_from_classified(
            confidence_threshold=0.80,
            auto_approve_threshold=Decimal("50.00"),
        )
        await s.commit()

        print(f"entries_created={result['entries_created']}  errors={result['errors']}")
        # Show first 10 for sanity
        for e in result["entries"][:10]:
            print(f"  {e['description'][:70]:<70} ${e['amount']:>8}  [{e['status']}]")
        if len(result["entries"]) > 10:
            print(f"  ... +{len(result['entries']) - 10} more")

asyncio.run(main())
