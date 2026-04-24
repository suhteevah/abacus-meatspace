"""
Direct CSV bank-statement importer for Matt's Abacus instance.

Usage:
  python import_csv.py <org> <csv_path> [csv_path2 ...]

<org> is a prefix match against organization name, e.g.:
  rcr       → Ridge Cell Repair LLC
  kalshi    → Kalshi Trading
  personal  → Personal - Matt Gates

Bypasses the HTTP API — writes directly to the DB. Idempotent:
re-imports are deduped via SHA-256 hash of (date|amount|description).
"""

import asyncio
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ABACUS_ROOT = Path(os.environ.get("ABACUS_ROOT", "J:/QBO FOSS alternative"))
sys.path.insert(0, str(ABACUS_ROOT))

os.environ.setdefault("DEBUG", "true")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from abacus.models import Organization
from abacus.importer import TransactionImporter

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


async def main(org_prefix: str, csv_paths: list[str]):
    async with Session() as session:
        orgs = (await session.execute(select(Organization))).scalars().all()
        matches = [o for o in orgs if o.name.lower().startswith(org_prefix.lower())
                   or org_prefix.lower() in o.name.lower()]
        if len(matches) != 1:
            print(f"[error] org prefix '{org_prefix}' matched {len(matches)} orgs:")
            for o in orgs:
                print(f"  - {o.name}")
            sys.exit(2)
        org = matches[0]
        print(f"Target: {org.name}\n")

        importer = TransactionImporter(session, org.id)
        total_in = total_dup = total_err = 0

        for csv_path in csv_paths:
            p = Path(csv_path)
            if not p.exists():
                print(f"  [skip] {csv_path} — not found")
                continue
            content = p.read_bytes()
            try:
                result = await importer.import_file(content, p.name)
            except Exception as e:
                print(f"  [fail] {p.name} — {e}")
                continue
            await session.commit()
            print(f"  {p.name}: imported={result.imported} "
                  f"duplicates={result.duplicates_skipped} errors={len(result.errors)}")
            if result.errors:
                for e in result.errors[:5]:
                    print(f"    - {e}")
                if len(result.errors) > 5:
                    print(f"    ... +{len(result.errors)-5} more")
            total_in += result.imported
            total_dup += result.duplicates_skipped
            total_err += len(result.errors)

        print(f"\nTotals: imported={total_in} duplicates={total_dup} errors={total_err}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2:]))
