"""Backfill historical data for liquidity monitor."""

import argparse
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from db.session import AsyncSessionLocal
from etl.extractors.extract_etf import ETFExtractor
from etl.transformers.transform_etf import transform_gld, transform_slv, transform_pslv
from etl.loaders.load_postgres import PostgresLoader, generate_etl_id
from etl.index.compute import LiquidityIndexComputer

logging.basicConfig(
    level=logging.INFO,
    format='{"ts": "%(asctime)s", "level": "%(levelname)s", "msg": "%(message)s"}',
)
logger = logging.getLogger(__name__)


async def backfill_etf_flows(days: int, delay_seconds: int = 60) -> None:
    """Backfill ETF flow data.

    Args:
        days: Number of days to backfill
        delay_seconds: Delay between requests to respect rate limits
    """
    job = "etf_flows_backfill"
    logger.info(f'{{"job": "{job}", "step": "start", "days": {days}}}')

    async with AsyncSessionLocal() as session:
        loader = PostgresLoader(session)

        # Process each ETF source
        sources = [
            ("GLD", transform_gld),
            ("SLV", transform_slv),
            ("PSLV", transform_pslv),
        ]

        async with ETFExtractor() as extractor:
            for source, transformer in sources:
                started_at = datetime.utcnow()
                etl_id = generate_etl_id(job, source, started_at)

                try:
                    # Extract
                    if source == "GLD":
                        raw_data = await extractor.extract_gld()
                    elif source == "SLV":
                        raw_data = await extractor.extract_slv()
                    elif source == "PSLV":
                        raw_data = await extractor.extract_pslv()
                    else:
                        continue

                    # Transform
                    records = transformer(raw_data)

                    # Filter to requested date range
                    cutoff_date = (datetime.utcnow().date() - timedelta(days=days))
                    records = [r for r in records if r["ds"] >= cutoff_date]

                    # Load
                    rows = await loader.load_etf_flows(records, etl_id, job, source)

                    # Log success
                    await loader.log_etl_run(
                        etl_id=etl_id,
                        job=job,
                        source=source,
                        started_at=started_at,
                        finished_at=datetime.utcnow(),
                        status="success",
                        rows=rows,
                    )

                    logger.info(
                        f'{{"job": "{job}", "source": "{source}", "status": "success", "rows": {rows}, "etl_id": "{etl_id}"}}'
                    )

                    # Polite delay between sources
                    if delay_seconds > 0:
                        logger.info(f'{{"job": "{job}", "step": "delay", "seconds": {delay_seconds}}}')
                        await asyncio.sleep(delay_seconds)

                except Exception as e:
                    await loader.log_etl_run(
                        etl_id=etl_id,
                        job=job,
                        source=source,
                        started_at=started_at,
                        finished_at=datetime.utcnow(),
                        status="failure",
                        error=str(e),
                    )

                    logger.error(
                        f'{{"job": "{job}", "source": "{source}", "status": "failure", "error": "{str(e)}", "etl_id": "{etl_id}"}}'
                    )


async def backfill_inventory(days: int, delay_seconds: int = 60) -> None:
    """Backfill inventory data (COMEX/LBMA).

    Args:
        days: Number of days to backfill
        delay_seconds: Delay between requests
    """
    job = "inventory_backfill"
    logger.info(f'{{"job": "{job}", "step": "start", "days": {days}}}')

    # Placeholder for future COMEX/LBMA extractors
    logger.warning(f'{{"job": "{job}", "status": "not_implemented"}}')


async def backfill_futures(days: int, delay_seconds: int = 60) -> None:
    """Backfill futures positioning data (CME).

    Args:
        days: Number of days to backfill
        delay_seconds: Delay between requests
    """
    job = "futures_backfill"
    logger.info(f'{{"job": "{job}", "step": "start", "days": {days}}}')

    # Placeholder for future CME futures extractor
    logger.warning(f'{{"job": "{job}", "status": "not_implemented"}}')


async def backfill_index(days: int) -> None:
    """Recompute liquidity index for historical dates.

    Args:
        days: Number of days to recompute
    """
    job = "index_backfill"
    logger.info(f'{{"job": "{job}", "step": "start", "days": {days}}}')

    async with AsyncSessionLocal() as session:
        computer = LiquidityIndexComputer(session)

        # Compute index for each hour in the backfill period
        start_date = datetime.utcnow() - timedelta(days=days)
        current_ts = start_date.replace(minute=0, second=0, microsecond=0)
        end_ts = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

        count = 0
        errors = 0

        while current_ts <= end_ts:
            try:
                index_data = await computer.compute_index(current_ts)
                await computer.save_index(index_data)

                if count % 24 == 0:  # Log progress daily
                    logger.info(
                        f'{{"job": "{job}", "ts": "{current_ts.isoformat()}", "li_raw": {index_data["li_raw"]}, "count": {count}}}'
                    )

                count += 1
            except Exception as e:
                errors += 1
                logger.error(f'{{"job": "{job}", "ts": "{current_ts.isoformat()}", "error": "{str(e)}"}}')

            # Move to next hour
            current_ts += timedelta(hours=1)

        logger.info(f'{{"job": "{job}", "status": "complete", "count": {count}, "errors": {errors}}}')


async def run_backfill(days: int, delay_seconds: int = 60) -> None:
    """Run complete backfill process.

    Order: inventory → ETF → futures → index recompute

    Args:
        days: Number of days to backfill (30-90 recommended)
        delay_seconds: Delay between requests to respect rate limits
    """
    logger.info(f'{{"backfill": "start", "days": {days}, "delay_seconds": {delay_seconds}}}')

    # 1. Inventory (COMEX/LBMA)
    await backfill_inventory(days, delay_seconds)

    # 2. ETF flows
    await backfill_etf_flows(days, delay_seconds)

    # 3. Futures positioning
    await backfill_futures(days, delay_seconds)

    # 4. Recompute index
    await backfill_index(days)

    logger.info(f'{{"backfill": "complete", "days": {days}}}')


def main() -> None:
    """Main entry point for backfill script."""
    parser = argparse.ArgumentParser(description="Backfill historical liquidity data")
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Number of days to backfill (default: 90)",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=60,
        help="Delay between requests in seconds (default: 60)",
    )

    args = parser.parse_args()

    if args.days < 1 or args.days > 365:
        logger.error(f'{{"error": "days must be between 1 and 365", "days": {args.days}}}')
        return

    asyncio.run(run_backfill(args.days, args.delay))


if __name__ == "__main__":
    main()
