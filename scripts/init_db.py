"""Initialize database with seed data."""

import asyncio
import sys
from datetime import datetime

from sqlalchemy import select

from db.models import Metal, Source, FormulaVersion
from db.session import AsyncSessionLocal
from scoring.composite import DEFAULT_WEIGHTS


async def init_database() -> None:
    """Initialize database with seed data."""
    print(f"[{datetime.utcnow()}] Initializing database...")

    async with AsyncSessionLocal() as session:
        try:
            # Create metals
            metals_data = [
                {"symbol": "XAU", "name": "Gold"},
                {"symbol": "XAG", "name": "Silver"},
            ]

            for metal_data in metals_data:
                result = await session.execute(
                    select(Metal).where(Metal.symbol == metal_data["symbol"])
                )
                existing = result.scalar_one_or_none()

                if existing is None:
                    metal = Metal(**metal_data)
                    session.add(metal)
                    print(f"[{datetime.utcnow()}] Created metal: {metal_data['symbol']}")
                else:
                    print(
                        f"[{datetime.utcnow()}] Metal already exists: {metal_data['symbol']}"
                    )

            await session.commit()

            # Create default formula version
            result = await session.execute(
                select(FormulaVersion).where(FormulaVersion.weights == DEFAULT_WEIGHTS)
            )
            existing_formula = result.scalar_one_or_none()

            if existing_formula is None:
                formula = FormulaVersion(
                    description="Default liquidity index formula v1", weights=DEFAULT_WEIGHTS
                )
                session.add(formula)
                await session.commit()
                await session.refresh(formula)
                print(f"[{datetime.utcnow()}] Created formula version: {formula.formula_id}")
            else:
                print(
                    f"[{datetime.utcnow()}] Formula already exists: {existing_formula.formula_id}"
                )

            # Create initial sources (will be created by ingestors on first run)
            # This is just for reference
            print(f"[{datetime.utcnow()}] Database initialization complete")

        except Exception as e:
            print(f"[{datetime.utcnow()}] ERROR: {e}", file=sys.stderr)
            await session.rollback()
            raise


async def main() -> None:
    """Main entry point."""
    await init_database()


if __name__ == "__main__":
    asyncio.run(main())
