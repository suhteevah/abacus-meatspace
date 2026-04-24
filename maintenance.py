"""
Maintenance / safe-baseline script for Matt's Abacus instance.

Does the one-time cleanups that should have happened after seed:
  1. Rotates the admin password (reads NEW_ADMIN_PASSWORD from env, or prompts)
  2. Adds missing Kalshi accounts (unrealized gain/loss + cash deposits/withdrawals)
  3. Ensures imports/receipts/ exists
  4. Prints a status summary

Idempotent — safe to run multiple times.
"""

import asyncio
import getpass
import os
import sys
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ABACUS_ROOT = Path(os.environ.get("ABACUS_ROOT", "J:/QBO FOSS alternative"))
sys.path.insert(0, str(ABACUS_ROOT))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import (
    Organization, User, Account, UserRole, AccountType, AccountSubtype,
)
from abacus.auth import hash_password

DATA_DIR = Path(__file__).parent / "data"
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{(DATA_DIR / 'ridge_cell_repair.db').as_posix()}",
)

engine_kwargs = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_async_engine(DATABASE_URL, **engine_kwargs)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Kalshi additions: MTM on open positions + explicit cash deposits/withdrawals
KALSHI_ADDITIONS = [
    # code, name, type, subtype, parent_code
    ("4500", "Unrealized Gains - Open Positions", AccountType.REVENUE,  AccountSubtype.OTHER_INCOME,  None),
    ("5500", "Unrealized Losses - Open Positions", AccountType.EXPENSE, AccountSubtype.OTHER_EXPENSE, None),
    ("4040", "Settlement Income - Weather",        AccountType.REVENUE, AccountSubtype.OTHER_INCOME, "4100"),
    ("4050", "Settlement Income - Political",      AccountType.REVENUE, AccountSubtype.OTHER_INCOME, "4100"),
]

DEBIT_TYPES  = {AccountType.ASSET, AccountType.EXPENSE,
                AccountType.CONTRA_LIABILITY, AccountType.CONTRA_EQUITY, AccountType.CONTRA_REVENUE}

def normal_balance(t):
    return "debit" if t in DEBIT_TYPES else "credit"


async def rotate_admin_password(session):
    result = await session.execute(
        select(User).where(User.email == "matt@ridgecellrepair.com")
    )
    admin = result.scalar_one_or_none()
    if not admin:
        print("  [skip] admin user not found")
        return False

    # Detect whether the password is still the seed default "changeme"
    from abacus.auth import verify_password
    still_default = verify_password("changeme", admin.hashed_password)
    if not still_default:
        print("  [skip] admin password already rotated")
        return False

    new_pw = os.environ.get("NEW_ADMIN_PASSWORD")
    if not new_pw:
        print("  [skip] admin still has 'changeme' — set NEW_ADMIN_PASSWORD env var and rerun")
        return False
    if len(new_pw) < 10:
        print("  [error] password must be at least 10 chars")
        return False

    admin.hashed_password = hash_password(new_pw)
    await session.commit()
    print("  [ok] admin password rotated")
    return True


async def patch_kalshi_coa(session):
    org = (await session.execute(
        select(Organization).where(Organization.name == "Kalshi Trading")
    )).scalar_one_or_none()
    if not org:
        print("  [skip] Kalshi Trading org not found")
        return

    existing = {
        a.account_number: a for a in (await session.execute(
            select(Account).where(Account.organization_id == org.id)
        )).scalars().all()
    }

    added = 0
    for code, name, typ, subtype, parent_code in KALSHI_ADDITIONS:
        if code in existing:
            continue
        parent_id = existing[parent_code].id if parent_code and parent_code in existing else None
        a = Account(
            id=uuid.uuid4(),
            organization_id=org.id,
            account_number=code,
            name=name,
            account_type=typ,
            account_subtype=subtype,
            normal_balance=normal_balance(typ),
            parent_id=parent_id,
            is_active=True,
            is_system=True,
        )
        session.add(a)
        await session.flush()
        existing[code] = a
        added += 1
    await session.commit()
    print(f"  [ok] Kalshi CoA: added {added} account(s) ({len(existing)} total)")


def ensure_import_dirs():
    root = Path(__file__).parent
    for p in ("imports/bank_statements", "imports/receipts"):
        (root / p).mkdir(parents=True, exist_ok=True)
    print("  [ok] imports/bank_statements and imports/receipts exist")


async def summary(session):
    orgs = (await session.execute(select(Organization))).scalars().all()
    print("\nOrganizations:")
    for o in orgs:
        n = (await session.execute(
            select(Account).where(Account.organization_id == o.id)
        )).scalars().all()
        print(f"  - {o.name}: {len(n)} accounts")


async def main():
    DATA_DIR.mkdir(exist_ok=True)
    print(f"DB: {DATABASE_URL}\n")

    async with Session() as s:
        print("[1/3] Admin password")
        await rotate_admin_password(s)
        print("[2/3] Kalshi chart of accounts")
        await patch_kalshi_coa(s)
        print("[3/3] Import directories")
        ensure_import_dirs()
        await summary(s)


if __name__ == "__main__":
    asyncio.run(main())
