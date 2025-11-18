"""Script to compute component and composite scores."""

import asyncio
import sys
from datetime import datetime

from sqlalchemy import select

from db.models import Metal
from db.session import AsyncSessionLocal
from scoring.components import score_all_components_and_save
from scoring.composite import get_or_create_formula, compute_and_save_composite


async def compute_scores_for_all_metals() -> None:
    """Compute scores for all metals."""
    print(f"[{datetime.utcnow()}] Computing scores...")

    async with AsyncSessionLocal() as session:
        try:
            # Get or create default formula
            formula_id = await get_or_create_formula(session)
            print(f"[{datetime.utcnow()}] Using formula ID: {formula_id}")

            # Get all metals
            result = await session.execute(select(Metal))
            metals = result.scalars().all()

            for metal in metals:
                print(f"[{datetime.utcnow()}] Processing {metal.symbol}...")

                try:
                    # Compute component scores
                    component_scores = await score_all_components_and_save(
                        session, metal.metal_id, formula_id
                    )
                    print(f"[{datetime.utcnow()}] Component scores: {component_scores}")

                    # Compute composite score
                    composite_score = await compute_and_save_composite(
                        session, metal.metal_id, formula_id
                    )
                    print(
                        f"[{datetime.utcnow()}] {metal.symbol} composite score: {composite_score}"
                    )

                except Exception as e:
                    print(
                        f"[{datetime.utcnow()}] ERROR computing scores for {metal.symbol}: {e}",
                        file=sys.stderr,
                    )

            print(f"[{datetime.utcnow()}] Score computation complete")

        except Exception as e:
            print(f"[{datetime.utcnow()}] ERROR: {e}", file=sys.stderr)
            raise


async def main() -> None:
    """Main entry point."""
    await compute_scores_for_all_metals()


if __name__ == "__main__":
    asyncio.run(main())
