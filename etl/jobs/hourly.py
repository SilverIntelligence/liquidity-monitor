"""APScheduler-based job scheduler with circuit breaker and retries."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

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


class CircuitBreaker:
    """Simple circuit breaker for data source failures."""

    def __init__(self, threshold: int = 3, timeout_minutes: int = 60) -> None:
        """Initialize circuit breaker.

        Args:
            threshold: Number of failures before opening
            timeout_minutes: Minutes to wait before retry
        """
        self.threshold = threshold
        self.timeout = timeout_minutes * 60
        self.failures: dict[str, int] = {}
        self.opened_at: dict[str, datetime] = {}

    def record_failure(self, source: str) -> None:
        """Record a failure for a source.

        Args:
            source: Source name
        """
        self.failures[source] = self.failures.get(source, 0) + 1
        if self.failures[source] >= self.threshold:
            self.opened_at[source] = datetime.utcnow()
            logger.warning(f'{{"source": "{source}", "status": "circuit_open", "failures": {self.failures[source]}}}')

    def record_success(self, source: str) -> None:
        """Record a success for a source.

        Args:
            source: Source name
        """
        self.failures[source] = 0
        if source in self.opened_at:
            del self.opened_at[source]
            logger.info(f'{{"source": "{source}", "status": "circuit_closed"}}')

    def is_open(self, source: str) -> bool:
        """Check if circuit is open for a source.

        Args:
            source: Source name

        Returns:
            True if circuit is open
        """
        if source not in self.opened_at:
            return False

        # Check if timeout has passed
        elapsed = (datetime.utcnow() - self.opened_at[source]).total_seconds()
        if elapsed > self.timeout:
            logger.info(f'{{"source": "{source}", "status": "circuit_retry"}}')
            del self.opened_at[source]
            return False

        return True


# Global circuit breaker
circuit_breaker = CircuitBreaker()


async def run_etf_job() -> None:
    """Run ETF extraction job with retries."""
    job = "etf_flows"
    started_at = datetime.utcnow()

    logger.info(f'{{"job": "{job}", "step": "start", "ts": "{started_at.isoformat()}"}}')

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
                if circuit_breaker.is_open(source):
                    logger.warning(f'{{"job": "{job}", "source": "{source}", "status": "skipped_circuit_open"}}')
                    continue

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

                    circuit_breaker.record_success(source)

                    logger.info(
                        f'{{"job": "{job}", "source": "{source}", "status": "success", "rows": {rows}, "etl_id": "{etl_id}"}}'
                    )

                except Exception as e:
                    circuit_breaker.record_failure(source)

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


async def compute_liquidity_index() -> None:
    """Compute liquidity index hourly."""
    job = "compute_index"
    started_at = datetime.utcnow()

    logger.info(f'{{"job": "{job}", "step": "start", "ts": "{started_at.isoformat()}"}}')

    async with AsyncSessionLocal() as session:
        computer = LiquidityIndexComputer(session)

        try:
            # Compute index
            index_data = await computer.compute_index(started_at)

            # Save to database
            await computer.save_index(index_data)

            logger.info(
                f'{{"job": "{job}", "status": "success", "li_raw": {index_data["li_raw"]}, "li_z": {index_data["li_z"]}, "stale": {len(index_data["stale_components"])}}}'
            )

        except Exception as e:
            logger.error(f'{{"job": "{job}", "status": "failure", "error": "{str(e)}"}}')


def start_scheduler() -> AsyncIOScheduler:
    """Start APScheduler with all jobs.

    Returns:
        Running scheduler instance
    """
    scheduler = AsyncIOScheduler()

    # ETF flows - hourly at top of hour
    scheduler.add_job(
        run_etf_job,
        CronTrigger(minute=0),
        id="etf_flows",
        name="ETF Flows Extraction",
        replace_existing=True,
    )

    # Compute index - every 15 minutes
    scheduler.add_job(
        compute_liquidity_index,
        CronTrigger(minute="*/15"),
        id="compute_index",
        name="Liquidity Index Computation",
        replace_existing=True,
    )

    scheduler.start()
    logger.info('{"scheduler": "started", "jobs": ["etf_flows", "compute_index"]}')

    return scheduler


async def main() -> None:
    """Main entry point for scheduler."""
    scheduler = start_scheduler()

    try:
        # Keep running
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info('{"scheduler": "shutdown"}')


if __name__ == "__main__":
    asyncio.run(main())
