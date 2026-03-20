"""
Seed script for Ridge Cell Repair LLC's Abacus instance.
Creates three organizations with tailored charts of accounts:
  1. Ridge Cell Repair LLC (business)
  2. Kalshi Trading (investment/trading)
  3. Personal (Matt's personal finances)

Run once against a fresh Abacus database to bootstrap everything.
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import date

# Add the Abacus source to path
ABACUS_ROOT = Path(os.environ.get("ABACUS_ROOT", "J:/QBO FOSS alternative"))
sys.path.insert(0, str(ABACUS_ROOT))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from abacus.models import (
    Organization, User, Account,
    AccountType, AccountSubtype,
)
from abacus.auth import hash_password

# ---------------------------------------------------------------------------
# Database URL — reads from env or defaults to local SQLite
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///data/ridge_cell_repair.db",
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Chart of accounts definitions
# ---------------------------------------------------------------------------

# Shorthand helpers
A = AccountType.ASSET
L = AccountType.LIABILITY
E = AccountType.EQUITY
R = AccountType.REVENUE
X = AccountType.EXPENSE

def acct(code, name, typ, subtype=None, parent_code=None):
    return {"code": code, "name": name, "type": typ, "subtype": subtype, "parent_code": parent_code}


# ===== 1. Ridge Cell Repair LLC =====
RCR_ACCOUNTS = [
    # Assets
    acct("1000", "Cash & Bank Accounts", A, AccountSubtype.CASH),
    acct("1010", "Business Checking", A, AccountSubtype.CASH, "1000"),
    acct("1020", "Business Savings", A, AccountSubtype.CASH, "1000"),
    acct("1030", "Stripe Balance", A, AccountSubtype.CASH, "1000"),
    acct("1040", "PayPal Balance", A, AccountSubtype.CASH, "1000"),
    acct("1100", "Accounts Receivable", A, AccountSubtype.ACCOUNTS_RECEIVABLE),
    acct("1110", "A/R - Digital Services", A, AccountSubtype.ACCOUNTS_RECEIVABLE, "1100"),
    acct("1120", "A/R - Hardware Sales", A, AccountSubtype.ACCOUNTS_RECEIVABLE, "1100"),
    acct("1200", "Inventory", A, AccountSubtype.INVENTORY),
    acct("1210", "Inventory - ESP32 Components", A, AccountSubtype.INVENTORY, "1200"),
    acct("1220", "Inventory - LatchPac Assemblies", A, AccountSubtype.INVENTORY, "1200"),
    acct("1230", "Inventory - 3D Printer Filament", A, AccountSubtype.INVENTORY, "1200"),
    acct("1240", "Inventory - 3D Printed Goods", A, AccountSubtype.INVENTORY, "1200"),
    acct("1300", "Prepaid Expenses", A, AccountSubtype.PREPAID),
    acct("1310", "Prepaid - Cloud Subscriptions", A, AccountSubtype.PREPAID, "1300"),
    acct("1500", "Fixed Assets", A, AccountSubtype.FIXED_ASSET),
    acct("1510", "Computer Equipment", A, AccountSubtype.FIXED_ASSET, "1500"),
    acct("1520", "Elegoo Carbon 3D Printer", A, AccountSubtype.FIXED_ASSET, "1500"),
    acct("1530", "Soldering & Lab Equipment", A, AccountSubtype.FIXED_ASSET, "1500"),
    acct("1540", "Accumulated Depreciation", A, AccountSubtype.FIXED_ASSET, "1500"),

    # Liabilities
    acct("2000", "Credit Cards", L, AccountSubtype.CREDIT_CARD),
    acct("2010", "Business Credit Card", L, AccountSubtype.CREDIT_CARD, "2000"),
    acct("2100", "Accounts Payable", L, AccountSubtype.ACCOUNTS_PAYABLE),
    acct("2200", "Sales Tax Payable", L, AccountSubtype.ACCRUED_LIABILITY),
    acct("2300", "Accrued Liabilities", L, AccountSubtype.ACCRUED_LIABILITY),
    acct("2400", "Stripe Fees Payable", L, AccountSubtype.ACCRUED_LIABILITY),

    # Equity
    acct("3000", "Owner's Equity", E, AccountSubtype.OWNERS_EQUITY),
    acct("3100", "Owner's Draws", E, AccountSubtype.OWNERS_EQUITY),
    acct("3200", "Owner's Contributions", E, AccountSubtype.OWNERS_EQUITY),
    acct("3900", "Retained Earnings", E, AccountSubtype.RETAINED_EARNINGS),

    # Revenue
    acct("4000", "Service Revenue", R, AccountSubtype.SERVICE_REVENUE),
    acct("4010", "SEO Services", R, AccountSubtype.SERVICE_REVENUE, "4000"),
    acct("4020", "Web Development", R, AccountSubtype.SERVICE_REVENUE, "4000"),
    acct("4030", "Digital Marketing", R, AccountSubtype.SERVICE_REVENUE, "4000"),
    acct("4040", "Business Analysis / Consulting", R, AccountSubtype.SERVICE_REVENUE, "4000"),
    acct("4100", "SaaS Revenue - ClawHub", R, AccountSubtype.SALES),
    acct("4110", "ClawHub Pro Subscriptions", R, AccountSubtype.SALES, "4100"),
    acct("4120", "ClawHub Team Subscriptions", R, AccountSubtype.SALES, "4100"),
    acct("4200", "Hardware Sales", R, AccountSubtype.SALES),
    acct("4210", "LatchPac Validator Sales", R, AccountSubtype.SALES, "4200"),
    acct("4220", "ESP32-Enail Sales", R, AccountSubtype.SALES, "4200"),
    acct("4300", "3D Printing Revenue", R, AccountSubtype.SALES),
    acct("4310", "3D Print - Custom Orders", R, AccountSubtype.SALES, "4300"),
    acct("4320", "3D Print - Product Sales", R, AccountSubtype.SALES, "4300"),
    acct("4400", "OpenClaw / AI Agent Revenue", R, AccountSubtype.SERVICE_REVENUE),
    acct("4900", "Other Income", R, AccountSubtype.OTHER_INCOME),

    # COGS
    acct("5000", "Cost of Goods Sold", X, AccountSubtype.COST_OF_GOODS),
    acct("5010", "COGS - Electronic Components", X, AccountSubtype.COST_OF_GOODS, "5000"),
    acct("5020", "COGS - PCB Fabrication", X, AccountSubtype.COST_OF_GOODS, "5000"),
    acct("5030", "COGS - 3D Printer Filament Used", X, AccountSubtype.COST_OF_GOODS, "5000"),
    acct("5040", "COGS - Packaging & Shipping", X, AccountSubtype.COST_OF_GOODS, "5000"),
    acct("5050", "Stripe Processing Fees", X, AccountSubtype.COST_OF_GOODS, "5000"),

    # Operating Expenses
    acct("6000", "Operating Expenses", X, AccountSubtype.OPERATING_EXPENSE),
    acct("6010", "Cloud Infrastructure", X, AccountSubtype.OPERATING_EXPENSE, "6000"),
    acct("6011", "Cloudflare Workers / Pages", X, AccountSubtype.OPERATING_EXPENSE, "6010"),
    acct("6012", "Domain Registrations", X, AccountSubtype.OPERATING_EXPENSE, "6010"),
    acct("6013", "Hosting & VPS", X, AccountSubtype.OPERATING_EXPENSE, "6010"),
    acct("6020", "AI / API Costs", X, AccountSubtype.OPERATING_EXPENSE, "6000"),
    acct("6021", "Anthropic API", X, AccountSubtype.OPERATING_EXPENSE, "6020"),
    acct("6022", "OpenAI API", X, AccountSubtype.OPERATING_EXPENSE, "6020"),
    acct("6023", "Other AI Services", X, AccountSubtype.OPERATING_EXPENSE, "6020"),
    acct("6030", "Software Subscriptions", X, AccountSubtype.OPERATING_EXPENSE, "6000"),
    acct("6031", "GitHub", X, AccountSubtype.OPERATING_EXPENSE, "6030"),
    acct("6032", "Claude Code / Cursor", X, AccountSubtype.OPERATING_EXPENSE, "6030"),
    acct("6033", "Other SaaS Tools", X, AccountSubtype.OPERATING_EXPENSE, "6030"),
    acct("6040", "Office & Supplies", X, AccountSubtype.OPERATING_EXPENSE, "6000"),
    acct("6050", "Marketing & Advertising", X, AccountSubtype.OPERATING_EXPENSE, "6000"),
    acct("6060", "Professional Services", X, AccountSubtype.OPERATING_EXPENSE, "6000"),
    acct("6061", "Legal", X, AccountSubtype.OPERATING_EXPENSE, "6060"),
    acct("6062", "Accounting / Tax Prep", X, AccountSubtype.OPERATING_EXPENSE, "6060"),
    acct("6070", "Insurance", X, AccountSubtype.OPERATING_EXPENSE, "6000"),
    acct("6080", "Vehicle / Travel", X, AccountSubtype.OPERATING_EXPENSE, "6000"),
    acct("6090", "Meals & Entertainment", X, AccountSubtype.OPERATING_EXPENSE, "6000"),
    acct("6100", "Depreciation Expense", X, AccountSubtype.DEPRECIATION),
    acct("6200", "Bank & Merchant Fees", X, AccountSubtype.OPERATING_EXPENSE, "6000"),

    # Tax
    acct("7000", "Tax Expense", X, AccountSubtype.TAX_EXPENSE),
    acct("7010", "Federal Income Tax", X, AccountSubtype.TAX_EXPENSE, "7000"),
    acct("7020", "State Income Tax (CA)", X, AccountSubtype.TAX_EXPENSE, "7000"),
    acct("7030", "Self-Employment Tax", X, AccountSubtype.TAX_EXPENSE, "7000"),
    acct("7040", "Sales Tax Expense", X, AccountSubtype.TAX_EXPENSE, "7000"),
    acct("7050", "CA Franchise Tax", X, AccountSubtype.TAX_EXPENSE, "7000"),
]


# ===== 2. Kalshi Trading =====
KALSHI_ACCOUNTS = [
    # Assets
    acct("1000", "Cash & Balances", A, AccountSubtype.CASH),
    acct("1010", "Kalshi Account Balance", A, AccountSubtype.CASH, "1000"),
    acct("1020", "Funding Bank Account", A, AccountSubtype.CASH, "1000"),
    acct("1100", "Open Positions", A, AccountSubtype.INVENTORY),
    acct("1110", "Weather Contracts", A, AccountSubtype.INVENTORY, "1100"),
    acct("1120", "Political Contracts", A, AccountSubtype.INVENTORY, "1100"),
    acct("1130", "Other Event Contracts", A, AccountSubtype.INVENTORY, "1100"),

    # Liabilities
    acct("2000", "Liabilities", L, AccountSubtype.ACCRUED_LIABILITY),
    acct("2010", "Taxes Payable on Trading Gains", L, AccountSubtype.ACCRUED_LIABILITY, "2000"),

    # Equity
    acct("3000", "Trading Capital", E, AccountSubtype.OWNERS_EQUITY),
    acct("3100", "Deposits", E, AccountSubtype.OWNERS_EQUITY),
    acct("3200", "Withdrawals", E, AccountSubtype.OWNERS_EQUITY),
    acct("3900", "Retained P&L", E, AccountSubtype.RETAINED_EARNINGS),

    # Revenue
    acct("4000", "Trading Gains", R, AccountSubtype.OTHER_INCOME),
    acct("4010", "Realized Gains - Weather", R, AccountSubtype.OTHER_INCOME, "4000"),
    acct("4020", "Realized Gains - Political", R, AccountSubtype.OTHER_INCOME, "4000"),
    acct("4030", "Realized Gains - Other Events", R, AccountSubtype.OTHER_INCOME, "4000"),
    acct("4100", "Settlement Income", R, AccountSubtype.OTHER_INCOME),

    # Expenses (losses)
    acct("5000", "Trading Losses", X, AccountSubtype.OTHER_EXPENSE),
    acct("5010", "Realized Losses - Weather", X, AccountSubtype.OTHER_EXPENSE, "5000"),
    acct("5020", "Realized Losses - Political", X, AccountSubtype.OTHER_EXPENSE, "5000"),
    acct("5030", "Realized Losses - Other Events", X, AccountSubtype.OTHER_EXPENSE, "5000"),
    acct("5100", "Kalshi Fees", X, AccountSubtype.OTHER_EXPENSE),
    acct("5200", "Settlement Losses", X, AccountSubtype.OTHER_EXPENSE),

    # Tax
    acct("7000", "Tax Expense", X, AccountSubtype.TAX_EXPENSE),
    acct("7010", "Short-Term Capital Gains Tax", X, AccountSubtype.TAX_EXPENSE, "7000"),
]


# ===== 3. Personal =====
PERSONAL_ACCOUNTS = [
    # Assets
    acct("1000", "Cash & Bank Accounts", A, AccountSubtype.CASH),
    acct("1010", "Personal Checking", A, AccountSubtype.CASH, "1000"),
    acct("1020", "Personal Savings", A, AccountSubtype.CASH, "1000"),
    acct("1030", "Cash on Hand", A, AccountSubtype.CASH, "1000"),
    acct("1100", "Investments", A, AccountSubtype.INVENTORY),
    acct("1110", "Brokerage Account", A, AccountSubtype.INVENTORY, "1100"),
    acct("1120", "Crypto Holdings", A, AccountSubtype.INVENTORY, "1100"),
    acct("1200", "Personal Property", A, AccountSubtype.FIXED_ASSET),
    acct("1210", "Vehicle", A, AccountSubtype.FIXED_ASSET, "1200"),
    acct("1220", "Electronics / Gaming", A, AccountSubtype.FIXED_ASSET, "1200"),

    # Liabilities
    acct("2000", "Credit Cards", L, AccountSubtype.CREDIT_CARD),
    acct("2010", "Personal Credit Card", L, AccountSubtype.CREDIT_CARD, "2000"),
    acct("2100", "Loans", L, AccountSubtype.LONG_TERM_DEBT),
    acct("2110", "Vehicle Loan", L, AccountSubtype.LONG_TERM_DEBT, "2100"),
    acct("2120", "Other Loans", L, AccountSubtype.LONG_TERM_DEBT, "2100"),

    # Equity
    acct("3000", "Net Worth", E, AccountSubtype.OWNERS_EQUITY),
    acct("3100", "Opening Balances", E, AccountSubtype.OWNERS_EQUITY),

    # Income
    acct("4000", "Income", R, AccountSubtype.OTHER_INCOME),
    acct("4010", "Owner's Draw from RCR LLC", R, AccountSubtype.OTHER_INCOME, "4000"),
    acct("4020", "Kalshi Withdrawals", R, AccountSubtype.OTHER_INCOME, "4000"),
    acct("4030", "Other Income", R, AccountSubtype.OTHER_INCOME, "4000"),

    # Expenses
    acct("5000", "Housing", X, AccountSubtype.OPERATING_EXPENSE),
    acct("5010", "Rent / Mortgage", X, AccountSubtype.OPERATING_EXPENSE, "5000"),
    acct("5020", "Utilities", X, AccountSubtype.OPERATING_EXPENSE, "5000"),
    acct("5030", "Internet", X, AccountSubtype.OPERATING_EXPENSE, "5000"),
    acct("5100", "Transportation", X, AccountSubtype.OPERATING_EXPENSE),
    acct("5110", "Gas", X, AccountSubtype.OPERATING_EXPENSE, "5100"),
    acct("5120", "Car Insurance", X, AccountSubtype.OPERATING_EXPENSE, "5100"),
    acct("5130", "Maintenance / Repairs", X, AccountSubtype.OPERATING_EXPENSE, "5100"),
    acct("5200", "Food", X, AccountSubtype.OPERATING_EXPENSE),
    acct("5210", "Groceries", X, AccountSubtype.OPERATING_EXPENSE, "5200"),
    acct("5220", "Dining Out", X, AccountSubtype.OPERATING_EXPENSE, "5200"),
    acct("5300", "Health", X, AccountSubtype.OPERATING_EXPENSE),
    acct("5310", "Health Insurance", X, AccountSubtype.OPERATING_EXPENSE, "5300"),
    acct("5320", "Medical / Dental", X, AccountSubtype.OPERATING_EXPENSE, "5300"),
    acct("5400", "Entertainment & Gaming", X, AccountSubtype.OPERATING_EXPENSE),
    acct("5410", "Game Subscriptions (WoW, etc.)", X, AccountSubtype.OPERATING_EXPENSE, "5400"),
    acct("5420", "Game Purchases", X, AccountSubtype.OPERATING_EXPENSE, "5400"),
    acct("5430", "Streaming Services", X, AccountSubtype.OPERATING_EXPENSE, "5400"),
    acct("5500", "Personal Subscriptions", X, AccountSubtype.OPERATING_EXPENSE),
    acct("5600", "Clothing", X, AccountSubtype.OPERATING_EXPENSE),
    acct("5700", "Gifts & Donations", X, AccountSubtype.OPERATING_EXPENSE),
    acct("5800", "Miscellaneous", X, AccountSubtype.OTHER_EXPENSE),

    # Tax
    acct("7000", "Personal Tax", X, AccountSubtype.TAX_EXPENSE),
    acct("7010", "Federal Income Tax", X, AccountSubtype.TAX_EXPENSE, "7000"),
    acct("7020", "CA State Income Tax", X, AccountSubtype.TAX_EXPENSE, "7000"),
]


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

ORGS = [
    {
        "name": "Ridge Cell Repair LLC",
        "fiscal_year_start": 1,
        "currency": "USD",
        "accounts": RCR_ACCOUNTS,
    },
    {
        "name": "Kalshi Trading",
        "fiscal_year_start": 1,
        "currency": "USD",
        "accounts": KALSHI_ACCOUNTS,
    },
    {
        "name": "Personal - Matt Gates",
        "fiscal_year_start": 1,
        "currency": "USD",
        "accounts": PERSONAL_ACCOUNTS,
    },
]


async def seed():
    from sqlalchemy import text

    async with engine.begin() as conn:
        # Import metadata and create tables if they don't exist
        from abacus.models import Base
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Create admin user
        admin = User(
            email="matt@ridgecellrepair.com",
            hashed_password=hash_password("changeme"),
            full_name="Matt Gates",
            role="admin",
            is_active=True,
        )
        session.add(admin)
        await session.flush()

        for org_def in ORGS:
            org = Organization(
                name=org_def["name"],
                fiscal_year_start=org_def["fiscal_year_start"],
                currency=org_def["currency"],
            )
            session.add(org)
            await session.flush()

            # Assign admin to org
            admin.organization_id = admin.organization_id or org.id

            # Build accounts - two passes for parent references
            code_to_id = {}
            # First pass: accounts without parents
            for a in org_def["accounts"]:
                if a["parent_code"] is not None:
                    continue
                account = Account(
                    organization_id=org.id,
                    code=a["code"],
                    name=a["name"],
                    type=a["type"],
                    subtype=a["subtype"],
                    normal_balance="debit" if a["type"] in (A, X) else "credit",
                    is_active=True,
                )
                session.add(account)
                await session.flush()
                code_to_id[a["code"]] = account.id

            # Second pass: accounts with parents
            for a in org_def["accounts"]:
                if a["parent_code"] is None:
                    continue
                account = Account(
                    organization_id=org.id,
                    code=a["code"],
                    name=a["name"],
                    type=a["type"],
                    subtype=a["subtype"],
                    normal_balance="debit" if a["type"] in (A, X) else "credit",
                    parent_id=code_to_id.get(a["parent_code"]),
                    is_active=True,
                )
                session.add(account)
                await session.flush()
                code_to_id[a["code"]] = account.id

            print(f"  Created org '{org_def['name']}' with {len(org_def['accounts'])} accounts")

        await session.commit()
        print("\nDone. Admin user: matt@ridgecellrepair.com / changeme")
        print("CHANGE THE PASSWORD IMMEDIATELY after first login.")


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    asyncio.run(seed())
