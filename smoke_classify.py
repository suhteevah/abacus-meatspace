"""
Smoke-test classifier. Tiers:

  1. Deterministic rule pass — fast, free, covers ~70-80% of Matt's txns.
  2. Claude.ai session-cookie LLM (zero-API-cost) for the rest.

Usage:
    python smoke_classify.py [N]       # default 10
    python smoke_classify.py --all     # process every unclassified txn

Env vars picked up automatically (set them in meatspace/.env):
    CLAUDE_AI_SESSION_COOKIE  — paste the full cookie string from your browser
                                (e.g.  "sessionKey=<value>; __ssid=<value>" OR just
                                "__ssid=<value>").  DevTools → Application →
                                Cookies → https://claude.ai → copy the live session.
    CLAUDE_AI_ORG_ID          — your claude.ai org UUID. Default from baremetal
                                is Matt's: 9cb75ae8-c9bb-4ef3-afed-7ff716b22fd3.
    CLAUDE_AI_CONV_ID         — reuse a saved conversation (optional).
    CLAUDE_AI_MODEL           — override the default claude-sonnet-4-5-20250929.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ABACUS_ROOT = Path(os.environ.get("ABACUS_ROOT", "J:/QBO FOSS alternative"))
sys.path.insert(0, str(ABACUS_ROOT))

DATA_DIR = Path(__file__).parent / "data"
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{(DATA_DIR / 'ridge_cell_repair.db').as_posix()}",
)
# Default Matt's claude.ai org UUID unless overridden.
os.environ.setdefault(
    "CLAUDE_AI_ORG_ID",
    "9cb75ae8-c9bb-4ef3-afed-7ff716b22fd3",
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from abacus.classifier import Classifier
from abacus.config import settings
from abacus.models import Organization, BankTransaction


async def main(limit: int | None):
    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        org = (await session.execute(
            select(Organization).where(Organization.name.ilike("%Personal%"))
        )).scalar_one_or_none()
        if not org:
            print("[error] Personal org not found")
            return

        q = (
            select(BankTransaction)
            .where(
                BankTransaction.organization_id == org.id,
                BankTransaction.suggested_account_id.is_(None),
            )
            .order_by(BankTransaction.transaction_date)
        )
        if limit is not None:
            q = q.limit(limit)
        txns = (await session.execute(q)).scalars().all()

        print(f"Target: {org.name}")
        print(f"Unclassified txns to process: {len(txns)}")
        have_llm = bool(settings.claude_ai_session_cookie)
        print(f"LLM path: {'claude.ai session cookie' if have_llm else 'disabled (rules only)'}")
        print()

        classifier = Classifier(session, org.id, ruleset_key="personal")

        buckets = {"rule_high": 0, "rule_low": 0, "llm": 0, "unknown": 0}
        for t in txns:
            sign = "-" if t.amount < 0 else "+"
            head = (
                f"  {t.transaction_date} {sign}${abs(t.amount):>8,.2f}  "
                f"{t.description_raw[:55]}"
            )
            result = await classifier.classify(
                description=t.description_raw,
                amount=t.amount,
                llm_threshold=0.80,
            )
            if result.account_id is None:
                buckets["unknown"] += 1
                print(f"{head}\n     ✗ unclassified — {result.memo}")
                continue

            if result.source == "rule" and result.confidence >= 0.80:
                buckets["rule_high"] += 1
                tag = "rule"
            elif result.source == "rule":
                buckets["rule_low"] += 1
                tag = "rule?"
            else:
                buckets["llm"] += 1
                tag = "llm"

            await classifier.apply_to(t, result)
            print(f"{head}\n     → {result.account_number} {result.account_name:<30} "
                  f"[{tag} {result.confidence:.2f}]  {result.memo[:60]}")

        await session.commit()
        print()
        print(f"Summary: rule_high={buckets['rule_high']}  "
              f"rule_low={buckets['rule_low']}  "
              f"llm={buckets['llm']}  "
              f"unknown={buckets['unknown']}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        asyncio.run(main(None))
    else:
        n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
        asyncio.run(main(n))
