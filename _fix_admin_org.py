import asyncio, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "J:/QBO FOSS alternative")
os.environ["DEBUG"] = "true"
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import Organization, User

e = create_async_engine("sqlite+aiosqlite:///J:/abacus-meatspace/data/ridge_cell_repair.db",
                        connect_args={"check_same_thread": False})
S = async_sessionmaker(e, class_=AsyncSession, expire_on_commit=False)

async def m():
    async with S() as s:
        orgs = (await s.execute(select(Organization))).scalars().all()
        for o in orgs:
            print(f"  org {o.id}  {o.name}")
        admin = (await s.execute(
            select(User).where(User.email == "matt@ridgecellrepair.com")
        )).scalar_one()
        personal = next(o for o in orgs if "Personal" in o.name)
        print(f"\nAdmin was in: {admin.organization_id}")
        print(f"Moving admin to Personal: {personal.id} ({personal.name})")
        admin.organization_id = personal.id
        await s.commit()
        print("✓ updated")

asyncio.run(m())
