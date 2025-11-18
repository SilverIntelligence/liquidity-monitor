"""PostgreSQL loader with ON CONFLICT handling and ETL logging."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class PostgresLoader:
    """Load transformed data into PostgreSQL with conflict handling."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize loader.

        Args:
            session: Async database session
        """
        self.session = session

    async def load_etf_flows(
        self, records: list[dict[str, Any]], etl_id: str, job: str, source: str
    ) -> int:
        """Load ETF flow records with ON CONFLICT DO UPDATE.

        Args:
            records: Transformed records
            etl_id: ETL run identifier
            job: Job name
            source: Source name

        Returns:
            Number of rows loaded
        """
        if not records:
            return 0

        # Use raw SQL for ON CONFLICT
        insert_sql = """
            INSERT INTO liquidity.etf_flows (ds, fund, nav, aum, shares_in, shares_out, net_shares, price)
            VALUES (:ds, :fund, :nav, :aum, :shares_in, :shares_out, :net_shares, :price)
            ON CONFLICT (ds, fund) DO UPDATE SET
                nav = EXCLUDED.nav,
                aum = EXCLUDED.aum,
                shares_in = EXCLUDED.shares_in,
                shares_out = EXCLUDED.shares_out,
                net_shares = EXCLUDED.net_shares,
                price = EXCLUDED.price
        """

        for record in records:
            await self.session.execute(text(insert_sql), record)

        await self.session.commit()
        return len(records)

    async def load_inventory(
        self, records: list[dict[str, Any]], etl_id: str, job: str, source: str
    ) -> int:
        """Load inventory records.

        Args:
            records: Transformed records
            etl_id: ETL run identifier
            job: Job name
            source: Source name

        Returns:
            Number of rows loaded
        """
        if not records:
            return 0

        insert_sql = """
            INSERT INTO liquidity.inventory (ds, venue, category, tonnes_oz, change_oz)
            VALUES (:ds, :venue, :category, :tonnes_oz, :change_oz)
            ON CONFLICT (ds, venue, category) DO UPDATE SET
                tonnes_oz = EXCLUDED.tonnes_oz,
                change_oz = EXCLUDED.change_oz
        """

        for record in records:
            await self.session.execute(text(insert_sql), record)

        await self.session.commit()
        return len(records)

    async def load_futures(
        self, records: list[dict[str, Any]], etl_id: str, job: str, source: str
    ) -> int:
        """Load futures positioning records.

        Args:
            records: Transformed records
            etl_id: ETL run identifier
            job: Job name
            source: Source name

        Returns:
            Number of rows loaded
        """
        if not records:
            return 0

        insert_sql = """
            INSERT INTO liquidity.futures_positioning (ds, venue, contract, open_interest, volume)
            VALUES (:ds, :venue, :contract, :open_interest, :volume)
            ON CONFLICT (ds, venue, contract) DO UPDATE SET
                open_interest = EXCLUDED.open_interest,
                volume = EXCLUDED.volume
        """

        for record in records:
            await self.session.execute(text(insert_sql), record)

        await self.session.commit()
        return len(records)

    async def log_etl_run(
        self,
        etl_id: str,
        job: str,
        source: str,
        started_at: datetime,
        finished_at: datetime | None,
        status: str,
        rows: int | None = None,
        error: str | None = None,
    ) -> None:
        """Log ETL run to liquidity.etl_runs.

        Args:
            etl_id: Unique ETL run ID
            job: Job name
            source: Source name
            started_at: Start timestamp
            finished_at: Finish timestamp
            status: Status (success/failure/running)
            rows: Number of rows processed
            error: Error message if failed
        """
        insert_sql = """
            INSERT INTO liquidity.etl_runs (etl_id, job, source, started_at, finished_at, status, rows, error)
            VALUES (:etl_id, :job, :source, :started_at, :finished_at, :status, :rows, :error)
        """

        await self.session.execute(
            text(insert_sql),
            {
                "etl_id": etl_id,
                "job": job,
                "source": source,
                "started_at": started_at,
                "finished_at": finished_at,
                "status": status,
                "rows": rows,
                "error": error,
            },
        )
        await self.session.commit()


def generate_etl_id(job: str, source: str, timestamp: datetime) -> str:
    """Generate idempotent ETL ID.

    Args:
        job: Job name
        source: Source name
        timestamp: Job timestamp

    Returns:
        ETL ID string
    """
    ts_str = timestamp.strftime("%Y%m%d%H%M")
    return f"{job}:{source}:{ts_str}"
